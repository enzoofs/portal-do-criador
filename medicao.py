"""
medicao.py — Resultado em leads, não só em visitas: GA4 + Search Console.

O que mede, por cliente:
  - visitas que chegaram vindas de IAs (ChatGPT, Perplexity, Gemini, Copilot, Claude…)  [GA4]
  - cliques no botão de WhatsApp de cada artigo (saída para wa.me)                       [GA4]
  - cliques e impressões de cada artigo na busca do Google                               [Search Console]

Acesso: uma conta de serviço do Google (arquivo JSON, caminho em GOOGLE_CREDENCIAIS no .env)
com permissão de Leitor na propriedade do GA4 e de Usuário no Search Console do cliente.
No cadastro do cliente: medicao.ga4 (ID numérico da propriedade) e medicao.search_console
("sc-domain:site.com.br" ou "https://site.com.br/"). As duas APIs são gratuitas.
"""

import json
from datetime import date, datetime, timedelta
from urllib.parse import quote, urlparse

from config import settings

PASTA = settings.BASE_DIR / "data" / "medicao"
ESCOPOS = ["https://www.googleapis.com/auth/analytics.readonly",
           "https://www.googleapis.com/auth/webmasters.readonly"]
# Origens de visita que são assistentes de IA
FONTES_IA = r"chatgpt|openai|perplexity|gemini\.google|bard\.google|copilot|claude\.ai|deepseek|grok|meta\.ai"
NOMES_FONTE = [("chatgpt", "ChatGPT"), ("openai", "ChatGPT"), ("perplexity", "Perplexity"), ("gemini", "Gemini"),
               ("bard", "Gemini"), ("copilot", "Copilot"), ("claude", "Claude"), ("deepseek", "DeepSeek"),
               ("grok", "Grok"), ("meta.ai", "Meta AI")]


class SemAcesso(RuntimeError):
    pass


def configurado(cliente: dict) -> dict:
    m = cliente.get("medicao") or {}
    return {"ga4": bool(m.get("ga4")), "search_console": bool(m.get("search_console")),
            "credencial": bool(settings.GOOGLE_CREDENCIAIS)}


def _sessao():
    if not settings.GOOGLE_CREDENCIAIS:
        raise SemAcesso("Falta GOOGLE_CREDENCIAIS no .env (arquivo JSON da conta de serviço).")
    from google.auth.transport.requests import AuthorizedSession
    from google.oauth2 import service_account
    cred = service_account.Credentials.from_service_account_file(settings.GOOGLE_CREDENCIAIS, scopes=ESCOPOS)
    return AuthorizedSession(cred)


def _post(sessao, url: str, corpo: dict) -> dict:
    r = sessao.post(url, json=corpo, timeout=60)
    if r.status_code >= 400:
        try:
            msg = r.json().get("error", {}).get("message", r.text[:200])
        except ValueError:
            msg = r.text[:200]
        raise SemAcesso(f"{r.status_code}: {msg}")
    return r.json()


# --------------------------------------------------------------------------
# GA4
# --------------------------------------------------------------------------

def _ga4(sessao, propriedade: str, corpo: dict) -> list[dict]:
    url = f"https://analyticsdata.googleapis.com/v1beta/properties/{propriedade}:runReport"
    res = _post(sessao, url, corpo)
    linhas = []
    for row in res.get("rows") or []:
        linhas.append({"d": [v.get("value", "") for v in row.get("dimensionValues", [])],
                       "m": [float(v.get("value") or 0) for v in row.get("metricValues", [])]})
    return linhas


def nome_fonte(origem: str) -> str:
    o = origem.lower()
    return next((n for chave, n in NOMES_FONTE if chave in o), origem)


def visitas_ia(sessao, propriedade: str, inicio: str, fim: str) -> dict:
    linhas = _ga4(sessao, propriedade, {
        "dateRanges": [{"startDate": inicio, "endDate": fim}],
        "dimensions": [{"name": "sessionSource"}, {"name": "landingPage"}],
        "metrics": [{"name": "sessions"}],
        "dimensionFilter": {"filter": {"fieldName": "sessionSource",
                                       "stringFilter": {"matchType": "PARTIAL_REGEXP", "value": FONTES_IA}}},
        "limit": 1000,
    })
    por_fonte: dict[str, int] = {}
    por_pagina: dict[str, int] = {}
    for registro in linhas:
        fonte, pagina = registro["d"]
        n = int(registro["m"][0])
        por_fonte[nome_fonte(fonte)] = por_fonte.get(nome_fonte(fonte), 0) + n
        por_pagina[pagina] = por_pagina.get(pagina, 0) + n
    return {"total": sum(por_fonte.values()),
            "por_fonte": sorted(por_fonte.items(), key=lambda x: -x[1]),
            "por_pagina": por_pagina}


