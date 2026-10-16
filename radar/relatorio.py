"""
radar/relatorio.py — Relatório de visibilidade em IA (HTML único, abre offline).

Linguagem visual portada do diagram-design (github.com/cathrynlavery/diagram-design,
MIT, Cathryn Lavery): papel neutro, tinta grafite, UM acento por figura, títulos
que já dizem a conclusão e cartões de leitura abaixo de cada painel. Gráficos em
HTML/CSS (não SVG) para o texto reflowar no celular; cada marca tem rótulo
direto e tooltip, e os valores completos ficam no anexo.
"""

import base64
import html
import re
from datetime import datetime

from config import settings
from radar.modelos import NOMES_PROVEDOR, descrever_coleta, numero_br

MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
         "setembro", "outubro", "novembro", "dezembro"]

FONTES_WOFF2 = [
    ("Geist", "geist-latin-400-normal.woff2", 400, "normal"),
    ("Geist", "geist-latin-500-normal.woff2", 500, "normal"),
    ("Geist", "geist-latin-600-normal.woff2", 600, "normal"),
    ("Geist Mono", "geist-mono-latin-400-normal.woff2", 400, "normal"),
    ("Geist Mono", "geist-mono-latin-500-normal.woff2", 500, "normal"),
]

CSS = """
:root{
 --paper:#f5f5f5;--paper-2:#ececec;--card:#fbfbfa;--ink:#2d3142;--muted:#4f5d75;--soft:#5a6580;
 --rule:rgba(45,49,66,.12);--rule-solid:#bfc0c0;--accent:#bf4520;--accent-tint:rgba(191,69,32,.08);
 --bar:#4f5d75;--good:#3d6b4f;
 --sans:'Geist',system-ui,sans-serif;
 --mono:'Geist Mono',ui-monospace,monospace}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--paper);color:var(--ink);font:400 16px/1.65 var(--sans)}
.pagina{max-width:1120px;margin:0 auto;padding:clamp(32px,6vw,80px) clamp(16px,4vw,48px) 96px}
.eyebrow{font:500 11px/1.4 var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--soft)}
h1{font:600 clamp(30px,4.2vw,46px)/1.1 var(--sans);letter-spacing:-.03em;margin:14px 0 18px;max-width:30ch}
h2{font:600 clamp(23px,2.7vw,30px)/1.2 var(--sans);letter-spacing:-.022em;margin:10px 0 12px;max-width:38ch}
h1 em,h2 em{font-style:normal;color:var(--accent)}
.lead{font-size:clamp(17px,1.9vw,19px);color:var(--muted);max-width:64ch;margin:0}
.demo{border:1px solid var(--accent);background:var(--accent-tint);padding:12px 16px;border-radius:0;
 font:500 12px/1.5 var(--mono);letter-spacing:.04em;margin-bottom:32px}

/* abertura */
.numeros{display:grid;grid-template-columns:minmax(0,1.4fr) repeat(auto-fit,minmax(180px,1fr));
 gap:12px;margin:clamp(32px,5vw,56px) 0 0}
.tile{background:var(--card);border:1px solid var(--rule);border-radius:0;padding:20px 22px}
.tile .v{font:600 clamp(32px,4vw,44px)/1.05 var(--sans);letter-spacing:-.02em}
.tile .l{color:var(--muted);font-size:14px;line-height:1.45;margin-top:8px}
.tile.hero{border-color:var(--accent);background:var(--accent-tint)}
.tile.hero .v{font-size:clamp(64px,9vw,96px)}
@media(max-width:720px){.numeros{grid-template-columns:1fr 1fr}.tile.hero{grid-column:1/-1}}

/* painéis */
section.painel{margin-top:clamp(72px,10vw,120px)}
.figura{background:var(--paper-2);border:1px solid var(--rule);border-radius:0;
 padding:clamp(12px,2.4vw,24px);margin-top:28px}
.figura-in{background:var(--paper);border-radius:0;padding:clamp(16px,3vw,32px)}
.cartoes{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px;margin-top:12px}
.cartoes.duas{grid-template-columns:repeat(auto-fit,minmax(340px,1fr))}
.cartoes.tres{grid-template-columns:repeat(auto-fit,minmax(280px,1fr))}
@media(min-width:900px){.cartoes.tres{grid-template-columns:repeat(3,1fr)}}
.cartao{background:var(--card);border:1px solid var(--rule);border-radius:0;padding:20px 22px}
.cartao .eyebrow{margin-bottom:10px}
.cartao h3{font:600 16px/1.35 var(--sans);margin:0 0 12px;padding-bottom:12px;border-bottom:1px solid var(--rule);
 display:flex;gap:10px;align-items:baseline}
.cartao p{margin:0;color:var(--muted);font-size:15px;line-height:1.6}
.cartao.foco{border-color:var(--accent)}
.sw{width:10px;height:10px;border-radius:0;flex:none;background:var(--bar);transform:translateY(1px)}
.sw.acento{background:var(--accent)}.sw.claro{background:var(--rule-solid)}

/* barras horizontais (série única; o foco usa o acento) */
.barras{display:grid;grid-template-columns:minmax(120px,max-content) 1fr;gap:10px 16px;align-items:center}
.barras .n{font-size:14px;line-height:1.3;max-width:260px}
.barras .trilho{display:flex;align-items:center;gap:10px;min-width:0}
.barras .b{height:16px;background:var(--bar);border-radius:0 2px 2px 0;min-width:2px}
.barras .val{font:400 12px var(--mono);color:var(--muted);white-space:nowrap}
.barras .foco .n,.barras .n.foco{font-weight:600}.barras .b.acento{background:var(--accent)}
.barras .vazio{height:16px;border:1px dashed var(--accent);border-radius:0 2px 2px 0;width:4px}
.eixo{font:500 10px var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--soft);margin-bottom:14px}

/* matriz pergunta × IA */
.matriz{display:grid;gap:2px;background:var(--rule);border-radius:0;overflow:hidden}
.matriz .lin{display:grid;grid-template-columns:minmax(200px,1.6fr) repeat(var(--cols),minmax(0,1fr));gap:2px}
.matriz .c{background:var(--paper);padding:12px 14px;font-size:14px;line-height:1.4}
.matriz .cab{font:500 10px var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--soft);
 background:var(--paper-2)}
.matriz .sim{background:var(--accent-tint);box-shadow:inset 0 0 0 1px var(--accent)}
.matriz .st{font-weight:600;display:block}
.matriz .quem{color:var(--muted);font-size:13px}
@media(max-width:720px){.matriz .lin{grid-template-columns:1fr}.matriz .cab:not(:first-child){display:none}
 .matriz .c[data-ia]::before{content:attr(data-ia) " · ";font:500 10px var(--mono);letter-spacing:.12em;
 text-transform:uppercase;color:var(--soft)}}

/* fontes */
.dominios{columns:2 260px;column-gap:32px;margin:28px 0 0;padding:0;list-style:none}
.dominios li{break-inside:avoid;display:flex;justify-content:space-between;gap:12px;padding:8px 0;
 border-bottom:1px solid var(--rule);font-size:14px}
.dominios .t{font:500 10px var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--soft);
 white-space:nowrap}

.paginas{list-style:none;margin:0;padding:0;display:grid;gap:0}
.paginas li{display:flex;justify-content:space-between;gap:16px;padding:10px 0;border-bottom:1px solid var(--rule);
 font-size:14px;flex-wrap:wrap}
.paginas a{color:var(--ink);text-decoration:none;min-width:0;overflow-wrap:anywhere}
.paginas a b{font-weight:600}
.paginas a:hover{color:var(--accent)}
.paginas .t{font:500 10.5px var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--soft)}
.amostra{font:400 12.5px/1.6 var(--mono);color:var(--soft);margin:14px 0 0;max-width:90ch}

/* checagens */
.check{display:flex;gap:12px;align-items:flex-start}
.check .ic{font:600 13px var(--sans);width:22px;height:22px;border-radius:0;flex:none;display:grid;
 place-items:center;border:1px solid var(--rule-solid);color:var(--good)}
.check .ic.x{border-color:var(--accent);color:var(--accent)}
.check h3{font:600 16px/1.35 var(--sans);margin:0 0 4px}
.check .det{font:400 12px/1.5 var(--mono);color:var(--soft);word-break:break-word}
.check p{margin:10px 0 0}

/* plano */
ol.plano{list-style:none;counter-reset:p;margin:28px 0 0;padding:0;display:grid;gap:12px}
ol.plano li{counter-increment:p;display:grid;grid-template-columns:48px 1fr;gap:4px 16px;
 background:var(--card);border:1px solid var(--rule);border-radius:0;padding:20px 22px}
ol.plano li::before{content:counter(p,decimal-leading-zero);font:500 15px/1.5 var(--mono);color:var(--accent);
 grid-row:span 2}
ol.plano h3{font:600 16px/1.35 var(--sans);margin:0}
ol.plano p{margin:0;color:var(--muted);font-size:15px}

/* anexo */
.anexo details{border-top:1px solid var(--rule);padding:14px 0}
.anexo summary{cursor:pointer;font-weight:500}
.anexo .resp{white-space:pre-wrap;font-size:14px;color:var(--ink);margin:12px 0 8px;max-width:78ch}
.anexo .srcs{font:400 12px/1.7 var(--mono);color:var(--soft);word-break:break-all}
.anexo h4{font:500 11px var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--soft);margin:16px 0 4px}
.metodo{font-size:14px;color:var(--muted);max-width:72ch}
footer{margin-top:72px;padding-top:16px;border-top:1px solid var(--rule)}
@media print{body{background:#fff}.figura,.tile,.cartao,ol.plano li{break-inside:avoid}
 section.painel{margin-top:48px}}
"""


