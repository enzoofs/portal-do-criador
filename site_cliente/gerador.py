"""
site_cliente/gerador.py — Gera o site completo de um cliente a partir de páginas feitas de blocos.

Entrada: config/sites/<id>/site.json (configurações + páginas com blocos; ver blocos.py) e
config/sites/<id>/assets/, mais os artigos da pauta real mais recente (data/conteudo/<id>/).

Saída, em entregas/<id>/:
    site-novo/      prévia: faixa de aviso, dados faltando tracejados, noindex (o Portal serve esta)
    site-publicar/  versão para o ar: sem marcações; campo vazio simplesmente não aparece

Cada página vira HTML estático com o texto inteiro no próprio arquivo (o que os robôs de IA leem
sem executar JavaScript). As fichas JSON-LD saem dos blocos: um bloco de perguntas gera a ficha
FAQPage da página, a página de serviço gera Service, a Sobre gera AboutPage.

    python main.py site exemplo [--publicar] [--com-pendencias]
"""

import json
import shutil
import time
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from config import settings
from conteudo import fluxo, render
from conteudo import pauta as pauta_mod
from site_cliente import blocos

MODELOS = Path(__file__).parent / "modelos"
FONTES = Path(__file__).parent / "fontes"   # woff2 + licença de cada família do catálogo
SITES = settings.BASE_DIR / "config" / "sites"
ENTREGAS = settings.BASE_DIR / "entregas"
CACHE_IMAGENS = settings.BASE_DIR / "data" / "cache_sites"
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro",
         "outubro", "novembro", "dezembro"]
LARGURA_MAX = 1920
LARGURA_RETRATO = 900  # fotos de pessoa (bloco Sobre o fundador)
ROBOS_IA = ["GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-SearchBot", "Claude-User",
            "PerplexityBot", "Perplexity-User", "Google-Extended", "Applebot-Extended", "bingbot"]


def _rgb(hexa: str) -> str:
    h = hexa.lstrip("#")
    return ",".join(str(int(h[i:i + 2], 16)) for i in (0, 2, 4))


def _cores(c: dict) -> dict:
    c = dict(c)
    c.setdefault("fundo_rodape", c["fundo"])
    for k in ("fundo", "texto", "destaque", "secundaria"):
        c[f"{k}_rgb"] = _rgb(c[k])
    return c


def _data(iso: str) -> str:
    d = datetime.fromisoformat(iso)
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def pasta_site(cid: str) -> Path:
    return SITES / cid


def carregar(cid: str) -> tuple[dict, dict]:
    s = json.loads((SITES / cid / "site.json").read_text(encoding="utf-8"))
    cliente = json.loads((settings.CLIENTES_DIR / f"{cid}.json").read_text(encoding="utf-8"))
    return s, cliente


def assets(cid: str) -> set[str]:
    pasta = SITES / cid / "assets"
    return {p.name for p in pasta.iterdir() if p.is_file()} if pasta.exists() else set()


def _retratos(s: dict) -> set[str]:
    return {b.get("foto") for p in s["paginas"] for b in p["blocos"] if b["tipo"] == "sobre_fundador" and b.get("foto")}


def _copiar_assets(cid: str, s: dict, destino: Path) -> None:
    """Copia as imagens da marca, reduzindo fotos grandes. O resultado fica em cache por arquivo,
    para salvar no editor não reprocessar a foto de 3,6 MB toda vez."""
    from PIL import Image
    destino.mkdir(parents=True, exist_ok=True)
    retratos = _retratos(s)
    cache = CACHE_IMAGENS / cid
    cache.mkdir(parents=True, exist_ok=True)
    for arq in (SITES / cid / "assets").iterdir():
        if not arq.is_file():
            continue
        alvo = destino / arq.name
        if arq.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp") and arq.stat().st_size > 300_000:
            limite = LARGURA_RETRATO if arq.name in retratos else LARGURA_MAX
            chave = cache / f"{arq.stem}-{int(arq.stat().st_mtime)}-{arq.stat().st_size}-{limite}{arq.suffix}"
            if not chave.exists():
                with Image.open(arq) as original:
                    imagem = original.convert("RGB") if arq.suffix.lower() in (".jpg", ".jpeg") else original.copy()
                if imagem.width > limite:
                    imagem = imagem.resize((limite, round(imagem.height * limite / imagem.width)), Image.LANCZOS)
                imagem.save(chave, quality=82, optimize=True)
            shutil.copy(chave, alvo)
        else:
            shutil.copy(arq, alvo)
    shutil.copy(MODELOS / "estilo.css", destino / "estilo.css")
    _copiar_fontes(s, destino)


