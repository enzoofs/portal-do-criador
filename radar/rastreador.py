"""
radar/rastreador.py — O site do cliente página por página, como um robô de IA o encontra.

A auditoria (radar/auditoria.py) testa a página inicial. Aqui vai o site inteiro: começa pela
página inicial e pelo sitemap, segue os links internos e anota de cada página o que um robô
encontra sem executar JavaScript: status, redirecionamentos, noindex, título, descrição, texto,
fichas JSON-LD e links. Sem IA e sem API paga, então roda junto com cada radar e sozinho, depois
de cada correção.

Educação com o site: respeita o robots.txt (grupo "*"), espera entre um pedido e outro, para se o
servidor começar a recusar e não sai do domínio do cliente. Endereços com "?" ficam de fora
(filtros e buscas geram páginas sem fim). Guarda só os sinais de cada página, nunca o HTML.

    python main.py rastrear <cliente> [--limite 300] [--demo]
"""

import json
import re
import time
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
from html import unescape
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlencode, urljoin, urlsplit, urlunsplit

import rede
from config import settings
from radar import auditoria
from radar.analise import ROBOS_DE_BUSCA, url_canonica
from radar.pagina import sinais

PASTA = settings.RASTREIO_DIR
POUCO_TEXTO = 150          # palavras no HTML: abaixo disso a IA tem pouco o que citar
QUASE_VAZIA = 50           # abaixo disso, com raiz de app JavaScript, a página está vazia para o robô
MAX_FALHAS_SEGUIDAS = 10
MAX_BYTES = 5_000_000
MAX_SITEMAPS = 10
NOSSO_ROBO = "PortalDoCriador"   # não aparece em robots.txt: vale o grupo "*"
UA_GPTBOT = next(ua for nome, _, ua in auditoria.ROBOS if nome == "GPTBot")
ARQUIVO = re.compile(r"\.(jpe?g|png|gif|webp|avif|svg|ico|pdf|zip|rar|mp[34]|webm|mov|css|js|json|xml|txt"
                     r"|docx?|xlsx?|pptx?|woff2?|ttf|eot)$", re.I)
# Campos de radar/pagina.sinais guardados de cada página
CAMPOS = ("titulo", "descricao", "canonical", "h1", "h1_texto", "palavras", "inicio", "jsonld_tipos",
          "jsonld_invalido", "tem_preco", "tem_faq")


@dataclass
class Baixado:
    """O que o rastreador usa de uma resposta HTTP (da internet, do disco ou de um teste)."""
    status: int
    url: str                        # endereço final, depois dos redirecionamentos
    texto: str = ""
    tipo: str = "text/html"
    cabecalhos: dict = field(default_factory=dict)   # nomes em minúsculas


def _baixar_web(url: str, ua: str, cadeia: list) -> Baixado | None:
    r = rede.baixar(url, {"User-Agent": ua}, timeout=20, cadeia=cadeia, max_bytes=MAX_BYTES)
    if r is None:
        return None
    tipo = r.headers.get("Content-Type", "")
    if "charset" not in tipo.lower():
        r.encoding = "utf-8"    # sem charset, o requests supõe latin-1 e estraga os acentos
    texto = r.text if re.search(r"html|xml|text", tipo, re.I) else ""
    return Baixado(r.status_code, r.url, texto, tipo, {k.lower(): v for k, v in r.headers.items()})


def baixar_local(pasta: Path, site: str):
    """Um site gerado (entregas/<id>/site-publicar) servido como se estivesse no ar.
    Para o modo demonstração e para os testes: nada sai da máquina."""
    pasta, host = pasta.resolve(), urlsplit(site).netloc.lower()

    def baixar(url: str, ua: str, cadeia: list) -> Baixado | None:
        partes = urlsplit(url)
        if partes.netloc.lower() != host:
            return None
        alvo = (pasta / unquote(partes.path).lstrip("/")).resolve()
        if alvo.is_dir() and alvo.is_relative_to(pasta):
            if not partes.path.endswith("/"):        # como um servidor de verdade: /sobre -> /sobre/
                cadeia.append((301, url))
                return baixar(f"{partes.scheme}://{partes.netloc}{partes.path}/", ua, cadeia)
            alvo = alvo / "index.html"
        if not alvo.is_file() or not alvo.is_relative_to(pasta):
            erro = pasta / "404.html"
            return Baixado(404, url, erro.read_text(encoding="utf-8") if erro.exists() else "")
        tipo = {".html": "text/html", ".xml": "application/xml", ".txt": "text/plain"}.get(alvo.suffix, "")
        return Baixado(200, url, alvo.read_text(encoding="utf-8") if tipo else "", tipo or "application/octet-stream")
    return baixar


