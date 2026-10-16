"""
radar/cruzamento.py — O radar mostra o sintoma; o rastreamento do site, a causa.

Junta um radar com o rastreamento do site do cliente:
  - as páginas do cliente que as IAs citaram estão abrindo, sem noindex, com texto?
  - para cada pergunta de indicação, a página do site que trata do assunto e se ela tem condições
    de ser citada, ou se falta a página;
  - as ações que entram no plano, na ordem de impacto.
Sem rede e sem IA: só cruza dados já salvos, então roda a cada tela aberta.

A ligação pergunta → página é por palavras em comum, e título, H1 e endereço pesam mais. É uma
aproximação: as telas dizem "página mais próxima", não "a página certa".
"""

import re
from datetime import datetime
from urllib.parse import urlsplit

from radar import auditoria, rastreador
from radar.analise import ROBOS_DE_BUSCA
from radar.extrator import normalizar

# Palavras que não dizem o assunto da pergunta ("qual a melhor…", "me indica…", "quanto custa…")
PALAVRAS_VAZIAS = set("""a o as os um uma uns umas de da do das dos em no na nos nas para pra por pelo pela com sem
e ou que qual quais quem onde como quando quanto quanta me te se eu voce vc sabe sobre melhor melhores bom boa bons
boas otimo otima top indica indique indicar indicacao recomenda recomende recomendar recomendacao sugere sugestao
conhece existe tem ha preciso quero procuro algum alguma mais perto aqui confiavel confiaveis empresa empresas
custa custo preco precos valor valores orcamento contratar cobra cobram vale pena""".split())
INTENCAO_PRECO = {"quanto", "custa", "custo", "preco", "precos", "valor", "valores", "orcamento", "cobra", "cobram"}
PESOS = {"titulo": 2, "h1": 1, "endereco": 2, "descricao": 1, "inicio": 1}
FORTES = ("titulo", "h1", "endereco")

# Ações do site no plano: títulos fixos (o andamento salvo no plano é pela chave do título)
ACOES = {
    "citadas": ("Consertar as páginas do site que as IAs citam", "antes"),
    "bloqueio": ("Liberar as páginas bloqueadas para os robôs de busca das IAs", "antes"),
    "noindex": ("Tirar o noindex das páginas que precisam aparecer", "antes"),
    "javascript": ("Pôr o texto das páginas no HTML", "antes"),
    "recusa": ("Destravar o acesso de robôs ao site", "antes"),
    "sem_pagina": ("Criar uma página para cada pergunta sem resposta no site", "depois"),
    "fracas": ("Reforçar as páginas que respondem às perguntas dos clientes", "depois"),
    "links": ("Corrigir links quebrados e redirecionamentos", "depois"),
    "metadados": ("Ajustar títulos, descrições e fichas das páginas", "depois"),
    "soltas": ("Ligar ao site as páginas soltas", "depois"),
}

def _radical(t: str) -> str:
    return t[:-1] if len(t) > 4 and t.endswith("s") else t


def termos(texto: str) -> set[str]:
    """Palavras que dizem o assunto: sem acento, sem palavras vazias, no singular aproximado."""
    return {_radical(t) for t in normalizar(texto or "").split() if len(t) > 1 and t not in PALAVRAS_VAZIAS}


def _cidade(cliente: dict) -> tuple[set[str], set[str]]:
    """Palavras do nome da cidade e a sigla (Belo Horizonte -> belo, horizonte; bh)."""
    nomes = [t for t in normalizar(cliente.get("cidade", "")).split() if t not in ("de", "da", "do", "das", "dos")]
    sigla = "".join(t[0] for t in nomes) if len(nomes) > 1 else ""
    return {_radical(t) for t in nomes}, ({sigla} if sigla else set())


def _tem_cidade(palavras: set[str], nomes: set[str], siglas: set[str]) -> bool:
    return bool(nomes) and (nomes <= palavras or bool(siglas & palavras))