def _copiar_fontes(s: dict, destino: Path) -> None:
    """Fontes servidas pelo próprio site, com assets/fontes.css. Nenhum pedido vai ao Google Fonts:
    o IP de quem visita não sai do domínio do cliente (LGPD) e o carregamento tem uma conexão a menos."""
    catalogo = json.loads((FONTES / "fontes.json").read_text(encoding="utf-8"))["familias"]
    regras = []
    for familia in dict.fromkeys(s["marca"]["fontes"].values()):   # título e corpo, sem repetir
        info = catalogo[familia]   # blocos.validar só aceita fonte do catálogo
        pasta = destino / "fontes" / info["pasta"]
        pasta.mkdir(parents=True, exist_ok=True)
        shutil.copy(FONTES / info["pasta"] / "LICENSE.txt", pasta / "LICENSE.txt")
        for a in info["arquivos"]:
            shutil.copy(FONTES / info["pasta"] / a["arquivo"], pasta / a["arquivo"])
            regras.append(f"@font-face{{font-family:'{familia}';font-style:normal;font-weight:{a['pesos']};"
                          f"font-display:swap;src:url(fontes/{info['pasta']}/{a['arquivo']}) format('woff2')}}")
    (destino / "fontes.css").write_text("\n".join(regras) + "\n", encoding="utf-8", newline="\n")


def _artigos(cid: str, s: dict, cliente: dict, com_pendencias: bool) -> list[dict]:
    if not (s.get("blog") or {}).get("ativo", True):
        return []
    pasta = pauta_mod.ultima_pauta(cid, incluir_demo=False)
    if not pasta:
        return []
    autor = (cliente.get("perfil") or {}).get("autor") or {}
    saida = []
    for a in fluxo.carregar_artigos(pasta):
        if a.get("demo") or (a["pendencias"] and not com_pendencias):
            continue
        artigo = dict(a, url=f'{s["dominio"]}/blog/{a["slug"]}/')
        html = render.conteudo_post(artigo, {**cliente, "site": s["dominio"] + "/"})
        # dado a confirmar (só com --com-pendencias) aparece marcado, nunca escondido
        html = render.MARCADOR.sub(lambda m: f'<span class="preencher">a confirmar: {m.group(1).partition(":")[2].strip()}</span>', html)
        nicho = (artigo.get("tema") or {}).get("nicho") or ""
        saida.append({**artigo, "html": html, "data": _data(artigo["gerado_em"]),
                      "minutos": max(1, round(artigo["palavras"] / 200)),
                      "tag": nicho if nicho and nicho != "geral" else "Tráfego pago", "autor": autor.get("nome"),
                      "whatsapp": render.link_whatsapp(s["empresa"]["whatsapp"], artigo["titulo"])})
    saida.sort(key=lambda a: (a.get("status") != "aprovado", a["gerado_em"]))
    return saida


# ---------------------------------------------------------------- fichas para Google e IAs

def organizacao(s: dict) -> dict:
    """Ficha da empresa só com o que está confirmado: campo vazio não vira texto de exemplo."""
    e, dom = s["empresa"], s["dominio"]
    org = {"@type": "ProfessionalService", "@id": f"{dom}/#empresa", "name": e["nome"], "url": f"{dom}/",
           "description": e.get("descricao"), "logo": f'{dom}/assets/{s["marca"]["logo"]}',
           "image": f'{dom}/assets/{s["marca"]["imagem_compartilhamento"]}',
           "telephone": "+" + e["whatsapp"],
           "areaServed": [{"@type": "City", "name": e["cidade"]}, {"@type": "Country", "name": "Brasil"}],
           "address": {"@type": "PostalAddress", "addressLocality": e["cidade"], "addressRegion": e["uf"], "addressCountry": "BR"}}
    if e.get("desde"):
        org["foundingDate"] = str(e["desde"])
    f = s.get("fundador") or {}
    if f.get("nome"):
        org["founder"] = {"@type": "Person", "name": f["nome"], "jobTitle": f.get("cargo") or None}
    for chave, campo in (("razao_social", "legalName"), ("cnpj", "taxID"), ("email", "email")):
        if e.get(chave):
            org[campo] = e[chave]
    if e.get("endereco"):
        org["address"]["streetAddress"] = e["endereco"]
    perfis = [u for u in (e.get("perfis") or {}).values() if u]
    if perfis:
        org["sameAs"] = perfis
    return {k: v for k, v in org.items() if v not in (None, "")}


