"""
conteudo/redator.py — Escreve um artigo de blog a partir de um tema da pauta.

Formato pensado para ser citado por IAs e ranquear no Google: resposta direta
no topo, seções que espelham as perguntas do cliente, FAQ e dados
estruturados. Fatos que não estão no perfil viram marcadores [[CONFIRMAR: ...]]
e perguntas para o especialista — o humano completa antes de publicar.
"""

import json
import re
from datetime import datetime

from pydantic import BaseModel, Field

import ia

SISTEMA_REDATOR = """Você escreve artigos de blog em português do Brasil para empresas clientes da TimeLabs.

O leitor é um empresário que perguntou algo a um assistente de IA ou ao Google e quer decidir
rápido. Assistentes de IA citam páginas que respondem a pergunta de forma direta, específica e
verificável, então o artigo abre com a resposta, usa subtítulos que são as perguntas reais do
cliente e traz detalhes concretos (etapas, critérios, faixas, exemplos de nicho, contexto local).

Credibilidade é o ativo da empresa: nunca invente números, preços, cases, depoimentos, clientes,
prêmios ou anos de experiência. Use só os fatos do perfil. Afirmações que o perfil marca como
"a confirmar" entram no texto dentro de [[CONFIRMAR: ...]]. Quando um dado real deixaria o texto
muito melhor (um resultado de cliente, uma faixa de investimento, um exemplo vivido), deixe um
marcador [[DADO DO ESPECIALISTA: o que inserir]] e inclua a pergunta correspondente em
perguntas_especialista.

A empresa aparece como especialista que explica, não como anúncio: cite-a onde ela é a resposta
natural (o processo dela, os nichos que atende, a cidade) e feche com um convite curto ao contato.
Tom: {tom}"""

PROMPT_ARTIGO = """Empresa: {nome} — {segmento} em {cidade}/{regiao}. Site: {site}

Perfil (única fonte de fatos sobre a empresa):
{perfil}

Tema da pauta:
{tema}

O que as IAs respondem hoje para essa pergunta (concorrentes e fontes que usam):
{contexto}

Escreva o artigo completo. corpo_markdown começa no primeiro subtítulo (##), sem repetir o
título nem a resposta direta, e não inclui a seção de FAQ (ela vai em faq). Entre 1.000 e 1.800
palavras no corpo."""


class ItemFAQ(BaseModel):
    pergunta: str
    resposta: str


class Artigo(BaseModel):
    titulo: str
    meta_titulo: str = Field(description="até 60 caracteres, com a palavra-chave")
    meta_descricao: str = Field(description="até 155 caracteres, responde e convida ao clique")
    resposta_direta: str = Field(description="2 a 4 frases que respondem a pergunta-alvo sozinhas")
    corpo_markdown: str
    faq: list[ItemFAQ] = Field(description="4 a 6 perguntas relacionadas, respostas curtas")
    perguntas_especialista: list[str] = Field(
        description="perguntas para o especialista da empresa responder (áudio ou texto)")


def contexto_do_radar(run: dict | None, pergunta: str) -> str:
    if not run:
        return "(sem radar)"
    rs = [r for r in run["respostas"] if r["pergunta"] == pergunta and not r["erro"]]
    if not rs:  # tema não veio exatamente de uma pergunta do radar
        return "Fontes mais usadas pelas IAs no radar: " + ", ".join(
            f["dominio"] for f in run["metricas"]["fontes"][:8])
    return "\n".join(
        f"- {r['provedor']}: recomendou {', '.join(r['empresas_recomendadas']) or 'ninguém'}; "
        f"fontes: {', '.join(sorted({f['dominio'] for f in r['fontes']})[:6]) or 'nenhuma'}"
        for r in rs)


def _artigo_demo(tema: dict, cliente: dict) -> Artigo:
    p = cliente["perfil"]
    return Artigo(
        titulo=tema["titulo"],
        meta_titulo=tema["titulo"][:60],
        meta_descricao=f"[demonstração] {tema['pergunta_alvo']}"[:155],
        resposta_direta=f"[DEMONSTRAÇÃO — texto gerado sem IA] Resposta direta para "
                        f"“{tema['pergunta_alvo']}” entraria aqui, citando a {cliente['nome']}.",
        corpo_markdown="\n\n".join(
            [f"## Como funciona o trabalho da {cliente['nome']}"]
            + [f"- {etapa}" for etapa in p["processo"]]
            + ["## Para quais negócios", ", ".join(p["nichos"]) + ".",
               "## Resultados", "[[DADO DO ESPECIALISTA: um resultado real de cliente deste nicho]]"]),
        faq=[ItemFAQ(pergunta="Pergunta frequente de exemplo?", resposta="[demonstração]")],
        perguntas_especialista=["Qual resultado de um cliente deste nicho você pode citar com números?"],
    )


def escrever(tema: dict, cliente: dict, run: dict | None, demo: bool = False) -> dict:
    if demo:
        artigo = _artigo_demo(tema, cliente)
    else:
        artigo = ia.gerar(
            PROMPT_ARTIGO.format(
                nome=cliente["nome"], segmento=cliente["segmento"], cidade=cliente["cidade"],
                regiao=cliente["regiao"], site=cliente["site"],
                perfil=ia.perfil_para_prompt(cliente["perfil"]),
                tema=json.dumps(tema, ensure_ascii=False, indent=1),
                contexto=contexto_do_radar(run, tema["pergunta_alvo"]),
            ),
            Artigo, sistema=SISTEMA_REDATOR.format(tom=cliente["perfil"]["tom"]), esforco="high",
        )

    texto_todo = " ".join([artigo.resposta_direta, artigo.corpo_markdown]
                          + [f.resposta for f in artigo.faq])
    return {
        "cliente_id": cliente["id"],
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "demo": demo,
        "status": "rascunho",
        "tema": tema,
        "slug": tema["slug"],
        "pendencias": re.findall(r"\[\[([^\]]+)\]\]", texto_todo),
        "palavras": len(re.findall(r"\w+", artigo.corpo_markdown)),
        **artigo.model_dump(),
    }
