"""
radar/provedores/demo_provedor.py — Respostas FICTÍCIAS para testar o fluxo.

Usado quando não há nenhuma chave de API (ou com --demo). Os nomes de
agências são inventados e o relatório sai com a faixa "dados de
demonstração" — nunca apresentar isso como medição real.
"""

import hashlib

from radar.modelos import Fonte, Resposta
from radar.provedores.base import Provedor

AGENCIAS_FICTICIAS = [
    "Agência Alfa Performance", "Beta Growth BH", "Gama Ads", "Delta Marketing Digital",
    "Épsilon Tráfego", "Zeta Conversão",
]

FONTES_FICTICIAS = [
    ("https://www.google.com/maps/search/agencia+trafego+pago+bh", "Google Maps"),
    ("https://www.instagram.com/agenciaalfaperformance", "Instagram"),
    ("https://clutch.co/br/agencies/ppc/belo-horizonte", "Clutch — PPC Agencies"),
    ("https://blog-exemplo-marketing.com.br/melhores-agencias-bh", "Ranking de agências em BH"),
    ("https://www.reclameaqui.com.br/empresa/exemplo", "Reclame Aqui"),
    ("https://www.linkedin.com/company/beta-growth-bh", "LinkedIn"),
]


def _semente(*partes: str) -> int:
    return int(hashlib.sha256("|".join(partes).encode()).hexdigest(), 16)


class DemoProvedor(Provedor):
    def __init__(self, nome: str, chance_marca: int):
        # chance_marca: em quantas de cada 10 perguntas de descoberta a marca aparece
        self.nome = nome
        self.modelo = f"demo-{nome}"
        self.chance_marca = chance_marca

    def perguntar(self, pergunta: str, tipo: str, cliente: dict) -> Resposta:
        s = _semente(self.nome, pergunta)
        if tipo == "marca":
            conhece = s % 2 == 0
            texto = (
                f"A **{cliente['nome']}** é uma agência de Belo Horizonte focada em tráfego pago "
                f"(Google e Meta Ads). O site ({cliente['dominios'][0]}) apresenta um processo em "
                "4 etapas, mas encontrei poucas avaliações públicas de clientes para confirmar resultados."
                if conhece else
                f"Não encontrei informações suficientes sobre a {cliente['nome']} para avaliar. "
                "Recomendo verificar avaliações no Google e cases publicados."
            )
            fontes = [Fonte(cliente["site"], cliente["nome"])] if conhece else []
            return Resposta(self.nome, self.modelo, pergunta, tipo, texto, fontes,
                            buscas=[f"{cliente['nome'].lower()} avaliações"])

        k = 3 + s % 2
        inicio = s % len(AGENCIAS_FICTICIAS)
        nomes = [AGENCIAS_FICTICIAS[(inicio + i) % len(AGENCIAS_FICTICIAS)] for i in range(k)]
        if s % 10 < self.chance_marca:
            nomes.insert(min(2, len(nomes)), cliente["nome"])
        linhas = [f"{i}. **{n}** — atende negócios locais com campanhas de Google e Meta Ads."
                  for i, n in enumerate(nomes, start=1)]
        texto = "Algumas opções bem avaliadas em BH:\n\n" + "\n".join(linhas)
        fontes = [Fonte(u, t) for u, t in FONTES_FICTICIAS if _semente(u, pergunta, self.nome) % 3]
        q = pergunta.lower().rstrip("?. ")
        return Resposta(self.nome, self.modelo, pergunta, tipo, texto, fontes,
                        buscas=[q, f"{q} 2026", f"{q} avaliações"])


def provedores_demo() -> list[DemoProvedor]:
    return [DemoProvedor("chatgpt", 2), DemoProvedor("claude", 0), DemoProvedor("gemini", 3)]