def fontes_embutidas() -> str:
    regras = []
    for familia, arquivo, peso, estilo in FONTES_WOFF2:
        caminho = settings.BASE_DIR / "assets" / "fonts" / arquivo
        if caminho.exists():
            b64 = base64.b64encode(caminho.read_bytes()).decode()
            regras.append(f"@font-face{{font-family:'{familia}';font-weight:{peso};font-style:{estilo};"
                          f"font-display:swap;src:url(data:font/woff2;base64,{b64}) format('woff2')}}")
    return "\n".join(regras)


def _e(texto) -> str:
    return html.escape(str(texto))


def _ia(prov: str) -> str:
    return NOMES_PROVEDOR.get(prov, prov)


def _lista_br(itens: list[str]) -> str:
    itens = [i for i in itens if i]
    if len(itens) <= 1:
        return "".join(itens)
    return ", ".join(itens[:-1]) + " e " + itens[-1]


def data_extenso(iso: str) -> str:
    d = datetime.fromisoformat(iso)
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def _texto_resposta(texto: str) -> str:
    t = _e(texto)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    return re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"\1", t)


# --------------------------------------------------------------------------
# Peças
# --------------------------------------------------------------------------

def _cartao(eyebrow: str, titulo: str, texto: str, cor: str = "", foco: bool = False) -> str:
    """texto já vem escapado/formatado; cor: "" (tinta), "acento", "claro"."""
    return (f'<div class="cartao{" foco" if foco else ""}"><div class="eyebrow">{_e(eyebrow)}</div>'
            f'<h3><span class="sw {cor}"></span>{_e(titulo)}</h3><p>{texto}</p></div>')


