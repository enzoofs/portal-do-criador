---
titulo: Liberar os robôs das IAs
eyebrow: Guia · técnico · 10 a 30 minutos
resumo: O site recusa robôs que as IAs usam para ler e conhecer a empresa. O ajuste costuma ser rápido, no painel da hospedagem, do Cloudflare ou no robots.txt.
gerado: portal
---

## O que o radar de {{ data }} encontrou

{% if robos_bloqueados %}
Testamos o acesso ao site simulando cada robô. Estes foram recusados:

{% for r in robos_bloqueados %}
- {{ r }}
{% endfor %}

Recusa de robô vem quase sempre de um firewall na frente do site (Cloudflare, plugin de segurança,
proteção da hospedagem), não do conteúdo.
{% endif %}
{% if robots_bloqueia %}

O arquivo `robots.txt` do site proíbe estes robôs de ler o site: {{ robots_bloqueia }}.
{% endif %}

## O que isso muda

Robôs de **busca** (OAI-SearchBot, ChatGPT-User, Claude-SearchBot, PerplexityBot, Googlebot, bingbot)
leem o site na hora de responder: bloqueados, a empresa não pode ser citada. Robôs de **treino**
(GPTBot, ClaudeBot) definem o que os modelos sabem da empresa sem pesquisar. Liberar o treino
significa permitir que o conteúdo público seja usado para treinar esses modelos; para um site
institucional que quer ser conhecido, isso tende a ser vantagem. **A decisão é da empresa.**

## Como liberar

1. **Cloudflare:** abra **AI Crawl Control** (ou **Segurança → Bots**, em contas mais antigas) e
   permita os robôs de IA em vez do bloqueio geral. Em **Segurança → WAF → Regras personalizadas**,
   desative regras que bloqueiem "GPTBot", "ClaudeBot" ou "AI". Não mexa nas proteções contra robôs
   maliciosos.
2. **Plugin de segurança ou hospedagem:** procure a lista de robôs bloqueados e tire os de IA.
3. **robots.txt:** apague as linhas `Disallow` dos robôs de IA.

## Como conferir

```
curl -s -o /dev/null -w "%{http_code}\n" -A "GPTBot/1.2" https://{{ dominio }}/
curl -s -o /dev/null -w "%{http_code}\n" -A "OAI-SearchBot/1.3" https://{{ dominio }}/
```

Os dois precisam responder **200**. A auditoria do radar confere isso a cada execução.
