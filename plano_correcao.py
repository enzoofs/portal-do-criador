"""
plano_correcao.py — Monta o "Plano de correção" do cliente (HTML único, mesmo visual do radar).

Junta os guias escritos em entregas/<cliente>/*.md (front matter com titulo,
eyebrow e resumo) e uma seção gerada a partir da pauta de conteúdo mais
recente, com o estado de cada artigo. Arquivos que não são .md (ex.: llms.txt)
aparecem como anexos prontos para publicar.
"""

import html
import json
import os
import re
from datetime import datetime
from pathlib import Path

import markdown

from config import settings
from conteudo import pauta as pauta_mod
from radar.relatorio import CSS, data_extenso, fontes_embutidas

ENTREGAS_DIR = settings.BASE_DIR / "entregas"

CSS_DOC = """
.doc{max-width:72ch}
.doc h2{font:600 19px/1.35 var(--sans);margin:36px 0 10px;max-width:none}
.doc h3{font:600 16px/1.35 var(--sans);margin:24px 0 8px}
.doc p,.doc li{color:var(--ink);font-size:16px}
.doc ul,.doc ol{padding-left:22px}
.doc li{margin:4px 0}
.doc li.tarefa{list-style:none;position:relative;padding-left:24px;margin-left:-22px}
.doc li.tarefa::before{content:"";position:absolute;left:0;top:6px;width:14px;height:14px;
 border:1.5px solid var(--muted);border-radius:3px}
.doc table{border-collapse:collapse;width:100%;font-size:14px;margin:16px 0}
.doc th{font:500 10px var(--mono);letter-spacing:.14em;text-transform:uppercase;color:var(--soft);text-align:left}
.doc th,.doc td{border-bottom:1px solid var(--rule);padding:10px 12px 10px 0;vertical-align:top}
.doc code{font:400 13px var(--mono);background:var(--paper-2);padding:1px 5px;border-radius:4px}
.doc pre{background:var(--ink);color:#f5f5f5;padding:16px 18px;border-radius:8px;font-size:13px;
 white-space:pre-wrap;word-break:break-word}
.doc pre code{background:none;color:inherit;padding:0}
.doc blockquote{margin:16px 0;background:var(--card);border:1px solid var(--rule);border-left:3px solid var(--accent);
 border-radius:8px;padding:6px 22px}
.doc strong{font-weight:600}
.doc a{color:var(--accent)}
.anexos{display:flex;gap:12px;flex-wrap:wrap;margin-top:20px}
.anexos a{font:500 13px var(--mono);color:var(--ink);background:var(--card);border:1px solid var(--rule);
 border-radius:6px;padding:10px 14px;text-decoration:none}
.indice{list-style:none;padding:0;margin:40px 0 0;display:grid;gap:8px;
 grid-template-columns:repeat(auto-fit,minmax(240px,1fr))}
.indice a{display:block;background:var(--card);border:1px solid var(--rule);border-radius:8px;padding:16px 18px;
 text-decoration:none;color:var(--ink);height:100%}
.indice .eyebrow{display:block;margin-bottom:6px}
"""


def _e(t) -> str:
    return html.escape(str(t))


def ler_md(caminho: Path) -> tuple[dict, str]:
    texto = caminho.read_text(encoding="utf-8")
    meta = {}
    m = re.match(r"^---\n(.*?)\n---\n", texto, re.S)
    if m:
        for linha in m.group(1).splitlines():
            if ":" in linha:
                k, v = linha.split(":", 1)
                meta[k.strip()] = v.strip()
        texto = texto[m.end():]
    return meta, texto


def md_para_html(texto: str) -> str:
    corpo = markdown.markdown(texto, extensions=["tables", "fenced_code", "sane_lists"])
    # checklists "- [ ] tarefa" viram itens com caixinha
    return re.sub(r"<li>\[ \]\s*", '<li class="tarefa">', corpo)


