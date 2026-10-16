"""
site_cliente/blocos.py — Catálogo de blocos dos sites e validação do site.json.

Cada página é uma lista de blocos; cada bloco declara os próprios campos (como as seções com
schema do Shopify ou os componentes do Puck). O editor do Portal monta os formulários a partir
destas declarações, e o gerador desenha cada bloco com modelos/blocos/<tipo>.html.

Tipos de campo:
    texto, texto_longo, lista (uma linha por item), imagem (arquivo em assets/), numero,
    opcao (com "opcoes"), sim_nao, itens (lista de objetos com "campos" próprios)

Regra de produto: nenhum campo aceita HTML. Destaque de título é um campo separado.
"""

import re

# ---------------------------------------------------------------- campos reutilizados
OLHO = {"nome": "olho", "tipo": "texto", "rotulo": "Rótulo acima do título", "ajuda": "Curto, em maiúsculas no site. Ex.: Como trabalhamos"}
TITULO = {"nome": "titulo", "tipo": "texto", "rotulo": "Título", "obrigatorio": True}
TEXTO = {"nome": "texto", "tipo": "texto_longo", "rotulo": "Texto de apoio"}
FUNDO = {"nome": "imagem_fundo", "tipo": "imagem", "rotulo": "Imagem de fundo", "ajuda": "Foto larga, com o assunto à direita."}

