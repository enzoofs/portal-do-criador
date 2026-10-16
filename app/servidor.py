"""
app/servidor.py — Portal do Criador (app web local).

    python main.py servir            # http://127.0.0.1:5050

Páginas montadas no servidor (Jinja), com os dados de cada tela preparados em
app/telas.py. O JavaScript cuida do que é interação: janela de custo, progresso
das execuções, gaveta de respostas do radar, seleção no conteúdo, paleta (Ctrl K)
e o modo apresentação.
"""

import io
import json
import re
from datetime import datetime
from pathlib import Path

from flask import Flask, abort, jsonify, redirect, render_template, request, send_file, url_for
from markupsafe import Markup

import cadastro
import custos
import ia
import orcamento
from app import dados, seguranca, tarefas, telas
from config import settings
from conteudo import fluxo, pendencias, plataformas, redes, render
from conteudo.pauta import slugify
from radar import rastreador, relatorio
from site_cliente import blocos, checagem, gerador, inicial

app = Flask(__name__)
seguranca.proteger(app)


# --------------------------------------------------------------------------
# Utilidades de template
# --------------------------------------------------------------------------

@app.context_processor
def _globais():
    import plano_correcao
    # CSS fixo do próprio código, sem dado de usuário
    return {"css_base": Markup(relatorio.CSS), "css_doc": Markup(plano_correcao.CSS_DOC),  # noqa: S704  # nosec B704
            "tarefa_ativa": tarefas.em_andamento(), "STATUS_ACAO": dados.STATUS_ACAO,
            "ROTULO_ETAPA": {s: r.lower() for s, r, *_ in telas.ETAPAS},
            "lateral": telas.lateral()}


@app.template_filter("data_br")
def _data_br(iso: str) -> str:
    return datetime.fromisoformat(iso).strftime("%d/%m/%Y %H:%M") if iso else ""


@app.template_filter("num")
def _num(v) -> str:
    return relatorio.numero_br(v)


@app.template_filter("data_extenso")
def _data_extenso(iso: str) -> str:
    return relatorio.data_extenso(iso)


@app.template_filter("milhar")
def _milhar(v) -> str:
    return f"{v:,}".replace(",", ".")


@app.route("/fontes/<nome>")
def fontes(nome):
    caminho = seguranca.arquivo_dentro(settings.BASE_DIR / "assets" / "fonts", nome)
    if not caminho.is_file() or caminho.suffix != ".woff2":
        abort(404)
    return send_file(caminho, mimetype="font/woff2", max_age=86400)


def _cliente_ou_404(cid: str) -> dict:
    seguranca.exigir_id(cid)  # o id vira caminho de arquivo: nada de \, .. ou maiúsculas
    c = dados.cliente(cid)
    if not c:
        abort(404)
    return c


def _linhas(form, campo: str) -> list[str]:
    """Campo de texto de várias linhas do formulário -> lista sem linhas vazias."""
    return [linha.strip() for linha in form.get(campo, "").splitlines() if linha.strip()]


# --------------------------------------------------------------------------
# Painel da agência
# --------------------------------------------------------------------------

@app.route("/")
def inicio():
    return render_template("inicio.html", v=telas.carteira())


