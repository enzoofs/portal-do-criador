"""
radar/auditoria.py — O site do cliente está acessível e legível para as IAs?

Checagens rápidas, sem IA: robôs de busca/treino conseguem baixar a página,
robots.txt, sitemap, dados estruturados e blog. Cada falha vem com
o impacto em linguagem de dono de negócio.
"""

import json
import re
from urllib.parse import unquote, urljoin, urlsplit

import rede

NAVEGADOR = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36"

# (robô, para que serve, user-agent)
ROBOS = [
    ("OAI-SearchBot", "busca do ChatGPT",
     "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; OAI-SearchBot/1.3; +https://openai.com/searchbot"),
    ("ChatGPT-User", "ChatGPT abrindo o link a pedido do usuário",
     "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; ChatGPT-User/1.0; +https://openai.com/bot"),
    ("GPTBot", "treino do ChatGPT",
     "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; GPTBot/1.2; +https://openai.com/gptbot"),
    ("Claude-SearchBot", "busca do Claude",
     "Mozilla/5.0 (compatible; Claude-SearchBot/1.0; +https://www.anthropic.com)"),
    ("ClaudeBot", "treino do Claude",
     "Mozilla/5.0 (compatible; ClaudeBot/1.0; +claudebot@anthropic.com)"),
    ("PerplexityBot", "busca do Perplexity",
     "Mozilla/5.0 (compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot)"),
    ("Googlebot", "Google e Gemini",
     "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"),
    ("bingbot", "Bing (fonte de busca do ChatGPT e Copilot)",
     "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)"),
]


def _get(url: str, ua: str = NAVEGADOR):
    return rede.baixar(url, {"User-Agent": ua}, timeout=20)


# --------------------------------------------------------------------------
# robots.txt pelo padrão (RFC 9309), igual em qualquer versão do Python. O leitor da biblioteca
# padrão muda de comportamento entre versões: até a 3.13 ignora curingas e usa a primeira regra
# que casa, não a mais longa.
# --------------------------------------------------------------------------

def regras_robots(texto: str) -> dict[str, list[tuple[bool, str]]]:
    """Robô (minúsculas, ou "*") -> [(permite, caminho)]. Linhas User-agent seguidas formam um
    grupo só, e grupos repetidos do mesmo robô se somam."""
    grupos: dict[str, list[tuple[bool, str]]] = {}
    agentes: list[str] = []
    em_regras = False
    for linha in texto.splitlines():
        campo, _, valor = linha.split("#", 1)[0].partition(":")
        campo, valor = campo.strip().lower(), valor.strip()
        if campo == "user-agent":
            if em_regras:
                agentes, em_regras = [], False
            nome = (valor.split("/")[0].split() or [""])[0].lower()
            if nome:
                agentes.append(nome)
                grupos.setdefault(nome, [])
        elif campo in ("allow", "disallow") and agentes:
            em_regras = True
            for a in agentes:
                grupos[a].append((campo == "allow", valor))
    return grupos


def caminho_de(url: str) -> str:
    partes = urlsplit(url)
    return (partes.path or "/") + (f"?{partes.query}" if partes.query else "")


def _casa(padrao: str, caminho: str) -> bool:
    fim = padrao.endswith("$")
    corpo = re.sub(r"\*+", "*", unquote(padrao[:-1] if fim else padrao))
    if corpo.count("*") > 10:   # regra patológica: não deixa a expressão travar o rastreamento
        return False
    regex = ".*".join(re.escape(p) for p in corpo.split("*")) + ("$" if fim else "")
    return re.match(regex, unquote(caminho)) is not None


def permite(regras: dict, robo: str, caminho: str) -> bool:
    """O robô pode abrir o caminho? Vale o grupo do robô ou, sem ele, o "*". Entre as regras que
    casam, a mais longa vence; no empate, Allow. "Disallow:" vazio não proíbe nada."""
    grupo = regras.get(robo.lower(), regras.get("*", []))
    melhor, pode = -1, True
    for allow, padrao in grupo:
        if padrao and _casa(padrao, caminho) and (len(padrao) > melhor or (len(padrao) == melhor and allow)):
            melhor, pode = len(padrao), allow
    return pode


def robos_bloqueados(texto_robots: str, url: str) -> list[str]:
    """Robôs da lista que o robots.txt proíbe de abrir a URL."""
    regras, caminho = regras_robots(texto_robots), caminho_de(url)
    return [r for r, _, _ in ROBOS if not permite(regras, r, caminho)]


def _check(nome, ok, detalhe, impacto="") -> dict:
    return {"nome": nome, "ok": ok, "detalhe": detalhe, "impacto": impacto if not ok else ""}


