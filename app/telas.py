"""
app/telas.py — Os dados de cada tela do app, prontos para os templates.

As contas do radar seguem as do relatório (radar/relatorio.py), para o app, o
modo apresentação e o relatório enviado ao cliente dizerem sempre o mesmo.
"""


from flask import g, url_for
from markupsafe import Markup

from app import dados, leituras
from conteudo import render
from radar.modelos import NOMES_PROVEDOR, descrever_coleta, numero_br

ROTULO_TIPO = {"concorrente": "concorrente", "terceiro": "outro site", "plataforma": "plataforma",
               "marca": "site da marca"}

# Etapas do conteúdo: status, rótulo curto, o que acontece ali, o que dizer quando está vazia
ETAPAS = [("a escrever", "A escrever", "temas da pauta", "Todos os temas da pauta já foram escritos."),
          ("rascunho", "Rascunho", "em revisão", "Nenhum rascunho esperando revisão."),
          ("aprovado", "Aprovado", "prontos para enviar",
           "Nenhum artigo aprovado ainda. Um rascunho sem pendências pode ser aprovado no editor."),
          ("rascunho no WordPress", "No site", "rascunho no site",
           "Nada enviado ao site ainda. Os aprovados vão para lá como rascunho."),
          ("publicado", "Publicado", "Bing avisado na hora",
           "Nenhum artigo publicado ainda. Ao publicar, o portal avisa o Bing na hora (IndexNow); "
           "o Google encontra pelo sitemap.")]


def ia(prov: str) -> str:
    return NOMES_PROVEDOR.get(prov, prov)


def texto_ia(texto: str) -> Markup:
    """Resposta de uma IA em HTML: o Markdown dela vira títulos, listas e negrito; HTML cru é escapado."""
    return Markup(render.markdown_seguro(texto, ("sane_lists",)))  # noqa: S704  # nosec B704


def _plural(n: int, um: str, varios: str) -> str:
    return f"{n} {um if n == 1 else varios}"


# --------------------------------------------------------------------------
# Carteira e barra lateral
# --------------------------------------------------------------------------

def resumo_cliente(c: dict) -> dict:
    run = dados.ultimo_radar(c["id"])
    col = dados.quadro(c["id"])["colunas"]
    plano = dados.plano(c["id"], run)
    itens = [i for s in dados.STATUS_ARTIGO for i in col.get(s, [])]
    m = run["metricas"] if run else None
    return {
        "c": c, "run": run, "resumo": m["resumo"] if m else None,
        "lider": next((e for e in m["ranking"] if not e["e_a_marca"]), None) if m else None,
        "temas": len(itens), "escritos": len(itens) - len(col["a escrever"]),
        "publicados": len(col["publicado"]),
        "pendencias": sum(len(i["artigo"]["pendencias"]) for i in itens if i["artigo"]),
        "acoes": len(plano), "acoes_feitas": sum(a["status"] == "feito" for a in plano),
    }


def lateral() -> dict:
    """A carteira na barra lateral. Calculada uma vez por requisição."""
    if "lateral" not in g:
        clientes = [resumo_cliente(c) for c in dados.clientes()]
        g.lateral = {"clientes": clientes, "por_id": {k["c"]["id"]: k for k in clientes}}
    return g.lateral


def carteira() -> dict:
    ks = lateral()["clientes"]
    com_radar = [k for k in ks if k["resumo"]]
    media = (sum(k["resumo"]["visibilidade"] for k in com_radar) / len(com_radar)) if com_radar else None
    return {"clientes": ks, "media": media,
            "escritos": sum(k["escritos"] for k in ks), "temas": sum(k["temas"] for k in ks),
            "publicados": sum(k["publicados"] for k in ks),
            "pendencias": sum(k["pendencias"] for k in ks),
            "acoes": sum(k["acoes"] for k in ks), "acoes_feitas": sum(k["acoes_feitas"] for k in ks)}


# --------------------------------------------------------------------------
# Radar
# --------------------------------------------------------------------------

def veredito(run: dict) -> Markup:
    # Markup(...).format escapa o nome do cliente; só o <em> do modelo passa como HTML
    r, nome = run["metricas"]["resumo"], run["cliente"]["nome"]
    if r["mencoes"] == 0:
        return Markup("Quando pedem uma indicação às IAs, a <em>{}</em> não aparece.").format(nome)
    if r["visibilidade"] < 30:
        return Markup("As IAs quase não indicam a <em>{}</em>.").format(nome)
    return Markup("As IAs já indicam a <em>{}</em> — e dá para ir além.").format(nome)


