"""
app/dados.py — Leitura e escrita do estado que o app mostra.

Tudo continua em arquivos (config/clientes, data/runs, data/conteudo,
entregas/), os mesmos que a linha de comando usa. Só o estado do plano de
ações é novo: data/plano/<cliente>.json.
"""

import json
import re
import unicodedata
from pathlib import Path

from config import settings
from conteudo import fluxo
from conteudo import pauta as pauta_mod

PLANO_DIR = settings.BASE_DIR / "data" / "plano"
ENTREGAS_DIR = settings.BASE_DIR / "entregas"

# Status de um artigo, na ordem do quadro de conteúdo
STATUS_ARTIGO = ["a escrever", "rascunho", "aprovado", "rascunho no WordPress", "publicado"]
STATUS_ACAO = ["pendente", "em andamento", "feito"]


def _ler(caminho: Path) -> dict:
    return json.loads(caminho.read_text(encoding="utf-8"))


def _gravar(caminho: Path, dados: dict) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


# --------------------------------------------------------------------------
# Clientes
# --------------------------------------------------------------------------

def clientes() -> list[dict]:
    return [_ler(p) for p in sorted(settings.CLIENTES_DIR.glob("*.json"))]


def cliente(cliente_id: str) -> dict | None:
    caminho = settings.CLIENTES_DIR / f"{cliente_id}.json"
    return _ler(caminho) if caminho.exists() else None


def salvar_cliente(dados: dict) -> None:
    _gravar(settings.CLIENTES_DIR / f"{dados['id']}.json", dados)


def gerar_id(nome: str) -> str:
    t = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode().lower()
    base = re.sub(r"[^a-z0-9]+", "_", t).strip("_")[:40] or "cliente"
    cid, n = base, 2
    while (settings.CLIENTES_DIR / f"{cid}.json").exists():
        cid, n = f"{base}_{n}", n + 1
    return cid


# --------------------------------------------------------------------------
# Radar
# --------------------------------------------------------------------------

def radares(cliente_id: str) -> list[Path]:
    """Execuções salvas, da mais antiga para a mais recente (reais e demo)."""
    return sorted((settings.RUNS_DIR / cliente_id).glob("*.json"))


def ultimo_radar(cliente_id: str) -> dict | None:
    """O real mais recente; se não houver nenhum real, o demo mais recente."""
    todos = radares(cliente_id)
    reais = [p for p in todos if "-demo" not in p.name]
    escolhido = (reais or todos or [None])[-1]
    if not escolhido:
        return None
    run = _ler(escolhido)
    run["_arquivo"] = str(escolhido)
    return run


# --------------------------------------------------------------------------
# Conteúdo
# --------------------------------------------------------------------------

def pasta_pauta(cliente_id: str) -> Path | None:
    return (pauta_mod.ultima_pauta(cliente_id, incluir_demo=False)
            or pauta_mod.ultima_pauta(cliente_id, incluir_demo=True))


def pauta(cliente_id: str) -> tuple[Path | None, dict | None]:
    pasta = pasta_pauta(cliente_id)
    return (pasta, _ler(pasta / "pauta.json")) if pasta else (None, None)


def artigos(pasta: Path) -> dict[str, dict]:
    return {a["slug"]: a for a in fluxo.carregar_artigos(pasta)}


def artigo(pasta: Path, slug: str) -> dict | None:
    caminho = pasta / f"{slug}.json"
    return _ler(caminho) if caminho.exists() else None


def quadro(cliente_id: str) -> dict:
    """Temas da pauta agrupados por status, para o quadro de conteúdo."""
    pasta, p = pauta(cliente_id)
    colunas = {s: [] for s in STATUS_ARTIGO}
    if not p:
        return {"pasta": None, "pauta": None, "colunas": colunas}
    arts = artigos(pasta)
    for i, t in enumerate(p["temas"], start=1):
        a = arts.get(t["slug"])
        status = a.get("status", "rascunho") if a else "a escrever"
        colunas.setdefault(status, []).append({"numero": i, "tema": t, "artigo": a})
    return {"pasta": pasta, "pauta": p, "colunas": colunas}


# --------------------------------------------------------------------------
# Plano de ações
# --------------------------------------------------------------------------

def plano(cliente_id: str, run: dict | None) -> list[dict]:
    """Ações do último radar + o status salvo de cada uma (chave = título)."""
    caminho = PLANO_DIR / f"{cliente_id}.json"
    estado = _ler(caminho) if caminho.exists() else {}
    acoes = (run or {}).get("metricas", {}).get("recomendacoes", [])
    return [{**a, "status": estado.get(a["titulo"], "pendente"), "guia": guia_para(cliente_id, a["titulo"])}
            for a in acoes]


def marcar_acao(cliente_id: str, titulo: str, status: str) -> None:
    caminho = PLANO_DIR / f"{cliente_id}.json"
    estado = _ler(caminho) if caminho.exists() else {}
    estado[titulo] = status
    _gravar(caminho, estado)


# Ação do plano -> guia em entregas/<cliente>/ (pelo assunto do título; a primeira que bater vale)
_GUIAS = [("identidade", "01-identidade-oficial"), ("ficha técnica", "01-identidade-oficial"),
          ("listas", "02-listas-de-terceiros"), ("terceiros", "02-listas-de-terceiros"),
          ("avaliações", "03-avaliacoes"),
          ("bing", "05-bing-e-plataformas"), ("plataformas", "05-bing-e-plataformas"),
          ("robôs", "06-robos-de-treino"), ("robots", "06-robos-de-treino"),
          ("chatgpt", "07-anuncios-chatgpt")]


def guia_para(cliente_id: str, titulo: str) -> str | None:
    t = titulo.lower()
    for chave, arquivo in _GUIAS:
        if chave in t and (ENTREGAS_DIR / cliente_id / f"{arquivo}.md").exists():
            return arquivo
    return None


def guia(cliente_id: str, nome: str) -> tuple[dict, str] | None:
    import plano_correcao
    caminho = ENTREGAS_DIR / cliente_id / f"{nome}.md"
    if not caminho.exists():
        return None
    meta, texto = plano_correcao.ler_md(caminho)
    corpo = plano_correcao.md_para_html(texto)
    if nome == plano_correcao.GUIA_LISTAS:
        corpo += plano_correcao.tabela_paginas(cliente_id)
    return meta, corpo
