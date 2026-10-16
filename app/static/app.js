// Portal do Criador — interações do app: execuções pagas (janela de custo + progresso), gaveta com as
// respostas do radar, seleção e filtro do conteúdo, abas do editor, paleta (Ctrl K) e atalhos.

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const digitando = (el) => el && (el.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName));

async function api(url, corpo) {
  const r = await fetch(url, corpo === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo),
  });
  const dados = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(dados.erro || `Erro ${r.status}`);
  return dados;
}

function aviso(texto) {
  const el = document.createElement("div");
  el.className = "toast";
  el.setAttribute("role", "status");
  el.textContent = texto;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 5200);
}
$$(".toast").forEach((el) => setTimeout(() => el.remove(), 5200));

const NOMES = { radar: "Radar de visibilidade", pauta: "Pauta de conteúdo", artigos: "Escrever artigos" };
const usd = (v) => "US$ " + Number(v).toFixed(2).replace(".", ",");
// Texto vindo do servidor que entra em innerHTML passa por aqui (a CSP é a segunda barreira)
const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

// ---------------------------------------------------------------- execuções
function painelExecucao(tarefa) {
  let el = $(".execucao");
  if (!el) {
    el = document.createElement("div");
    el.className = "execucao";
    el.setAttribute("role", "status");
    document.body.appendChild(el);
  }
  const rodando = tarefa.status === "rodando";
  el.innerHTML = `<div class="eyebrow">${rodando ? '<span class="spin"></span>em andamento' :
      tarefa.status === "ok" ? "concluído" : "terminou com erro"}</div>
    <h3>${esc(NOMES[tarefa.tipo] || tarefa.tipo)}</h3><pre></pre>
    ${rodando ? "" : '<div class="acoes"><button class="btn peq" data-recarregar>Ver resultado</button></div>'}`;
  const pre = $("pre", el);
  pre.textContent = tarefa.linhas.slice(-40).join("\n");
  pre.scrollTop = pre.scrollHeight;
  const b = $("[data-recarregar]", el);
  if (b) b.onclick = () => location.reload();
}

async function acompanhar(id) {
  const t = await api(`/api/tarefas/${id}`);
  painelExecucao(t);
  if (t.status === "rodando") setTimeout(() => acompanhar(id), 1500);
  else $$("[data-tarefa]").forEach((b) => (b.disabled = false));
}

async function iniciar(cid, tipo, extra) {
  $$("[data-tarefa]").forEach((b) => (b.disabled = true));
  try {
    const t = await api(`/api/c/${cid}/tarefas`, { tipo, ...extra });
    acompanhar(t.id);
  } catch (e) {
    alert(e.message);
    $$("[data-tarefa]").forEach((b) => (b.disabled = false));
  }
}

// ---------------------------------------------------------------- janela de custo
async function pedirConfirmacao(botao) {
  const { cliente: cid, tarefa: tipo } = botao.dataset;
  const temas = botao.dataset.temas ? botao.dataset.temas.split(",").map(Number) : null;
  if (botao.dataset.demo !== undefined) return iniciar(cid, tipo, { demo: true, temas });

  const dlg = $("#custo");
  const rodadas = $("select[name=rodadas]", dlg);
  $("[data-rodadas]", dlg).hidden = tipo !== "radar";
  if (tipo !== "radar") rodadas.value = "1";
  const est = await api(`/api/c/${cid}/estimativa`, { tipo, temas, repeticoes: Number(rodadas.value) });
  $("[data-titulo]", dlg).textContent = NOMES[tipo] || tipo;
  $("tbody", dlg).innerHTML = est.linhas.map((l) => `<tr><td>${esc(l.item)}</td><td>${usd(l.usd)}</td></tr>`).join("")
    + `<tr class="total"><td>Total estimado</td><td>${usd(est.total)}</td></tr>`;
  const teto = $("input[name=limite]", dlg);
  teto.value = Math.max(est.limite, Math.ceil(est.total * 1.5 * 100) / 100).toFixed(2);
  $("[data-sem-chave]", dlg).hidden = !est.sem_chave;
  $("[data-confirmar]", dlg).disabled = est.sem_chave;
  // a demonstração (grátis, respostas fictícias) fica aqui dentro, e só para o radar
  const demo = $("[data-demo-rodar]", dlg);
  demo.hidden = tipo !== "radar";
  demo.onclick = () => { dlg.close(); iniciar(cid, tipo, { demo: true, temas, repeticoes: Number(rodadas.value) }); };
  dlg.showModal();
  $("[data-confirmar]", dlg).onclick = () => {
    dlg.close();
    iniciar(cid, tipo, { confirmado: true, limite: Number(teto.value), temas, repeticoes: Number(rodadas.value), opcoes });
  };
  // trocar as rodadas refaz a estimativa
  rodadas.onchange = () => { dlg.close(); pedirConfirmacao(botao).catch((e) => alert(e.message)); };
}

