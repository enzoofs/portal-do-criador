"""
testes.py — Testes de regressão da análise (sem chamar nenhuma IA).

    python testes.py

Cada teste nasce de um erro real encontrado em radar de verdade. Se algum
falhar depois de uma mudança no código, a mudança quebrou algo que já foi
corrigido uma vez.
"""

import sys

from radar import analise
from radar.extrator import e_a_marca
from radar.modelos import Fonte, Resposta

# Cliente e concorrentes fictícios: cada teste reproduz a situação de um erro real, sem dado real.
CLIENTE = {"id": "t", "nome": "Norte Digital", "site": "https://nortedigital.example/",
           "apelidos": ["Norte Digital", "nortedigital"], "dominios": ["nortedigital.example"],
           "cidade": "Belo Horizonte", "regiao": "MG", "pais": "BR", "segmento": "agência", "perfil": {},
           "perguntas": [{"texto": "Qual a melhor agência em BH?", "tipo": "descoberta"}]}


def resposta(empresas, fontes=(), marca=False):
    r = Resposta("chatgpt_app", "x", "Qual a melhor agência em BH?", "descoberta", texto=" ".join(empresas),
                 fontes=[Fonte(u) for u in fontes])
    r.empresas_recomendadas, r.marca_mencionada = list(empresas), marca
    return r


def teste_ranking_nao_e_concorrente():
    """13/10/2026: o ChatGPT citou um site de ranking local e ele virou "concorrente"."""
    m = analise.calcular([resposta(["Ranking Cidade", "Agência Alfa"], ["https://ranking.cidade.example/agencias", "https://agenciaalfa.example/"])],
                         CLIENTE, [])
    nomes = [e["nome"] for e in m["ranking"]]
    assert "Ranking Cidade" not in nomes, nomes
    tipos = {f["dominio"]: f["tipo"] for f in m["fontes"]}
    assert tipos["ranking.cidade.example"] == "terceiro", tipos
    assert tipos["agenciaalfa.example"] == "concorrente", tipos


def teste_site_com_hifen_e_concorrente():
    """15/10/2026: o domínio com hífen de uma agência concorrente era tratado como site de terceiro,
    e a leitura do radar mandava o cliente "marcar presença" no site de um concorrente."""
    m = analise.calcular([resposta(["Leads Mais"], ["https://leads-mais.example/trafego"])], CLIENTE, [])
    tipos = {f["dominio"]: f["tipo"] for f in m["fontes"]}
    assert tipos["leads-mais.example"] == "concorrente", tipos


def teste_listas_nao_viram_empresa():
    for nome in ["Ranking Cidade", "Guia BH Agências", "Top 10 agências", "Melhores agências de BH"]:
        assert analise.e_fonte_de_lista(nome), nome
    for nome in ["Agência Alfa", "Beta Marketing Digital", "Gama Digital", "Agência Delta"]:
        assert not analise.e_fonte_de_lista(nome), nome


def teste_empresa_de_nome_parecido_nao_e_a_marca():
    """Empresa de nome parecido é outra empresa: confundir as duas foi o achado central do primeiro radar."""
    assert not e_a_marca("Agência Norte", CLIENTE)
    assert e_a_marca("Norte Digital", CLIENTE)


def teste_visibilidade_conta_uma_vez_por_resposta():
    m = analise.calcular([resposta(["Norte Digital", "Norte Digital"], marca=True), resposta(["Agência Alfa"])], CLIENTE, [])
    assert m["resumo"]["respostas_descoberta"] == 2
    assert m["resumo"]["mencoes"] == 1


def teste_pendencias_viram_campos_e_somem_do_texto():
    """15/10/2026: o especialista respondia caçando o amarelo no texto. Agora responde em campos."""
    from conteudo import pendencias
    a = {"resposta_direta": "Atendemos BH.", "faq": [{"pergunta": "Desde quando?", "resposta": "Desde [[CONFIRMAR: 2018]]."}],
         "corpo_markdown": "Mais de [[CONFIRMAR: 100 empresas]] atendidas.\n\n[[DADO DO ESPECIALISTA: um case real]]\n\nFim."}
    itens = pendencias.listar(a)
    assert [i["tipo"] for i in itens] == ["confirmar", "dado", "confirmar"], itens
    assert itens[0]["contexto"] == "Mais de ____ atendidas.", itens[0]
    feitas = pendencias.aplicar(a, [("CONFIRMAR: 100 empresas", "usar", "120 empresas"),
                                    ("DADO DO ESPECIALISTA: um case real", "tirar", ""),
                                    ("CONFIRMAR: 2018", "depois", "2018")])
    assert feitas == 2
    assert a["corpo_markdown"] == "Mais de 120 empresas atendidas.\n\nFim.", a["corpo_markdown"]
    assert "[[CONFIRMAR: 2018]]" in a["faq"][0]["resposta"]
    assert pendencias.decidir("depois", "R$ 3 mil", "") == "usar"


def teste_site_publicado_sem_rascunho():
    """O site para o ar não pode ter campo tracejado, faixa de prévia nem noindex, e toda ficha
    JSON-LD precisa ser válida. Campo vazio some; nunca vira "PREENCHER" para o Google."""
    import json
    import re

    from site_cliente import gerador
    pasta = gerador.gerar("exemplo", previa=False)
    for f in pasta.rglob("*.html"):
        t = f.read_text(encoding="utf-8")
        assert 'class="preencher"' not in t and "noindex" not in t and "Prévia da TimeLabs" not in t, f
        for bloco in re.findall(r'<script type="application/ld\+json">(.*?)</script>', t, re.S):
            json.loads(bloco.replace("<\\/", "</"))
    assert "Disallow" not in (pasta / "robots.txt").read_text(encoding="utf-8")