@app.route("/novo", methods=["GET", "POST"])
def novo_cliente():
    if request.method == "GET":
        return render_template("novo.html")
    f = request.form
    nome = f["nome"].strip()
    site = f["site"].strip()
    if not site.startswith("http"):
        site = "https://" + site
    dominio = re.sub(r"^https?://(www\.)?", "", site).split("/")[0]
    servico = f["servico"].strip()
    cidade = f["cidade"].strip()
    nichos = _linhas(f, "nichos")
    cid = dados.gerar_id(nome)
    perguntas = _perguntas_padrao(nome, servico, cidade, nichos)
    dados.salvar_cliente({
        "id": cid, "nome": nome, "site": site,
        "apelidos": [nome, *_linhas(f, "apelidos")], "dominios": [dominio],
        "cidade": cidade, "regiao": f["regiao"].strip(), "pais": "BR",
        "segmento": servico,
        "perfil": {
            "_fonte": f"Cadastro no Portal do Criador em {datetime.now():%Y-%m-%d}.",
            "servicos": _linhas(f, "servicos"), "processo": _linhas(f, "processo"), "nichos": nichos,
            "diferenciais": _linhas(f, "diferenciais"), "afirmacoes_a_confirmar": _linhas(f, "afirmacoes"),
            "clientes_citados_no_site": _linhas(f, "clientes"),
            "cta": {"texto": f"Fale com a {nome} pelo WhatsApp", "whatsapp": re.sub(r"\D", "", f["whatsapp"])},
            "tom": f.get("tom", "").strip() or "Direto, próximo e confiante.",
        },
        "perguntas": perguntas,
    })
    return redirect(url_for("config", cid=cid, novo=1))


def _perguntas_padrao(nome: str, servico: str, cidade: str, nichos: list[str]) -> list[dict]:
    """Perguntas que um cliente final faria — sem IA, editáveis depois."""
    s = servico.lower()
    qs = [f"Qual a melhor {s} em {cidade}?",
          f"Me indica uma {s} em {cidade}.",
          f"Quanto custa contratar uma {s} em {cidade} e quais você recomenda?"]
    qs += [f"{servico} para {n.lower()} em {cidade}" for n in nichos[:5]]
    d = [{"texto": q, "tipo": "descoberta"} for q in qs]
    d += [{"texto": f"A {nome} de {cidade} é uma boa {s}?", "tipo": "marca"},
          {"texto": f"O que você sabe sobre a {nome}?", "tipo": "marca"}]
    return d


# --------------------------------------------------------------------------
# Cliente: radar
# --------------------------------------------------------------------------

@app.route("/c/<cid>")
def cliente(cid):
    return redirect(url_for("radar", cid=cid))


@app.route("/c/<cid>/radar")
def radar(cid):
    c = _cliente_ou_404(cid)
    run, rast = dados.ultimo_radar(cid), rastreador.ultimo(cid)
    v = telas.radar(run, rast) if run else None
    return render_template("radar.html", c=c, aba="radar", run=run, v=v, rast=rast)


@app.route("/c/<cid>/rastreio")
def rastreio(cid):
    """O site do cliente página por página, como um robô de IA o encontra."""
    c = _cliente_ou_404(cid)
    rast = rastreador.ultimo(cid)
    v = telas.rastreio(rast, dados.ultimo_radar(cid), rastreador.anterior(cid)) if rast else None
    return render_template("rastreio.html", c=c, aba="radar", rast=rast, v=v)


@app.route("/c/<cid>/apresentar")
def apresentar(cid):
    """Modo apresentação: o último radar em slides (setas, espaço, F para tela cheia)."""
    c = _cliente_ou_404(cid)
    run = dados.ultimo_radar(cid)
    if not run:
        return redirect(url_for("radar", cid=cid))
    return render_template("apresentar.html", c=c, run=run, v=telas.radar(run, rastreador.ultimo(cid)),
                           conteudo=telas.conteudo(c), plano=dados.plano(cid, run))


@app.route("/c/<cid>/radar/relatorio")
def radar_relatorio(cid):
    run = dados.ultimo_radar(cid) or abort(404)
    return send_file(relatorio.salvar(run, rastreador.ultimo(cid)))  # regera sempre: é rápido e não chama IA


# --------------------------------------------------------------------------
# Cliente: conteúdo
# --------------------------------------------------------------------------

@app.route("/c/<cid>/conteudo")
def conteudo(cid):
    c = _cliente_ou_404(cid)
    run = dados.ultimo_radar(cid)
    v = telas.conteudo(c)
    return render_template("conteudo.html", c=c, aba="conteudo", v=v, q=v["q"],
                           tem_radar=bool(run), radar_demo=bool(run and run["demo"]))