document.addEventListener("click", (ev) => {
  const b = ev.target.closest("[data-tarefa]");
  if (b) { ev.preventDefault(); ev.stopPropagation(); pedirConfirmacao(b).catch((e) => alert(e.message)); }
  if (ev.target.closest("[data-fechar]")) ev.target.closest("dialog").close();
});

// ---------------------------------------------------------------- andamento das ações do plano
document.addEventListener("click", async (ev) => {
  const b = ev.target.closest(".status-acao button");
  if (!b) return;
  const grupo = b.parentElement;
  await api(`/api/c/${grupo.dataset.cliente}/plano`, { titulo: grupo.dataset.titulo, status: b.dataset.s });
  grupo.querySelectorAll("button").forEach((x) => {
    x.classList.toggle("sel", x === b);
    x.setAttribute("aria-pressed", x === b);
  });
  const li = b.closest(".acao");
  if (li) li.classList.toggle("feito", b.dataset.s === "feito");
  const feitas = $$('.status-acao button.sel[data-s="feito"]').length;
  const total = $$(".status-acao").length;
  const barra = $(".progresso i");
  if (barra) barra.style.width = `${(100 * feitas) / total}%`;
  const rot = $("[data-feitas]");
  if (rot) rot.textContent = feitas;
  const lat = $("[data-lat-plano]");
  if (lat && li) lat.textContent = `${feitas}/${total}`;
});

// ---------------------------------------------------------------- contadores de caracteres
$$("[data-max]").forEach((campo) => {
  const cont = $(`[data-cont="${campo.name}"]`);
  const atualiza = () => {
    cont.textContent = `${campo.value.length}/${campo.dataset.max}`;
    cont.classList.toggle("alerta", campo.value.length > Number(campo.dataset.max));
  };
  campo.addEventListener("input", atualiza);
  atualiza();
});

// ---------------------------------------------------------------- linhas que levam a outra página
document.addEventListener("click", (ev) => {
  const tr = ev.target.closest("tr[data-href]");
  if (!tr || !tr.dataset.href || ev.target.closest("a, button") || tr.closest(".tab-art")) return;
  location.href = tr.dataset.href;
});

// ---------------------------------------------------------------- radar: gaveta com a resposta completa
const gaveta = $("#gaveta");
if (gaveta) {
  const ordem = [...new Set($$("[data-resposta]").map((b) => b.dataset.resposta))];
  let atual = null;
  const abrir = (i) => {
    const tpl = document.getElementById(`resp-${i}`);
    if (!tpl) return;
    atual = String(i);
    $("[data-gaveta-rot]", gaveta).textContent = `${tpl.dataset.rot} · ${ordem.indexOf(atual) + 1} de ${ordem.length}`;
    const corpo = $("[data-gaveta-corpo]", gaveta);
    corpo.replaceChildren(tpl.content.cloneNode(true));
    corpo.scrollTop = 0;
    if (!gaveta.open) gaveta.showModal();
  };
  const andar = (passo) => {
    const k = ordem.indexOf(atual) + passo;
    if (k >= 0 && k < ordem.length) abrir(ordem[k]);
  };
  document.addEventListener("click", (ev) => {
    const b = ev.target.closest("[data-resposta]");
    if (b) abrir(b.dataset.resposta);
    const ir = ev.target.closest("[data-gaveta-ir]");
    if (ir) andar(Number(ir.dataset.gavetaIr));
  });
  gaveta.addEventListener("keydown", (ev) => {
    if (ev.key === "ArrowRight") { ev.preventDefault(); andar(1); }
    if (ev.key === "ArrowLeft") { ev.preventDefault(); andar(-1); }
  });
  gaveta.addEventListener("click", (ev) => { if (ev.target === gaveta) gaveta.close(); });
}

