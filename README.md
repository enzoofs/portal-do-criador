# Portal do Criador

[![CI](https://github.com/enzoofs/portal-do-criador/actions/workflows/ci.yml/badge.svg)](https://github.com/enzoofs/portal-do-criador/actions/workflows/ci.yml)

Sistema da TimeLabs para fazer uma empresa aparecer no Google **e nas respostas das IAs**
(ChatGPT, Gemini, resumo de IA do Google), medindo o antes e o depois. Nome provisório.

O que ele faz, por cliente:

1. **Radar**: faz ao ChatGPT e ao Google as perguntas que um cliente real faria ("qual a melhor
   agência de tráfego pago em BH?"), várias vezes, e mede se a marca aparece, quem aparece no lugar
   e quais sites as IAs usaram como fonte. Mostra a margem de erro de cada número.
   Junto, o **rastreamento do site**: percorre página por página como um robô de IA (sem executar
   JavaScript, respeitando o robots.txt) e cruza com o radar: qual página do site responde a cada
   pergunta, se as páginas que as IAs citaram estão abrindo e o que as páginas de concorrentes citadas
   têm que as do cliente não têm. Grátis: não usa IA nem API paga.
2. **Plano de ações**: o que corrigir (identidade da empresa, robôs bloqueados, presença em sites de
   terceiros, avaliações, páginas que faltam ou estão fracas), com guias prontos. Um novo rastreamento
   confirma sozinho o que foi corrigido no site.
3. **Conteúdo**: pauta e artigos escritos a partir do radar. O redator não inventa dados: o que falta
   vira pendência para o especialista responder num formulário. Envio sempre como rascunho
   (WordPress, Webflow, Shopify ou Wix).
4. **Resultados**: visitas vindas de IAs e cliques no WhatsApp (GA4 e Search Console).
5. **Mídia paga**: os termos que o cliente compra no Google Ads viram perguntas do radar e pauta.
6. **Site do cliente com blog**: editor por blocos com prévia ao vivo, checagens antes de publicar e
   .zip para subir no domínio do cliente. Páginas estáticas com o texto inteiro no HTML, fichas para
   Google e IAs, e nada carregado de outro domínio. Ver [docs/SITES.md](docs/SITES.md).

**Estado:** protótipo funcional que roda localmente (Flask, um usuário, sem login). Um cliente real
já passou pelo radar com coleta paga; os dados dele não estão neste repositório (ver
[docs/LGPD.md](docs/LGPD.md)). Desenho técnico e limitações em [docs/ARQUITETURA.md](docs/ARQUITETURA.md);
a auditoria antes da publicação está em [docs/AUDITORIA.md](docs/AUDITORIA.md).

## Requisitos

- Python 3.11 ou mais novo (desenvolvido em 3.14, Windows 10; o CI testa 3.11 e 3.14 no Linux)
- Chaves de API são opcionais. Sem nenhuma, tudo roda em **modo demonstração** (respostas fictícias,
  marcadas como tal em todas as telas).

## Como rodar

```bash
python -m venv venv
venv\Scripts\activate              # Windows  (Linux/macOS: source venv/bin/activate)
pip install -r requirements-lock.txt
copy .env.example .env             # Linux/macOS: cp .env.example .env
python main.py servir              # abre http://127.0.0.1:5050
```

No Windows, `ABRIR-PORTAL.bat` faz o último passo com dois cliques.

O repositório traz um cliente **fictício**, `exemplo` (Agência Exemplo, domínio `.example`). Para ver
as telas com dados sem gastar nada:

```bash
python main.py radar exemplo --demo
python main.py pauta exemplo --demo
python main.py escrever exemplo      # pauta de demonstração = artigos de demonstração, sem custo
python main.py site exemplo          # prévia do site em entregas/exemplo/site-novo/
python main.py site exemplo --publicar && python main.py rastrear exemplo --demo   # rastreia o site gerado, sem rede
```

O `exemplo.json` do repositório vem sem perguntas: cadastre algumas em **Configurar** antes do radar
de demonstração, ou ele sai vazio.

### Compartilhar com a equipe (ngrok)

Para a equipe usar o Portal que roda nesta máquina, por um tempo (um teste, uma reunião):

1. Uma vez: conta grátis no [ngrok](https://dashboard.ngrok.com) e `ngrok config add-authtoken <token>`.
2. No `.env`: `PORTAL_HOST_PUBLICO` (o domínio do túnel, sem `https://`) e `PORTAL_SENHA` (12
   caracteres ou mais). O usuário é `equipe` (`PORTAL_USUARIO` muda).
3. `python main.py servir --sem-navegador` e, em outro terminal, `ngrok http 5050 --url https://<domínio>`.

No endereço do túnel, todo pedido exige usuário e senha; sem senha no `.env`, ele fica fechado. Quem
tem a senha faz tudo o que o operador faz (inclusive execuções pagas e ver todos os clientes): mande
por mensagem, nunca junto com o link, e feche o túnel (Ctrl+C) quando acabar. Ver [SECURITY.md](SECURITY.md).

## Testes e checagens

```bash
python testes.py                     # 28 testes, sem IA, sem rede, sem custo
ruff check .                         # estilo, erros e regras de segurança (pyproject.toml)
bandit -c pyproject.toml -r . -q
```

Cada teste reproduz um erro real já corrigido ou um comportamento combinado (ver a docstring de cada
um): análise do radar, pendências, geração e checagem do site, rastreamento e cruzamento com o radar
(sobre um site falso em memória), LGPD (exportar e apagar) e segurança (leitura de arquivo fora da
pasta, CSRF, DNS rebinding, XSS, SSRF, upload). O CI roda tudo isso a cada push, mais
`pip-audit` nas dependências e `gitleaks` no histórico. Como contribuir: [CONTRIBUTING.md](CONTRIBUTING.md).

## Custos: nada pago roda sem confirmação

Toda chamada paga (IA ou coleta) passa por `custos.py`:

- **Linha de comando:** sem `--confirmar`, `radar`, `pauta` e `escrever` só mostram a
  estimativa em dólar e saem. Com `--confirmar`, rodam com teto de gasto (`--limite`, padrão US$ 2).
- **App:** a janela de custo mostra a estimativa antes de cada execução.
- **Segunda trava:** `custos.contador.checar()` recusa qualquer chamada paga que não tenha passado
  por uma das confirmações acima.

O gasto real de cada execução vai para `data/gastos.jsonl` (uso interno; não aparece no app).

## Comandos

| Comando | O que faz |
|---|---|
| `python main.py servir [--porta 5050] [--sem-navegador]` | Abre o app |
| `python main.py radar <cliente> [--demo] [--ias chatgpt_app,google_ia] [--repeticoes 3] [--confirmar]` | Mede a visibilidade nas IAs |
| `python main.py relatorio data/runs/<cliente>/<arquivo>.json` | Recalcula e regera o relatório HTML |
| `python main.py rastrear <cliente> [--limite 300] [--demo]` | Percorre o site como um robô de IA (grátis); o radar já faz isso sozinho |
| `python main.py pauta <cliente> [--demo] [--confirmar]` | Monta a pauta de artigos a partir do último radar |
| `python main.py escrever <cliente> [--temas 1,3] [--confirmar]` | Escreve os artigos (rascunhos) |
| `python main.py wordpress <cliente> <slug\|todos> [--publicar]` | Envia ao site do cliente como rascunho |
| `python main.py indexnow <cliente> <url>...` | Avisa o Bing sobre URLs publicadas |
| `python main.py guias <cliente>` | Refaz os guias do plano a partir do último radar real (o radar real já faz sozinho) |
| `python main.py entregas <cliente>` | Gera o plano de correção em HTML |
| `python main.py site <cliente> [--publicar] [--com-pendencias]` | Gera o site completo do cliente; ver [docs/SITES.md](docs/SITES.md) |
| `python main.py exportar <cliente> [--destino pasta]` | Junta todos os dados do cliente num .zip (LGPD: acesso e portabilidade) |
| `python main.py esquecer <cliente> [--confirmar]` | Apaga todos os dados do cliente (LGPD: eliminação); sem `--confirmar`, só lista |

## Configuração (`.env`)

Todas as variáveis estão documentadas em [.env.example](.env.example). As principais:

| Variável | Para quê |
|---|---|
| `DATAFORSEO_LOGIN`, `DATAFORSEO_SENHA` | Coleta das respostas como aparecem no app do ChatGPT, Gemini e Google (~US$ 0,004 por pergunta) |
| `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY` | Extração, pauta e redação (e coleta via API, se não houver DataForSEO) |
| `RADAR_PROVEDORES` | Quais coletas o radar usa, ex.: `chatgpt_app,google_ia` |
| `GERACAO_PROVEDORES` | Ordem de preferência para pauta e artigos, ex.: `openai` |
| `GOOGLE_CREDENCIAIS` | Caminho do JSON da conta de serviço (GA4 e Search Console, só leitura) |
| `WP_<CLIENTE>_USUARIO`, `WP_<CLIENTE>_SENHA_APP`, `WEBFLOW_…`, `SHOPIFY_…`, `WIX_…` | Publicação como rascunho no site de cada cliente |

Clientes ficam em `config/clientes/<id>.json` (criados pela tela **Novo cliente**, que pode ler o site
da empresa para preencher o cadastro). Só o `exemplo.json` vai para o Git.

## Estrutura

```
main.py                   linha de comando (todas as operações)
config/
  settings.py             configuração única: caminhos, modelos, chaves lidas do .env
  clientes/<id>.json      perfil e perguntas de cada cliente (no Git, só o exemplo)
  sites/<id>/             textos, marca e imagens do site de cada cliente (no Git, só o exemplo)
radar/                    medição de visibilidade
  provedores/             coletas: DataForSEO (app do ChatGPT/Gemini, Google), APIs OpenAI/Claude/Gemini, demo
  executor.py             roda perguntas × IAs × rodadas em paralelo e salva em data/runs/
  extrator.py             tira de cada resposta: a marca aparece? quem foi recomendado?
  analise.py              métricas, ranking de concorrentes, tipos de fonte
  auditoria.py            checagens da página inicial (robôs, robots.txt pelo RFC 9309, sitemap, identidade)
  pagina.py               o que um robô encontra numa página HTML (título, texto, links, fichas)
  rastreador.py           percorre o site página por página e lista os problemas; salva em data/rastreios/
  cruzamento.py           radar × rastreamento: pergunta × página, páginas citadas, ações do plano
  relatorio.py            relatório HTML autocontido
conteudo/                 pauta → artigos → publicação
  pauta.py, redator.py    temas e artigos (com marcadores [[...]] para o que falta)
  pendencias.py           marcadores viram campos para o especialista
  render.py               HTML do post, JSON-LD, Markdown seguro, prévia e central de conteúdo
  publicador.py           WordPress e IndexNow
  plataformas.py          Webflow, Shopify e Wix
  fluxo.py                orquestra a escrita e atualiza a central
site_cliente/             site do cliente
  blocos.py               catálogo de blocos e validação
  gerador.py, checagem.py geração estática e checagens antes de publicar
  inicial.py              rascunho a partir do cadastro
  modelos/                Jinja, um arquivo por bloco
  fontes/                 fontes do catálogo (woff2 + licença), servidas pelo próprio site
midia/termos.py           importa termos de pesquisa do Google Ads (CSV)
medicao.py                GA4 e Search Console
cadastro.py               rascunho do cadastro de cliente a partir do site
guias/                    modelos dos guias do plano, preenchidos com o radar de cada cliente
plano_correcao.py         plano de correção (guias em entregas/<cliente>/*.md)
ia.py                     chamada de IA com saída estruturada (Claude ou OpenAI)
custos.py, orcamento.py   preços, estimativas, trava de gasto, registro de gastos
rede.py                   downloads feitos pelo servidor, sem acesso à rede interna (SSRF)
privacidade.py            exportar e apagar os dados de um cliente (LGPD)
app/                      app web (Flask + waitress)
  servidor.py             rotas e API
  seguranca.py            caminhos, origem dos pedidos, Hosts, CSP e cabeçalhos
  tarefas.py              execuções pagas em segundo plano, com progresso
  telas.py, dados.py      dados de cada tela e acesso a arquivos
  templates/, static/     telas (Jinja), CSS e JS sem framework
assets/fonts/             Geist (interface e relatórios; licença em OFL.txt)
docs/                     arquitetura, sites, LGPD, auditoria e pesquisa
exemplos/                 CSV fictício do Google Ads para testar a importação
testes.py                 testes (sem IA, sem rede)
.github/                  CI e Dependabot
pyproject.toml            configuração do ruff, bandit e pytest
```

Pastas criadas pelo uso e fora do Git: `data/` (radares, pautas, artigos, medições, gastos),
`entregas/` (guias e sites gerados) e `relatorios/` (HTML e exportações).

## Segurança e dados pessoais

- O app só escuta em `127.0.0.1` e foi feito para um operador, na máquina dele. Proteções, modelo de
  ameaça e como relatar uma falha: [SECURITY.md](SECURITY.md).
- Chaves só no `.env`, que está no `.gitignore`. Nunca no código nem no `.env.example`.
- Dados de clientes não entram no Git. Inventário, papéis, fornecedores, retenção e direitos do titular:
  [docs/LGPD.md](docs/LGPD.md).
- Publicação em sites de clientes é sempre rascunho; publicar direto é bloqueado enquanto houver
  pendência no texto.

## Licença

Proprietário: todos os direitos reservados à TimeLabs ([LICENSE](LICENSE)). O repositório está público
temporariamente, para avaliação técnica.

## Créditos

Visual do relatório inspirado no [diagram-design](https://github.com/cathrynlavery/diagram-design) (MIT).
Fonte Geist (SIL Open Font License). Fontes dos sites gerados via [Fontsource](https://fontsource.org)
(SIL Open Font License; licença junto de cada família em `site_cliente/fontes/`).
