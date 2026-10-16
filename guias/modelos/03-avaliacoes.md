---
titulo: Aumentar as avaliações no Google
eyebrow: Guia · reputação · contínuo
resumo: Avaliações são o sinal que mais separa empresas recomendadas pelas IAs das que não são. É um processo simples, que precisa virar rotina.
gerado: portal
---

## Por que isso pesa tanto

- Num estudo com 10 mil empresas, as recomendadas pelo ChatGPT e pelo Perplexity tinham, em média,
  **133 avaliações no Google**. As não recomendadas, **11**. O mesmo estudo viu quase nenhuma relação
  entre SEO técnico e ser recomendado.
- Avaliações recentes e respondidas pesam mais que um volume antigo e parado.

## A meta

{% if concorrentes %}
Olhar no Google Maps quantas avaliações têm as empresas mais indicadas no radar de {{ data }}
({{ concorrentes | join(", ") }}) e definir uma meta para a {{ nome }} alcançá-las em 90 dias.
{% else %}
Olhar no Google Maps quantas avaliações têm as empresas mais indicadas no setor e definir uma meta
para a {{ nome }} alcançá-las em 90 dias.
{% endif %}
O ritmo importa: avaliações chegando todo mês valem mais que um mutirão de uma semana.

## Como pedir

- [ ] Gerar o link direto de avaliação no Perfil da Empresa no Google ("Pedir avaliações")
- [ ] Pedir no momento certo: depois de uma entrega ou de um resultado que o cliente comemorou
- [ ] Mandar pelo WhatsApp, com a mensagem abaixo e o link
- [ ] Deixar um QR code com o link em reuniões, propostas e relatórios
- [ ] Responder todas as avaliações em até 48 horas, inclusive as negativas, com educação e fatos

**Mensagem pronta (WhatsApp):**

> Oi, [nome]! Que bom ver o resultado de [projeto]. Se a parceria com a {{ nome }} está valendo a pena,
> uma avaliação no Google ajuda muito outras empresas a nos encontrarem: [link]. Leva menos de um
> minuto. Obrigado!

## Regras que não podem ser quebradas

- **Sem incentivo:** o Google proíbe oferecer desconto, brinde ou qualquer vantagem em troca de
  avaliação.
- **Sem filtro:** pedir a todos os clientes, não só aos satisfeitos. Selecionar quem pode avaliar
  também viola as regras do Google.
- **Sem avaliação comprada ou de conhecidos se passando por clientes.** Além de proibido, as IAs e o
  Google identificam padrões artificiais.
- **LGPD:** usar só o contato que o cliente forneceu para o atendimento.
{% if not e_a_timelabs %}

## O que a TimeLabs pode montar

Página com o QR code e o link de avaliação, mensagem pronta no WhatsApp e acompanhamento mensal do
número de avaliações da {{ nome }} contra os concorrentes.
{% endif %}