# --------------------------------------------------------------------------
# Endereços
# --------------------------------------------------------------------------

def chave(url: str) -> str:
    """Mesma página, mesma chave: sem http/https, sem www, sem utm_*, âncora e barra final.
    É como o radar e o rastreamento se encontram (a IA cita com utm_source e sem a barra)."""
    p = urlsplit(url_canonica(url))
    return p.netloc.removeprefix("www.") + p.path + (f"?{p.query}" if p.query else "")


def hosts_do_cliente(cliente: dict) -> set[str]:
    hosts = {urlsplit(cliente["site"]).netloc} | set(cliente.get("dominios") or [])
    return {h.lower().split(":")[0].removeprefix("www.") for h in hosts if h}


def e_interna(url: str, hosts: set[str]) -> bool:
    host = urlsplit(url).netloc.lower().split(":")[0].removeprefix("www.")
    return any(host == h or host.endswith("." + h) for h in hosts)


def _rastreavel(url: str) -> bool:
    p = urlsplit(url_canonica(url))
    return not p.query and not ARQUIVO.search(p.path)


def sem_utm(url: str) -> str:
    """O endereço como a IA citou, sem os utm_* que ela acrescenta e sem âncora."""
    p = urlsplit(url)
    query = urlencode([(k, v) for k, v in parse_qsl(p.query) if not k.lower().startswith("utm_")])
    return urlunsplit((p.scheme, p.netloc, p.path or "/", query, ""))


# --------------------------------------------------------------------------
# Rastreamento
# --------------------------------------------------------------------------

def _ler_sitemaps(texto_robots: str, site: str, baixar, hosts: set[str]) -> tuple[list[str], bool]:
    """URLs do site listadas nos sitemaps (inclusive índice de sitemaps) e se algum foi lido."""
    fila = re.findall(r"(?im)^\s*sitemap:\s*(\S+)", texto_robots) or \
        [urljoin(site, n) for n in ("/sitemap.xml", "/sitemap_index.xml", "/wp-sitemap.xml")]
    lidos, urls, algum = set(), [], False
    while fila and len(lidos) < MAX_SITEMAPS:
        u = fila.pop(0)
        if u in lidos:
            continue
        lidos.add(u)
        r = baixar(u, auditoria.NAVEGADOR, [])
        if r is None or r.status != 200 or "<loc" not in r.texto.lower():
            continue
        algum = True
        locs = [unescape(x.strip()) for x in re.findall(r"<loc>(.*?)</loc>", r.texto, re.S | re.I)]
        if re.search(r"<sitemapindex", r.texto, re.I):
            fila += locs
        else:
            urls += [x for x in locs if e_interna(x, hosts)]
    return list(dict.fromkeys(urls)), algum


def _registro(url: str, profundidade: int | None, origem: str, no_sitemap: set[str]) -> dict:
    return {"url": url, "chave": chave(url), "origem": origem, "profundidade": profundidade,
            "no_sitemap": chave(url) in no_sitemap}


@dataclass
class _Contexto:
    """O que toda visita precisa: como baixar, as regras do robots.txt e o que já foi visto."""
    baixar: Callable
    regras: dict
    hosts: set
    no_sitemap: set
    pausa: float
    paginas: dict = field(default_factory=dict)     # chave -> registro
    vistos: set = field(default_factory=set)


