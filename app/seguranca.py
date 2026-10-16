"""
app/seguranca.py — Proteções do app local contra outros sites e contra leitura de arquivos.

O Portal escuta só em 127.0.0.1, mas qualquer página aberta no navegador de quem usa o Portal
consegue mandar pedidos para ele. Sem estas proteções, um site malicioso poderia:
  - disparar execuções pagas (radar, artigos) com as chaves de API do .env (CSRF);
  - ler os dados do Portal apontando um domínio próprio para 127.0.0.1 (DNS rebinding);
  - ler qualquer arquivo do projeto, inclusive o .env, por "..\\" na URL (no Windows a barra
    invertida passa pelas rotas do Flask e vira separador de pasta).

Regras:
  1. Host só 127.0.0.1, localhost ou [::1].
  2. Pedido que altera algo (POST etc.) vindo de outra origem é recusado.
  3. API JSON só com Content-Type application/json (pedido "simples" de outro site não passa).
  4. Todo identificador que vem da URL passa por um padrão estrito; arquivo servido precisa
     continuar dentro da pasta permitida depois de resolvido.
  5. Cabeçalhos de segurança em todas as respostas; CSP estrita nas telas do Portal.
"""

import re
from pathlib import Path
from urllib.parse import urlparse

from flask import abort, request

HOSTS_PERMITIDOS = {"127.0.0.1", "localhost", "[::1]", "::1"}
METODOS_SEGUROS = {"GET", "HEAD", "OPTIONS"}
LIMITE_PEDIDO = 10 * 1024 * 1024  # maior envio aceito (imagem de 8 MB + folga)

ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,79}$")              # cliente, página, artigo, tarefa
ARQUIVO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")  # nome de arquivo sem pasta

# Telas do Portal: nada de script de fora nem embutido. A prévia do site do cliente
# (que usa Google Fonts e vídeos) fica fora desta política.
CSP_PORTAL = "; ".join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data:",
    "font-src 'self'",
    "connect-src 'self'",
    "frame-src 'self'",
    "frame-ancestors 'self'",
    "base-uri 'none'",
    "form-action 'self'",
    "object-src 'none'",
])


def id_valido(valor: str) -> bool:
    return bool(valor) and bool(ID.fullmatch(valor))


def exigir_id(*valores: str) -> None:
    for v in valores:
        if not id_valido(v):
            abort(404)


def arquivo_dentro(pasta: Path, nome: str) -> Path:
    """Caminho de `nome` dentro de `pasta`, ou 404. Aceita subpastas com / (prévia do site),
    nunca \\, .. nem caminho absoluto; e confere o resultado depois de resolvido."""
    partes = nome.split("/")
    if not nome or "\\" in nome or any(p in ("", ".", "..") for p in partes) or not all(ARQUIVO.fullmatch(p) for p in partes):
        abort(404)
    base = pasta.resolve()
    alvo = (base / nome).resolve()
    if base != alvo and base not in alvo.parents:
        abort(404)
    return alvo


def json_do_pedido() -> dict:
    """Corpo JSON de uma API do Portal. Exige o Content-Type: um pedido "simples" (texto puro),
    que outro site manda sem perguntar ao navegador, é recusado."""
    if not request.is_json:
        abort(415)
    corpo = request.get_json(silent=True)
    if not isinstance(corpo, dict):
        abort(400)
    return corpo


def _mesma_origem() -> bool:
    site = request.headers.get("Sec-Fetch-Site")
    if site and site not in ("same-origin", "none"):
        return False
    origem = request.headers.get("Origin")
    if origem is None:
        referer = request.headers.get("Referer")
        return not referer or urlparse(referer).netloc == request.host
    return origem != "null" and urlparse(origem).netloc == request.host


def proteger(app) -> None:
    app.config["MAX_CONTENT_LENGTH"] = LIMITE_PEDIDO

    @app.before_request
    def _filtrar():
        host = request.host.rsplit(":", 1)[0] if not request.host.startswith("[") else request.host.split("]")[0] + "]"
        if host not in HOSTS_PERMITIDOS:
            abort(421)  # Misdirected Request: protege contra DNS rebinding
        if request.method not in METODOS_SEGUROS and not _mesma_origem():
            abort(403)

    @app.after_request
    def _cabecalhos(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        resp.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        resp.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        if "/site-novo/" not in request.path:
            resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
            if resp.mimetype == "text/html":
                resp.headers.setdefault("Content-Security-Policy", CSP_PORTAL)
        return resp
