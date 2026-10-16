"""
site_cliente/checagem.py — O que conferir antes de publicar o site de um cliente.

Roda sobre a versão para publicar (o que vai ao ar) e sobre o site.json. Cada item diz o
problema em linguagem simples e onde resolver no editor. Níveis:
    erro   impede publicar (quebra o site ou engana o Google)
    aviso  publica, mas perde força no Google ou nas IAs
    ok     conferido
"""

import re
from pathlib import Path

from radar import auditoria
from radar.pagina import sinais
from site_cliente import gerador

ROBOS_ESSENCIAIS = ("GPTBot", "OAI-SearchBot", "ClaudeBot", "PerplexityBot")


def _item(nivel, area, mensagem, resolver="", pagina=""):
    return {"nivel": nivel, "area": area, "mensagem": mensagem, "resolver": resolver, "pagina": pagina}


def _rotulo(arquivo: Path, raiz: Path) -> str:
    rel = arquivo.relative_to(raiz).as_posix()
    return "/" + rel.removesuffix("index.html")


def _links_internos(html: str, arquivo: Path, raiz: Path) -> list[str]:
    quebrados = []
    for href in re.findall(r'href="([^"]+)"', html):
        if href.startswith(("http://", "https://", "mailto:", "tel:", "#", "//")):
            continue
        caminho = href.split("#")[0].split("?")[0]
        if not caminho:
            continue
        alvo = (raiz / caminho.lstrip("/")) if caminho.startswith("/") else (arquivo.parent / caminho)
        alvo = alvo.resolve()
        if alvo.is_dir():
            alvo = alvo / "index.html"
        if not alvo.exists():
            quebrados.append(href)
    return quebrados