def _ler(ctx: _Contexto, reg: dict, r: Baixado) -> list[str]:
    """Preenche o registro com o que a resposta mostra; devolve os links internos a seguir."""
    reg["status"] = r.status
    reg["tipo"] = r.tipo.split(";")[0].strip().lower()
    reg["bloqueada_para"] = [robo for robo, _, _ in auditoria.ROBOS
                             if not auditoria.permite(ctx.regras, robo, auditoria.caminho_de(r.url))]
    if r.status != 200 or "html" not in reg["tipo"]:
        return []
    s = sinais(r.texto, r.url)
    reg["js"] = s["raiz_js"]
    if s["palavras"] < POUCO_TEXTO:
        # há sites que entregam o HTML pronto só para robôs: se o GPTBot recebe mais texto,
        # é essa a versão que as IAs leem, e é ela que vale
        r2 = ctx.baixar(r.url, UA_GPTBOT, [])
        if ctx.pausa:
            time.sleep(ctx.pausa)
        if r2 is not None and r2.status == 200 and "html" in r2.tipo.lower():
            s2 = sinais(r2.texto, r2.url)
            if s2["palavras"] > s["palavras"]:
                reg["palavras_navegador"], s = s["palavras"], s2
    reg.update({k: s[k] for k in CAMPOS})
    diretivas = set(re.split(r"[\s,:]+", s["robots"] + " " + r.cabecalhos.get("x-robots-tag", "").lower()))
    reg["noindex"] = bool(diretivas & {"noindex", "none"})
    internos = [u for u in s["links"] if e_interna(u, ctx.hosts)]
    reg["links"] = list(dict.fromkeys(chave(u) for u in internos if not ARQUIVO.search(urlsplit(u).path)))
    return [u for u in internos if _rastreavel(u)]


def _visitar(ctx: _Contexto, url: str, prof: int | None, origem: str) -> tuple[list[str], bool]:
    """Baixa e registra uma página (e o destino, se ela redirecionar para outra). Devolve os links a
    seguir e se o servidor falhou ou recusou o pedido."""
    k = chave(url)
    ctx.vistos.add(k)
    reg = ctx.paginas[k] = _registro(url, prof, origem, ctx.no_sitemap)
    if not auditoria.permite(ctx.regras, NOSSO_ROBO, auditoria.caminho_de(url)):
        reg.update(status=None, nao_rastreada=True, erro="o robots.txt pede para não rastrear")
        return [], False
    cadeia: list = []
    r = ctx.baixar(url, auditoria.NAVEGADOR, cadeia)
    if ctx.pausa:
        time.sleep(ctx.pausa)
    reg["cadeia"] = [[s, u] for s, u in cadeia]
    falhou = r is None or r.status in (403, 429) or r.status >= 500
    if r is None:
        reg.update(status=None, erro=f"redirecionamentos demais ({len(cadeia)})"
                   if len(cadeia) > rede.MAX_REDIRECIONAMENTOS else "sem resposta")
        return [], falhou
    if cadeia and chave(r.url) != k:
        # redirecionou para outra página: o endereço vira um registro de redirecionamento
        # e o destino, se for do site e ainda não visto, vira a página lida
        reg.update(status=cadeia[0][0], destino=r.url)
        kd = chave(r.url)
        if not e_interna(r.url, ctx.hosts) or kd in ctx.vistos:
            return [], falhou
        ctx.vistos.add(kd)
        reg = ctx.paginas[kd] = _registro(r.url, prof, origem, ctx.no_sitemap)
    return _ler(ctx, reg, r), falhou


def _baixador(cliente: dict, demo: bool, baixar, pausa: float | None) -> tuple[Callable, float]:
    if baixar is None and demo:
        pasta = settings.BASE_DIR / "entregas" / cliente["id"] / "site-publicar"
        if not (pasta / "index.html").exists():
            raise RuntimeError(f"Sem site gerado para a demonstração. Rode: python main.py site {cliente['id']} --publicar")
        return baixar_local(pasta, cliente["site"]), 0
    return baixar or _baixar_web, settings.RASTREIO_PAUSA if pausa is None else pausa


def _robots(baixar, site: str) -> str:
    r = baixar(urljoin(site, "/robots.txt"), auditoria.NAVEGADOR, [])
    return r.texto if r is not None and r.status == 200 else ""


