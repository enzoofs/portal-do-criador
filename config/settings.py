"""
config/settings.py — Configurações centralizadas do Portal do Criador.

Mesma regra do Content Agent: nenhum valor de configuração fica hardcoded
nos módulos. Modelos, chaves, preços e caminhos vivem aqui.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# --------------------------------------------------------------------------
# Caminhos
# --------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent.parent
CLIENTES_DIR = BASE_DIR / "config" / "clientes"
RUNS_DIR = BASE_DIR / "data" / "runs"
RELATORIOS_DIR = BASE_DIR / "relatorios"

# --------------------------------------------------------------------------
# Chaves de API (todas opcionais: o radar usa só os provedores com chave)
# --------------------------------------------------------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# DataForSEO: respostas como aparecem no app (ChatGPT, Gemini, Google). Login e senha da API.
DATAFORSEO_LOGIN = os.getenv("DATAFORSEO_LOGIN")
DATAFORSEO_SENHA = os.getenv("DATAFORSEO_SENHA")
DATAFORSEO_LOCAL = int(os.getenv("DATAFORSEO_LOCAL", "2076"))   # 2076 = Brasil
DATAFORSEO_IDIOMA = os.getenv("DATAFORSEO_IDIOMA", "pt")
# GA4 + Search Console: arquivo JSON de uma conta de serviço do Google (leitura)
GOOGLE_CREDENCIAIS = os.getenv("GOOGLE_CREDENCIAIS")

# --------------------------------------------------------------------------
# Modelos — padrões BARATOS; os caros só por escolha explícita no .env
# --------------------------------------------------------------------------
# Preços por 1M tokens em custos.PRECOS_TOKENS. Ex.: gpt-5.5 custa US$5/US$30,
# gpt-5.4-mini US$0,75/US$4,50; Opus 5.5 US$4/US$20, Sonnet 5.5 US$2/US$10.

# Radar: cada modelo simula o "assistente" que o cliente final usa
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")
CLAUDE_EFFORT = os.getenv("CLAUDE_EFFORT", "medium")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# IAs que o radar consulta (entre as que têm chave). Vazio = todas.
RADAR_PROVEDORES = [p for p in os.getenv("RADAR_PROVEDORES", "").split(",") if p]

# Buscas na web por pergunta (cada busca é cobrada à parte)
MAX_BUSCAS_POR_PERGUNTA = 5

# Geração estruturada, por nível de exigência:
#   extracao = ler uma resposta e tirar nomes (tarefa simples)
#   redacao  = pauta e artigos (qualidade importa)
MODELOS_GERACAO = {
    "extracao": {"claude": os.getenv("EXTRACAO_CLAUDE_MODEL", "claude-haiku-5-5"),
                 "openai": os.getenv("EXTRACAO_OPENAI_MODEL", "gpt-5.4-mini")},
    "redacao": {"claude": os.getenv("REDACAO_CLAUDE_MODEL", "claude-sonnet-5-5"),
                "openai": os.getenv("REDACAO_OPENAI_MODEL", "gpt-5.4-mini")},
}

# Teto de gasto padrão por execução (US$); muda com --limite
LIMITE_USD_PADRAO = 2.00

# Geração com saída estruturada (extrator do radar, pauta, redator):
# usa o primeiro provedor com chave, nesta ordem.
GERACAO_PROVEDORES = os.getenv("GERACAO_PROVEDORES", "claude,openai").split(",")

# Execução paralela (uma thread por pergunta x provedor)
MAX_WORKERS = 6

# --------------------------------------------------------------------------
# Conteúdo
# --------------------------------------------------------------------------
CONTEUDO_DIR = BASE_DIR / "data" / "conteudo"
ARTIGOS_POR_PAUTA = 6

# WordPress do cliente (REST API + senha de aplicativo; publica só como rascunho)
# As credenciais ficam no .env com o id do cliente: WP_<ID>_USUARIO / WP_<ID>_SENHA_APP
WP_STATUS_PADRAO = "draft"

# IndexNow (Bing, Yandex, Seznam...) — avisa os buscadores na hora que um post sai
INDEXNOW_ENDPOINT = "https://api.indexnow.org/indexnow"
