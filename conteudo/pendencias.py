"""
conteudo/pendencias.py — Os marcadores [[...]] do redator viram campos para o especialista.

Em vez de caçar o trecho amarelo no texto, o especialista vê cada pendência como uma
pergunta com o trecho em volta, responde no campo e o texto é atualizado sozinho.

    [[CONFIRMAR: mais de 100 empresas]]        -> manter o dado, corrigir ou tirar
    [[DADO DO ESPECIALISTA: um case real]]     -> escrever o dado ou tirar o trecho
"""

import re

MARCADOR = re.compile(r"\[\[([^\]]+)\]\]")
USAR, TIRAR, DEPOIS = "usar", "tirar", "depois"
_LACUNA = "⁣"  # separador invisível: marca onde estava a pendência enquanto o markdown é limpo

# "contexto desses cases antes de publicar" é instrução, não um dado a manter
_INSTRUCAO = re.compile(r"^\w+(ar|er|ir)\b|antes de publicar|explicitamente", re.I)


def _textos(a: dict) -> list[str]:
    return [a.get("resposta_direta", ""), a.get("corpo_markdown", "")] + [f["resposta"] for f in a.get("faq", [])]


def _sem_markdown(t: str) -> str:
    return re.sub(r"[#*_>`]+(?=\S)|(?<=\S)[*_`]+", "", t).strip(" -")


def _contexto(marcador: str, textos: list[str]) -> str:
    """A frase onde o marcador aparece, com ele trocado por ____. Se o marcador é o
    parágrafo inteiro, mostra o fim do parágrafo anterior."""
    alvo = f"[[{marcador}]]"
    for t in textos:
        linhas = t.splitlines()
        for n, linha in enumerate(linhas):
            if alvo not in linha:
                continue
            frases = re.split(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ])", linha)
            frase = next((f for f in frases if alvo in f), linha)
            frase = _sem_markdown(MARCADOR.sub(lambda m: _LACUNA if m.group(1) == marcador else "…", frase))
            if not frase.strip(_LACUNA + " .…"):
                antes = next((trecho for trecho in reversed(linhas[:n]) if trecho.strip() and not trecho.lstrip().startswith("#")), "")
                fim = re.split(r"(?<=[.!?])\s+", _sem_markdown(MARCADOR.sub("…", antes)))[-1] if antes else ""
                return f"Logo depois de: {fim}" if fim else ""
            if len(frase) > 260:
                i = frase.index(_LACUNA)
                frase = "…" + frase[max(0, i - 180):i + 80] + "…"
            return frase.replace(_LACUNA, "____")
    return ""


def listar(a: dict) -> list[dict]:
    """Uma entrada por marcador distinto, na ordem em que aparecem."""
    textos = _textos(a)
    vistos, itens = set(), []
    for m in MARCADOR.findall(" ".join(textos)):
        if m in vistos:
            continue
        vistos.add(m)
        tipo, _, texto = m.partition(":")
        texto = texto.strip()
        confirmar = tipo.strip().upper() == "CONFIRMAR" and texto and not _INSTRUCAO.search(texto)
        itens.append({
            "marcador": m,
            "tipo": "confirmar" if confirmar else "dado",
            "pedido": texto or m.strip(),
            "sugestao": texto if confirmar else "",
            "contexto": _contexto(m, textos),
        })
    return itens


def _limpar(texto: str) -> str:
    texto = re.sub(r"[ \t]{2,}", " ", texto)
    texto = re.sub(r"[ \t]+([,.;:!?])", r"\1", texto)
    texto = re.sub(r"\(\s*\)", "", texto)
    texto = re.sub(r",\s*(,|\.|e\s*\.)", r"\1", texto)
    linhas = [trecho for trecho in texto.split("\n") if trecho.strip(" \t-*>.,;:") or not trecho.strip()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(linhas)).strip()


def _trocar(texto: str, marcador: str, valor: str | None) -> str:
    alvo = f"[[{marcador}]]"
    if alvo not in texto:
        return texto
    if valor is None:  # tirar: some o marcador e, se sobrar só pontuação, a linha
        return _limpar(texto.replace(alvo, ""))
    return texto.replace(alvo, valor)


def decidir(acao: str, valor: str, original: str) -> str:
    """Quem digitou algo novo quer usar, mesmo sem mudar a opção."""
    valor = valor.strip()
    if acao == DEPOIS and valor and valor != original.strip():
        return USAR
    if acao == USAR and not valor:
        return DEPOIS
    return acao


def aplicar(a: dict, respostas: list[tuple[str, str, str]]) -> int:
    """respostas: (marcador, ação, valor). Devolve quantas pendências foram resolvidas."""
    feitas = 0
    for marcador, acao, valor in respostas:
        if acao not in (USAR, TIRAR):
            continue
        novo = valor.strip() if acao == USAR else None
        a["resposta_direta"] = _trocar(a.get("resposta_direta", ""), marcador, novo)
        a["corpo_markdown"] = _trocar(a.get("corpo_markdown", ""), marcador, novo)
        for f in a.get("faq", []):
            f["resposta"] = _trocar(f["resposta"], marcador, novo)
        feitas += 1
    return feitas


def do_formulario(form, slug: str | None = None) -> list[tuple[str, str, str]]:
    """Lê as listas paralelas pend_m / pend_acao / pend_valor / pend_orig (e pend_slug na tela geral)."""
    campos = [form.getlist(k) for k in ("pend_m", "pend_acao", "pend_valor", "pend_orig")]
    slugs = form.getlist("pend_slug") or [slug] * len(campos[0])
    if len({len(slugs), *(len(c) for c in campos)}) != 1:
        raise ValueError("Formulário de pendências incompleto.")
    return [(m, decidir(acao, valor, orig), valor)
            for s, m, acao, valor, orig in zip(slugs, *campos, strict=True) if slug is None or s == slug]
