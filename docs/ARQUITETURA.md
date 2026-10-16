# Arquitetura

Visão técnica do Portal do Criador para quem vai revisar ou evoluir o código. O README cobre
instalação e uso.

## Visão geral

Aplicação Python monolítica, sem banco de dados: cada entidade é um arquivo JSON em disco.
A mesma lógica é usada por dois pontos de entrada:

- `main.py`: linha de comando (argparse), um subcomando por operação.
- `app/`: app web local em Flask, servido por waitress em `127.0.0.1:5050`. Operações longas
  (radar, pauta, artigos) rodam em threads (`app/tarefas.py`) e a tela consulta o
  progresso por `/api/tarefas/<id>`.

Não há login nem multiusuário: o app foi feito para rodar na máquina de quem opera.

## Fluxo principal

```
config/clientes/<id>.json  (perfil + perguntas)
        │
        ▼
radar/executor.py ──► provedores (coleta) ──► extrator (IA barata) ──► analise ──► data/runs/<id>/<data>.json
        │                                                                            │
        ├─► auditoria.py (página inicial, sem IA)                                     ▼
        └─► rastreador.py (site inteiro, em paralelo,  ──► data/rastreios/<id>/   cruzamento.py (radar × site)
            sem IA; também sozinho: main.py rastrear)                              │
                                                                         radar/relatorio.py → relatorios/*.html
                                                                         app/telas.py → telas do app e plano
        │
        ▼
conteudo/pauta.py ──► conteudo/redator.py ──► data/conteudo/<id>/<data>/<slug>.json + prévia .html
        │                                           │
        │                                  pendencias.py (especialista responde)
        ▼                                           ▼
plano_correcao.py → entregas/<id>/plano-de-correcao.html   publicador.py / plataformas.py → rascunho no site
```

## Módulos

| Módulo | Responsabilidade | Depende de |
|---|---|---|
| `config/settings.py` | Caminhos, modelos e chaves (lidas do `.env` com python-dotenv). Fonte única de configuração. | — |
| `radar/provedores/` | Uma classe por coleta, todas com `perguntar(texto, tipo, cliente) -> Resposta`. `provedores_reais(filtro)` devolve só as que têm credencial. | APIs externas |
| `radar/executor.py` | Monta perguntas × provedores × rodadas, roda em `ThreadPoolExecutor`, para na primeira recusa de conta (401/403/sem saldo) para não repetir o erro. | provedores, extrator, analise |
| `radar/extrator.py` | Para cada resposta: a marca aparece? Quem foi recomendado? Usa IA (nível "extracao") com saída estruturada; filtra listas e diretórios que não são concorrentes. | `ia.py` |
| `radar/analise.py` | Métricas por IA e por pergunta, ranking de concorrentes, tipo de cada fonte (concorrente, terceiro, plataforma, marca). Sem IA. | — |
| `radar/auditoria.py` | Robôs de IA conseguem acessar o site? robots.txt (leitor próprio pelo RFC 9309: a regra mais longa vence, curingas `*` e `$`; igual em qualquer versão do Python), sitemap, dados estruturados, sinais de identidade (CNPJ, endereço, perfis, página Sobre). Só a página inicial. | `rede.py` |
| `radar/pagina.py` | O que um robô encontra numa página HTML sem executar JavaScript: título, descrição, diretivas, canonical, H1, texto visível, links, fichas JSON-LD. Usa o parser da biblioteca padrão. Também usado pela checagem do site gerado. | — |
| `radar/rastreador.py` | Percorre o site do cliente (página inicial + sitemap + links, até `RASTREIO_LIMITE` páginas), respeitando o robots.txt e com pausa entre pedidos. Grava só os sinais de cada página. `problemas()` lista os defeitos (calculados na leitura, para regras novas valerem em rastreios antigos); `comparar()` diz o que foi resolvido entre dois rastreios; `ler_externas()` lê uma vez as páginas de concorrentes citadas. | `rede.py`, `pagina.py`, `auditoria.py` |
| `radar/cruzamento.py` | Junta radar e rastreamento, sem rede e sem IA: estado das páginas do cliente que as IAs citaram, a página mais próxima de cada pergunta (por palavras em comum; título, H1 e endereço pesam mais) e as ações do site no plano, com títulos fixos. | `rastreador.py` |
| `ia.py` | Chamada única de IA com saída validada por Pydantic. Tenta os provedores na ordem de `GERACAO_PROVEDORES`; pula o que falhar por conta. | anthropic, openai |
| `conteudo/` | Pauta, redação, marcadores de pendência, renderização (HTML + JSON-LD), publicação como rascunho. | `ia.py` |
| `custos.py` | Tabela de preços, `Contador` (thread-safe) que barra chamada paga sem autorização ou acima do teto, livro de gastos. | — |
| `orcamento.py` | Estimativas exibidas antes de cada execução paga. | `custos.py` |
| `site_cliente/` | Sites dos clientes: catálogo de blocos com campos declarados e validação (`blocos.py`), geração estática por blocos com fichas JSON-LD derivadas (`gerador.py`), checagens antes de publicar (`checagem.py`) e rascunho a partir do cadastro (`inicial.py`). O editor do Portal (`app/static/site-editor.js`) monta os formulários a partir do catálogo. | Jinja2, Pillow |
| `app/telas.py` | Transforma resultados salvos no que cada tela mostra (inclui intervalos de confiança de Wilson). | — |
| `app/seguranca.py` | Proteções do app web: ids e caminhos de arquivo validados, lista de Hosts (DNS rebinding), bloqueio de pedidos de outra origem (CSRF), JSON só com Content-Type, CSP e cabeçalhos. Ver [SECURITY.md](../SECURITY.md). | Flask |
| `rede.py` | Downloads feitos pelo servidor (cadastro, auditoria, rastreamento): só http(s), só IP público, cada redirecionamento conferido (SSRF); opcionalmente registra a cadeia de redirecionamentos e corta respostas grandes. | requests |
| `privacidade.py` | Lista, exporta e apaga tudo de um cliente (LGPD, Art. 18). Fonte de verdade de onde o sistema grava dados por cliente. Ver [LGPD.md](LGPD.md). | — |
| `guias/` | Guias do plano por cliente: modelos em `guias/modelos/` (Jinja) preenchidos com o último radar real, o cadastro e o rastreamento, gravados em `entregas/<id>/` depois de cada radar real. Texto vindo das IAs é escapado (sem HTML nem link). Guia sem `gerado: portal` no cabeçalho é escrito à mão e não é sobrescrito. | Jinja2 |
| `plano_correcao.py` | Monta o plano de correção em HTML a partir dos guias em `entregas/<id>/*.md`. | Markdown |

