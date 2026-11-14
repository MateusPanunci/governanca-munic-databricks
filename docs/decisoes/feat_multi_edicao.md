# Relatório de decisões e mudanças — branch `feat/multi-edicao`

> **Documento vivo (parcial)** — cobre TODO o trabalho da branch `feat/multi-edicao`, do primeiro commit `4dbb042` até o fechamento da funcionalidade (silver/gold multi-edição completas).
>
> Fontes: sessões de trabalho com o agente (com evidências verificadas), `git diff main..HEAD` + árvore de trabalho, e histórico da conversa do grupo.

## Contexto

Objetivo da branch: o pipeline MUNIC operar **por edição**, com 2019 e 2024 coexistindo em bronze/silver/gold e nos artefatos de qualidade `dq_*` — sem duplicar código nem reconfigurar nada por mão a cada ano.

---

## Commit `4dbb042`: multi-edição na ingestão

### Mudanças (3 arquivos)

* **`environment/env_variables`** — o mapa `munic_source_url_map` passa a carregar as edições **2019 e 2024** (2019 entra no lugar de 2022); novo `munic_file_paths`, **derivado das URLs** por comprehension (caminho da landing nunca é digitado manualmente); variáveis da edição corrente (`munic_source_url`, `munic_file_name`, `munic_file`) definidas a partir de `reference_year` e consumidas pelos notebooks do pipeline; nota md explicitando que só a ingestão usa `munic_file_paths` — o restante do pipeline seleciona tabela por `reference_year`.
* **`pipeline/ingest_to_landing`** — download e hash refatorados em funções: `download_file()` (idempotente — se o XLSX já existe na landing, ignora) e `get_file_sha256()` (SHA-256 do arquivo baixado como evidência de integridade por edição); prints de origem/destino desativados.
* **`pipeline/landing_to_bronze`** — adaptado para consumir as variáveis de edição do env em vez de configuração própria.

### Decisões (e alternativas descartadas)

* **Fonte única da verdade por edição**: a edição é definida uma única vez no mapa URL do env; adicionar uma edição nova = uma linha no mapa, e caminhos/variáveis derivam disso. Alternativa descartada: manter URLs/caminhos espalhados por notebook.
* **Download idempotente + SHA-256 por arquivo**: reexecutar a ingestão não baixa de novo e sempre evidencia o hash do insumo — auditoria da origem dos dados.

---

## Fundação da multi-edição (bronze + profiling)

### Mudanças

* **`environment/env_functions`** — `upsert_delta_table` refatorado em 6 passos nomeados (detectar tabelas/colunas → evolução de schema → deleção da edição → MERGE → estatísticas → histórico de commits), cada passo testável e auditável; funções de detecção automática de abas/colunas do XLSX (`detect_munic_sheets`, `detect_identity_renames`, tokens `ABAS_*`/`COLUNAS_IDENTIDADE`) movidas para cá.
* **`environment/env_variables`** — fica só com os **overrides opcionais por edição** (vazios no dia a dia); `reference_year` é o único ponto de controle da edição corrente.
* **`pipeline/landing_to_bronze`** — reestruturado: `reference_year` e detecção automática vêm do env (zero configuração por edição); célula `%pip install openpyxl`; **bloco 33 (populacao) removido** por redundância — o passo 5 do upsert já faz o null-fill.
* **`governance/bronze_quality_profiling`** — persistência multi-edição com `gravar_por_edicao` (coluna `ano_edicao` + `replaceWhere`: cada gravação troca só a edição corrente, preservando as anteriores; tabelas antigas sem a coluna são migradas uma única vez); CSVs de apoio com sufixo da edição.

### Decisões (e alternativas descartadas)

* **Detecção automática no env_functions** em vez de configuração hardcodada por edição — os overrides por edição existem apenas como escape opcional, vazios por padrão.
* **Remover o bloco populacao do landing_to_bronze** (era cópia redundante do null-fill do upsert) em vez de manter as duas vias.

### Execuções e evidência

* Bronze executada nas duas edições: 2024 (populacao sem nulls) e 2019 (5.570 linhas, todas null-fill corretamente pelo passo 5).
* **`bronze_to_silver` 2019 executado e RECUSADO pelo guard fail-fast de validação** — silver 2019 pendente de investigação (não é defeito do fluxo: o guard impediu a gravação de silver inválida).

