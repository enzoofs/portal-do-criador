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
from radar import analise, auditoria, extrator
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


def executar(cliente_id: str, demo: bool = False, filtro: list[str] | None = None,
             repeticoes: int = 1, progresso=print) -> dict:
    return executar_cliente(carregar_cliente(cliente_id), demo, filtro, repeticoes, progresso)


def executar_cliente(cliente: dict, demo: bool = False, filtro: list[str] | None = None,
                     repeticoes: int = 1, progresso=print, pasta=None, auditar: bool = True) -> dict:
    """Roda o radar para um cliente e salva em `pasta` (padrão: data/runs/<cliente>)."""
    provedores = [] if demo else provedores_reais(filtro)
    if not provedores:
        if not demo:
            progresso("Nenhuma chave de API configurada — rodando em modo DEMONSTRAÇÃO.")
        demo = True
        provedores = provedores_demo()
    if not demo:
        contador.checar()  # aborta antes de qualquer consulta se não houve --confirmar
    nome_extrator = "heuristica" if demo else extrator.extrator_disponivel()

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

    resultado = {
        "cliente": cliente,
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "demo": demo,
        "provedores": {p.nome: p.modelo for p in provedores},
        "extrator": nome_extrator,
        "repeticoes": repeticoes,
        "auditoria": checks,
        "metricas": analise.calcular(respostas, cliente, checks),
        "respostas": [r.to_dict() for r in respostas],
    }

    pasta = pasta or settings.RUNS_DIR / cliente["id"]
    pasta.mkdir(parents=True, exist_ok=True)
    carimbo = datetime.now().strftime("%Y%m%d-%H%M%S") + ("-demo" if demo else "")
    caminho = pasta / f"{carimbo}.json"
    caminho.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    resultado["_arquivo"] = str(caminho)
    return resultado