def rastrear(cliente: dict, limite: int | None = None, demo: bool = False, baixar=None, progresso=print,
             pausa: float | None = None, extras: list[str] | None = None) -> dict:
    """Percorre o site do cliente e devolve o rastreamento (para salvar com `salvar`).
    `extras`: endereços para conferir mesmo sem link até eles (as páginas que as IAs citaram)."""
    limite = limite or settings.RASTREIO_LIMITE
    baixar, pausa = _baixador(cliente, demo, baixar, pausa)
    t0 = time.monotonic()
    site = cliente["site"].rstrip("/") + "/"
    hosts = hosts_do_cliente(cliente)
    progresso(f"Rastreando {site} (até {limite} páginas)")

    texto_robots = _robots(baixar, site)
    do_sitemap, sitemap_lido = _ler_sitemaps(texto_robots, site, baixar, hosts)
    ctx = _Contexto(baixar, auditoria.regras_robots(texto_robots), hosts, {chave(u) for u in do_sitemap}, pausa)

    fila = deque([(site, 0, "inicio")])                                    # links, por camadas
    reserva = deque([(sem_utm(u), None, "citada") for u in extras or [] if e_interna(u, hosts) and _rastreavel(u)]
                    + [(u, None, "sitemap") for u in do_sitemap if _rastreavel(u)])
    links_completos, parou, interrompido, falhas = False, False, None, 0
    while fila or reserva:
        if not fila:
            links_completos = True
        url, prof, origem = (fila or reserva).popleft()
        if chave(url) in ctx.vistos:
            continue
        if len(ctx.paginas) >= limite:
            parou = True
            break
        novos, falhou = _visitar(ctx, url, prof, origem)
        fila.extend((u, (prof or 0) + 1, "link") for u in novos)
        falhas = falhas + 1 if falhou else 0
        if len(ctx.paginas) % 10 == 0:
            progresso(f"  [{len(ctx.paginas)}/{limite}] {auditoria.caminho_de(url)}")
        if falhas >= MAX_FALHAS_SEGUIDAS:
            interrompido = (f"O site parou de responder ou passou a recusar os pedidos depois de {len(ctx.paginas)} "
                            "páginas (erro 403, 429 ou 5xx em sequência).")
            progresso(interrompido)
            break
    else:
        links_completos = True

    rastreio = {
        "cliente_id": cliente["id"], "site": site, "demo": demo,
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "limite": limite, "parou_no_limite": parou,
        "links_completos": links_completos, "interrompido": interrompido,
        "duracao_s": round(time.monotonic() - t0, 1),
        "robots_encontrado": bool(texto_robots),
        "sitemap": {"lido": sitemap_lido, "urls": len(do_sitemap)},
        "paginas": list(ctx.paginas.values()),
    }
    res = resumo(rastreio)
    progresso(f"Rastreamento: {res['lidas']} páginas lidas · {res['erros']} problemas graves · {res['avisos']} avisos")
    return rastreio


def ler_externas(urls: list[str], baixar=None, pausa: float | None = None, maximo: int = 10) -> list[dict]:
    """Páginas de outros sites (as de concorrentes que as IAs citaram): uma leitura de cada, como um
    visitante, respeitando o robots.txt de cada site. Guarda só os sinais, para comparar."""
    baixar = baixar or _baixar_web
    pausa = settings.RASTREIO_PAUSA if pausa is None else pausa
    regras: dict[str, dict] = {}
    saida = []
    for url in list(dict.fromkeys(sem_utm(u) for u in urls))[:maximo]:
        partes = urlsplit(url)
        host = partes.netloc.lower()
        if host not in regras:
            regras[host] = auditoria.regras_robots(_robots(baixar, f"{partes.scheme}://{host}/"))
        item = {"url": url, "chave": chave(url), "dominio": host.removeprefix("www.")}
        if not auditoria.permite(regras[host], NOSSO_ROBO, auditoria.caminho_de(url)):
            item["erro"] = "o robots.txt do site pede para não rastrear"
        else:
            r = baixar(url, auditoria.NAVEGADOR, [])
            if pausa:
                time.sleep(pausa)
            if r is None or r.status != 200 or "html" not in r.tipo.lower():
                item["erro"] = f"HTTP {r.status}" if r is not None else "sem resposta"
            else:
                s = sinais(r.texto, r.url)
                item.update({k: s[k] for k in CAMPOS})
        saida.append(item)
    return saida