BLOCOS: dict[str, dict] = {
    "abertura": {
        "rotulo": "Abertura", "descricao": "Primeira dobra da página: título grande, texto e botões.",
        "campos": [OLHO, {"nome": "titulo", "tipo": "texto", "rotulo": "Título", "obrigatorio": True},
                   {"nome": "titulo_destaque", "tipo": "texto", "rotulo": "Continuação do título em destaque", "ajuda": "Aparece na cor de destaque, logo após o título."},
                   {"nome": "subtitulo", "tipo": "texto_longo", "rotulo": "Subtítulo"},
                   {"nome": "botao", "tipo": "texto", "rotulo": "Texto do botão do WhatsApp", "padrao": "Falar no WhatsApp"},
                   {"nome": "botao2_texto", "tipo": "texto", "rotulo": "Segundo botão: texto"},
                   {"nome": "botao2_pagina", "tipo": "pagina", "rotulo": "Segundo botão: leva para a página"},
                   FUNDO],
    },
    "cabecalho_pagina": {
        "rotulo": "Cabeçalho de página", "descricao": "Título principal (H1) e resumo de uma página interna.",
        "campos": [{"nome": "titulo", "tipo": "texto", "rotulo": "Título da página (H1)", "obrigatorio": True},
                   {"nome": "resumo", "tipo": "texto_longo", "rotulo": "Resumo", "ajuda": "Uma ou duas frases que respondem direto o que a página promete. As IAs costumam citar esse trecho."},
                   {"nome": "mostrar_botao", "tipo": "sim_nao", "rotulo": "Mostrar botão do WhatsApp", "padrao": True}],
    },
    "numeros": {
        "rotulo": "Números", "descricao": "Faixa com números da empresa. Só use números confirmados.",
        "campos": [{"nome": "itens", "tipo": "itens", "rotulo": "Números", "minimo": 1, "maximo": 6,
                    "campos": [{"nome": "valor", "tipo": "texto", "rotulo": "Valor", "obrigatorio": True},
                               {"nome": "rotulo", "tipo": "texto", "rotulo": "O que significa", "obrigatorio": True}]}],
    },
    "para_quem": {
        "rotulo": "Para quem é", "descricao": "Dores do cliente ideal e segmentos atendidos.",
        "campos": [OLHO, TITULO, TEXTO, {"nome": "dores", "tipo": "lista", "rotulo": "Dores (uma por linha)"},
                   {"nome": "segmentos", "tipo": "lista", "rotulo": "Segmentos atendidos (um por linha)"},
                   {"nome": "nota", "tipo": "texto_longo", "rotulo": "Nota no fim do bloco"}],
    },
    "servicos": {
        "rotulo": "Serviços", "descricao": "O que a empresa faz, em até três colunas.",
        "campos": [OLHO, TITULO, {"nome": "itens", "tipo": "itens", "rotulo": "Serviços", "minimo": 1, "maximo": 6,
                                  "campos": [{"nome": "nome", "tipo": "texto", "rotulo": "Serviço", "obrigatorio": True},
                                             {"nome": "texto", "tipo": "texto_longo", "rotulo": "Descrição"}]}],
    },
    "processo": {
        "rotulo": "Processo", "descricao": "Como a empresa trabalha, em etapas.",
        "campos": [OLHO, TITULO, TEXTO,
                   {"nome": "estilo", "tipo": "opcao", "rotulo": "Estilo", "opcoes": [["cartoes", "Cartões com ilustração"], ["lista", "Lista simples"]], "padrao": "cartoes"},
                   {"nome": "etapas", "tipo": "itens", "rotulo": "Etapas", "minimo": 2, "maximo": 6,
                    "campos": [{"nome": "nome", "tipo": "texto", "rotulo": "Etapa", "obrigatorio": True},
                               {"nome": "texto", "tipo": "texto_longo", "rotulo": "Descrição"},
                               {"nome": "imagem", "tipo": "imagem", "rotulo": "Ilustração"}]}],
    },
    "depoimentos": {
        "rotulo": "Depoimentos", "descricao": "O que os clientes dizem, nas palavras deles.",
        "campos": [OLHO, TITULO, TEXTO, {"nome": "maximo", "tipo": "numero", "rotulo": "Mostrar no máximo", "padrao": 6},
                   {"nome": "itens", "tipo": "itens", "rotulo": "Depoimentos", "minimo": 1, "maximo": 12,
                    "campos": [{"nome": "texto", "tipo": "texto_longo", "rotulo": "Depoimento", "obrigatorio": True},
                               {"nome": "nome", "tipo": "texto", "rotulo": "Nome", "obrigatorio": True},
                               {"nome": "empresa", "tipo": "texto", "rotulo": "Empresa"},
                               {"nome": "video", "tipo": "texto", "rotulo": "Link do vídeo (opcional)"}]}],
    },
    "fundador": {
        "rotulo": "Fundador em destaque", "descricao": "Faixa com a bio do fundador (vem de Configurações) sobre uma foto larga.",
        "campos": [OLHO, TITULO, FUNDO, {"nome": "link_sobre", "tipo": "sim_nao", "rotulo": "Mostrar link para a página Sobre", "padrao": True}],
    },
    "sobre_fundador": {
        "rotulo": "Sobre o fundador", "descricao": "Bio do fundador com foto de retrato (bio vem de Configurações).",
        "campos": [OLHO, TITULO, {"nome": "foto", "tipo": "imagem", "rotulo": "Foto de retrato"}],
    },
    "ficha_empresa": {
        "rotulo": "Dados da empresa", "descricao": "CNPJ, endereço e perfis oficiais. É o que prova para as IAs quem é a empresa.",
        "campos": [OLHO, TITULO],
    },
    "texto": {
        "rotulo": "Texto", "descricao": "Seções de texto com subtítulo. Bom para páginas de serviço.",
        "campos": [OLHO, {"nome": "titulo", "tipo": "texto", "rotulo": "Título"},
                   {"nome": "secoes", "tipo": "itens", "rotulo": "Seções", "minimo": 1, "maximo": 12,
                    "campos": [{"nome": "titulo", "tipo": "texto", "rotulo": "Subtítulo (de preferência uma pergunta)"},
                               {"nome": "texto", "tipo": "texto_longo", "rotulo": "Texto", "obrigatorio": True,
                                "ajuda": "Linha em branco separa parágrafos."}]}],
    },
    "blog_recente": {
        "rotulo": "Artigos recentes", "descricao": "Últimos artigos do blog. Some sozinho se não houver artigo publicado.",
        "campos": [OLHO, TITULO, TEXTO, {"nome": "quantidade", "tipo": "numero", "rotulo": "Quantos artigos", "padrao": 3}],
    },
    "perguntas": {
        "rotulo": "Perguntas frequentes", "descricao": "Vira ficha FAQ para o Google e as IAs automaticamente.",
        "campos": [OLHO, TITULO, {"nome": "itens", "tipo": "itens", "rotulo": "Perguntas", "minimo": 1, "maximo": 15,
                                  "campos": [{"nome": "pergunta", "tipo": "texto", "rotulo": "Pergunta", "obrigatorio": True},
                                             {"nome": "resposta", "tipo": "texto_longo", "rotulo": "Resposta", "obrigatorio": True}]}],
    },
    "chamada_final": {
        "rotulo": "Chamada final", "descricao": "Fecho da página com WhatsApp e formulário.",
        "campos": [OLHO, TITULO, TEXTO, FUNDO],
    },
}

