"""
app/leituras.py — "Aviso" e "Como resolver" de cada seção do radar.

Cada achado do radar vem com uma leitura em linguagem de dono de negócio: o que o
número quer dizer, os termos que aparecem nele (diretório, lista local…) e os passos
para corrigir, com o guia do plano quando existir. Tudo montado a partir dos dados
do próprio radar, para valer para qualquer cliente.
"""

import re

from app import dados
from radar.analise import e_fonte_de_lista
from radar.extrator import normalizar
from radar.modelos import numero_br

# O que é cada site que costuma aparecer como fonte das IAs
SITES = {
    "clutch.co": "diretório internacional de agências, com avaliações de clientes verificadas por entrevista",
    "reddit.com": "fórum de discussões; as IAs citam muito as recomendações feitas por pessoas ali",
    "youtube.com": "vídeos; as IAs usam títulos, descrições e transcrições",
    "linkedin.com": "perfis e artigos profissionais da empresa e da equipe",
    "instagram.com": "perfil da empresa; ajuda a IA a confirmar que a empresa existe",
    "facebook.com": "página da empresa, com avaliações",
    "reclameaqui.com.br": "reputação e atendimento de reclamações",
    "wikipedia.org": "enciclopédia; só para empresas com cobertura na imprensa",
    "sortlist.com.br": "diretório de agências com avaliações",
    "goodfirms.co": "diretório de empresas de serviços com avaliações",
}

TERMOS = {
    "diretorio": ("Diretório", "catálogo de empresas de um setor, com uma página para cada uma e avaliações "
                               "de clientes. Funciona como uma lista telefônica especializada."),
    "lista": ("Lista local", "página do tipo “as 10 melhores opções de {servico} em {cidade}”, feita por um site "
                             "de rankings ou da cidade. É o que a IA encontra quando pesquisa “melhor … em {cidade}”."),
    "confirmacao": ("Por que pesa", "a IA confia mais quando sites independentes confirmam o que a empresa diz "
                                    "de si mesma. Só o próprio site não basta."),
    "margem": ("Margem de erro", "a faixa onde o valor real está, com 95% de confiança. Zero em poucas respostas "
                                 "não prova que é zero: prova que é baixo."),
    "identidade": ("Identidade", "os dados que provam qual empresa é esta: CNPJ, endereço, telefone, redes oficiais "
                                 "e página Sobre. Sem eles, a IA mistura empresas de nome parecido."),
    "bing": ("Bing", "o ChatGPT pesquisa a web pelo índice do Bing. Estar bem no Bing é pré-requisito para "
                     "aparecer no ChatGPT."),
}

# Como resolver cada checagem técnica que falhar (nome da checagem -> passo, guia)
RESOLVER_CHECK = {
    "Robôs das IAs conseguem acessar o site": (
        "Liberar esses robôs no painel do Cloudflare ou da hospedagem (regras de bots e firewall).",
        "06-robos-de-treino"),
    "robots.txt libera as IAs": (
        "Tirar do robots.txt as linhas “Disallow” dos robôs de IA.", "06-robos-de-treino"),
    "Sitemap publicado": (
        "Ativar o sitemap no plugin de SEO do site e enviar o endereço ao Search Console e ao Bing Webmaster Tools.",
        "05-bing-e-plataformas"),
    "Dados estruturados da empresa": (
        "Colar no site a ficha da empresa em JSON-LD (nome, CNPJ, endereço, telefone, redes). O código pronto está no guia.",
        "01-identidade-oficial"),
    "Identidade da empresa clara para as IAs": (
        "Publicar no site o que falta: {detalhe}.", "01-identidade-oficial"),
    "Blog com conteúdo": (
        "Publicar os artigos da pauta, começando pelas perguntas em que a marca não apareceu.", None),
}


def _guia(cid: str, nome: str | None) -> str | None:
    return nome if nome and (dados.ENTREGAS_DIR / cid / f"{nome}.md").exists() else None


def _termo(chave: str, cli: dict) -> dict:
    rotulo, texto = TERMOS[chave]
    servico = cli.get("segmento", "serviço").split("/")[0].strip().lower()
    return {"termo": rotulo, "texto": texto.format(servico=servico, cidade=cli.get("cidade", "sua cidade"))}


