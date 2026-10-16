"""
guias — Os guias do plano de ações, gerados para cada cliente a partir do último radar real.

Cada ação do plano que tem passo a passo ganha um guia em entregas/<cliente>/<nome>.md. O texto
que vale para qualquer cliente (por que pesa, como agir, o que não fazer) vem dos modelos em
guias/modelos/; o que é do cliente (com quem as IAs confundiram a marca, os sites de terceiros que
elas leram, os dados oficiais, os robôs bloqueados) vem do radar, do cadastro e do rastreamento.

Guia escrito à mão (sem a linha "gerado: portal" no cabeçalho) nunca é sobrescrito.

    python main.py guias <cliente>       # também roda sozinho depois de cada radar real
"""

import html
import json
import re
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from config import settings
from radar.analise import PLATAFORMAS, e_fonte_de_lista
from radar.modelos import NOMES_PROVEDOR

MODELOS = Path(__file__).parent / "modelos"
PASTA = settings.BASE_DIR / "entregas"
MARCA = "gerado: portal"

# Markdown, não HTML: o que vem de fora (respostas das IAs, cadastro) é escapado em _t antes de entrar
_env = Environment(loader=FileSystemLoader(MODELOS), undefined=StrictUndefined, trim_blocks=True,
                   lstrip_blocks=True, keep_trailing_newline=True,
                   autoescape=False)  # noqa: S701  # nosec B701


def _t(valor) -> str:
    """Texto de fora que entra no Markdown: sem HTML e sem sintaxe de link, ênfase ou código."""
    texto = html.escape(str(valor or "").strip(), quote=False)
    return re.sub(r"([\\`*_\[\]()#!|])", r"\\\1", texto)


def _lista(valores) -> list[str]:
    return [_t(v) for v in valores or [] if str(v or "").strip()]


def _whatsapp(numero: str) -> str:
    d = re.sub(r"\D", "", numero or "")
    if len(d) == 13 and d.startswith("55"):
        return f"+55 {d[2:4]} {d[4:9]}-{d[9:]}"
    return f"+{d}" if d else ""


def _falha(run: dict, nome: str) -> dict | None:
    return next((c for c in run.get("auditoria") or [] if c["nome"] == nome and not c["ok"]), None)


def _ok(run: dict, nome: str) -> bool:
    return any(c["nome"] == nome and c["ok"] for c in run.get("auditoria") or [])


def _ficha(cli: dict, dominio: str, whatsapp: str) -> str:
    """Bloco JSON-LD da empresa (fica dentro de um bloco de código: sem crase, para não fechá-lo)."""
    def limpo(v: str) -> str:
        return str(v or "").replace("`", "'")

    def frase(v: str) -> str:
        texto = limpo(v).strip()
        return texto[:1].upper() + texto[1:]
    ficha = {
        "@context": "https://schema.org", "@type": "ProfessionalService",
        "@id": f"https://{dominio}/#empresa", "name": limpo(cli["nome"]), "url": limpo(cli["site"]),
        "description": frase(f"{cli.get('segmento', '')} em {cli.get('cidade', '')}"),
        "disambiguatingDescription": frase(f"{cli.get('segmento', '')} de {cli.get('cidade', '')}, site {dominio}."),
        "telephone": whatsapp or "[telefone]",
        "address": {"@type": "PostalAddress", "addressLocality": limpo(cli.get("cidade")),
                    "addressRegion": limpo(cli.get("regiao")), "addressCountry": "BR"},
        "areaServed": [limpo(cli.get("cidade")), limpo(cli.get("regiao"))],
        "taxID": "[CNPJ]",
        "sameAs": ["[link do Wikidata]", "[link do Instagram]", "[link do LinkedIn]",
                   "[link do Perfil da Empresa no Google]"],
    }
    return json.dumps(ficha, ensure_ascii=False, indent=2)