def _trilha(s: dict, itens: list[tuple[str, str]]) -> dict:
    lista = [("Início", f'{s["dominio"]}/'), *itens]
    return {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i, "name": n, "item": u} for i, (n, u) in enumerate(lista, start=1)]}


def _faq(pagina: dict) -> dict | None:
    perguntas = [p for b in pagina["blocos"] if b["tipo"] == "perguntas" for p in b.get("itens", [])]
    if not perguntas:
        return None
    return {"@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": p["pergunta"], "acceptedAnswer": {"@type": "Answer", "text": p["resposta"]}}
        for p in perguntas]}


def _cabecalho(pagina: dict) -> dict:
    return next((b for b in pagina["blocos"] if b["tipo"] in ("cabecalho_pagina", "abertura")), {})


def fichas_da_pagina(s: dict, pagina: dict, url: str) -> list[dict]:
    org, e = organizacao(s), s["empresa"]
    cab = _cabecalho(pagina)
    rotulo = pagina.get("menu") or cab.get("titulo") or pagina["titulo_pagina"]
    tipo = pagina["tipo"]
    if tipo == "inicio":
        blocos_ld = [org, {"@type": "WebSite", "name": e["nome"], "url": url, "inLanguage": s.get("idioma", "pt-BR")}]
    elif tipo == "sobre":
        blocos_ld = [{"@type": "AboutPage", "name": rotulo, "url": url, "about": {"@id": org["@id"]}}, org,
                     _trilha(s, [(rotulo, url)])]
    elif tipo == "servico":
        blocos_ld = [{"@type": "Service", "name": pagina.get("servico_nome") or cab.get("titulo"),
                      "description": cab.get("resumo") or pagina["descricao"], "url": url,
                      "provider": {"@id": org["@id"]}, "areaServed": {"@type": "City", "name": e["cidade"]}},
                     _trilha(s, [(rotulo, url)])]
    else:
        blocos_ld = [_trilha(s, [(rotulo, url)])]
    faq = _faq(pagina)
    if faq:
        blocos_ld.append(faq)
    return [{"@context": "https://schema.org", **b} for b in blocos_ld]


# ---------------------------------------------------------------- geração

def _paragrafos(texto: str) -> list[str]:
    return [p.strip() for p in (texto or "").replace("\r\n", "\n").split("\n\n") if p.strip()]