def resolver_check(ch: dict, cid: str) -> dict | None:
    if ch["ok"] or ch["nome"] not in RESOLVER_CHECK:
        return None
    passo, guia = RESOLVER_CHECK[ch["nome"]]
    detalhe = ch["detalhe"].removeprefix("faltam: ").replace("; ", ", ")
    return {"passo": passo.format(detalhe=detalhe), "guia": _guia(cid, guia)}


def _sem_simbolos(t: str) -> str:
    return normalizar(t).replace(" ", "")


def _alvos_terceiros(m: dict) -> list[dict]:
    """Diretórios, listas e plataformas conhecidas que as IAs leram, do mais usado ao menos.
    Sites genéricos ficam de fora: muitas vezes são de concorrentes (ex.: fm-leads.com.br)."""
    concorrentes = {_sem_simbolos(e["nome"]) for e in m.get("ranking", []) if not e.get("e_a_marca")}
    vistos, alvos = set(), []
    for f in (m.get("paginas") or []) + (m.get("fontes") or []):
        dom = f["dominio"].removeprefix("www.")
        if f["tipo"] not in ("terceiro", "plataforma") or dom in vistos or dom.endswith(("google.com", "google.com.br")):
            continue
        vistos.add(dom)
        tipo = "lista" if e_fonte_de_lista(dom) else ("diretorio" if dom in ("clutch.co", "sortlist.com.br", "goodfirms.co") else "site")
        base = _sem_simbolos(dom.split(".")[0])
        if tipo == "site" and (dom not in SITES or any(base in n or n in base for n in concorrentes if len(n) >= 4)):
            continue
        desc = SITES.get(dom) or ("lista ou ranking de empresas" if tipo == "lista" else "site de terceiros")
        alvos.append({"dominio": dom, "tipo": tipo, "descricao": desc, "vezes": f["respostas"]})
    return alvos[:5]