---

## Item 2.1: drift do dicionário entre edições

### Mudanças

* Nova seção no `bronze_quality_profiling`: **`dq_dict_drift`** — divergência de significado dos códigos comuns entre edições, classificada por tipo (reescrita editorial, ano de referência embutido, reformulação parcial, suspeita de reutilização do código).
* Endurecimento da seção: lista de colunas fixada, fallback da edição B, ordenação determinística, dedup na classificação, labels em md e concatenação via StringBuilder.

### Evidência

* 86 códigos com significado divergente em 2019×2024 — aviso registrado a quem escreve a configuração do radar de uma edição.

---

## Profiling por edição, vereditos e LGPD

### Mudanças

* **Tradução 100% PT** do `bronze_quality_profiling` e reestruturação dos markdowns (funil de seleção, visão geral das etapas, esclarecimento de que o notebook é somente leitura sobre os dados e de que o funil **registra** não-descartes).
* **Renomeação dos vereditos**: `relacao_confirmada` → **`veredito_dados`** e `hipotese_confirmada` → **`verificacao_questionario`**; nova célula de verificação manual dos saltos lógicos contra o questionário.
* **Guarda LGPD por edição** (`lgpd_coletada`): quando a edição não coletou o bloco de LGPD (2019), as Figuras 1 e 2 são suprimidas com AVISO que lista dinamicamente as colunas vazias; mensagens de supressão genéricas (sem comportamento hardcodado de edição). Em 2024, tudo plota normalmente.
* **Fallback dos widgets fora do Databricks**: `VALORES_PADRAO` mutáveis no código + `try/except NameError` em `dbutils` — padrão seguro (`persistir_tabelas: "nao"`).

### Decisões (e alternativas descartadas)
* **Suprimir as figuras com AVISO explícito** em vez de plotar vazias/quebradas quando o bloco LGPD não existe na edição.
* **Lógica edition-robusta e genérica** (guards dinâmicos) em vez de exceções hardcodadas para 2019/2024.

### Execuções e evidência

* Profiling 2019: 30/30 células success, AVISO com as colunas vazias listadas dinamicamente, figuras suprimidas.
* Profiling 2024: 30/30 células, figuras plotadas, viés real restaurado — taxa de "Sim" sobe com o porte (19,8% na faixa 1 → 85,42% na faixa 7), não-resposta no bloco cai (13,22% → 2,5%); as 7 faixas somam 5.570 municípios.
* Estado final das dq_*: `dq_column_profile` 406 (2019) + 406 (2024); `dq_skiplogic_candidates` 124 + 171; `dq_dimension_summary` 6+6; `dq_nonresponse_by_size` 7+7; `dq_dict_drift` 86.

---

## Dependência dq_* → gold corrigida e gold 2024 revalidada

### Problema

O `silver_to_gold` construía a `dim_indicador` **direto** de `dq_column_profile` e `dq_skiplogic_candidates`, lendo as tabelas **sem filtro de `ano_edicao`**. Com as dq_* acumulando duas edições, cada variável viria duplicada no JOIN e o MERGE do `upsert` falharia por chave duplicada — a gold estava quebrada **mesmo** com `persistir_tabelas = "sim"`. Além disso, num workspace novo, a ausência das dq_* dava erro críptico de tabela inexistente.

### Mudanças

* **`pipeline/silver_to_gold`** (célula dim_indicador): guard de pré-requisito `_exigir_dq_da_edicao` (aborta com instrução clara — "rode o bronze_quality_profiling com `persistir_tabelas='sim'` para a edição X" — se a dq_* não existir ou não tiver linhas da edição corrente) + filtros `ano_edicao == reference_year` nas leituras de `profile_df` e `skiplogic_raw`.
* **Documentação da dependência**: markdowns de abertura e Persistência do profiling + decisão 3 da seção 1 do `docs/arquitetura/gold_dimensional_model.md` (incluindo correção da linha de linhagem do `grupo_pergunta`).

