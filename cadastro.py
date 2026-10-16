"""
cadastro.py — Rascunho do cadastro de um cliente a partir do site dele.

Duas etapas:
  ler_site(url)          grátis: baixa a página inicial e até 4 páginas internas
                         (sobre, serviços, contato) e tira nome, WhatsApp, cidade e CNPJ.
  completar_com_ia(...)  uma chamada de IA (nível "extracao"): serviço, nichos, processo,
                         diferenciais, números a confirmar e clientes citados.

A IA só organiza o que está escrito no site. Números e promessas vão para
"afirmações a confirmar", nunca direto para o perfil.
"""

import html
import json
import re
from urllib.parse import urljoin, urlparse

from pydantic import BaseModel, Field

import ia
import rede

NAVEGADOR = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36"
INTERNAS = re.compile(r"sobre|quem-somos|about|servic|solucoes|o-que-fazemos|contato|empresa", re.I)
UFS = {"AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas", "BA": "Bahia", "CE": "Ceará",
       "DF": "Distrito Federal", "ES": "Espírito Santo", "GO": "Goiás", "MA": "Maranhão", "MT": "Mato Grosso",
       "MS": "Mato Grosso do Sul", "MG": "Minas Gerais", "PA": "Pará", "PB": "Paraíba", "PR": "Paraná",
       "PE": "Pernambuco", "PI": "Piauí", "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte",
       "RS": "Rio Grande do Sul", "RO": "Rondônia", "RR": "Roraima", "SC": "Santa Catarina",
       "SP": "São Paulo", "SE": "Sergipe", "TO": "Tocantins"}
MAX_TEXTO = 24000  # caracteres enviados à IA (~7 mil tokens)


class SiteInacessivel(RuntimeError):
    pass


def normalizar(site: str) -> str:
    site = site.strip()
    return site if site.startswith("http") else "https://" + site


def _baixar(url: str) -> str | None:
    r = rede.baixar(url, {"User-Agent": NAVEGADOR})  # só internet pública (nada de 127.0.0.1 ou rede interna)
    return r.text if r is not None and r.status_code == 200 and "html" in r.headers.get("content-type", "") else None


def _texto(pagina: str) -> str:
    s = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>|<!--.*?-->", " ", pagina)
    s = re.sub(r"(?i)<(h[1-6]|p|li|br|div|section|header|footer|tr)[^>]*>", "\n", s)
    s = html.unescape(re.sub(r"<[^>]+>", " ", s))
    linhas, vistas = [], set()
    for trecho in (re.sub(r"\s+", " ", trecho).strip() for trecho in s.split("\n")):
        if len(trecho) > 2 and trecho not in vistas:
            vistas.add(trecho)
            linhas.append(trecho)
    return "\n".join(linhas)


def _jsonld(pagina: str) -> list[dict]:
    itens = []
    for bloco in re.findall(r'(?is)<script[^>]+application/ld\+json[^>]*>(.*?)</script>', pagina):
        try:
            dados = json.loads(bloco)
        except ValueError:
            continue
        for i in (dados.get("@graph", [dados]) if isinstance(dados, dict) else dados):
            if isinstance(i, dict):
                itens.append(i)
    return itens


def _nome(pagina: str, ld: list[dict]) -> str:
    for i in ld:
        if re.search(r"Organization|LocalBusiness|Service", str(i.get("@type"))) and i.get("name"):
            return str(i["name"]).strip()
    if m := re.search(r'(?i)<meta[^>]+property="og:site_name"[^>]+content="([^"]+)"', pagina):
        return html.unescape(m.group(1)).strip()
    titulo = re.search(r"(?is)<title>(.*?)</title>", pagina)
    if titulo:
        partes = re.split(r"\s+[-|–·]\s+", html.unescape(titulo.group(1)).strip())
        return min(partes, key=len) if partes else ""
    return ""


def _whatsapp(pagina: str) -> str:
    m = re.search(r"(?:wa\.me/|phone=)(\d{10,13})", pagina)
    if m:
        return m.group(1)
    m = re.search(r"\(?\b(\d{2})\)?\s?9\d{4}[-\s]?\d{4}\b", _texto(pagina))
    return re.sub(r"\D", "", m.group(0)) if m else ""


