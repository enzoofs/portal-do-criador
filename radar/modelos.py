"""
radar/modelos.py — Estruturas de dados do radar de visibilidade em IA.
"""

from dataclasses import asdict, dataclass, field
from urllib.parse import urlparse


def dominio_de(url: str) -> str:
    """Extrai o domínio sem 'www.' de uma URL (ou devolve o texto como veio)."""
    host = urlparse(url).netloc or url
    return host.lower().removeprefix("www.")


NOMES_PROVEDOR = {"chatgpt": "ChatGPT", "claude": "Claude", "gemini": "Gemini",
                  "chatgpt_app": "ChatGPT (app)", "gemini_app": "Gemini (app)",
                  "google_ia": "Google (resumo de IA)", "google_modo": "Google (modo IA)"}
# Como cada provedor coleta: pela API do modelo ou como o usuário vê no app/site
COLETA_APP = {"chatgpt_app", "gemini_app", "google_ia", "google_modo"}


def descrever_coleta(provedores) -> str:
    """'coleta como aparece para o usuário' / 'coleta via API' / misto, para notas de método."""
    app = [p for p in provedores if p in COLETA_APP]
    if app and len(app) == len(list(provedores)):
        return "coleta como aparece para o usuário (app e Google)"
    if app:
        nomes = ", ".join(NOMES_PROVEDOR.get(p, p) for p in app)
        return f"coleta como aparece para o usuário em {nomes} e via API nas demais"
    return "coleta via API"


def numero_br(valor) -> str:
    """Número no padrão brasileiro: 16,7 (e 50 em vez de 50,0)."""
    return f"{valor:g}".replace(".", ",")


@dataclass
class Fonte:
    """Página que a IA citou ou consultou para montar a resposta."""
    url: str
    titulo: str = ""
    dominio: str = ""

    def __post_init__(self):
        if not self.dominio:
            self.dominio = dominio_de(self.url)


@dataclass
class Resposta:
    """Uma resposta de um provedor de IA para uma pergunta do cliente."""
    provedor: str
    modelo: str
    pergunta: str
    tipo_pergunta: str
    texto: str = ""
    fontes: list[Fonte] = field(default_factory=list)
    erro: str | None = None
    buscas: list[str] = field(default_factory=list)   # o que a IA pesquisou antes de responder
    marcas_destacadas: list[str] = field(default_factory=list)  # marcas que o app destacou (DataForSEO)
    # Preenchidos pelo extrator depois da consulta
    marca_mencionada: bool = False
    marca_citada_como_fonte: bool = False
    empresas_recomendadas: list[str] = field(default_factory=list)
    posicao_marca: int | None = None   # 1 = primeira empresa recomendada
    # Só em perguntas de "marca": a IA falou da empresa certa?
    empresa_certa: bool | None = None
    tem_informacao: bool | None = None
    empresa_confundida: str | None = None
    resumo_marca: str = ""

    def to_dict(self) -> dict:
        return asdict(self)