### Decisões (e alternativas descartadas)
* **Manter o widget `persistir_tabelas` com padrão "nao"** (alternativas descartadas: fixar sempre "sim" ou excluir a opção) — preserva a execução read-only sem permissão de escrita, prometida na célula Persistência; a dependência da gold foi resolvida com **documentação + guard instrutiva**, que transforma o erro críptico numa instrução, em vez de remover flexibilidade.
* **Filtrar por edição na origem da leitura** em vez de deduplicar no MERGE — resolve a causa (ambiguidade de edição) e não o sintoma.
* **Abortar quando a edição não está perfilada** em vez de cair silenciosamente na evidência de outra edição.

### Execuções e evidência

* Guard testada nos três ramos (tabela inexistente, edição ausente, caminho feliz).
* Run read-only do profiling com `persistir_tabelas = "nao"`: 30/30 células, "nada foi gravado", SQL confirmou todas as dq_* **idênticas** ao snapshot (nenhuma escrita).
* **Gold 2024 reconstruída e validada**: 11/11 células; guard aprovou 406 (profile) e 171 (skiplogic) linhas de 2024; 133 pais de salto confirmados; **Step 9: 20 controles, todos PASS** (incluindo dim_indicador 360=360); checagem SQL independente: 360 linhas, 360 variáveis distintas, 0 chaves duplicadas.

---

## Decisões de processo (não-técnicas)

* **Relatório de decisões por branch no fechamento** (este arquivo) em vez de CHANGELOG incremental por commit — decisão do grupo, priorizando baixo atrito; commit messages decentes continuam como registro atômico.
* Fluxo de trabalho: o agente registra sessões na memória interna automaticamente; o relatório final será gerado cruzando memória + `git diff main..HEAD` + histórico da conversa.
* **Ledger do pipeline** (desenhado como decisão de processo, implementado na seção seguinte): tabela `pipeline_manifest` — uma linha por etapa×edição com o contrato de execução (linhas, indicadores com dados, recusa, SHA-256), substituindo os fail-fasts hardcoded do bronze_to_silver (que estouram para 2019 e até para re-runs de 2024 no schema união: 403 colunas vs. 360 esperadas) e padronizando as guards de fronteira com as funções de verificação `check_igual`/`contrato_da_edicao` (família do contrato). Desenho completo em `docs/arquitetura/pipeline_manifest.md` (renomeado de `pipeline_ledger.md` — doc nomeado pela tabela que documenta). Correção irmã: `userMetadata` não chega nos MERGEs do upsert (histórico mostra None) — setar `spark.databricks.delta.commitInfo.userMetadata` no passo 6.

---

## Ledger pipeline_manifest implementado (desenho, itens 1 a 4)

### Mudanças (7 arquivos)

* **env_functions** - funções do ledger: `gravar_linha_manifest` (MERGE na chave etapa+ano_edicao; cria a tabela na primeira gravação; `detalhes` como MAP), `contrato_da_edicao` (aborta com instrução quando ausente e confere as tabelas físicas declaradas - DROP manual = contrato desmentido), `check_igual` + `resumo_validacoes` (fail-fast acumulado que estoura em bloco - padrão do Step 9 da gold). Correção irmã no passo 6 do upsert e no ledger: userMetadata via conf de sessão pelo helper `_set_user_metadata`.
* **env_variables** - `manifest_tbl = munic_catalog.gold.pipeline_manifest`.

* **ingest_to_landing** - %run do env_functions; `get_file_sha256` retorna o hash; o loop por edição declara a linha `landing` (SHA-256 real + detalhes: arquivo, tamanho_mb, url_origem, baixado_em, ja_existia). Aviso de divergência: se o SHA calculado difere do último declarado no ledger (arquivo excluído e baixado de novo com outro conteúdo, origem alterada no IBGE ou arquivo substituído), imprime AVISO com os dois hashes e grava `detalhes.sha_anterior_divergente` - a linha landing nunca é atualizada em silêncio. Verificado nos dois ramos: SHA idêntico (sem aviso, atualização normal) e SHA divergente (AVISO + sha_anterior_divergente no MAP). baixado_em corrigido: agora é o momento em que o arquivo chegou ao volume - now() se o run baixou, mtime do arquivo se já existia (nunca um agora fabricado para arquivo que não baixamos). Ambos documentados no desenho (nova seção 5.6). Refatoração em função: a declaração da landing saiu do loop da ingestão para gravar_linha_landing (env_functions, junto da família do ledger - mesmo padrão das funções de detecção do XLSX); get_file_sha256 e o import hashlib foram removidos do notebook (dobra de lógica) e a célula 7 ficou só com o loop download + declaração. Testado nos dois ramos após a refatoração.
* **landing_to_bronze** - linha `bronze` com linhas/indicadores-com-dados/recusa_total medidos após o upsert, SHA-256 refeito do XLSX (elo de linhagem) e detalhes (info_com_dados, gov_com_dados, dict_linhas, schema_uniao).
* **bronze_to_silver** - asserts hardcoded (360/5570/2520) substituídos por `check_igual` contra o contrato da bronze (Step 5, fail-fast e Step 8); fail-fast movido para ANTES da migração de schema (run reprovado morre sem deixar a silver meio-migrada); descarte das colunas 100% nulas da edição (silver por edição: 360 em 2024, 307 em 2019 - resolve os 403 vs. 360 do schema união); linha `silver` declarada após o Step 8; célula de debug e fail-fast antigo removidas.