def teste_todo_bloco_tem_modelo():
    """Bloco no catálogo sem modelo quebraria a página na hora de gerar, não na hora de editar."""
    from site_cliente import blocos, gerador
    for tipo in blocos.BLOCOS:
        assert (gerador.MODELOS / "blocos" / f"{tipo}.html").exists(), tipo


def teste_validacao_junta_erros_e_recusa_html():
    """O editor mostra todos os problemas de uma vez; HTML em campo de texto nunca entra."""
    import json

    from site_cliente import blocos, gerador
    s, _ = gerador.carregar("exemplo")
    ruim = json.loads(json.dumps(s))
    ruim["paginas"][0]["blocos"][0]["titulo"] = "<script>alert(1)</script>"
    ruim["marca"]["cores"]["fundo"] = "azul"
    ruim["empresa"]["whatsapp"] = "31 9999"
    try:
        blocos.validar(ruim, gerador.assets("exemplo"))
    except blocos.SiteInvalido as e:
        assert len(e.erros) == 3, e.erros
        assert any("não aceita HTML" in x for x in e.erros), e.erros
    else:
        raise AssertionError("site inválido passou na validação")


def teste_bloco_de_perguntas_gera_ficha_faq():
    """A ficha FAQPage sai dos próprios blocos: tirou o bloco, some a ficha (o Google exige que bata
    com o que está visível na página)."""
    from site_cliente import gerador
    s, _ = gerador.carregar("exemplo")
    inicio = next(p for p in s["paginas"] if p["tipo"] == "inicio")
    tipos = [f["@type"] for f in gerador.fichas_da_pagina(s, inicio, s["dominio"] + "/")]
    assert "FAQPage" in tipos and "ProfessionalService" in tipos, tipos
    sem = dict(inicio, blocos=[b for b in inicio["blocos"] if b["tipo"] != "perguntas"])
    assert "FAQPage" not in [f["@type"] for f in gerador.fichas_da_pagina(s, sem, s["dominio"] + "/")]


def teste_checagem_aponta_identidade_incompleta():
    """Sem CNPJ e perfis oficiais, a checagem avisa: é o que fazia as IAs confundirem a marca do primeiro cliente."""
    from site_cliente import checagem
    r = checagem.checar("exemplo")
    assert r["pode_publicar"], r["itens"]
    assert any(i["area"] == "Identidade" and i["nivel"] == "aviso" for i in r["itens"]), r["itens"]


def teste_site_nao_carrega_nada_de_terceiros():
    """Fonte, CSS, script ou imagem vindos de outro domínio mandam o IP do visitante para fora (LGPD).
    O site do cliente carregava as fontes do Google Fonts; agora vêm de assets/fontes/."""
    import re

    from site_cliente import gerador
    pasta = gerador.gerar("exemplo", previa=False, destino=gerador.CACHE_IMAGENS / "exemplo" / "teste-terceiros")
    externos = set()
    for pagina in pasta.rglob("*.html"):
        html = pagina.read_text(encoding="utf-8")
        externos |= set(re.findall(r'<(?:link|script|img|iframe|source)\b[^>]*?(?:href|src)="(https?://[^"]+)"', html))
    dominio = gerador.carregar("exemplo")[0]["dominio"]
    assert not {u for u in externos if not u.startswith(dominio)}, externos
    assert (pasta / "assets" / "fontes.css").read_text(encoding="utf-8").count("@font-face") >= 1
    assert list((pasta / "assets" / "fontes").glob("*/LICENSE.txt")), "fonte sem a licença junto"


def teste_esquecer_apaga_tudo_do_cliente():
    """Direito de eliminação (LGPD): some tudo do cliente, e só dele (o cliente "<id>-b" fica)."""
    import json
    import tempfile
    from pathlib import Path

    import custos
    import privacidade
    from config import settings

    cid = "teste_esquecer"
    settings.RELATORIOS_DIR.mkdir(parents=True, exist_ok=True)
    vizinho = settings.RELATORIOS_DIR / f"radar-{cid}-b-20260101-000000.html"
    vizinho.write_text("x", encoding="utf-8")
    gastos_original = custos.GASTOS_ARQ
    with tempfile.TemporaryDirectory() as tmp:
        custos.GASTOS_ARQ = Path(tmp) / "gastos.jsonl"
        custos.GASTOS_ARQ.write_text(json.dumps({"cliente": cid, "usd": 1.0}) + "\n"
                                     + json.dumps({"cliente": "outro", "usd": 2.0}) + "\n", encoding="utf-8")
        try:
            (settings.CLIENTES_DIR / f"{cid}.json").write_text("{}", encoding="utf-8")
            for pasta in (settings.RUNS_DIR / cid, settings.CONTEUDO_DIR / cid, settings.RASTREIO_DIR / cid):
                pasta.mkdir(parents=True, exist_ok=True)
                (pasta / "a.json").write_text("{}", encoding="utf-8")
            (settings.RELATORIOS_DIR / f"radar-{cid}-20260101-000000-demo.html").write_text("x", encoding="utf-8")
            assert len(privacidade.locais(cid)) == 5, privacidade.locais(cid)
            exportado = privacidade.exportar(cid, settings.RELATORIOS_DIR)
            assert exportado and len(privacidade.locais(cid)) == 6   # a exportação também é dado do cliente
            privacidade.esquecer(cid)
            assert privacidade.locais(cid) == []
            assert vizinho.exists(), "apagou o relatório de outro cliente"
            gastos = [json.loads(linha) for linha in custos.GASTOS_ARQ.read_text(encoding="utf-8").splitlines()]
            assert [g["cliente"] for g in gastos] == ["removido", "outro"], gastos
            assert sum(g["usd"] for g in gastos) == 3.0
        finally:
            if privacidade.locais(cid):      # ainda com o registro de gastos temporário
                privacidade.esquecer(cid)
            custos.GASTOS_ARQ = gastos_original
            vizinho.unlink(missing_ok=True)


