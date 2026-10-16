"""
radar/provedores/base.py — Interface comum dos provedores de IA.

Cada provedor recebe a pergunta "como um usuário faria" e devolve a
resposta com as fontes da web que usou. A busca na web fica sempre ligada:
sem ela a resposta da API não reflete o que o usuário vê no app.
"""

from abc import ABC, abstractmethod

from radar.modelos import Resposta

# Instrução mínima: só situa o assistente no país/cidade do cliente, sem
# induzir a resposta (o objetivo é medir o comportamento natural da IA).
SISTEMA = (
    "Você é um assistente respondendo a um usuário que mora em {cidade}, "
    "{regiao}, Brasil. Responda em português do Brasil."
)


class Provedor(ABC):
    nome: str
    modelo: str

    @abstractmethod
    def perguntar(self, pergunta: str, tipo: str, cliente: dict) -> Resposta:
        """Faz a pergunta com busca na web e devolve a resposta normalizada."""