* **silver_to_gold** - Step 1 valida contra o contrato silver/edição (indicadores com dados, municípios) e despivotiza só as colunas com dados da edição; linha `gold` declarada após o Step 9, fechando o invariante da recusa (bronze até gold) e reportando checks_pass/fact_linhas/âncoras/radar em detalhes.
* **bronze_quality_profiling** - %run do env_functions; linha `profiling` quando persistir_tabelas=sim (contrato = indicadores com dados; universo perfilado, saltos, drift, faixas e LGPD em detalhes).

### Refatoração: verificação e declaração separadas (landing)

* `verificar_arquivo_landing` (env_functions): calcula o SHA-256 do arquivo, avisa divergência contra o último declarado e monta `baixado_em` honesto + `detalhes`; retorna `(sha256_xlsx, detalhes)` — não grava nada.
* `gravar_linha_manifest` segue como único ponto de gravação: a ingestão chama `verificar_arquivo_landing` e depois `gravar_linha_manifest(etapa="landing", ...)`, no mesmo padrão de declaração das demais etapas.
* Substitui a `gravar_linha_landing` (que gravava internamente), eliminando a impressão de que existiria uma função `gravar_linha_*` por etapa.
* Nome `verificar_*` (não `validar_*`): no projeto, `validar_*` estoura quando reprova (ex.: `resumo_validacoes`); a divergência de SHA é AVISO, não aborto — o nome reflete isso.
* Alternativa descartada: `if etapa == "landing"` dentro do `gravar_linha_manifest` — esconderia leitura de arquivo do disco dentro do gravador genérico e abriria precedente para um ramo por etapa, a sopa de flags em versão introvertida.
* Validado com execução de ponta a ponta do ingest_to_landing (serverless): downloads ignorados, sem AVISO de divergência, linhas landing 2019/2024 atualizadas com `baixado_em` do mtime real.

### Organização do output da ingestão

* Cabeçalho por edição no loop da ingestão (separador `---` + `Edição {year}`) abrindo cada bloco: download → verificação → linha do ledger.
* O print da verificação mostra também o caminho do arquivo no volume (`Volume : ...`).
* `gravar_linha_manifest` suprime as ~2 linhas em branco que o commit do MERGE da Delta emite no stdout em compute serverless: o MERGE executa com o stdout capturado e só as linhas com conteúdo são reimpressas — o espaçamento entre blocos de edição fica de exatamente uma linha em branco.
* Cabeçalho mantido no loop (não dentro do `download_file`): o rótulo `Edição {year}` é um conceito da iteração, não do download — a função utilitária não recebe o ano e imprimiria cabeçalhos indevidos em chamadas fora do loop.

### Descoberta em execução (userMetadata)

Em compute serverless, a conf `spark.databricks.delta.commitInfo.userMetadata` é CONFIG_NOT_AVAILABLE (SQLSTATE 42K0I) - nem spark.conf.set nem SET SQL funcionam; o userMetadata do MERGE só chega ao histórico em clusters clássicos. O helper tenta setar, avisa UMA vez e segue sem interromper; nesses MERGEs a trilha fica com operation/timestamp do DESCRIBE HISTORY, e a auditoria declarativa (quem, o quê, a partir de qual SHA-256) é papel do ledger. Documentado no desenho (seção 6).

### Evidência (execução real, testes de unidade do ledger)