## Dados em disco

Dado real de cliente nunca vai para o Git (ver [LGPD.md](LGPD.md)). O repositório só traz o cliente
fictício `exemplo`, para testes e demonstração.

| Caminho | Conteúdo | No Git? |
|---|---|---|
| `config/clientes/<id>.json` | Perfil do cliente (fatos que o redator pode usar), perguntas, configuração de publicação | Só `exemplo.json` |
| `config/sites/<id>/` | Textos, marca e imagens do site do cliente (`site.json` + `assets/`) | Só `exemplo/` |
| `data/runs/<id>/*.json` | Resultado completo de cada radar: respostas, fontes, métricas, auditoria, nome do rastreamento feito junto e sinais das páginas de concorrentes citadas | Não |
| `data/rastreios/<id>/*.json` | Cada rastreamento do site: os sinais de cada página (sem o HTML) | Não |
| `data/conteudo/<id>/<data>/` | Pauta, artigos (JSON + prévia HTML) e central de conteúdo | Não |
| `data/plano/<id>.json` | Andamento das ações do plano | Não |
| `data/medicao/<id>/` | Coletas de GA4 e Search Console | Não |
| `data/midia/<id>.json` | Termos importados do Google Ads | Não |
| `data/sites_historico/<id>/` | Últimas 50 versões salvas do site | Não |
| `data/cache_sites/<id>/` | Fotos reduzidas e cópia usada pela checagem | Não |
| `data/gastos.jsonl` | Custo real de cada execução paga (uso interno) | Não |
| `entregas/<id>/` | Guias do plano de correção, sites gerados (`site-novo/`, `site-publicar/`) | Não |
| `relatorios/` | Relatórios HTML e exportações de dados | Não |

## Integrações externas