def _campos(p: dict) -> dict[str, set[str]]:
    endereco = " ".join(re.split(r"[/\-_.]+", urlsplit(p["url"]).path))
    return {"titulo": termos(p.get("titulo")), "h1": termos(p.get("h1_texto")), "endereco": termos(endereco),
            "descricao": termos(p.get("descricao")), "inicio": termos(p.get("inicio"))}


def _ordem(candidata: tuple[dict, dict], servico: set[str]) -> tuple:
    p, campos = candidata
    pontos = sum(PESOS[c] for t in servico for c, palavras in campos.items() if t in palavras)
    prof = p["profundidade"] if p.get("profundidade") is not None else 99
    return pontos, rastreador.indexavel(p), -prof, p["palavras"]


def _motivos(p: dict, campos: dict, cidade: tuple | None, preco: bool) -> list[str]:
    """Por que a página tem pouca chance de ser citada para a pergunta."""
    m = []
    if p.get("noindex"):
        m.append("tem noindex: não aparece na busca")
    elif not rastreador.indexavel(p):
        m.append("indica outra página como a oficial (canonical)")
    if rastreador.so_javascript(p):
        m.append("o texto só aparece depois do JavaScript")
    elif p["palavras"] < rastreador.POUCO_TEXTO:
        m.append(f"só {p['palavras']} palavras no HTML")
    busca = [b for b in p.get("bloqueada_para", []) if b in ROBOS_DE_BUSCA]
    if busca:
        m.append("bloqueada no robots.txt para " + ", ".join(busca))
    if cidade and not _tem_cidade(campos["titulo"] | campos["h1"], *cidade):
        m.append("a cidade não aparece no título nem no H1")
    if preco and not p.get("tem_preco"):
        m.append("a pergunta é sobre preço e a página não mostra valores")
    return m