def checar(cid: str, pasta: Path | None = None) -> dict:
    s, _ = gerador.carregar(cid)
    pasta = pasta or gerador.gerar(cid, previa=False)
    itens = []
    e = s["empresa"]

    # identidade: o que prova para as IAs qual empresa é esta
    faltam = [r for k, r in (("cnpj", "CNPJ"), ("razao_social", "razão social"), ("endereco", "endereço"), ("email", "e-mail")) if not e.get(k)]
    perfis = [u for u in (e.get("perfis") or {}).values() if u]
    if faltam:
        itens.append(_item("aviso", "Identidade", f"Faltam {', '.join(faltam)} da empresa.",
                           "Configurações → Dados oficiais. Sem eles as IAs confundem a marca com empresas de nome parecido."))
    else:
        itens.append(_item("ok", "Identidade", "CNPJ, razão social, endereço e e-mail preenchidos."))
    if not perfis:
        itens.append(_item("aviso", "Identidade", "Nenhum perfil oficial (Instagram, LinkedIn, Perfil no Google) ligado ao site.",
                           "Configurações → Perfis oficiais. Eles entram na ficha da empresa (sameAs)."))
    else:
        itens.append(_item("ok", "Identidade", f"{len(perfis)} perfil(is) oficial(is) ligado(s) ao site."))

    tipos = {p["tipo"] for p in s["paginas"]}
    if "sobre" not in tipos:
        itens.append(_item("aviso", "Estrutura", "Não há página Sobre.", "Páginas → Adicionar página → Sobre a empresa."))
    if "servico" not in tipos:
        itens.append(_item("aviso", "Estrutura", "Não há página de serviço com a cidade (ex.: “tráfego pago em Belo Horizonte”).",
                           "Páginas → Adicionar página → Serviço e cidade. É o que a IA encontra em buscas locais."))

    # robots e sitemap da versão para publicar
    regras = auditoria.regras_robots((pasta / "robots.txt").read_text(encoding="utf-8"))
    bloqueados = [r for r in ROBOS_ESSENCIAIS if not auditoria.permite(regras, r, "/")] + \
                 (["todos"] if not auditoria.permite(regras, "*", "/") else [])
    itens.append(_item("erro", "Robôs", f"robots.txt bloqueia {', '.join(bloqueados)}.", "Gerar de novo a versão para publicar.")
                 if bloqueados else _item("ok", "Robôs", "Robôs de busca e de IA liberados no robots.txt."))
    sitemap = (pasta / "sitemap.xml").read_text(encoding="utf-8")
    no_sitemap = set(re.findall(r"<loc>([^<]+)</loc>", sitemap))

    paginas_html = sorted(pasta.rglob("index.html"))
    for f in paginas_html:
        html = f.read_text(encoding="utf-8")
        rot = _rotulo(f, pasta)
        sn = sinais(html, s["dominio"].rstrip("/") + rot)
        titulo, desc, h1, canon = sn["titulo"], sn["descricao"], sn["h1"], sn["canonical"]
        if not titulo:
            itens.append(_item("erro", "Google", "Página sem título.", "Edite o título para o Google da página.", rot))
        elif len(titulo) > 60:
            itens.append(_item("aviso", "Google", f"Título com {len(titulo)} caracteres; o Google corta depois de uns 60.",
                               "Encurte o título para o Google, com o serviço e a cidade no começo.", rot))
        if not desc:
            itens.append(_item("erro", "Google", "Página sem descrição.", "Escreva a descrição para o Google.", rot))
        elif not 70 <= len(desc) <= 160:
            itens.append(_item("aviso", "Google", f"Descrição com {len(desc)} caracteres (ideal entre 70 e 160).",
                               "Ajuste a descrição para o Google.", rot))
        if h1 != 1:
            itens.append(_item("erro" if h1 == 0 else "aviso", "Estrutura", f"A página tem {h1} títulos principais (H1); o certo é 1.",
                               "Use um bloco Abertura ou Cabeçalho de página, e só um.", rot))
        if canon and canon not in no_sitemap and not rot.startswith("/404"):
            itens.append(_item("aviso", "Google", "Página fora do sitemap.", "Gerar de novo a versão para publicar.", rot))
        if sn["jsonld_invalido"]:
            itens.append(_item("erro", "Fichas", "Ficha para Google e IAs (JSON-LD) inválida.", "Avise a TimeLabs: é erro do gerador.", rot))
        palavras = sn["palavras"]
        if "/blog/" not in rot and rot not in ("/",) and palavras < 300:
            itens.append(_item("aviso", "Conteúdo", f"Página com só {palavras} palavras.",
                               "Acrescente um bloco Texto respondendo o que o cliente pergunta. Páginas curtas raramente são citadas.", rot))
        quebrados = _links_internos(html, f, pasta)
        if quebrados:
            itens.append(_item("erro", "Links", f"{len(quebrados)} link(s) interno(s) quebrado(s): {', '.join(quebrados[:3])}.",
                               "Confira os botões e o menu desta página.", rot))

    pesadas = [(p.name, p.stat().st_size // 1024) for p in (pasta / "assets").iterdir() if p.stat().st_size > 400_000]
    if pesadas:
        itens.append(_item("aviso", "Velocidade", "Imagens pesadas: " + ", ".join(f"{n} ({k} KB)" for n, k in pesadas) + ".",
                           "Troque por versões menores ou em WebP."))
    else:
        itens.append(_item("ok", "Velocidade", "Todas as imagens com menos de 400 KB."))

    artigos = list((pasta / "blog").glob("*/index.html")) if (pasta / "blog").exists() else []
    if len(artigos) < 3:
        itens.append(_item("aviso", "Conteúdo", f"O blog tem {len(artigos)} artigo(s) publicado(s).",
                           "Aprove artigos em Conteúdo; o blog ganha força com publicação constante."))
    else:
        itens.append(_item("ok", "Conteúdo", f"Blog com {len(artigos)} artigos."))

    n = {"erro": 0, "aviso": 0, "ok": 0}
    for i in itens:
        n[i["nivel"]] += 1
    ordem = {"erro": 0, "aviso": 1, "ok": 2}
    itens.sort(key=lambda i: (ordem[i["nivel"]], i["area"], i["pagina"]))
    return {"itens": itens, "contagem": n, "pode_publicar": n["erro"] == 0, "paginas": len(paginas_html)}