FONTES = ["Sora", "Manrope", "Inter", "DM Sans", "Plus Jakarta Sans", "Outfit", "Figtree", "Lexend", "Poppins",
          "Montserrat", "Raleway", "Work Sans", "Nunito", "Lato", "Open Sans", "Archivo", "Space Grotesk",
          "Playfair Display", "Fraunces", "Merriweather"]
_FONTES = [[f, f] for f in FONTES]


def _cor(nome, rotulo):
    return {"nome": nome, "tipo": "cor", "rotulo": rotulo, "obrigatorio": True}


# Configurações do site inteiro, em grupos. "caminho" é onde o grupo mora no site.json.
CONFIGURACOES = [
    {"grupo": "Empresa", "caminho": "empresa", "campos": [
        {"nome": "nome", "tipo": "texto", "rotulo": "Nome da empresa", "obrigatorio": True},
        {"nome": "descricao", "tipo": "texto_longo", "rotulo": "O que a empresa faz, em uma frase", "obrigatorio": True,
         "ajuda": "Vai para a ficha da empresa que o Google e as IAs leem."},
        {"nome": "cidade", "tipo": "texto", "rotulo": "Cidade", "obrigatorio": True},
        {"nome": "uf", "tipo": "texto", "rotulo": "Estado (sigla)", "obrigatorio": True},
        {"nome": "atende", "tipo": "texto", "rotulo": "Região atendida", "ajuda": "Ex.: Belo Horizonte e todo o Brasil"},
        {"nome": "desde", "tipo": "numero", "rotulo": "Ano de fundação"},
        {"nome": "whatsapp", "tipo": "texto", "rotulo": "WhatsApp (só números, com 55 e DDD)", "obrigatorio": True},
        {"nome": "whatsapp_exibir", "tipo": "texto", "rotulo": "WhatsApp como aparece no site", "obrigatorio": True},
        {"nome": "mensagem_whatsapp", "tipo": "texto", "rotulo": "Mensagem que já vem escrita no WhatsApp", "obrigatorio": True},
        {"nome": "formulario", "tipo": "link", "rotulo": "Link do formulário de contato (opcional)"}]},
    {"grupo": "Dados oficiais", "caminho": "empresa",
     "ajuda": "Provam para as IAs qual empresa é esta. Campo vazio não aparece no site publicado.",
     "campos": [
        {"nome": "razao_social", "tipo": "texto", "rotulo": "Razão social"},
        {"nome": "cnpj", "tipo": "texto", "rotulo": "CNPJ", "ajuda": "00.000.000/0000-00"},
        {"nome": "endereco", "tipo": "texto", "rotulo": "Endereço completo"},
        {"nome": "email", "tipo": "texto", "rotulo": "E-mail de contato"}]},
    {"grupo": "Perfis oficiais", "caminho": "empresa.perfis", "campos": [
        {"nome": "instagram", "tipo": "link", "rotulo": "Instagram (link)"},
        {"nome": "linkedin", "tipo": "link", "rotulo": "LinkedIn (link)"},
        {"nome": "google", "tipo": "link", "rotulo": "Perfil da Empresa no Google (link)"}]},
    {"grupo": "Fundador", "caminho": "fundador", "campos": [
        {"nome": "nome", "tipo": "texto", "rotulo": "Nome"},
        {"nome": "cargo", "tipo": "texto", "rotulo": "Cargo"},
        {"nome": "bio", "tipo": "lista", "rotulo": "Bio (um parágrafo por linha)"},
        {"nome": "destaques", "tipo": "lista", "rotulo": "Destaques (um por linha; só o que for confirmado)"}]},
    {"grupo": "Marca", "caminho": "marca", "campos": [
        {"nome": "logo", "tipo": "imagem", "rotulo": "Logo", "obrigatorio": True},
        {"nome": "icone", "tipo": "imagem", "rotulo": "Ícone (aba do navegador)", "obrigatorio": True},
        {"nome": "imagem_compartilhamento", "tipo": "imagem", "rotulo": "Imagem ao compartilhar o link", "obrigatorio": True}]},
    {"grupo": "Fontes", "caminho": "marca.fontes", "campos": [
        {"nome": "titulo", "tipo": "opcao", "rotulo": "Fonte dos títulos", "opcoes": _FONTES},
        {"nome": "corpo", "tipo": "opcao", "rotulo": "Fonte do texto", "opcoes": _FONTES}]},
    {"grupo": "Cores", "caminho": "marca.cores", "campos": [
        _cor("fundo", "Fundo"), _cor("fundo_2", "Fundo dos cartões"), _cor("fundo_3", "Fundo de destaque"),
        _cor("texto", "Texto"), _cor("suave", "Texto secundário"), _cor("destaque", "Cor de destaque"),
        _cor("destaque_hover", "Destaque ao passar o mouse"), _cor("texto_no_destaque", "Texto sobre o destaque"),
        _cor("secundaria", "Cor secundária")]},
    {"grupo": "Blog", "caminho": "blog", "campos": [
        {"nome": "ativo", "tipo": "sim_nao", "rotulo": "Publicar o blog com os artigos aprovados"},
        {"nome": "titulo", "tipo": "texto", "rotulo": "Título da página do blog"},
        {"nome": "texto", "tipo": "texto_longo", "rotulo": "Texto da página do blog"},
        {"nome": "rotulo_menu", "tipo": "texto", "rotulo": "Nome no menu"}]},
    {"grupo": "Endereço do site", "caminho": "", "campos": [
        {"nome": "dominio", "tipo": "texto", "rotulo": "Domínio", "obrigatorio": True,
         "ajuda": "https://empresa.com.br, sem barra no fim"}]},
]