def _barras(linhas: list[dict], eixo: str) -> str:
    """linhas: {nome, valor, rotulo, foco, dica}. Série única; o foco leva o acento."""
    maior = max((faixa["valor"] for faixa in linhas), default=0) or 1
    partes = [f'<div class="eixo">{_e(eixo)}</div><div class="barras">']
    for faixa in linhas:
        if faixa["valor"] == 0:
            marca = '<span class="vazio"></span>' if faixa["foco"] else ""
        else:
            marca = (f'<span class="b{" acento" if faixa["foco"] else ""}" '
                     f'style="width:calc({100 * faixa["valor"] / maior:.1f}% - 64px)"></span>')
        partes.append(f'<div class="n{" foco" if faixa["foco"] else ""}">{_e(faixa["nome"])}</div>'
                      f'<div class="trilho" title="{_e(faixa["dica"])}">{marca}'
                      f'<span class="val">{_e(faixa["rotulo"])}</span></div>')
    partes.append("</div>")
    return "".join(partes)


def _painel(eyebrow: str, titulo: str, lead: str, figura: str, cartoes: list[str],
            grade: str = "") -> str:
    fig = f'<div class="figura"><div class="figura-in">{figura}</div></div>' if figura else ""
    cards = (f'<div class="cartoes {grade}">{"".join(c for c in cartoes if c)}</div>'
             if cartoes else "")
    return (f'<section class="painel"><div class="eyebrow">{_e(eyebrow)}</div><h2>{titulo}</h2>'
            f'<p class="lead">{lead}</p>{fig}{cards}</section>')