# --------------------------------------------------------------------------
# Segurança do Portal (ver SECURITY.md). Rodam no cliente fictício, sem servidor e sem rede.
# --------------------------------------------------------------------------

def _portal():
    from app.servidor import app
    return app.test_client()


def teste_seguranca_recusa_ataques():
    """Cada linha é um ataque que funcionava antes da auditoria (o primeiro entregava o .env)."""
    c, cid, fora = _portal(), "exemplo", {"Origin": "https://site-malicioso.example"}
    ataques = [
        ("arquivo fora da pasta por ..\\ (anexo)", c.get(f"/c/{cid}/anexo/..%5C..%5CREADME.md"), 404),
        ("arquivo fora da pasta por ..\\ (fontes)", c.get("/fontes/..%5C..%5CREADME.md"), 404),
        ("id de cliente com ..\\", c.get("/c/..%5Cconfig%5Cclientes%5Cexemplo/radar"), 404),
        ("prévia do site com ..\\", c.get(f"/c/{cid}/site-novo/..%5C..%5C..%5CREADME.md"), 404),
        ("slug de artigo com ..\\", c.get(f"/c/{cid}/artigo/..%5C..%5Cx"), 404),
        ("JSON como texto puro (CSRF sem pré-checagem)",
         c.post(f"/api/c/{cid}/tarefas", data='{"tipo":"radar","demo":true}', content_type="text/plain"), 415),
        ("execução vinda de outro site", c.post(f"/api/c/{cid}/tarefas", json={"tipo": "radar", "demo": True}, headers=fora), 403),
        ("formulário vindo de outro site", c.post(f"/c/{cid}/config", data={"tom": "x"}, headers=fora), 403),
        ("Sec-Fetch-Site cross-site", c.post(f"/c/{cid}/config", data={"tom": "x"}, headers={"Sec-Fetch-Site": "cross-site"}), 403),
        ("DNS rebinding", c.get("/", headers={"Host": "rebind.site-malicioso.example:5050"}), 421),
    ]
    erradas = [(d, r.status_code, esperado) for d, r, esperado in ataques if r.status_code != esperado]
    assert not erradas, erradas


def teste_seguranca_uso_normal_e_cabecalhos():
    from site_cliente import gerador
    gerador.gerar("exemplo", previa=True)
    c, cid = _portal(), "exemplo"
    urls = ["/", "/novo", f"/c/{cid}/radar", f"/c/{cid}/rastreio", f"/c/{cid}/conteudo", f"/c/{cid}/plano", f"/c/{cid}/site",
            f"/c/{cid}/resultados", f"/c/{cid}/midia", f"/c/{cid}/config", f"/c/{cid}/site-novo/",
            f"/c/{cid}/site/assets/logo.svg", "/fontes/geist-latin-400-normal.woff2", "/api/paleta"]
    erradas = [(u, c.get(u).status_code) for u in urls if c.get(u).status_code != 200]
    assert not erradas, erradas
    tela = c.get(f"/c/{cid}/config").headers
    assert "script-src 'self'" in tela["Content-Security-Policy"] and "unsafe-inline" not in tela["Content-Security-Policy"].split("script-src")[1].split(";")[0]
    assert tela["X-Content-Type-Options"] == "nosniff" and tela["X-Frame-Options"] == "SAMEORIGIN"
    r = c.post(f"/api/c/{cid}/site/checar", json={}, headers={"Origin": "http://localhost"})
    assert r.status_code == 200, r.status_code


