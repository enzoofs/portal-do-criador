"""
main.py — Ponto de entrada do Portal do Criador.

    python main.py radar exemplo              # usa as IAs com chave no .env
    python main.py radar exemplo --demo       # respostas fictícias, sem custo
    python main.py radar exemplo --ias chatgpt,claude --repeticoes 2
    python main.py relatorio data/runs/exemplo/<arquivo>.json   # refaz só o HTML
    python main.py rastrear exemplo --demo      # percorre o site como um robô de IA (grátis)

    python main.py pauta exemplo                # pauta de artigos a partir do radar
    python main.py escrever exemplo --temas 1,2 # rascunhos para aprovação
    python main.py wordpress exemplo todos      # envia como rascunho ao WordPress
    python main.py indexnow exemplo https://.../post/
    python main.py exportar exemplo             # .zip com todos os dados do cliente
    python main.py esquecer exemplo             # lista os dados do cliente; --confirmar apaga
"""

import argparse
import json
import sys
from pathlib import Path

import custos
import orcamento
from config import settings
from conteudo import fluxo, publicador
from conteudo import pauta as pauta_mod
from radar import analise, executor, rastreador, relatorio
from radar.modelos import Fonte, Resposta

# --------------------------------------------------------------------------
# Trava de custo: nada pago roda sem estimativa + --confirmar, sempre com teto
# --------------------------------------------------------------------------

def _autorizar(args, linhas: list[tuple[str, float]]):
    total = sum(v for _, v in linhas)
    print("Estimativa de custo (aproximada):")
    for nome, valor in linhas:
        print(f"  {nome:<58} US$ {valor:6.2f}")
    print(f"  {'TOTAL':<58} US$ {total:6.2f}   (teto desta execução: US$ {args.limite:.2f})")
    if total > args.limite:
        print(f"  ATENÇÃO: a estimativa passa do teto; a execução para ao gastar US$ {args.limite:.2f}.")
    if not args.confirmar:
        sys.exit("\nNada foi executado. Para rodar, repita o comando com --confirmar "
                 "(e --limite N para mudar o teto).")
    custos.contador.iniciar(args.limite)


def _custo_real(tipo: str, cliente_id: str) -> dict:
    r = custos.contador.resumo()
    print(f"Custo real: US$ {r['total_usd']:.2f} em {r['chamadas']} chamada(s) pagas")
    custos.anotar_gasto(tipo, cliente_id, r["total_usd"])
    return r


def cmd_radar(args):
    filtro = args.ias.split(",") if args.ias else None
    if not args.demo:
        _autorizar(args, orcamento.radar(args.cliente, filtro, args.repeticoes))

    resultado = executor.executar(args.cliente, demo=args.demo, filtro=filtro,
                                  repeticoes=args.repeticoes)
    r = resultado["metricas"]["resumo"]
    print(f"\nVisibilidade: {r['visibilidade']}% ({r['mencoes']}/{r['respostas_descoberta']}) · "
          f"erros: {r['erros']}")
    if not args.demo:
        resultado["custo"] = _custo_real("radar", args.cliente)
        Path(resultado["_arquivo"]).write_text(json.dumps(
            {k: v for k, v in resultado.items() if k != "_arquivo"}, ensure_ascii=False, indent=2),
            encoding="utf-8")
    print(f"Dados:     {resultado['_arquivo']}")
    print(f"Relatório: {relatorio.salvar(resultado, rastreador.do_run(resultado))}")
    if not args.demo:
        import guias
        escritos = guias.gerar(resultado["cliente"], resultado, rastreador.do_run(resultado))
        print(f"Guias:     {len(escritos)} em entregas/{args.cliente}/")


def cmd_guias(args):
    """Refaz os guias do plano a partir do último radar real (os escritos à mão ficam como estão)."""
    import guias
    run = _carregar_run(args.cliente, demo=False)
    if not run:
        sys.exit("Nenhum radar real para este cliente. Rode: python main.py radar <cliente> --confirmar")
    for p in guias.gerar(executor.carregar_cliente(args.cliente), run, rastreador.do_run(run) or rastreador.ultimo(args.cliente)):
        print(p)


