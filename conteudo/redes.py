"""
conteudo/redes.py — Cada artigo vira post para LinkedIn e carrossel para Instagram.

Sem IA e sem custo: usa as partes que o artigo já tem (resposta rápida, subtítulos
em forma de pergunta e a primeira frase de cada seção). O texto sai pronto para
copiar e revisar; nada é publicado nas redes pelo sistema.
"""

import re

from conteudo.render import MARCADOR

MAX_SLIDES = 6


def _limpo(t: str) -> str:
    t = MARCADOR.sub("", t)
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)          # [texto](link) -> texto
    t = re.sub(r"[*_`>#]+", "", t)
    return re.sub(r"\s+", " ", t).strip()


def _primeira_frase(t: str, limite: int = 220) -> str:
    frase = re.split(r"(?<=[.!?])\s+", _limpo(t))[0]
    return frase if len(frase) <= limite else frase[:limite].rsplit(" ", 1)[0] + "…"


def secoes(corpo_markdown: str) -> list[tuple[str, str]]:
    """(subtítulo, primeiro parágrafo) de cada seção ## do artigo."""
    partes = re.split(r"^##\s+", corpo_markdown, flags=re.M)[1:]
    saida = []
    for p in partes:
        titulo, _, resto = p.partition("\n")
        paragrafo = next((bloco for bloco in resto.split("\n\n") if bloco.strip() and not bloco.lstrip().startswith(("#", "|", "-", "*", "1."))), "")
        if titulo.strip() and paragrafo:
            saida.append((_limpo(titulo), _primeira_frase(paragrafo)))
    return saida


def gerar(artigo: dict, cliente: dict, url: str) -> dict:
    nome = cliente["nome"]
    cta = cliente.get("perfil", {}).get("cta", {})
    secs = [s for s in secoes(artigo.get("corpo_markdown", "")) if not s[0].lower().startswith("perguntas frequentes")]
    resposta = _primeira_frase(artigo.get("resposta_direta", ""), 280)

    pontos = "\n".join(f"→ {t}" for t, _ in secs[:4])
    linkedin = (f"{artigo['titulo']}\n\n{resposta}\n\n"
                + (f"No artigo:\n{pontos}\n\n" if pontos else "")
                + f"Leia completo: {url}")

    slides = [{"titulo": artigo["titulo"], "texto": f"Arraste para o lado →  {nome}"}]
    slides += [{"titulo": t, "texto": f} for t, f in secs[:MAX_SLIDES - 2]]
    slides.append({"titulo": "Quer ajuda com isso?",
                   "texto": f"{cta.get('texto') or f'Fale com a {nome}'}. Link na bio."})
    tags = " ".join("#" + re.sub(r"\W", "", w.title()) for w in
                    [cliente.get("cidade", ""), *(artigo.get("tema", {}).get("nicho", "") or "").split(" e ")][:3] if w and w != "geral")
    legenda = f"{resposta}\n\nArtigo completo no blog (link na bio).\n\n{tags}".strip()
    return {"linkedin": linkedin, "slides": slides, "legenda": legenda}
