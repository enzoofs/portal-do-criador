"""
ia.py — Chamada única de IA com saída estruturada (JSON validado por Pydantic).

Usado pelo extrator do radar, pela pauta e pelo redator. Tenta os provedores
na ordem de settings.GERACAO_PROVEDORES e usa o primeiro com chave.
"""

import json
from typing import TypeVar

from pydantic import BaseModel

from config import settings
from custos import contador

T = TypeVar("T", bound=BaseModel)


class SemChaveDeIA(RuntimeError):
    pass


# Campos do perfil que não ajudam a escrever e identificam alguém (o WhatsApp costuma ser o celular
# do dono) ou são notas internas: ficam fora do prompt (LGPD, Art. 6, III: necessidade)
_FORA_DO_PROMPT = ("cta", "_fonte")


def perfil_para_prompt(perfil: dict) -> str:
    return json.dumps({k: v for k, v in perfil.items() if k not in _FORA_DO_PROMPT}, ensure_ascii=False, indent=1)


# Provedores que falharam por conta (crédito, chave) nesta execução: pulados daqui em diante
_indisponiveis: set[str] = set()


def _provedores_com_chave() -> list[str]:
    chaves = {"claude": settings.ANTHROPIC_API_KEY, "openai": settings.OPENAI_API_KEY}
    return [p for p in settings.GERACAO_PROVEDORES if chaves.get(p) and p not in _indisponiveis]


def provedor_disponivel() -> str | None:
    provedores = _provedores_com_chave()
    return provedores[0] if provedores else None


def _erro_de_conta(e: Exception) -> bool:
    """Falta de crédito ou chave inválida: não adianta repetir no mesmo provedor."""
    status = getattr(e, "status_code", None)
    texto = str(e).lower()
    return status in (401, 402, 403) or "credit balance" in texto or "insufficient_quota" in texto


def modelo_de(provedor: str, nivel: str) -> str:
    return settings.MODELOS_GERACAO[nivel][provedor]


def gerar(prompt: str, formato: type[T], sistema: str = "", esforco: str = "medium",
          max_tokens: int = 16000, nivel: str = "redacao") -> T:
    provedores = _provedores_com_chave()
    if not provedores:
        raise SemChaveDeIA("Nenhuma chave de IA utilizável no .env (ANTHROPIC_API_KEY ou OPENAI_API_KEY).")
    for i, provedor in enumerate(provedores):
        contador.checar()
        try:
            if provedor == "claude":
                return _claude(prompt, formato, sistema, esforco, max_tokens, modelo_de("claude", nivel))
            return _openai(prompt, formato, sistema, modelo_de("openai", nivel))
        except Exception as e:
            if not _erro_de_conta(e) or i == len(provedores) - 1:
                raise
            _indisponiveis.add(provedor)
    raise SemChaveDeIA("Nenhum provedor de IA respondeu.")  # inalcançável: o último erro já sobe acima


def _claude(prompt, formato, sistema, esforco, max_tokens, modelo):
    import anthropic
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    extra = {"system": sistema} if sistema else {}
    if "haiku" not in modelo:  # Haiku não tem fallback no servidor
        # Se um classificador recusar, a API refaz no modelo de fallback
        extra.update(betas=["server-side-fallback-2026-07-01"], fallbacks="default")
    resp = client.beta.messages.parse(
        model=modelo,
        max_tokens=max_tokens,
        output_config={"effort": esforco},
        messages=[{"role": "user", "content": prompt}],
        output_format=formato,
        **extra,
    )
    u = resp.usage
    contador.registrar("claude", modelo, u.input_tokens, u.output_tokens)
    if resp.stop_reason == "refusal":
        raise RuntimeError("O modelo recusou a solicitação.")
    if resp.stop_reason == "max_tokens" or resp.parsed_output is None:
        raise RuntimeError(f"Resposta incompleta (stop_reason={resp.stop_reason}).")
    return resp.parsed_output


def _openai(prompt, formato, sistema, modelo):
    from openai import OpenAI
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    resp = client.responses.parse(
        model=modelo,
        instructions=sistema or None,
        input=prompt,
        text_format=formato,
        store=False,   # a OpenAI não guarda a resposta (o padrão guardaria por até 30 dias)
    )
    contador.registrar("chatgpt", modelo, resp.usage.input_tokens, resp.usage.output_tokens)
    if resp.output_parsed is None:
        raise RuntimeError("Resposta da OpenAI sem JSON válido.")
    return resp.output_parsed
