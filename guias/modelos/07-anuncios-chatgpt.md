---
titulo: Preparar campanhas de anúncios no ChatGPT
eyebrow: Guia · mídia paga · acompanhar
resumo: O ChatGPT virou canal de mídia. Onde a marca não aparece de forma orgânica, o anúncio cobre, e quem chegar primeiro aprende antes dos concorrentes.
gerado: portal
---

## O que já existe

- **Estados Unidos:** compra por conta própria desde maio de 2026, para qualquer empresa. Cobrança
  por clique (lance mínimo de US$ 3 a 5 por categoria) ou por mil impressões (de US$ 25 a 60).
- **Reino Unido:** compra por conta própria desde junho de 2026.
- **Brasil:** piloto desde agosto de 2026, para usuários dos planos Free e Go. As categorias
  iniciais incluem estilo de vida, casa, **serviços locais**, viagens, produtos digitais e educação.
  Até a data deste guia, não havia compra por conta própria aberta no Brasil.

Os números acima vêm de imprensa e guias especializados, não de documentação da OpenAI. Conferir
com a OpenAI antes de planejar verba.

## Como a medição funciona

- O clique no anúncio chega ao site com um parâmetro de rastreamento (`oppref`).
- O **pixel da OpenAI** registra conversões no site (lead, compra, página vista). Também existe
  envio pelo servidor (API de conversões), recomendado junto com o pixel.

## Como se preparar agora

- [ ] Usar as perguntas em que a {{ nome }} não aparece no radar como temas de campanha
- [ ] Ter uma página de destino para cada serviço e nicho, que a ação de conteúdo já cria
- [ ] Medição no site pronta: GA4 com eventos de lead{% if whatsapp %} e clique no WhatsApp{% endif %}

- [ ] Acompanhar a abertura da compra no Brasil e reservar uma verba de teste
- [ ] Separar no relatório o que veio de anúncio e o que veio de citação orgânica
{% if agencia %}

## Para a agência

A {{ nome }} vende mídia paga. Saber operar anúncios no ChatGPT antes dos concorrentes é uma oferta
nova para a carteira inteira, além do uso na própria agência.
{% endif %}
