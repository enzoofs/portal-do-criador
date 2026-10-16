"""
radar/pagina.py — O que um robô de IA encontra numa página HTML, sem executar JavaScript.

Usado pelo rastreador (site atual do cliente e páginas de concorrentes citadas) e pela checagem
antes de publicar o site gerado. Lê com o parser de HTML da biblioteca padrão: expressão regular
falha no HTML de terceiros (atributos em outra ordem, aspas simples, maiúsculas).
"""

import json
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

# Conteúdo que o robô baixa mas não é texto da página
_FORA_DO_TEXTO = {"script", "style", "noscript", "svg", "template"}
# Contêiner vazio onde o JavaScript monta a página (React, Next, Nuxt, Vue, Angular)
_RAIZES_JS = {"root", "app", "__next", "__nuxt", "q-app", "svelte"}
_PRECO = re.compile(r"R\$\s?\d")
_TITULO_FAQ = re.compile(r"perguntas frequentes|d[uú]vidas frequentes|\bfaq\b", re.I)


class _Leitor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.titulo, self.descricao, self.robots, self.canonical, self.base = [], None, "", "", ""
        self.h1, self.h1_texto, self.links, self.jsonld = 0, [], [], []
        self.texto, self.texto_main, self.tem_main, self.raiz_js = [], [], False, False
        self.titulos_secao = []
        self._fora = 0          # dentro de script/style/svg…
        self._main = 0          # dentro de <main>
        self._em = None         # "title", "h1", "h2", "h3" ou "jsonld"
        self._buffer = []

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        self._espaco()
        if tag == "base" and a.get("href") and not self.base:
            self.base = a["href"]
        elif tag == "meta":
            nome = a.get("name", "").lower()
            if nome == "description" and self.descricao is None:
                self.descricao = a.get("content", "").strip()
            elif nome == "robots":
                self.robots += " " + a.get("content", "").lower()
        elif tag == "link" and "canonical" in a.get("rel", "").lower().split() and not self.canonical:
            self.canonical = a.get("href", "").strip()
        elif tag == "a" and a.get("href"):
            self.links.append(a["href"].strip())
        elif tag == "main":
            self._main += 1
            self.tem_main = True
        elif tag in ("div", "body") and a.get("id", "").lower() in _RAIZES_JS:
            self.raiz_js = True
        if tag == "script" and "ld+json" in a.get("type", "").lower():
            self._abrir("jsonld")
        elif tag in _FORA_DO_TEXTO:
            self._fora += 1
        elif tag == "title" and not self._fora and not self.titulo:
            self._abrir("title")
        elif tag == "h1":
            self.h1 += 1
            self._abrir("h1")
        elif tag in ("h2", "h3") and self._em is None:
            self._abrir(tag)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag in _FORA_DO_TEXTO:
            self._fora = max(0, self._fora - 1)

    def handle_endtag(self, tag):
        self._espaco()
        if self._em == "jsonld" and tag == "script":
            self.jsonld.append("".join(self._buffer))
            self._em = None
        elif tag in _FORA_DO_TEXTO:
            self._fora = max(0, self._fora - 1)
        elif tag == "main":
            self._main = max(0, self._main - 1)
        elif tag == self._em:
            texto = _limpo("".join(self._buffer))
            if tag == "title":
                self.titulo.append(texto)
            elif tag == "h1":
                self.h1_texto.append(texto)
            else:
                self.titulos_secao.append(texto)
            self._em = None

    def handle_data(self, data):
        if self._em is not None:
            self._buffer.append(data)
        if self._em in ("jsonld", "title") or self._fora:
            return
        self.texto.append(data)
        if self._main:
            self.texto_main.append(data)

    def _abrir(self, em):
        self._em, self._buffer = em, []

    def _espaco(self):
        # tag separa palavras ("<b>a</b>b" são duas), como na contagem antiga da checagem
        self.texto.append(" ")
        if self._main:
            self.texto_main.append(" ")


def _limpo(texto: str) -> str:
    return re.sub(r"\s+", " ", texto).strip()


def _tipos_jsonld(blocos: list[str]) -> tuple[list[str], bool]:
    tipos, invalido = [], False
    for bloco in blocos:
        try:
            dados = json.loads(bloco.strip())
        except ValueError:
            invalido = True
            continue
        itens = dados.get("@graph", [dados]) if isinstance(dados, dict) else dados if isinstance(dados, list) else []
        for item in itens:
            if isinstance(item, dict):
                t = item.get("@type")
                tipos += [str(x) for x in t] if isinstance(t, list) else [str(t)] if t else []
    return list(dict.fromkeys(tipos)), invalido


def links_absolutos(hrefs: list[str], base: str) -> list[str]:
    """Só http(s), sem âncora, sem repetir."""
    saida = []
    for href in hrefs:
        if href.lower().startswith(("mailto:", "tel:", "javascript:", "data:", "#", "whatsapp:")):
            continue
        url = urljoin(base, href).split("#")[0]
        if urlsplit(url).scheme in ("http", "https"):
            saida.append(url)
    return list(dict.fromkeys(saida))


def sinais(html: str, url: str) -> dict:
    """Título, descrição, diretivas, H1, texto visível, links e fichas de uma página."""
    leitor = _Leitor()
    leitor.feed(html)
    leitor.close()
    base = urljoin(url, leitor.base) if leitor.base else url
    texto = _limpo("".join(leitor.texto_main if leitor.tem_main else leitor.texto))
    tipos, invalido = _tipos_jsonld(leitor.jsonld)
    return {
        "titulo": leitor.titulo[0] if leitor.titulo else "",
        "descricao": leitor.descricao or "",
        "robots": leitor.robots.strip(),
        "canonical": urljoin(base, leitor.canonical) if leitor.canonical else "",
        "h1": leitor.h1,
        "h1_texto": leitor.h1_texto[0] if leitor.h1_texto else "",
        "palavras": len(texto.split()),
        "inicio": texto[:300],
        "links": links_absolutos(leitor.links, base),
        "jsonld_tipos": tipos,
        "jsonld_invalido": invalido,
        "raiz_js": leitor.raiz_js,
        "tem_preco": bool(_PRECO.search(texto)),
        "tem_faq": "FAQPage" in tipos or any(_TITULO_FAQ.search(t) for t in leitor.titulos_secao),
    }
