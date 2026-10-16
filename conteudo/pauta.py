"""
conteudo/pauta.py — Monta a pauta de artigos a partir do radar.

A lógica de prioridade: perguntas em que a marca NÃO aparece e concorrentes
aparecem viram artigos primeiro. Cada artigo mira uma pergunta real que o
cliente final faz para a IA.
"""

import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

import ia
from config import settings
from radar import cruzamento, rastreador

PROMPT_PAUTA = """Você é estrategista de conteúdo da TimeLabs. Monte uma pauta de {n} artigos de blog
para o site de {nome} ({segmento}, {cidade}/{regiao}). O objetivo de cada artigo é fazer a empresa
ser citada e recomendada por assistentes de IA (ChatGPT, Gemini, Claude) e aparecer no Google
quando um potencial cliente fizer a pergunta-alvo.

Perfil da empresa (fonte: site dela):
{perfil}

Resultado do radar de visibilidade (o que as IAs responderam hoje):
{radar}
{midia}
Critérios:
- Priorize perguntas em que a marca não apareceu e concorrentes apareceram.
- Perguntas sem nenhuma página no site vêm primeiro. Quando já existe uma página sobre o assunto,
  o artigo complementa essa página (e diz no ângulo qual é), em vez de repetir o que ela já cobre.
- Um artigo por intenção; nada de dois artigos disputando a mesma pergunta.
- Prefira recortes que a empresa pode responder com autoridade: os nichos e o processo dela.
- Inclua variações locais e de nicho que um cliente realmente digitaria ou perguntaria.
- O título responde à pergunta; nada de clickbait.
- Se houver termos do Google Ads, dê prioridade aos mais caros e aos que convertem: um artigo que
  responde a esse termo tira dinheiro da conta de mídia paga e já tem demanda comprovada."""


class Tema(BaseModel):
    titulo: str
    pergunta_alvo: str = Field(description="pergunta principal que o cliente final faz à IA")
    perguntas_relacionadas: list[str]
    palavra_chave: str
    nicho: str = Field(description="nicho atendido, ou 'geral'")
    angulo: str = Field(description="por que este artigo faria a IA citar a empresa")
    prioridade: int = Field(description="1 = mais urgente, 3 = menos")


class Pauta(BaseModel):
    temas: list[Tema]


def slugify(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    if len(slug) > 70:  # corta entre palavras, nunca no meio de uma
        slug = slug[:71].rsplit("-", 1)[0]
    return slug


def ultimo_radar(cliente_id: str, incluir_demo: bool) -> Path | None:
    pasta = settings.RUNS_DIR / cliente_id
    runs = sorted(p for p in pasta.glob("*.json") if incluir_demo or "-demo" not in p.name)
    return runs[-1] if runs else None


def resumir_radar(run: dict, rastreio: dict | None = None) -> str:
    """Texto curto por pergunta: quem foi citado, se a marca apareceu, fontes. Com o rastreamento
    do site: a página que já trata de cada pergunta, ou que não há nenhuma."""
    paginas = {q["pergunta"]: q for q in cruzamento.perguntas(run, rastreio)} if rastreio else {}
    linhas = []
    for q in run["cliente"]["perguntas"]:
        if q["tipo"] != "descoberta":
            continue
        rs = [r for r in run["respostas"] if r["pergunta"] == q["texto"] and not r["erro"]]
        com_marca = sum(r["marca_mencionada"] for r in rs)
        concorrentes = sorted({n for r in rs for n in r["empresas_recomendadas"]})[:8]
        site = ""
        if q["texto"] in paginas:
            p = paginas[q["texto"]]
            site = (f"; no site: {p['pagina']['url']} (“{p['pagina']['titulo']}”"
                    + (f"; problemas: {', '.join(p['motivos'])}" if p["motivos"] else "") + ")"
                    if p["pagina"] else "; no site: NENHUMA página trata disso")
        linhas.append(f"- \"{q['texto']}\": marca em {com_marca}/{len(rs)} respostas; "
                      f"recomendados: {', '.join(concorrentes) or 'nenhum'}{site}")
    fontes = ", ".join(f["dominio"] for f in run["metricas"]["fontes"][:8])
    linhas.append(f"Fontes mais usadas pelas IAs: {fontes or 'nenhuma'}")
    return "\n".join(linhas)


def _bloco_midia(cliente_id: str) -> str:
    from midia import termos
    linhas = termos.para_pauta(termos.carregar(cliente_id))
    if not linhas:
        return ""
    return ("\nTermos que a agência já paga no Google Ads (custo no período, cliques, conversões):\n"
            + linhas + "\n")


def _pauta_demo(cliente: dict) -> Pauta:
    """Sem chave de IA: um tema por pergunta de descoberta, sem refinamento."""
    temas = [Tema(titulo=q["texto"].rstrip("?") + ": guia completo", pergunta_alvo=q["texto"],
                  perguntas_relacionadas=[], palavra_chave=q["texto"].lower().rstrip("?"),
                  nicho="geral", angulo="[demonstração] tema derivado direto da pergunta do radar",
                  prioridade=1 + i // 3)
             for i, q in enumerate(q for q in cliente["perguntas"] if q["tipo"] == "descoberta")]
    return Pauta(temas=temas[:settings.ARTIGOS_POR_PAUTA])


def gerar_pauta(cliente: dict, run: dict | None, demo: bool = False) -> dict:
    if demo:
        pauta = _pauta_demo(cliente)
    else:
        pauta = ia.gerar(PROMPT_PAUTA.format(
            n=settings.ARTIGOS_POR_PAUTA, nome=cliente["nome"], segmento=cliente["segmento"],
            cidade=cliente["cidade"], regiao=cliente["regiao"],
            perfil=ia.perfil_para_prompt(cliente["perfil"]),
            radar=resumir_radar(run, rastreador.ultimo(cliente["id"])) if run else "(radar ainda não rodado)",
            midia=_bloco_midia(cliente["id"]),
        ), Pauta, esforco="high")

    temas = sorted(pauta.temas, key=lambda t: t.prioridade)
    resultado = {
        "cliente_id": cliente["id"],
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "demo": demo,
        "radar_usado": run.get("_arquivo") if run else None,
        "temas": [{**t.model_dump(), "slug": slugify(t.titulo)} for t in temas],
    }
    # Uma pasta por pauta: pauta.json + um .json/.html por artigo + index.html
    carimbo = datetime.now().strftime("%Y%m%d-%H%M%S") + ("-demo" if demo else "")
    pasta = settings.CONTEUDO_DIR / cliente["id"] / carimbo
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "pauta.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=2),
                                      encoding="utf-8")
    resultado["_pasta"] = str(pasta)
    return resultado


def ultima_pauta(cliente_id: str, incluir_demo: bool) -> Path | None:
    pastas = sorted(p for p in (settings.CONTEUDO_DIR / cliente_id).glob("*/pauta.json")
                    if incluir_demo or "-demo" not in p.parent.name)
    return pastas[-1].parent if pastas else None