// ---------------------------------------------------------------- radar: a barra de seções marca onde você está
const secoesNav = $(".secoes-nav");
if (secoesNav) {
  const links = $$("a", secoesNav);
  const secoes = links.map((a) => document.querySelector(a.getAttribute("href")));
  const marcar = () => {
    const linha = secoesNav.getBoundingClientRect().bottom + 48;
    let atual = 0;
    secoes.forEach((s, k) => { if (s.getBoundingClientRect().top <= linha) atual = k; });
    if (innerHeight + scrollY >= document.documentElement.scrollHeight - 4) atual = secoes.length - 1;
    links.forEach((a, k) => a.classList.toggle("ativa", k === atual));
  };
  addEventListener("scroll", marcar, { passive: true });
  marcar();
}

// ---------------------------------------------------------------- conteúdo: seleção, filtro e inspetor
const insp = $("[data-insp]");
if (insp) {
  const linhas = $$(".tab-art tbody tr[data-slug]");
  const semItens = $(".tab-art tr.sem-itens");
  const visiveis = () => linhas.filter((l) => !l.hidden);
  const inspetorVisivel = () => getComputedStyle(insp).display !== "none";
  const abrirEditor = (tr) => { if (tr.dataset.href) location.href = tr.dataset.href; };

  const selecionar = (tr, focar, marcarUrl = true) => {
    if (!tr) { insp.innerHTML = '<div class="insp-vazio">Nenhum artigo nesta etapa.</div>'; return; }
    linhas.forEach((l) => l.classList.toggle("sel", l === tr));
    const tpl = document.getElementById(`insp-${tr.dataset.slug}`);
    if (tpl) insp.replaceChildren(tpl.content.cloneNode(true));
    if (marcarUrl) history.replaceState(null, "", `#${tr.dataset.slug}`);
    if (focar) { tr.focus({ preventScroll: true }); tr.scrollIntoView({ block: "nearest" }); }
  };

  linhas.forEach((tr) => {
    tr.addEventListener("click", (ev) => {
      if (ev.target.closest("a, button")) return;
      if (!inspetorVisivel()) return abrirEditor(tr);
      selecionar(tr);
    });
    tr.addEventListener("dblclick", () => abrirEditor(tr));
    tr.addEventListener("keydown", (ev) => {
      const vis = visiveis();
      const k = vis.indexOf(tr);
      if (ev.key === "ArrowDown" && k < vis.length - 1) { ev.preventDefault(); selecionar(vis[k + 1], true); }
      if (ev.key === "ArrowUp" && k > 0) { ev.preventDefault(); selecionar(vis[k - 1], true); }
      if (ev.key === "Enter") abrirEditor(tr);
    });
  });

  const rotulo = $("[data-filtro-rot]");
  const limpar = $('.lista-art [data-filtro=""]');
  const total = linhas.length;
  const filtrar = (status) => {
    $$(".etapa").forEach((e) => e.setAttribute("aria-pressed", e.dataset.filtro === status));
    linhas.forEach((l) => (l.hidden = !!status && l.dataset.status !== status));
    const n = visiveis().length;
    rotulo.textContent = status ? `${n} de ${total} artigos · ${status}` : `${total} artigos`;
    semItens.hidden = n > 0;
    if (!n) $("[data-sem-itens]", semItens).textContent = $(`.etapa[data-filtro="${status}"]`).dataset.vazio;
    limpar.hidden = !status;
    const sel = $(".tab-art tr.sel");
    if (!sel || sel.hidden) selecionar(visiveis()[0]);
  };
  $$("[data-filtro]").forEach((b) => b.addEventListener("click", () => {
    const ja = b.getAttribute("aria-pressed") === "true";
    filtrar(ja ? "" : b.dataset.filtro);
  }));

  const inicial = linhas.find((l) => `#${l.dataset.slug}` === location.hash) || linhas[0];
  if (inicial) selecionar(inicial, false, false);
}

// ---------------------------------------------------------------- copiar texto para o cliente
document.addEventListener("click", async (ev) => {
  const b = ev.target.closest("[data-copiar]");
  if (!b) return;
  const fonte = $(b.dataset.copiar);
  const texto = fonte.value ?? fonte.textContent;
  try {
    await navigator.clipboard.writeText(texto);
  } catch {
    const t = document.createElement("textarea");
    t.value = texto;
    document.body.appendChild(t);
    t.select();
    document.execCommand("copy");
    t.remove();
  }
  aviso(b.dataset.aviso || "Copiado. Cole no WhatsApp ou no e-mail.");
});