def cmd_relatorio(args):
    caminho = Path(args.arquivo)
    resultado = json.loads(caminho.read_text(encoding="utf-8"))
    # Recalcula as métricas com a versão atual da análise (sem chamar nenhuma IA)
    respostas = [Resposta(**{**r, "fontes": [Fonte(**f) for f in r["fontes"]]})
                 for r in resultado["respostas"]]
    resultado["metricas"] = analise.calcular(respostas, resultado["cliente"],
                                             resultado.get("auditoria", []))
    resultado["respostas"] = [r.to_dict() for r in respostas]   # já sem listas/rankings como empresa
    caminho.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    print(relatorio.salvar(resultado, rastreador.do_run(resultado)))   # com o rastreamento feito junto com o radar


def cmd_rastrear(args):
    from radar import cruzamento
    run = _carregar_run(args.cliente, demo=True)
    try:
        r = rastreador.rastrear(executor.carregar_cliente(args.cliente), limite=args.limite, demo=args.demo,
                                extras=cruzamento.urls_citadas(run) if run else None)
    except RuntimeError as e:
        sys.exit(str(e))
    caminho = rastreador.salvar(r)
    for p in rastreador.problemas(r):
        print(f"  {p['nivel']:<5}  {p['titulo']} ({p['total']})")
    if r["parou_no_limite"]:
        print(f"Parou no limite de {r['limite']} páginas; use --limite para ler mais.")
    print(f"Dados: {caminho}")


def _carregar_run(cliente_id: str, demo: bool) -> dict | None:
    caminho = pauta_mod.ultimo_radar(cliente_id, incluir_demo=demo)
    if not caminho:
        return None
    run = json.loads(caminho.read_text(encoding="utf-8"))
    run["_arquivo"] = str(caminho)
    return run


def _pasta_pauta(args) -> Path:
    pasta = Path(args.pauta) if args.pauta else pauta_mod.ultima_pauta(args.cliente, incluir_demo=True)
    if not pasta or not (pasta / "pauta.json").exists():
        sys.exit("Nenhuma pauta encontrada. Rode: python main.py pauta <cliente>")
    return pasta


def cmd_pauta(args):
    cliente = executor.carregar_cliente(args.cliente)
    run = _carregar_run(args.cliente, args.demo)
    print(f"Radar usado: {run['_arquivo'] if run else 'nenhum'}")
    if not args.demo:
        _autorizar(args, orcamento.pauta())
    pauta = pauta_mod.gerar_pauta(cliente, run, demo=args.demo)
    for i, t in enumerate(pauta["temas"], start=1):
        print(f"  {i}. [P{t['prioridade']}] {t['titulo']}")
    central = fluxo.atualizar_central(Path(pauta["_pasta"]), cliente)
    print(f"Central: {central}")
    if not args.demo:
        _custo_real("pauta", args.cliente)


def cmd_escrever(args):
    cliente = executor.carregar_cliente(args.cliente)
    pasta = _pasta_pauta(args)
    demo = json.loads((pasta / "pauta.json").read_text(encoding="utf-8"))["demo"]
    numeros = [int(n) for n in args.temas.split(",")] if args.temas else None
    if not demo:
        total = len(json.loads((pasta / "pauta.json").read_text(encoding="utf-8"))["temas"])
        _autorizar(args, orcamento.artigos(len(numeros) if numeros else total))
    central = fluxo.escrever_pauta(pasta, cliente, _carregar_run(args.cliente, demo), numeros)
    print(f"Central: {central}")
    if not demo:
        _custo_real("artigos", args.cliente)


def cmd_site(args):
    from site_cliente import gerador
    pasta = gerador.gerar(args.cliente, previa=not args.publicar, com_pendencias=args.com_pendencias)
    paginas = sorted(p.relative_to(pasta).as_posix() for p in pasta.rglob("index.html"))
    print(f"{'Versão para publicar' if args.publicar else 'Prévia'}: {pasta} ({len(paginas)} páginas)")
    for p in paginas:
        print(f"  /{p.removesuffix('index.html')}")


