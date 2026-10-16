"""
site_cliente/inicial.py — Primeiro rascunho do site de um cliente, a partir do cadastro.

Usa só o que já está no cadastro (config/clientes/<id>.json): nome, site, cidade, serviço,
nichos, processo, diferenciais, WhatsApp e autor. Nada é inventado: número, depoimento e dado
oficial ficam para o editor. Cria também um logo de texto e uma imagem de compartilhamento
provisórios, para o site já gerar e o cliente ver algo no primeiro clique.
"""

import json
import re

from conteudo.pauta import slugify
from site_cliente import gerador

UF = {"Acre": "AC", "Alagoas": "AL", "Amapá": "AP", "Amazonas": "AM", "Bahia": "BA", "Ceará": "CE",
      "Distrito Federal": "DF", "Espírito Santo": "ES", "Goiás": "GO", "Maranhão": "MA", "Mato Grosso": "MT",
      "Mato Grosso do Sul": "MS", "Minas Gerais": "MG", "Pará": "PA", "Paraíba": "PB", "Paraná": "PR",
      "Pernambuco": "PE", "Piauí": "PI", "Rio de Janeiro": "RJ", "Rio Grande do Norte": "RN",
      "Rio Grande do Sul": "RS", "Rondônia": "RO", "Roraima": "RR", "Santa Catarina": "SC", "São Paulo": "SP",
      "Sergipe": "SE", "Tocantins": "TO"}
CORES_PADRAO = {"fundo": "#101318", "fundo_2": "#171b22", "fundo_3": "#1f2530", "texto": "#eef1f6", "suave": "#a7afbf",
                "destaque": "#3ddc97", "destaque_hover": "#6ee7b3", "texto_no_destaque": "#06140d", "secundaria": "#5b8cff"}


def _whatsapp_exibir(numero: str) -> str:
    n = re.sub(r"\D", "", numero)
    if len(n) == 13:
        return f"+{n[:2]} {n[2:4]} {n[4:9]}-{n[9:]}"
    if len(n) == 12:
        return f"+{n[:2]} {n[2:4]} {n[4:8]}-{n[8:]}"
    return numero


def _imagens_provisorias(pasta, nome: str, cores: dict) -> None:
    """Logo de texto, ícone com a inicial e imagem de compartilhamento 1200x630."""
    from PIL import Image, ImageDraw, ImageFont
    pasta.mkdir(parents=True, exist_ok=True)
    seguro = nome.replace("&", "&amp;").replace("<", "").replace(">", "")
    (pasta / "logo.svg").write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {40 + 22 * len(nome)} 60">'
        f'<text x="0" y="42" font-family="Arial, sans-serif" font-size="36" font-weight="700" fill="{cores["texto"]}">{seguro}</text></svg>',
        encoding="utf-8")
    (pasta / "icone.svg").write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="{cores["destaque"]}"/>'
        f'<text x="32" y="44" text-anchor="middle" font-family="Arial, sans-serif" font-size="36" font-weight="700" '
        f'fill="{cores["texto_no_destaque"]}">{seguro[:1].upper()}</text></svg>', encoding="utf-8")
    im = Image.new("RGB", (1200, 630), cores["fundo"])
    d = ImageDraw.Draw(im)
    try:
        fonte = ImageFont.truetype("arialbd.ttf", 84)
    except OSError:
        fonte = ImageFont.load_default()
    d.rectangle([80, 270, 200, 282], fill=cores["destaque"])
    d.text((80, 300), nome, font=fonte, fill=cores["texto"])
    im.save(pasta / "compartilhar.png", optimize=True)