// ---------------------------------------------------------------- editor: abas e Ctrl S
$$(".abas-p [data-aba]").forEach((b) => b.addEventListener("click", () => {
  $$(".abas-p [data-aba]").forEach((x) => x.setAttribute("aria-selected", x === b));
  $$("[data-painel]").forEach((p) => (p.hidden = p.dataset.painel !== b.dataset.aba));
}));
document.addEventListener("keydown", (ev) => {
  if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === "s") {
    const salvar = $('[form="f-artigo"][value="salvar"]') || $('[form="f-config"]');
    if (salvar) { ev.preventDefault(); salvar.click(); }
  }
});

// ---------------------------------------------------------------- guia: índice das seções
const indice = $("[data-indice]");
if (indice) {
  const titulos = $$(".doc h2");
  titulos.forEach((h, k) => {
    h.id = h.id || `secao-${k + 1}`;
    const a = document.createElement("a");
    a.href = `#${h.id}`;
    a.textContent = h.textContent;
    indice.appendChild(a);
  });
  if (!titulos.length) indice.closest(".pane").remove();
}

// ---------------------------------------------------------------- paleta (Ctrl K)
const paleta = $("#paleta");
let itensPaleta = null;
const sem_acento = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

function desenharPaleta(busca) {
  const termos = sem_acento(busca).split(/\s+/).filter(Boolean);
  const achados = itensPaleta.filter((i) => termos.every((t) => sem_acento(`${i.t} ${i.tipo}`).includes(t)));
  const ul = $("ul", paleta);
  ul.replaceChildren(...achados.slice(0, 60).map((it, k) => {
    const li = document.createElement("li");
    li.setAttribute("role", "option");
    li.setAttribute("aria-selected", k === 0);
    li.dataset.url = it.url;
    const tipo = document.createElement("span");
    tipo.textContent = it.tipo;
    li.append(it.t, tipo);
    return li;
  }));
  if (!achados.length) ul.innerHTML = '<li class="vazio">Nada encontrado.</li>';
}

async function abrirPaleta() {
  if (!itensPaleta) itensPaleta = await api(`/api/paleta?c=${document.body.dataset.cliente || ""}`);
  const campo = $("input", paleta);
  campo.value = "";
  desenharPaleta("");
  paleta.showModal();
  campo.focus();
}

if (paleta) {
  const campo = $("input", paleta);
  campo.addEventListener("input", () => desenharPaleta(campo.value));
  campo.addEventListener("keydown", (ev) => {
    const itens = $$("li[data-url]", paleta);
    const k = itens.findIndex((li) => li.getAttribute("aria-selected") === "true");
    const marcar = (n) => {
      itens.forEach((li, j) => li.setAttribute("aria-selected", j === n));
      itens[n]?.scrollIntoView({ block: "nearest" });
    };
    if (ev.key === "ArrowDown") { ev.preventDefault(); marcar(Math.min(k + 1, itens.length - 1)); }
    if (ev.key === "ArrowUp") { ev.preventDefault(); marcar(Math.max(k - 1, 0)); }
    if (ev.key === "Enter" && itens[k]) location.href = itens[k].dataset.url;
  });
  paleta.addEventListener("click", (ev) => {
    const li = ev.target.closest("li[data-url]");
    if (li) location.href = li.dataset.url;
    if (ev.target === paleta) paleta.close();
  });
  $$("[data-paleta]").forEach((b) => b.addEventListener("click", abrirPaleta));
  document.addEventListener("keydown", (ev) => {
    if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === "k") { ev.preventDefault(); abrirPaleta(); }
  });
}

// retoma o acompanhamento se a página abriu com uma execução em andamento
const ativa = document.body.dataset.tarefaAtiva;
if (ativa) { $$("[data-tarefa]").forEach((b) => (b.disabled = true)); acompanhar(ativa); }

// Pendências: digitar uma resposta já marca "usar"; a escolha muda a cara do item
$$("[data-pend]").forEach((item) => {
  const txt = item.querySelector("textarea"), sel = item.querySelector("select");
  const original = txt.value;
  const pintar = () => {
    item.classList.toggle("resolvida", sel.value === "usar");
    item.classList.toggle("tirada", sel.value === "tirar");
  };
  txt.addEventListener("input", () => {
    if (txt.value.trim() && txt.value !== original && sel.value === "depois") sel.value = "usar";
    pintar();
  });
  sel.addEventListener("change", pintar);
});

