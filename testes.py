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
            for pasta in (settings.RUNS_DIR / cid, settings.CONTEUDO_DIR / cid):
                pasta.mkdir(parents=True, exist_ok=True)
                (pasta / "a.json").write_text("{}", encoding="utf-8")
            (settings.RELATORIOS_DIR / f"radar-{cid}-20260101-000000-demo.html").write_text("x", encoding="utf-8")
            assert len(privacidade.locais(cid)) == 4, privacidade.locais(cid)
            exportado = privacidade.exportar(cid, settings.RELATORIOS_DIR)
            assert exportado and len(privacidade.locais(cid)) == 5   # a exportação também é dado do cliente
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
    urls = ["/", "/novo", f"/c/{cid}/radar", f"/c/{cid}/conteudo", f"/c/{cid}/plano", f"/c/{cid}/site",
            f"/c/{cid}/resultados", f"/c/{cid}/midia", f"/c/{cid}/config", f"/c/{cid}/site-novo/",
            f"/c/{cid}/site/assets/logo.svg", "/fontes/geist-latin-400-normal.woff2", "/api/paleta"]
    erradas = [(u, c.get(u).status_code) for u in urls if c.get(u).status_code != 200]
    assert not erradas, erradas
    tela = c.get(f"/c/{cid}/config").headers
    assert "script-src 'self'" in tela["Content-Security-Policy"] and "unsafe-inline" not in tela["Content-Security-Policy"].split("script-src")[1].split(";")[0]
    assert tela["X-Content-Type-Options"] == "nosniff" and tela["X-Frame-Options"] == "SAMEORIGIN"
    r = c.post(f"/api/c/{cid}/site/checar", json={}, headers={"Origin": "http://localhost"})
    assert r.status_code == 200, r.status_code


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
