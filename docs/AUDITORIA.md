# Auditoria antes da publicação (15/10/2026)

Revisão completa do Portal do Criador antes de abrir o repositório para a equipe de TI: segurança,
LGPD, qualidade de código, UX/acessibilidade e organização do repositório. Este documento registra o
método, o que foi achado, o que foi corrigido (com o teste que prova) e o que continua em aberto.

## 1. Escopo

O pedido, reescrito como critério verificável:

1. **Segurança:** nenhuma entrada externa (URL, formulário, JSON, upload, resposta de IA, site de
   terceiro) consegue ler arquivo fora do lugar, executar script, disparar ação de outro site ou
   fazer o servidor acessar a rede interna. Nenhum segredo no histórico do Git.
2. **LGPD:** saber que dado pessoal existe, onde fica, para onde vai; conseguir exportar e apagar;
   nada de dado real no repositório público; minimização no que vai para fornecedores.
3. **Qualidade:** lint e análise estática limpos com configuração versionada; testes que rodam sem
   custo e pegam regressões; dependências fixadas e auditadas; CI.
4. **UX e acessibilidade:** telas sem violação automática de acessibilidade (axe) e textos claros.
5. **Organização:** nada desnecessário no repositório, documentação que bate com o código, licença,
   política de segurança e guia de contribuição.

Fora do escopo: teste de invasão com o app exposto na internet (ele só escuta em `127.0.0.1`),
revisão jurídica (ver [LGPD.md](LGPD.md)) e chamadas pagas às APIs.

## 2. Método e ferramentas

| Etapa | Ferramenta | Versão |
|---|---|---|
| Mapa de entradas e modelo de ameaça | leitura de todas as rotas, guiada pelas skills `entry-point-analyzer`, `insecure-defaults`, `supply-chain-risk-auditor` e `open-sourcing` (trailofbits/skills) | — |
| Lint e regras de segurança | ruff (E, W, F, I, B, S, C4, PIE, RUF, UP) | 0.17.1 |
| Análise estática de segurança | bandit | 1.9.4 |
| Vulnerabilidades conhecidas nas dependências | pip-audit sobre `requirements-lock.txt` | 2.10.1 |
| Segredos no histórico e na árvore | gitleaks; detect-secrets | 8.30.1; 1.5.0 |
| Código morto | vulture | 2.16 |
| Complexidade | radon | 6.0.1 |
| Acessibilidade | axe-core no Chrome headless, 13 telas | 4.10.2 |
| Testes dinâmicos | cliente de teste do Flask com os ataques; teste de mutação (devolver cada falha antiga e ver o teste acusar) | — |

## 3. Resultado em números

| Medida | Antes | Depois |
|---|---|---|
| Falhas críticas/altas abertas | 5 | 0 |
| ruff (conjunto acima) | dezenas de achados | 0 |
| bandit | 5 médios (Markup) | 0 (5 supressões justificadas na linha) |
| CVEs nas dependências (43 pacotes) | 0 | 0 |
| Segredos no histórico (gitleaks) | 0 | 0 |
| Violações de acessibilidade (axe, 13 telas) | várias (contraste, botões em `<summary>`) | 0 |
| Testes | 11 (análise, pendências e site) | 19 (+ LGPD e segurança) |
| Teste de mutação nas proteções | — | 4 de 4 regressões acusadas |
| Complexidade ciclomática média | — | B (5,2) |

## 4. Achados e correções

Gravidade: impacto × facilidade, considerando que o app roda na máquina do operador e que uma página
qualquer aberta no mesmo navegador é o atacante mais provável.

### Crítico