def teste_tunel_da_equipe_exige_senha():
    """O Portal compartilhado pelo ngrok não tem login próprio: o endereço público do túnel só abre com
    usuário e senha, fica fechado se a senha não estiver configurada, e o resto das proteções continua."""
    import base64

    from config import settings
    originais = settings.PORTAL_HOST_PUBLICO, settings.PORTAL_SENHA
    publico = "equipe-teste.ngrok-free.app"

    def entrar(usuario, senha):
        return {"Host": publico, "Authorization": "Basic " + base64.b64encode(f"{usuario}:{senha}".encode()).decode()}
    c = _portal()
    try:
        settings.PORTAL_HOST_PUBLICO, settings.PORTAL_SENHA = publico, ""
        assert c.get("/", headers=entrar(settings.PORTAL_USUARIO, "")).status_code == 401   # sem senha no .env: fechado
        settings.PORTAL_SENHA = "senha-de-teste-123"
        assert c.get("/", headers={"Host": publico}).status_code == 401
        assert c.get("/", headers=entrar(settings.PORTAL_USUARIO, "errada")).status_code == 401
        assert c.get("/", headers=entrar(settings.PORTAL_USUARIO, "senha-de-teste-123")).status_code == 200
        ok = {**entrar(settings.PORTAL_USUARIO, "senha-de-teste-123"), "Origin": f"https://{publico}"}
        assert c.post("/api/c/exemplo/estimativa", json={"tipo": "radar"}, headers=ok).status_code == 200
        fora = {**ok, "Origin": "https://site-malicioso.example"}
        assert c.post("/api/c/exemplo/estimativa", json={"tipo": "radar"}, headers=fora).status_code == 403
        assert c.get("/", headers={"Host": "outro.ngrok-free.app"}).status_code == 421
        assert c.get("/").status_code == 200    # na própria máquina, nada muda
    finally:
        settings.PORTAL_HOST_PUBLICO, settings.PORTAL_SENHA = originais


def teste_markdown_nao_vira_script():
    """Texto de IA pode trazer injeção. O navegador ignora tab, quebra de linha e controle dentro da
    URL ("java\\nscript:" executa); o filtro antigo, por lista de proibidos, deixava passar esses dois."""
    from conteudo.render import markdown_seguro
    ataques = ["<img src=x onerror=alert(1)>", "[a](javascript:alert(1))", "[a]( JaVaScRiPt:alert(1))",
               "[a](java\nscript:alert(1))", "[a](\x01javascript:alert(1))", "![x](javascript:alert(1))",
               "[a](data:text/html,x)", "[a](vbscript:x)", "[a][r]\n\n[r]: javascript:alert(1)"]
    for a in ataques:
        saida = markdown_seguro(a).lower()
        assert "<img src=x" not in saida and "script:" not in saida.replace("\n", "").replace("\x01", "") \
            and "data:" not in saida, (a, saida)
    for ok in ["[a](https://x.example/?a=1&b=2)", "[a](/blog/)", "[a](#faq)", "[a](mailto:a@x.example)", "[a](tel:+5531)"]:
        assert 'href="#"' not in markdown_seguro(ok), ok


def teste_rede_bloqueia_enderecos_internos():
    """SSRF: o cadastro baixa o site que o usuário digitar; não pode ler a máquina nem a rede interna."""
    from rede import EnderecoBloqueado, conferir_url
    for url in ["http://127.0.0.1:5050/", "http://localhost/", "http://10.0.0.1/", "http://192.168.0.1/",
                "http://169.254.169.254/latest/meta-data/", "http://[::1]/", "file:///etc/passwd", "ftp://x.example/"]:
        try:
            conferir_url(url)
        except EnderecoBloqueado:
            continue
        raise AssertionError(f"não bloqueou {url}")


def teste_upload_confere_o_formato_real():
    """Vale o conteúdo, não a extensão: GIF renomeado para .png e imagem gigante em pixels não entram."""
    import io

    from PIL import Image

    from site_cliente import gerador

    def arquivo(formato, tamanho=(8, 8), modo="RGB"):
        b = io.BytesIO()
        Image.new(modo, tamanho).save(b, formato)
        return b.getvalue()

    c = _portal()

    def enviar(conteudo, nome):
        return c.post("/api/c/exemplo/site/imagem", data={"imagem": (io.BytesIO(conteudo), nome)},
                      content_type="multipart/form-data")

    assert enviar(arquivo("GIF"), "x.png").status_code == 400
    assert enviar(b"<svg onload=alert(1)>", "x.svg").status_code == 400
    assert enviar(arquivo("PNG", (10_000, 10_000), "1"), "grande.png").status_code == 400
    r = enviar(arquivo("JPEG"), "Foto Válida.png")
    assert r.status_code == 200 and r.get_json()["nome"].startswith("foto-valida") and r.get_json()["nome"].endswith(".jpg")
    (gerador.pasta_site("exemplo") / "assets" / r.get_json()["nome"]).unlink()


def teste_robots_txt_le_cada_grupo_de_robos():
    """16/10/2026: a regra antiga atravessava o bloco de um robô até o "Disallow: /" de outro (dizia
    que o GPTBot estava bloqueado sem estar) e não via "User-agent: *" bloqueando todos."""
    from radar.auditoria import robos_bloqueados
    base = "https://nortedigital.example/"
    outro_bloqueado = "User-agent: GPTBot\nAllow: /\n\nUser-agent: *\nDisallow: /admin/\n\nUser-agent: RoboRuim\nDisallow: /\n"
    assert robos_bloqueados(outro_bloqueado, base) == [], robos_bloqueados(outro_bloqueado, base)
    assert len(robos_bloqueados("User-agent: *\nDisallow: /\n", base)) == 8
    so_gptbot = "User-agent: *\nDisallow: /\n\nUser-agent: GPTBot\nAllow: /\n"
    assert "GPTBot" not in robos_bloqueados(so_gptbot, base) and "ClaudeBot" in robos_bloqueados(so_gptbot, base)
    grupo = "User-agent: GPTBot\nUser-agent: ClaudeBot\nDisallow: /*\n"
    assert robos_bloqueados(grupo, base) == ["GPTBot", "ClaudeBot"], robos_bloqueados(grupo, base)
    # páginas internas (rastreador): a regra mais longa vence e os curingas valem em qualquer Python
    from radar.auditoria import permite, regras_robots
    regras = regras_robots("User-agent: *\nDisallow: /\nAllow: /blog/\nDisallow: /*.pdf$\n")
    assert permite(regras, "GPTBot", "/blog/artigo") and not permite(regras, "GPTBot", "/servicos")
    assert not permite(regras, "GPTBot", "/blog/guia.pdf") and permite(regras, "GPTBot", "/blog/guia.pdf?v=2")