# --------------------------------------------------------------------------
# Seções (na ordem de leitura)
# --------------------------------------------------------------------------

def _abertura(res: dict) -> str:
    cli, m = res["cliente"], res["metricas"]
    r, ranking = m["resumo"], m["ranking"]
    nome = _e(cli["nome"])
    lideres = [e["nome"] for e in ranking if not e["e_a_marca"]][:3]
    provs = _lista_br([_ia(p) for p in res["provedores"]]).replace(" e ", " e ao ")

    if r["mencoes"] == 0:
        titulo = f"Quando pedem uma indicação às IAs, a <em>{nome}</em> não aparece."
    elif r["visibilidade"] < 30:
        titulo = f"As IAs quase não indicam a <em>{nome}</em>."
    else:
        titulo = f"As IAs já indicam a <em>{nome}</em> — e dá para ir além."

    lead = (f"Fizemos ao {_e(provs)} as perguntas que um cliente faria antes de contratar "
            f"{_e(cli['segmento'].lower())} em {_e(cli['cidade'])}. A {nome} foi citada em "
            f"<strong>{r['mencoes']} de {r['respostas_descoberta']}</strong> respostas. No lugar dela, "
            f"as IAs indicaram {r['concorrentes']} outras empresas")
    lead += f", com {_e(_lista_br(lideres))} à frente." if lideres else "."

    falhas = [c for c in res.get("auditoria", []) if not c["ok"]]
    tiles = [
        f'<div class="tile hero"><div class="v">{numero_br(r["visibilidade"])}%</div>'
        f'<div class="l">das respostas de indicação citam a {nome}</div></div>',
        f'<div class="tile"><div class="v">{r["concorrentes"]}</div>'
        f'<div class="l">concorrentes indicados no lugar</div></div>',
    ]
    if m["fontes"]:
        tiles.append(f'<div class="tile"><div class="v">{numero_br(round(r["fontes_concorrentes"]))}%</div>'
                     f'<div class="l">das fontes lidas pelas IAs são sites de concorrentes</div></div>')
    if res.get("auditoria"):
        tiles.append(f'<div class="tile"><div class="v">{len(falhas)} de {len(res["auditoria"])}</div>'
                     f'<div class="l">checagens técnicas do site falharam</div></div>')

    demo = ('<div class="demo">Dados de demonstração — respostas e empresas fictícias, só para testar '
            'o relatório. Não é uma medição real.</div>') if res["demo"] else ""
    rodadas = res.get("repeticoes", 1)
    amostra = (f'Amostra: {r["respostas_descoberta"]} respostas de indicação · {rodadas} rodada'
               f'{"s" if rodadas > 1 else ""} por pergunta · {descrever_coleta(res["provedores"])}. As respostas das IAs variam '
               'a cada consulta; os números indicam direção, não posição exata.')
    return (f'{demo}<div class="eyebrow">Radar de visibilidade em IA · {nome} · '
            f'{data_extenso(res["gerado_em"])}</div><h1>{titulo}</h1><p class="lead">{lead}</p>'
            f'<div class="numeros">{"".join(tiles)}</div><p class="amostra">{_e(amostra)}</p>')


