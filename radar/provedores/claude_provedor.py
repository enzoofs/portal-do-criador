"""
radar/provedores/claude_provedor.py — Claude via Messages API + web search.
"""

import anthropic

from config import settings
from custos import contador
from radar.modelos import Fonte, Resposta
from radar.provedores.base import SISTEMA, Provedor

# Buscas longas podem pausar o turno no servidor (stop_reason "pause_turn");
# reenviamos a conversa para ele continuar, até este limite.
MAX_CONTINUACOES = 5


class ClaudeProvedor(Provedor):
    nome = "claude"

    def __init__(self):
        self.modelo = settings.CLAUDE_MODEL
        self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    def perguntar(self, pergunta: str, tipo: str, cliente: dict) -> Resposta:
        tools = [{
            "type": "web_search_20260209",
            "name": "web_search",
            "max_uses": settings.MAX_BUSCAS_POR_PERGUNTA,
            "user_location": {
                "type": "approximate",
                "city": cliente["cidade"],
                "region": cliente["regiao"],
                "country": cliente["pais"],
                "timezone": "America/Sao_Paulo",
            },
        }]
        messages = [{"role": "user", "content": pergunta}]
        entrada = saida = buscas = 0

        for _ in range(MAX_CONTINUACOES):
            contador.checar()
            resp = self.client.beta.messages.create(
                model=self.modelo,
                max_tokens=16000,
                system=SISTEMA.format(**cliente),
                messages=messages,
                tools=tools,
                output_config={"effort": settings.CLAUDE_EFFORT},
                # Se um classificador recusar, a API refaz no modelo de fallback
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
            u = resp.usage
            entrada += u.input_tokens + (u.cache_creation_input_tokens or 0) + (u.cache_read_input_tokens or 0)
            saida += u.output_tokens
            buscas += (u.server_tool_use.web_search_requests or 0) if u.server_tool_use else 0
            if resp.stop_reason != "pause_turn":
                break
            messages = [
                {"role": "user", "content": pergunta},
                {"role": "assistant", "content": resp.content},
            ]

        contador.registrar(self.nome, self.modelo, entrada, saida, buscas)
        if resp.stop_reason == "refusal":
            return Resposta(provedor=self.nome, modelo=self.modelo, pergunta=pergunta,
                            tipo_pergunta=tipo, erro="recusado pelo modelo")

        texto, fontes, buscas = [], {}, []
        for bloco in resp.content:
            if bloco.type == "server_tool_use" and bloco.name == "web_search":
                q = (bloco.input or {}).get("query") if isinstance(bloco.input, dict) else None
                if q:
                    buscas.append(q)  # o que o Claude pesquisou
            elif bloco.type == "text":
                texto.append(bloco.text)
                for cit in getattr(bloco, "citations", None) or []:
                    url = getattr(cit, "url", None)
                    if url:
                        fontes.setdefault(url, Fonte(url, getattr(cit, "title", "") or ""))
            elif bloco.type == "web_search_tool_result":
                # Sucesso = lista de resultados; erro = objeto (não levanta exceção)
                if isinstance(bloco.content, list):
                    for r in bloco.content:
                        fontes.setdefault(r.url, Fonte(r.url, r.title or ""))

        return Resposta(
            provedor=self.nome, modelo=resp.model, pergunta=pergunta, tipo_pergunta=tipo,
            texto="".join(texto), fontes=list(fontes.values()), buscas=list(dict.fromkeys(buscas)),
        )