| # | Achado | Evidência | Correção | Prova |
|---|---|---|---|---|
| C1 | Leitura de qualquer arquivo com `..\` (barra invertida, no Windows) | `GET /c/<id>/anexo/..%5C..%5C.env` devolvia o `.env` com as chaves (200, 746 bytes). `/fontes/` e a prévia do site tinham o mesmo problema | `seguranca.exigir_id` e `seguranca.arquivo_dentro`: lista de caracteres permitidos, recusa `\` e `..`, confere o caminho depois de resolvido | `teste_seguranca_recusa_ataques` |

### Alto

| # | Achado | Evidência | Correção | Prova |
|---|---|---|---|---|
| A1 | CSRF: qualquer site aberto no navegador disparava execuções pagas e mudava configurações | `get_json(force=True)` aceitava `text/plain`, que o navegador manda de outro site sem pré-checagem | `json_do_pedido()` exige `application/json`; métodos que mudam estado exigem mesma origem (`Sec-Fetch-Site`, `Origin`, `Referer`) | idem |
| A2 | DNS rebinding: um domínio do atacante apontando para 127.0.0.1 lia o Portal inteiro (incluindo o C1) | nenhum controle de `Host` | lista de Hosts permitidos; outro Host recebe 421 | idem |
| A3 | SSRF: o cadastro e a auditoria baixavam qualquer URL, inclusive `127.0.0.1`, rede interna e metadados de nuvem | `requests.get(url)` direto | `rede.py`: só http(s), todos os IPs públicos, cada redirecionamento conferido | `teste_rede_bloqueia_enderecos_internos` |
| A4 | Dados pessoais de cliente e de terceiros no repositório público | cadastro, fotos do fundador, análises de concorrentes e entregas versionados | `.gitignore`, cliente fictício `exemplo`, histórico reescrito num commit novo | `gitleaks`; revisão da árvore publicada |
| A5 | XSS: Markdown de resposta de IA virava HTML sem escape | `Markup(markdown(texto))` | `render.markdown_seguro` escapa HTML cru | `teste_markdown_nao_vira_script` |

### Médio

| # | Achado | Correção | Prova |
|---|---|---|---|
| M1 | O filtro de links do Markdown (lista de proibidos) deixava passar `java\nscript:` e `\x01javascript:`, que o navegador executa. Nos sites dos clientes não há CSP | lista de esquemas **permitidos** (http, https, mailto, tel), com a URL normalizada como o navegador faz | `teste_markdown_nao_vira_script` |
| M2 | Perfis oficiais e link do formulário aceitavam `javascript:` e viravam `href` no site publicado | campo do tipo `link`: só `http(s)://` | `teste_link_do_site_so_aceita_http` |
| M3 | Upload confiava na extensão (GIF ou TIFF renomeado entrava) e não limitava pixels: um PNG de 12 KB com 100 megapixels estourava a memória ao redimensionar | formato lido do conteúdo; limite de 40 MP; extensão gravada pelo formato real | `teste_upload_confere_o_formato_real` |
| M4 | Sites gerados carregavam fontes do Google Fonts: o IP de cada visitante ia para o Google sem aviso (LGPD; caso LG München, 2022) | fontes dentro do site (Fontsource, OFL, versão e sha256 em `fontes.json`) | `teste_site_nao_carrega_nada_de_terceiros` |
| M5 | Chamadas à OpenAI sem `store=False`: a API guarda a resposta por padrão | `store=False` nas duas chamadas | não testado ao vivo (chamada paga) |
| M6 | O perfil inteiro do cliente, com o WhatsApp, ia para a IA ao escrever pauta e artigos | `ia.perfil_para_prompt` tira contato e notas internas | revisão |
| M7 | Sem como exportar ou apagar os dados de um cliente (LGPD, Art. 18) | `privacidade.py`; `main.py exportar` e `esquecer` | `teste_esquecer_apaga_tudo_do_cliente` |
| M8 | Sem cabeçalhos de segurança; script inline no modo apresentação | CSP sem script inline, `nosniff`, `X-Frame-Options`, `Referrer-Policy`, COOP/CORP; script movido para `static/apresentar.js` | `teste_seguranca_uso_normal_e_cabecalhos` |
| M9 | Histórico de versões do site sem limite (retenção) | guarda as últimas 50 | revisão |

### Baixo, bugs e qualidade