def teste_link_do_site_so_aceita_http():
    """Perfis e formulário viram href no site publicado: javascript: seria script no site do cliente."""
    import copy

    from site_cliente import blocos, gerador
    s, _ = gerador.carregar("exemplo")
    ruim = copy.deepcopy(s)
    ruim["empresa"]["perfis"]["instagram"] = "javascript:alert(1)"
    ruim["empresa"]["formulario"] = "data:text/html,x"
    try:
        blocos.validar(ruim, gerador.assets("exemplo"))
    except blocos.SiteInvalido as e:
        assert sum("link" in erro for erro in e.erros) == 2, e.erros
    else:
        raise AssertionError("aceitou link javascript:")


# --------------------------------------------------------------------------
# Rastreamento do site e cruzamento com o radar. Site falso em memória: sem rede.
# --------------------------------------------------------------------------

SITE = "https://nortedigital.example"
TEXTO = "Agência de tráfego pago em Belo Horizonte com campanhas no Google e no Instagram. " * 20


def _html(titulo, corpo=TEXTO, links=(), extra=""):
    lks = "".join(f'<a href="{u}">{u}</a>' for u in links)
    return (f"<html><head><title>{titulo}</title><meta name='description' content='Sobre {titulo}'>{extra}</head>"
            f"<body><h1>{titulo}</h1><main><p>{corpo}</p>{lks}</main></body></html>")


def _site_falso(paginas: dict, pedidos: list | None = None):
    """URL -> HTML (200), status de erro, (301, destino) ou função ua -> HTML (resposta por robô)."""
    from urllib.parse import urljoin

    from radar.rastreador import Baixado

    def baixar(url, ua, cadeia):
        for _ in range(5):
            if pedidos is not None:
                pedidos.append(url)
            item = paginas.get(url, 404)
            if isinstance(item, tuple):
                cadeia.append((item[0], url))
                url = urljoin(url, item[1])
                continue
            if isinstance(item, int):
                return Baixado(item, url)
            tipo = "application/xml" if url.endswith(".xml") else "text/plain" if url.endswith(".txt") else "text/html"
            return Baixado(200, url, item(ua) if callable(item) else item, tipo)
        return None
    return baixar


def _site_com_defeitos() -> dict:
    vazia = '<html><head><title>{}</title></head><body><div id="root"></div><script src="/a.js"></script></body></html>'
    menu = ["/servicos/", "/antiga", "/quebrada/", "/cadeia", "/escondida/", "/app/", "/prerender/",
            "/titulo-a/", "/titulo-b/", "/privado/", "/blog/", "https://outro.example/x"]
    return {
        f"{SITE}/robots.txt": f"User-agent: *\nDisallow: /privado/\n\nUser-agent: GPTBot\nDisallow: /blog/\n\nSitemap: {SITE}/sitemap.xml",
        f"{SITE}/sitemap.xml": "<urlset>" + "".join(f"<url><loc>{SITE}{p}</loc></url>" for p in ("/", "/servicos/", "/orfa/", "/sumiu/")) + "</urlset>",
        f"{SITE}/": _html("Norte Digital | tráfego pago em BH", links=menu),
        f"{SITE}/servicos/": _html("Serviços", links=["/"]),
        f"{SITE}/antiga": (301, "/nova/"),
        f"{SITE}/nova/": _html("Nova"),
        f"{SITE}/cadeia": (301, "/cadeia2"),
        f"{SITE}/cadeia2": (301, "/final/"),
        f"{SITE}/final/": _html("Final"),
        f"{SITE}/escondida/": _html("Escondida", extra='<meta name="robots" content="noindex, follow">'),
        f"{SITE}/app/": vazia.format("App"),
        f"{SITE}/prerender/": lambda ua: _html("Pré-renderizada") if "GPTBot" in ua else vazia.format("Pré"),
        f"{SITE}/titulo-a/": _html("Título igual"),
        f"{SITE}/titulo-b/": _html("Título igual"),
        f"{SITE}/blog/": _html("Blog"),
        f"{SITE}/orfa/": _html("Órfã"),
    }


