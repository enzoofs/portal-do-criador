"""
radar/extrator.py — Lê cada resposta e marca o que importa para o relatório.

- Menção da marca e citação do site: regra determinística (apelidos/domínios),
  sem custo e sem risco de alucinação.
- Lista de empresas recomendadas, em ordem: um modelo de IA lê a resposta e
  devolve JSON validado. Sem chave nenhuma, cai numa heurística simples
  (nomes em **negrito**), suficiente para o modo demonstração.
"""

import re
import unicodedata

from pydantic import BaseModel

import ia
from radar.modelos import Resposta

PROMPT_EXTRACAO = """Abaixo está a resposta de um assistente de IA para a pergunta de um usuário.
Liste, na ordem em que aparecem, as empresas, agências ou profissionais que a resposta
recomenda ou sugere ao usuário. Use o nome como aparece no texto. Não inclua
plataformas genéricas (Google, Instagram, Meta, LinkedIn, Clutch, Reclame Aqui etc.)
a menos que sejam recomendadas como prestadoras do serviço. Também não inclua sites de
ranking, listas de "melhores", guias, diretórios, portais de notícia ou de avaliação que a
resposta usou como fonte: só quem presta o serviço. Se nenhuma for recomendada,
devolva a lista vazia.

Pergunta: {pergunta}

Resposta:
{texto}"""


PROMPT_MARCA = """Um usuário perguntou a um assistente de IA sobre a empresa {nome}
(site oficial: {site}; {segmento} em {cidade}). Leia a resposta e avalie:

- empresa_certa: a resposta fala da empresa do site oficial acima? Falso se ela trata de outra
  empresa de nome parecido (outro site, outro CNPJ, outro foco) como se fosse a mesma.
- tem_informacao: a resposta traz informação concreta sobre a empresa certa (não só
  "não encontrei" ou dicas genéricas de como avaliar uma agência)?
- empresa_confundida: nome e site da outra empresa, se houve confusão; senão vazio.
- resumo: uma frase dizendo o que a IA comunicou ao usuário sobre a empresa.

Pergunta: {pergunta}

Resposta:
{texto}"""


class EmpresasRecomendadas(BaseModel):
    empresas: list[str]


class VerificacaoMarca(BaseModel):
    empresa_certa: bool
    tem_informacao: bool
    empresa_confundida: str
    resumo: str


def normalizar(texto: str) -> str:
    """minúsculas, sem acento e sem pontuação — para comparar nomes."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", sem_acento.lower()).strip()


def e_a_marca(nome: str, cliente: dict) -> bool:
    n = normalizar(nome)
    return any(normalizar(a) in n or n in normalizar(a) for a in cliente["apelidos"] if n)


def _extrair_com_ia(r: Resposta) -> list[str]:
    resultado = ia.gerar(PROMPT_EXTRACAO.format(pergunta=r.pergunta, texto=r.texto),
                         EmpresasRecomendadas, esforco="low", max_tokens=2000, nivel="extracao")
    return resultado.empresas


def _extrair_heuristica(r: Resposta) -> list[str]:
    vistos = []
    for nome in re.findall(r"\*\*([^*]{2,60})\*\*", r.texto):
        nome = nome.strip(" :.-")
        if nome not in vistos:
            vistos.append(nome)
    return vistos


def extrator_disponivel() -> str:
    """Nome do extrator que será usado com as chaves configuradas."""
    return ia.provedor_disponivel() or "heuristica"


_EXTRATORES = {
    "claude": _extrair_com_ia,
    "openai": _extrair_com_ia,
    "heuristica": _extrair_heuristica,
}


def analisar(r: Resposta, cliente: dict, extrator: str) -> Resposta:
    if r.erro or not r.texto:
        return r

    texto_norm = normalizar(r.texto)
    r.marca_mencionada = any(normalizar(a) in texto_norm for a in cliente["apelidos"]) or any(
        d in r.texto.lower() for d in cliente["dominios"])
    r.marca_citada_como_fonte = any(
        any(f.dominio.endswith(d) for d in cliente["dominios"]) for f in r.fontes)

    if r.tipo_pergunta == "marca" and extrator != "heuristica":
        v = ia.gerar(PROMPT_MARCA.format(pergunta=r.pergunta, texto=r.texto, nome=cliente["nome"],
                                         site=cliente["site"], segmento=cliente["segmento"],
                                         cidade=cliente["cidade"]),
                     VerificacaoMarca, esforco="low", max_tokens=2000, nivel="extracao")
        r.empresa_certa, r.tem_informacao = v.empresa_certa, v.tem_informacao
        r.empresa_confundida, r.resumo_marca = v.empresa_confundida or None, v.resumo
        return r

    from radar.analise import e_fonte_de_lista
    r.empresas_recomendadas = [n for n in _EXTRATORES[extrator](r) if not e_fonte_de_lista(n)]
    for i, nome in enumerate(r.empresas_recomendadas, start=1):
        if e_a_marca(nome, cliente):
            r.posicao_marca = i
            break
    return r
