# Como trabalhar neste repositório

## Preparar o ambiente

```bash
python -m venv venv
venv\Scripts\activate                      # Linux/macOS: source venv/bin/activate
pip install -r requirements-lock.txt       # versões exatas testadas
pip install ruff==0.17.1 bandit==1.9.4 pip-audit==2.10.1
copy .env.example .env                     # Linux/macOS: cp; sem chaves, tudo roda em modo demonstração
```

## Antes de cada commit

As mesmas checagens do CI ([.github/workflows/ci.yml](.github/workflows/ci.yml)):

```bash
ruff check .                     # estilo, erros e regras de segurança (config no pyproject.toml)
bandit -c pyproject.toml -r . -q
python testes.py                 # sem IA, sem rede, sem custo
```

Se mexer em dependências: atualize `requirements.txt` (faixa aceita), gere de novo o
`requirements-lock.txt` (`pip freeze`) e rode `pip-audit -r requirements-lock.txt --no-deps --disable-pip`.

## Regras do projeto

1. **Dado real de cliente não entra no Git.** Cadastros (`config/clientes/`), sites
   (`config/sites/`), entregas e tudo em `data/` e `relatorios/` ficam no `.gitignore`. Para
   testes e exemplos use o cliente fictício `exemplo` (domínio `.example`, WhatsApp `5500000000000`)
   e nomes inventados. Nada de nome, telefone, e-mail ou foto de pessoa real. Ver [docs/LGPD.md](docs/LGPD.md).
2. **Nada pago roda sem confirmação.** Chamadas de IA ou de coleta passam por `custos.py`
   (estimativa, `--confirmar`, teto). Teste nunca chama API paga.
3. **Chaves só no `.env`.** Nunca no código, em teste, em log ou no `.env.example`.
4. **Entrada de fora é hostil.** Id ou nome de arquivo vindo da URL passa por
   `seguranca.exigir_id` / `seguranca.arquivo_dentro`; JSON das APIs por
   `seguranca.json_do_pedido`; Markdown de IA ou de cliente por `render.markdown_seguro`;
   URL que o servidor vai buscar por `rede.baixar`. `Markup(...)` só com conteúdo já escapado,
   com comentário dizendo por quê.
5. **Novo lugar de gravação por cliente** precisa entrar em `privacidade.locais()`, para o
   comando `esquecer` continuar apagando tudo.
6. **Todo bug corrigido ganha um teste** em `testes.py` que reproduz o erro (veja as docstrings).
7. **Interface:** fonte Geist, cantos retos, linhas de 1 px, contraste AA. Rode o axe nas telas
   que mudar.

## Estilo

- Código, nomes e comentários em português, como o resto do projeto.
- Comentário explica o porquê, não o quê.
- Funções usadas por outros módulos não começam com `_`.
- Commits pequenos, com mensagem no imperativo ("Corrige ...", "Adiciona ...").