def _recalcular(a: dict) -> None:
    texto = " ".join([a["resposta_direta"], a["corpo_markdown"]] + [f["resposta"] for f in a["faq"]])
    a["pendencias"] = re.findall(r"\[\[([^\]]+)\]\]", texto)
    a["palavras"] = len(re.findall(r"\w+", a["corpo_markdown"]))


@app.route("/c/<cid>/artigo/<slug>", methods=["GET", "POST"])
def artigo(cid, slug):
    c = _cliente_ou_404(cid)
    seguranca.exigir_id(slug)
    pasta = dados.pasta_pauta(cid) or abort(404)
    a = dados.artigo(pasta, slug) or abort(404)
    aviso = request.args.get("aviso")

    if request.method == "POST":
        acao = request.form.get("acao")
        for campo in ("titulo", "meta_titulo", "meta_descricao", "resposta_direta", "corpo_markdown"):
            if campo in request.form:
                a[campo] = request.form[campo].strip()
        faq = []
        for p, r in zip(request.form.getlist("faq_pergunta"), request.form.getlist("faq_resposta"), strict=False):
            if p.strip() and r.strip():
                faq.append({"pergunta": p.strip(), "resposta": r.strip()})
        if faq or "faq_pergunta" in request.form:
            a["faq"] = faq
        try:
            resolvidas = pendencias.aplicar(a, pendencias.do_formulario(request.form))
        except ValueError:
            abort(400)
        _recalcular(a)
        aviso = "Alterações salvas." + (f" {resolvidas} pendência(s) resolvida(s)." if resolvidas else "")
        if acao == "aprovar":
            if a["pendencias"]:
                aviso = f"Ainda há {len(a['pendencias'])} pendência(s) no texto — resolva antes de aprovar."
            else:
                a["status"], aviso = "aprovado", "Artigo aprovado."
        elif acao == "reabrir":
            a["status"], aviso = "rascunho", "Artigo voltou para rascunho."
        elif acao == "wordpress":
            destino = plataformas.nome(c)
            if a.get("demo"):
                aviso = f"Artigo de demonstração não vai para o {destino}."
            else:
                try:
                    a["wordpress"] = plataformas.enviar_rascunho(a, c)
                    a["status"], aviso = "rascunho no WordPress", f"Enviado ao {destino} como rascunho."
                except Exception as e:
                    aviso = f"Não foi possível enviar: {e}"
        fluxo.salvar_artigo(pasta, a, c)
        fluxo.atualizar_central(pasta, c)
        return redirect(url_for("artigo", cid=cid, slug=slug, aviso=aviso))

    # conteudo_post passa o Markdown por markdown_seguro; os marcadores só ganham <mark>
    previa = Markup(render.destacar_marcadores(render.conteudo_post(a, c)))  # noqa: S704  # nosec B704
    url_post = c["site"].rstrip("/") + "/" + a["slug"] + "/"
    _, p = dados.pauta(cid)
    numero, tema = next(((i, t) for i, t in enumerate((p or {}).get("temas", []), start=1)
                         if t["slug"] == slug), (None, a.get("tema") or {}))
    return render_template("artigo.html", c=c, aba="conteudo", destino=plataformas.nome(c), a=a, previa=previa, aviso=aviso,
                           numero=numero, tema=tema, pend_itens=pendencias.listar(a), url_post=url_post,
                           redes=redes.gerar(a, c, url_post))


@app.route("/c/<cid>/site-novo/")
@app.route("/c/<cid>/site-novo/<path:arquivo>")
def site_novo(cid, arquivo="index.html"):
    """Prévia do site reconstruído (entregas/<cliente>/site-novo), para mostrar na reunião."""
    _cliente_ou_404(cid)
    alvo = seguranca.arquivo_dentro(dados.ENTREGAS_DIR / cid / "site-novo", arquivo.rstrip("/") or "index.html")
    if alvo.is_dir():  # blog/ e blog/<slug>/ servem o index.html da pasta
        alvo = alvo / "index.html"
    if not alvo.is_file():
        abort(404)
    resp = send_file(alvo)
    resp.headers["Cache-Control"] = "no-store"  # o editor recarrega a prévia a cada salvamento
    return resp