| # | Achado | Correção |
|---|---|---|
| B1 | Plano de correção saía com o nome de um cliente fixo no texto, para qualquer cliente | usa o nome do cliente |
| B2 | Formulário de pendências com listas de tamanhos diferentes gravava a resposta no artigo errado | recusa (400) e `zip(strict=True)` |
| B3 | Gerar a prévia com ela aberta dava erro 500 no Windows (arquivo em uso) | sobrescreve no lugar e apaga as sobras |
| B4 | O executor de testes só capturava `AssertionError`: um erro de outro tipo interrompia a rodada e escondia os testes seguintes | captura qualquer exceção e continua |
| B5 | Fontes Geist redistribuídas sem o texto da licença OFL (exigência da licença) | `assets/fonts/OFL.txt`; licença junto de cada fonte dos sites |
| B6 | `innerHTML` com texto do servidor em `app.js` (a CSP já barrava) | `esc()` |
| B7 | Contraste insuficiente e botões dentro de `<summary>` em 13 telas | cores e estrutura corrigidas; axe sem violações |
| B8 | Testes usavam domínios que podem existir | domínios reservados `.example` (RFC 2606) |
| B9 | `.env.example` sem 10 das variáveis que o código lê | completo, com os padrões |
| B10 | Documentação desatualizada (dizia que dados de cliente iam para o Git) | ARQUITETURA, README e SITES revistos |
| Q1 | Variáveis `l`, lambdas atribuídas, imports e variáveis sem uso, imagem do Pillow sem fechar, `None` implícito em `ia.gerar`, funções privadas usadas por outros módulos | corrigido; ruff limpo |
| Q2 | Duas funções de slug iguais | uma só (`conteudo.pauta.slugify`) |
| Q3 | Módulo `entregas.py` com o mesmo nome da pasta `entregas/` | renomeado para `plano_correcao.py` |
| Q4 | Sem CI, configuração de lint, versões fixadas, licença, política de segurança e guia de contribuição | `.github/workflows/ci.yml` (actions fixadas por SHA, permissão só de leitura), `dependabot.yml`, `pyproject.toml`, `requirements-lock.txt`, `.editorconfig`, `LICENSE`, `SECURITY.md`, `CONTRIBUTING.md` |

Os 5 `Markup(...)` que sobraram foram revistos um a um: CSS fixo do código, Markdown já passado por
`markdown_seguro` e guias escritos pela equipe. Cada um tem o motivo comentado na linha.

## 5. Em aberto

| # | Item | Por que ficou | Próximo passo |
|---|---|---|---|
| R1 | Commits antigos continuam acessíveis por SHA no GitHub até a limpeza deles | o force push tira do histórico, não do cache | pedir ao suporte do GitHub a remoção das visualizações em cache, se necessário |
| R2 | Chaves de API usadas antes da correção do C1 | o `.env` nunca foi para o Git, mas era legível por C1 + A2 enquanto o Portal rodava | trocar as chaves por precaução |
| R3 | Sem login, multiusuário nem HTTPS | o app é local por desenho | pré-requisito antes de virar serviço na internet ([ARQUITETURA.md](ARQUITETURA.md)) |
| R4 | `rede.py` resolve o nome duas vezes (conferência e download) | risco baixo: quem digita a URL é o operador | fixar o IP na conexão se virar serviço aberto |
| R5 | Gravação de JSON sem trava entre processos | um operador, uso local | banco de dados no modo multiusuário |
| R6 | Funções complexas: `radar/analise.calcular` (64), `app/telas.radar` (57), `radar/auditoria.auditar` (30), `app/telas.conteudo` (30) | funcionam e têm teste; refatorar sem cobertura mais fina é risco maior | quebrar em partes junto com testes por parte |
| R7 | `store=False` não validado contra a API real | exige chamada paga | uma chamada de ~US$ 0,01, com aprovação |
| R8 | Acessibilidade só automática | o axe não pega tudo | teste manual de teclado e leitor de tela |
| R9 | Pendências jurídicas da LGPD (contratos com fornecedores, cláusulas-padrão da ANPD, canal do titular, RIPD para clientes de saúde) | não é código | [LGPD.md](LGPD.md), seções 4, 8 e 9 |
| R10 | Página de política de privacidade nos sites gerados | hoje o site não coleta nada; passa a ser necessária se o cliente puser GA4, pixel ou chat | bloco "Privacidade" no catálogo |

## 6. Como repetir esta auditoria

```bash
ruff check .
bandit -c pyproject.toml -r .
pip-audit -r requirements-lock.txt --no-deps --disable-pip
gitleaks git . --redact
python testes.py
```

O CI ([.github/workflows/ci.yml](../.github/workflows/ci.yml)) roda as mesmas etapas a cada push.
