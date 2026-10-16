"""
conteudo/fluxo.py — Escreve os artigos de uma pauta e atualiza a central.
"""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from conteudo import redator, render

# Artigos são longos; poucos em paralelo para não estourar limite de taxa
MAX_ARTIGOS_PARALELOS = 3


def carregar_artigos(pasta: Path) -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(pasta.glob("*.json")) if p.name != "pauta.json"]


def salvar_artigo(pasta: Path, artigo: dict, cliente: dict) -> None:
    (pasta / f"{artigo['slug']}.json").write_text(
        json.dumps(artigo, ensure_ascii=False, indent=2), encoding="utf-8")
    (pasta / f"{artigo['slug']}.html").write_text(
        render.pagina_previa(artigo, cliente), encoding="utf-8")


def atualizar_central(pasta: Path, cliente: dict) -> Path:
    pauta = json.loads((pasta / "pauta.json").read_text(encoding="utf-8"))
    central = pasta / "index.html"
    central.write_text(render.pagina_central(cliente, pauta, carregar_artigos(pasta)),
                       encoding="utf-8")
    return central


def escrever_pauta(pasta: Path, cliente: dict, run: dict | None, numeros: list[int] | None,
                   progresso=print) -> Path:
    pauta = json.loads((pasta / "pauta.json").read_text(encoding="utf-8"))
    temas = [t for i, t in enumerate(pauta["temas"], start=1) if not numeros or i in numeros]
    progresso(f"Escrevendo {len(temas)} artigo(s)…")

    with ThreadPoolExecutor(max_workers=MAX_ARTIGOS_PARALELOS) as pool:
        futuros = {pool.submit(redator.escrever, t, cliente, run, pauta["demo"]): t for t in temas}
        for fut in as_completed(futuros):
            tema = futuros[fut]
            try:
                artigo = fut.result()
            except Exception as e:  # um artigo com erro não perde os outros
                progresso(f"  ✗ {tema['titulo']}: {type(e).__name__}: {e}")
                continue
            if cliente.get("aprovacao") == "pauta" and not artigo["pendencias"] and not artigo.get("demo"):
                artigo["status"] = "aprovado"  # o cliente aprovou a pauta; sem pendência, o texto já pode seguir
            salvar_artigo(pasta, artigo, cliente)
            progresso(f"  ✓ {artigo['titulo']} ({artigo['palavras']} palavras, "
                      f"{len(artigo['pendencias'])} pendências{', aprovado pela pauta' if artigo['status'] == 'aprovado' else ''})")

    return atualizar_central(pasta, cliente)