def complementar(cliente: dict, rastreio: dict, urls: list[str], demo: bool = False, baixar=None,
                 pausa: float | None = None, maximo: int = 20) -> int:
    """Confere endereços que o rastreamento não leu (as páginas que as IAs citaram neste radar e que
    nenhum link do site alcança). Altera o rastreio e devolve quantas páginas entraram."""
    hosts = hosts_do_cliente(cliente)
    paginas = {p["chave"]: p for p in rastreio["paginas"]}
    faltam = list(dict.fromkeys(sem_utm(u) for u in urls if e_interna(u, hosts) and chave(u) not in paginas))[:maximo]
    if not faltam:
        return 0
    baixar, pausa = _baixador(cliente, demo, baixar, pausa)
    no_sitemap = {k for k, p in paginas.items() if p["no_sitemap"]}
    ctx = _Contexto(baixar, auditoria.regras_robots(_robots(baixar, rastreio["site"])), hosts, no_sitemap, pausa,
                    paginas=paginas, vistos=set(paginas))
    for url in faltam:
        if chave(url) not in ctx.vistos:
            _visitar(ctx, url, None, "citada")
    antes = len(rastreio["paginas"])
    rastreio["paginas"] = list(ctx.paginas.values())
    return len(rastreio["paginas"]) - antes


# --------------------------------------------------------------------------
# Problemas encontrados (calculados na leitura: mudança nas regras vale para rastreios antigos)
# --------------------------------------------------------------------------

def lidas(rastreio: dict) -> list[dict]:
    """Páginas HTML que abriram e foram lidas."""
    return [p for p in rastreio["paginas"] if p.get("status") == 200 and "palavras" in p]


def quebrada(p: dict) -> bool:
    return (p.get("status") is None and not p.get("nao_rastreada")) or (p.get("status") or 0) >= 400


def indexavel(p: dict) -> bool:
    return "palavras" in p and not p.get("noindex") and (not p.get("canonical") or chave(p["canonical"]) == p["chave"])


def so_javascript(p: dict) -> bool:
    return p["palavras"] < QUASE_VAZIA and bool(p.get("js"))


def _caminho(url: str) -> str:
    return auditoria.caminho_de(url)


def _problema(codigo, nivel, titulo, detalhe, resolver, paginas) -> dict:
    return {"codigo": codigo, "nivel": nivel, "titulo": titulo, "detalhe": detalhe, "resolver": resolver,
            "paginas": paginas, "total": len(paginas)}


def _repetidos(paginas: list[dict], campo: str) -> list[dict]:
    grupos = defaultdict(list)
    for p in paginas:
        if p.get(campo):
            grupos[p[campo].strip().lower()].append(p)
    return [{"url": p["url"], "nota": f"“{g[0][campo][:90]}” em {len(g)} páginas"}
            for g in grupos.values() if len(g) > 1 for p in g]


def entradas(rastreio: dict) -> dict[str, list[str]]:
    """Chave da página -> URLs das páginas que linkam para ela."""
    origens = defaultdict(list)
    for p in lidas(rastreio):
        for k in p.get("links", []):
            if k != p["chave"]:
                origens[k].append(p["url"])
    return origens


