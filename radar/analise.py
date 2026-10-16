"""
radar/analise.py — Transforma as respostas em métricas de visibilidade.

Visibilidade e ranking usam só as perguntas de "descoberta" (o usuário
procura um fornecedor sem citar a marca). Perguntas de "marca" medem outra
coisa: o que a IA sabe sobre a empresa quando perguntam por ela.
"""

import unicodedata
from collections import Counter, defaultdict
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from radar.extrator import e_a_marca, normalizar
from radar.modelos import NOMES_PROVEDOR, Resposta, dominio_de, numero_br

# Plataformas que as IAs citam como fonte mas que não são concorrentes
PLATAFORMAS = {"google.com", "instagram.com", "facebook.com", "linkedin.com", "youtube.com",
               "clutch.co", "reclameaqui.com.br", "wikipedia.org", "reddit.com", "tiktok.com"}

# Rankings, listas e diretórios: são fontes que citam empresas, não concorrentes.
# Ex.: o ChatGPT cita um site de ranking local ("Ranking <cidade>") e o extrator não deve tratá-lo como agência.
PALAVRAS_DE_LISTA = ("ranking", "melhores", "top10", "top 10", "lista", "guia", "diretorio",
                     "catalogo", "review", "avaliacoes", "comparativo", "indicacoes")


def e_fonte_de_lista(nome_ou_dominio: str) -> bool:
    t = unicodedata.normalize("NFKD", nome_ou_dominio).encode("ascii", "ignore").decode().lower()
    return any(p in t for p in PALAVRAS_DE_LISTA)


# Robôs que buscam na hora da pergunta (bloquear = a empresa some das respostas)
ROBOS_DE_BUSCA = ("OAI-SearchBot", "ChatGPT-User", "Claude-SearchBot", "PerplexityBot", "Googlebot", "bingbot")

# Falha técnica (nome da checagem em radar/auditoria.py) -> ação para o plano
ACOES_TECNICAS = {
    "robots.txt libera as IAs": (
        "Ajustar o robots.txt", "As regras atuais impedem IAs de lerem o site ({detalhe})."),
    "Sitemap publicado": (
        "Publicar o sitemap", "Sem ele, Google e Bing demoram mais para achar páginas novas."),
    "Dados estruturados da empresa": (
        "Adicionar a ficha técnica da empresa ao site",
        "Nome, endereço, telefone e área de atuação em formato que Google e IAs leem direto."),
    "Blog com conteúdo": (
        "Criar o blog com artigos que respondem aos clientes",
        "Hoje: {detalhe}. Artigos por serviço e por nicho são o que transforma o site em fonte."),
}


def _pct(parte: int, total: int) -> float:
    return round(100 * parte / total, 1) if total else 0.0


def url_canonica(url: str) -> str:
    """Mesma página = mesma chave: sem utm_* (o ChatGPT acrescenta utm_source=openai),
    sem âncora e sem barra final."""
    partes = urlsplit(url)
    query = urlencode([(k, v) for k, v in parse_qsl(partes.query) if not k.lower().startswith("utm_")])
    caminho = partes.path.rstrip("/") or "/"
    return urlunsplit((partes.scheme, partes.netloc.lower(), caminho, query, ""))


