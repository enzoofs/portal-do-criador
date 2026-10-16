# Pesquisa: ferramentas de SEO (Screaming Frog e Yoast)

16/10/2026. Base para decidir o que trazer de ferramentas de SEO estabelecidas para o Portal.
Fontes: as análises do canivibecodeit.com sobre o
[Screaming Frog SEO Spider](https://canivibecodeit.com/screaming-frog-seo-spider) e o
[Yoast SEO Premium](https://canivibecodeit.com/yoast-seo-premium), comparadas com o código atual.

## O que cada ferramenta é

| | Screaming Frog SEO Spider | Yoast SEO Premium |
|---|---|---|
| O que faz | Rastreia o site inteiro e lista problemas técnicos por página | Plugin de WordPress: analisa o texto enquanto se escreve, sugere links internos, gerencia redirecionamentos, gera fichas (schema) |
| Preço | US$ 23,55 por usuário/mês (anual); grátis até 500 URLs | US$ 118,80/ano por site; grátis com 1 frase-chave por post |
| Veredito do site | "Sim", em alguns dias | "Sim", numa sessão |
| Onde está o valor que não se copia | Anos de casos raros de rastreamento, desempenho, integrações | Dados próprios de palavras-chave e ranking (via Semrush e Wincher) e acabamento |
| Dados por página | Status, título, descrição, títulos, canonical, diretivas de robôs, links, imagens, fichas, texto | Frase-chave, legibilidade, links internos, prévia no Google e nas redes |
| Problemas que aponta | Conteúdo duplicado, páginas órfãs, links quebrados, cadeias de redirecionamento, metadados faltando, conflitos de indexação | Frase-chave ausente do título, da introdução ou do endereço; texto difícil; post sem links internos |

## O que o Portal já cobre

| Módulo | O que confere | Limite |
|---|---|---|
| `radar/auditoria.py` | Robôs de IA bloqueados, robots.txt, sitemap, JSON-LD, sinais de identidade, blog | Só a **página inicial** do site atual do cliente |
| `site_cliente/checagem.py` | Título, descrição, H1, canonical no sitemap, JSON-LD válido, palavras por página, links internos quebrados, imagens pesadas | Todas as páginas, mas só do site **gerado por nós** |
| `conteudo/redator.py` | Meta título com a palavra-chave (pedido à IA) | Nada confere depois se a IA cumpriu |

O site que o cliente tem no ar hoje, que é o que as IAs leem, só é examinado pela página inicial.

## Problema encontrado no código atual

A regra que lê o robots.txt em `radar/auditoria.py` (`bloqueio_robots`) é frágil:

- `(?:.*\n)*?` atravessa para o bloco de outro robô: se algum robô listado depois do GPTBot tiver
  `Disallow: /`, o relatório diz que o GPTBot está bloqueado.
- Não detecta `User-agent: *` com `Disallow: /`, que bloqueia todos.

Correção: `urllib.robotparser` (biblioteca padrão) e `can_fetch(robo, url)`. Ele não entende os
curingas `*` e `$` do padrão do Google; tratar à parte se aparecerem.

## Propostas

### 1. Rastreador do site do cliente (do Screaming Frog)

Partir do sitemap e dos links internos, baixar cada página pelo `rede.baixar` (proteção contra
SSRF já pronta), respeitar o robots.txt e esperar entre pedidos. Por página, rodar as mesmas
checagens do `checagem.py`, separadas num módulo que os dois usam. Acrescentar o que só aparece
olhando o site inteiro:

- títulos e descrições repetidos (o `checagem.py` também não confere isso hoje);
- páginas do sitemap sem nenhum link apontando (órfãs) e páginas linkadas fora do sitemap;
- URLs do sitemap que não respondem 200, cadeias de redirecionamento;
- `noindex` na página ou no cabeçalho `X-Robots-Tag`, canonical apontando para outra página;
- **texto que só existe depois do JavaScript:** contar as palavras no HTML como chega ao robô.
  GPTBot, ClaudeBot e PerplexityBot não executam JavaScript. Não precisa de Playwright; o HTML
  cru é justamente o que importa.

Cada problema entra no plano de correção com as páginas afetadas, a evidência e como resolver.

### 2. Rastreamento sem limite

O código do rastreador é o mesmo; o que muda é onde os dados ficam. Hoje tudo é JSON carregado
inteiro na memória, o que não aguenta dezenas de milhares de páginas. Caminho:

- guardar o rastreamento em SQLite (já é o primeiro passo previsto em `ARQUITETURA.md`), página
  por página, para poder retomar se parar no meio;
- limite configurável por cliente em vez de "sem limite" literal. O próprio Screaming Frog
  esbarra na memória da máquina; para os clientes atuais, sites pequenos, um teto de 10 mil URLs
  já funciona como ilimitado;
- velocidade controlada por domínio, para não derrubar o site do cliente.

### 3. Backlinks e palavras-chave

Índice próprio de backlinks e de palavras-chave não é viável: é exatamente o que essas empresas
cobram (o próprio site aponta isso como o valor que não se copia). Mas já temos três fontes:

- **Search Console** (já integrado em `medicao.py`, grátis): as buscas reais que trazem o
  cliente, com cliques e posição. É a melhor fonte de palavra-chave para o site do próprio cliente.
- **Google Ads** (já importado em `midia/termos.py`): termos que o cliente paga para aparecer.
- **DataForSEO** (já temos conta): vende backlinks, volume de busca e palavras de concorrentes,
  cobrados por chamada, o que encaixa na trava do `custos.py`. Confirmar preço e se a API de
  backlinks exige assinatura mínima mensal antes de prometer ao cliente.

Encaixe no produto: backlinks de sites que as IAs citam como fonte (o radar já sabe quais são)
valem mais do que backlinks em geral. Dá para cruzar e priorizar.

### 4. Nota própria

Encaixa, desde que siga a regra do projeto de não esconder incerteza:

- **separar duas notas:** saúde técnica (do rastreador, sem IA) e visibilidade nas IAs (do radar,
  que já mostra margem de erro). Misturar as duas num número só esconde o que mexe em quê;
- a nota técnica mostra quanto cada problema tirou, para o cliente ver por que está em 72 e o que
  sobe para 85;
- pesos escritos no código e na documentação, sem fórmula escondida.

### 5. Monitoramento contínuo

- O rastreador não custa nada (não usa IA nem API paga), então pode rodar toda semana.
- O radar é pago: monitorar exige um teto mensal aprovado por cliente, uma autorização que hoje
  o `custos.py` não tem (ele pede confirmação a cada execução).
- Não precisa de servidor: um comando `python main.py monitorar <cliente>` agendado no
  Agendador de Tarefas do Windows (ou cron) resolve enquanto o Portal roda numa máquina só.
- O valor está em **comparar com a vez anterior** e avisar só o que mudou: "o robots.txt passou
  a bloquear o GPTBot", "3 páginas ganharam noindex", "a marca sumiu das respostas sobre X".

### 6. Análise dos artigos antes de aprovar (do Yoast)

O redator pede à IA que siga as regras, mas nada confere depois. Uma checagem sem IA na tela do
artigo, antes de aprovar:

- a palavra-chave está no título, no primeiro parágrafo, no endereço e na descrição?
- o primeiro parágrafo responde a pergunta-alvo de forma direta? (é o trecho que as IAs costumam
  citar; pesa mais do que a densidade de palavra-chave que o Yoast mede);
- legibilidade em português (o Yoast usa uma adaptação do índice Flesch para português);
- tamanho do título e da descrição, como já faz o `checagem.py`.

### 7. Links internos sugeridos (do Yoast)

Ao escrever um artigo, sugerir links para a página de serviço e para outros artigos do mesmo
assunto (comparando palavras-chave e perguntas da pauta, sem IA). Também evita artigo órfão no
blog do site gerado.

### 8. Redirecionamentos (do Yoast)

Quando o endereço de uma página ou artigo muda no editor do site, o endereço antigo quebra e
perde o que já tinha no Google. Guardar os endereços antigos no `site.json` e gerar o
redirecionamento na versão para publicar: página com `meta refresh` e canonical, que funciona em
qualquer hospedagem estática, ou `.htaccess` e `_redirects` quando a hospedagem aceitar.

### 9. Prévia no Google e no compartilhamento (do Yoast)

No editor do site e na tela do artigo, mostrar como o título e a descrição aparecem no Google e
num link compartilhado no WhatsApp. Barato e ajuda o cliente a entender por que o tamanho importa.

## O que não trazer

- **Renderização de JavaScript com Playwright:** dependência pesada, e os robôs de IA não renderizam.
- **Trocar a base técnica** (FastAPI, Typer, HTMX, como sugerem os prompts do site): o projeto já
  usa Flask e linha de comando com argparse; trocar não traz ganho.
- **Índice próprio de backlinks ou palavras-chave:** comprar da DataForSEO quando precisar.
- **Densidade de palavra-chave e regras antigas do Yoast:** o leitor final é uma IA que resume;
  repetir a palavra não ajuda e piora o texto.

## Ordem sugerida

| # | O quê | Esforço | Por quê primeiro |
|---|---|---|---|
| 1 | Corrigir a leitura do robots.txt | horas | Erro real no relatório entregue ao cliente |
| 2 | Rastreador com teto (proposta 1) | 1 a 2 dias | Maior lacuna: o site atual do cliente só é visto pela página inicial |
| 3 | Análise dos artigos e prévia no Google (6 e 9) | 1 dia | Usa só dados que já temos |
| 4 | Redirecionamentos e links internos (8 e 7) | 1 a 2 dias | Protege o que o site já conquistou |
| 5 | Nota técnica (4) | 1 dia | Depende do rastreador |
| 6 | Monitoramento com comparação (5) | 2 a 3 dias | Depende do rastreador e da nota; o radar precisa da autorização mensal no `custos.py` |
| 7 | SQLite e teto alto (2) | 2 a 3 dias | Só quando aparecer cliente com site grande |
| 8 | Backlinks e palavras-chave pela DataForSEO (3) | 2 dias + custo | Confirmar preço antes; Search Console já cobre o site do próprio cliente |

## Situação em 16/10/2026

Feito:

- **1. Leitura do robots.txt:** leitor próprio pelo RFC 9309 em `radar/auditoria.py`, igual na 3.11 e na
  3.14, e serve para qualquer página (não só a inicial).
- **2. Rastreador com teto** (`radar/rastreador.py`), integrado ao radar pelo `radar/cruzamento.py`:
  - roda junto com cada radar, em paralelo às consultas, e sozinho (botão "Rastrear o site" e
    `python main.py rastrear`);
  - cruza com o radar: pergunta × página mais próxima, estado das páginas que as IAs citaram, e as ações
    do site no plano;
  - compara com até 10 páginas de concorrentes citadas;
  - um novo rastreio confirma no plano o que foi corrigido.
- **Parte do 6:** a comparação entre rastreios. Falta o agendamento (o rastreio ainda é disparado à
  mão) e a autorização mensal do radar no `custos.py`.

Continua em aberto: 3, 4, 5, 7 e 8.
