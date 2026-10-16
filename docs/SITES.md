# Sites dos clientes

O Portal gera o site completo de um cliente (não só o blog) a partir de arquivos de configuração,
para publicar no domínio dele. O cliente é dono do que foi gerado: são arquivos estáticos que
funcionam em qualquer hospedagem.

## Quando usar

Oferecemos três caminhos e recomendamos um, conforme o caso:

| Opção | Quando | O que é |
|---|---|---|
| A. Ajustar o site atual | Site razoável em WordPress, Webflow, Shopify ou Wix, com acesso | Correções e blog publicando na própria plataforma (`conteudo/plataformas.py`) |
| B. Só o blog | Cliente não quer mexer no site agora | Este gerador publicando apenas `/blog` em `blog.cliente.com.br` ou em `cliente.com.br/blog` (proxy) |
| C. Site novo completo | Site fraco, sem base técnica ou sem site | Este gerador, com tudo: páginas, blog, fichas, sitemap |

Regra: uma marca, um site, um domínio, blog em `/blog`.

## Editor no Portal

Tela **Site** de cada cliente (`/c/<cliente>/site`):

- **Páginas:** cada página é uma lista de blocos. Abrir um bloco mostra o formulário dele e rola a prévia
  até ele. Blocos sobem, descem, duplicam e saem; páginas novas (serviço e cidade, simples) são criadas ali.
- **Configurações:** empresa, dados oficiais (CNPJ, endereço), perfis, fundador, marca, fontes, cores, blog
  e domínio.
- **Antes de publicar:** checagens da versão que vai ao ar, cada uma com o que fazer.
- **Prévia ao vivo** em computador e celular; **Ctrl S** salva, valida e atualiza a prévia.
- **Gerar versão para publicar** e **baixar o .zip**.
- Cliente sem site: **Criar site a partir do cadastro** monta o primeiro rascunho só com fatos do cadastro.

Cada salvamento guarda a versão anterior em `data/sites_historico/<cliente>/` (as últimas 50).

## Pela linha de comando

```bash
python main.py site exemplo              # prévia: entregas/exemplo/site-novo/
python main.py site exemplo --publicar   # para o ar: entregas/exemplo/site-publicar/
```

A prévia também abre em Plano de ações → "Prévia do site novo" (`/c/<cliente>/site-novo/`).
Ela tem faixa de aviso, `noindex` e mostra tracejado o que falta preencher. A versão para publicar
não tem nada disso: campo vazio simplesmente não aparece, nem nas fichas JSON-LD.

O blog usa os artigos da pauta real mais recente que **não têm pendências**. Com
`--com-pendencias` eles entram, com o dado a confirmar marcado (nunca escondido).

## Configuração (`config/sites/<cliente>/`)

- `site.json` (versão 2): configurações (domínio, marca, empresa, dados oficiais, fundador, blog) e
  `paginas`, cada uma com tipo (`inicio`, `sobre`, `servico`, `simples`), título e descrição para o Google,
  nome no menu e a lista de `blocos`.
- **Blocos disponíveis** (`site_cliente/blocos.py`): abertura, cabeçalho de página, números, para quem é,
  serviços, processo, depoimentos, fundador em destaque, sobre o fundador, dados da empresa, texto,
  artigos recentes, perguntas frequentes e chamada final. Cada bloco declara seus campos; o editor e a
  validação usam essa mesma declaração. Nenhum campo aceita HTML, e campos de link (perfis,
  formulário) só aceitam endereço `http(s)://`.
- `assets/`: imagens. Fotos acima de 300 KB são reduzidas na geração (com cache em `data/cache_sites/`).
- Modelos e estilo comuns em `site_cliente/modelos/` (um arquivo por bloco em `modelos/blocos/`).
- Fontes do catálogo em `site_cliente/fontes/` (woff2 do Fontsource com a licença de cada família;
  versões e sha256 em `fontes.json`).

Para acrescentar um bloco: declarar em `BLOCOS` (campos e textos de ajuda) e criar
`modelos/blocos/<tipo>.html`. O teste `teste_todo_bloco_tem_modelo` garante que os dois existem.

## Checagens antes de publicar (`site_cliente/checagem.py`)

Rodam sobre a versão para publicar: identidade (CNPJ, razão social, endereço, e-mail, perfis), páginas
Sobre e de serviço, robôs liberados, título e descrição no tamanho, um H1 por página, fichas JSON-LD
válidas, páginas no sitemap, links internos, texto suficiente, peso das imagens e artigos no blog.
**Erro** impede publicar; **aviso** publica, mas perde força no Google ou nas IAs.

## O que sai

Uma pasta por página, `blog/` e um diretório por artigo, `404.html`, `sitemap.xml`, `robots.txt` (robôs de
IA liberados), `_headers` (cache) e `assets/` (com as duas fontes escolhidas e a licença delas).
O site não carrega nada de outro domínio: sem Google Fonts, sem script de terceiros, sem cookie. Assim
o IP de quem visita não vai para ninguém além da hospedagem (LGPD; teste `teste_site_nao_carrega_nada_de_terceiros`). Fichas JSON-LD derivadas dos blocos e do tipo de página:
empresa (ProfessionalService), site, perguntas frequentes (de cada bloco de perguntas), página Sobre,
serviço, blog, artigo (BlogPosting com autor) e trilha de navegação.

A pesquisa que embasou estas escolhas está em [pesquisa-geradores.md](pesquisa-geradores.md).

## Publicar no Cloudflare Pages

Recomendado: plano gratuito, uso comercial permitido, e o painel do Cloudflare mostra as visitas de
robôs de IA ao site.

1. Criar o projeto no Cloudflare Pages (upload direto ou via `wrangler pages deploy entregas/<cliente>/site-publicar`).
2. Em Custom domains, adicionar `cliente.com.br` e `www.cliente.com.br`.
3. Redirecionar endereços antigos para o domínio principal (301): subdomínios usados antes
   (ex.: `site.empresa.com.br`) e páginas do site anterior que tinham visitas.
4. Enviar o `sitemap.xml` ao Search Console e ao Bing Webmaster Tools.
5. A cada artigo aprovado: `python main.py site <cliente> --publicar` e publicar de novo.

Pendente de automação: publicar direto pelo Portal (precisa do token da conta Cloudflare).

## Caso real (anonimizado, 15/10/2026)

O primeiro cliente tinha dois sites no ar: um WordPress antigo no domínio principal e um site novo
num subdomínio (Next.js de página única, sem sitemap, sem fichas e com os números renderizados como
zero no HTML). O site gerado juntou os textos do novo (números confirmados) com o conteúdo do antigo
e vai para o domínio principal, com o subdomínio redirecionando.
