# LGPD: dados pessoais no Portal do Criador

Documento técnico. Mostra que dados o sistema trata, onde ficam, para onde vão e como atender
o titular. **Não substitui parecer jurídico.** Os papéis, as bases legais e os contratos com
fornecedores precisam ser confirmados com a assessoria jurídica da TimeLabs antes do uso comercial.

Lei 13.709/2018 (LGPD) e resoluções da ANPD citadas: CD/ANPD nº 2/2022 (agentes de pequeno porte),
nº 15/2024 (comunicação de incidente), nº 18/2024 (encarregado) e nº 19/2024 (transferência internacional).

## 1. Papéis

| Situação | Controlador | Operador |
|---|---|---|
| Dados que a empresa cliente entrega (perfil, fotos, depoimentos, acesso ao GA4/Search Console/Google Ads) | a empresa cliente | TimeLabs |
| Revenda por agência (ex.: a agência vende o serviço aos clientes dela) | o cliente final | a agência; a TimeLabs como suboperadora |
| Dados da própria TimeLabs (contrato, cobrança, registro de gastos) | TimeLabs | — |

Como operadora, a TimeLabs trata os dados só conforme as instruções do controlador (Art. 39). Isso
precisa estar no contrato, com as finalidades, os fornecedores (seção 4) e o que acontece no fim
do contrato (seção 5).

## 2. Inventário

Tudo fica em arquivos na máquina de quem opera o Portal. Nada disso vai para o Git (`.gitignore`).

| Dado | Exemplo | Titular | Onde fica | Finalidade |
|---|---|---|---|---|
| Cadastro da empresa | nome, site, cidade, serviços | (empresa; não é dado pessoal, exceto MEI/empresário individual) | `config/clientes/<id>.json` | radar, conteúdo, site |
| Especialista/autor | nome, cargo, minibio | sócio ou funcionário do cliente | `config/clientes/<id>.json` (`perfil.autor`) | assinatura dos artigos (E-E-A-T) |
| Contato comercial | WhatsApp | muitas vezes o celular do dono | `config/clientes/<id>.json` (`perfil.cta`) | botão do site e dos artigos |
| Site do cliente | fotos do fundador, depoimentos (nome e cargo de quem deu), CNPJ, endereço | fundador; clientes do cliente | `config/sites/<id>/` | site gerado |
| Respostas das IAs (radar) | texto público que cita empresas e, às vezes, pessoas | terceiros citados | `data/runs/<id>/` | medir a visibilidade |
| Artigos e respostas do especialista | texto, dados que o especialista confirma | especialista | `data/conteudo/<id>/` | blog |
| Métricas | sessões e cliques agregados do GA4 e do Search Console | (agregado; sem visitante individual) | `data/medicao/<id>/` | resultados |
| Termos do Google Ads | buscas agregadas | (agregado; raramente contém um nome) | `data/midia/<id>.json` | pauta |
| Credenciais | senhas de aplicativo do WordPress, tokens de Webflow/Shopify/Wix | (dado de segurança) | `.env` | publicar rascunhos |
| Derivados | relatórios, plano de correção, site gerado, histórico de versões, cache de imagens | os mesmos acima | `relatorios/`, `entregas/<id>/`, `data/sites_historico/<id>/`, `data/cache_sites/<id>/` | entrega ao cliente |

`privacidade.locais()` lista exatamente esses caminhos; é a fonte de verdade para exportar e apagar.

**Dado sensível (Art. 11).** Clientes da área da saúde (clínicas, consultórios) podem trazer
depoimentos que revelam tratamento ou condição de saúde. Isso é dado sensível e exige
consentimento específico e destacado do paciente, colhido pelo cliente. Regra de operação: não
cadastrar depoimento de paciente sem esse consentimento por escrito.

**Visitantes dos sites gerados.** O site gerado não usa cookie, formulário, script de terceiros
nem fonte externa (as fontes vão dentro do site; teste `teste_site_nao_carrega_nada_de_terceiros`).
O único dado de visitante é o log da hospedagem escolhida pelo cliente. Se o cliente acrescentar
GA4, pixel ou chat, o site passa a precisar de aviso e de gestão de consentimento.

## 3. Bases legais (Art. 7) — proposta a validar

| Tratamento | Base sugerida | Observação |
|---|---|---|
| Perfil, site e conteúdo do cliente | execução de contrato (V), pelo controlador | a TimeLabs opera em nome do cliente |
| Foto, nome e minibio do fundador no site | consentimento (I) ou contrato, se o fundador for parte | também é direito de imagem (Código Civil, Art. 20): pedir autorização por escrito |
| Depoimentos de clientes do cliente | consentimento (I) de quem deu o depoimento, colhido pelo cliente | registrar a autorização; sem ela, o bloco não vai ao ar |
| Respostas públicas de IA que citam terceiros (radar) | legítimo interesse (IX), com teste de balanceamento | dado tornado público; uso limitado à medição (Art. 7, §§ 3º, 4º e 7º) |
| Métricas agregadas | não é dado pessoal se não der para reidentificar (Art. 12) | o sistema só lê relatórios agregados, com permissão de leitura |

## 4. Fornecedores e transferência internacional (Art. 33)

| Fornecedor | O que recebe | País |
|---|---|---|
| OpenAI | perguntas do radar com cidade e região; perfil da empresa **sem o contato** para pauta e artigos; texto público do site do cliente no cadastro | EUA |
| Anthropic | o mesmo, quando configurada como provedora | EUA |
| Google (Gemini, GA4, Search Console) | perguntas do radar; leitura das métricas do próprio cliente | EUA |
| DataForSEO | perguntas do radar e a localização | exterior |
| WordPress, Webflow, Shopify, Wix | os artigos, como rascunho, na conta do próprio cliente | conforme a plataforma do cliente |