def calcular(respostas: list[Resposta], cliente: dict, auditoria: list[dict] | None = None) -> dict:
    for r in respostas:   # listas e rankings citados como fonte não são concorrentes
        r.empresas_recomendadas = [n for n in r.empresas_recomendadas if not e_fonte_de_lista(n)]
    validas = [r for r in respostas if not r.erro]
    descoberta = [r for r in validas if r.tipo_pergunta == "descoberta"]
    marca = [r for r in validas if r.tipo_pergunta == "marca"]

    # --- visibilidade por provedor ---
    por_provedor = {}
    for prov in sorted({r.provedor for r in validas}):
        rs = [r for r in descoberta if r.provedor == prov]
        posicoes = [r.posicao_marca for r in rs if r.posicao_marca]
        por_provedor[prov] = {
            "respostas": len(rs),
            "mencoes": sum(r.marca_mencionada for r in rs),
            "visibilidade": _pct(sum(r.marca_mencionada for r in rs), len(rs)),
            "posicao_media": round(sum(posicoes) / len(posicoes), 1) if posicoes else None,
            "site_citado": sum(r.marca_citada_como_fonte for r in rs),
        }

    # --- ranking de empresas recomendadas (participação nas menções) ---
    contagem: Counter = Counter()
    nome_exibicao: dict[str, Counter] = defaultdict(Counter)
    for r in descoberta:
        # dict dedup: a mesma empresa conta uma vez por resposta
        for chave, original in {normalizar(n): n for n in r.empresas_recomendadas}.items():
            contagem[chave] += 1
            nome_exibicao[chave][original] += 1
    total_mencoes = sum(contagem.values())
    ranking = [{
        "nome": nome_exibicao[chave].most_common(1)[0][0],
        "respostas": n,
        "participacao": _pct(n, total_mencoes),
        "e_a_marca": e_a_marca(nome_exibicao[chave].most_common(1)[0][0], cliente),
    } for chave, n in contagem.most_common()]

    # --- fontes que as IAs usaram (onde a marca precisa estar) ---
    fontes: Counter = Counter()
    for r in descoberta:
        for dom in {f.dominio for f in r.fontes if f.dominio}:
            fontes[dom] += 1
    nomes_concorrentes = {normalizar(e["nome"]).replace(" ", "") for e in ranking if not e["e_a_marca"]}

    def tipo_fonte(dom: str) -> str:
        if any(dom.endswith(d) for d in cliente["dominios"]):
            return "marca"
        if any(dom == p or dom.endswith("." + p) for p in PLATAFORMAS):
            return "plataforma"
        if e_fonte_de_lista(dom):
            return "terceiro"
        base = dom.split(".")[0] if not dom.startswith(("blog.", "ads.")) else dom.split(".")[1]
        base = base.replace("-", "")  # fm-leads.com.br -> fmleads, igual ao nome normalizado
        if len(base) >= 4 and any(base in n or n in base for n in nomes_concorrentes):
            return "concorrente"
        return "terceiro"

    ranking_fontes = [{
        "dominio": dom,
        "respostas": n,
        "pct_respostas": _pct(n, len(descoberta)),
        "tipo": tipo_fonte(dom),
    } for dom, n in fontes.most_common(20)]

    # --- páginas (URL) mais consultadas, com os concorrentes que aparecem junto ---
    paginas: Counter = Counter()
    junto: dict[str, Counter] = defaultdict(Counter)
    tipo_url: dict[str, str] = {}
    for r in descoberta:
        outros = [n for n in r.empresas_recomendadas if not e_a_marca(n, cliente)]
        for url, f in {url_canonica(f.url): f for f in r.fontes if f.url}.items():
            paginas[url] += 1
            tipo_url[url] = tipo_fonte(f.dominio)
            junto[url].update(outros)
    ranking_paginas = [{
        "url": url,
        "dominio": dominio_de(url),
        "respostas": n,
        "tipo": tipo_url[url],
        "junto_de": [nome for nome, _ in junto[url].most_common(3)],
    } for url, n in paginas.most_common(15)]

    # --- o que as IAs pesquisaram antes de responder (pautas e alvos de SEO) ---
    buscas: Counter = Counter()
    for r in validas:
        for q in {b.strip().lower() for b in (r.buscas or []) if b and b.strip()}:
            buscas[q] += 1
    ranking_buscas = [{"busca": q, "vezes": n} for q, n in buscas.most_common(20)]

    resumo = {
        "respostas_descoberta": len(descoberta),
        "mencoes": sum(r.marca_mencionada for r in descoberta),
        "visibilidade": _pct(sum(r.marca_mencionada for r in descoberta), len(descoberta)),
        "participacao": next((e["participacao"] for e in ranking if e["e_a_marca"]), 0.0),
        "site_citado": _pct(sum(r.marca_citada_como_fonte for r in descoberta), len(descoberta)),
        "posicao_no_ranking": next((i for i, e in enumerate(ranking, 1) if e["e_a_marca"]), None),
        "concorrentes": len([e for e in ranking if not e["e_a_marca"]]),
        "erros": len(respostas) - len(validas),
        "marca_conhecida": sum(bool(r.empresa_certa and r.tem_informacao) for r in marca),
        "perguntas_marca": len(marca),
        "confusoes": [{"provedor": r.provedor, "empresa": r.empresa_confundida}
                      for r in marca if r.empresa_certa is False and r.empresa_confundida],
        "fontes_concorrentes": _pct(sum(f["respostas"] for f in ranking_fontes if f["tipo"] == "concorrente"),
                                    sum(f["respostas"] for f in ranking_fontes)),
    }

    return {
        "resumo": resumo,
        "por_provedor": por_provedor,
        "ranking": ranking,
        "fontes": ranking_fontes,
        "paginas": ranking_paginas,
        "buscas": ranking_buscas,
        "recomendacoes": recomendacoes(resumo, ranking_fontes, ranking_paginas, cliente, auditoria or []),
    }


