"""
orcamento.py — Estimativas de custo antes de qualquer execução paga.

Usado pela linha de comando (main.py) e pelo app (janela de confirmação).
Cada função devolve linhas (descrição, US$) — nada aqui chama API paga.
"""

import custos
import ia
from radar.executor import carregar_cliente
from radar.modelos import NOMES_PROVEDOR
from radar.provedores import provedores_reais


def _plural(n: int, um: str, varios: str) -> str:
    return f"{n} {um if n == 1 else varios}"


def linha_geracao(nivel: str, tipo: str, chamadas: int, rotulo: str) -> tuple[str, float]:
    """tipo é o perfil de custo (custos.PERFIL_CHAMADA); rotulo é o que a pessoa lê."""
    provedor = ia.provedor_disponivel()
    if not provedor:
        return (f"{rotulo} (sem chave de IA)", 0.0)
    modelo = ia.modelo_de(provedor, nivel)
    return (f"{rotulo} ({modelo})", custos.estimar(tipo, modelo, chamadas=chamadas))


def radar(cliente_id: str, filtro: list[str] | None = None, repeticoes: int = 1) -> list[tuple[str, float]]:
    n = len(carregar_cliente(cliente_id)["perguntas"]) * repeticoes
    linhas = []
    for p in provedores_reais(filtro):
        nome = NOMES_PROVEDOR.get(p.nome, p.nome)
        if p.nome in custos.PRECO_CHAMADA:   # coleta como no app, preço fixo por pergunta
            linhas.append((f"{_plural(n, 'pergunta', 'perguntas')} ao {nome}, como aparece para o usuário",
                           custos.PRECO_CHAMADA[p.nome] * n))
        else:
            linhas.append((f"{_plural(n, 'pergunta', 'perguntas')} ao {nome} ({p.modelo}, com busca na web)",
                           custos.estimar("radar", p.modelo, p.nome, chamadas=n)))
    if linhas:
        total = n * len(linhas)
        linhas.append(linha_geracao("extracao", "extracao", total,
                                    f"Leitura das {_plural(total, 'resposta', 'respostas')}"))
    return linhas


def pauta() -> list[tuple[str, float]]:
    return [linha_geracao("redacao", "pauta", 1, "Pauta de conteúdo")]


def artigos(quantidade: int) -> list[tuple[str, float]]:
    return [linha_geracao("redacao", "artigo", quantidade, _plural(quantidade, "artigo", "artigos"))]
