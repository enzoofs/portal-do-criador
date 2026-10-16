"""
radar/provedores/gemini_provedor.py — Gemini com grounding no Google Search.
"""

from google import genai
from google.genai import types

from config import settings
from custos import contador
from radar.modelos import Fonte, Resposta
from radar.provedores.base import SISTEMA, Provedor


class GeminiProvedor(Provedor):
    nome = "gemini"

    def __init__(self):
        self.modelo = settings.GEMINI_MODEL
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)

    def perguntar(self, pergunta: str, tipo: str, cliente: dict) -> Resposta:
        contador.checar()
        resp = self.client.models.generate_content(
            model=self.modelo,
            contents=pergunta,
            config=types.GenerateContentConfig(
                system_instruction=SISTEMA.format(**cliente),
                tools=[types.Tool(google_search=types.GoogleSearch())],
            ),
        )

        u = resp.usage_metadata
        contador.registrar(self.nome, self.modelo, (u.prompt_token_count or 0) if u else 0,
                           (u.candidates_token_count or 0) if u else 0)
        fontes: dict[str, Fonte] = {}
        buscas: list[str] = []
        for cand in resp.candidates or []:
            meta = cand.grounding_metadata
            buscas += (meta.web_search_queries if meta else None) or []  # o que o Gemini pesquisou
            for chunk in (meta.grounding_chunks if meta else None) or []:
                web = chunk.web
                if web and web.uri:
                    # Na Gemini API a URI é um link de redirecionamento do
                    # Google; o título traz o domínio real da página.
                    titulo = web.title or ""
                    fontes.setdefault(web.uri, Fonte(web.uri, titulo, dominio=titulo.lower()))

        return Resposta(
            provedor=self.nome, modelo=self.modelo, pergunta=pergunta, tipo_pergunta=tipo,
            texto=resp.text or "", fontes=list(fontes.values()), buscas=list(dict.fromkeys(buscas)),
        )
