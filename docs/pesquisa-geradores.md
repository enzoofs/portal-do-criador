# Pesquisa: geradores e construtores de sites

15/10/2026. Base para decidir como o gerador de sites do Portal vira produto. Três fontes:
medição do que grandes construtores entregam (com o REA e o protocolo do Chrome), leitura de
projetos abertos no GitHub e o nosso próprio gerador como referência.

## Como foi feito, e o limite

- **REA (`rea-agents` 6.5.0, MIT, github.com/morluto/rea)**, só a parte de observação passiva de páginas:
  `inspect-web-page` (árvore da página, acessibilidade, recursos) e `analyze-web-bundle`, sem baixar
  source maps. Rodou numa instância local do Chrome, sobre páginas públicas.
- **HTML cru buscado como GPTBot**, para medir o que um robô de IA lê sem executar JavaScript.
- **Limite respeitado:** nada de descompilar ou desofuscar os editores fechados (Webflow, Framer, Wix,
  Squarespace). Os termos deles proíbem, e o aviso do próprio REA exclui "reproduzir código protegido".
  Medimos apenas o que qualquer visitante recebe.
- Amostra pequena: a página inicial de cada plataforma (feita nela mesma), uma carga cada. Serve para
  ordem de grandeza, não para ranking.

## O que os construtores entregam

| Página | Plataforma | HTML | Total baixado | Requisições | JavaScript | Nós no DOM (REA) | Texto no HTML sem JS | Fichas JSON-LD |
|---|---|---|---|---|---|---|---|---|
| webflow.com | Webflow | 514 KB | 1.181 KB | 190 | 1.069 KB | 4.644 | sim | Organization, WebSite, SoftwareApplication |
| framer.com | Framer | 1.858 KB | 2.633 KB | 172 | 1.114 KB | 4.830 | sim | Organization |
| pt.wix.com | Wix | 1.419 KB | 2.353 KB | 174 | 711 KB | 9.655 | sim | Organization, FAQPage, HowTo |
| pt.squarespace.com | Squarespace | 609 KB | 1.861 KB | 60 | 1.742 KB | 4.736 | sim | WebSite, Organization, FAQPage, HowTo |
| Site de cliente A | Next.js na Vercel | 59 KB | 475 KB | 18 | 272 KB | 666 | sim, mas contadores saem "R$ 0" | nenhuma |
| Site de cliente B | WordPress + Elementor | — | 1.346 KB | 77 | 458 KB | 1.468 | **403 para o GPTBot** | Organization (sem endereço) |
| Prévia do Portal | gerador próprio | 18 KB | 610 KB (quase tudo imagem) | 13 | 0 KB | 666 | sim | ProfessionalService, WebSite, FAQPage |

**Leitura:**
1. **Os grandes entregam o texto inteiro no HTML.** A ideia de que "site de construtor é invisível para
   IA" está errada para Webflow, Framer, Wix e Squarespace. Nosso diferencial não pode ser esse.
2. **O peso é a diferença real:** 60 a 190 requisições e 0,7 a 1,7 MB de JavaScript contra zero no nosso.
   Ajuda em velocidade e em celular fraco, mas sozinho não vende.
3. **Onde clientes pequenos realmente perdem:** bloqueio de robôs (o WordPress do cliente B responde 403
   ao GPTBot), fichas incompletas, números que só aparecem depois do JavaScript, falta de página Sobre e
   de dados oficiais. É isso que a checagem do Portal ataca.

## Projetos abertos analisados

Dados do GitHub em 15/10/2026.

| Projeto | Estrelas | Licença | O que é | O que levamos |
|---|---|---|---|---|
| Shopify/dawn | 3,1 mil | própria | Tema de referência do Shopify | **O modelo:** cada seção declara seus campos ("schema") e a página é uma lista ordenada de seções |
| puckeditor/puck | 13,5 mil | MIT | Editor visual para React | Componente = campos + desenho; página = JSON. Candidato se o editor virar React |
| GrapesJS/grapesjs | 26,3 mil | BSD | Construtor visual de HTML/CSS | Edição livre demais para o nosso caso (quebra a estrutura que o Google lê) |
| webstudio-is/webstudio | 9,1 mil | **AGPL-3.0** | Alternativa aberta ao Webflow | Referência de produto; AGPL obrigaria a abrir o nosso código se embutido |
| silexlabs/Silex | 3,0 mil | **AGPL-3.0** | Editor visual de sites estáticos | Mesmo problema de licença |
| plasmicapp/plasmic, BuilderIO/builder | 7,1 mil / 8,9 mil | MIT | Construtores visuais ligados a código | Padrão "conteúdo como dado, desenho em componentes" |
| prevwong/craft.js | 8,8 mil | MIT | Base para editores de arrastar | Último commit em 2025: risco de abandono |
| onlook-dev/onlook | 26,9 mil | Apache-2.0 | Editor visual com IA sobre código React | Direção futura: IA editando o site com prévia |
| firecrawl/open-lovable | 28,7 mil | MIT | Recria um site a partir da URL, com IA | **Importar site existente:** raspar, extrair e reconstruir. Nós faremos para blocos, não para código livre |
| abi/screenshot-to-code | 80,4 mil | MIT | Imagem de tela vira código | Idem, a partir de captura |
| stackblitz-labs/bolt.diy, dyad-sh/dyad | 19,9 mil / 21,9 mil | MIT / própria | Construtores de app por prompt | Mostram o custo de gerar código livre: difícil de manter e de medir |
| payloadcms/payload, strapi/strapi, directus/directus | 45 mil / 73 mil / 38 mil | MIT / própria / própria | CMS headless | Banco e API prontos, para quando o produto tiver vários usuários |
| tinacms/tinacms, decaporg/decap-cms, Thinkmill/keystatic | 13,8 mil / 19,4 mil / 2,5 mil | Apache / MIT / MIT | CMS sobre arquivos no Git | Conteúdo versionado com formulários gerados por schema, como o nosso `site.json` |
| GetPublii/Publii | 7,3 mil | GPL-3.0 | CMS de site estático para desktop | Mais parecido com o nosso: temas, SEO e publicação em vários destinos |
| withastro/astro, gohugoio/hugo, 11ty | 63 mil / 90 mil / 20 mil | variadas | Geradores de site estático | Saída estática é o caminho; não precisamos trocar o Jinja |
| vercel/platforms | 6,7 mil | — | Vários clientes com subdomínio próprio | Padrão de multi-cliente para quando houver hospedagem nossa |
| morluto/rea | 268 mil | MIT | Engenharia reversa com agentes | Usado só para observação passiva de páginas públicas |