def cmd_wordpress(args):
    cliente = executor.carregar_cliente(args.cliente)
    pasta = _pasta_pauta(args)
    artigos = [a for a in fluxo.carregar_artigos(pasta) if args.slug in ("todos", a["slug"])]
    if not artigos:
        sys.exit(f"Nenhum artigo com slug '{args.slug}' em {pasta}")
    for a in artigos:
        if a["demo"]:
            print(f"  – {a['slug']}: artigo de demonstração, não enviado")
            continue
        try:
            if args.publicar:   # publicar direto só existe no WordPress (e só sem pendências)
                a["wordpress"] = publicador.enviar_wordpress(a, cliente, status="publish")
            else:
                from conteudo import plataformas
                a["wordpress"] = plataformas.enviar_rascunho(a, cliente)
        except Exception as e:
            print(f"  ✗ {a['slug']}: {e}")
            continue
        a["status"] = "publicado" if args.publicar else "rascunho no WordPress"
        fluxo.salvar_artigo(pasta, a, cliente)
        print(f"  ✓ {a['slug']}: {a['wordpress']['status']} → {a['wordpress']['editar']}")
    fluxo.atualizar_central(pasta, cliente)


def cmd_indexnow(args):
    cliente = executor.carregar_cliente(args.cliente)
    print(f"IndexNow: HTTP {publicador.avisar_indexnow(args.urls, cliente)}")


def cmd_servir(args):
    from app.servidor import app
    url = f"http://127.0.0.1:{args.porta}"
    print(f"Portal do Criador em {url}  (Ctrl+C para parar)")
    if settings.PORTAL_HOST_PUBLICO:
        if len(settings.PORTAL_SENHA) < 12:
            sys.exit("PORTAL_HOST_PUBLICO está no .env, mas PORTAL_SENHA tem menos de 12 caracteres. "
                     "O endereço público não abre sem uma senha forte.")
        print(f"Equipe: https://{settings.PORTAL_HOST_PUBLICO} (usuário {settings.PORTAL_USUARIO!r} e a senha do .env). "
              f"Abra o túnel com: ngrok http {args.porta} --url https://{settings.PORTAL_HOST_PUBLICO}")
    if not args.sem_navegador:
        import threading
        import webbrowser
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    from waitress import serve
    serve(app, host="127.0.0.1", port=args.porta, threads=8)


def cmd_entregas(args):
    import plano_correcao
    print(plano_correcao.gerar(executor.carregar_cliente(args.cliente)))


def cmd_exportar(args):
    import privacidade
    try:
        arq = privacidade.exportar(args.cliente, Path(args.destino))
    except ValueError as e:
        sys.exit(str(e))
    if not arq:
        sys.exit(f"Nada encontrado para o cliente {args.cliente!r}.")
    print(f"Dados do cliente {args.cliente!r} exportados para {arq}")
    print("O arquivo tem dados pessoais: entregue por canal seguro e apague a cópia local depois.")


def cmd_esquecer(args):
    import privacidade
    try:
        alvos = privacidade.locais(args.cliente)
    except ValueError as e:
        sys.exit(str(e))
    if not alvos:
        sys.exit(f"Nada encontrado para o cliente {args.cliente!r}.")
    raiz = settings.BASE_DIR
    print(f"Dados do cliente {args.cliente!r} no disco:")
    for a in alvos:
        print(f"  {a.relative_to(raiz).as_posix()}{'/' if a.is_dir() else ''}")
    print("  data/gastos.jsonl (o id do cliente vira \"removido\"; os valores ficam)")
    if not args.confirmar:
        sys.exit("\nNada foi apagado. Para apagar de vez, repita o comando com --confirmar. "
                 "Cópias de segurança e arquivos enviados ao cliente não são alcançados (ver docs/LGPD.md).")
    privacidade.esquecer(args.cliente)
    print(f"\nApagado: {len(alvos)} item(ns).")