def teste_rastreio_acha_os_problemas_do_site():
    """O rastreador vê o site como um robô de IA: cada página com um defeito conhecido cai no problema
    certo, a página que só tem texto para robôs (pré-renderizada) não vira falso alarme, e nada fora do
    domínio ou proibido no robots.txt é baixado."""
    from urllib.parse import urlsplit

    from radar import rastreador
    pedidos = []
    r = rastreador.rastrear({"id": "t", "site": SITE + "/", "dominios": ["nortedigital.example"]},
                            baixar=_site_falso(_site_com_defeitos(), pedidos), progresso=lambda _: None, pausa=0)
    achados = {p["codigo"]: {urlsplit(x["url"]).path for x in p["paginas"]} for p in rastreador.problemas(r)}
    esperado = {"quebrada": {"/quebrada/"}, "cadeia_redirecionamento": {"/cadeia"},
                "link_para_redirecionamento": {"/"}, "noindex": {"/escondida/"}, "texto_so_com_javascript": {"/app/"},
                "titulo_repetido": {"/titulo-a/", "/titulo-b/"}, "orfa": {"/orfa/"}, "sitemap_com_erro": {"/sumiu/"},
                "bloqueada_para_ias": {"/blog/"}}
    errados = {k: achados.get(k) for k, v in esperado.items() if achados.get(k) != v}
    assert not errados, errados
    assert "/prerender/" not in achados.get("h1", set()) | achados.get("pouco_texto", set()), achados
    assert not any("outro.example" in u or "/privado/" in u for u in pedidos), pedidos
    assert r["links_completos"] and not r["parou_no_limite"]
    curto = rastreador.rastrear({"id": "t", "site": SITE + "/", "dominios": ["nortedigital.example"]}, limite=3,
                                baixar=_site_falso(_site_com_defeitos()), progresso=lambda _: None, pausa=0)
    assert curto["parou_no_limite"] and "orfa" not in {p["codigo"] for p in rastreador.problemas(curto)}


def teste_rastreio_e_tarefa_gratis():
    """Rastrear não usa IA nem API paga: roda sem a janela de custo e não mexe no contador de gasto.
    O radar continua exigindo confirmação."""
    import time

    import custos
    from app import tarefas
    from site_cliente import gerador
    gerador.gerar("exemplo", previa=False)
    from radar import rastreador
    antes = set(rastreador.PASTA.glob("exemplo/*.json"))
    c = _portal()
    r = c.post("/api/c/exemplo/tarefas", json={"tipo": "rastreio", "demo": True})
    assert r.status_code == 200, r.get_json()
    t = tarefas.obter(r.get_json()["id"])
    for _ in range(200):
        if t.status != "rodando":
            break
        time.sleep(0.05)
    for novo in set(rastreador.PASTA.glob("exemplo/*.json")) - antes:
        novo.unlink()
    assert t.status == "ok", t.linhas
    assert t.custo_usd is None and not custos.contador.autorizado
    assert c.post("/api/c/exemplo/tarefas", json={"tipo": "radar"}).status_code == 400


def teste_rastreio_nao_herda_o_modo_demonstracao_do_radar():
    """16/10/2026: no teste do Fran, depois de um radar de demonstração o "Rastrear de novo" virou
    demonstração e travou em "sem site gerado". O rastreio é grátis e sempre lê o site real; só a pauta
    herda o modo do radar."""
    from app import dados, tarefas
    pedidos = []
    originais = tarefas.iniciar, dados.ultimo_radar

    class Falsa:
        def to_dict(self):
            return {"id": "x"}
    tarefas.iniciar = lambda tipo, cid, demo, **_: pedidos.append((tipo, demo)) or Falsa()
    dados.ultimo_radar = lambda cid: {"demo": True}       # o último radar foi de demonstração
    try:
        c = _portal()
        assert c.post("/api/c/exemplo/tarefas", json={"tipo": "rastreio"}).status_code == 200
        assert c.post("/api/c/exemplo/tarefas", json={"tipo": "pauta", "confirmado": True}).status_code == 200
    finally:
        tarefas.iniciar, dados.ultimo_radar = originais
    assert pedidos == [("rastreio", False), ("pauta", True)], pedidos


