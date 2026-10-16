"""
conteudo/plataformas.py — Envia o artigo como RASCUNHO para o site do cliente.

Plataformas: WordPress, Webflow, Shopify e Wix. A escolha fica no cadastro do
cliente (publicacao.plataforma) e as chaves ficam no .env com o id do cliente:

  wordpress  WP_<ID>_USUARIO, WP_<ID>_SENHA_APP
  webflow    WEBFLOW_<ID>_TOKEN            + publicacao.colecao (ID da coleção do blog)
                                             + publicacao.campos {"corpo": "post-body", "resumo": "post-summary"}
  shopify    SHOPIFY_<ID>_TOKEN            + publicacao.loja ("minhaloja"), publicacao.blog_id
  wix        WIX_<ID>_CHAVE (chave de API) + publicacao.site_id, publicacao.membro_id (autor)

Nunca publica direto: o cliente revisa no painel da plataforma e publica lá.
"""

import html
import os
import re
import uuid

import requests

from conteudo import publicador, render

NOMES = {"wordpress": "WordPress", "webflow": "Webflow", "shopify": "Shopify", "wix": "Wix"}
SHOPIFY_VERSAO = "2026-07"


def plataforma(cliente: dict) -> str:
    return (cliente.get("publicacao") or {}).get("plataforma") or "wordpress"


def nome(cliente: dict) -> str:
    return NOMES.get(plataforma(cliente), plataforma(cliente))


def _chave(cliente: dict, prefixo: str, campo: str) -> str:
    nome_var = f"{prefixo}_{cliente['id'].upper()}_{campo}"
    valor = os.getenv(nome_var)
    if not valor:
        raise RuntimeError(f"Falta {nome_var} no .env.")
    return valor


def _conf(cliente: dict, campo: str) -> str:
    valor = (cliente.get("publicacao") or {}).get(campo)
    if not valor:
        raise RuntimeError(f"Falta publicacao.{campo} no cadastro do cliente (Configurar).")
    return str(valor)


def enviar_rascunho(artigo: dict, cliente: dict) -> dict:
    """-> {plataforma, id, status, link, editar}. Reenviar atualiza o mesmo rascunho."""
    p = plataforma(cliente)
    anterior = artigo.get("wordpress") or {}
    mesmo = anterior.get("id") if anterior.get("plataforma", "wordpress") == p else None
    if p == "wordpress":
        r = publicador.enviar_wordpress(artigo, cliente)
    elif p == "webflow":
        r = _webflow(artigo, cliente, mesmo)
    elif p == "shopify":
        r = _shopify(artigo, cliente, mesmo)
    elif p == "wix":
        r = _wix(artigo, cliente, mesmo)
    else:
        raise RuntimeError(f"Plataforma desconhecida: {p}")
    return {"plataforma": p, **r}


# --------------------------------------------------------------------------
# Webflow (CMS API v2)
# --------------------------------------------------------------------------

def _webflow(artigo, cliente, item_id):
    token = _chave(cliente, "WEBFLOW", "TOKEN")
    colecao = _conf(cliente, "colecao")
    campos = {"corpo": "post-body", "resumo": "post-summary", **((cliente.get("publicacao") or {}).get("campos") or {})}
    corpo = {"isDraft": True, "isArchived": False, "fieldData": {
        "name": artigo["titulo"], "slug": artigo["slug"],
        campos["corpo"]: render.conteudo_post(artigo, cliente),
        campos["resumo"]: artigo["meta_descricao"]}}
    base = f"https://api.webflow.com/v2/collections/{colecao}/items"
    h = {"Authorization": f"Bearer {token}", "accept": "application/json"}
    resp = (requests.patch(f"{base}/{item_id}", json=corpo, headers=h, timeout=60) if item_id
            else requests.post(base, json=corpo, headers=h, timeout=60))
    resp.raise_for_status()
    item = resp.json()
    return {"id": item["id"], "status": "rascunho", "link": cliente["site"].rstrip("/") + "/",
            "editar": "https://webflow.com/dashboard"}


# --------------------------------------------------------------------------
# Shopify (Admin REST: artigos de blog)
# --------------------------------------------------------------------------

def _shopify(artigo, cliente, artigo_id):
    token = _chave(cliente, "SHOPIFY", "TOKEN")
    loja, blog = _conf(cliente, "loja"), _conf(cliente, "blog_id")
    versao = (cliente.get("publicacao") or {}).get("versao") or SHOPIFY_VERSAO
    base = f"https://{loja}.myshopify.com/admin/api/{versao}/blogs/{blog}/articles"
    corpo = {"article": {"title": artigo["titulo"], "handle": artigo["slug"], "published": False,
                         "body_html": render.conteudo_post(artigo, cliente),
                         "summary_html": f"<p>{html.escape(artigo['meta_descricao'])}</p>"}}
    h = {"X-Shopify-Access-Token": token}
    resp = (requests.put(f"{base}/{artigo_id}.json", json=corpo, headers=h, timeout=60) if artigo_id
            else requests.post(f"{base}.json", json=corpo, headers=h, timeout=60))
    resp.raise_for_status()
    a = resp.json()["article"]
    return {"id": a["id"], "status": "rascunho", "link": cliente["site"].rstrip("/") + "/",
            "editar": f"https://admin.shopify.com/store/{loja}/content/articles/{a['id']}"}