def _secao(ancora: str, eyebrow: str, titulo: str, resumo: str, corpo_html: str) -> str:
    return (f'<section class="painel" id="{ancora}"><div class="eyebrow">{_e(eyebrow)}</div>'
            f'<h2>{_e(titulo)}</h2><p class="lead">{_e(resumo)}</p>'
            f'<div class="doc">{corpo_html}</div></section>')


def _secao_conteudo(cliente: dict, destino: Path) -> tuple[dict, str] | None:
    pasta = pauta_mod.ultima_pauta(cliente["id"], incluir_demo=False)
    if not pasta:
        return None
    pauta = json.loads((pasta / "pauta.json").read_text(encoding="utf-8"))
    artigos = {p.stem: json.loads(p.read_text(encoding="utf-8"))
               for p in pasta.glob("*.json") if p.name != "pauta.json"}
    def rel(p: Path) -> str:
        return Path(os.path.relpath(p, destino)).as_posix()

    linhas = ["<table><tr><th>Artigo</th><th>Pergunta que responde</th><th>Situação</th></tr>"]
    for t in pauta["temas"]:
        a = artigos.get(t["slug"])
        if a:
            pend = len(a["pendencias"])
            sit = (f'<a href="{rel(pasta / (t["slug"] + ".html"))}">rascunho</a> · {a["palavras"]} palavras'
                   + (f" · {pend} pendência{'s' if pend != 1 else ''}" if pend else ""))
        else:
            sit = "a escrever"
        linhas.append(f"<tr><td>{_e(t['titulo'])}</td><td>“{_e(t['pergunta_alvo'])}”</td><td>{sit}</td></tr>")
    linhas.append("</table>")
    # duas por artigo, na ordem da pauta, sem as quase repetidas (mesmo começo)
    perguntas, inicios = [], set()
    for t in pauta["temas"]:
        for q in artigos.get(t["slug"], {}).get("perguntas_especialista", [])[:2]:
            inicio = " ".join(q.lower().split()[:5])
            if inicio not in inicios:
                inicios.add(inicio)
                perguntas.append(q)
    texto = (
        f"<p>Um artigo para cada pergunta de compra em que a {_e(cliente['nome'])} não apareceu. Os textos "
        "seguem o formato que as IAs costumam citar: resposta direta no início, subtítulos que são "
        "as perguntas do cliente, perguntas frequentes e dados estruturados. Nenhum número, case ou "
        "cliente foi inventado — o que precisa de confirmação está marcado no rascunho.</p>"
        + "".join(linhas)
        + f'<p><a href="{rel(pasta / "index.html")}">Abrir a central de conteúdo →</a></p>'
        "<h2>Como publicar</h2><ol><li>Revisar cada rascunho e resolver as pendências marcadas em "
        "amarelo.</li><li>Responder às perguntas para o especialista (por áudio, se preferir): são "
        f"elas que transformam um texto bom em um texto que só a {_e(cliente['nome'])} poderia ter "
        "escrito.</li><li>A TimeLabs envia os artigos aprovados para o WordPress como rascunho e "
        "avisa o Bing assim que forem publicados (o Google encontra pelo sitemap).</li></ol>"
    )
    if perguntas:
        texto += "<h2>Perguntas para o especialista</h2><ul>" + "".join(
            f'<li class="tarefa">{_e(q)}</li>' for q in perguntas) + "</ul>"
    meta = {"titulo": "Publicar conteúdo que responde aos clientes",
            "eyebrow": f"Ação 04 · conteúdo · {len(artigos)} de {len(pauta['temas'])} artigos prontos",
            "resumo": "É assim que os concorrentes viram fonte das IAs. A pauta e os rascunhos já estão prontos para revisão."}
    return meta, texto


GUIA_LISTAS = "02-listas-de-terceiros"
ROTULO_TIPO = {"concorrente": "concorrente", "terceiro": "outro site", "plataforma": "plataforma",
               "marca": "site da marca"}