| Serviço | Uso | Autenticação | Custo |
|---|---|---|---|
| DataForSEO | Coleta: ChatGPT e Gemini como no app, Google com resumo de IA e modo IA | Basic (login + senha da API) | ~US$ 0,004 a 0,006 por consulta; o custo real volta na resposta |
| OpenAI / Anthropic | Extração, pauta, redação, leitura do site no cadastro | Chave de API | Por token; tabela em `custos.py` |
| Google Gemini | Coleta via API (alternativa) | Chave de API | Por token |
| GA4 Data API, Search Console API | Medição (só leitura) | Conta de serviço (`GOOGLE_CREDENCIAIS`) | Grátis |
| WordPress REST, Webflow CMS v2, Shopify Admin, Wix Blog | Envio de artigos como rascunho | Senha de aplicativo / tokens por cliente no `.env` | Grátis |
| IndexNow | Aviso de URL nova ao Bing | Chave por cliente | Grátis |

## Decisões de projeto

- **Arquivos JSON em vez de banco:** volume pequeno (um operador, poucos clientes) e fácil de auditar
  e versionar. Migrar para banco é pré-requisito do modo multiusuário.
- **Coleta "como o usuário vê":** as respostas pela API das IAs diferem do que aparece no app.
  Por isso a coleta principal usa a DataForSEO, que lê o app.
- **Várias rodadas e margem de erro:** a mesma pergunta devolve empresas diferentes a cada vez
  (22% de sobreposição medida). Todo número de visibilidade mostra intervalo de confiança.
- **O redator não inventa fatos:** só usa o perfil do cliente; o resto vira marcador
  `[[CONFIRMAR: …]]` ou `[[DADO DO ESPECIALISTA: …]]`, e o artigo não pode ser aprovado nem
  publicado com marcador.
- **Nada pago sem confirmação:** dupla trava (estimativa na entrada + `Contador.checar()` antes de
  cada chamada).

## Limitações conhecidas

- Sem login, sem multiusuário e sem HTTPS: não deve ser exposto na internet como está.
- Tarefas em segundo plano vivem na memória do processo; reiniciar o servidor perde o progresso
  de uma execução em andamento.
- Gravação de JSON sem trava entre processos: rodar a linha de comando e o app ao mesmo tempo no
  mesmo cliente pode sobrescrever dados.
- Testes cobrem análise, pendências, geração e checagem do site, LGPD (exportar/esquecer) e as
  proteções de segurança; coletas e publicação nas plataformas não têm teste automatizado (dependem
  de APIs pagas ou de contas de clientes).
- A leitura de site no cadastro (`cadastro.py`) não executa JavaScript: sites montados só no
  navegador devolvem pouco texto.
- O rastreador também não executa JavaScript, de propósito: é assim que os robôs de IA leem. Página
  quase vazia com raiz de app (React, Next, Vue…) vira o problema "texto só com JavaScript"; se o
  GPTBot recebe mais texto que o navegador (pré-renderização), vale a versão do GPTBot.
- Rastreamento em JSON: até alguns milhares de páginas vai bem; acima disso, precisa de banco
  (SQLite) e de poder retomar do meio. Endereços com `?` ficam de fora (filtros e buscas geram
  páginas sem fim).
- A ligação pergunta → página é por palavras em comum: aproximação, mostrada como "página mais
  próxima". A comparação com concorrentes mostra o que as páginas citadas têm em comum, não a causa
  da citação.
- `rede.py` confere o IP antes de baixar, mas o `requests` resolve o nome de novo: um domínio
  preparado para trocar de IP entre as duas consultas passaria (DNS rebinding). Risco baixo aqui,
  porque quem digita a URL é o próprio operador; num serviço aberto, fixar o IP na conexão.
- Algumas funções concentram lógica demais (complexidade ciclomática medida com radon):
  `radar/analise.calcular` (64), `app/telas.radar` (57), `app/telas.conteudo` (30). Funcionam e têm
  teste, mas são as primeiras candidatas a quebrar em partes. Detalhes em [AUDITORIA.md](AUDITORIA.md).
  Do rastreamento, a maior é `radar/rastreador.problemas` (23 pela contagem do ruff, que conta menos
  que o radon): uma sequência de checagens independentes, cada uma coberta pelo teste do site falso.

## Próximos passos técnicos sugeridos

1. Banco de dados (SQLite → Postgres) e login, para o modo agência com vários usuários.
2. Fila de tarefas persistente (ex.: RQ ou Celery) no lugar das threads.
3. Testes de integração com respostas gravadas das APIs.
4. Deploy em servidor com HTTPS e segredos fora do disco.