def problemas(rastreio: dict) -> list[dict]:
    todas, ok = rastreio["paginas"], lidas(rastreio)
    indexaveis = [p for p in ok if indexavel(p)]
    origens = entradas(rastreio)
    # robô bloqueado em todas as páginas é bloqueio do site inteiro: a auditoria do radar já aponta
    bloqueio_geral = set.intersection(*(set(p.get("bloqueada_para", [])) for p in ok)) if ok else set()
    lista = []

    if rastreio.get("interrompido"):
        lista.append(_problema(
            "interrompido", "erro", "O site passou a recusar o rastreamento", rastreio["interrompido"],
            "Conferir o firewall, o Cloudflare ou o plugin de segurança: se barram um rastreador educado, "
            "provavelmente barram os robôs das IAs também.", []))

    # quebrada só no sitemap fica em "sitemap com erro": aqui, as que o site linka (e a inicial)
    q = [{"url": p["url"], "nota": (f"HTTP {p['status']}" if p.get("status") else p.get("erro", "sem resposta"))
          + (f" · linkada em {_caminho(origens[p['chave']][0])}" if origens.get(p["chave"]) else "")}
         for p in todas if quebrada(p) and (p["origem"] != "sitemap" or origens.get(p["chave"]))]
    if q:
        lista.append(_problema(
            "quebrada", "erro", "Páginas que não abrem",
            f"{len(q)} endereço(s) do site respondem com erro. Quem chega por um link, pelo Google ou pela "
            "indicação de uma IA encontra uma página de erro.",
            "Restaurar a página ou redirecionar (301) o endereço para a página nova mais parecida, e corrigir "
            "os links que apontam para ela.", q))

    bloq = []
    for p in todas:
        extra = [b for b in p.get("bloqueada_para", []) if b not in bloqueio_geral]
        if extra:
            bloq.append({"url": p["url"], "nota": "bloqueada para " + ", ".join(extra), "_busca": bool(set(extra) & set(ROBOS_DE_BUSCA))})
    if bloq:
        lista.append(_problema(
            "bloqueada_para_ias", "erro" if any(b["_busca"] for b in bloq) else "aviso",
            "Páginas bloqueadas para robôs de IA",
            "O robots.txt proíbe robôs de IA de abrir estas páginas. As de busca (ChatGPT, Claude, Perplexity, "
            "Google, Bing) não conseguem citá-las.",
            "Tirar do robots.txt as linhas “Disallow” que cobrem estas páginas.",
            [{k: v for k, v in b.items() if k != "_busca"} for b in bloq]))

    ni = [p for p in ok if p.get("noindex")]
    if ni:
        importante = any(p["no_sitemap"] or (p["profundidade"] is not None and p["profundidade"] <= 1) for p in ni)
        lista.append(_problema(
            "noindex", "erro" if importante else "aviso", "Páginas marcadas para não aparecer na busca (noindex)",
            "Com noindex, Google e Bing tiram a página da busca, e as IAs que pesquisam por eles deixam de achá-la.",
            "No plugin de SEO, desmarcar “não indexar” nestas páginas. Se alguma não deve mesmo aparecer, tirar "
            "do sitemap e do menu.",
            [{"url": p["url"], "nota": "noindex" + (" · está no sitemap" if p["no_sitemap"] else "")} for p in ni]))

    js = [p for p in ok if so_javascript(p)]
    if js:
        lista.append(_problema(
            "texto_so_com_javascript", "erro", "Páginas que só mostram o texto depois do JavaScript",
            "No HTML que o robô baixa, estas páginas estão quase vazias: o texto é montado no navegador. "
            "Robôs de IA não executam JavaScript e veem a página em branco.",
            "Ativar a renderização no servidor (SSR) ou a geração estática no construtor do site, ou um serviço "
            "de pré-renderização para robôs.",
            [{"url": p["url"], "nota": f"{p['palavras']} palavras no HTML"} for p in js]))

    pouco = [p for p in indexaveis if p["palavras"] < POUCO_TEXTO and not so_javascript(p)]
    if pouco:
        lista.append(_problema(
            "pouco_texto", "aviso", "Páginas com pouco texto",
            f"Menos de {POUCO_TEXTO} palavras no HTML: a IA tem pouco o que citar destas páginas.",
            "Acrescentar o que o cliente pergunta: o que é o serviço, para quem, como funciona, preço, prazo e "
            "perguntas frequentes.",
            [{"url": p["url"], "nota": f"{p['palavras']} palavras"} for p in pouco]))

    fi = [p for p in ok if p.get("jsonld_invalido")]
    if fi:
        lista.append(_problema(
            "ficha_invalida", "erro", "Fichas para Google e IAs (JSON-LD) com erro",
            "O código da ficha tem erro de sintaxe: Google e IAs descartam a ficha inteira.",
            "Validar no teste de pesquisa aprimorada do Google e corrigir o código.",
            [{"url": p["url"], "nota": "JSON-LD inválido"} for p in fi]))

    st = [p for p in indexaveis if not p["titulo"]]
    if st:
        lista.append(_problema("sem_titulo", "erro", "Páginas sem título",
                               "Sem título, o Google inventa um e a IA não sabe do que a página trata.",
                               "Escrever um título com o serviço e a cidade, de até 60 caracteres.",
                               [{"url": p["url"], "nota": "sem <title>"} for p in st]))

    cad = [p for p in todas if len(p.get("cadeia", [])) >= 2]
    if cad:
        lista.append(_problema(
            "cadeia_redirecionamento", "aviso", "Redirecionamentos em cadeia",
            "O endereço passa por vários redirecionamentos até chegar à página. Robôs desistem no meio do caminho.",
            "Apontar o endereço antigo direto para o destino final (um redirecionamento só).",
            [{"url": p["url"], "nota": " → ".join(_caminho(u) for _, u in p["cadeia"]) + " → "
              + _caminho(p.get("destino") or p["url"])} for p in cad]))

    redir = [{"url": o, "nota": f"linka {_caminho(p['url'])}, que redireciona para {_caminho(p['destino'])}"}
             for p in todas if p.get("destino") for o in origens.get(p["chave"], [])]
    if redir:
        lista.append(_problema("link_para_redirecionamento", "aviso", "Links internos que passam por redirecionamento",
                               "Cada redirecionamento é um passo a mais para o robô e um sinal de endereço antigo.",
                               "Trocar o link pelo endereço final.", redir))

    can = [p for p in ok if p.get("canonical") and chave(p["canonical"]) != p["chave"] and not p.get("noindex")]
    if can:
        lista.append(_problema(
            "canonical_outra", "aviso", "Páginas que indicam outra como a versão oficial (canonical)",
            "Google e IAs tendem a mostrar a outra página no lugar desta.",
            "Se a página deve aparecer, o canonical dela tem que apontar para ela mesma.",
            [{"url": p["url"], "nota": "canonical: " + p["canonical"]} for p in can]))

    for codigo, campo, titulo in (("titulo_repetido", "titulo", "Títulos repetidos em páginas diferentes"),
                                  ("descricao_repetida", "descricao", "Descrições repetidas em páginas diferentes")):
        rep = _repetidos(indexaveis, campo)
        if rep:
            lista.append(_problema(codigo, "aviso", titulo,
                                   "O Google e as IAs não conseguem distinguir as páginas pelo que elas dizem de si.",
                                   f"Escrever {'um título' if campo == 'titulo' else 'uma descrição'} próprio para cada página.", rep))

    sd = [p for p in indexaveis if not p["descricao"]]
    if sd:
        lista.append(_problema("sem_descricao", "aviso", "Páginas sem descrição",
                               "Sem descrição, o Google monta o resumo com trechos soltos da página.",
                               "Escrever uma descrição de 70 a 160 caracteres para cada página.",
                               [{"url": p["url"], "nota": "sem meta description"} for p in sd]))

    h1 = [p for p in indexaveis if p["h1"] != 1]
    if h1:
        lista.append(_problema("h1", "aviso", "Páginas sem um título principal (H1) único",
                               "O H1 diz ao robô qual é o assunto da página; nenhum ou vários confundem.",
                               "Deixar um H1 por página, com o serviço e a cidade.",
                               [{"url": p["url"], "nota": f"{p['h1']} H1"} for p in h1]))

    if rastreio.get("links_completos"):
        orf = [p for p in indexaveis if p["origem"] in ("sitemap", "citada") and not origens.get(p["chave"])]
        if orf:
            lista.append(_problema("orfa", "aviso", "Páginas sem nenhum link no site (órfãs)",
                                   "Existem (estão no sitemap ou as IAs citaram), mas nenhuma página do site leva até "
                                   "elas: robôs e visitantes quase não as encontram.",
                                   "Linkar cada uma a partir de uma página relacionada (menu, serviço ou artigo).",
                                   [{"url": p["url"], "nota": "nenhum link interno"} for p in orf]))

    if rastreio["sitemap"]["lido"] and rastreio["sitemap"]["urls"]:
        fora = [p for p in indexaveis if not p["no_sitemap"]]
        if fora:
            lista.append(_problema("fora_do_sitemap", "aviso", "Páginas fora do sitemap",
                                   "O sitemap é a lista que Google e Bing usam para achar páginas novas.",
                                   "Incluir no sitemap (no plugin de SEO, conferir se esse tipo de página está ativado).",
                                   [{"url": p["url"], "nota": "não está no sitemap"} for p in fora]))
        ruins = [{"url": p["url"], "nota": "não abre" if quebrada(p) else "redireciona" if p.get("destino") else "noindex"}
                 for p in todas if p["no_sitemap"] and (quebrada(p) or p.get("destino") or p.get("noindex"))]
        if ruins:
            lista.append(_problema("sitemap_com_erro", "aviso", "Sitemap com endereços que não servem",
                                   "O sitemap manda os buscadores para páginas que não abrem, redirecionam ou pedem "
                                   "para não aparecer.",
                                   "Tirar do sitemap esses endereços (o plugin de SEO costuma fazer isso sozinho "
                                   "quando a página é apagada ou marcada como noindex).", ruins))

    return sorted(lista, key=lambda p: p["nivel"] != "erro")