def criar(cid: str) -> dict:
    pasta = gerador.pasta_site(cid)
    if (pasta / "site.json").exists():
        raise FileExistsError("Este cliente já tem site.")
    c = json.loads((gerador.settings.CLIENTES_DIR / f"{cid}.json").read_text(encoding="utf-8"))
    perfil = c.get("perfil") or {}
    nome, cidade = c["nome"], c.get("cidade", "")
    servico = (c.get("segmento") or "serviço").split("/")[0].strip()
    whatsapp = re.sub(r"\D", "", (perfil.get("cta") or {}).get("whatsapp", ""))
    autor = perfil.get("autor") or {}
    dominio = re.sub(r"/+$", "", re.sub(r"^http://", "https://", c["site"]))
    _imagens_provisorias(pasta / "assets", nome, CORES_PADRAO)

    servicos = [{"nome": x, "texto": ""} for x in perfil.get("servicos", [])][:6]
    etapas = []
    for linha in perfil.get("processo", [])[:6]:
        titulo, _, texto = linha.partition(":")
        etapas.append({"nome": titulo.strip(), "texto": texto.strip(), "imagem": ""})
    pagina_servico = slugify(f"{servico} {cidade}")
    perguntas = [{"pergunta": f"Onde fica a {nome}?", "resposta": f"Em {cidade}, {c.get('regiao', '')}.".replace(", .", ".")}]
    if perfil.get("servicos"):
        perguntas.append({"pergunta": f"Quais serviços a {nome} oferece?", "resposta": "; ".join(perfil["servicos"]) + "."})

    inicio = [
        {"tipo": "abertura", "olho": f"{servico} em {cidade}", "titulo": f"{servico[:1].upper()}{servico[1:]} em {cidade}",
         "titulo_destaque": "", "subtitulo": (perfil.get("diferenciais") or [""])[0], "botao": "Falar no WhatsApp",
         "botao2_texto": "", "botao2_pagina": pagina_servico, "imagem_fundo": ""},
    ]
    if perfil.get("nichos") or perfil.get("diferenciais"):
        inicio.append({"tipo": "para_quem", "olho": "Para quem é", "titulo": f"Para quem a {nome} trabalha", "texto": "",
                       "dores": perfil.get("diferenciais", [])[1:5], "segmentos": perfil.get("nichos", []), "nota": ""})
    if servicos:
        inicio.append({"tipo": "servicos", "olho": "O que fazemos", "titulo": "Serviços", "itens": servicos})
    if len(etapas) >= 2:
        inicio.append({"tipo": "processo", "olho": "Como trabalhamos", "titulo": "Nosso processo", "texto": "", "estilo": "lista", "etapas": etapas})
    inicio += [{"tipo": "blog_recente", "olho": "Blog", "titulo": "Do nosso blog", "texto": "", "quantidade": 3},
               {"tipo": "perguntas", "olho": "Perguntas frequentes", "titulo": "Perguntas frequentes", "itens": perguntas},
               {"tipo": "chamada_final", "olho": "Vamos conversar", "titulo": f"Fale com a {nome}", "texto": "", "imagem_fundo": ""}]

    sobre = [{"tipo": "cabecalho_pagina", "titulo": f"Sobre a {nome}", "resumo": "", "mostrar_botao": False}]
    if autor.get("nome"):
        sobre.append({"tipo": "sobre_fundador", "olho": "Quem está por trás", "titulo": f"{autor['nome']}, {autor.get('cargo', '')}".strip(", "), "foto": ""})
    if servicos:
        sobre.append({"tipo": "servicos", "olho": "O que fazemos", "titulo": "Serviços", "itens": servicos})
    sobre += [{"tipo": "ficha_empresa", "olho": "Dados da empresa", "titulo": "Quem somos, oficialmente"},
              {"tipo": "chamada_final", "olho": "Vamos conversar", "titulo": f"Fale com a {nome}", "texto": "", "imagem_fundo": ""}]

    pag_servico = [{"tipo": "cabecalho_pagina", "titulo": f"{servico[:1].upper()}{servico[1:]} em {cidade}", "resumo": "", "mostrar_botao": True},
                   {"tipo": "texto", "olho": "", "titulo": "", "secoes": [{"titulo": f"Como a {nome} trabalha", "texto":
                    " ".join(perfil.get("diferenciais", [])) or "Escreva aqui como a empresa atende quem procura este serviço na cidade."}]},
                   {"tipo": "perguntas", "olho": "Perguntas frequentes", "titulo": f"Perguntas sobre {servico} em {cidade}", "itens": perguntas[:1]},
                   {"tipo": "chamada_final", "olho": "Vamos conversar", "titulo": f"Fale com a {nome}", "texto": "", "imagem_fundo": ""}]

    def descricao(texto: str) -> str:
        return texto if len(texto) <= 160 else texto[:157].rsplit(" ", 1)[0] + "…"

    site = {
        "versao": 2, "_fonte": f"Rascunho criado do cadastro de {nome}. Revise tudo antes de publicar.",
        "dominio": dominio, "idioma": "pt-BR",
        "marca": {"logo": "logo.svg", "icone": "icone.svg", "imagem_compartilhamento": "compartilhar.png",
                  "fontes": {"titulo": "Sora", "corpo": "Manrope"}, "cores": CORES_PADRAO},
        "empresa": {"nome": nome, "razao_social": "", "cnpj": "", "descricao": descricao(f"{servico[:1].upper()}{servico[1:]} em {cidade}."),
                    "desde": None, "cidade": cidade, "uf": UF.get(c.get("regiao", ""), c.get("regiao", "")[:2].upper()),
                    "endereco": "", "email": "", "whatsapp": whatsapp, "whatsapp_exibir": _whatsapp_exibir(whatsapp),
                    "mensagem_whatsapp": "Olá! Vim pelo site e quero saber mais.", "formulario": "",
                    "perfis": {"instagram": "", "linkedin": "", "google": ""}, "atende": cidade},
        "fundador": {"nome": autor.get("nome", ""), "cargo": autor.get("cargo", ""), "bio": [autor["bio"]] if autor.get("bio") else [], "destaques": []},
        "blog": {"ativo": True, "titulo": f"Blog da {nome}", "texto": "", "rotulo_menu": "Blog"},
        "paginas": [
            {"slug": "", "tipo": "inicio", "titulo_pagina": f"{nome} | {servico} em {cidade}"[:60], "descricao": descricao(
                f"{servico[:1].upper()}{servico[1:]} em {cidade}. Fale com a {nome} pelo WhatsApp."), "menu": "", "blocos": inicio},
            {"slug": "sobre", "tipo": "sobre", "titulo_pagina": f"Sobre a {nome}"[:60], "descricao": descricao(
                f"Conheça a {nome}: quem somos, o que fazemos em {cidade} e nossos dados oficiais."), "menu": "Sobre", "blocos": sobre},
            {"slug": pagina_servico, "tipo": "servico", "titulo_pagina": f"{servico} em {cidade} | {nome}"[:60], "descricao": descricao(
                f"{servico[:1].upper()}{servico[1:]} em {cidade} com a {nome}."), "menu": f"{servico[:1].upper()}{servico[1:]} em {cidade}",
             "servico_nome": servico, "blocos": pag_servico},
        ],
    }
    (pasta / "site.json").write_text(json.dumps(site, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return site