* Linhas `landing` de 2024 e 2019 gravadas com SHA-256 real dos XLSX da landing; tabela nasce no primeiro gravar_linha_manifest.
* MERGE idempotente: 2 regravações da mesma chave mantêm 1 linha (chave etapa+ano_edicao, sem duplicação).
* Ramos da guard: contrato ausente gera instrução (rodar a etapa primeiro); tabela declarada inexistente gera contrato desmentido; check_igual acumula FAILs e resumo_validacoes estoura com todas de uma vez, citando o contexto dos detalhes.

---

## Refatoração: env_functions em módulos + funções de medição do shape

### Mudanças

* **`environment/modulos/` (novo)** — o env_functions deixa de ser monólito e vira hub; três módulos self-contained (imports e documentação próprios), cada um documentando seu próprio fluxo:
  * `modulos/deteccao` — detecção automática de abas e colunas de identidade (`detect_munic_sheets`, `detect_identity_renames`, marcadores `ABAS_TOKENS`/`COLUNAS_IDENTIDADE`);
  * `modulos/upsert` — `upsert_delta_table` e os 6 passos auxiliares (incluindo `_set_user_metadata`);
  * `modulos/ledger` — família do contrato (`gravar_linha_manifest`, `contrato_da_edicao`, `check_igual`, `resumo_validacoes`, `verificar_arquivo_landing`) + as novas utilidades de medição do shape.
* **`environment/env_functions`** — agora é só índice + 3 `%run` (`./modulos/deteccao` → `./modulos/upsert` → `./modulos/ledger`); o contrato dos consumidores não muda (`%run ../environment/env_functions` continua válido). A ordem importa: o ledger chama `_set_user_metadata` (definido no upsert) apenas em tempo de chamada.
* **Funções de medição promovidas para `modulos/ledger`** — `colunas_com_dados(df, cols)` e `celulas_recusa(df, cols)`: o padrão `.agg` + `isNotNull().cast("int")` / reduce de `'Recusa'` que se repetia em 4 lugares agora vive uma única vez:
  * `landing_to_bronze` (célula do ledger da bronze) — removeu as versões locais `_colunas_com_dados`/`_celulas_recusa`;
  * `bronze_to_silver` — fail-fast pré-migração (o `com_dados` local virou `set(colunas_com_dados(...))` para derivar as colunas 100% nulas) e Step 8 pós-gravação;
  * `silver_to_gold` — Step 1 (fronteira silver→gold).
* **Terminologia "estoura"** — deprecada em código: comentários e docstrings agora dizem "interrompe o run (fail-fast)" / "interrompem juntas" (chamadas de `resumo_validacoes` no silver_to_gold e bronze_to_silver, docstrings de `check_igual`/`resumo_validacoes` no ledger).

### Decisões (e alternativas descartadas)

* **Módulos carregados por `%run` a partir do hub** (alternativas descartadas: módulo único grande — mesmo problema do monólito; wheel/pacote Python — infraestrutura desnecessária para o porte do projeto).
* **`colunas_com_dados`/`celulas_recusa` no módulo ledger**, não em módulo próprio — são utilidades de MEDIÇÃO dos valores do contrato (campo `indicadores` = shape com dados; campo `recusa_total`), usadas tanto por quem declara (bronze) quanto por quem valida (silver/gold); módulo separado seria granularidade prematura, e inline a duplicação já era 4×.
* **O hub não guarda código** — é o ponto de entrada estável para os consumidores: reorganizações internas de `modulos/` não propagam para os notebooks do pipeline.

### Evidência

* Corpos das funções promovidas executados contra a silver 2024 real (leitura, sessão de validação): 360 indicadores com dados, 2.520 células 'Recusa', 5.570 linhas — exatamente os números do contrato declarado pela silver; assert de confirmação passou.
* Estrutura do hub verificada: 4 células (índice md + 3 `%run`).
* O carregamento de ponta a ponta do hub nos notebooks consumidores (células `%run` re-executadas) não foi executado nesta sessão — fica como primeira verificação do re-run do zero (pendência).

### Comentários-banner → markdown (varredura geral)

