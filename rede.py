"""
rede.py — Baixar páginas da internet sem abrir porta para a rede interna (SSRF).

O Portal baixa sites informados por quem usa (cadastro de cliente) e sites de clientes
(auditoria e rastreamento do radar). Sem esta checagem, um endereço como http://127.0.0.1:5050/ ou
http://169.254.169.254/ (metadados de nuvem) faria o Portal ler a própria máquina ou a
rede interna. Regra: só http(s), e cada endereço, inclusive depois de redirecionamento,
precisa resolver para IP público.
"""

import ipaddress
import socket
from urllib.parse import urljoin, urlparse

import requests

MAX_REDIRECIONAMENTOS = 4


class EnderecoBloqueado(ValueError):
    pass


def conferir_url(url: str) -> str:
    """Devolve a URL se ela aponta para a internet pública; senão levanta EnderecoBloqueado."""
    partes = urlparse(url)
    if partes.scheme not in ("http", "https") or not partes.hostname:
        raise EnderecoBloqueado(f"Endereço inválido: {url}")
    try:
        infos = socket.getaddrinfo(partes.hostname, partes.port or (443 if partes.scheme == "https" else 80),
                                   proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        raise EnderecoBloqueado(f"Domínio não encontrado: {partes.hostname}") from e
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise EnderecoBloqueado(f"{partes.hostname} aponta para um endereço interno ({ip}).")
    return url


def baixar(url: str, cabecalhos: dict | None = None, timeout: int = 15, cadeia: list | None = None,
           max_bytes: int | None = None) -> requests.Response | None:
    """GET seguindo redirecionamentos um a um, conferindo cada destino. None se falhar.

    `cadeia`, se vier, recebe (status, url) de cada redirecionamento seguido (o rastreador mostra
    cadeias longas). `max_bytes` lê só o começo de respostas grandes, para um arquivo enorme no
    site não lotar a memória."""
    atual = url
    for _ in range(MAX_REDIRECIONAMENTOS + 1):
        try:
            conferir_url(atual)
            resp = requests.get(atual, headers=cabecalhos or {}, timeout=timeout, allow_redirects=False,
                                stream=max_bytes is not None)
        except (EnderecoBloqueado, requests.RequestException):
            return None
        if resp.is_redirect or resp.is_permanent_redirect:
            if cadeia is not None:
                cadeia.append((resp.status_code, atual))
            resp.close()
            atual = urljoin(atual, resp.headers.get("Location", ""))
            continue
        if max_bytes is not None:
            try:
                _ler_no_maximo(resp, max_bytes)
            except requests.RequestException:
                return None
        return resp
    return None


def _ler_no_maximo(resp: requests.Response, max_bytes: int) -> None:
    """Lê até max_bytes do corpo, descarta o resto e fecha a conexão. resp.text passa a valer o lido."""
    partes, total = [], 0
    for parte in resp.iter_content(64 * 1024):
        partes.append(parte)
        total += len(parte)
        if total >= max_bytes:
            break
    resp._content = b"".join(partes)[:max_bytes]
    resp.close()
