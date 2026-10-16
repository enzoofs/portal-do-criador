---
titulo: Bing, Google e as plataformas que as IAs mais citam
eyebrow: Guia · presença · 1 dia para começar
resumo: A busca do ChatGPT usa principalmente o índice do Bing, e Reddit, YouTube e LinkedIn lideram as citações das IAs. Perfis completos e consistentes nesses lugares sustentam todo o resto.
gerado: portal
---

## Regra de ouro: os mesmos dados em todo lugar

Nome **{{ nome }}**, cidade **{{ cidade }}, {{ regiao }}**{% if whatsapp %}, telefone **{{ whatsapp }}**{% endif %}, site
**{{ dominio }}**, escritos sempre igual. Dados divergentes entre perfis são uma das causas de IA
confundir empresas.

## 1. Bing (prioridade, de graça)

Estudos encontraram entre 73% e 87% de coincidência entre as fontes do ChatGPT e os resultados do
Bing. Ninguém olha para o Bing, e é por ele que o ChatGPT encontra sites.

O radar não tem como ver as contas da empresa: confira cada item e pule o que já estiver feito.

- [ ] **Bing Webmaster Tools:** cadastrar o site, se ainda não estiver (dá para importar direto do Google Search Console)
{% if sitemap_ok %}
- [ ] Enviar o sitemap do site
{% else %}
- [ ] Publicar o sitemap (o radar não encontrou um) e enviar o endereço
{% endif %}
- [ ] Acompanhar o relatório **AI Performance**: mostra quando o site é citado no Copilot e quais
      buscas a IA fez antes de citar. É gratuito.
- [ ] **Bing Places:** criar o perfil local, se ainda não existir (dá para importar do Perfil da Empresa no Google)

## 2. Perfil da Empresa no Google

- [ ] Criar o perfil, se ainda não existir
- [ ] Categoria principal que descreve {{ segmento }}
- [ ] Área atendida, serviços, descrição com as mesmas palavras da página "Sobre", link do site{% if whatsapp %} e do WhatsApp{% endif %}

- [ ] Uma novidade por mês (pode ser o resumo de cada artigo novo)
- [ ] Avaliações: ver o guia de avaliações

## 3. LinkedIn

- [ ] Página da empresa com o texto do "Sobre" e o link do site
- [ ] Perfil dos sócios apontando para a empresa como cargo atual
- [ ] Publicar como artigo os conteúdos do blog: o LinkedIn está entre os sites mais citados pelo
      ChatGPT

## 4. YouTube

O resumo com IA do Google cita o YouTube mais que qualquer outro site. Vídeos curtos respondendo
às perguntas que os clientes fazem{% if pergunta_exemplo %} ("{{ pergunta_exemplo }}"){% endif %} servem ao YouTube,
ao Instagram e às IAs ao mesmo tempo.

## 5. Instagram

- [ ] Bio com cidade, serviço e o link do site
{% if sem_perfis %}
- [ ] O site não linka nenhum perfil oficial (a auditoria do radar conferiu): pôr o Instagram e o LinkedIn no rodapé
{% endif %}
{% if plataformas_citadas %}

## O que o radar de {{ data }} mostrou

As IAs citaram estas plataformas nas respostas: {{ plataformas_citadas | join(", ") }}. Perfis completos
nelas vêm primeiro.
{% endif %}

## O que não fazer

- Criar página na Wikipédia sem relevância comprovada por imprensa.
- Comprar avaliações, seguidores ou listas de "melhores empresas".
