"""
radar/provedores — Escolhe os provedores conforme as chaves configuradas.
"""

from config import settings
from radar.provedores.base import Provedor


def provedores_reais(filtro: list[str] | None = None) -> list[Provedor]:
    """Instancia só os provedores que têm chave (e que estão no filtro, se houver)."""
    disponiveis = []
    if settings.OPENAI_API_KEY:
        from radar.provedores.openai_provedor import OpenAIProvedor
        disponiveis.append(OpenAIProvedor)
    if settings.ANTHROPIC_API_KEY:
        from radar.provedores.claude_provedor import ClaudeProvedor
        disponiveis.append(ClaudeProvedor)
    if settings.GEMINI_API_KEY:
        from radar.provedores.gemini_provedor import GeminiProvedor
        disponiveis.append(GeminiProvedor)
    if settings.DATAFORSEO_LOGIN and settings.DATAFORSEO_SENHA:
        from radar.provedores.dataforseo_provedor import PROVEDORES
        disponiveis += PROVEDORES
    filtro = filtro or settings.RADAR_PROVEDORES
    return [cls() for cls in disponiveis if not filtro or cls.nome in filtro]