// Novo cliente: ler o site e preencher só os campos ainda vazios
const CAMPOS_SITE = { nome: "nome", site: "site", servico: "servico", cidade: "cidade", regiao: "regiao",
  whatsapp: "whatsapp", nichos: "nichos", servicos: "servicos", processo: "processo", diferenciais: "diferenciais",
  afirmacoes_a_confirmar: "afirmacoes", clientes_citados_no_site: "clientes", apelidos: "apelidos", tom: "tom" };
const PADRAO_NOVO = { cidade: "Belo Horizonte", regiao: "Minas Gerais" };
$$("[data-ler-site]").forEach((b) => b.addEventListener("click", async () => {
  const site = $("#ls-site").value.trim() || ($("[name=site]") || {}).value || "";
  const status = $("#ls-status");
  const comIa = b.dataset.lerSite === "ia";
  if (!site) { $("#ls-site").focus(); return; }
  $$("[data-ler-site]").forEach((x) => (x.disabled = true));
  status.hidden = false;
  status.textContent = comIa ? "Lendo o site e organizando o perfil…" : "Lendo o site…";
  try {
    const d = await api("/api/novo/ler-site", { site, com_ia: comIa });
    let n = 0;
    for (const [chave, nome] of Object.entries(CAMPOS_SITE)) {
      const el = $(`#f-novo [name=${nome}]`), v = d[chave];
      if (!el || v === undefined || v === "" || (Array.isArray(v) && !v.length)) continue;
      const atual = el.value.trim();
      if (atual && atual !== PADRAO_NOVO[nome]) continue;
      el.value = Array.isArray(v) ? v.join("\n") : v;
      el.classList.add("veio-do-site");
      n++;
    }
    const pags = (d.paginas || []).length;
    status.textContent = `${n} campo${n === 1 ? "" : "s"} preenchido${n === 1 ? "" : "s"} a partir de ${pags} página${pags === 1 ? "" : "s"}.`
      + (d.cnpj ? ` CNPJ no site: ${d.cnpj}.` : " O site não mostra CNPJ.")
      + (comIa ? " Confira antes de criar." : " Para nichos, serviços e diferenciais, use o botão com IA.");
  } catch (e) {
    status.textContent = e.message;
  } finally {
    $$("[data-ler-site]").forEach((x) => (x.disabled = false));
  }
}));
$$("#f-novo input, #f-novo textarea").forEach((el) => el.addEventListener("input", () => el.classList.remove("veio-do-site")));

// Resultados: projeção de 12 meses com premissas editáveis (sem custo, tudo no navegador)
$$("[data-projecao]").forEach((caixa) => {
  const num = (id) => Number($(`#${id}`, caixa).value) || 0;
  const fmt = (n) => Math.round(n).toLocaleString("pt-BR");
  const brl = (n) => "R$ " + fmt(n);
  const FATORES = [0.5, 1, 1.5];  // cauteloso, base, otimista: só as visitas por artigo mudam
  const calcular = () => {
    const art = num("pj-art"), mat = num("pj-mat"), vis = num("pj-vis");
    const conv = num("pj-conv") / 100, fech = num("pj-fech") / 100, valor = num("pj-val");
    // no mês t, rendem os artigos publicados até o mês t - maturação
    let ativosMes = 0;
    for (let t = 1; t <= 12; t++) ativosMes += art * Math.max(0, t - mat);
    FATORES.forEach((f, i) => {
      const visitas = ativosMes * vis * f, contatos = visitas * conv, clientes = contatos * fech;
      $(`[data-r=visitas-${i}]`, caixa).textContent = fmt(visitas);
      $(`[data-r=contatos-${i}]`, caixa).textContent = fmt(contatos);
      $(`[data-r=clientes-${i}]`, caixa).textContent = clientes < 10 ? clientes.toFixed(1).replace(".", ",") : fmt(clientes);
      $(`[data-r=valor-${i}]`, caixa).textContent = valor ? brl(clientes * valor) : "informe o valor";
    });
    const inicio = mat + 1;
    $("[data-r=leitura]", caixa).textContent = inicio > 12
      ? "Com essa maturação, nenhum artigo rende dentro de 12 meses."
      : `Os primeiros resultados aparecem a partir do mês ${inicio}. Cauteloso e otimista usam metade e uma vez e meia as visitas por artigo.`;
  };
  $$("input", caixa).forEach((el) => el.addEventListener("input", calcular));
  calcular();
});