PAGINA_CAMPOS = [
    {"nome": "titulo_pagina", "tipo": "texto", "rotulo": "Título para o Google", "obrigatorio": True, "limite": 60,
     "ajuda": "Serviço e cidade no começo. O Google corta depois de uns 60 caracteres."},
    {"nome": "descricao", "tipo": "texto_longo", "rotulo": "Descrição para o Google", "obrigatorio": True, "limite": 160},
    {"nome": "menu", "tipo": "texto", "rotulo": "Nome no menu", "ajuda": "Vazio = a página fica fora do menu."},
    {"nome": "servico_nome", "tipo": "texto", "rotulo": "Nome do serviço (ficha Service)", "so_tipo": "servico"},
]

TIPOS_PAGINA = {"inicio": "Página inicial", "sobre": "Sobre a empresa", "servico": "Serviço e cidade", "simples": "Página simples"}
TIPOS_CAMPO = {"texto", "texto_longo", "lista", "imagem", "numero", "opcao", "sim_nao", "itens", "pagina", "cor"}
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
CAMPOS_EMPRESA_IDENTIDADE = [("cnpj", "CNPJ"), ("razao_social", "razão social"), ("endereco", "endereço"), ("email", "e-mail")]


class SiteInvalido(ValueError):
    def __init__(self, erros: list[str]):
        super().__init__("; ".join(erros))
        self.erros = erros


def padrao_do_bloco(tipo: str) -> dict:
    """Bloco novo com os valores padrão, para o botão 'Adicionar bloco'."""
    bloco = {"tipo": tipo}
    for c in BLOCOS[tipo]["campos"]:
        if "padrao" in c:
            bloco[c["nome"]] = c["padrao"]
        elif c["tipo"] in ("itens", "lista"):
            bloco[c["nome"]] = []
        elif c["tipo"] == "sim_nao":
            bloco[c["nome"]] = False
        else:
            bloco[c["nome"]] = ""
    return bloco