* Busca por `# ===` em todo o repo: os banners existiam apenas nos 3 módulos novos e na landing_to_bronze (célula do ledger da bronze) — bronze_to_silver, silver_to_gold, bronze_quality_profiling, env_variables e ingest_to_landing já estavam limpos.
* Banners de topo viraram células markdown acima de cada bloco: visão geral por módulo (deteccao: problema + fluxo de 3 passos + uso; upsert: assinatura + 6 passos + por que merge_keys incluem ano_edicao + auditoria; ledger: blocos do módulo + papéis do desenho) e uma md por bloco do ledger (família do contrato, medição do shape, verificação da landing).
* Correção embutida: as células md de visão geral dos módulos tinham sido criadas vazias (o conteúdo do md não chegou a ir no payload da criação) — preenchidas nesta varredura.
* No modulos/upsert, os separadores de 3 linhas dos PASSO 1–6 foram comprimidos para comentários de 1 linha (`# ---- PASSO N — título ----`); na landing_to_bronze, o banner do ledger da bronze virou a md "Ledger (pipeline_manifest): a bronze declara o contrato".
* Convenção de estilo estabelecida: docstrings seguem nas funções (documentação de API); comentários no código apenas curtos e pontuais; documentação de bloco/seção vive em células markdown.
* Evidência: as 5 células de código dos módulos re-executadas após a limpeza — todas success (definem funções, sem efeitos colaterais).

### Nomenclatura: rename check_igual + convenções no hub

* `validar_igual` → **`check_igual`** (pergunta em review: nome genérico, confuso nos call sites). O novo nome descreve o que a função faz — REGISTRA um check PASS/FAIL (obtido vs. esperado do contrato) e não interrompe — e devolve o verbo `validar_*` ao seu papel no projeto (interromper quando reprova; quem interrompe é o `resumo_validacoes`). Docstring reescrita explicando obtido/esperado/contexto. Rename aplicado em modulos/ledger (def + mds de visão geral e família), bronze_to_silver (Step 5, fail-fast, Step 8, header md), silver_to_gold (Step 1) e no índice do hub.
* Prefixo `_` mantido nas auxiliares do upsert (pergunta em review: não seria `aux`?): é a convenção Python de função interna de módulo — diz “não faz parte da API”, enquanto `aux` não diz nada sobre o que a função faz. API pública × interna e a taxonomia de verbos (`gravar_*`, `contrato_*`, `check_*`, `resumo_*`, `verificar_*`, `detect_*`) documentadas em nova md “Convenções de nomenclatura” no hub env_functions.

---

## Pendências da branch

* **Silver 2019**: investigar o fail-fast que recusou o bronze_to_silver (provável causa: dicionário 2019 - 307 linhas - não cobre colunas de identidade renomeadas em relação a 2024). Com o ledger, o mesmo teste agora valida contra o contrato da bronze - reexecutar para confirmar.
* **Re-run do zero do pipeline (destrutivo: apaga as 14 tabelas)** para popular o ledger de ponta a ponta e validar as fronteiras bronze-silver-gold com os números reais (5570/360/2520 em 2024) - aguarda confirmação do usuário.
* Gold 2019 (após silver) e camada semantic por edição.
* Re-run read-only do profiling 2024 para atualizar os outputs do notebook (hoje exibindo 2019 - cosmético; o mecanismo já foi verificado).
* **Varredura de "estoura" no `bronze_quality_profiling`** — último notebook com o termo em comentários/docstrings; substituir por "interrompe o run (fail-fast)" (mesma deprecicação aplicada nos demais).
* Flowchart do modelo gold adicionado pelo usuário ao profiling - avaliar mudança para o silver_to_gold.
* reference_year está em 2024 - religar para 2019 ao retomar a Etapa 4 (silver/gold 2019).

## Commits da branch

| Hash | Mensagem |
| --- | --- |
| `4dbb042` | feat: multi-edição em ingest_to_landing |
| `ae8da3b` | feat: multi-edição no landing_to_bronze e dq_* por edição no bronze_quality_profiling |
| `bfc942e` | docs: relatório de decisões da branch feat/multi-edicao |
| `d553edc` | docs: desenho da tabela pipeline_manifest (contrato de execução por etapa e edição) |
| `17da9b5` | feat: ledger pipeline_manifest — contrato por edição nas fronteiras das etapas |
| (pendente) | refactor: env_functions em módulos (deteccao/upsert/ledger) + check_igual |