def _local(texto: str, ld: list[dict]) -> tuple[str, str]:
    for i in ld:
        end = i.get("address")
        if isinstance(end, dict) and end.get("addressLocality"):
            uf = str(end.get("addressRegion", "")).upper()
            return end["addressLocality"], UFS.get(uf, end.get("addressRegion", ""))
    m = re.search(r"([A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÀ-ú]+(?: (?:de |do |da |dos )?[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÀ-ú]+)*)\s*[-–/,]\s*(" +
                  "|".join(UFS) + r")\b", texto)
    return (m.group(1), UFS[m.group(2)]) if m else ("", "")


def ler_site(site: str) -> dict:
    """Baixa o site (sem IA) e devolve o que dá para tirar com segurança, mais o texto das páginas."""
    base = normalizar(site)
    inicial = _baixar(base)
    if not inicial:
        raise SiteInacessivel(f"Não consegui abrir {base}. Confira o endereço ou se o site bloqueia acesso automático.")
    dominio = urlparse(base).netloc
    links = []
    for href in re.findall(r'href="([^"#]+)"', inicial):
        url = urljoin(base, href)
        if urlparse(url).netloc == dominio and INTERNAS.search(urlparse(url).path) and url not in links:
            links.append(url)
    paginas = {base: inicial}
    for url in links[:4]:
        if conteudo := _baixar(url):
            paginas[url] = conteudo

    ld = [i for p in paginas.values() for i in _jsonld(p)]
    texto = "\n\n".join(f"### {u}\n{_texto(p)}" for u, p in paginas.items())
    cidade, regiao = _local(texto, ld)
    cnpj = re.search(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}", texto)
    return {
        "site": base,
        "nome": _nome(inicial, ld),
        "whatsapp": next((w for w in map(_whatsapp, paginas.values()) if w), ""),
        "cidade": cidade, "regiao": regiao,
        "cnpj": cnpj.group(0) if cnpj else "",
        "paginas": list(paginas),
        "_texto": texto[:MAX_TEXTO],
    }


class PerfilDoSite(BaseModel):
    nome: str = Field(description="Nome da empresa como ela se apresenta")
    servico: str = Field(description="O que a empresa é, do jeito que um cliente procuraria no Google ou no ChatGPT, "
                                     "no singular e sem a cidade. Ex.: 'agência de tráfego pago', 'clínica odontológica'")
    cidade: str = Field(description="Cidade onde atende; vazio se o site não diz")
    regiao: str = Field(description="Estado por extenso; vazio se o site não diz")
    nichos: list[str] = Field(description="Públicos ou segmentos atendidos citados no site")
    servicos: list[str] = Field(description="Serviços oferecidos, uma linha curta cada")
    processo: list[str] = Field(description="Etapas de como trabalha, se o site descreve; senão, vazio")
    diferenciais: list[str] = Field(description="Diferenciais afirmados no site, sem números")
    afirmacoes_a_confirmar: list[str] = Field(description="Números, prêmios, anos de experiência, garantias e "
                                                          "resultados afirmados no site, copiados como estão")
    clientes_citados_no_site: list[str] = Field(description="Nomes de clientes, marcas ou depoimentos citados")
    apelidos: list[str] = Field(description="Outras grafias do nome (sem acento, abreviações, domínio)")
    tom: str = Field(description="Tom de voz do site em uma frase curta")


PROMPT = """Abaixo está o texto do site de uma empresa brasileira. Preencha o cadastro dela.

Regras:
- Use só o que está escrito no texto. Se algo não aparece, deixe vazio. Não invente serviço, nicho nem cidade.
- Qualquer número, resultado, prêmio, tempo de mercado ou garantia vai para afirmacoes_a_confirmar, copiado do site.
  Não repita esses números em diferenciais.
- Linhas curtas e em português, sem marketing ("líder", "melhor do mercado" só se o site disser, e aí vai para afirmações).

Dados já encontrados sem IA (confira, mas não contradiga sem motivo): {basico}

Texto do site:
{texto}
"""


def completar_com_ia(lido: dict) -> dict:
    basico = {k: lido.get(k) for k in ("nome", "cidade", "regiao", "whatsapp", "cnpj")}
    perfil = ia.gerar(PROMPT.format(basico=json.dumps(basico, ensure_ascii=False), texto=lido["_texto"]),
                      PerfilDoSite, esforco="low", max_tokens=4000, nivel="extracao")
    return perfil.model_dump()