def tabela_paginas(cliente_id: str) -> str:
    """Páginas que as IAs mais consultaram no último radar real, com quem apareceu junto.
    Vai dentro do guia de listas de terceiros: é a lista de alvos de presença."""
    runs = sorted(p for p in (settings.RUNS_DIR / cliente_id).glob("*.json") if "-demo" not in p.name)
    if not runs:
        return ""
    paginas = json.loads(runs[-1].read_text(encoding="utf-8"))["metricas"].get("paginas") or []
    if not paginas:
        return ""
    linhas = ["<table><tr><th>Página</th><th>Tipo</th><th>Respostas</th><th>Apareceu junto de</th></tr>"]
    for p in paginas[:12]:
        caminho = p["url"].split(p["dominio"], 1)[-1].rstrip("/")
        rotulo = f"{p['dominio']}{caminho[:48]}{'…' if len(caminho) > 48 else ''}"
        linhas.append(f'<tr><td><a href="{_e(p["url"])}">{_e(rotulo)}</a></td>'
                      f'<td>{ROTULO_TIPO.get(p["tipo"], p["tipo"])}</td><td>{p["respostas"]}×</td>'
                      f'<td>{_e(", ".join(p["junto_de"]))}</td></tr>')
    linhas.append("</table>")
    return "<h2>Páginas que as IAs consultaram no último radar</h2>" + "".join(linhas)


NUMEROS = ["Nenhuma", "Uma", "Duas", "Três", "Quatro", "Cinco", "Seis", "Sete", "Oito", "Nove", "Dez"]


def gerar(cliente: dict) -> Path:
    pasta = ENTREGAS_DIR / cliente["id"]
    secoes = []  # (ordem, ancora, meta, corpo_html)
    for md in sorted(pasta.glob("*.md")):
        meta, texto = ler_md(md)
        corpo_html = md_para_html(texto)
        if md.stem == GUIA_LISTAS:
            corpo_html += tabela_paginas(cliente["id"])
        secoes.append((md.stem, md.stem, meta, corpo_html))
    conteudo = _secao_conteudo(cliente, pasta)
    if conteudo:
        secoes.append(("04-conteudo", "04-conteudo", conteudo[0], conteudo[1]))
    secoes.sort(key=lambda s: s[0])
    n = len(secoes)
    quantas = NUMEROS[n] if n < len(NUMEROS) else str(n)

    anexos = [p for p in sorted(pasta.iterdir()) if p.is_file() and p.suffix not in (".md", ".html")]
    indice = "".join(f'<li><a href="#{a}"><span class="eyebrow">{_e(m.get("eyebrow", ""))}</span>'
                     f'{_e(m.get("titulo", a))}</a></li>' for _, a, m, _ in secoes)
    corpo = "".join(_secao(a, m.get("eyebrow", ""), m.get("titulo", a), m.get("resumo", ""), h)
                    for _, a, m, h in secoes)
    links_anexos = "".join(f'<a href="{_e(p.name)}">{_e(p.name)}{" (opcional)" if p.name == "llms.txt" else ""} ↓</a>'
                           for p in anexos)

    agora = datetime.now().isoformat(timespec="seconds")
    pagina = f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Plano de correção · {_e(cliente['nome'])}</title>
<style>{fontes_embutidas()}{CSS}{CSS_DOC}</style></head><body><main class="pagina">
<div class="eyebrow">Plano de correção · {_e(cliente['nome'])} · {data_extenso(agora)}</div>
<h1>{quantas} ações para as IAs encontrarem e indicarem a <em>{_e(cliente['nome'])}</em>.</h1>
<p class="lead">Cada ação responde a um achado do radar de visibilidade, em ordem de impacto: primeiro
o que mais muda as respostas das IAs, depois os ajustes de apoio. Tudo o que pôde ser adiantado já
está pronto: textos, código e arquivos.</p>
{f'<div class="anexos">{links_anexos}</div>' if links_anexos else ''}
<ol class="indice">{indice}</ol>{corpo}
<footer class="eyebrow">TimeLabs · Portal do Criador</footer></main></body></html>"""
    destino = pasta / "plano-de-correcao.html"
    destino.write_text(pagina, encoding="utf-8")
    return destino