def teste_guias_saem_do_radar_de_cada_cliente():
    """16/10/2026: a TimeLabs ficou sem guia nenhum no plano (os da Última Digital foram escritos à mão).
    Agora cada radar real gera os guias do cliente com os dados dele; o nome que a IA inventou não vira
    HTML nem link; guia escrito à mão fica; o de robôs só existe quando há robô bloqueado."""
    import tempfile
    from pathlib import Path

    import guias
    import plano_correcao
    perigosa = "<script>alert(1)</script> [clique](javascript:alert(1))"
    cliente = {**CLIENTE, "id": "guias_teste", "site": SITE + "/", "dominios": ["nortedigital.example"],
               "perfil": {"servicos": ["tráfego pago"], "cta": {"whatsapp": "5531999990000"}}}
    run = {"demo": False, "gerado_em": "2026-10-16T15:00:00", "provedores": {"chatgpt_app": "x"},
           "auditoria": [{"nome": "Robôs das IAs conseguem acessar o site", "ok": False,
                          "detalhe": "bloqueados: GPTBot (treino do ChatGPT)", "impacto": ""}],
           "metricas": {"resumo": {"confusoes": [{"provedor": "chatgpt_app", "empresa": perigosa}],
                                   "marca_conhecida": 1, "perguntas_marca": 3},
                        "fontes": [{"dominio": "ranking-bh.example", "respostas": 2, "tipo": "terceiro"},
                                   {"dominio": "empresa-qualquer.example", "respostas": 3, "tipo": "terceiro"}],
                        "paginas": [], "ranking": [{"nome": "Agência Alfa", "e_a_marca": False}]}}
    with tempfile.TemporaryDirectory() as tmp:
        pasta = Path(tmp) / "guias_teste"
        pasta.mkdir()
        (pasta / "03-avaliacoes.md").write_text("---\ntitulo: escrito à mão\n---\nTexto da equipe.", encoding="utf-8")
        nomes = {p.name for p in guias.gerar(cliente, run, pasta=Path(tmp))}
        assert nomes == {"01-identidade-oficial.md", "02-listas-de-terceiros.md", "05-bing-e-plataformas.md",
                         "06-robos-de-treino.md", "07-anuncios-chatgpt.md"}, nomes
        assert "Texto da equipe." in (pasta / "03-avaliacoes.md").read_text(encoding="utf-8")
        identidade = plano_correcao.md_para_html((pasta / "01-identidade-oficial.md").read_text(encoding="utf-8"))
        assert "alert(1)" in identidade, "o nome da empresa confundida tem que aparecer, como texto"
        assert "<script" not in identidade and 'href="javascript' not in identidade, identidade
        listas = (pasta / "02-listas-de-terceiros.md").read_text(encoding="utf-8")
        assert "ranking-bh.example" in listas and "empresa-qualquer.example" not in listas
        assert "+55 31 99999-0000" in (pasta / "05-bing-e-plataformas.md").read_text(encoding="utf-8")
        assert "Se o site ainda não tiver" in identidade        # sem rastreio: não afirma que falta
        # 16/10/2026: o guia mandava criar timelabs.com.br/sobre, que já existia
        sobre = {"paginas": [{"url": f"{SITE}/sobre", "status": 200}]}
        guias.gerar(cliente, run, sobre, pasta=Path(tmp))
        texto = (pasta / "01-identidade-oficial.md").read_text(encoding="utf-8")
        assert "já existe" in texto and "Criar a página" not in texto, texto
        guias.gerar(cliente, run, {"paginas": [{"url": f"{SITE}/", "status": 200}]}, pasta=Path(tmp))
        assert "O rastreamento não encontrou uma página" in (pasta / "01-identidade-oficial.md").read_text(encoding="utf-8")
        run["auditoria"] = []
        guias.gerar(cliente, run, pasta=Path(tmp))
        assert not (pasta / "06-robos-de-treino.md").exists()
        assert guias.gerar(cliente, {**run, "demo": True}, pasta=Path(tmp)) == []


def _run_falso(perguntas_e_fontes: list[tuple[str, list[str], bool]]) -> dict:
    """Radar mínimo: (pergunta, URLs citadas, marca citada?) por resposta."""
    perguntas = list(dict.fromkeys(p for p, _, _ in perguntas_e_fontes))
    return {"cliente": {**CLIENTE, "site": SITE + "/", "dominios": ["nortedigital.example"],
                        "perguntas": [{"texto": p, "tipo": "descoberta"} for p in perguntas]},
            "respostas": [{"pergunta": p, "provedor": "chatgpt_app", "tipo_pergunta": "descoberta", "erro": None,
                           "marca_mencionada": m, "fontes": [{"url": u} for u in fontes]} for p, fontes, m in perguntas_e_fontes],
            "metricas": {"recomendacoes": [{"titulo": "Aumentar as avaliações no Google", "texto": "do radar"}]}}


def teste_cruzamento_liga_radar_e_site():
    """O radar diz se a marca aparece; o rastreamento, por quê. A URL citada pela IA (com www, utm e sem
    a barra) liga à página rastreada; "BH" acha a página de "Belo Horizonte"; pergunta sem página vira
    ação; e a página citada que não abre vem antes de tudo no plano."""
    from radar import cruzamento, rastreador
    run = _run_falso([
        ("Qual a melhor agência de tráfego pago em BH?",
         ["https://www.nortedigital.example/trafego-pago-belo-horizonte?utm_source=openai"], True),
        ("Qual a melhor agência de tráfego pago em BH?", ["https://nortedigital.example/antiga/"], False),
        ("Agência de anúncios para clínicas em BH", [], False)])
    site = {f"{SITE}/robots.txt": "User-agent: *\nAllow: /\n",
            f"{SITE}/": _html("Norte Digital | tráfego pago em BH", links=["/trafego-pago-belo-horizonte/"]),
            f"{SITE}/trafego-pago-belo-horizonte/": _html("Tráfego pago em Belo Horizonte", links=["/"])}
    rast = rastreador.rastrear(run["cliente"], baixar=_site_falso(site), progresso=lambda _: None, pausa=0,
                               extras=cruzamento.urls_citadas(run))
    cz = cruzamento.cruzar(run, rast)
    citadas = {c["url"].split("nortedigital.example")[1].split("?")[0]: c for c in cz["paginas_citadas"]}
    assert citadas["/trafego-pago-belo-horizonte"]["nivel"] == "ok", citadas
    assert citadas["/antiga/"]["nivel"] == "erro", citadas
    q = {x["pergunta"]: x for x in cz["perguntas"]}
    tp = q["Qual a melhor agência de tráfego pago em BH?"]
    assert tp["diagnostico"] == "pagina_ok" and tp["pagina"]["url"].endswith("/trafego-pago-belo-horizonte/"), tp
    assert tp["mencoes"] == 1 and tp["respostas"] == 2, tp
    assert q["Agência de anúncios para clínicas em BH"]["diagnostico"] == "sem_pagina", q
    titulos = [a["titulo"] for a in cruzamento.plano(run, rast)]
    assert titulos[0] == "Consertar as páginas do site que as IAs citam", titulos
    assert titulos.index("Aumentar as avaliações no Google") < titulos.index("Criar uma página para cada pergunta sem resposta no site")
    assert cruzamento.plano(run, None) == run["metricas"]["recomendacoes"]


