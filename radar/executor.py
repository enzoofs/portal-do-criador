"""
radar/executor.py — Roda as perguntas do cliente em todos os provedores.

Cada (pergunta x provedor x repetição) vira uma consulta independente, em
paralelo. As IAs variam a resposta a cada chamada; repetir a mesma pergunta
dá uma medição mais estável.
"""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from config import settings
from custos import contador
from radar import analise, auditoria, cruzamento, extrator, rastreador
from radar.modelos import Resposta
from radar.provedores import provedores_reais
from radar.provedores.demo_provedor import provedores_demo


def carregar_cliente(cliente_id: str) -> dict:
    caminho = settings.CLIENTES_DIR / f"{cliente_id}.json"
    return json.loads(caminho.read_text(encoding="utf-8"))


def _consultar(provedor, pergunta: dict, cliente: dict, nome_extrator: str) -> Resposta:
    try:
        r = provedor.perguntar(pergunta["texto"], pergunta["tipo"], cliente)
    except Exception as e:  # uma falha não derruba o relatório inteiro
        r = Resposta(provedor.nome, provedor.modelo, pergunta["texto"], pergunta["tipo"],
                     erro=f"{type(e).__name__}: {e}")
    try:
        return extrator.analisar(r, cliente, nome_extrator)
    except Exception as e:
        r.erro = f"extração falhou — {type(e).__name__}: {e}"
        return r


def _rastrear_site(cliente: dict, demo: bool, progresso) -> dict | None:
    """Rastreamento do site que acompanha o radar. Se falhar, o radar segue sem ele.
    Começa conferindo também as páginas que as IAs citaram no radar anterior."""
    runs = sorted((settings.RUNS_DIR / cliente["id"]).glob("*.json"))
    extras = cruzamento.urls_citadas(json.loads(runs[-1].read_text(encoding="utf-8"))) if runs else []
    try:
        return rastreador.rastrear(cliente, demo=demo, extras=extras, progresso=lambda t: progresso(f"  [site] {t}"))
    except RuntimeError as e:          # demonstração sem site gerado
        progresso(f"Rastreamento do site pulado: {e}")
    except Exception as e:  # o radar vale mesmo sem o rastreamento
        progresso(f"Rastreamento do site falhou: {type(e).__name__}: {e}")
    return None


def _fechar_rastreio(futuro, cliente: dict, respostas: list[dict], demo: bool, progresso) -> str | None:
    """Espera o rastreamento, confere as páginas citadas neste radar que ele não leu e salva."""
    r = futuro.result() if futuro else None
    if r is None:
        return None
    try:
        novas = rastreador.complementar(cliente, r, cruzamento.urls_citadas({"cliente": cliente, "respostas": respostas}), demo=demo)
        if novas:
            progresso(f"  [site] {novas} página(s) citada(s) pelas IAs conferida(s) fora do rastreamento")
    except Exception as e:  # sem o complemento, o rastreamento continua valendo
        progresso(f"  [site] conferência das páginas citadas falhou: {type(e).__name__}: {e}")
    return rastreador.salvar(r).name


def _ler_concorrentes(metricas: dict, progresso) -> list[dict]:
    """Uma leitura de cada página de concorrente que as IAs citaram, para comparar com as do cliente."""
    urls = [p["url"] for p in metricas["paginas"] if p["tipo"] == "concorrente"][:10]
    if not urls:
        return []
    progresso(f"Lendo {len(urls)} página(s) de concorrentes que as IAs citaram")
    try:
        return rastreador.ler_externas(urls)
    except Exception as e:  # a comparação é um extra: o radar vale sem ela
        progresso(f"Leitura das páginas de concorrentes falhou: {type(e).__name__}: {e}")
        return []


def executar(cliente_id: str, demo: bool = False, filtro: list[str] | None = None,
             repeticoes: int = 1, progresso=print) -> dict:
    return executar_cliente(carregar_cliente(cliente_id), demo, filtro, repeticoes, progresso)