## Padrões que se repetem

1. **Página = dados; desenho = componentes.** Todos guardam a página como uma árvore ou lista de blocos
   com propriedades, e o editor só altera esses dados.
2. **Formulário gerado a partir do schema do bloco** (Shopify, Puck, Keystatic, Tina, Decap, WordPress).
3. **Dois tipos de editor:** tela livre (Webflow, Framer, GrapesJS, Webstudio) ou seções com regras
   (Shopify, Squarespace). A tela livre dá mais poder e quebra a estrutura com facilidade.
4. **Publicação estática ou na borda**, com domínio do cliente apontado por DNS.
5. **Importação a partir do site existente** já é commodity com IA (open-lovable).

## Decisões

| Decisão | Por quê |
|---|---|
| Seções com regras, não tela livre | Agência e dono de negócio precisam de guarda-corpo; a estrutura é o que o Google e as IAs leem |
| Catálogo de blocos com campos declarados (`site_cliente/blocos.py`) | Um só lugar define formulário, validação e desenho |
| `site.json` como fonte única, em arquivo | Simples de versionar e auditar agora; migra para banco sem mudar o formato |
| Fichas JSON-LD derivadas dos blocos | Garante que a ficha bate com o que está visível, como o Google exige |
| Nenhum campo aceita HTML | Evita injeção e mantém o visual consistente |
| Checagem antes de publicar com "como resolver" | É o que nenhum construtor faz pelo cliente pequeno: identidade, robôs, fichas, tamanhos |
| Sem arrastar e soltar e sem edição na própria prévia, por ora | Custo alto, pouco valor para o primeiro cliente; reavaliar com uso real |
| Evitar dependências AGPL | Webstudio e Silex obrigariam a abrir o código do produto |

## Avaliação crítica

- **O HTML não é o fosso.** Os grandes já entregam texto completo. O que defendemos é o método inteiro:
  radar → plano → conteúdo com dados reais → site com identidade completa → medição. O editor é meio.
- **Editor de site é um poço sem fundo.** Webflow e Framer têm centenas de engenheiros. Crescemos em
  blocos novos e checagens, não em liberdade de desenho.
- **Saída estática tem limites:** formulários e conteúdo dinâmico dependem de serviço externo
  (hoje: WhatsApp e link de formulário).
- **Ainda é ferramenta de um operador:** sem login, sem multiusuário, arquivos em disco, histórico por cópia.
  Para virar produto: contas, banco, hospedagem multi-cliente, cobrança.
- **Riscos jurídicos a acompanhar:** licenças de terceiros, direito de uso das imagens do cliente e
  consentimento para usar depoimentos.
- **Dívidas técnicas conhecidas:** editor sem testes automatizados de interface, sem salvamento automático,
  sem desfazer além das cópias em `data/sites_historico/`.

## Caminho até produto

1. **Feito em 15/10/2026:** editor por blocos com prévia ao vivo, configurações da marca, checagens antes de
   publicar, criação do primeiro rascunho a partir do cadastro e .zip para subir.
2. **Próximo:** publicar direto no Cloudflare Pages pela API, domínio próprio, voltar para uma versão
   anterior, importar o site existente para blocos, mais blocos (galeria, mapa, contato, preços),
   variações de layout e checagem de acessibilidade.
3. **Produto:** login e equipes, banco de dados, hospedagem multi-cliente com domínios próprios
   (um Worker servindo todos os sites a partir do R2, com Cloudflare for SaaS), marca da agência
   (white-label), cobrança e IA preenchendo blocos com as afirmações conferidas.