def _identidade(home) -> dict:
    """Sinais que amarram o site a UMA empresa real. Sem eles, as IAs confundem a marca com
    outras de nome parecido (num radar real, 5 de 9 respostas sobre a marca falaram de outra empresa)."""
    html = home.text if home is not None and home.status_code == 200 else ""
    texto = re.sub(r"<[^>]+>", " ", html)
    org = {}
    for bloco in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', html, re.S):
        try:
            dados = json.loads(bloco)
        except ValueError:
            continue
        for i in (dados.get("@graph", [dados]) if isinstance(dados, dict) else dados):
            if isinstance(i, dict) and re.search(r"Organization|LocalBusiness|ProfessionalService", str(i.get("@type"))):
                org = i
    sinais = {
        "CNPJ visível": bool(re.search(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}", texto)),
        "endereço na ficha da empresa": bool(org.get("address")),
        "perfis oficiais ligados (sameAs ou links)": bool(org.get("sameAs")) or bool(
            re.search(r'https?://(?:www\.)?(?:instagram|linkedin|facebook|youtube)\.com/', html)),
        "página Sobre": bool(re.search(r'href="[^"]*(sobre|quem-somos|about)[^"]*"', html, re.I)),
    }
    faltam = [k for k, v in sinais.items() if not v]
    return _check(
        "Identidade da empresa clara para as IAs", len(faltam) <= 1,
        ("faltam: " + "; ".join(faltam)) if faltam else "CNPJ, endereço, perfis oficiais e página Sobre presentes",
        "Sem CNPJ, endereço e perfis oficiais ligados ao site, as IAs não têm como saber qual empresa "
        "é esta e confundem com outras de nome parecido.")


def auditar(site: str) -> list[dict]:
    base = site.rstrip("/") + "/"
    checks = []

    bloqueados = []
    for robo, papel, ua in ROBOS:
        r = _get(base, ua)
        if r is None or r.status_code >= 400:
            bloqueados.append(f"{robo} ({papel})")
    checks.append(_check(
        "Robôs das IAs conseguem acessar o site", not bloqueados,
        ("bloqueados: " + "; ".join(bloqueados)) if bloqueados else f"{len(ROBOS)} robôs testados, todos com acesso",
        "O servidor recusa robôs de IA. Mesmo com o robots.txt liberado, um firewall/plugin de "
        "segurança está bloqueando quem lê o site para as IAs."))

    robots = _get(urljoin(base, "robots.txt"))
    texto_robots = robots.text if robots is not None and robots.status_code == 200 else ""
    bloqueio_robots = robos_bloqueados(texto_robots, base) if texto_robots else []
    checks.append(_check(
        "robots.txt libera as IAs", bool(texto_robots) and not bloqueio_robots,
        ("bloqueia: " + ", ".join(bloqueio_robots)) if bloqueio_robots else
        ("ok" if texto_robots else f"não encontrado (HTTP {robots.status_code if robots is not None else '—'})"),
        "Regras do robots.txt impedem IAs de lerem o site."))

    tem_sitemap = any((r := _get(urljoin(base, nome))) is not None and r.status_code == 200
                      for nome in ("sitemap_index.xml", "sitemap.xml"))
    checks.append(_check("Sitemap publicado", tem_sitemap, "ok" if tem_sitemap else "não encontrado",
                         "Buscadores demoram mais para descobrir páginas novas."))

    # llms.txt ficou de fora: estudo com ~300 mil domínios não achou efeito nas citações,
    # e o Google diz que não usa o arquivo. Não vendemos como correção.

    home = _get(base)
    tipos = []
    if home is not None and home.status_code == 200:
        for bloco in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', home.text, re.S):
            try:
                dados = json.loads(bloco)
            except ValueError:
                continue
            itens = dados.get("@graph", [dados]) if isinstance(dados, dict) else dados
            tipos += [str(i.get("@type")) for i in itens if isinstance(i, dict)]
    empresa = [t for t in tipos if re.search(r"Organization|LocalBusiness|ProfessionalService|Agency", t)]
    checks.append(_check(
        "Dados estruturados da empresa", bool(empresa),
        ("tipos: " + ", ".join(sorted(set(tipos)))) if tipos else "nenhum JSON-LD na página inicial",
        "Falta a ficha técnica da empresa (nome, endereço, telefone, área de atuação) em formato "
        "que Google e IAs leem diretamente."))

    checks.append(_identidade(home))

    posts = _get(urljoin(base, "wp-json/wp/v2/posts?per_page=1"))
    total = posts.headers.get("X-WP-Total") if posts is not None and posts.status_code == 200 else None
    checks.append(_check(
        "Blog com conteúdo", bool(total and int(total) >= 5),
        f"{total} post(s) publicados" if total is not None else "blog não encontrado",
        "Sem conteúdo próprio, as IAs não têm o que citar do site quando alguém pergunta sobre o serviço."))
    return checks