def gerar(cid: str, previa: bool = True, com_pendencias: bool = False, destino: Path | None = None) -> Path:
    s, cliente = carregar(cid)
    blocos.validar(s, assets(cid))  # site inválido não vira HTML pela metade
    destino = destino or ENTREGAS / cid / ("site-novo" if previa else "site-publicar")
    # Sobrescreve no lugar e depois apaga o que sobrou. Apagar a pasta antes falhava no Windows
    # quando a prévia estava aberta (arquivo em uso não pode ser apagado, mas pode ser reescrito).
    inicio = time.time()
    antes = [p for p in destino.rglob("*") if p.is_file()] if destino.exists() else []
    _copiar_assets(cid, s, destino / "assets")

    dom, e = s["dominio"], s["empresa"]
    artigos = _artigos(cid, s, cliente, com_pendencias)
    paginas = s["paginas"]
    servico = next((p for p in paginas if p["tipo"] == "servico"), None)
    env = Environment(loader=FileSystemLoader(MODELOS), autoescape=select_autoescape(["html"]),
                      trim_blocks=True, lstrip_blocks=True)
    base = {"s": s, "previa": previa, "cores": _cores(s["marca"]["cores"]), "ano": datetime.now().year,
            "link_whatsapp": render.link_whatsapp_texto(e["whatsapp"], e["mensagem_whatsapp"]),
            "tem_blog": bool(artigos), "artigos": artigos, "tem_sobre": any(p["slug"] == "sobre" for p in paginas),
            "paragrafos": _paragrafos,
            "servico_principal": ({"slug": servico["slug"], "titulo": _cabecalho(servico).get("titulo", ""),
                                   "resumo": _cabecalho(servico).get("resumo", "")} if servico else None)}
    mapa: list[str] = []

    def contexto(raiz: str, slug_atual: str | None) -> dict:
        def link_pagina(slug: str) -> str:
            return f"{raiz}{slug}/" if slug else (raiz or "./")
        menu = [{"rotulo": p["menu"], "href": link_pagina(p["slug"]), "atual": p["slug"] == slug_atual}
                for p in paginas if p.get("menu")]
        if artigos:
            menu.append({"rotulo": (s.get("blog") or {}).get("rotulo_menu") or "Blog", "href": f"{raiz}blog/",
                         "atual": slug_atual == "blog"})
        return {"raiz": raiz, "link_pagina": link_pagina, "menu": menu}

    def escrever(modelo: str, caminho: str, raiz: str, slug_atual, pagina: dict, **extra):
        alvo = destino / caminho
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text(env.get_template(modelo).render(**base, **contexto(raiz, slug_atual), pagina=pagina, **extra),
                        encoding="utf-8")

    for p in paginas:
        url = f'{dom}/{p["slug"]}/' if p["slug"] else f"{dom}/"
        raiz = "../" if p["slug"] else ""
        escrever("pagina.html", f'{p["slug"]}/index.html' if p["slug"] else "index.html", raiz, p["slug"],
                 {**p, "titulo": p["titulo_pagina"], "url": url, "jsonld": fichas_da_pagina(s, p, url)})
        mapa.append(url)

    if artigos:
        url = f"{dom}/blog/"
        escrever("blog.html", "blog/index.html", "../", "blog", {
            "titulo": f'{s["blog"]["titulo"]}', "descricao": s["blog"].get("texto") or e["descricao"], "url": url,
            "tipo": "blog", "jsonld": [{"@context": "https://schema.org", "@type": "Blog", "name": s["blog"]["titulo"],
                                        "url": url, "publisher": {"@id": f"{dom}/#empresa"}},
                                       {"@context": "https://schema.org", **_trilha(s, [("Blog", url)])}]})
        mapa.append(url)
        for a in artigos:
            outros = [o for o in artigos if o["slug"] != a["slug"]][:4]
            escrever("post.html", f'blog/{a["slug"]}/index.html', "../../", "blog", {
                "titulo": a["meta_titulo"] or a["titulo"], "descricao": a["meta_descricao"], "url": a["url"],
                "og_tipo": "article", "tipo": "artigo",
                "jsonld": [{"@context": "https://schema.org", **_trilha(s, [("Blog", f"{dom}/blog/"), (a["titulo"], a["url"])])}]},
                a=a, outros=outros)
            mapa.append(a["url"])

    escrever("404.html", "404.html", "/", None, {"titulo": f'Página não encontrada | {e["nome"]}',
                                                 "descricao": e["descricao"], "url": f"{dom}/404", "jsonld": [], "tipo": "erro"})

    hoje = datetime.now().strftime("%Y-%m-%d")
    (destino / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{u}</loc><lastmod>{hoje}</lastmod></url>\n" for u in mapa) + "</urlset>\n",
        encoding="utf-8")
    robos = "User-agent: *\n" + ("Disallow: /\n" if previa else "Allow: /\n")
    if not previa:
        robos += "".join(f"\nUser-agent: {r}\nAllow: /\n" for r in ROBOS_IA)
    (destino / "robots.txt").write_text(robos + f"\nSitemap: {dom}/sitemap.xml\n", encoding="utf-8")
    (destino / "_headers").write_text("/assets/*\n  Cache-Control: public, max-age=31536000, immutable\n", encoding="utf-8")
    _apagar_sobras(destino, antes, inicio)
    return destino


def _apagar_sobras(destino: Path, antes: list[Path], inicio: float) -> None:
    """Apaga arquivos da geração anterior que não foram reescritos (página ou artigo removido).
    Arquivo em uso fica para a próxima geração, em vez de derrubar a atual."""
    for arq in antes:
        try:
            if arq.exists() and arq.stat().st_mtime < inicio - 1:
                arq.unlink()
        except OSError:
            continue
    for pasta in sorted((p for p in destino.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
        try:
            pasta.rmdir()  # só some se estiver vazia
        except OSError:
            continue