def _painel_ranking(res: dict) -> str:
    cli, m = res["cliente"], res["metricas"]
    r, ranking = m["resumo"], m["ranking"]
    if not ranking:
        return ""
    total = r["respostas_descoberta"]
    concorrentes = [e for e in ranking if not e["e_a_marca"]]
    marca = next((e for e in ranking if e["e_a_marca"]), None)
    lider = concorrentes[0] if concorrentes else None

    linhas = [{"nome": e["nome"], "valor": e["respostas"], "foco": e["e_a_marca"],
               "rotulo": f"{e['respostas']} de {total}",
               "dica": f"{e['nome']}: indicada em {e['respostas']} de {total} respostas"}
              for e in ranking[:10]]
    if not any(faixa["foco"] for faixa in linhas):
        linhas.append({"nome": cli["nome"], "valor": marca["respostas"] if marca else 0, "foco": True,
                       "rotulo": f"{marca['respostas'] if marca else 0} de {total}",
                       "dica": f"{cli['nome']}: fora das 10 mais indicadas"})

    top5 = sum(e["participacao"] for e in concorrentes[:5])
    if marca:
        titulo = (f"A <em>{_e(cli['nome'])}</em> aparece em {r['posicao_no_ranking']}º lugar "
                  "entre as indicadas.")
    else:
        titulo = f"{_e(lider['nome'])} é a mais indicada. A <em>{_e(cli['nome'])}</em> não entra na lista."
    lead = (f"Cada barra conta em quantas das {total} respostas a empresa foi indicada "
            "(uma vez por resposta).")
    cartoes = [
        _cartao("Quem lidera", f"{lider['nome']} — {lider['respostas']} de {total}",
                f"Indicada em {numero_br(round(100 * lider['respostas'] / total))}% das respostas. "
                "É a referência que as IAs usam para a categoria.") if lider else "",
        _cartao("Concentração", f"As 5 primeiras somam {numero_br(round(top5))}%",
                f"das indicações. As outras {max(0, len(concorrentes) - 5)} empresas dividem o resto, "
                "quase sempre com uma menção cada.", "claro"),
        _cartao(cli["nome"], f"{r['mencoes']} indicação(ões)" if r["mencoes"] else "Nenhuma indicação",
                "Para ser indicada, a empresa precisa estar nas fontes que as IAs consultam — "
                "veja os próximos painéis.", "acento", foco=True),
    ]
    return _painel("Quem as IAs indicam", titulo, lead,
                   _barras(linhas, "Respostas que indicaram a empresa"), cartoes)


def _painel_matriz(res: dict) -> str:
    cli = res["cliente"]
    provs = list(res["provedores"])
    perguntas = [q for q in cli["perguntas"] if q["tipo"] == "descoberta"]
    resps = {(x["pergunta"], x["provedor"]): x for x in res["respostas"]}
    validas = [x for q in perguntas for p in provs
               if (x := resps.get((q["texto"], p))) and not x["erro"]]
    com_marca = sum(x["marca_mencionada"] for x in validas)

    linhas = ['<div class="lin"><div class="c cab">Pergunta do cliente</div>'
              + "".join(f'<div class="c cab">{_e(_ia(p))}</div>' for p in provs) + "</div>"]
    for q in perguntas:
        cels = [f'<div class="c">“{_e(q["texto"])}”</div>']
        for p in provs:
            x = resps.get((q["texto"], p))
            ia = _e(_ia(p))
            if not x or x["erro"]:
                cels.append(f'<div class="c" data-ia="{ia}"><span class="st">—</span>'
                            '<span class="quem">sem resposta</span></div>')
            elif x["marca_mencionada"]:
                pos = f"{x['posicao_marca']}ª indicação" if x["posicao_marca"] else "citada"
                cels.append(f'<div class="c sim" data-ia="{ia}"><span class="st">✓ {pos}</span>'
                            f'<span class="quem">{_e(cli["nome"])}</span></div>')
            else:
                primeira = x["empresas_recomendadas"][0] if x["empresas_recomendadas"] else ""
                quem = f"1ª indicada: {_e(primeira)}" if primeira else "nenhuma empresa indicada"
                cels.append(f'<div class="c" data-ia="{ia}"><span class="st">✕ não citou</span>'
                            f'<span class="quem">{quem}</span></div>')
        linhas.append(f'<div class="lin">{"".join(cels)}</div>')
    figura = f'<div class="matriz" style="--cols:{len(provs)}">{"".join(linhas)}</div>'

    if com_marca == 0:
        titulo = f"Nenhuma das {len(perguntas)} perguntas de compra trouxe a marca, em nenhuma IA."
    else:
        titulo = f"A marca apareceu em {com_marca} de {len(validas)} respostas."
    lead = ("Cada linha é uma pergunta real de quem procura o serviço; cada coluna, uma IA. "
            "Quando a marca não aparece, mostramos quem foi indicado primeiro no lugar dela.")
    return _painel("Pergunta por pergunta", titulo, lead, figura, [])