def comparar(anterior: dict, atual: dict) -> dict:
    """O que mudou entre dois rastreios: problemas resolvidos e novos, por tipo e endereço. Se o
    rastreio atual parou no limite, só conta como resolvido o problema de uma página que ele leu de
    novo (a que ficou de fora não está resolvida, só não foi vista). Num rastreio completo, a página
    que sumiu também conta: nenhum link leva mais a ela."""
    def itens(r: dict) -> dict:
        return {(p["codigo"], chave(x["url"]) if x.get("url") else ""): (p["titulo"], x.get("url", ""))
                for p in problemas(r) for x in (p["paginas"] or [{}])}
    antes, agora = itens(anterior), itens(atual)
    vistas = {p["chave"] for p in atual["paginas"]}
    completo = not atual["parou_no_limite"] and not atual.get("interrompido")
    resolvidos = [k for k in antes.keys() - agora.keys() if completo or not k[1] or k[1] in vistas]
    novos = list(agora.keys() - antes.keys())

    def rotulo(k: tuple, origem: dict) -> dict:
        titulo, url = origem[k]
        return {"codigo": k[0], "url": url, "rotulo": titulo + (f": {_caminho(url)}" if url else "")}
    return {"desde": anterior["gerado_em"], "resolvidos": [rotulo(k, antes) for k in sorted(resolvidos)],
            "novos": [rotulo(k, agora) for k in sorted(novos)]}


