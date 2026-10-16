"""
custos.py — Quanto cada execução custa, antes (estimativa) e depois (real).

Regra do projeto: nada pago roda sem a pessoa ver a estimativa e confirmar
(--confirmar), e toda execução tem teto de gasto (--limite). O custo real é
somado a partir do `usage` que cada API devolve.
"""

import json
import threading
from datetime import datetime
from pathlib import Path

# US$ por 1M de tokens (entrada, saída). Conferir em mudanças de preço:
# Claude: platform.claude.com/docs/en/about-claude/pricing
# OpenAI: developers.openai.com (valores de 2026-10)
PRECOS_TOKENS = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
    "gpt-5.5": (5.00, 30.00),
    "gpt-5.4-mini": (0.75, 4.50),
    "gpt-4o": (2.50, 10.00),
}
# US$ por busca na web (Claude: US$10/1.000; OpenAI: US$10/1.000 desde 2026, segundo
# rastreadores de preço — conferir no painel de uso depois de cada execução real)
PRECO_BUSCA = {"claude": 0.010, "chatgpt": 0.010, "gemini": 0.0}
# Provedores cobrados por chamada (DataForSEO, modo live). O custo real vem na resposta.
PRECO_CHAMADA = {"chatgpt_app": 0.004, "gemini_app": 0.004, "google_ia": 0.006, "google_modo": 0.004}

# Médias por chamada usadas na ESTIMATIVA (entrada, saída, buscas).
# Pesquisas na web inflam muito a entrada: os resultados entram como tokens.
PERFIL_CHAMADA = {
    "radar": (40_000, 2_000, 5),
    "extracao": (3_000, 300, 0),
    "pauta": (6_000, 3_000, 0),
    "artigo": (5_000, 6_000, 0),
}


class SemPreco(KeyError):
    pass


def preco_tokens(modelo: str, entrada: int, saida: int) -> float:
    if modelo not in PRECOS_TOKENS:
        raise SemPreco(f"Sem preço cadastrado para {modelo} em custos.PRECOS_TOKENS")
    pe, ps = PRECOS_TOKENS[modelo]
    return entrada / 1e6 * pe + saida / 1e6 * ps


def estimar(tipo: str, modelo: str, provedor_busca: str | None = None, chamadas: int = 1) -> float:
    entrada, saida, buscas = PERFIL_CHAMADA[tipo]
    custo = preco_tokens(modelo, entrada, saida)
    if provedor_busca:
        custo += buscas * PRECO_BUSCA.get(provedor_busca, 0.0)
    return custo * chamadas


class OrcamentoEstourado(RuntimeError):
    pass


class ExecucaoNaoAutorizada(RuntimeError):
    pass


class Contador:
    """Soma o gasto real de uma execução (thread-safe) e barra quando passa do teto."""

    def __init__(self):
        self._lock = threading.Lock()
        self.limite: float | None = None
        self.autorizado = False
        self.total = 0.0
        self.itens: list[dict] = []

    def iniciar(self, limite: float):
        """Só a trava da linha de comando (após --confirmar) chama isto."""
        with self._lock:
            self.limite, self.autorizado, self.total, self.itens = limite, True, 0.0, []

    def checar(self):
        """Chamar ANTES de cada chamada paga. Sem autorização explícita, nada passa."""
        if not self.autorizado:
            raise ExecucaoNaoAutorizada("chamada paga sem autorização (falta --confirmar)")
        if self.total >= self.limite:
            raise OrcamentoEstourado(f"limite de US$ {self.limite:.2f} atingido")

    def registrar(self, provedor: str, modelo: str, entrada: int, saida: int, buscas: int = 0):
        try:
            custo = preco_tokens(modelo, entrada, saida)
        except SemPreco:
            custo = 0.0  # aparece no resumo como modelo sem preço
        custo += buscas * PRECO_BUSCA.get(provedor, 0.0)
        with self._lock:
            self.total += custo
            self.itens.append({"provedor": provedor, "modelo": modelo, "entrada": entrada,
                               "saida": saida, "buscas": buscas, "usd": round(custo, 4)})

    def registrar_valor(self, provedor: str, modelo: str, usd: float):
        """Para APIs que já devolvem o custo da chamada (ex.: DataForSEO)."""
        with self._lock:
            self.total += usd
            self.itens.append({"provedor": provedor, "modelo": modelo, "entrada": 0, "saida": 0,
                               "buscas": 0, "usd": round(usd, 4)})

    def resumo(self) -> dict:
        with self._lock:
            return {"total_usd": round(self.total, 4), "chamadas": len(self.itens),
                    "limite_usd": self.limite, "itens": list(self.itens)}


contador = Contador()


# --------------------------------------------------------------------------
# Livro de gastos: cada execução paga (linha de comando ou app) vira uma linha
# em data/gastos.jsonl. Uso interno da TimeLabs, para conferir o custo real por
# cliente (o cliente paga valor fixo; isso não aparece no app).
# --------------------------------------------------------------------------

GASTOS_ARQ = Path(__file__).parent / "data" / "gastos.jsonl"


def anotar_gasto(tipo: str, cliente_id: str, usd: float) -> None:
    if not usd:
        return
    GASTOS_ARQ.parent.mkdir(parents=True, exist_ok=True)
    linha = {"em": datetime.now().isoformat(timespec="seconds"), "tipo": tipo,
             "cliente": cliente_id, "usd": round(usd, 4)}
    with GASTOS_ARQ.open("a", encoding="utf-8") as f:
        f.write(json.dumps(linha, ensure_ascii=False) + "\n")