def _painel_fontes(res: dict) -> str:
    cli, m = res["cliente"], res["metricas"]
    fontes = m["fontes"]
    if not fontes:
        return ""
    soma = sum(f["respostas"] for f in fontes) or 1
    grupos = [("concorrente", "Sites de concorrentes"), ("terceiro", "Outros sites"),
              ("plataforma", "Plataformas e diretórios"), ("marca", f"Site da {cli['nome']}")]
    por_tipo = {t: sum(f["respostas"] for f in fontes if f["tipo"] == t) for t, _ in grupos}
    linhas = [{"nome": rotulo, "valor": por_tipo[t], "foco": t == "concorrente",
               "rotulo": f"{numero_br(round(100 * por_tipo[t] / soma))}%",
               "dica": f"{rotulo}: {por_tipo[t]} usos como fonte"} for t, rotulo in grupos]

    rotulo_tipo = {"concorrente": "concorrente", "terceiro": "outro site", "plataforma": "plataforma",
                   "marca": "site da marca"}
    paginas = m.get("paginas") or []
    if paginas:
        # Página a página, com quem aparece junto: é a lista de alvos de presença
        itens = []
        for p in paginas[:10]:
            caminho = p["url"].split(p["dominio"], 1)[-1].rstrip("/") or "/"
            junto = f' · junto de {_e(_lista_br(p["junto_de"]))}' if p["junto_de"] else ""
            itens.append(f'<li><a href="{_e(p["url"])}" target="_blank" rel="noopener">'
                         f'<b>{_e(p["dominio"])}</b>{_e(caminho[:60])}</a>'
                         f'<span class="t">{rotulo_tipo[p["tipo"]]} · {p["respostas"]}× {junto}</span></li>')
        lista = (f'<div class="eixo" style="margin-top:32px">Páginas mais consultadas</div>'
                 f'<ul class="paginas">{"".join(itens)}</ul>')
    else:
        lista = '<ul class="dominios">' + "".join(
            f'<li><span>{_e(f["dominio"])}</span><span class="t">{rotulo_tipo[f["tipo"]]} · '
            f'{numero_br(round(f["pct_respostas"]))}% das respostas</span></li>' for f in fontes[:10]) + "</ul>"
    figura = _barras(linhas, "Participação de cada tipo de site nas fontes") + lista

    pct_conc = round(100 * por_tipo["concorrente"] / soma)
    inicio = "Metade" if 45 <= pct_conc <= 55 else f"{pct_conc}%"
    titulo = f"{inicio} do que as IAs leem para responder são sites de concorrentes."
    lead = ("Para indicar alguém, as IAs pesquisam na web e se apoiam no que encontram. "
            "Quem publica páginas que respondem às perguntas do cliente vira fonte — e é indicado.")
    plataformas = [f["dominio"] for f in fontes if f["tipo"] == "plataforma"
                   and not f["dominio"].endswith("google.com")][:3]
    cartoes = [
        _cartao("Por que eles aparecem", "Concorrentes publicam conteúdo",
                "As agências mais indicadas têm páginas e artigos que respondem exatamente o que o "
                "cliente pergunta. As IAs leem e repetem.", "acento", foco=True),
        _cartao("Plataformas consultadas", _lista_br(plataformas) or "—",
                "Fóruns, enciclopédias e diretórios também pesam. Estar bem representado neles "
                "aumenta a chance de indicação.") if plataformas else "",
        _cartao(f"Site da {cli['nome']}",
                f"Usado {por_tipo['marca']} vez(es)" if por_tipo["marca"] else "Nunca usado como fonte",
                "Sem conteúdo próprio sobre serviços e nichos, o site não tem o que oferecer às IAs.",
                "claro"),
    ]
    return _painel("Onde as IAs buscam a resposta", titulo, lead, figura, cartoes)