def radar(run: dict) -> dict:
    cli, m = run["cliente"], run["metricas"]
    r, ranking = m["resumo"], m["ranking"]
    nome, total = cli["nome"], r["respostas_descoberta"]
    provs = list(run["provedores"])
    checks = sorted(run.get("auditoria") or [], key=lambda c: c["ok"])  # falhas primeiro
    falhas = [c for c in checks if not c["ok"]]

    # números de cima: o herói é a visibilidade, os outros explicam por quê
    kpis = [{"k": "Concorrentes", "v": str(r["concorrentes"]), "l": "empresas indicadas no lugar"}]
    if m["fontes"]:
        kpis.append({"k": "Fontes", "v": f'{numero_br(round(r["fontes_concorrentes"]))}%',
                     "l": "do que as IAs leem são sites de concorrentes",
                     "alerta": r["fontes_concorrentes"] >= 20})
    if r.get("perguntas_marca"):
        conf = r.get("confusoes") or []
        if conf:
            kpis.append({"k": "Marca", "v": str(len(conf)), "alerta": True,
                         "l": f"{'IA confundiu' if len(conf) == 1 else 'IAs confundiram'} a marca com outra empresa"})
        else:
            kpis.append({"k": "Marca", "v": f'{r["marca_conhecida"]} de {r["perguntas_marca"]}',
                         "l": "respostas sobre a marca a reconhecem"})
    if checks:
        kpis.append({"k": "Site", "v": f"{len(falhas)} de {len(checks)}", "alerta": bool(falhas),
                     "l": "checagens técnicas falharam"})

    # ranking: as 10 mais indicadas + a marca, mesmo zerada
    maior = max((e["respostas"] for e in ranking), default=0) or 1
    barras = [{"nome": e["nome"], "n": e["respostas"], "pct": 100 * e["respostas"] / maior,
               "marca": e["e_a_marca"]} for e in ranking[:10]]
    if not any(b["marca"] for b in barras):
        marca = next((e for e in ranking if e["e_a_marca"]), None)
        n = marca["respostas"] if marca else 0
        barras.append({"nome": nome, "n": n, "pct": 100 * n / maior, "marca": True})

    concorrentes = [e for e in ranking if not e["e_a_marca"]]
    lider = concorrentes[0] if concorrentes else None
    destaque = {
        "lider": lider, "lider_pct": round(100 * lider["respostas"] / total) if lider and total else 0,
        "top5": round(sum(e["participacao"] for e in concorrentes[:5])),
        "resto": max(0, len(concorrentes) - 5),
    }

    # fontes: composição por tipo de site + páginas mais lidas
    fontes = m["fontes"]
    soma = sum(f["respostas"] for f in fontes) or 1
    composicao = []
    for tipo, rotulo in [("concorrente", "Sites de concorrentes"), ("terceiro", "Outros sites"),
                         ("plataforma", "Plataformas e diretórios"), ("marca", f"Site da {nome}")]:
        n = sum(f["respostas"] for f in fontes if f["tipo"] == tipo)
        composicao.append({"tipo": tipo, "rotulo": rotulo, "n": n, "pct": round(100 * n / soma)})
    paginas = []
    for p in (m.get("paginas") or [])[:8]:
        caminho = p["url"].split(p["dominio"], 1)[-1].rstrip("/") or "/"
        paginas.append({**p, "caminho": caminho, "rotulo": ROTULO_TIPO.get(p["tipo"], p["tipo"])})

    # matriz pergunta × IA (cada célula abre a resposta completa)
    idx = {(x["pergunta"], x["provedor"]): i for i, x in enumerate(run["respostas"])}
    matriz = []
    for q in (q for q in cli["perguntas"] if q["tipo"] == "descoberta"):
        cels = []
        for p in provs:
            i = idx.get((q["texto"], p))
            x = run["respostas"][i] if i is not None else None
            if not x or x["erro"]:
                cels.append({"i": i, "ia": ia(p), "estado": "erro", "st": "sem resposta", "sub": ""})
            elif x["marca_mencionada"]:
                pos = f'{x["posicao_marca"]}ª indicação' if x["posicao_marca"] else "citada"
                cels.append({"i": i, "ia": ia(p), "estado": "sim", "st": pos, "sub": nome})
            else:
                rec = x["empresas_recomendadas"]
                cels.append({"i": i, "ia": ia(p), "estado": "nao", "st": "não citou",
                             "sub": f"1ª indicada: {rec[0]}" if rec else "nenhuma empresa indicada"})
        matriz.append({"pergunta": q["texto"], "cels": cels})

    # perguntas pelo nome
    marca = []
    for i, x in enumerate(run["respostas"]):
        if x["tipo_pergunta"] != "marca" or x["erro"] or not x.get("resumo_marca"):
            continue
        if x["empresa_certa"] is False:
            estado, titulo = "confundiu", f"Falou de {x['empresa_confundida'] or 'outra empresa'}"
        elif x["tem_informacao"]:
            estado, titulo = "certa", "Descreveu a empresa certa"
        else:
            estado, titulo = "sem", "Não soube responder"
        marca.append({"i": i, "ia": ia(x["provedor"]), "pergunta": x["pergunta"], "estado": estado,
                      "titulo": titulo, "resumo": x["resumo_marca"]})

    respostas = [{"i": i, "ia": ia(x["provedor"]), "modelo": x["modelo"], "pergunta": x["pergunta"],
                  "tipo": x["tipo_pergunta"], "erro": x["erro"],
                  "texto": texto_ia(x["texto"]) if x["texto"] else "",
                  "fontes": x["fontes"], "buscas": x.get("buscas") or [],
                  "empresas": x["empresas_recomendadas"], "marca": x["marca_mencionada"],
                  "posicao": x["posicao_marca"]}
                 for i, x in enumerate(run["respostas"])]

    rodadas = run.get("repeticoes", 1)
    confianca = confiabilidade(run)
    for ch in checks:
        ch["resolver"] = leituras.resolver_check(ch, cli["id"])
    v = {
        "confianca": confianca,
        "veredito": veredito(run), "visibilidade": numero_br(r["visibilidade"]),
        "mencoes": r["mencoes"], "total": total, "kpis": kpis,
        "ias": [ia(p) for p in provs], "concorrentes": r["concorrentes"],
        "n_perguntas": len(matriz), "n_marca": sum(q["tipo"] == "marca" for q in cli["perguntas"]),
        "barras": barras, "destaque": destaque, "composicao": composicao, "n_fontes": len(fontes), "paginas": paginas,
        "matriz": matriz, "marca": marca, "checks": checks, "falhas": len(falhas),
        "buscas": (m.get("buscas") or [])[:16], "respostas": respostas,
        "amostra": (f"{total} respostas de indicação · {_plural(rodadas, 'rodada', 'rodadas')} por pergunta "
                    f"· {descrever_coleta(run['provedores'])}. As respostas variam a cada consulta: os números indicam direção, "
                    "não posição exata."),
        "plano": m["recomendacoes"],
    }
    v["leituras"] = leituras.montar(run, v)
    return v