def resumo(rastreio: dict) -> dict:
    ok, probs = lidas(rastreio), problemas(rastreio)
    return {"paginas": len(rastreio["paginas"]), "lidas": len(ok),
            "quebradas": sum(quebrada(p) for p in rastreio["paginas"]),
            "pouco_texto": sum(p["palavras"] < POUCO_TEXTO for p in ok),
            "erros": sum(p["nivel"] == "erro" for p in probs), "avisos": sum(p["nivel"] == "aviso" for p in probs),
            "parou_no_limite": rastreio["parou_no_limite"], "limite": rastreio["limite"],
            "interrompido": rastreio.get("interrompido")}


# --------------------------------------------------------------------------
# Arquivos: data/rastreios/<cliente>/<AAAAMMDD-HHMMSS>[-demo].json
# --------------------------------------------------------------------------

def salvar(rastreio: dict) -> Path:
    pasta = PASTA / rastreio["cliente_id"]
    pasta.mkdir(parents=True, exist_ok=True)
    carimbo = datetime.fromisoformat(rastreio["gerado_em"]).strftime("%Y%m%d-%H%M%S")
    caminho = pasta / f"{carimbo}{'-demo' if rastreio['demo'] else ''}.json"
    caminho.write_text(json.dumps(rastreio, ensure_ascii=False, indent=1), encoding="utf-8")
    return caminho


@lru_cache(maxsize=16)
def _carregar(caminho: str, _mtime: float) -> dict:
    r = json.loads(Path(caminho).read_text(encoding="utf-8"))
    r["_arquivo"] = Path(caminho).name
    return r


def carregar(caminho: Path) -> dict:
    """Rastreio salvo. O dicionário é compartilhado entre chamadas: só leitura."""
    return _carregar(str(caminho), caminho.stat().st_mtime)


def arquivos(cliente_id: str) -> list[Path]:
    """Rastreios do cliente, do mais antigo ao mais recente: os reais ou, se não houver, os de demonstração."""
    todos = sorted((PASTA / cliente_id).glob("*.json"))
    return [p for p in todos if "-demo" not in p.name] or todos


def ultimo(cliente_id: str) -> dict | None:
    lista = arquivos(cliente_id)
    return carregar(lista[-1]) if lista else None


def do_run(run: dict) -> dict | None:
    """O rastreamento feito junto com este radar (None em radar antigo ou sem rastreamento)."""
    nome = run.get("rastreio")
    if not nome or Path(nome).name != nome:
        return None
    caminho = PASTA / run["cliente"]["id"] / nome
    return carregar(caminho) if caminho.exists() else None


def anterior(cliente_id: str) -> dict | None:
    """O rastreio de antes do último (para ver o que mudou)."""
    lista = arquivos(cliente_id)
    return carregar(lista[-2]) if len(lista) > 1 else None