def _painel_buscas(res: dict) -> str:
    buscas = res["metricas"].get("buscas") or []
    if not buscas:
        return ""
    itens = "".join(f'<li><span>{_e(b["busca"])}</span><span class="t">{b["vezes"]}×</span></li>'
                    for b in buscas[:16])
    titulo = "Antes de responder, as IAs fizeram estas buscas."
    lead = ("São as perguntas que o site e os perfis da empresa precisam responder. Cada uma vira "
            "pauta, página ou alvo de presença em terceiros.")
    return _painel("O que as IAs pesquisaram", titulo, lead, f'<ul class="dominios">{itens}</ul>', [])


def _painel_marca(res: dict) -> str:
    cli = res["cliente"]
    rs = [x for x in res["respostas"] if x["tipo_pergunta"] == "marca" and not x["erro"]
          and x.get("resumo_marca")]
    if not rs:
        return ""
    cartoes = []
    for x in rs:
        if x["empresa_certa"] is False:
            cartoes.append(_cartao(f"{_ia(x['provedor'])} · confundiu a empresa",
                                   f"Falou de {x['empresa_confundida'] or 'outra empresa'}",
                                   _e(x["resumo_marca"]), "acento", foco=True))
        elif x["tem_informacao"]:
            cartoes.append(_cartao(f"{_ia(x['provedor'])} · empresa certa", "Descreveu a empresa",
                                   _e(x["resumo_marca"])))
        else:
            cartoes.append(_cartao(f"{_ia(x['provedor'])} · sem informação", "Não soube responder",
                                   _e(x["resumo_marca"]), "claro"))
    nome = _e(cli["nome"])
    if any(x["empresa_certa"] is False for x in rs):
        titulo = f"Uma das IAs confundiu a <em>{nome}</em> com outra empresa."
    elif all(x["tem_informacao"] for x in rs):
        titulo = f"Perguntadas pelo nome, as IAs reconhecem a <em>{nome}</em>."
    else:
        titulo = f"Perguntadas pelo nome, as IAs sabem pouco sobre a <em>{nome}</em>."
    lead = ("Aqui a pergunta cita a empresa diretamente — é o que acontece quando alguém já ouviu "
            "falar dela e vai conferir antes de contratar.")
    return _painel("Quando perguntam pelo nome", titulo, lead, "", cartoes, grade="duas")


def _painel_tecnico(res: dict) -> str:
    checks = res.get("auditoria") or []
    if not checks:
        return ""
    falhas = [c for c in checks if not c["ok"]]
    cartoes = []
    for c in sorted(checks, key=lambda c: c["ok"]):  # falhas primeiro
        ic = '<span class="ic">✓</span>' if c["ok"] else '<span class="ic x">✕</span>'
        impacto = f'<p>{_e(c["impacto"])}</p>' if not c["ok"] else ""
        cartoes.append(f'<div class="cartao{"" if c["ok"] else " foco"}"><div class="check">{ic}<div>'
                       f'<h3>{_e(c["nome"])}</h3><div class="det">{_e(c["detalhe"])}</div>{impacto}'
                       f'</div></div></div>')
    bloqueio = any("Robôs" in c["nome"] for c in falhas)
    titulo = f"{len(falhas)} de {len(checks)} checagens falharam"
    titulo += " — inclusive o bloqueio a robôs de IA." if bloqueio else "."
    lead = ("Testamos o site como cada IA o acessa. Bloqueios e arquivos ausentes impedem que ele "
            "seja lido, entendido e citado.")
    return _painel("O site visto pelas IAs", titulo, lead, "", cartoes, grade="tres")


