# Segurança

## Como relatar uma vulnerabilidade

Não abra issue pública. Use o relato privado do GitHub: aba **Security** do repositório,
botão **Report a vulnerability**. Só a TimeLabs vê o relato.

Inclua o que for possível: a rota ou o arquivo afetado, como reproduzir e o impacto que você
imagina. A resposta inicial sai em até 3 dias úteis. Se o problema expuser dados pessoais, a
TimeLabs avalia a comunicação à ANPD e aos titulares (LGPD, Art. 48; ver [docs/LGPD.md](docs/LGPD.md)).

## Versões cobertas

Só o ramo `main`. Não há versões publicadas.

## Modelo de ameaça (resumo)

O Portal roda **na máquina de quem opera** (`127.0.0.1:5050`, um usuário, sem login). O risco
principal não é alguém na rede chegar nele, e sim **uma página aberta no mesmo navegador** tentar
usá-lo, ou um dado de fora (resposta de IA, site de cliente, arquivo enviado) carregar código.

| Ameaça | Proteção | Onde |
|---|---|---|
| Ler arquivos fora da pasta (ex.: `..\..\.env`) | ids e nomes de arquivo validados por lista de caracteres; caminho resolvido e conferido dentro da pasta | `app/seguranca.py` (`exigir_id`, `arquivo_dentro`) |
| Outro site mandar o Portal agir (CSRF) | métodos que mudam estado exigem mesma origem (`Sec-Fetch-Site`/`Origin`/`Referer`); APIs exigem `Content-Type: application/json` | `app/seguranca.py` (`proteger`, `json_do_pedido`) |
| DNS rebinding | lista de `Host` permitidos (`127.0.0.1`, `localhost`, `::1`); outro Host recebe 421 | `app/seguranca.py` |
| Portal aberto à equipe por túnel (ngrok) | só o endereço em `PORTAL_HOST_PUBLICO` é aceito além dos locais, e nele todo pedido exige usuário e senha (HTTP Basic sobre o HTTPS do túnel, comparação em tempo constante); sem senha no `.env`, esse endereço fica fechado e `main.py servir` se recusa a subir com senha de menos de 12 caracteres | `app/seguranca.py`, `main.py` |
| XSS por resposta de IA ou texto do cliente | Jinja com escape automático; Markdown passa por `markdown_seguro` (HTML cru escapado, links `javascript:`/`data:` neutralizados); CSP sem script inline | `conteudo/render.py`, `app/seguranca.py` |
| SSRF ao ler o site de um cliente | só `http(s)`; todos os IPs do nome precisam ser públicos; cada redirecionamento é conferido de novo | `rede.py` |
| Rastreamento sair do controle | só o domínio do cliente (concorrentes: uma leitura por página citada); respeita o robots.txt; pausa entre pedidos; teto de páginas e de 5 MB por resposta; para depois de 10 recusas seguidas; robots.txt patológico não trava a leitura | `radar/rastreador.py`, `radar/auditoria.py` |
| Clickjacking e vazamento por Referer | `X-Frame-Options`, `frame-ancestors`, `Referrer-Policy: same-origin`, COOP/CORP | `app/seguranca.py` |
| Upload malicioso | só JPG/PNG/WebP até 8 MB, conferidos pelo Pillow; nome gerado pelo sistema | `app/servidor.py` (`api_site_imagem`) |
| Gasto de API sem querer | toda chamada paga exige estimativa e confirmação, com teto por execução | `custos.py` |
| Chave ou dado de cliente no Git | `.env` e dados de uso fora do Git; gitleaks no CI varre o histórico inteiro | `.gitignore`, `.github/workflows/ci.yml` |

Fora do escopo, por desenho: contas de usuário e multiusuário (o Portal não deve ser exposto na rede;
`main.py servir` só escuta em `127.0.0.1`). A exceção é o túnel temporário para a equipe, com uma
senha só para todos: quem tem a senha faz tudo o que o operador faz, inclusive rodar execuções pagas
e ver os dados de todos os clientes. Feche o túnel quando o teste acabar e troque a senha se ela vazar. Antes de virar serviço na internet, ver os itens
pendentes em [docs/AUDITORIA.md](docs/AUDITORIA.md).

## Checagens automáticas

A cada push: `ruff` (inclui as regras de segurança do bandit), `bandit`, `pip-audit` sobre as
versões exatas do `requirements-lock.txt`, testes e `gitleaks` no histórico. O Dependabot avisa de
atualizações das dependências e das actions.
