"""
conteudo/render.py — HTML do artigo (o que vai para o WordPress) e páginas de revisão.

- conteudo_post(): fragmento HTML do post com FAQ, CTA e dados estruturados
  (JSON-LD Article + FAQPage), que ajudam Google e IAs a entender a página.
- pagina_previa(): o artigo como o leitor verá, com metadados, pendências e
  perguntas para o especialista em destaque.
- pagina_central(): lista de artigos da pauta para aprovação.
"""

import html
import json
import re
from urllib.parse import quote

import markdown

from radar.relatorio import CSS as CSS_RELATORIO
from radar.relatorio import fontes_embutidas

MARCADOR = re.compile(r"\[\[([^\]]+)\]\]")


def _e(t) -> str:
    return html.escape(str(t))


_ATRIBUTO_URL = re.compile(r'\b(href|src)="([^"]*)"', re.I)
_ESQUEMA = re.compile(r"^([a-z][a-z0-9+.-]*):")
ESQUEMAS_PERMITIDOS = {"http", "https", "mailto", "tel"}


def _url_segura(m: re.Match) -> str:
    # O navegador decodifica o atributo e ignora espaços, tabs, quebras de linha e caracteres de
    # controle dentro da URL ("java\nscript:" vira "javascript:"); a checagem faz o mesmo.
    url = re.sub(r"[\x00-\x20\x7f]", "", html.unescape(m.group(2))).lower()
    esquema = _ESQUEMA.match(url)
    return f'{m.group(1)}="#"' if esquema and esquema.group(1) not in ESQUEMAS_PERMITIDOS else m.group(0)


def markdown_seguro(texto: str, extensoes: tuple[str, ...] = ("tables", "sane_lists")) -> str:
    """Markdown para HTML sem deixar passar HTML cru nem links javascript:/data:.

    O texto vem de IA (que pode ter lido uma página com injeção de prompt) ou de quem edita
    o artigo; nos dois casos não pode virar script no Portal nem no site do cliente.
    Escapa só & e < (o > continua funcionando para citação em Markdown)."""
    seguro = (texto or "").replace("&", "&amp;").replace("<", "&lt;")
    return _ATRIBUTO_URL.sub(_url_segura, markdown.markdown(seguro, extensions=list(extensoes)))


def _md(texto: str) -> str:
    return markdown_seguro(texto)


def _autor(cliente: dict) -> dict | None:
    """Autor real configurado em Configurar → Conteúdo (perfil.autor), ou None."""
    autor = (cliente.get("perfil") or {}).get("autor") or {}
    return autor if autor.get("nome") else None


def _json_ld(artigo: dict, cliente: dict) -> str:
    empresa = {"@type": "Organization", "name": cliente["nome"], "url": cliente["site"]}
    autor = _autor(cliente)
    data = artigo["gerado_em"][:10]
    post = {
        "@context": "https://schema.org", "@type": "BlogPosting",
        "headline": artigo["titulo"], "description": artigo["meta_descricao"],
        "inLanguage": "pt-BR", "datePublished": data, "dateModified": artigo.get("modificado_em", data)[:10],
        "author": ({"@type": "Person", "name": autor["nome"], "jobTitle": autor.get("cargo") or None,
                    "worksFor": empresa} if autor else empresa),
        "publisher": empresa,
        "mainEntityOfPage": artigo.get("url") or f'{cliente["site"].rstrip("/")}/{artigo["slug"]}/',
        "about": artigo["tema"]["palavra_chave"],
        "wordCount": artigo.get("palavras"),
    }
    dados = [
        {k: v for k, v in post.items() if v is not None},
        {
            "@context": "https://schema.org", "@type": "FAQPage",
            "mainEntity": [{"@type": "Question", "name": f["pergunta"],
                            "acceptedAnswer": {"@type": "Answer", "text": f["resposta"]}}
                           for f in artigo["faq"]],
        },
    ]
    # "</" dentro de JSON quebraria a tag <script>
    return json.dumps(dados, ensure_ascii=False).replace("</", "<\\/")


def link_whatsapp(numero: str, titulo: str) -> str:
    """Link do WhatsApp com a mensagem já escrita dizendo de qual artigo o lead veio.
    Quem atende vê a origem na hora; o GA4 conta o clique como saída para wa.me."""
    return link_whatsapp_texto(numero, f"Olá! Vim pelo artigo “{titulo}” no site.")