def cliques_whatsapp(sessao, propriedade: str, inicio: str, fim: str) -> dict:
    """Cliques de saída para wa.me / api.whatsapp.com (medição aprimorada do GA4), por página."""
    linhas = _ga4(sessao, propriedade, {
        "dateRanges": [{"startDate": inicio, "endDate": fim}],
        "dimensions": [{"name": "pagePath"}, {"name": "linkUrl"}],
        "metrics": [{"name": "eventCount"}],
        "dimensionFilter": {"andGroup": {"expressions": [
            {"filter": {"fieldName": "eventName", "stringFilter": {"matchType": "EXACT", "value": "click"}}},
            {"filter": {"fieldName": "linkUrl",
                        "stringFilter": {"matchType": "PARTIAL_REGEXP", "value": r"wa\.me|whatsapp\.com"}}},
        ]}},
        "limit": 1000,
    })
    por_pagina: dict[str, int] = {}
    for registro in linhas:
        por_pagina[registro["d"][0]] = por_pagina.get(registro["d"][0], 0) + int(registro["m"][0])
    return {"total": sum(por_pagina.values()), "por_pagina": por_pagina}


# --------------------------------------------------------------------------
# Search Console
# --------------------------------------------------------------------------

def busca_google(sessao, site: str, inicio: str, fim: str) -> dict:
    url = f"https://searchconsole.googleapis.com/webmasters/v3/sites/{quote(site, safe='')}/searchAnalytics/query"
    res = _post(sessao, url, {"startDate": inicio, "endDate": fim, "dimensions": ["page"], "rowLimit": 500})
    por_pagina = {}
    for row in res.get("rows") or []:
        por_pagina[urlparse(row["keys"][0]).path or "/"] = {
            "cliques": int(row.get("clicks", 0)), "impressoes": int(row.get("impressions", 0)),
            "posicao": round(row.get("position", 0), 1)}
    return {"cliques": sum(p["cliques"] for p in por_pagina.values()),
            "impressoes": sum(p["impressoes"] for p in por_pagina.values()), "por_pagina": por_pagina}


# --------------------------------------------------------------------------
# Coleta e leitura
# --------------------------------------------------------------------------

def _da_pagina(por_pagina: dict, slug: str):
    """Soma o que for da página do artigo (/slug/, /blog/slug/, com ou sem barra no fim)."""
    return [v for k, v in por_pagina.items() if slug and slug in k]


def coletar(cliente: dict, dias: int = 28, artigos: list[dict] | None = None) -> dict:
    m = cliente.get("medicao") or {}
    fim = date.today() - timedelta(days=1)
    inicio = fim - timedelta(days=dias - 1)
    ini_s, fim_s = inicio.isoformat(), fim.isoformat()
    sessao = _sessao()
    res = {"gerado_em": datetime.now().isoformat(timespec="seconds"), "periodo": [ini_s, fim_s],
           "demo": False, "erros": {}}
    if m.get("ga4"):
        try:
            res["ia"] = visitas_ia(sessao, m["ga4"], ini_s, fim_s)
        except SemAcesso as e:
            res["erros"]["ga4"] = str(e)
        try:
            res["whatsapp"] = cliques_whatsapp(sessao, m["ga4"], ini_s, fim_s)
        except SemAcesso as e:
            res["erros"]["whatsapp"] = str(e)
    if m.get("search_console"):
        try:
            res["google"] = busca_google(sessao, m["search_console"], ini_s, fim_s)
        except SemAcesso as e:
            res["erros"]["search_console"] = str(e)
    res["artigos"] = por_artigo(res, artigos or [])
    _salvar(cliente["id"], res)
    return res


def por_artigo(res: dict, artigos: list[dict]) -> list[dict]:
    saida = []
    for a in artigos:
        slug = a["slug"]
        g = _da_pagina((res.get("google") or {}).get("por_pagina", {}), slug)
        saida.append({
            "slug": slug, "titulo": a["titulo"],
            "visitas_ia": sum(_da_pagina((res.get("ia") or {}).get("por_pagina", {}), slug)),
            "whatsapp": sum(_da_pagina((res.get("whatsapp") or {}).get("por_pagina", {}), slug)),
            "cliques_google": sum(x["cliques"] for x in g), "impressoes": sum(x["impressoes"] for x in g),
        })
    return saida


def _salvar(cliente_id: str, res: dict):
    pasta = PASTA / cliente_id
    pasta.mkdir(parents=True, exist_ok=True)
    nome = datetime.now().strftime("%Y%m%d-%H%M%S") + ("-demo" if res.get("demo") else "") + ".json"
    (pasta / nome).write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")


def ultima(cliente_id: str) -> dict | None:
    arquivos = sorted((PASTA / cliente_id).glob("*.json"))
    reais = [p for p in arquivos if "-demo" not in p.name]
    escolhido = (reais or arquivos or [None])[-1]
    return json.loads(escolhido.read_text(encoding="utf-8")) if escolhido else None