def _validar_valor(campo: dict, valor, onde: str, erros: list[str], assets: set[str], slugs: set[str]):
    t, nome = campo["tipo"], campo.get("rotulo", campo["nome"])
    vazio = valor in (None, "", [])
    if campo.get("obrigatorio") and vazio:
        erros.append(f"{onde}: “{nome}” é obrigatório")
        return
    if vazio:
        return
    if t in ("texto", "texto_longo"):
        if not isinstance(valor, str):
            erros.append(f"{onde}: “{nome}” precisa ser texto")
        elif re.search(r"<\s*/?\s*[a-zA-Z][^>]*>", valor):
            erros.append(f"{onde}: “{nome}” não aceita HTML")
    elif t == "link":
        # vira href no site publicado: só http(s), para nunca virar javascript: nem data:
        if not isinstance(valor, str) or not re.fullmatch(r"https?://[^\s\"'<>]+", valor):
            erros.append(f"{onde}: “{nome}” precisa ser um link começando com https://")
    elif t == "lista":
        if not isinstance(valor, list) or not all(isinstance(x, str) for x in valor):
            erros.append(f"{onde}: “{nome}” precisa ser uma lista de textos")
    elif t == "numero":
        if not isinstance(valor, (int, float)) or isinstance(valor, bool):
            erros.append(f"{onde}: “{nome}” precisa ser número")
    elif t == "sim_nao":
        if not isinstance(valor, bool):
            erros.append(f"{onde}: “{nome}” precisa ser sim ou não")
    elif t == "opcao":
        if valor not in [o[0] for o in campo["opcoes"]]:
            erros.append(f"{onde}: “{nome}” tem uma opção desconhecida")
    elif t == "imagem":
        if valor not in assets:
            erros.append(f"{onde}: a imagem “{valor}” não existe em assets/")
    elif t == "cor":
        if not isinstance(valor, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", valor):
            erros.append(f"{onde}: “{nome}” precisa ser uma cor como #ffc200")
    elif t == "pagina":
        if valor not in slugs:
            erros.append(f"{onde}: “{nome}” aponta para uma página que não existe")
    elif t == "itens":
        if not isinstance(valor, list):
            erros.append(f"{onde}: “{nome}” precisa ser uma lista")
            return
        if len(valor) > campo.get("maximo", 99):
            erros.append(f"{onde}: “{nome}” aceita no máximo {campo['maximo']}")
        for i, item in enumerate(valor, start=1):
            if not isinstance(item, dict):
                erros.append(f"{onde}: item {i} de “{nome}” inválido")
                continue
            for sub in campo["campos"]:
                _validar_valor(sub, item.get(sub["nome"]), f"{onde} › {nome} {i}", erros, assets, slugs)


def validar(site: dict, assets: set[str]) -> None:
    """Levanta SiteInvalido com todos os problemas encontrados (não só o primeiro)."""
    erros: list[str] = []
    e = site.get("empresa") or {}
    for chave, rotulo in (("nome", "nome da empresa"), ("cidade", "cidade"), ("uf", "estado"), ("whatsapp", "WhatsApp")):
        if not str(e.get(chave, "")).strip():
            erros.append(f"Configurações: falta o {rotulo}")
    if e.get("whatsapp") and not re.fullmatch(r"\d{12,13}", str(e["whatsapp"])):
        erros.append("Configurações: WhatsApp precisa ter só números, com 55 e DDD (ex.: 5531900000000)")
    if e.get("cnpj") and not re.fullmatch(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}", e["cnpj"]):
        erros.append("Configurações: CNPJ no formato 00.000.000/0000-00")
    if not re.match(r"^https://[a-z0-9.-]+\.[a-z]{2,}$", site.get("dominio", "")):
        erros.append("Configurações: domínio no formato https://empresa.com.br, sem barra no fim")
    paginas = site.get("paginas") or []
    slugs = [p.get("slug", "") for p in paginas]
    for g in CONFIGURACOES:
        alvo = site
        for parte in [x for x in g["caminho"].split(".") if x]:
            alvo = (alvo or {}).get(parte) or {}
        for campo in g["campos"]:
            if g["caminho"] == "empresa" and campo["nome"] in ("cnpj", "whatsapp"):
                continue  # formato conferido acima, com mensagem própria
            _validar_valor(campo, alvo.get(campo["nome"]), f"Configurações › {g['grupo']}", erros, assets, set(slugs))
    if "" not in slugs:
        erros.append("Falta a página inicial")
    if len(set(slugs)) != len(slugs):
        erros.append("Há duas páginas com o mesmo endereço")
    for p in paginas:
        onde = f"Página “{p.get('slug') or 'início'}”"
        if p.get("slug") and (not SLUG.match(p["slug"]) or p["slug"] in ("blog", "assets")):
            erros.append(f"{onde}: endereço só com letras minúsculas, números e hífen (e diferente de blog/assets)")
        if p.get("tipo") not in TIPOS_PAGINA:
            erros.append(f"{onde}: tipo de página desconhecido")
        for chave, rotulo in (("titulo_pagina", "título para o Google"), ("descricao", "descrição para o Google")):
            if not str(p.get(chave, "")).strip():
                erros.append(f"{onde}: falta o {rotulo}")
        for i, b in enumerate(p.get("blocos") or [], start=1):
            tipo = b.get("tipo")
            if tipo not in BLOCOS:
                erros.append(f"{onde}: bloco {i} de tipo desconhecido ({tipo})")
                continue
            for campo in BLOCOS[tipo]["campos"]:
                _validar_valor(campo, b.get(campo["nome"]), f"{onde} › {BLOCOS[tipo]['rotulo']}", erros, assets, set(slugs))
    if erros:
        raise SiteInvalido(erros)


def catalogo() -> dict:
    """O que o editor precisa para montar os formulários (sem o que é só do servidor)."""
    return {"blocos": BLOCOS, "tipos_pagina": TIPOS_PAGINA, "configuracoes": CONFIGURACOES, "pagina_campos": PAGINA_CAMPOS}