def _wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Intervalo de confiança de 95% para uma proporção (bom para amostras pequenas e para zero)."""
    if not n:
        return 0.0, 0.0
    p, d = k / n, 1 + z * z / n
    centro, margem = p + z * z / (2 * n), z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return max(0.0, (centro - margem) / d), min(1.0, (centro + margem) / d)


def confiabilidade(run: dict) -> dict:
    """O quanto confiar nos números: margem de erro, quem cada IA indica e se as rodadas concordam."""
    from radar.extrator import normalizar
    ok = [x for x in run["respostas"] if x["tipo_pergunta"] == "descoberta" and not x["erro"]]
    k = sum(x["marca_mencionada"] for x in ok)
    baixo, alto = _wilson(k, len(ok))
    por_ia, conjuntos = [], {}
    for prov in run["provedores"]:
        rs = [x for x in ok if x["provedor"] == prov]
        cont, nomes = {}, {}
        for x in rs:
            for e in {normalizar(n): n for n in x["empresas_recomendadas"]}.items():
                cont[e[0]] = cont.get(e[0], 0) + 1
                nomes.setdefault(e[0], e[1])
        conjuntos[prov] = set(cont)
        kk = sum(x["marca_mencionada"] for x in rs)
        por_ia.append({"ia": ia(prov), "respostas": len(rs), "mencoes": kk,
                       "teto": round(100 * _wilson(kk, len(rs))[1]),
                       "lideres": [(nomes[c], n) for c, n in sorted(cont.items(), key=lambda x: -x[1])[:5]]})
    todos = set().union(*conjuntos.values()) if conjuntos else set()
    em_todas = set.intersection(*conjuntos.values()) if len(conjuntos) > 1 else set()
    # mesma pergunta, mesma IA, rodadas diferentes: quanto as listas de empresas coincidem
    grupos: dict = {}
    for x in ok:
        grupos.setdefault((x["pergunta"], x["provedor"]), []).append({normalizar(e) for e in x["empresas_recomendadas"]})
    pares = [len(a & b) / len(a | b) for g in grupos.values() for i, a in enumerate(g) for b in g[i + 1:] if a | b]
    return {
        "amostra": len(ok), "intervalo": (round(100 * baixo), round(100 * alto)),
        "por_ia": por_ia, "empresas": len(todos), "em_todas_ias": len(em_todas),
        "estabilidade": round(100 * sum(pares) / len(pares)) if pares else None,
    }


# --------------------------------------------------------------------------
# Conteúdo
# --------------------------------------------------------------------------

def pedido_de(pendencia: str) -> str:
    """[[CONFIRMAR: x]] -> "Confirmar: x"; [[DADO DO ESPECIALISTA: x]] -> "Informar: x"."""
    tipo, _, texto = pendencia.partition(":")
    if not texto:
        return pendencia.strip()
    verbo = {"CONFIRMAR": "Confirmar", "DADO DO ESPECIALISTA": "Informar"}.get(tipo.strip().upper(), tipo.strip())
    return f"{verbo}: {texto.strip()}"


def conteudo(c: dict) -> dict:
    q = dados.quadro(c["id"])
    if not q["pauta"]:
        return {"q": q, "etapas": [], "linhas": []}
    linhas = sorted(({**item, "status": s} for s in dados.STATUS_ARTIGO for item in q["colunas"][s]),
                    key=lambda entrada: entrada["numero"])
    etapas = []
    for status, rotulo, desc, vazio in ETAPAS:
        itens = q["colunas"][status]
        pend = sum(len(i["artigo"]["pendencias"]) for i in itens if i["artigo"])
        if pend:
            desc = f"{_plural(pend, 'pendência', 'pendências')} para resolver"
        etapas.append({"status": status, "rotulo": rotulo, "n": len(itens), "desc": desc, "vazio": vazio})
    # foco: a etapa (antes de publicado) onde mais artigos esperam alguém agir
    esperando = [e for e in etapas[:-1] if e["n"]]
    foco = max(esperando, key=lambda e: e["n"])["status"] if esperando else None

    escritos = [entrada for entrada in linhas if entrada["artigo"]]
    site = c["site"].rstrip("/")
    for entrada in linhas:
        entrada["url"] = f"{site}/{entrada['tema']['slug']}/"

    # Texto para mandar ao especialista (WhatsApp/e-mail): o que confirmar e o que perguntar
    blocos = []
    for entrada in escritos:
        a = entrada["artigo"]
        itens = [f"   • {pedido_de(p)}" for p in a["pendencias"]]
        itens += [f"   • {p}" for p in a.get("perguntas_especialista", [])[:3]]
        if itens:
            blocos.append(f"{entrada['numero']}. {a['titulo']}\n" + "\n".join(itens))
    especialista = ""
    if blocos:
        especialista = (f"Perguntas para o especialista da {c['nome']}\n"
                        "Pode responder por áudio. As respostas entram nos artigos do blog.\n\n"
                        + "\n\n".join(blocos))
    # próxima ação: o primeiro rascunho com pendências (ou qualquer rascunho); senão, o primeiro aprovado
    rascunhos = [entrada for entrada in linhas if entrada["status"] == "rascunho"]
    alvo = (next((entrada for entrada in rascunhos if entrada["artigo"]["pendencias"]), None) or next(iter(rascunhos), None))
    proximo = None
    if alvo:
        proximo = {"slug": alvo["tema"]["slug"], "rotulo": "Revisar o próximo rascunho"}
    elif aprovado := next((entrada for entrada in linhas if entrada["status"] == "aprovado"), None):
        proximo = {"slug": aprovado["tema"]["slug"], "rotulo": "Enviar o próximo ao WordPress"}
    return {
        "q": q, "etapas": etapas, "foco": foco, "linhas": linhas, "proximo": proximo,
        "palavras": sum(entrada["artigo"]["palavras"] for entrada in escritos),
        "pendencias": sum(len(entrada["artigo"]["pendencias"]) for entrada in escritos),
        "especialista": especialista,
    }


# --------------------------------------------------------------------------
# Paleta de comandos (Ctrl K)
# --------------------------------------------------------------------------

def paleta(cid: str | None) -> list[dict]:
    itens = [{"t": "Carteira de clientes", "tipo": "página", "url": url_for("inicio")},
             {"t": "Novo cliente", "tipo": "página", "url": url_for("novo_cliente")}]
    for c in dados.clientes():
        for rotulo, rota in [("Radar", "radar"), ("Conteúdo", "conteudo"), ("Plano de ações", "plano"),
                             ("Resultados", "resultados"), ("Mídia paga", "midia"), ("Configurar", "config"), ("Apresentar o radar", "apresentar")]:
            itens.append({"t": f"{c['nome']} · {rotulo}", "tipo": "cliente", "url": url_for(rota, cid=c["id"])})
    if cid and dados.cliente(cid):
        pasta, p = dados.pauta(cid)
        if p:
            arts = dados.artigos(pasta)
            for t in p["temas"]:
                a = arts.get(t["slug"])
                url = (url_for("artigo", cid=cid, slug=t["slug"]) if a
                       else url_for("conteudo", cid=cid) + "#" + t["slug"])
                itens.append({"t": a["titulo"] if a else t["titulo"], "tipo": "artigo", "url": url})
        for a in dados.plano(cid, dados.ultimo_radar(cid)):
            if a["guia"]:
                itens.append({"t": a["titulo"], "tipo": "guia",
                              "url": url_for("guia", cid=cid, nome=a["guia"])})
    return itens
