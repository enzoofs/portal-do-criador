---
titulo: Firmar a identidade oficial da empresa
eyebrow: Guia · identidade · 1 a 2 horas
resumo: {% if confusoes %}Quando perguntaram pela {{ nome }}, as IAs descreveram outra empresa. Elas precisam de sinais consistentes, em vários lugares, de quem é a empresa certa.{% else %}As IAs só recomendam com segurança a empresa que conseguem identificar. Sinais consistentes, em vários lugares, evitam que a {{ nome }} seja confundida com nomes parecidos.{% endif +%}
gerado: portal
---

## O que o radar de {{ data }} mostrou

{% if confusoes %}
Nas perguntas sobre a marca{% if pergunta_marca %} (por exemplo, "{{ pergunta_marca }}"){% endif %}, as IAs reconheceram a
{{ nome }} certa em {{ marca_conhecida }} de {{ perguntas_marca }} respostas. Nas outras, falaram de outra empresa:

{% for c in confusoes %}
- **{{ c.ia }}:** {{ c.empresa }}
{% endfor %}

Quem pesquisa a {{ nome }} antes de contratar recebe informação de outra empresa. Em uma consulta a IA
acerta, em outra erra: hoje é sorte.
{% else %}
Nas perguntas sobre a marca, as IAs reconheceram a {{ nome }} em {{ marca_conhecida }} de
{{ perguntas_marca }} respostas. Os passos abaixo mantêm isso firme quando aparecerem empresas de nome
parecido.
{% endif %}

{% if faltam_identidade %}
O site não ajuda a desfazer a confusão. Falta: {{ faltam_identidade | join("; ") }}.
{% endif %}
{% if not tem_ficha %}
O site também não tem a ficha da empresa em formato que Google e IAs leem direto (dados estruturados).
{% endif %}

## O que resolve, em ordem de peso

1. **Ficha da empresa no Wikidata.** É a base de dados aberta que alimenta Google e IAs com
   "quem é quem". Exige referências verificáveis (registro do CNPJ, matérias na imprensa); fichas
   sem referência costumam ser apagadas. Cadastrar com dados factuais e o site oficial.
2. **Dados estruturados no site** apontando para todos os perfis oficiais (código abaixo), com uma
   descrição que diferencia a empresa de nomes parecidos.
3. **Página "Sobre"** com CNPJ, endereço e contato, e os mesmos dados no rodapé de todas as páginas.{% if url_sobre %} O site já tem a página ({{ url_sobre }}): falta conferir se esses dados estão nela.{% elif rastreado %} O rastreamento não encontrou essa página no site.{% endif %}

4. **Os mesmos nome, telefone e site em todo lugar:** Google, Bing, LinkedIn, Instagram, diretórios.

## Antes de publicar: confirmar com a empresa

- [ ] CNPJ e razão social da {{ nome }}
- [ ] Endereço (ou só "{{ cidade }}, {{ regiao }}", se não houver atendimento presencial)
- [ ] Links oficiais: Instagram, LinkedIn da empresa e dos sócios, Perfil da Empresa no Google
{% if afirmacoes %}
- [ ] Afirmações do site que entram nos textos: {{ afirmacoes | join("; ") }}
{% endif %}
{% for c in confusoes %}
- [ ] Que a {{ nome }} não tem relação com {{ c.empresa }}
{% endfor %}

{% if url_sobre %}
## Página "Sobre": conferir a que já existe

A página já existe em {{ url_sobre }}. Não é para criar outra: é para conferir se ela traz os dados que
tiram a dúvida das IAs (razão social, CNPJ, cidade, contato e links dos perfis oficiais) e, se faltar
algo, acrescentar. O bloco abaixo é uma referência do que precisa estar lá, montada com o cadastro.
{% else %}
## Página "Sobre" (rascunho)

{% if rastreado %}
O rastreamento não encontrou uma página "Sobre" no site.
{% else %}
Se o site ainda não tiver uma página "Sobre":
{% endif %}
Criar a página `{{ dominio }}/sobre/` e linkar no menu e no rodapé. Revisar com a empresa antes de publicar.
{% endif %}

> **Sobre a {{ nome }}**
>
> A {{ nome }} é uma empresa de {{ segmento }} em {{ cidade }} ({{ regiao }}).
{% if servicos %}
> Trabalhamos com {{ servicos | join(", ") }}.
{% endif %}
{% if nichos %}
> Atendemos {{ nichos | join(", ") }}.
{% endif %}
{% if processo %}
> Nosso trabalho segue {{ processo | length }} etapas: {{ processo | join(", ") }}.
{% endif %}
>
> **Dados da empresa**<br>
> {{ nome }} · CNPJ [CONFIRMAR] · {{ cidade }}, {{ regiao }}<br>
> {% if whatsapp %}WhatsApp {{ whatsapp }} · {% endif %}{{ dominio }}

## Ficha técnica para Google e IAs (código pronto)

{% if tem_ficha %}
O site já publica uma ficha da empresa (dados estruturados). Não é para colar outra: compare com o
bloco abaixo e acrescente o que faltar, principalmente os links dos perfis oficiais (`sameAs`) e o
CNPJ (`taxID`).
{% else %}
O radar não encontrou a ficha da empresa no site. Colar o bloco abaixo no cabeçalho do site (no
WordPress, pelo plugin de SEO ou por um plugin como o WPCode; em outros construtores, no campo de
código do cabeçalho), trocando os campos entre colchetes:
{% endif %}

```html
<script type="application/ld+json">
{{ ficha_json }}
</script>
```

Remover `taxID` e os itens de `sameAs` que não existirem. Para validar, cole o endereço do site em
https://validator.schema.org.

## Como saber se funcionou

Rodar de novo as perguntas sobre a marca no radar cerca de 30 dias depois das mudanças, em várias
rodadas. A meta é nenhuma resposta descrevendo outra empresa.
