"""
conteudo/publicador.py — Envia artigos ao WordPress e avisa buscadores.

WordPress: REST API com senha de aplicativo (Usuários → Perfil → Senhas de
aplicativo). Por padrão o post vai como RASCUNHO; publicar direto só é
permitido sem pendências [[...]] no texto.

IndexNow: avisa Bing e outros buscadores assim que uma URL pública muda.
Exige uma chave hospedada em https://<site>/<chave>.txt.
"""

import os
from urllib.parse import urlparse

import requests

from config import settings
from conteudo import render


def _env(cliente_id: str, campo: str) -> str | None:
    return os.getenv(f"WP_{cliente_id.upper()}_{campo}")


def enviar_wordpress(artigo: dict, cliente: dict, status: str = settings.WP_STATUS_PADRAO) -> dict:
    if status == "publish" and artigo["pendencias"]:
        raise ValueError(f"{len(artigo['pendencias'])} pendência(s) no texto; resolva antes de publicar.")
    usuario, senha = _env(cliente["id"], "USUARIO"), _env(cliente["id"], "SENHA_APP")
    if not usuario or not senha:
        raise RuntimeError(f"Faltam WP_{cliente['id'].upper()}_USUARIO e "
                           f"WP_{cliente['id'].upper()}_SENHA_APP no .env.")

    endpoint = cliente["site"].rstrip("/") + "/wp-json/wp/v2/posts"
    payload = {
        "title": artigo["titulo"],
        "slug": artigo["slug"],
        "status": status,
        "excerpt": artigo["meta_descricao"],
        "content": render.conteudo_post(artigo, cliente),
    }
    if artigo.get("wordpress", {}).get("id"):  # reenvio atualiza o mesmo post
        endpoint += f"/{artigo['wordpress']['id']}"
    resp = requests.post(endpoint, json=payload, auth=(usuario, senha), timeout=60)
    resp.raise_for_status()
    post = resp.json()
    return {"id": post["id"], "status": post["status"], "link": post["link"],
            "editar": cliente["site"].rstrip("/") + f"/wp-admin/post.php?post={post['id']}&action=edit"}


def avisar_indexnow(urls: list[str], cliente: dict) -> int:
    chave = os.getenv(f"INDEXNOW_{cliente['id'].upper()}_CHAVE")
    if not chave:
        raise RuntimeError(f"Falta INDEXNOW_{cliente['id'].upper()}_CHAVE no .env "
                           f"(e o arquivo <chave>.txt na raiz do site).")
    host = urlparse(cliente["site"]).netloc
    resp = requests.post(settings.INDEXNOW_ENDPOINT, timeout=30, json={
        "host": host,
        "key": chave,
        "keyLocation": f"https://{host}/{chave}.txt",
        "urlList": urls,
    })
    resp.raise_for_status()  # 200/202 = aceito
    return resp.status_code