# --------------------------------------------------------------------------
# Cliente: editor do site (site_cliente/)
# --------------------------------------------------------------------------

IMAGENS_ACEITAS = {".jpg", ".jpeg", ".png", ".webp"}
FORMATOS_IMAGEM = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}   # formato lido do arquivo -> extensão gravada
LIMITE_IMAGEM = 8 * 1024 * 1024
LIMITE_PIXELS = 40_000_000      # ~ 8000 x 5000; acima disso é foto exagerada ou "bomba de descompressão"
VERSOES_GUARDADAS = 50          # histórico de salvamentos do site por cliente


def _site_existe(cid: str) -> bool:
    return (gerador.pasta_site(cid) / "site.json").exists()


@app.route("/c/<cid>/site")
def site_editor(cid):
    c = _cliente_ou_404(cid)
    if not _site_existe(cid):
        return render_template("site.html", c=c, aba="site", existe=False)
    s, _ = gerador.carregar(cid)
    dados_editor = {"site": s, "catalogo": blocos.catalogo(), "assets": sorted(gerador.assets(cid)),
                    "cliente": cid, "previa": url_for("site_novo", cid=cid),
                    "assets_url": url_for("site_asset", cid=cid, nome="")}
    return render_template("site.html", c=c, aba="site", existe=True, dados=dados_editor)


@app.route("/c/<cid>/site/assets/<path:nome>")
def site_asset(cid, nome):
    """Imagens originais do site (miniaturas no editor)."""
    _cliente_ou_404(cid)
    alvo = seguranca.arquivo_dentro(gerador.pasta_site(cid) / "assets", nome)
    if not alvo.is_file():
        abort(404)
    return send_file(alvo)


def _gerar_e_checar(cid: str) -> dict:
    gerador.gerar(cid, previa=True)
    pasta = gerador.gerar(cid, previa=False, destino=gerador.CACHE_IMAGENS / cid / "checagem")
    return checagem.checar(cid, pasta)