def executar_cliente(cliente: dict, demo: bool = False, filtro: list[str] | None = None,
                     repeticoes: int = 1, progresso=print, pasta=None, auditar: bool = True) -> dict:
    """Roda o radar para um cliente e salva em `pasta` (padrão: data/runs/<cliente>).
    Com `auditar`, também confere o site: auditoria da página inicial e rastreamento de todas as
    páginas (este em paralelo às consultas, porque não disputa nada com elas)."""
    provedores = [] if demo else provedores_reais(filtro)
    if not provedores:
        if not demo:
            progresso("Nenhuma chave de API configurada — rodando em modo DEMONSTRAÇÃO.")
        demo = True
        provedores = provedores_demo()
    if not demo:
        contador.checar()  # aborta antes de qualquer consulta se não houve --confirmar
    nome_extrator = "heuristica" if demo else extrator.extrator_disponivel()
    rastreio = None
    if auditar:
        fundo = ThreadPoolExecutor(max_workers=1)
        rastreio = fundo.submit(_rastrear_site, cliente, demo, progresso)
        fundo.shutdown(wait=False)

    tarefas = [(p, q) for p in provedores for q in cliente["perguntas"] for _ in range(repeticoes)]
    progresso(f"{len(tarefas)} consultas em {', '.join(p.nome for p in provedores)} "
              f"(extrator: {nome_extrator})")

    respostas: list[Resposta] = []
    # A primeira consulta vai sozinha: se a conta do provedor estiver bloqueada (chave errada,
    # conta não verificada, sem saldo), para aqui em vez de repetir o erro em todas.
    if tarefas and not demo:
        primeira = _consultar(*tarefas[0], cliente, nome_extrator)
        if primeira.erro and any(s in primeira.erro for s in ("40104", "401", "403", "verify", "insufficient")):
            raise RuntimeError(f"{primeira.provedor} recusou a consulta: {primeira.erro}")
        respostas.append(primeira)
        tarefas = tarefas[1:]
    with ThreadPoolExecutor(max_workers=settings.MAX_WORKERS) as pool:
        futuros = [pool.submit(_consultar, p, q, cliente, nome_extrator) for p, q in tarefas]
        for i, fut in enumerate(as_completed(futuros), start=1):
            r = fut.result()
            respostas.append(r)
            status = "ERRO " + r.erro if r.erro else ("marca ✓" if r.marca_mencionada else "marca ✗")
            progresso(f"  [{i}/{len(tarefas)}] {r.provedor}: {r.pergunta[:55]}… {status}")

    # Auditoria técnica do site (pulada no modo demo, que roda offline)
    checks = [] if demo or not auditar else auditoria.auditar(cliente["site"])
    if checks:
        progresso(f"Auditoria técnica: {sum(c['ok'] for c in checks)}/{len(checks)} itens ok")

    ordem = {q["texto"]: i for i, q in enumerate(cliente["perguntas"])}
    respostas.sort(key=lambda r: (ordem.get(r.pergunta, 99), r.provedor))
    metricas = analise.calcular(respostas, cliente, checks)   # tira listas e rankings das empresas citadas
    dicts = [r.to_dict() for r in respostas]

    resultado = {
        "cliente": cliente,
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "demo": demo,
        "provedores": {p.nome: p.modelo for p in provedores},
        "extrator": nome_extrator,
        "repeticoes": repeticoes,
        "auditoria": checks,
        "rastreio": _fechar_rastreio(rastreio, cliente, dicts, demo, progresso),   # arquivo em data/rastreios/<cliente>/
        "paginas_concorrentes": _ler_concorrentes(metricas, progresso) if auditar and not demo else [],
        "metricas": metricas,
        "respostas": dicts,
    }

    pasta = pasta or settings.RUNS_DIR / cliente["id"]
    pasta.mkdir(parents=True, exist_ok=True)
    carimbo = datetime.now().strftime("%Y%m%d-%H%M%S") + ("-demo" if demo else "")
    caminho = pasta / f"{carimbo}.json"
    caminho.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    resultado["_arquivo"] = str(caminho)
    return resultado