# --------------------------------------------------------------------------
# Wix (Blog API v3, conteúdo em Ricos)
# --------------------------------------------------------------------------

def _wix(artigo, cliente, rascunho_id):
    chave = _chave(cliente, "WIX", "CHAVE")
    site = _conf(cliente, "site_id")
    post = {"title": artigo["titulo"], "memberId": _conf(cliente, "membro_id"),
            "richContent": ricos(artigo, cliente), "seoSlug": artigo["slug"],
            "excerpt": artigo["meta_descricao"][:500]}
    h = {"Authorization": chave, "wix-site-id": site}
    base = "https://www.wixapis.com/blog/v3/draft-posts"
    resp = (requests.patch(f"{base}/{rascunho_id}", json={"draftPost": {"id": rascunho_id, **post}}, headers=h, timeout=60)
            if rascunho_id else requests.post(base, json={"draftPost": post}, headers=h, timeout=60))
    resp.raise_for_status()
    d = resp.json()["draftPost"]
    return {"id": d["id"], "status": "rascunho", "link": cliente["site"].rstrip("/") + "/",
            "editar": f"https://manage.wix.com/dashboard/{site}/blog"}


def _id() -> str:
    return uuid.uuid4().hex[:8]


def _textos(linha: str) -> list[dict]:
    """Texto com **negrito** e [links](url) -> nós TEXT do Ricos."""
    nos = []
    for parte in re.split(r"(\*\*[^*]+\*\*|\[[^\]]+\]\([^)]+\))", linha):
        if not parte:
            continue
        deco, texto = [], parte
        if parte.startswith("**") and parte.endswith("**"):
            texto, deco = parte[2:-2], [{"type": "BOLD", "fontWeightValue": 700}]
        elif m := re.fullmatch(r"\[([^\]]+)\]\(([^)]+)\)", parte):
            texto, deco = m.group(1), [{"type": "LINK", "linkData": {"link": {"url": m.group(2), "target": "BLANK"}}}]
        nos.append({"type": "TEXT", "id": "", "nodes": [], "textData": {"text": texto, "decorations": deco}})
    return nos


def _paragrafo(linha: str) -> dict:
    return {"type": "PARAGRAPH", "id": _id(), "nodes": _textos(linha), "paragraphData": {}}


def _titulo(texto: str, nivel: int) -> dict:
    return {"type": "HEADING", "id": _id(), "nodes": _textos(texto), "headingData": {"level": nivel}}


def markdown_para_ricos(md: str) -> list[dict]:
    nos, lista, tipo_lista, paragrafo = [], [], None, []

    def fechar():
        nonlocal lista, tipo_lista, paragrafo
        if paragrafo:
            nos.append(_paragrafo(" ".join(paragrafo)))
            paragrafo = []
        if lista:
            nos.append({"type": tipo_lista, "id": _id(), "nodes": [
                {"type": "LIST_ITEM", "id": _id(), "nodes": [_paragrafo(i)]} for i in lista]})
            lista, tipo_lista = [], None

    for linha in md.splitlines():
        limpa = linha.strip()
        if not limpa:
            fechar()
        elif m := re.match(r"^(#{1,6})\s+(.*)", limpa):
            fechar()
            nos.append(_titulo(m.group(2), min(max(len(m.group(1)), 2), 6)))
        elif m := re.match(r"^([-*]|\d+[.)])\s+(.*)", limpa):
            novo = "ORDERED_LIST" if m.group(1)[0].isdigit() else "BULLETED_LIST"
            if paragrafo or (tipo_lista and tipo_lista != novo):
                fechar()
            tipo_lista = novo
            lista.append(m.group(2))
        else:
            if lista:
                fechar()
            paragrafo.append(limpa)
    fechar()
    return nos


def ricos(artigo: dict, cliente: dict) -> dict:
    nos = [_paragrafo(f"**Resposta rápida:** {artigo['resposta_direta']}")]
    nos += markdown_para_ricos(artigo["corpo_markdown"])
    if artigo["faq"]:
        nos.append(_titulo("Perguntas frequentes", 2))
        for f in artigo["faq"]:
            nos += [_titulo(f["pergunta"], 3), _paragrafo(f["resposta"])]
    cta = cliente["perfil"]["cta"]
    nos.append(_paragrafo(f"[{cta['texto']}]({render.link_whatsapp(cta['whatsapp'], artigo['titulo'])})"))
    return {"nodes": nos}