def teste_compara_com_paginas_de_concorrentes_citadas():
    """O radar lê uma vez cada página de concorrente que as IAs citaram (respeitando o robots.txt de cada
    site) e compara com a do cliente: o que a maioria tem e a do cliente não vira referência no plano."""
    from radar import cruzamento, rastreador
    conc = "https://alfa.example"
    faq = '<script type="application/ld+json">{"@type": "FAQPage"}</script>'
    site_conc = {f"{conc}/robots.txt": "User-agent: *\nDisallow: /privado/\n",
                 f"{conc}/trafego-bh/": _html("Tráfego pago em Belo Horizonte", TEXTO + " Planos a partir de R$ 1.500.", extra=faq),
                 f"{conc}/privado/x": _html("Privado")}
    pedidos = []
    lidas = rastreador.ler_externas([f"{conc}/trafego-bh/?utm_source=openai", f"{conc}/privado/x"],
                                    baixar=_site_falso(site_conc, pedidos), pausa=0)
    assert "palavras" in lidas[0] and "erro" in lidas[1] and f"{conc}/privado/x" not in pedidos, lidas
    run = _run_falso([("Quanto custa uma agência de tráfego pago em BH?", [f"{conc}/trafego-bh/?utm_source=openai"], False)])
    run["paginas_concorrentes"] = lidas
    site = {f"{SITE}/robots.txt": "", f"{SITE}/": _html("Norte Digital", links=["/trafego-pago/"]),
            f"{SITE}/trafego-pago/": _html("Agência de tráfego pago", "Campanhas de tráfego pago para empresas.")}
    rast = rastreador.rastrear(run["cliente"], baixar=_site_falso(site), progresso=lambda _: None, pausa=0)
    q = cruzamento.perguntas(run, rast)[0]
    dif = {s["sinal"] for s in q["concorrentes"]["sinais"] if s["diferenca"]}
    assert dif == {"cidade no título ou no H1", "perguntas frequentes", "preço ou faixa de preço"}, q["concorrentes"]
    acao = next(a for a in cruzamento.cruzar(run, rast)["acoes"] if a["chave"] == "fracas")
    assert "concorrente que as IAs citaram tem cerca de" in acao["texto"] and "preço ou faixa de preço" in acao["texto"], acao["texto"]


def teste_novo_rastreio_confirma_a_correcao():
    """Corrigiu e rastreou de novo: o problema sai da lista, a ação do plano aparece como feita sem
    ninguém marcar, e a ação marcada como feita antes do rastreio que ainda encontra o problema volta
    para pendente, com o aviso."""
    import json
    import tempfile
    from pathlib import Path

    from app import dados
    from radar import rastreador
    run = _run_falso([("Qual a melhor agência de tráfego pago em BH?", [], False)])
    run["cliente"]["id"] = "teste_plano_site"
    quebrado = {f"{SITE}/robots.txt": "", f"{SITE}/a/": _html("Igual"), f"{SITE}/b/": _html("Igual"),
                f"{SITE}/": _html("Norte Digital | tráfego pago em BH", links=["/quebrada/", "/a/", "/b/"])}
    corrigido = {**quebrado, f"{SITE}/": _html("Norte Digital | tráfego pago em BH", links=["/a/", "/b/"])}

    def rastrear(site, quando):
        r = rastreador.rastrear(run["cliente"], baixar=_site_falso(site), progresso=lambda _: None, pausa=0)
        r["gerado_em"] = quando
        return r
    velho, novo = rastrear(quebrado, "2026-10-01T10:00:00"), rastrear(corrigido, "2026-10-08T10:00:00")
    mudou = rastreador.comparar(velho, novo)
    assert [m["codigo"] for m in mudou["resolvidos"]] == ["quebrada"] and not mudou["novos"], mudou
    originais = rastreador.PASTA, dados.PLANO_DIR
    titulos = "Ajustar títulos, descrições e fichas das páginas"
    with tempfile.TemporaryDirectory() as tmp:
        rastreador.PASTA, dados.PLANO_DIR = Path(tmp) / "rastreios", Path(tmp) / "plano"
        try:
            rastreador.salvar(velho)
            rastreador.salvar(novo)
            dados.PLANO_DIR.mkdir()
            (dados.PLANO_DIR / "teste_plano_site.json").write_text(
                json.dumps({titulos: "feito", "_datas": {titulos: "2026-10-05T00:00:00"}}), encoding="utf-8")
            acoes = {a["titulo"]: a for a in dados.plano("teste_plano_site", run)}
            links = acoes["Corrigir links quebrados e redirecionamentos"]
            assert links["status"] == "feito" and links.get("resolvida"), links
            assert acoes[titulos]["status"] == "pendente" and acoes[titulos].get("nota_alerta"), acoes[titulos]
        finally:
            rastreador.PASTA, dados.PLANO_DIR = originais


if __name__ == "__main__":
    falhas = 0
    for nome, fn in [(n, f) for n, f in globals().items() if n.startswith("teste_")]:
        try:
            fn()
            print(f"ok    {nome}")
        except Exception as e:  # um erro inesperado também é falha, e os outros testes seguem
            falhas += 1
            print(f"FALHA {nome}: {type(e).__name__}: {e}")
    sys.exit(1 if falhas else 0)
