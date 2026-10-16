"""
radar/provedores/openai_provedor.py — ChatGPT via Responses API + web search.
"""

from openai import OpenAI

from config import settings
from custos import contador
from radar.modelos import Fonte, Resposta
from radar.provedores.base import SISTEMA, Provedor


class OpenAIProvedor(Provedor):
    nome = "chatgpt"

    def __init__(self):
        self.modelo = settings.OPENAI_MODEL
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)

    def perguntar(self, pergunta: str, tipo: str, cliente: dict) -> Resposta:
        contador.checar()
        resp = self.client.responses.create(
            model=self.modelo,
            instructions=SISTEMA.format(**cliente),
            input=pergunta,
            store=False,   # a OpenAI não guarda a resposta (o padrão guardaria por até 30 dias)
            tools=[{
                "type": "web_search",
                "user_location": {
                    "type": "approximate",
                    "city": cliente["cidade"],
                    "region": cliente["regiao"],
                    "country": cliente["pais"],
                },
            }],
            include=["web_search_call.action.sources"],
        )

        contador.registrar(self.nome, self.modelo, resp.usage.input_tokens, resp.usage.output_tokens,
                           buscas=sum(item.type == "web_search_call" for item in resp.output))
        fontes: dict[str, Fonte] = {}
        buscas: list[str] = []
        for item in resp.output:
            if item.type == "message":
                for parte in item.content:
                    for anot in getattr(parte, "annotations", None) or []:
                        if anot.type == "url_citation":
                            fontes.setdefault(anot.url, Fonte(anot.url, anot.title))
            elif item.type == "web_search_call":
                acao = item.action
                # O que o ChatGPT pesquisou: vira pauta e alvo de SEO
                buscas += [q for q in [getattr(acao, "query", None), *(getattr(acao, "queries", None) or [])] if q]
                # Páginas consultadas mas não necessariamente citadas no texto
                for src in getattr(acao, "sources", None) or []:
                    url = getattr(src, "url", None)
                    if url:
                        fontes.setdefault(url, Fonte(url))

        return Resposta(
            provedor=self.nome, modelo=self.modelo, pergunta=pergunta,
            tipo_pergunta=tipo, texto=resp.output_text, fontes=list(fontes.values()),
            buscas=list(dict.fromkeys(buscas)),
        )