def _comparar(rs: list[dict], externas: dict[str, dict], p: dict | None, cidade: tuple) -> dict | None:
    """O que as páginas de concorrentes citadas nesta pergunta têm, ao lado da página do cliente (p).
    Mostra o que elas têm em comum; não prova que foi isso que fez a IA citá-las."""
    chaves = {rastreador.chave(f["url"]) for r in rs for f in r["fontes"] if f.get("url")}
    citadas = [externas[k] for k in chaves if k in externas]
    if not citadas:
        return None

    def tem_cidade(x: dict) -> bool:
        return _tem_cidade(termos(x.get("titulo")) | termos(x.get("h1_texto")), *cidade)

    def tem_ficha(x: dict) -> bool:
        return any(re.search(r"Organization|LocalBusiness|ProfessionalService|Service", t) for t in x.get("jsonld_tipos", []))

    sinais = []
    for rotulo, teste in (("cidade no título ou no H1", tem_cidade), ("perguntas frequentes", lambda x: bool(x.get("tem_faq"))),
                          ("preço ou faixa de preço", lambda x: bool(x.get("tem_preco"))), ("ficha da empresa ou do serviço", tem_ficha)):
        if cidade[0] or rotulo != "cidade no título ou no H1":
            n = sum(teste(x) for x in citadas)
            sinais.append({"sinal": rotulo, "concorrentes": n, "cliente": teste(p) if p else None,
                           "diferenca": 2 * n >= len(citadas) and not (p and teste(p))})
    palavras = sorted(x["palavras"] for x in citadas)
    return {"citadas": len(citadas), "dominios": sorted({x["dominio"] for x in citadas}),
            "mediana_palavras": palavras[len(palavras) // 2], "cliente_palavras": p["palavras"] if p else None,
            "sinais": sinais}


def _lista(itens: list[str]) -> str:
    return ", ".join(itens[:-1]) + " e " + itens[-1] if len(itens) > 1 else "".join(itens)


def resumo_comparacao(c: dict) -> str:
    """Uma frase com o que a maioria das páginas citadas tem e a do cliente não."""
    difs = [s for s in c["sinais"] if s["diferenca"]]
    palavras = (f"cerca de {c['mediana_palavras']} palavras"
                + (f" (a do site: {c['cliente_palavras']})" if c["cliente_palavras"] is not None else ""))
    mais_texto = c["cliente_palavras"] is None or c["mediana_palavras"] > 2 * c["cliente_palavras"]
    if c["citadas"] == 1:
        itens = ([palavras] if mais_texto else []) + [s["sinal"] for s in difs]
        return f"A página de concorrente que as IAs citaram tem {_lista(itens)}." if itens else ""
    partes = ([f"têm {palavras}"] if mais_texto else []) + [
        f"{s['concorrentes']} de {c['citadas']} {'tem' if s['concorrentes'] == 1 else 'têm'} {s['sinal']}" for s in difs]
    return ("As páginas de concorrentes que as IAs citaram " + "; ".join(partes) + ".") if partes else ""


def perguntas(run: dict, rastreio: dict) -> list[dict]:
    """Cada pergunta de indicação, a página do site mais próxima do assunto e o diagnóstico:
    sem_pagina, pagina_fraca (com os motivos) ou pagina_ok. Com as páginas de concorrentes que o
    radar leu, também a comparação com elas."""
    cli = run["cliente"]
    nomes, siglas = _cidade(cli)
    candidatas = [(p, _campos(p)) for p in rastreador.lidas(rastreio)]
    externas = {x["chave"]: x for x in run.get("paginas_concorrentes") or [] if "palavras" in x}
    saida = []
    for q in (q for q in cli["perguntas"] if q["tipo"] == "descoberta"):
        rs = [r for r in run["respostas"] if r["pergunta"] == q["texto"] and not r["erro"]]
        palavras = termos(q["texto"])
        servico = palavras - nomes - siglas
        item = {"pergunta": q["texto"], "mencoes": sum(r["marca_mencionada"] for r in rs), "respostas": len(rs),
                "pagina": None, "diagnostico": "sem_pagina", "motivos": []}
        pagina = None
        if servico and candidatas:
            p, campos = max(candidatas, key=lambda c: _ordem(c, servico))
            fortes = {t for t in servico if any(t in campos[c] for c in FORTES)}
            if 2 * len(fortes) >= len(servico):   # metade das palavras da pergunta no título, H1 ou endereço
                cidade = (nomes, siglas) if _tem_cidade(palavras, nomes, siglas) else None
                preco = bool(set(normalizar(q["texto"]).split()) & INTENCAO_PRECO)
                motivos, pagina = _motivos(p, campos, cidade, preco), p
                item.update(pagina={"url": p["url"], "titulo": p["titulo"], "palavras": p["palavras"]},
                            diagnostico="pagina_fraca" if motivos else "pagina_ok", motivos=motivos)
        comparacao = _comparar(rs, externas, pagina, (nomes, siglas)) if externas else None
        item["concorrentes"] = comparacao
        item["comparacao"] = resumo_comparacao(comparacao) if comparacao else ""
        saida.append(item)
    return saida


def urls_citadas(run: dict) -> list[str]:
    """Endereços do site do cliente que as IAs citaram neste radar (para o rastreamento conferir)."""
    hosts = rastreador.hosts_do_cliente(run["cliente"])
    urls = {}
    for r in run["respostas"]:
        for f in r["fontes"]:
            if f.get("url") and rastreador.e_interna(f["url"], hosts):
                urls.setdefault(rastreador.chave(f["url"]), f["url"])
    return list(urls.values())


def _estado(p: dict | None, por_chave: dict) -> tuple[str, str]:
    """(o que acontece com a página citada, nível: erro, aviso ou ok)"""
    if p is None:
        return "não foi lida pelo rastreamento", "aviso"
    if p.get("nao_rastreada"):
        return "o robots.txt pede para não rastrear", "aviso"
    if rastreador.quebrada(p):
        return (f"não abre (HTTP {p['status']})" if p.get("status") else f"não abre ({p.get('erro', 'sem resposta')})"), "erro"
    if p.get("destino"):
        destino = por_chave.get(rastreador.chave(p["destino"]))
        if destino and rastreador.quebrada(destino):
            return "redireciona para uma página que não abre", "erro"
        return f"redireciona para {auditoria.caminho_de(p['destino'])}", "aviso"
    if "palavras" not in p:
        return "não é uma página HTML", "aviso"
    if p.get("noindex"):
        return "tem noindex: some da busca", "erro"
    if rastreador.so_javascript(p):
        return "o texto só aparece com JavaScript", "erro"
    busca = [b for b in p.get("bloqueada_para", []) if b in ROBOS_DE_BUSCA]
    if busca:
        return "bloqueada para " + ", ".join(busca), "erro"
    if p["palavras"] < rastreador.POUCO_TEXTO:
        return f"só {p['palavras']} palavras no HTML", "aviso"
    return "abre, com texto e sem bloqueio", "ok"


def paginas_citadas(run: dict, rastreio: dict) -> list[dict]:
    """Páginas do cliente que as IAs citaram: quantas vezes, em quais perguntas e o estado de cada uma."""
    hosts = rastreador.hosts_do_cliente(run["cliente"])
    por_chave = {p["chave"]: p for p in rastreio["paginas"]}
    finais = {rastreador.chave(p["destino"]): p for p in rastreio["paginas"] if p.get("destino")}
    citadas: dict[str, dict] = {}
    for r in run["respostas"]:
        if r["erro"]:
            continue
        urls = {rastreador.chave(f["url"]): f["url"] for f in r["fontes"] if f.get("url") and rastreador.e_interna(f["url"], hosts)}
        for k, url in urls.items():
            c = citadas.setdefault(k, {"url": url, "vezes": 0, "perguntas": [], "ias": []})
            c["vezes"] += 1
            for campo, valor in (("perguntas", r["pergunta"]), ("ias", r["provedor"])):
                if valor not in c[campo]:
                    c[campo].append(valor)
    for k, c in citadas.items():
        p = por_chave.get(k) or finais.get(k)
        c["estado"], c["nivel"] = _estado(p, por_chave)
    return sorted(citadas.values(), key=lambda c: (-c["vezes"], c["url"]))


def _exemplos(paginas: list[dict], n: int = 3) -> str:
    caminhos = list(dict.fromkeys(auditoria.caminho_de(p["url"]) for p in paginas))
    return ", ".join(caminhos[:n]) + (f" e mais {len(caminhos) - n}" if len(caminhos) > n else "")


def _acao(chave: str, texto: str) -> dict:
    titulo, lugar = ACOES[chave]
    return {"titulo": titulo, "texto": texto, "lugar": lugar, "origem": "site", "chave": chave}


def _acoes(rastreio: dict, citadas: list[dict], qs: list[dict]) -> list[dict]:
    probs = {p["codigo"]: p for p in rastreador.problemas(rastreio)}
    acoes = []
    ruins = [c for c in citadas if c["nivel"] == "erro"]
    if ruins:
        acoes.append(_acao("citadas", "As IAs mandam quem pergunta para páginas do site que hoje não servem: "
                           + "; ".join(f"{auditoria.caminho_de(c['url'])} ({c['estado']})" for c in ruins[:3])
                           + ". Cada citação perdida é um cliente que chega numa página de erro, ou que a busca nem mostra."))
    if probs.get("interrompido"):
        acoes.append(_acao("recusa", probs["interrompido"]["detalhe"] + " Se o firewall barra um rastreador educado, "
                                    "provavelmente barra os robôs das IAs também."))
    for chave, codigo, texto in (
            ("bloqueio", "bloqueada_para_ias", "O robots.txt impede robôs de busca das IAs de abrir {n} página(s), como {ex}."),
            ("noindex", "noindex", "{n} página(s) importantes estão marcadas para não aparecer na busca, como {ex}. "
                                   "É um ajuste no plugin de SEO."),
            ("javascript", "texto_so_com_javascript", "{n} página(s) chegam vazias para os robôs de IA, que não executam "
                                                      "JavaScript ({ex}). Sem o texto no HTML, não há o que citar.")):
        p = probs.get(codigo)
        if p and p["nivel"] == "erro":
            acoes.append(_acao(chave, texto.format(n=p["total"], ex=_exemplos(p["paginas"]))))

    sem = [q for q in qs if q["diagnostico"] == "sem_pagina"]
    if sem:
        referencia = next((q["comparacao"] for q in sem if q["comparacao"]), "")
        acoes.append(_acao("sem_pagina", "Nenhuma página do site trata de: " + "; ".join(f"“{q['pergunta']}”" for q in sem[:4])
                           + ("…" if len(sem) > 4 else "") + ". Uma página ou artigo por pergunta, com a resposta "
                           "logo no primeiro parágrafo, a cidade no título e perguntas frequentes no fim."
                           + (f" {referencia}" if referencia else "")))
    fracas = [q for q in qs if q["diagnostico"] == "pagina_fraca"]
    if fracas:
        por_pagina: dict[str, list[str]] = {}
        for q in fracas:
            por_pagina.setdefault(q["pagina"]["url"], [])
            por_pagina[q["pagina"]["url"]] += [m for m in q["motivos"] if m not in por_pagina[q["pagina"]["url"]]]
        referencia = next((q["comparacao"] for q in fracas if q["comparacao"]), "")
        acoes.append(_acao("fracas", "As páginas que tratam das perguntas dos clientes têm problemas: "
                           + "; ".join(f"{auditoria.caminho_de(u)}: {', '.join(m)}" for u, m in list(por_pagina.items())[:3])
                           + "." + (f" {referencia}" if referencia else "")))

    for chave, rotulos in (("links", {"quebrada": "página(s) que não abrem", "cadeia_redirecionamento": "cadeia(s) de redirecionamento",
                                      "link_para_redirecionamento": "link(s) para endereço antigo",
                                      "sitemap_com_erro": "endereço(s) ruins no sitemap"}),
                           ("metadados", {"sem_titulo": "sem título", "titulo_repetido": "com título repetido",
                                          "sem_descricao": "sem descrição", "descricao_repetida": "com descrição repetida",
                                          "h1": "sem um H1 único", "ficha_invalida": "com ficha JSON-LD inválida",
                                          "canonical_outra": "apontando outra página como oficial"}),
                           ("soltas", {"orfa": "sem nenhum link no site", "fora_do_sitemap": "fora do sitemap"})):
        partes = [f"{probs[c]['total']} {r}" for c, r in rotulos.items() if c in probs]
        if partes:
            prefixo = "Páginas: " if chave != "links" else ""
            acoes.append(_acao(chave, prefixo + "; ".join(partes) + ". A lista completa está no rastreamento do site."))
    return acoes


def cruzar(run: dict, rastreio: dict) -> dict:
    citadas, qs = paginas_citadas(run, rastreio), perguntas(run, rastreio)
    return {
        "paginas_citadas": citadas,
        "perguntas": qs,
        "acoes": _acoes(rastreio, citadas, qs),
        "resumo": {"citadas": len(citadas), "citadas_com_problema": sum(c["nivel"] == "erro" for c in citadas),
                   "sem_pagina": sum(q["diagnostico"] == "sem_pagina" for q in qs),
                   "fracas": sum(q["diagnostico"] == "pagina_fraca" for q in qs),
                   "ok": sum(q["diagnostico"] == "pagina_ok" for q in qs)},
    }


def plano(run: dict, rastreio: dict | None, anterior: dict | None = None) -> list[dict]:
    """Recomendações do radar com as ações do site: o que impede de ser citado vem antes de tudo,
    os ajustes de página depois das recomendações do radar. Com o rastreio `anterior`, a ação que
    existia nele e sumiu no atual volta marcada como resolvida (o rastreio confirmou a correção)."""
    recs = list(run["metricas"]["recomendacoes"])
    if not rastreio:
        return recs
    site = cruzar(run, rastreio)["acoes"]
    if anterior:
        agora = {a["chave"] for a in site}
        quando = datetime.fromisoformat(rastreio["gerado_em"]).strftime("%d/%m/%Y")
        site += [{**a, "resolvida": True, "nota": f"Resolvido: o rastreio de {quando} não encontra mais o problema."}
                 for a in cruzar(run, anterior)["acoes"] if a["chave"] not in agora]
    return [a for a in site if a["lugar"] == "antes"] + recs + [a for a in site if a["lugar"] == "depois"]
