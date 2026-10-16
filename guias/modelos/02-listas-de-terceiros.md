---
titulo: Entrar nas listas e páginas de terceiros que as IAs consultam
eyebrow: Guia · presença · contínuo
resumo: Quando alguém pede indicação, as IAs montam a resposta com sites de terceiros, não com o site da empresa. Estar nessas páginas é a alavanca mais forte para ser indicado.
gerado: portal
---

## Por que isso pesa tanto

- Num estudo com 175 marcas, praticamente todas as citações das IAs em perguntas de categoria
  ("qual a melhor empresa de…") apontavam para sites de terceiros.
- Em dois experimentos, listas de "melhores" publicadas por terceiros responderam por cerca de 86%
  das primeiras citações de uma marca nova. A lista feita pela própria marca, por 14%.
- Listas autopromocionais (a empresa se colocando em primeiro) são citadas cerca de três vezes
  menos que listas neutras.

## O que o radar de {{ data }} mostrou

{% if terceiros %}
As listas, rankings e plataformas que as IAs mais leram para responder as perguntas da {{ nome }}:

{% for f in terceiros %}
- **{{ f.dominio }}**, em {{ f.vezes }} resposta{{ "s" if f.vezes != 1 }}
{% endfor %}

Cada um é um alvo: pedir inclusão, completar o perfil ou participar da conversa.
{% else %}
Neste radar as IAs não citaram listas, rankings nem diretórios do setor.
{% endif %}
{% if empresas_fonte %}

Outros {{ empresas_fonte }} sites citados como fonte são de empresas, provavelmente do mesmo setor: não
são alvo de inclusão, mas mostram o tipo de página que as IAs gostam de ler.
{% endif %}

A tabela no fim deste guia mostra as páginas exatas e os concorrentes que apareceram junto.
{% if paginas_concorrentes %}

Páginas dos próprios concorrentes apareceram {{ paginas_concorrentes }} vez{{ "es" if paginas_concorrentes != 1 }} entre as mais lidas
{% if concorrentes %}(quem mais aparece: {{ concorrentes | join(", ") }}){% endif %}. É o sinal de que páginas de serviço
por cidade, com conteúdo próprio, viram fonte; a ação de conteúdo cria as equivalentes da {{ nome }}.
{% endif %}
{% if reddit %}

O **Reddit** apareceu entre as fontes: fóruns pesam, inclusive em português.
{% endif %}

## Como agir, por tipo de página

- **Fóruns (Reddit e similares):** responder discussões reais com experiência de quem faz, com o
  perfil identificado e sem propaganda. Comunidades punem autopromoção, e as IAs leem o tom.
- **Listas e diretórios:** pedir inclusão ao autor da lista com um motivo editorial (um case, um
  dado, um nicho que a empresa domina). Completar perfis em diretórios do setor.
- **Imprensa local e setorial:** oferecer pauta com dado próprio, com números anonimizados da
  carteira. Dados originais são o que jornalistas e IAs citam.
- **Wikipédia:** só com relevância comprovada por imprensa independente. Página promocional é
  apagada e marca o nome.

## O que não fazer

- **Comprar ranking disfarçado de notícia.** O Google tem política contra conteúdo de terceiros
  usado para manipular a busca, e o CONAR exige que publicidade seja identificada.
- **Criar perfis falsos em fóruns** ou publicar autoelogio em nome de terceiros.

## Como saber se funcionou

Rodar o radar a cada 30 dias e acompanhar duas coisas: se a {{ nome }} passa a aparecer nas
respostas e se ela aparece junto dessas páginas.
