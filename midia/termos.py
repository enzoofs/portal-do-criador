"""
midia/termos.py — Termos de pesquisa do Google Ads da agência.

O que o cliente já paga para aparecer no Google é a melhor pista do que ele
pergunta às IAs. O relatório "Termos de pesquisa" (Google Ads → Insights e
relatórios → Termos de pesquisa → Baixar → CSV) vira:
  - perguntas do radar (como um cliente perguntaria à IA)
  - contexto da pauta (artigos que atacam termos caros reduzem a conta de mídia)

Aceita o CSV como o Google Ads exporta: português ou inglês, UTF-8 ou UTF-16
("CSV para Excel"), vírgula, ponto e vírgula ou tabulação, linhas de título
antes do cabeçalho e números em formato brasileiro (R$ 1.234,56).
"""

import csv
import io
import json
import re
import unicodedata
from datetime import datetime

from config import settings

PASTA = settings.BASE_DIR / "data" / "midia"

# nome normalizado da coluna -> campo
COLUNAS = {
    "termo": ["termo de pesquisa", "termo de busca", "termos de pesquisa", "search term", "search terms"],
    "cliques": ["cliques", "clicks"],
    "impressoes": ["impr.", "impressoes", "impressions", "impr"],
    "custo": ["custo", "cost"],
    "conversoes": ["conversoes", "conversions", "conv."],
}


class ArquivoInvalido(ValueError):
    pass


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", t).strip()


def _decodificar(bruto: bytes) -> str:
    if bruto[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return bruto.decode("utf-16")
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return bruto.decode(enc)
        except UnicodeDecodeError:
            continue
    return bruto.decode("latin-1")


def numero(valor: str) -> float:
    """'R$ 1.234,56' -> 1234.56; '1,234.56' -> 1234.56; '--' -> 0."""
    v = re.sub(r"[^\d,.\-]", "", valor or "")
    if not v or v in "-.,":
        return 0.0
    if "," in v and "." in v:   # o último separador é o decimal
        v = v.replace(".", "").replace(",", ".") if v.rfind(",") > v.rfind(".") else v.replace(",", "")
    elif "," in v:
        inteiro, _, dec = v.rpartition(",")
        v = f"{inteiro.replace(',', '')}.{dec}" if len(dec) != 3 else v.replace(",", "")
    elif v.count(".") > 1 or (v.count(".") == 1 and len(v.rpartition(".")[2]) == 3 and len(v) > 4):
        v = v.replace(".", "")   # 1.234 = mil duzentos e trinta e quatro
    try:
        return float(v)
    except ValueError:
        return 0.0


def ler_csv(bruto: bytes) -> list[dict]:
    texto = _decodificar(bruto)
    linhas = texto.splitlines()
    # o cabeçalho é a primeira linha com uma célula "Termo de pesquisa" (o título do relatório
    # também fala em "termos de pesquisa", mas não é uma linha de colunas)
    def e_cabecalho(linha: str, d: str) -> bool:
        return d in linha and any(_norm(c.strip('"')) in COLUNAS["termo"] for c in linha.split(d))

    inicio, delim = next(((i, d) for i, linha_csv in enumerate(linhas) for d in ("\t", ";", ",")
                          if e_cabecalho(linha_csv, d)), (None, None))
    if inicio is None:
        raise ArquivoInvalido("Não achei a coluna 'Termo de pesquisa'. Exporte o relatório de termos "
                              "de pesquisa do Google Ads em CSV.")
    corpo = "\n".join(linhas[inicio:])
    leitor = csv.reader(io.StringIO(corpo), delimiter=delim)
    cab = [_norm(c) for c in next(leitor)]
    idx = {campo: next((i for i, c in enumerate(cab) if c in nomes), None) for campo, nomes in COLUNAS.items()}

    termos: dict[str, dict] = {}
    for linha in leitor:
        if not linha or idx["termo"] >= len(linha):
            continue
        termo = linha[idx["termo"]].strip()
        if not termo or _norm(termo).startswith(("total", "--")):
            continue   # linhas de total do relatório
        t = termos.setdefault(termo.lower(), {"termo": termo, "cliques": 0, "impressoes": 0,
                                              "custo": 0.0, "conversoes": 0.0})
        for campo in ("cliques", "impressoes", "custo", "conversoes"):
            if idx[campo] is not None and idx[campo] < len(linha):
                t[campo] += numero(linha[idx[campo]])
    if not termos:
        raise ArquivoInvalido("O arquivo não tem termos de pesquisa.")
    lista = sorted(termos.values(), key=lambda t: (-t["custo"], -t["conversoes"], -t["cliques"]))
    for t in lista:
        t["custo"] = round(t["custo"], 2)
        t["cpc"] = round(t["custo"] / t["cliques"], 2) if t["cliques"] else 0.0
    return lista


def salvar(cliente_id: str, termos: list[dict], arquivo: str) -> dict:
    dados = {"importado_em": datetime.now().isoformat(timespec="seconds"), "arquivo": arquivo,
             "termos": termos}
    PASTA.mkdir(parents=True, exist_ok=True)
    (PASTA / f"{cliente_id}.json").write_text(json.dumps(dados, ensure_ascii=False, indent=2),
                                              encoding="utf-8")
    return dados


def carregar(cliente_id: str) -> dict | None:
    caminho = PASTA / f"{cliente_id}.json"
    return json.loads(caminho.read_text(encoding="utf-8")) if caminho.exists() else None


def resumo(dados: dict) -> dict:
    ts = dados["termos"]
    return {"termos": len(ts), "custo": round(sum(t["custo"] for t in ts), 2),
            "cliques": int(sum(t["cliques"] for t in ts)),
            "conversoes": round(sum(t["conversoes"] for t in ts), 1)}


def como_pergunta(termo: str, cidade: str) -> str:
    """Termo de busca -> pergunta como alguém faria a uma IA. Editável depois em Configurar."""
    t = termo.strip().rstrip("?").strip()
    if re.match(r"(?i)^melhores\b", t):
        p = "Quais as " + t
    elif re.match(r"(?i)^melhor\b", t):
        p = "Qual a " + t
    elif re.match(r"(?i)^(qual|quais|quem|como|onde|quanto|me indica)\b", t):
        p = t[0].upper() + t[1:]
    else:
        p = f"Quem você indica para {t}"
    if _norm(cidade) not in _norm(p) and not re.search(r"(?i)\b(bh|belo horizonte|perto|em [a-z]{3,})", p):
        p += f" em {cidade}"
    return p + "?"


def para_pauta(dados: dict | None, n: int = 15) -> str:
    """Bloco de texto para o prompt da pauta: os termos mais caros e os que convertem."""
    if not dados:
        return ""
    linhas = [f"- \"{t['termo']}\": R$ {t['custo']:.2f} em {int(t['cliques'])} cliques, "
              f"{t['conversoes']:g} conversões" for t in dados["termos"][:n]]
    return "\n".join(linhas)
