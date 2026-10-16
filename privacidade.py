"""
privacidade.py — Direitos do titular sobre os dados de um cliente (LGPD, Art. 18; ver docs/LGPD.md).

    python main.py exportar <cliente>              # acesso e portabilidade: .zip com tudo do cliente
    python main.py esquecer <cliente>              # eliminação: só lista o que seria apagado
    python main.py esquecer <cliente> --confirmar  # apaga

Junta num lugar só todo arquivo que o sistema grava por cliente. Quem criar um
novo lugar de gravação por cliente precisa acrescentá-lo em `locais()`; o teste
`teste_esquecer_apaga_tudo_do_cliente` ajuda a lembrar.
"""

import json
import re
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

import custos
import medicao
from app import dados, seguranca
from config import settings
from midia import termos
from site_cliente import gerador


def locais(cliente_id: str) -> list[Path]:
    """Arquivos e pastas do cliente que existem hoje no disco."""
    if not seguranca.id_valido(cliente_id):
        raise ValueError(f"Id de cliente inválido: {cliente_id!r}")
    candidatos = [
        settings.CLIENTES_DIR / f"{cliente_id}.json",       # cadastro
        gerador.SITES / cliente_id,                         # rascunho do site e imagens enviadas
        settings.RUNS_DIR / cliente_id,                     # radares (respostas das IAs)
        settings.CONTEUDO_DIR / cliente_id,                 # pautas e artigos
        dados.PLANO_DIR / f"{cliente_id}.json",             # andamento do plano de ações
        medicao.PASTA / cliente_id,                         # GA4 e Search Console
        termos.PASTA / f"{cliente_id}.json",                # termos do Google Ads
        dados.ENTREGAS_DIR / cliente_id,                    # guias, plano de correção, sites gerados
        gerador.CACHE_IMAGENS / cliente_id,                 # fotos reduzidas
        settings.BASE_DIR / "data" / "sites_historico" / cliente_id,
    ]
    # radar-<id>-AAAAMMDD-HHMMSS[-demo].html e dados-<id>-AAAAMMDD-HHMMSS.zip (exportações):
    # o padrão exato evita pegar o cliente "<id>-b"
    relatorio = re.compile(rf"^(radar-{re.escape(cliente_id)}-\d{{8}}-\d{{6}}(-demo)?\.html"
                           rf"|dados-{re.escape(cliente_id)}-\d{{8}}-\d{{6}}\.zip)$")
    if settings.RELATORIOS_DIR.exists():
        candidatos += [p for p in settings.RELATORIOS_DIR.iterdir() if relatorio.match(p.name)]
    return [p for p in candidatos if p.exists()]


def exportar(cliente_id: str, pasta_destino: Path) -> Path | None:
    """Copia tudo do cliente para um .zip (formato aberto: JSON, HTML, imagens). None se não houver nada."""
    alvos = locais(cliente_id)
    if not alvos:
        return None
    pasta_destino.mkdir(parents=True, exist_ok=True)
    arq = pasta_destino / f"dados-{cliente_id}-{datetime.now():%Y%m%d-%H%M%S}.zip"
    with zipfile.ZipFile(arq, "w", zipfile.ZIP_DEFLATED) as z:
        for alvo in alvos:
            arquivos = [p for p in alvo.rglob("*") if p.is_file()] if alvo.is_dir() else [alvo]
            for p in arquivos:
                z.write(p, p.relative_to(settings.BASE_DIR).as_posix())
    return arq


def esquecer(cliente_id: str) -> list[Path]:
    """Apaga tudo do cliente e tira o id dele do registro interno de gastos. Devolve o que apagou."""
    apagados = locais(cliente_id)
    for p in apagados:
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()
    _anonimizar_gastos(cliente_id)
    return apagados


def _anonimizar_gastos(cliente_id: str):
    """O valor gasto fica (é conta da TimeLabs); o vínculo com o cliente sai."""
    arq = custos.GASTOS_ARQ
    if not arq.exists():
        return
    linhas = []
    for bruta in arq.read_text(encoding="utf-8").splitlines():
        try:
            registro = json.loads(bruta)
        except json.JSONDecodeError:
            linhas.append(bruta)
            continue
        if registro.get("cliente") == cliente_id:
            registro["cliente"] = "removido"
        linhas.append(json.dumps(registro, ensure_ascii=False))
    arq.write_text("\n".join(linhas) + ("\n" if linhas else ""), encoding="utf-8", newline="\n")