def _painel_plano(res: dict) -> str:
    recs = res["metricas"]["recomendacoes"]
    if not recs:
        return ""
    itens = "".join(f'<li><h3>{_e(r["titulo"])}</h3><p>{_e(r["texto"])}</p></li>' for r in recs)
    return ('<section class="painel"><div class="eyebrow">O plano</div>'
            '<h2>O que fazer, em ordem de impacto.</h2><p class="lead">Cada item ataca um dos achados '
            'acima; os primeiros são os que mais mudam o que as IAs respondem.</p>'
            f'<ol class="plano">{itens}</ol></section>')


def _anexo(res: dict) -> str:
    cli = res["cliente"]
    partes = ['<section class="painel anexo"><div class="eyebrow">Anexo</div>'
              '<h2>Todas as respostas.</h2><p class="lead">O texto completo de cada IA e as fontes '
              'que ela usou, para conferência.</p>']
    for q in cli["perguntas"]:
        partes.append(f'<details><summary>“{_e(q["texto"])}”</summary>')
        for x in [x for x in res["respostas"] if x["pergunta"] == q["texto"]]:
            partes.append(f'<h4>{_e(_ia(x["provedor"]))} · {_e(x["modelo"])}</h4>')
            if x["erro"]:
                partes.append(f'<div class="resp">Sem resposta ({_e(x["erro"][:160])})</div>')
                continue
            fontes = "<br>".join(_e(f["url"]) for f in x["fontes"][:10]) or "sem fontes"
            partes.append(f'<div class="resp">{_texto_resposta(x["texto"])}</div>'
                          f'<div class="srcs">{fontes}</div>')
        partes.append("</details>")
    modelos = "; ".join(f"{_ia(p)}: {mod}" for p, mod in res["provedores"].items())
    partes.append(f"""<h4 style="margin-top:40px">Como medimos</h4><p class="metodo">Cada pergunta foi
enviada {res['repeticoes']}× a cada IA ({descrever_coleta(res['provedores'])}), com busca na web e localização em
{_e(cli['cidade'])}/{_e(cli['regiao'])}. Respostas de IA variam entre consultas e entre usuários; os números
são uma amostra do comportamento das IAs nesta data, não uma garantia. Modelos: {_e(modelos)}.
As empresas indicadas foram identificadas automaticamente em cada resposta.</p></section>""")
    return "".join(partes)


def gerar(resultado: dict) -> str:
    cli = resultado["cliente"]
    corpo = "".join([
        _abertura(resultado), _painel_ranking(resultado), _painel_matriz(resultado),
        _painel_fontes(resultado), _painel_buscas(resultado), _painel_marca(resultado),
        _painel_tecnico(resultado),
        _painel_plano(resultado), _anexo(resultado),
    ])
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Radar de IA · {_e(cli['nome'])}</title><style>{fontes_embutidas()}{CSS}</style></head>
<body><main class="pagina">{corpo}<footer class="eyebrow">TimeLabs · Portal do Criador</footer></main></body></html>"""


def salvar(resultado: dict) -> str:
    settings.RELATORIOS_DIR.mkdir(parents=True, exist_ok=True)
    cli = resultado["cliente"]["id"]
    carimbo = datetime.fromisoformat(resultado["gerado_em"]).strftime("%Y%m%d-%H%M%S")
    sufixo = "-demo" if resultado["demo"] else ""
    caminho = settings.RELATORIOS_DIR / f"radar-{cli}-{carimbo}{sufixo}.html"
    caminho.write_text(gerar(resultado), encoding="utf-8")
    return str(caminho)