def recomendacoes(resumo: dict, fontes: list[dict], paginas: list[dict], cliente: dict,
                  auditoria: list[dict]) -> list[dict]:
    """Ações para o plano, da que mais muda as respostas das IAs para a que menos.

    A ordem segue o que os estudos de 2026 mostram: identidade, presença em sites
    de terceiros e avaliações pesam mais que ajustes técnicos e que o site próprio.
    """
    recs = []
    falhas = {c["nome"]: c for c in auditoria if not c["ok"]}
    nome = cliente["nome"]

    def tecnica(chave: str):
        if chave in falhas and chave in ACOES_TECNICAS:
            titulo, texto = ACOES_TECNICAS[chave]
            recs.append({"titulo": titulo, "texto": texto.format(detalhe=falhas[chave]["detalhe"])})

    # Bloqueio de robôs de BUSCA tira a empresa das respostas: vem antes de tudo.
    robos = falhas.get("Robôs das IAs conseguem acessar o site")
    detalhe_robos = robos["detalhe"].removeprefix("bloqueados: ").replace("; ", " e ") if robos else ""
    robos_busca = bool(robos and any(r in robos["detalhe"] for r in ROBOS_DE_BUSCA))
    if robos_busca:
        recs.append({"titulo": "Liberar os robôs de busca das IAs",
                     "texto": f"O site recusa robôs que buscam na hora da pergunta ({detalhe_robos}). "
                              "Enquanto isso durar, a empresa não pode ser citada por essas IAs."})
    tecnica("robots.txt libera as IAs")

    for c in resumo["confusoes"][:1]:
        recs.append({
            "titulo": "Firmar a identidade oficial da empresa",
            "texto": f"O {NOMES_PROVEDOR.get(c['provedor'], c['provedor'])} confundiu a {nome} com "
                     f"{c['empresa']}. Ficha da empresa no Wikidata, dados estruturados com links para "
                     "os perfis oficiais, página Sobre com CNPJ e endereço, e o mesmo nome, telefone e "
                     "site em todos os perfis.",
        })

    alvos = [p for p in paginas if p["tipo"] in ("terceiro", "plataforma")
             and "google." not in p["dominio"]][:3]
    if alvos:
        recs.append({
            "titulo": "Entrar nas listas e páginas de terceiros que as IAs consultam",
            "texto": "Em perguntas de categoria, as IAs citam quase só sites de terceiros. As páginas "
                     "mais usadas no radar foram de " + ", ".join(dict.fromkeys(p["dominio"] for p in alvos))
                     + ". Cada uma vira um alvo: pedir inclusão, completar o perfil ou participar da "
                     "conversa.",
        })

    recs.append({
        "titulo": "Aumentar as avaliações no Google",
        "texto": "Empresas recomendadas pelas IAs têm, em média, 133 avaliações no Google; as não "
                 "recomendadas, 11 (Insites, 2026). Pedir avaliação a cada cliente atendido, por QR "
                 "code e link no WhatsApp, e responder todas.",
    })

    if resumo["visibilidade"] < 30 or resumo["fontes_concorrentes"] >= 20:
        recs.append({
            "titulo": "Publicar conteúdo que responde às perguntas dos clientes",
            "texto": f"É assim que os concorrentes viram fonte ({numero_br(round(resumo['fontes_concorrentes']))}% "
                     "das fontes das IAs). Páginas por serviço, nicho e cidade, preços, comparações e "
                     "dados próprios, começando pelas perguntas de compra.",
        })
    else:
        tecnica("Blog com conteúdo")

    recs.append({
        "titulo": "Cadastrar o site no Bing Webmaster Tools e no Bing Places",
        "texto": "A busca do ChatGPT usa principalmente o índice do Bing. O Webmaster Tools mostra, "
                 "de graça, quais buscas feitas pela IA levaram ao site, e o Bing Places é o perfil "
                 "local equivalente ao do Google.",
    })

    if robos and not robos_busca:
        recs.append({"titulo": "Liberar os robôs de treino das IAs",
                     "texto": f"O site bloqueia {detalhe_robos}. A busca das IAs segue liberada; estes "
                              "robôs definem o que os modelos sabem da empresa sem pesquisar. É um ajuste "
                              "no painel do Cloudflare ou da hospedagem, e a decisão é da empresa."})
    tecnica("Dados estruturados da empresa")
    tecnica("Sitemap publicado")

    plataformas = [f["dominio"] for f in fontes if f["tipo"] == "plataforma"
                   and not f["dominio"].endswith("google.com")][:4]
    if plataformas:
        recs.append({
            "titulo": "Participar das plataformas que as IAs mais citam",
            "texto": "No radar apareceram " + ", ".join(plataformas) + ". Reddit, YouTube e LinkedIn "
                     "lideram as citações das IAs no mundo: respostas úteis, vídeos e artigos, sem "
                     "propaganda.",
        })

    if resumo["visibilidade"] < 30:
        recs.append({
            "titulo": "Preparar campanhas de anúncios no ChatGPT",
            "texto": "O piloto de anúncios no ChatGPT começou no Brasil em agosto de 2026, com serviços "
                     "locais entre as categorias iniciais. Onde o orgânico não aparece, o anúncio "
                     "cobre: preparar páginas de destino e medição para entrar quando a compra abrir.",
        })
    return recs