def _flags_custo(parser):
    parser.add_argument("--confirmar", action="store_true",
                        help="executa de fato (sem isso, só mostra a estimativa de custo)")
    parser.add_argument("--limite", type=float, default=settings.LIMITE_USD_PADRAO,
                        help=f"teto de gasto em US$ (padrão {settings.LIMITE_USD_PADRAO:.2f})")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Portal do Criador — TimeLabs")
    sub = p.add_subparsers(dest="comando", required=True)

    r = sub.add_parser("radar", help="mede a visibilidade do cliente nas IAs")
    r.add_argument("cliente", help="id do cliente (arquivo em config/clientes/)")
    r.add_argument("--demo", action="store_true", help="respostas fictícias, sem chamar APIs")
    r.add_argument("--ias", help="filtra provedores: chatgpt,claude,gemini")
    r.add_argument("--repeticoes", type=int, default=1, help="vezes que cada pergunta é feita")
    _flags_custo(r)
    r.set_defaults(func=cmd_radar)

    ra = sub.add_parser("rastrear", help="percorre o site do cliente como um robô de IA (grátis, sem IA)")
    ra.add_argument("cliente")
    ra.add_argument("--limite", type=int, default=settings.RASTREIO_LIMITE,
                    help=f"máximo de páginas (padrão {settings.RASTREIO_LIMITE})")
    ra.add_argument("--demo", action="store_true", help="lê o site gerado em entregas/<cliente>/site-publicar, sem rede")
    ra.set_defaults(func=cmd_rastrear)

    rel = sub.add_parser("relatorio", help="regera o HTML a partir de um resultado salvo")
    rel.add_argument("arquivo")
    rel.set_defaults(func=cmd_relatorio)

    pa = sub.add_parser("pauta", help="monta a pauta de artigos a partir do último radar")
    pa.add_argument("cliente")
    pa.add_argument("--demo", action="store_true", help="pauta sem IA, a partir das perguntas")
    _flags_custo(pa)
    pa.set_defaults(func=cmd_pauta)

    es = sub.add_parser("escrever", help="escreve os artigos da pauta (rascunhos para aprovação)")
    es.add_argument("cliente")
    es.add_argument("--pauta", help="pasta da pauta (padrão: a mais recente)")
    es.add_argument("--temas", help="números dos temas, ex.: 1,3 (padrão: todos)")
    _flags_custo(es)
    es.set_defaults(func=cmd_escrever)

    wp = sub.add_parser("wordpress", help="envia artigo(s) ao WordPress do cliente")
    wp.add_argument("cliente")
    wp.add_argument("slug", help="slug do artigo ou 'todos'")
    wp.add_argument("--pauta", help="pasta da pauta (padrão: a mais recente)")
    wp.add_argument("--publicar", action="store_true",
                    help="publica direto (só sem pendências); padrão é rascunho")
    wp.set_defaults(func=cmd_wordpress)

    ix = sub.add_parser("indexnow", help="avisa Bing e outros buscadores sobre URLs publicadas")
    ix.add_argument("cliente")
    ix.add_argument("urls", nargs="+")
    ix.set_defaults(func=cmd_indexnow)

    sv = sub.add_parser("servir", help="abre o app do Portal do Criador no navegador")
    sv.add_argument("--porta", type=int, default=5050)
    sv.add_argument("--sem-navegador", action="store_true")
    sv.set_defaults(func=cmd_servir)

    st = sub.add_parser("site", help="gera o site completo do cliente (páginas, blog, sitemap) a partir de config/sites/<id>")
    st.add_argument("cliente")
    st.add_argument("--publicar", action="store_true", help="versão para o ar: sem faixa de prévia e sem campos tracejados")
    st.add_argument("--com-pendencias", action="store_true", help="inclui artigos com dados a confirmar (marcados)")
    st.set_defaults(func=cmd_site)

    gu = sub.add_parser("guias", help="refaz os guias do plano a partir do último radar real")
    gu.add_argument("cliente")
    gu.set_defaults(func=cmd_guias)

    en = sub.add_parser("entregas", help="monta o plano de correção (guias + estado do conteúdo)")
    en.add_argument("cliente")
    en.set_defaults(func=cmd_entregas)

    ex = sub.add_parser("exportar", help="junta todos os dados de um cliente num .zip (LGPD: acesso e portabilidade)")
    ex.add_argument("cliente")
    ex.add_argument("--destino", default="relatorios", help="pasta onde salvar o .zip (padrão: relatorios/, fora do Git)")
    ex.set_defaults(func=cmd_exportar)

    eq = sub.add_parser("esquecer", help="apaga todos os dados de um cliente (LGPD); sem --confirmar só lista")
    eq.add_argument("cliente")
    eq.add_argument("--confirmar", action="store_true", help="apaga de fato (sem isso, só lista o que seria apagado)")
    eq.set_defaults(func=cmd_esquecer)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
