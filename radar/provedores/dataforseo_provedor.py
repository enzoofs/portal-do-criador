"""
radar/provedores/dataforseo_provedor.py — Respostas como o usuário vê no app.

A API do ChatGPT responde diferente do app (estudos mostram pouca sobreposição
de marcas). A DataForSEO abre o app de verdade e devolve o texto renderizado,
as fontes citadas, as buscas que a IA fez e as marcas destacadas. Cobre:

  chatgpt_app   ChatGPT, como no chatgpt.com          (LLM Scraper)
  gemini_app    Gemini, como no gemini.google.com      (LLM Scraper)
  google_ia     Resumo de IA no topo da busca Google   (SERP + AI Overview)
  google_modo   Modo IA do Google                      (SERP AI Mode)

Custo: cerca de US$ 0,004 por pergunta (US$ 0,006 no resumo de IA); o valor
real vem no campo "cost" de cada resposta e entra na trava de gasto.
Docs: docs.dataforseo.com/v3/ai_optimization e /v3/serp/google.
"""

import requests

from config import settings
from custos import contador
from radar.modelos import Fonte, Resposta
from radar.provedores.base import Provedor

API = "https://api.dataforseo.com/v3"


class ErroDataForSEO(RuntimeError):
    pass


def chamar(caminho: str, tarefa: dict, timeout: int = 150) -> tuple[dict, float]:
    """POST de uma tarefa "live"; devolve (result[0], custo em US$)."""
    r = requests.post(f"{API}/{caminho}", json=[tarefa], timeout=timeout,
                      auth=(settings.DATAFORSEO_LOGIN, settings.DATAFORSEO_SENHA))
    try:
        corpo = r.json()
    except ValueError:
        r.raise_for_status()
        raise
    # A DataForSEO explica o erro no corpo (ex.: 40104 = conta ainda não verificada)
    if corpo.get("status_code") != 20000:
        raise ErroDataForSEO(f"{corpo.get('status_code')} {corpo.get('status_message')}")
    t = (corpo.get("tasks") or [{}])[0]
    if t.get("status_code") != 20000:
        raise ErroDataForSEO(f"{t.get('status_code')} {t.get('status_message')}")
    return ((t.get("result") or [None])[0] or {}), float(t.get("cost") or 0)


def _local() -> dict:
    return {"location_code": settings.DATAFORSEO_LOCAL, "language_code": settings.DATAFORSEO_IDIOMA}


class _Base(Provedor):
    caminho = ""

    def tarefa(self, pergunta: str) -> dict:
        return {"keyword": pergunta[:700], **_local()}

    def ler(self, res: dict) -> tuple[str, dict[str, Fonte], list[str], list[str]]:
        """-> (texto, fontes, buscas, marcas destacadas)"""
        raise NotImplementedError

    def perguntar(self, pergunta: str, tipo: str, cliente: dict) -> Resposta:
        contador.checar()
        res, custo = chamar(self.caminho, self.tarefa(pergunta))
        contador.registrar_valor(self.nome, self.modelo, custo)
        texto, fontes, buscas, marcas = self.ler(res)
        r = Resposta(provedor=self.nome, modelo=res.get("model") or self.modelo, pergunta=pergunta,
                     tipo_pergunta=tipo, texto=texto, fontes=list(fontes.values()),
                     buscas=list(dict.fromkeys(buscas)))
        if marcas:
            r.marcas_destacadas = marcas
        return r


def _fonte(d: dict, fontes: dict[str, Fonte]):
    url = d.get("url")
    if url:
        fontes.setdefault(url, Fonte(url, d.get("title") or d.get("source_name") or ""))


class ChatGPTApp(_Base):
    nome, modelo = "chatgpt_app", "chatgpt.com"
    caminho = "ai_optimization/chat_gpt/llm_scraper/live/advanced"

    def tarefa(self, pergunta):
        return {**super().tarefa(pergunta), "force_web_search": True}

    def ler(self, res):
        fontes: dict[str, Fonte] = {}
        for s in res.get("sources") or []:          # citadas na resposta
            _fonte(s, fontes)
        for s in res.get("search_results") or []:   # consultadas
            _fonte(s, fontes)
        marcas = [b["title"] for b in res.get("brand_entities") or [] if b.get("title")]
        return res.get("markdown") or "", fontes, res.get("fan_out_queries") or [], marcas


class GeminiApp(_Base):
    nome, modelo = "gemini_app", "gemini.google.com"
    caminho = "ai_optimization/gemini/llm_scraper/live/advanced"

    def ler(self, res):
        fontes: dict[str, Fonte] = {}
        for s in res.get("sources") or []:
            _fonte(s, fontes)
        for item in res.get("items") or []:
            for s in item.get("sources") or []:
                _fonte(s, fontes)
        return res.get("markdown") or "", fontes, [], []


def _ler_ai_overview(res: dict) -> tuple[str, dict[str, Fonte]]:
    """Resumo de IA / modo IA: junta o markdown e as referências do bloco ai_overview."""
    textos, fontes = [], {}
    for item in res.get("items") or []:
        if item.get("type") != "ai_overview":
            continue
        if item.get("markdown"):
            textos.append(item["markdown"])
        for ref in item.get("references") or []:
            _fonte(ref, fontes)
        for el in item.get("items") or []:
            if not item.get("markdown") and (el.get("markdown") or el.get("text")):
                textos.append(el.get("markdown") or el.get("text"))
            for ref in el.get("references") or []:
                _fonte(ref, fontes)
            for link in el.get("links") or []:
                _fonte(link, fontes)
    return "\n\n".join(textos), fontes


class GoogleResumoIA(_Base):
    nome, modelo = "google_ia", "google.com (resumo de IA)"
    caminho = "serp/google/organic/live/advanced"

    def tarefa(self, pergunta):
        return {**super().tarefa(pergunta), "load_async_ai_overview": True, "depth": 10}

    def ler(self, res):
        texto, fontes = _ler_ai_overview(res)
        # Sem resumo de IA para esta busca: registra isso no texto, sem inventar resposta
        return texto or "(O Google não mostrou resumo de IA para esta busca.)", fontes, [], []


class GoogleModoIA(_Base):
    nome, modelo = "google_modo", "google.com (modo IA)"
    caminho = "serp/google/ai_mode/live/advanced"

    def ler(self, res):
        texto, fontes = _ler_ai_overview(res)
        return texto, fontes, [], []


PROVEDORES = [ChatGPTApp, GeminiApp, GoogleResumoIA, GoogleModoIA]
