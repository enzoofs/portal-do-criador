// Portal do Criador — editor do site do cliente.
// Os formulários saem do catálogo (site_cliente/blocos.py): cada bloco declara os próprios campos,
// como as seções com schema do Shopify. O editor só mexe no JSON do site; quem valida e gera o HTML
// é o servidor, a cada salvamento. Autossuficiente de propósito: não depende da ordem do app.js.
(() => {
  const q = (s, el = document) => el.querySelector(s);
  const qq = (s, el = document) => [...el.querySelectorAll(s)];

  // h("div", {class: "x", onclick: fn}, filhos...) — cria elemento sem innerHTML (nada de texto virar HTML)
  function h(tag, attrs = {}, ...filhos) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v === false || v == null) continue;
      if (k === "class") el.className = v;
      else if (k === "text") el.textContent = v;
      else if (k === "value") el.value = v;
      else if (k === "checked") el.checked = !!v;
      else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v === true ? "" : v);
    }
    for (const f of filhos.flat()) if (f != null && f !== false) el.append(f instanceof Node ? f : document.createTextNode(f));
    return el;
  }

  async function api(url, corpo) {
    const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo ?? {}) });
    const dados = await r.json().catch(() => ({}));
    if (!r.ok) {
      const erro = new Error(dados.erro || (dados.erros ? "O site tem itens para corrigir." : `Erro ${r.status}`));
      erro.erros = dados.erros;
      throw erro;
    }
    return dados;
  }

  function toast(texto) {
    const el = h("div", { class: "toast", role: "status" }, texto);
    document.body.append(el);
    setTimeout(() => el.remove(), 5200);
  }

  // ------------------------------------------------------------ estado vazio: criar a partir do cadastro
  qq("[data-site-criar]").forEach((b) => b.addEventListener("click", async () => {
    b.disabled = true;
    b.textContent = "Criando o rascunho…";
    try {
      await api(`/api/c/${b.dataset.siteCriar}/site/criar`);
      location.reload();
    } catch (e) {
      toast(e.message);
      b.disabled = false;
      b.textContent = "Criar site a partir do cadastro";
    }
  }));

  const raiz = q("[data-site-editor]");
  if (!raiz) return;

  const D = JSON.parse(q("#se-dados").textContent);
  const CAT = D.catalogo;
  let site = D.site;
  let assets = D.assets;
  let pag = 0;          // página em edição
  let aberto = null;    // bloco aberto (índice)
  let sujo = false;
  let salvando = false;
  let checagem = null;
  const painel = (n) => q(`[data-se-painel=${n}]`, raiz);
  const iframe = q("[data-previa]", raiz);

  const estado = (t, classe = "") => {
    const el = q("[data-estado]", raiz);
    el.textContent = t;
    el.className = "se-estado " + classe;
  };
  function marcar() {
    if (!sujo) estado("alterações não salvas", "sujo");
    sujo = true;
  }
  window.addEventListener("beforeunload", (ev) => { if (sujo) { ev.preventDefault(); ev.returnValue = ""; } });

  function garantir(obj, caminho) {
    let o = obj;
    for (const k of caminho.split(".").filter(Boolean)) {
      if (o[k] == null || typeof o[k] !== "object") o[k] = {};
      o = o[k];
    }
    return o;
  }
  const rotuloPagina = (p) => p.menu || (p.slug ? p.slug : "Início");
  const primeiroTexto = (b) => {
    for (const c of (CAT.blocos[b.tipo]?.campos || [])) {
      const v = b[c.nome];
      if (typeof v === "string" && v.trim() && c.tipo !== "imagem") return v.trim();
    }
    return "";
  };

  // ------------------------------------------------------------ campos (um renderizador por tipo)
  function rotulo(def, extra) {
    return h("label", { class: "se-rot-campo" },
      h("span", {}, def.rotulo || def.nome, def.obrigatorio ? h("i", { class: "obrig", title: "obrigatório" }, " *") : null), extra || null);
  }

  function contador(def, el) {
    if (!def.limite) return null;
    const c = h("span", { class: "se-cont" });
    const atualizar = () => {
      const n = el.value.length;
      c.textContent = `${n}/${def.limite}`;
      c.classList.toggle("alerta", n > def.limite);
    };
    el.addEventListener("input", atualizar);
    atualizar();
    return c;
  }

  function campo(def, alvo, chave, aoMudarEstrutura) {
    const set = (v) => { alvo[chave] = v; marcar(); };
    const val = alvo[chave];
    let entrada;
    switch (def.tipo) {
      case "texto":
        entrada = h("input", { type: "text", value: val ?? "", oninput: (e) => set(e.target.value) });
        break;
      case "link":
        entrada = h("input", { type: "url", inputmode: "url", placeholder: "https://", value: val ?? "", oninput: (e) => set(e.target.value.trim()) });
        break;
      case "texto_longo":
        entrada = h("textarea", { rows: 3, oninput: (e) => set(e.target.value) });
        entrada.value = val ?? "";
        break;
      case "lista":
        entrada = h("textarea", { rows: 4, oninput: (e) => set(e.target.value.split("\n").map((x) => x.trim()).filter(Boolean)) });
        entrada.value = (val || []).join("\n");
        break;
      case "numero":
        entrada = h("input", { type: "number", value: val ?? "", oninput: (e) => set(e.target.value === "" ? null : Number(e.target.value)) });
        break;
      case "opcao":
        entrada = h("select", { class: "sel", onchange: (e) => set(e.target.value) },
          (def.opcoes || []).map(([v, r]) => h("option", { value: v, selected: v === val }, r)));
        if (val == null && def.opcoes?.length) alvo[chave] = def.opcoes[0][0];
        break;
      case "sim_nao":
        return h("label", { class: "se-check" },
          h("input", { type: "checkbox", checked: !!val, onchange: (e) => set(e.target.checked) }), h("span", {}, def.rotulo));
      case "cor": {
        const txt = h("input", { type: "text", value: val ?? "", class: "se-cor-txt", maxlength: 7 });
        const cor = h("input", { type: "color", value: /^#[0-9a-f]{6}$/i.test(val || "") ? val : "#000000" });
        cor.addEventListener("input", () => { txt.value = cor.value; set(cor.value); });
        txt.addEventListener("input", () => { if (/^#[0-9a-f]{6}$/i.test(txt.value)) cor.value = txt.value; set(txt.value); });
        entrada = h("div", { class: "se-cor" }, cor, txt);
        break;
      }
      case "pagina":
        entrada = h("select", { class: "sel", onchange: (e) => set(e.target.value === "__nenhuma" ? "" : e.target.value) },
          site.paginas.map((p) => h("option", { value: p.slug, selected: p.slug === val }, rotuloPagina(p))));
        break;
      case "imagem":
        entrada = campoImagem(def, alvo, chave);
        break;
      case "itens":
        return campoItens(def, alvo, chave, aoMudarEstrutura);
      default:
        entrada = h("input", { type: "text", value: val ?? "", oninput: (e) => set(e.target.value) });
    }
    const wrap = h("div", { class: "se-campo" }, rotulo(def, (def.tipo === "texto" || def.tipo === "texto_longo") ? contador(def, entrada) : null), entrada);
    if (def.ajuda) wrap.append(h("p", { class: "se-ajuda" }, def.ajuda));
    return wrap;
  }

  function campoImagem(def, alvo, chave) {
    const mini = h("img", { class: "se-mini", alt: "" });
    const sel = h("select", { class: "sel" });
    const preencher = () => {
      sel.replaceChildren(h("option", { value: "" }, "— sem imagem —"), ...assets.map((a) => h("option", { value: a, selected: a === alvo[chave] }, a)));
      mini.hidden = !alvo[chave];
      if (alvo[chave]) mini.src = D.assets_url + encodeURIComponent(alvo[chave]);
    };
    sel.addEventListener("change", () => { alvo[chave] = sel.value; marcar(); preencher(); });
    const arquivo = h("input", { type: "file", accept: "image/jpeg,image/png,image/webp", hidden: true });
    const enviar = h("button", { type: "button", class: "btn leve", onclick: () => arquivo.click() }, "Enviar imagem");
    arquivo.addEventListener("change", async () => {
      if (!arquivo.files[0]) return;
      const form = new FormData();
      form.append("imagem", arquivo.files[0]);
      enviar.disabled = true;
      enviar.textContent = "Enviando…";
      try {
        const r = await fetch(`/api/c/${D.cliente}/site/imagem`, { method: "POST", body: form });
        const dados = await r.json();
        if (!r.ok) throw new Error(dados.erro || "Não foi possível enviar.");
        assets = dados.assets;
        alvo[chave] = dados.nome;
        marcar();
        preencher();
        toast(`Imagem ${dados.nome} enviada.`);
      } catch (e) {
        toast(e.message);
      } finally {
        enviar.disabled = false;
        enviar.textContent = "Enviar imagem";
        arquivo.value = "";
      }
    });
    preencher();
    return h("div", { class: "se-imagem" }, mini, h("div", { class: "se-imagem-ctrl" }, sel, enviar, arquivo));
  }

  function campoItens(def, alvo, chave) {
    if (!Array.isArray(alvo[chave])) alvo[chave] = [];
    const caixa = h("div", { class: "se-campo se-itens" });
    const desenhar = () => {
      const itens = alvo[chave];
      const resumo = (it) => Object.values(it).find((v) => typeof v === "string" && v.trim()) || "(vazio)";
      caixa.replaceChildren(rotulo(def, h("span", { class: "se-cont" }, `${itens.length}${def.maximo ? "/" + def.maximo : ""}`)));
      itens.forEach((it, i) => {
        const mover = (d) => { const j = i + d; if (j < 0 || j >= itens.length) return; [itens[i], itens[j]] = [itens[j], itens[i]]; marcar(); desenhar(); };
        const corpo = h("div", { class: "se-item-corpo" }, def.campos.map((sub) => campo(sub, it, sub.nome, desenhar)));
        caixa.append(h("div", { class: "se-item-caixa" },
          h("details", { class: "se-item", open: !resumo(it) || resumo(it) === "(vazio)" },
            h("summary", {}, h("span", { class: "se-item-tit" }, `${i + 1}. ${String(resumo(it)).slice(0, 60)}`)),
            corpo),
          h("div", { class: "se-ctrl se-ctrl-flutuante", role: "group", "aria-label": `Ações do item ${i + 1}` },
            h("button", { type: "button", title: "Subir", "aria-label": "Subir item", onclick: () => mover(-1) }, "↑"),
            h("button", { type: "button", title: "Descer", "aria-label": "Descer item", onclick: () => mover(1) }, "↓"),
            h("button", { type: "button", title: "Remover", "aria-label": "Remover item", onclick: () => { itens.splice(i, 1); marcar(); desenhar(); } }, "✕"))));
      });
      if (!def.maximo || itens.length < def.maximo) {
        caixa.append(h("button", { type: "button", class: "btn leve se-add", onclick: () => {
          const novo = {};
          def.campos.forEach((c) => { novo[c.nome] = c.tipo === "sim_nao" ? false : c.tipo === "lista" ? [] : ""; });
          itens.push(novo);
          marcar();
          desenhar();
        } }, `+ ${def.rotulo.replace(/s$/, "")}`));
      }
      if (def.ajuda) caixa.append(h("p", { class: "se-ajuda" }, def.ajuda));
    };
    desenhar();
    return caixa;
  }

  // ------------------------------------------------------------ aba Páginas
  function novaPagina(destino) {
    const tipo = h("select", { class: "sel" }, Object.entries(CAT.tipos_pagina).filter(([k]) => k !== "inicio").map(([k, r]) => h("option", { value: k }, r)));
    const titulo = h("input", { type: "text", placeholder: "Ex.: Tráfego pago para restaurantes" });
    const slug = h("input", { type: "text", placeholder: "trafego-pago-restaurantes" });
    titulo.addEventListener("input", () => {
      slug.value = titulo.value.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 60);
    });
    const erro = h("p", { class: "se-ajuda alerta", hidden: true });
    const criar = () => {
      const s = slug.value.trim();
      if (!titulo.value.trim() || !/^[a-z0-9]+(-[a-z0-9]+)*$/.test(s) || ["blog", "assets"].includes(s) || site.paginas.some((p) => p.slug === s)) {
        erro.textContent = "Dê um título e um endereço único, só com letras minúsculas, números e hífen.";
        erro.hidden = false;
        return;
      }
      const e = site.empresa;
      const t = titulo.value.trim();
      site.paginas.push({
        slug: s, tipo: tipo.value, titulo_pagina: `${t} | ${e.nome}`.slice(0, 60),
        descricao: `${t} com a ${e.nome}, em ${e.cidade}. Fale pelo WhatsApp.`.slice(0, 160), menu: t,
        ...(tipo.value === "servico" ? { servico_nome: t } : {}),
        blocos: [
          { tipo: "cabecalho_pagina", titulo: t, resumo: "", mostrar_botao: true },
          { tipo: "texto", olho: "", titulo: "", secoes: [{ titulo: "", texto: "Escreva aqui a resposta direta ao que o cliente pergunta." }] },
          { tipo: "chamada_final", olho: "Vamos conversar", titulo: `Fale com a ${e.nome}`, texto: "", imagem_fundo: "" },
        ],
      });
      pag = site.paginas.length - 1;
      aberto = null;
      marcar();
      desenharPaginas();
      toast("Página criada. Salve para ver na prévia.");
    };
    destino.replaceChildren(h("div", { class: "se-nova" },
      h("div", { class: "se-campo" }, rotulo({ rotulo: "Tipo" }), tipo),
      h("div", { class: "se-campo" }, rotulo({ rotulo: "Título da página" }), titulo),
      h("div", { class: "se-campo" }, rotulo({ rotulo: "Endereço" }), h("div", { class: "se-slug" }, h("span", {}, site.dominio + "/"), slug)),
      erro,
      h("div", { class: "se-linha" }, h("button", { type: "button", class: "btn primario", onclick: criar }, "Criar página"),
        h("button", { type: "button", class: "btn leve", onclick: () => destino.replaceChildren() }, "Cancelar"))));
    titulo.focus();
  }

  function cartaoBloco(p, b, i) {
    const def = CAT.blocos[b.tipo];
    const mover = (d) => {
      const j = i + d;
      if (j < 0 || j >= p.blocos.length) return;
      [p.blocos[i], p.blocos[j]] = [p.blocos[j], p.blocos[i]];
      aberto = aberto === i ? j : aberto;
      marcar();
      desenharPaginas();
    };
    const ctrl = (t, r, fn) => h("button", { type: "button", title: r, "aria-label": r, onclick: (e) => { e.preventDefault(); e.stopPropagation(); fn(); } }, t);
    const det = h("details", { class: "se-bloco", open: aberto === i },
      h("summary", {},
        h("span", { class: "se-bloco-n" }, String(i + 1).padStart(2, "0")),
        h("span", { class: "se-bloco-tit" }, h("b", {}, def?.rotulo || b.tipo), h("span", {}, primeiroTexto(b).slice(0, 70)))),
      def ? h("div", { class: "se-bloco-corpo" }, h("p", { class: "se-ajuda" }, def.descricao), def.campos.map((c) => campo(c, b, c.nome))) : h("p", {}, "Bloco desconhecido."));
    det.addEventListener("toggle", () => {
      if (det.open) {
        aberto = i;
        qq(".se-bloco[open]", painel("paginas")).forEach((o) => { if (o !== det) o.open = false; });
        destacar(i);
      }
    });
    // botões fora do <summary>: controle dentro de controle confunde leitor de tela e teclado
    return h("li", { class: "se-bloco-item" }, det,
      h("div", { class: "se-ctrl se-ctrl-flutuante", role: "group", "aria-label": `Ações do bloco ${i + 1}` },
        ctrl("↑", "Subir bloco", () => mover(-1)), ctrl("↓", "Descer bloco", () => mover(1)),
        ctrl("⧉", "Duplicar bloco", () => { p.blocos.splice(i + 1, 0, structuredClone(b)); marcar(); desenharPaginas(); }),
        ctrl("✕", "Remover bloco", () => { p.blocos.splice(i, 1); aberto = null; marcar(); desenharPaginas(); })));
  }

  function desenharPaginas() {
    const alvo = painel("paginas");
    const p = site.paginas[pag];
    const espacoNova = h("div");
    const abas = h("div", { class: "se-paginas" },
      site.paginas.map((pg, i) => h("button", { type: "button", class: i === pag ? "atual" : "", onclick: () => { pag = i; aberto = null; desenharPaginas(); irPrevia(); } }, rotuloPagina(pg))),
      h("button", { type: "button", class: "nova", onclick: () => novaPagina(espacoNova) }, "+ Página"));

    const camposPagina = CAT.pagina_campos.filter((c) => !c.so_tipo || c.so_tipo === p.tipo).map((c) => campo(c, p, c.nome));
    if (p.slug !== "") {
      camposPagina.push(h("div", { class: "se-campo" }, rotulo({ rotulo: "Endereço" }),
        h("div", { class: "se-slug" }, h("span", {}, site.dominio + "/"),
          h("input", { type: "text", value: p.slug, oninput: (e) => { p.slug = e.target.value.trim(); marcar(); } }), h("span", {}, "/")),
        h("p", { class: "se-ajuda" }, "Trocar o endereço de uma página já publicada quebra links. Combine um redirecionamento.")));
      camposPagina.push(h("button", { type: "button", class: "btn leve se-remover", onclick: () => {
        if (!confirm(`Remover a página “${rotuloPagina(p)}”? Ela sai do site na próxima vez que salvar.`)) return;
        site.paginas.splice(pag, 1);
        pag = 0;
        marcar();
        desenharPaginas();
        irPrevia();
      } }, "Remover esta página"));
    }
    const dadosPagina = h("details", { class: "se-grupo" },
      h("summary", {}, "Página ", h("b", {}, rotuloPagina(p)), h("span", { class: "se-sub" }, ` · ${CAT.tipos_pagina[p.tipo] || p.tipo} · /${p.slug ? p.slug + "/" : ""}`)),
      h("div", { class: "se-grupo-corpo" }, camposPagina));

    const novoTipo = h("select", { class: "sel", "aria-label": "Tipo de bloco" },
      Object.entries(CAT.blocos).map(([k, d]) => h("option", { value: k }, d.rotulo)));
    const adicionar = h("div", { class: "se-add-bloco" }, novoTipo, h("button", { type: "button", class: "btn", onclick: () => {
      const tipo = novoTipo.value;
      const novo = { tipo };
      CAT.blocos[tipo].campos.forEach((c) => {
        novo[c.nome] = "padrao" in c ? c.padrao : c.tipo === "itens" || c.tipo === "lista" ? [] : c.tipo === "sim_nao" ? false : "";
      });
      const posicao = aberto != null ? aberto + 1 : p.blocos.length;
      p.blocos.splice(posicao, 0, novo);
      aberto = posicao;
      marcar();
      desenharPaginas();
    } }, "Adicionar bloco"));

    alvo.replaceChildren(abas, espacoNova, dadosPagina,
      h("div", { class: "se-rot-secao" }, `Blocos da página · ${p.blocos.length}`),
      h("ol", { class: "se-blocos" }, p.blocos.map((b, i) => cartaoBloco(p, b, i))),
      adicionar);
    desenharSeletorPrevia();
  }

  // ------------------------------------------------------------ aba Configurações
  function desenharConfig() {
    painel("config").replaceChildren(...CAT.configuracoes.map((g, n) => {
      const alvo = g.caminho ? garantir(site, g.caminho) : site;
      return h("details", { class: "se-grupo", open: n === 0 },
        h("summary", {}, h("b", {}, g.grupo)),
        h("div", { class: "se-grupo-corpo" }, g.ajuda ? h("p", { class: "se-ajuda" }, g.ajuda) : null, g.campos.map((c) => campo(c, alvo, c.nome))));
    }));
  }

  // ------------------------------------------------------------ aba Antes de publicar
  function desenharChecagem() {
    const alvo = painel("checagem");
    const cont = q("[data-cont-checagem]", raiz);
    if (!checagem) {
      alvo.replaceChildren(h("p", { class: "se-ajuda" }, "Conferindo…"));
      return;
    }
    const n = checagem.contagem;
    cont.textContent = n.erro ? String(n.erro) : n.aviso ? String(n.aviso) : "✓";
    cont.className = n.erro ? "erro" : n.aviso ? "aviso" : "ok";
    alvo.replaceChildren(
      h("div", { class: "se-resumo-check " + (n.erro ? "erro" : "ok") },
        h("b", {}, n.erro ? `${n.erro} erro(s) impedem publicar` : "Pode publicar"),
        h("span", {}, `${n.aviso} aviso(s) · ${n.ok} ok · ${checagem.paginas} páginas conferidas na versão para publicar`)),
      h("ul", { class: "se-check-lista" }, checagem.itens.map((i) => h("li", { class: i.nivel },
        h("span", { class: "se-nivel" }, { erro: "Erro", aviso: "Aviso", ok: "Ok" }[i.nivel]),
        h("div", {}, h("b", {}, i.mensagem), h("span", { class: "se-sub" }, [i.area, i.pagina].filter(Boolean).join(" · ")),
          i.resolver ? h("p", {}, i.resolver) : null)))),
      h("button", { type: "button", class: "btn leve", onclick: conferir }, "Conferir de novo"));
  }

  async function conferir() {
    checagem = null;
    desenharChecagem();
    try {
      checagem = (await api(`/api/c/${D.cliente}/site/checar`)).checagem;
    } catch (e) {
      toast(e.message);
    }
    desenharChecagem();
    irPrevia();
  }

  // ------------------------------------------------------------ prévia
  const caminhoPrevia = (slug) => `${D.previa}${slug ? slug + "/" : ""}`;
  function desenharSeletorPrevia() {
    const sel = q("[data-previa-pagina]", raiz);
    sel.replaceChildren(...site.paginas.map((p, i) => h("option", { value: String(i), selected: i === pag }, rotuloPagina(p))),
      ...(site.blog?.ativo ? [h("option", { value: "blog" }, "Blog")] : []));
  }
  q("[data-previa-pagina]", raiz).addEventListener("change", (e) => {
    if (e.target.value === "blog") {
      iframe.src = `${D.previa}blog/?v=${Date.now()}`;
      return;
    }
    pag = Number(e.target.value);
    aberto = null;
    desenharPaginas();
    irPrevia();
  });
  function irPrevia() {
    const p = site.paginas[pag];
    const url = caminhoPrevia(p?.slug || "");
    iframe.src = `${url}?v=${Date.now()}`;
    q("[data-previa-aba]", raiz).href = url;
  }
  function destacar(i) {
    try {
      const doc = iframe.contentDocument;
      const el = doc && doc.querySelector(`[data-bloco="${i}"]`)?.firstElementChild;
      if (!el) return;
      // rola só a prévia: scrollIntoView arrastaria também a página do Portal
      const janela = doc.defaultView;
      janela.scrollTo({ top: el.getBoundingClientRect().top + janela.scrollY - 8, behavior: "smooth" });
      el.style.outline = "3px solid #bf4520";
      el.style.outlineOffset = "-3px";
      setTimeout(() => { el.style.outline = ""; }, 1400);
    } catch { /* prévia de outra origem: sem destaque */ }
  }
  iframe.addEventListener("load", () => { if (aberto != null) destacar(aberto); });
  qq("[data-dispositivo]", raiz).forEach((b) => b.addEventListener("click", () => {
    qq("[data-dispositivo]", raiz).forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    q("[data-moldura]", raiz).classList.toggle("celular", b.dataset.dispositivo === "celular");
  }));

  // ------------------------------------------------------------ abas, salvar e publicar
  qq("[data-se-aba]", raiz).forEach((b) => b.addEventListener("click", () => {
    qq("[data-se-aba]", raiz).forEach((x) => x.setAttribute("aria-selected", String(x === b)));
    qq("[data-se-painel]", raiz).forEach((p) => { p.hidden = p.dataset.sePainel !== b.dataset.seAba; });
  }));

  function mostrarErros(erros) {
    const caixa = q("[data-erros]", raiz);
    caixa.hidden = !erros.length;
    caixa.replaceChildren(...(erros.length ? [h("b", {}, `Corrija ${erros.length} item(ns) para salvar:`), h("ul", {}, erros.map((e) => h("li", {}, e)))] : []));
  }

  async function salvar() {
    if (salvando) return;
    salvando = true;
    estado("salvando…");
    try {
      const r = await api(`/api/c/${D.cliente}/site`, site);
      sujo = false;
      estado(`salvo às ${r.salvo_em}`, "ok");
      mostrarErros([]);
      checagem = r.checagem;
      desenharChecagem();
      irPrevia();
    } catch (e) {
      if (e.erros) {
        mostrarErros(e.erros);
        estado("não salvo: corrija os itens acima", "erro");
      } else {
        toast(e.message);
        estado("não salvo", "erro");
      }
    } finally {
      salvando = false;
    }
  }

  q("[data-salvar]", raiz).addEventListener("click", salvar);
  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
      e.preventDefault();
      salvar();
    }
  });

  q("[data-publicar]", raiz).addEventListener("click", async (ev) => {
    if (sujo) {
      toast("Salve antes de gerar a versão para publicar.");
      return;
    }
    const b = ev.currentTarget;
    b.disabled = true;
    b.textContent = "Gerando…";
    try {
      const r = await api(`/api/c/${D.cliente}/site/publicar`);
      checagem = r.checagem;
      desenharChecagem();
      q('[data-se-aba="checagem"]', raiz).click();
      const n = r.checagem.contagem;
      painel("checagem").prepend(h("div", { class: "se-publicado" },
        h("b", {}, n.erro ? "Versão gerada, mas com erros: corrija antes de subir." : "Versão para publicar gerada."),
        h("p", {}, "Sobe no Cloudflare Pages (ou em qualquer hospedagem) o conteúdo do .zip."),
        h("a", { class: "btn primario", href: r.baixar }, "Baixar .zip")));
    } catch (e) {
      toast(e.message);
    } finally {
      b.disabled = false;
      b.textContent = "Gerar versão para publicar";
    }
  });

  desenharPaginas();
  desenharConfig();
  desenharChecagem();
  conferir();
})();