def montar(run: dict, v: dict) -> dict:
    cli, m = run["cliente"], run["metricas"]
    cid, nome, r = cli["id"], cli["nome"], m["resumo"]
    servico = cli.get("segmento", "serviço").split("/")[0].strip().lower()
    cidade = cli.get("cidade", "")
    conf = v["confianca"]
    L = {}

    # --- resumo: a marca aparece? ---
    if r["mencoes"] == 0:
        aviso = (f"Em nenhuma das {v['total']} respostas de indicação a {nome} foi citada. Isso não prova que a chance "
                 f"é zero, mas mostra que, no melhor cenário, ela fica abaixo de {conf['intervalo'][1]}%: menos de "
                 f"{max(1, round(conf['intervalo'][1] / 10))} em cada 10 pessoas que pedem indicação ouviriam falar da empresa.")
    else:
        aviso = (f"A {nome} foi citada em {r['mencoes']} de {v['total']} respostas. A visibilidade real fica entre "
                 f"{conf['intervalo'][0]}% e {conf['intervalo'][1]}%.")
    L["resumo"] = {"tom": "alerta" if r["visibilidade"] < 30 else "ok", "aviso": aviso,
                   "termos": [_termo("margem", cli)],
                   "passos": [p["titulo"] for p in m["recomendacoes"][:3]],
                   "rodape": "Ordem do plano de ações: do que mais muda as respostas das IAs para o que menos."}

    # --- concorrentes ---
    lider = v["destaque"]["lider"]
    if lider:
        L["concorrentes"] = {
            "tom": "alerta",
            "aviso": (f"Quem pergunta às IAs recebe {r['concorrentes']} outras empresas no lugar da {nome}. "
                      f"{lider['nome']} lidera, citada em {v['destaque']['lider_pct']}% das respostas. Elas aparecem "
                      "porque os sites que as IAs leem falam delas: o próprio site, diretórios e listas."),
            "termos": [],
            "passos": [f"Criar uma página de serviço com a cidade no título, como “{servico} em {cidade}”, "
                       "respondendo o que o cliente pergunta (preço, prazo, como funciona).",
                       f"Abrir em “Pergunta por pergunta” as respostas em que {lider['nome']} aparece e ver quais "
                       "sites a IA citou junto: são os alvos de presença.",
                       "Repetir o radar depois das correções e comparar com este."],
        }

    # --- por IA ---
    if len(conf["por_ia"]) > 1:
        L["por-ia"] = {
            "tom": "alerta" if conf["em_todas_ias"] < 0.2 * max(conf["empresas"], 1) else "ok",
            "aviso": (f"Só {conf['em_todas_ias']} das {conf['empresas']} empresas aparecem em todas as IAs. Cada IA "
                      "pesquisa em lugares diferentes, então um plano feito só para o Google deixa as outras de fora."),
            "termos": [_termo("bing", cli)],
            "passos": ["Para o ChatGPT: cadastrar o site no Bing Webmaster Tools e a empresa no Bing Places.",
                       "Para o Google: completar o Perfil da Empresa no Google e cadastrar o site no Search Console.",
                       "Acompanhar cada IA separada no radar, não só a média."],
            "guia": _guia(cid, "05-bing-e-plataformas"),
        }

    # --- fontes: diretórios e listas ---
    alvos = _alvos_terceiros(m)
    pct_conc = round(r["fontes_concorrentes"])
    marca_pct = next((g["pct"] for g in v["composicao"] if g["tipo"] == "marca"), 0)
    termos = [_termo("diretorio", cli), _termo("lista", cli), _termo("confirmacao", cli)]
    passos = []
    for a in alvos[:4]:
        verbo = {"lista": "Pedir inclusão em", "diretorio": "Criar ou completar o perfil em"}.get(a["tipo"], "Marcar presença em")
        passos.append(f"{verbo} {a['dominio']} ({a['descricao']}; citado {a['vezes']}×).")
    passos.append("Pedir a 3 a 5 clientes satisfeitos que deixem avaliação nesses sites e no Google.")
    L["fontes"] = {
        "tom": "alerta" if pct_conc >= 20 or marca_pct == 0 else "ok",
        "aviso": (f"{numero_br(pct_conc)}% do que as IAs leram são sites de concorrentes, e o site da {nome} "
                  f"{'não aparece' if marca_pct == 0 else f'aparece em {marca_pct}%'}. O resto são diretórios, listas "
                  "e plataformas: é ali que dá para entrar mais rápido, porque são sites de terceiros que a IA já consulta."),
        "termos": termos, "passos": passos,
        "guia": _guia(cid, "02-listas-de-terceiros"),
    }

    # --- marca: confusão de identidade ---
    if v["marca"]:
        confundiu = [x for x in v["marca"] if x["estado"] == "confundiu"]
        ident = next((c for c in run.get("auditoria") or [] if c["nome"] == "Identidade da empresa clara para as IAs"), None)
        faltam = ident["detalhe"].removeprefix("faltam: ").split("; ") if ident and not ident["ok"] else []
        if confundiu:
            outra = re.split(r"\s+[—–-]\s+|\s*\(", confundiu[0]["titulo"].removeprefix("Falou de "))[0]
            aviso = (f"Em {len(confundiu)} de {len(v['marca'])} respostas sobre o nome, a IA descreveu {outra} no lugar "
                     f"da {nome}. Quem pesquisa a empresa antes de contratar recebe informação de outra.")
        else:
            aviso = f"As IAs reconhecem a {nome} quando perguntam pelo nome. Manter os dados iguais em todos os perfis."
        passos = [f"Publicar no site: {f}." for f in faltam]
        passos += ["Usar exatamente o mesmo nome, telefone e endereço no site, no Google, no Instagram e no LinkedIn.",
                   "Ligar o site aos perfis oficiais na ficha da empresa (dados estruturados) e criar o item no Wikidata.",
                   "Refazer as perguntas sobre o nome depois de publicar, para medir se a confusão diminuiu."]
        L["marca"] = {"tom": "alerta" if confundiu else "ok", "aviso": aviso,
                      "termos": [_termo("identidade", cli)], "passos": passos,
                      "guia": _guia(cid, "01-identidade-oficial")}

    # --- confiança ---
    L["confianca"] = {
        "tom": "ok",
        "aviso": (f"As IAs mudam a resposta a cada consulta: só {conf['estabilidade']}% das empresas se repetiram entre "
                  "rodadas. Uma rodada só pode ser sorte; os números deste radar indicam direção."
                  if conf.get("estabilidade") is not None else
                  "Com uma rodada por pergunta, os números indicam direção, não posição exata."),
        "termos": [],
        "passos": ["Medir uma vez por mês com cerca de 90 respostas (10 perguntas, 2 IAs, 5 rodadas).",
                   "Comparar sempre com o mesmo método e as mesmas perguntas, para separar melhora real de variação."],
    }
    return L