def link_whatsapp_texto(numero: str, texto: str) -> str:
    return f"https://wa.me/{numero}?text={quote(texto)}"


def _assinatura(cliente: dict) -> str:
    autor = _autor(cliente)
    if not autor:
        return ""
    cargo = f", {_e(autor['cargo'])} da {_e(cliente['nome'])}" if autor.get("cargo") else f", da {_e(cliente['nome'])}"
    bio = f" {_e(autor['bio'])}" if autor.get("bio") else ""
    return f'<p class="autor"><strong>Por {_e(autor["nome"])}</strong>{cargo}.{bio}</p>\n'


def conteudo_post(artigo: dict, cliente: dict) -> str:
    cta = cliente["perfil"]["cta"]
    faq = "".join(f"<h3>{_e(f['pergunta'])}</h3>\n<p>{_e(f['resposta'])}</p>\n" for f in artigo["faq"])
    return (
        f'<p class="resposta-direta"><strong>Resposta rápida:</strong> {_e(artigo["resposta_direta"])}</p>\n'
        f"{_md(artigo['corpo_markdown'])}\n"
        f"<h2>Perguntas frequentes</h2>\n{faq}"
        f"{_assinatura(cliente)}"
        f'<p class="cta"><a href="{_e(link_whatsapp(cta["whatsapp"], artigo["titulo"]))}" '
        f'data-lead="whatsapp" data-artigo="{_e(artigo["slug"])}">{_e(cta["texto"])}</a></p>\n'
        f'<script type="application/ld+json">{_json_ld(artigo, cliente)}</script>\n'
    )


def destacar_marcadores(fragmento: str) -> str:
    return MARCADOR.sub(lambda m: f'<mark>[[{m.group(1)}]]</mark>', fragmento)


CSS_PREVIA = """
*{box-sizing:border-box}
body{margin:0;background:#f5f5f5;color:#222;font:17px/1.7 -apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif}
.barra{background:#2d3142;color:#ecedf1;font:13px/1.5 ui-monospace,Consolas,Menlo,monospace;padding:12px 24px;
position:sticky;top:0;z-index:2}.barra b{color:#f08a65}
.barra a{color:#ecedf1}
.meta{max-width:760px;margin:24px auto;background:#fff;border:1px solid #ddd;padding:16px 20px;
font:14px/1.6 system-ui,sans-serif}
.meta h4{margin:12px 0 4px;font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:#777}
.meta .serp-t{color:#1a0dab;font-size:19px}.meta .serp-u{color:#006621;font-size:13px}
.meta ol{margin:4px 0;padding-left:20px}
.alerta{color:#bf4520}.ok{color:#3d6b4f}
article{max-width:760px;margin:0 auto 96px;background:#fff;padding:48px 56px;border:1px solid #ddd}
article h1{font-size:34px;line-height:1.2;margin:0 0 24px;letter-spacing:-.01em}
article h2{font-size:26px;margin:40px 0 12px}article h3{font-size:20px;margin:28px 0 8px}
.resposta-direta{background:rgba(191,69,32,.06);border-left:4px solid #bf4520;padding:14px 18px}
.cta a{display:inline-block;background:#25D366;color:#fff;padding:12px 20px;text-decoration:none;
font:600 16px system-ui,sans-serif}
table{border-collapse:collapse;width:100%}td,th{border:1px solid #ddd;padding:6px 10px;text-align:left}
mark{background:#ffe08a;padding:0 3px}
@media(max-width:700px){article{padding:24px 18px}article h1{font-size:28px}}
"""