def contexto(cliente: dict, run: dict, rastreio: dict | None = None) -> dict:
    m, r = run["metricas"], run["metricas"]["resumo"]
    perfil = cliente.get("perfil") or {}
    dominio = (cliente.get("dominios") or [""])[0] or re.sub(r"^https?://(www\.)?", "", cliente["site"]).strip("/")
    whatsapp = _whatsapp((perfil.get("cta") or {}).get("whatsapp", ""))
    perguntas = cliente.get("perguntas") or []
    identidade = _falha(run, "Identidade da empresa clara para as IAs")
    robos = _falha(run, "Robôs das IAs conseguem acessar o site")
    robots = _falha(run, "robots.txt libera as IAs")
    # alvo de presença = lista, ranking, diretório ou plataforma. Site genérico de "terceiro" costuma
    # ser de uma empresa do setor (concorrente que o radar não reconheceu pelo nome): fica de fora.
    terceiros = [f for f in m.get("fontes") or [] if not f["dominio"].endswith(("google.com", "google.com.br"))
                 and (f["tipo"] == "plataforma" or (f["tipo"] == "terceiro" and e_fonte_de_lista(f["dominio"])))]
    empresas_fonte = sum(f["tipo"] == "terceiro" and not e_fonte_de_lista(f["dominio"]) for f in m.get("fontes") or [])
    dominios_fonte = {f["dominio"] for f in m.get("fontes") or []}
    paginas_site = [p["url"] for p in (rastreio or {}).get("paginas", []) if p.get("status") == 200]
    return {
        "nome": _t(cliente["nome"]), "site": _t(cliente["site"]), "dominio": _t(dominio),
        "cidade": _t(cliente.get("cidade")), "regiao": _t(cliente.get("regiao")),
        "segmento": _t(cliente.get("segmento")), "whatsapp": whatsapp,
        "data": datetime.fromisoformat(run["gerado_em"]).strftime("%d/%m/%Y"),
        "ias": _lista(NOMES_PROVEDOR.get(p, p) for p in run.get("provedores") or {}),
        "confusoes": [{"ia": _t(NOMES_PROVEDOR.get(c["provedor"], c["provedor"])), "empresa": _t(c["empresa"])}
                      for c in r.get("confusoes") or []],
        "marca_conhecida": r.get("marca_conhecida", 0), "perguntas_marca": r.get("perguntas_marca", 0),
        "pergunta_marca": _t(next((q["texto"] for q in perguntas if q["tipo"] == "marca"), "")),
        "pergunta_exemplo": _t(next((q["texto"] for q in perguntas if q["tipo"] == "descoberta"), "")),
        "faltam_identidade": _lista(identidade["detalhe"].removeprefix("faltam: ").split("; ")) if identidade else [],
        "tem_ficha": _ok(run, "Dados estruturados da empresa"),
        "url_sobre": _t(next((u for u in paginas_site if re.search(r"/(sobre|quem-somos|about)(/|$)", u)), "")),
        "rastreado": rastreio is not None,
        "sem_perfis": bool(identidade and "perfis oficiais" in identidade["detalhe"]),
        "paginas_site": len(paginas_site),
        "afirmacoes": _lista(perfil.get("afirmacoes_a_confirmar")),
        "servicos": _lista(perfil.get("servicos")), "processo": _lista(perfil.get("processo")),
        "nichos": _lista(perfil.get("nichos")),
        "ficha_json": _ficha(cliente, dominio, whatsapp),
        "concorrentes": _lista(e["nome"] for e in m.get("ranking") or [] if not e["e_a_marca"])[:3],
        "terceiros": [{"dominio": _t(f["dominio"]), "vezes": f["respostas"]} for f in terceiros[:6]],
        "empresas_fonte": empresas_fonte,
        "reddit": any(d.endswith("reddit.com") for d in dominios_fonte),
        "youtube": any(d.endswith("youtube.com") for d in dominios_fonte),
        "linkedin": any(d.endswith("linkedin.com") for d in dominios_fonte),
        "paginas_concorrentes": sum(p["tipo"] == "concorrente" for p in m.get("paginas") or []),
        "plataformas_citadas": _lista(d for d in sorted(dominios_fonte) if d in PLATAFORMAS and "google" not in d),
        "sitemap_ok": _ok(run, "Sitemap publicado"),
        "robos_bloqueados": _lista(robos["detalhe"].removeprefix("bloqueados: ").split("; ")) if robos else [],
        "robots_bloqueia": _t(robots["detalhe"].removeprefix("bloqueia: ")) if robots else "",
        "agencia": bool(re.search(r"ag[eê]ncia|marketing|tr[aá]fego|publicidade", cliente.get("segmento", ""), re.I)),
        "e_a_timelabs": cliente["nome"].strip().lower() == "timelabs",
    }


def _relevante(nome: str, ctx: dict) -> bool:
    """O guia de robôs só existe quando o radar achou robô bloqueado; os outros, sempre."""
    if nome == "06-robos-de-treino":
        return bool(ctx["robos_bloqueados"] or ctx["robots_bloqueia"])
    return True


def _escrito_a_mao(caminho: Path) -> bool:
    return caminho.exists() and MARCA not in caminho.read_text(encoding="utf-8")[:600]


def gerar(cliente: dict, run: dict, rastreio: dict | None = None, pasta: Path | None = None) -> list[Path]:
    """Escreve os guias do cliente a partir do radar (só radar real). Devolve os arquivos escritos;
    guia escrito à mão fica como está, e guia gerado que deixou de valer é apagado."""
    if run.get("demo"):
        return []
    destino = (pasta or PASTA) / cliente["id"]
    destino.mkdir(parents=True, exist_ok=True)
    ctx = contexto(cliente, run, rastreio)
    escritos = []
    for modelo in sorted(MODELOS.glob("*.md")):
        caminho = destino / modelo.name
        if _escrito_a_mao(caminho):
            continue
        if not _relevante(modelo.stem, ctx):
            caminho.unlink(missing_ok=True)
            continue
        caminho.write_text(_env.get_template(modelo.name).render(**ctx), encoding="utf-8")
        escritos.append(caminho)
    return escritos