O que o código já faz:

- **Minimização (Art. 6, III):** `ia.perfil_para_prompt` tira o WhatsApp e as notas internas do perfil
  antes de montar o prompt. O radar só envia cidade e região. Fotos e depoimentos nunca vão para IA.
- **Sem retenção de resposta na OpenAI:** as chamadas usam `store=False`.
- **Nada pago roda sem confirmação** (`custos.py`), o que também evita envios não planejados.

O que falta e não é código:

- Confirmar se o contrato (DPA) de cada fornecedor traz as cláusulas-padrão da ANPD (Resolução
  nº 19/2024) ou outro mecanismo válido do Art. 33, e guardar a evidência.
- Registrar a política de retenção de cada fornecedor (registros de abuso podem ficar dias
  mesmo com `store=False`).
- Informar no contrato com o cliente quais fornecedores recebem dados e para quê (Art. 9).

## 5. Retenção e eliminação (Arts. 15 e 16)

| Dado | Retenção proposta |
|---|---|
| Tudo do cliente | enquanto durar o contrato; ao terminar, entregar a exportação e apagar em até 30 dias |
| Histórico de versões do site | as últimas 50 versões (`VERSOES_GUARDADAS` em `app/servidor.py`) |
| Exportações (`relatorios/dados-<id>-*.zip`) | apagar assim que entregues |
| Registro de gastos | fica (é conta da TimeLabs); o id do cliente é trocado por "removido" na eliminação |
| Cópias de segurança | precisam seguir o mesmo prazo: apagar ou deixar expirar os backups com dados do cliente |

Comandos:

```bash
python main.py exportar <cliente>              # acesso e portabilidade: .zip com tudo do cliente
python main.py esquecer <cliente>              # lista o que seria apagado
python main.py esquecer <cliente> --confirmar  # apaga
```

O `esquecer` não alcança o que já saiu do sistema: cópias de segurança, arquivos enviados ao
cliente, rascunhos publicados no site dele e o que ficou com os fornecedores. Isso vai num
checklist manual de encerramento.

## 6. Direitos do titular (Art. 18)

| Direito | Como atender |
|---|---|
| Confirmação e acesso (I, II) | `python main.py exportar <cliente>` e filtrar o que é do titular |
| Correção (III) | telas **Configurações** e **Site** do Portal |
| Anonimização, bloqueio ou eliminação (IV, VI) | `python main.py esquecer <cliente> --confirmar` (cliente inteiro) ou edição pontual (um depoimento, uma foto) |
| Portabilidade (V) | a exportação sai em formatos abertos (JSON, HTML, imagens) |
| Informação sobre compartilhamento (VII) | seção 4 deste documento |
| Revogação do consentimento (IX) | tirar o bloco (depoimento, foto) no editor do site e publicar de novo |

Pedidos de titular chegam ao controlador (o cliente). Quando chegarem à TimeLabs, encaminhar ao
cliente, indicar ao titular quem é o controlador (Art. 18, § 4º, I) e ajudar o cliente a cumprir. Prazo de referência: 15 dias para a resposta completa
(Art. 19, II).

## 7. Segurança (Art. 46)

Medidas no código: ver [SECURITY.md](../SECURITY.md). Em resumo: o Portal só escuta em
`127.0.0.1`, recusa pedidos de outros sites (CSRF e DNS rebinding), valida todo caminho de
arquivo, escapa todo HTML de origem externa e restringe uploads. O CI procura segredos no
histórico e vulnerabilidades nas dependências.

Medidas de operação, de responsabilidade de quem opera:

- Disco da máquina criptografado (BitLocker no Windows ou FileVault no macOS) e tela bloqueada:
  os dados ficam em arquivos comuns.
- `.env` com as credenciais só na máquina de quem opera; chave vazada deve ser trocada na hora.
- Backups criptografados e com prazo (seção 5).
- Acesso às contas do cliente (GA4, Search Console, Google Ads, CMS) com o menor papel possível,
  de preferência um usuário próprio da TimeLabs que o cliente consiga revogar.

## 8. Incidentes (Art. 48; Resolução ANPD nº 15/2024)

1. Conter: trocar chaves, revogar acessos, tirar do ar o que vazou.
2. Avaliar se o incidente pode causar risco ou dano relevante aos titulares.
3. Se puder: o controlador comunica a ANPD e os titulares em até **3 dias úteis** a partir do
   conhecimento. Como operadora, a TimeLabs avisa o cliente (controlador) imediatamente.
4. Registrar o incidente, mesmo o não comunicado, e guardar o registro por pelo menos **5 anos**.

## 9. Encarregado (Art. 41)

Agente de pequeno porte pode ficar dispensado de indicar encarregado (Resolução nº 2/2022), mas
precisa manter um canal para os titulares. Definir o canal da TimeLabs e publicá-lo no contrato e
no site.

## 10. Para o desenvolvimento

- Dado real de cliente nunca entra no Git; testes e exemplos usam o cliente fictício `exemplo`.
- Novo lugar de gravação por cliente entra em `privacidade.locais()`.
- Campo novo de perfil que não ajuda a escrever e identifica alguém entra em `ia._FORA_DO_PROMPT`.
- Antes de vender para clientes de saúde, fazer o relatório de impacto (RIPD, Art. 38).