def pagina_previa(artigo: dict, cliente: dict) -> str:
    pend = artigo["pendencias"]
    mt, md_ = artigo["meta_titulo"], artigo["meta_descricao"]
    url = cliente["site"].rstrip("/") + "/" + artigo["slug"] + "/"
    aviso_demo = " · <b>DEMONSTRAÇÃO (sem IA)</b>" if artigo["demo"] else ""
    perguntas = "".join(f"<li>{_e(p)}</li>" for p in artigo["perguntas_especialista"])
    lista_pend = "".join(f"<li>{_e(p)}</li>" for p in pend)
    corpo = destacar_marcadores(conteudo_post(artigo, cliente))
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{_e(artigo['titulo'])}</title>
<style>{CSS_PREVIA}</style></head><body>
<div class="barra"><a href="index.html">← Central</a> · Rascunho para aprovação · {_e(cliente['nome'])} ·
{artigo['palavras']} palavras · <b>{len(pend)} pendência(s)</b>{aviso_demo}</div>
<section class="meta">
<h4>Como aparece no Google</h4>
<div class="serp-t">{_e(mt)}</div><div class="serp-u">{_e(url)}</div><div>{_e(md_)}</div>
<div class="{'alerta' if len(mt) > 60 else 'ok'}">título: {len(mt)}/60 caracteres</div>
<div class="{'alerta' if len(md_) > 155 else 'ok'}">descrição: {len(md_)}/155 caracteres</div>
<h4>Pergunta-alvo</h4>“{_e(artigo['tema']['pergunta_alvo'])}” · palavra-chave: {_e(artigo['tema']['palavra_chave'])}
<h4>Pendências antes de publicar</h4><ol>{lista_pend or '<li class="ok">nenhuma</li>'}</ol>
<h4>Perguntas para o especialista (responder por áudio ou texto)</h4><ol>{perguntas}</ol>
</section>
<article><h1>{_e(artigo['titulo'])}</h1>{corpo}</article></body></html>"""


def pagina_central(cliente: dict, pauta: dict, artigos: list[dict]) -> str:
    """Mesma linguagem visual do relatório do radar: um cartão por artigo da pauta."""
    por_slug = {a["slug"]: a for a in artigos}
    itens = []
    for t in pauta["temas"]:
        a = por_slug.get(t["slug"])
        if a:
            pend = len(a["pendencias"])
            status = (f'<a class="abrir" href="{_e(t["slug"])}.html">Abrir rascunho →</a>'
                      f'<span class="meta">{a["palavras"]} palavras · {pend} pendência{"s" if pend != 1 else ""}'
                      f'{" · " + _e(a["status"]) if a.get("status") and a["status"] != "rascunho" else ""}</span>')
        else:
            status = '<span class="meta">ainda não escrito</span>'
        itens.append(f"""<li class="{'feito' if a else ''}"><div class="eyebrow">Prioridade {t['prioridade']} ·
{_e(t['nicho'])}</div><h3>{_e(t['titulo'])}</h3><p>“{_e(t['pergunta_alvo'])}”</p>
<p class="angulo"><b>Por que este artigo:</b> {_e(t['angulo'])}</p><div class="rodape">{status}</div></li>""")
    escritos = sum(1 for t in pauta["temas"] if t["slug"] in por_slug)
    aviso = ('<div class="demo">Pauta e artigos de demonstração — gerados sem IA, só para testar o '
             'fluxo.</div>') if pauta["demo"] else ""
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Central de conteúdo · {_e(cliente['nome'])}</title>
<style>{fontes_embutidas()}{CSS_RELATORIO}
ol.pauta{{list-style:none;margin:40px 0 0;padding:0;display:grid;gap:12px;
 grid-template-columns:repeat(auto-fit,minmax(320px,1fr))}}
ol.pauta li{{background:var(--card);border:1px solid var(--rule);padding:22px 24px;
 display:flex;flex-direction:column;gap:8px}}
ol.pauta li.feito{{border-color:var(--ink)}}
ol.pauta h3{{font:600 17px/1.35 var(--sans);margin:4px 0 0}}
ol.pauta p{{margin:0;color:var(--muted);font-size:15px}}
ol.pauta .angulo{{font-size:14px;line-height:1.55}}
ol.pauta .angulo b{{font-weight:500;color:var(--ink)}}
ol.pauta .rodape{{margin-top:auto;padding-top:14px;border-top:1px solid var(--rule);display:flex;
 justify-content:space-between;gap:12px;flex-wrap:wrap;align-items:baseline}}
.abrir{{color:var(--accent);font-weight:600;text-decoration:none}}
.meta{{font:400 12px var(--mono);color:var(--soft)}}</style></head>
<body><main class="pagina">{aviso}
<div class="eyebrow">Central de conteúdo · {_e(cliente['nome'])}</div>
<h1>{escritos} de {len(pauta['temas'])} artigos da pauta prontos para revisão.</h1>
<p class="lead">Cada artigo responde a uma pergunta que clientes fazem às IAs e ao Google. Nada é publicado
sem aprovação: abra o rascunho, resolva as pendências marcadas em amarelo e responda às perguntas para o
especialista.</p><ol class="pauta">{''.join(itens)}</ol>
<footer class="eyebrow">TimeLabs · Portal do Criador</footer></main></body></html>"""