@app.post("/api/c/<cid>/site")
def api_site_salvar(cid):
    _cliente_ou_404(cid)
    if not _site_existe(cid):
        abort(404)
    novo = seguranca.json_do_pedido()
    try:
        blocos.validar(novo, gerador.assets(cid))
    except blocos.SiteInvalido as e:
        return jsonify({"erros": e.erros}), 422
    arq = gerador.pasta_site(cid) / "site.json"
    historico = settings.BASE_DIR / "data" / "sites_historico" / cid
    historico.mkdir(parents=True, exist_ok=True)
    (historico / f"{datetime.now():%Y%m%d-%H%M%S-%f}.json").write_text(arq.read_text(encoding="utf-8"), encoding="utf-8")
    for velha in sorted(historico.glob("*.json"))[:-VERSOES_GUARDADAS]:   # retenção limitada
        velha.unlink()
    arq.write_text(json.dumps(novo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return jsonify({"salvo_em": datetime.now().strftime("%H:%M:%S"), "checagem": _gerar_e_checar(cid)})


@app.post("/api/c/<cid>/site/checar")
def api_site_checar(cid):
    _cliente_ou_404(cid)
    if not _site_existe(cid):
        abort(404)
    return jsonify({"checagem": _gerar_e_checar(cid)})


@app.post("/api/c/<cid>/site/criar")
def api_site_criar(cid):
    _cliente_ou_404(cid)
    try:
        inicial.criar(cid)
    except FileExistsError as e:
        return jsonify({"erro": str(e)}), 409
    _gerar_e_checar(cid)
    return jsonify({"ok": True})


@app.post("/api/c/<cid>/site/imagem")
def api_site_imagem(cid):
    """Recebe uma imagem para o site. Só JPG, PNG e WebP (SVG pode carregar script)."""
    _cliente_ou_404(cid)
    arq = request.files.get("imagem")
    if not arq or not arq.filename:
        return jsonify({"erro": "Escolha uma imagem."}), 400
    ext = Path(arq.filename).suffix.lower()
    if ext not in IMAGENS_ACEITAS:
        return jsonify({"erro": "Use JPG, PNG ou WebP."}), 400
    conteudo = arq.read(LIMITE_IMAGEM + 1)
    if len(conteudo) > LIMITE_IMAGEM:
        return jsonify({"erro": "Imagem maior que 8 MB."}), 400
    from PIL import Image, UnidentifiedImageError
    try:
        with Image.open(io.BytesIO(conteudo)) as imagem:
            formato, (largura, altura) = imagem.format, imagem.size
            imagem.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        return jsonify({"erro": "O arquivo não é uma imagem válida."}), 400
    # Vale o formato lido do conteúdo, não a extensão do nome (um GIF renomeado para .png não passa)
    if formato not in FORMATOS_IMAGEM:
        return jsonify({"erro": "Use JPG, PNG ou WebP."}), 400
    if largura * altura > LIMITE_PIXELS:
        return jsonify({"erro": "Imagem grande demais em pixels. Reduza para até 8000 × 5000."}), 400
    ext = FORMATOS_IMAGEM[formato]
    base = slugify(Path(arq.filename).stem)[:40].strip("-") or "imagem"
    pasta = gerador.pasta_site(cid) / "assets"
    pasta.mkdir(parents=True, exist_ok=True)
    nome, n = f"{base}{ext}", 2
    while (pasta / nome).exists():
        nome, n = f"{base}-{n}{ext}", n + 1
    (pasta / nome).write_bytes(conteudo)
    return jsonify({"nome": nome, "assets": sorted(gerador.assets(cid))})


@app.post("/api/c/<cid>/site/publicar")
def api_site_publicar(cid):
    _cliente_ou_404(cid)
    if not _site_existe(cid):
        abort(404)
    pasta = gerador.gerar(cid, previa=False)
    r = checagem.checar(cid, pasta)
    return jsonify({"checagem": r, "pasta": str(pasta), "baixar": url_for("site_baixar", cid=cid)})


@app.route("/c/<cid>/site/baixar")
def site_baixar(cid):
    """Versão para publicar em .zip, para subir no Cloudflare Pages ou em qualquer hospedagem."""
    import shutil
    _cliente_ou_404(cid)
    if not _site_existe(cid):
        abort(404)
    pasta = dados.ENTREGAS_DIR / cid / "site-publicar"
    if not pasta.exists():
        gerador.gerar(cid, previa=False)
    destino = gerador.CACHE_IMAGENS / cid / f"site-{cid}"
    zipado = shutil.make_archive(str(destino), "zip", pasta)
    return send_file(zipado, as_attachment=True, download_name=f"site-{cid}-{datetime.now():%Y%m%d}.zip")


@app.route("/c/<cid>/especialista", methods=["GET", "POST"])
def especialista(cid):
    """Todas as pendências dos artigos numa tela só, para o especialista responder sem abrir texto."""
    c = _cliente_ou_404(cid)
    pasta = dados.pasta_pauta(cid)
    if not pasta:  # sem pauta ainda, não há pendências
        return redirect(url_for("conteudo", cid=cid))
    artigos = dados.artigos(pasta)
    if request.method == "POST":
        total = 0
        for slug in dict.fromkeys(request.form.getlist("pend_slug")):
            a = artigos.get(slug)
            if not a:
                continue
            try:
                feitas = pendencias.aplicar(a, pendencias.do_formulario(request.form, slug))
            except ValueError:
                abort(400)
            if feitas:
                _recalcular(a)
                fluxo.salvar_artigo(pasta, a, c)
                total += feitas
        if total:
            fluxo.atualizar_central(pasta, c)
        aviso = f"{total} pendência(s) resolvida(s)." if total else "Nada mudou: escolha o que fazer em cada item."
        return redirect(url_for("especialista", cid=cid, aviso=aviso))
    _, p = dados.pauta(cid)
    ordem = {t["slug"]: i for i, t in enumerate((p or {}).get("temas", []), start=1)}
    grupos = [{"numero": ordem.get(a["slug"]), "artigo": a, "itens": pendencias.listar(a)}
              for a in artigos.values() if a.get("pendencias")]
    grupos.sort(key=lambda g: g["numero"] or 99)
    return render_template("especialista.html", c=c, aba="conteudo", grupos=grupos, aviso=request.args.get("aviso"),
                           total=sum(len(g["itens"]) for g in grupos))


# --------------------------------------------------------------------------
# Cliente: plano de ações e configuração
# --------------------------------------------------------------------------

@app.route("/c/<cid>/plano")
def plano(cid):
    c = _cliente_ou_404(cid)
    run = dados.ultimo_radar(cid)
    return render_template("plano.html", c=c, aba="plano", acoes=dados.plano(cid, run), run=run,
                           rast=rastreador.ultimo(cid) if run else None,
                           site_novo=(dados.ENTREGAS_DIR / cid / "site-novo" / "index.html").exists())


@app.route("/c/<cid>/guia/<nome>")
def guia(cid, nome):
    c = _cliente_ou_404(cid)
    seguranca.exigir_id(nome)
    g = dados.guia(cid, nome) or abort(404)
    # Os anexos (hoje só o llms.txt, opcional) pertencem ao guia de identidade
    anexos = [p.name for p in (dados.ENTREGAS_DIR / cid).iterdir()
              if p.is_file() and p.suffix not in (".md", ".html")] if nome.startswith("01-") else []
    acao = next((a for a in dados.plano(cid, dados.ultimo_radar(cid)) if a["guia"] == nome), None)
    # Os guias são escritos pela equipe (entregas/<cliente>/*.md) e podem trazer HTML de propósito
    corpo = Markup(g[1])  # noqa: S704  # nosec B704
    return render_template("guia.html", c=c, aba="plano", meta=g[0], corpo=corpo, anexos=anexos, acao=acao)


@app.route("/c/<cid>/anexo/<nome>")
def anexo(cid, nome):
    _cliente_ou_404(cid)
    caminho = seguranca.arquivo_dentro(dados.ENTREGAS_DIR / cid, nome)
    if not caminho.is_file() or caminho.suffix in (".md",):
        abort(404)
    return send_file(caminho, as_attachment=True)


@app.route("/c/<cid>/config", methods=["GET", "POST"])
def config(cid):
    c = _cliente_ou_404(cid)
    if request.method == "POST":
        f = request.form
        c["perguntas"] = ([{"texto": t, "tipo": "descoberta"} for t in _linhas(f, "descoberta")]
                          + [{"texto": t, "tipo": "marca"} for t in _linhas(f, "marca")])
        for campo in ("servicos", "processo", "nichos", "diferenciais", "afirmacoes_a_confirmar"):
            c["perfil"][campo] = _linhas(f, campo)
        c["perfil"]["tom"] = f.get("tom", "").strip()
        autor = {k: f.get(f"autor_{k}", "").strip() for k in ("nome", "cargo", "bio")}
        c["perfil"]["autor"] = autor if autor["nome"] else None
        c["aprovacao"] = f.get("aprovacao") if f.get("aprovacao") in ("completa", "pauta") else "completa"
        c["apelidos"] = _linhas(f, "apelidos") or [c["nome"]]
        pub = {k: f.get(f"pub_{k}", "").strip() for k in ("plataforma", "colecao", "loja", "blog_id", "site_id", "membro_id")}
        c["publicacao"] = {**(c.get("publicacao") or {}), **{k: v for k, v in pub.items() if v}}
        dados.salvar_cliente(c)
        return redirect(url_for("config", cid=cid, salvo=1))
    return render_template("config.html", c=c, aba="config", salvo=request.args.get("salvo"),
                           novo=request.args.get("novo"))


# --------------------------------------------------------------------------
# Cliente: resultados (GA4 + Search Console)
# --------------------------------------------------------------------------

@app.route("/c/<cid>/resultados", methods=["GET", "POST"])
def resultados(cid):
    import medicao
    c = _cliente_ou_404(cid)
    if request.method == "POST":
        if request.form.get("acao") == "atualizar":
            pasta = dados.pasta_pauta(cid)
            arts = list(dados.artigos(pasta).values()) if pasta else []
            try:
                r = medicao.coletar(c, artigos=arts)
                aviso = "Números atualizados." if not r["erros"] else "Atualizado, com avisos: veja abaixo."
            except medicao.SemAcesso as e:
                aviso = str(e)
            return redirect(url_for("resultados", cid=cid, aviso=aviso))
        c["medicao"] = {"ga4": re.sub(r"\D", "", request.form.get("ga4", "")),
                        "search_console": request.form.get("search_console", "").strip()}
        dados.salvar_cliente(c)
        return redirect(url_for("resultados", cid=cid, aviso="Acesso salvo."))
    return render_template("resultados.html", c=c, aba="resultados", r=medicao.ultima(cid),
                           conf=medicao.configurado(c), aviso=request.args.get("aviso"))


# --------------------------------------------------------------------------
# Cliente: mídia paga (termos de pesquisa do Google Ads)
# --------------------------------------------------------------------------

@app.route("/c/<cid>/midia", methods=["GET", "POST"])
def midia(cid):
    from midia import termos
    c = _cliente_ou_404(cid)
    if request.method == "POST":
        arquivo = request.files.get("arquivo")
        if not arquivo or not arquivo.filename:
            return redirect(url_for("midia", cid=cid, aviso="Escolha o arquivo CSV exportado do Google Ads."))
        try:
            lista = termos.ler_csv(arquivo.read())
        except termos.ArquivoInvalido as e:
            return redirect(url_for("midia", cid=cid, aviso=str(e)))
        termos.salvar(cid, lista, arquivo.filename)
        return redirect(url_for("midia", cid=cid, aviso=f"{len(lista)} termos importados."))
    dados_m = termos.carregar(cid)
    no_radar = {q["texto"].lower() for q in c["perguntas"]}
    linhas = []
    for t in (dados_m or {}).get("termos", [])[:100]:
        pergunta = termos.como_pergunta(t["termo"], c["cidade"])
        linhas.append({**t, "pergunta": pergunta, "no_radar": pergunta.lower() in no_radar})
    return render_template("midia.html", c=c, aba="midia", dados=dados_m, linhas=linhas,
                           resumo=termos.resumo(dados_m) if dados_m else None, aviso=request.args.get("aviso"))


@app.post("/c/<cid>/midia/radar")
def midia_para_radar(cid):
    """Os termos escolhidos viram perguntas de compra do radar (editáveis em Configurar)."""
    c = _cliente_ou_404(cid)
    existentes = {q["texto"].lower() for q in c["perguntas"]}
    novas = [p for p in dict.fromkeys(request.form.getlist("pergunta")) if p.lower() not in existentes]
    descoberta = [q for q in c["perguntas"] if q["tipo"] == "descoberta"]
    marca = [q for q in c["perguntas"] if q["tipo"] != "descoberta"]
    c["perguntas"] = descoberta + [{"texto": p, "tipo": "descoberta", "origem": "google_ads"} for p in novas] + marca
    dados.salvar_cliente(c)
    aviso = (f"{len(novas)} pergunta{'s' if len(novas) != 1 else ''} adicionada{'s' if len(novas) != 1 else ''} "
             "ao radar. Elas entram no próximo radar.") if novas else "Essas perguntas já estavam no radar."
    return redirect(url_for("midia", cid=cid, aviso=aviso))


# --------------------------------------------------------------------------
# API: custo, execuções e status das ações
# --------------------------------------------------------------------------

def _linhas_estimativa(cid: str, tipo: str, temas: list[int] | None, repeticoes: int = 1) -> list[tuple[str, float]]:
    if tipo == "radar":
        return orcamento.radar(cid, repeticoes=repeticoes)
    if tipo == "pauta":
        return orcamento.pauta()
    if tipo == "artigos":
        _, p = dados.pauta(cid)
        return orcamento.artigos(len(temas) if temas else len((p or {}).get("temas", [])))
    abort(400)


def _rodadas(corpo: dict) -> int:
    return max(1, min(5, int(corpo.get("repeticoes") or 1)))


@app.post("/api/novo/ler-site")
def api_ler_site():
    """Rascunho do cadastro a partir do site. com_ia=True faz uma chamada de IA curta (centavos),
    sempre a pedido explícito de quem está cadastrando."""
    corpo = seguranca.json_do_pedido()
    if not corpo.get("site", "").strip():
        return jsonify({"erro": "Informe o site."}), 400
    try:
        lido = cadastro.ler_site(corpo["site"])
    except cadastro.SiteInacessivel as e:
        return jsonify({"erro": str(e)}), 422
    campos = {k: v for k, v in lido.items() if not k.startswith("_")}
    if corpo.get("com_ia"):
        if not ia.provedor_disponivel():
            return jsonify({"erro": "Nenhuma chave de IA configurada. Os dados básicos já foram preenchidos."}), 422
        custos.contador.iniciar(0.05)
        try:
            campos.update({k: v for k, v in cadastro.completar_com_ia(lido).items() if v})
        except Exception as e:
            return jsonify({"erro": f"A IA não conseguiu ler o site: {e}"}), 502
        finally:
            custos.anotar_gasto("cadastro", re.sub(r"^https?://(www\.)?", "", lido["site"]),
                                custos.contador.resumo()["total_usd"])
            custos.contador.autorizado = False
    return jsonify(campos)


@app.post("/api/c/<cid>/estimativa")
def api_estimativa(cid):
    _cliente_ou_404(cid)
    corpo = seguranca.json_do_pedido()
    linhas = _linhas_estimativa(cid, corpo["tipo"], corpo.get("temas"), _rodadas(corpo))
    return jsonify({"linhas": [{"item": i, "usd": round(v, 2)} for i, v in linhas],
                    "total": round(sum(v for _, v in linhas), 2), "limite": settings.LIMITE_USD_PADRAO,
                    "sem_chave": not linhas or all(v == 0 for _, v in linhas)})


@app.post("/api/c/<cid>/tarefas")
def api_iniciar(cid):
    _cliente_ou_404(cid)
    corpo = seguranca.json_do_pedido()
    gratis = corpo.get("tipo") in tarefas.TAREFAS_GRATIS
    if not corpo.get("demo") and not corpo.get("confirmado") and not gratis:
        return jsonify({"erro": "Execução paga sem confirmação."}), 400
    demo = bool(corpo.get("demo"))
    # pauta de radar demo também é demo (grátis). O rastreio não herda: é grátis e lê o site como está no ar.
    if corpo["tipo"] == "pauta" and not demo:
        run = dados.ultimo_radar(cid)
        demo = bool(run and run["demo"])
    if corpo["tipo"] == "artigos":  # artigos seguem o modo da pauta
        _, p = dados.pauta(cid)
        demo = bool((p or {}).get("demo"))
    try:
        t = tarefas.iniciar(corpo["tipo"], cid, demo=demo,
                            limite=float(corpo.get("limite") or settings.LIMITE_USD_PADRAO),
                            temas=corpo.get("temas"), repeticoes=_rodadas(corpo))
    except tarefas.Ocupado as e:
        return jsonify({"erro": str(e)}), 409
    return jsonify(t.to_dict())


@app.get("/api/paleta")
def api_paleta():
    return jsonify(telas.paleta(request.args.get("c")))


@app.get("/api/tarefas/<tid>")
def api_tarefa(tid):
    seguranca.exigir_id(tid)
    t = tarefas.obter(tid) or abort(404)
    return jsonify(t.to_dict())


@app.post("/api/c/<cid>/plano")
def api_plano(cid):
    _cliente_ou_404(cid)
    corpo = seguranca.json_do_pedido()
    if corpo["status"] not in dados.STATUS_ACAO:
        abort(400)
    dados.marcar_acao(cid, corpo["titulo"], corpo["status"])
    return jsonify({"ok": True})
