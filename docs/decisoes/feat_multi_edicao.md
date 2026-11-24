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
* **`pipeline/bronze_quality_profiling`** — persistência multi-edição com `gravar_por_edicao` (coluna `ano_edicao` + `replaceWhere`: cada gravação troca só a edição corrente, preservando as anteriores; tabela legada sem a coluna interrompe com instrução de drop — o ramo de migração automática foi removido); CSVs de apoio com sufixo da edição.

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
* **`modulos/upsert` — prints reorganizados** (padrão do `gravar_linha_manifest`): cada chamada abre o bloco `Upsert : <tabela> — edição <ano>`; cada passo que agiu soma uma linha alinhada — `Criada :`, `Ordem  :` (reordenação), `Schema :` (+N colunas, lista truncada em 6) e `Null   :` (contagem em vez da lista gigante de colunas de outras edições) — e o MERGE fecha com as métricas do próprio commit (`MERGE  : N atualizada(s), M inserida(s)`, lidas de `history(1)` → `operationMetrics`, com fallback de chave), com o stdout capturado/reimpresso sem as ~2 linhas em branco do commit em serverless. Validado: célula do módulo re-executada (defs) + leitura das métricas contra MERGEs reais da silver (v11: 5.570 atualizadas / 0 inseridas; operações não-MERGE degradam para `?`).
* **Terminologia "estoura"** — deprecada em código: comentários e docstrings agora dizem "interrompe o run (fail-fast)" / "interrompem juntas" (chamadas de `resumo_validacoes` no silver_to_gold e bronze_to_silver, docstrings de `check_igual`/`resumo_validacoes` no ledger).

### Decisões (e alternativas descartadas)

* **Módulos carregados por `%run` a partir do hub** (alternativas descartadas: módulo único grande — mesmo problema do monólito; wheel/pacote Python — infraestrutura desnecessária para o porte do projeto).
* **`colunas_com_dados`/`celulas_recusa` no módulo ledger**, não em módulo próprio — são utilidades de MEDIÇÃO dos valores do contrato (campo `indicadores` = shape com dados; campo `recusa_total`), usadas tanto por quem declara (bronze) quanto por quem valida (silver/gold); módulo separado seria granularidade prematura, e inline a duplicação já era 4×.
* **O hub não guarda código** — é o ponto de entrada estável para os consumidores: reorganizações internas de `modulos/` não propagam para os notebooks do pipeline.

### Evidência

* Corpos das funções promovidas executados contra a silver 2024 real (leitura, sessão de validação): 360 indicadores com dados, 2.520 células 'Recusa', 5.570 linhas — exatamente os números do contrato declarado pela silver; assert de confirmação passou.
* Estrutura do hub verificada: 4 células (índice md + 3 `%run`).
* O carregamento de ponta a ponta do hub nos notebooks consumidores (células `%run` re-executadas) não foi executado naquela sessão — verificado no re-run do zero (todas as execuções seguintes carregaram o hub via %run).

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
* **Critério de promoção notebook→módulo** (pergunta em review: `extract_var_code_meaning`/`obtain_filled_cells` ficam no landing_to_bronze ou vão para módulo?): função de notebook fica **local** enquanto tiver um único consumidor — como `extract_var_code_meaning`/`obtain_filled_cells`, `prepare_data_to_delta_format` e `add_ingestion_metadata` (landing_to_bronze). Promove para `modulos/` (via hub) só quando aparece um **segundo consumidor** ou se forma uma **família** do mesmo tema. Registrado na mesma md de convenções do hub.
* **Assert do tratamento → check do lote + comentários de uma linha nos checks** (pergunta em review): o assert de StringType do Step 3 (MTIC) virou `check_igual` ("tratamento MTIC: indicadores em StringType"), com o simétrico criado para o MGOV — acumulam no lote e fecham no fail-fast pré-gravação, em vez de interromper sozinho (o MGOV nem tinha o assert). Banner da `treat_survey_indicators` reescrito: deixa claro que trata DataFrame lido da bronze (bloco mtic/mgov), não o XLSX. O comentário do fail-fast (Step 5/29) ficou enxuto, com uma linha por sub-bloco; e **toda chamada de check_igual** ganhou um comentário de uma linha dizendo o que compara (bronze_to_silver Steps 3/5/7/8 e silver_to_gold Step 1 — o Step 9 da gold usa checks locais já auto-descritivos). Docstring do `resumo_validacoes` esclarece: interrompe o run INTEIRO (nada depois da célula executa) e NÃO desfaz escritas já commitadas (MERGE Delta sem rollback — por isso o padrão do projeto é fechar o lote antes da primeira escrita); mesma clarificação na linha `resumo_*` da md de convenções do hub. Validado re-executando: fail-fast 7/7 checks PASS (lote agora inclui os 2 do tratamento), Step 8 4/4, silver_to_gold Step 1 2/2.

### Inspeção de tabelas → pasta exploration

* Convenção: notebook de pipeline carrega só células de produção; inspeção de tabela **persistida** (DESCRIBE HISTORY, leituras de conferência) mora na pasta `exploration/`. O critério é a dependência — tabela gravada no catálogo lê de qualquer sessão; DataFrame intermediário não gravado só existe na sessão do notebook que o construiu (inspeção dele continua lá).
* Células 37–39 do bronze_to_silver (header md "Histórico das tabelas silver" + dois `DESCRIBE HISTORY` das tabelas silver) movidas para o novo notebook de acompanhamento em `exploration/` (nomeado `tables_vizualization` pelo usuário, depois renomeado para `tables_overview`): `%run` do env_variables, nomes de todas as tabelas do pipeline, shape por `ano_edicao` em todas as camadas, linha de cada etapa × edição no `pipeline_manifest` e, por tabela principal de cada camada, o par `SELECT *` + `DESCRIBE HISTORY`. Validado executando — e o primeiro run de acompanhamento já expôs o estado atual: bronze carrega as duas edições (info/gov 5.570 cada, dict 307/358), silver e gold só 2024, e o manifest só tem as linhas `landing` (estado anterior ao re-run do zero, executado depois — seção “Re-run do zero”).

---

## Re-run do zero do pipeline (ingestão → silver)

### Escopo e método

* Executado após confirmação explícita do usuário. **Destrutivo**: DROP das 15 tabelas (bronze 3, silver 2, gold 10 — pipeline_manifest e dq_* incluídas), verificado 0 tabelas restantes antes de reexecutar. Os XLSX da landing (volume) foram mantidos — a ingestão é idempotente e recalcula o SHA-256.
* Ordem de execução: ingest_to_landing (duas edições) → landing_to_bronze 2024 → landing_to_bronze 2019 (toggle de `reference_year` no env) → bronze_to_silver 2024 → bronze_to_silver 2019 (confirmação da pendência da silver 2019) → `reference_year` restaurado para 2024.
* Verificação final independente por SQL (contagens por edição nas 6 tabelas + linhas do manifest), distinta dos checks dos próprios notebooks.

### Evidência

* Ingestão: downloads ignorados (idempotência), manifest recriado na primeira gravação (“Criada”), linhas landing 2019/2024 com os SHA-256 reais.
* Bronze 2024: tabelas criadas; contrato 5.570/360/2.520 (SQL independente confirmou 5.570 em info e gov; dict 358).
* Bronze 2019: renomes de identidade detectados automaticamente (`codmun→cod_munic`, `nome_munic→desc_mun`, `classe_pop→faixa_populacao`); MERGE +5.570 linhas por tabela com evolução de schema (+23/+20 colunas da edição); dict 307; contrato 5.570/307/610.
* Silver 2024: fail-fast 7/7 (43 colunas 100% nulas de outras edições descartadas), migração desnecessária (tabela nova), pós-gravação 4/4, linha silver/2024.
* **Silver 2019: PASSOU** — pendência histórica resolvida. Fail-fast 7/7 contra o contrato bronze 2019 (307 indicadores, 610 recusas; 96 colunas 100% nulas descartadas), MERGE +5.570 linhas (+43 colunas da edição), pós-gravação 4/4, linha silver/2019. O guard antigo recusava por números hardcoded (360/2520) que não valem para 2019; validado por contrato, o mesmo fluxo passa para qualquer edição — a suspeita do dicionário 2019 era procedente para o guard hardcoded, não para o validado por contrato.
* Estado final verificado (SQL): bronze info/gov 5.570 por edição (dict 307/358), silver data 5.570 por edição (dict 307/358), manifest com 6 linhas (landing×2, bronze×2, silver×2). `reference_year` de volta a 2024. Gold e dq_* permanecem ausentes (fora do escopo deste re-run — reconstrução é pendência).

---

## Reconstrução das dq_* e profiling no `pipeline/`

### Mudanças

* **`governance/bronze_quality_profiling` → `pipeline/bronze_quality_profiling`** — o notebook é etapa de fato do pipeline (produz as `dq_*`, insumo da gold, e integra a definição de "rodar o pipeline todo"). Pasta `governance/` removida (continha só ele). Referências ao caminho antigo corrigidas: guard `_exigir_dq_da_edicao` do silver_to_gold (2 mensagens de erro), README.md (diagrama, árvore — profiling listado em `pipeline/` na ordem de execução — e tabela de entregáveis) e este relatório. Os `%runs` (`../environment/...`) seguem válidos (mesma profundidade relativa). Nota: docs `.md` não são indexados pela busca de código — a varredura de caminhos usou grep direto.
* **dq_* reconstruídas nas duas edições** (2024 executada pelo agente, 2019 pelo usuário; `persistir_tabelas="sim"`): `dq_column_profile` 403+403, `dq_skiplogic_candidates` 171 (133 sim/38 parcial) + 124 (116 sim/8 parcial), `dq_dimension_summary` 6+6, `dq_nonresponse_by_size` 7+7, `dq_dict_drift` 86 (regravada — compara as edições entre si); manifest com 8 linhas (landing/bronze/silver/profiling ×2). Os 403 por edição (antes 406) refletem a bronze recriada sem as 3 colunas legadas.
* **Ramo morto removido do `gravar_por_edicao`** (célula 43 do profiling): a migração destrutiva (`overwrite`+`overwriteSchema`) de tabelas dq_* legadas sem `ano_edicao` virou `RuntimeError` com instrução de drop e re-executar. Pós re-run do zero nenhuma dq_* pode nascer legada — o código morto disparava bloqueios da camada de aprovação nas execuções via agente. Smoke test: célula re-executada isolada — "Gravada (edição 2019)" idempotente via `replaceWhere`, ledger ok.
* **Ramo morto equivalente removido do `modulos/upsert` (PASSO 3a)**: `_migrar_para_particionada` (regravação `overwrite` de tabelas legado com `reference_year`) substituída por fail-fast com instrução de drop; o PASSO 3 agora é só `_reordenar_para_padrao`. Docstring e md do módulo atualizados (sem `Migrada:` na lista de prints). **Validado com tabela temporária**: criação particionada (PASSO 2), MERGE idempotente (3b + 6) e o fail-fast do legado (3a) — todos conforme esperado; tabelas de teste removidas ao final.
* **Padrão do widget `persistir_tabelas` mudou de "nao" para "sim"** (decisão do usuário, 13/11) — supersede a decisão registrada na seção "Dependência dq_* → gold": o profiling integra o "rodar o pipeline todo" (que sempre grava as dq_*); a alternativa read-only continua disponível no dropdown.

### Decisões (e alternativas descartadas)

* **Migração legada vira fail-fast com instrução** (em vez de removida em silêncio ou mantida): pós re-run do zero o ramo nunca disparava — código `overwrite` morto era apenas fonte de bloqueio da camada de aprovação e ruído de leitura. O fail-fast preserva a sinalização de tabela legada sem comportamento destrutivo.
* **`gravar()` da `dq_dict_drift` mantém `overwrite`** — por design: tabela ENTRE edições, regravada inteira a cada execução (não é ramo morto).

---

## Parametrização da gold multi-edição (Step 6 + QC do Step 9)

> Mudanças pós-`aff8eed` no `pipeline/silver_to_gold`, validadas na edição 2024 e **ainda não commitadas**. Preparam a gold para rodar por edição; a decisão pendente da célula 19 está no fim da seção.

### Mudanças

* **Step 9 — QC (Seção 6), agora 21 checks**: todos os esperados passam a ser derivados da edição corrente, sem literal de 2024 — nº de variáveis e temas TIC/GOV das colunas com dados (`indicator_cols`); âncoras, regras e peso por dimensão do radar (Step 3) ∩ colunas com dados; linhas da fact = municípios × indicadores; Recusa contra o contrato da silver no ledger; classes fecham o total (a distribuição exata das classes saiu — passa a ser consequência da edição); IMDM NULL = municípios com Recusa (medido na própria fact); peso máximo por dimensão = nº de itens da edição. Checks condicionais à presença na edição: `mtic30`, `mgov05`, `mgov15`/`mgov16`; a verificação das 7 reconstruídas passou a testar apenas as presentes (antes, numa edição sem elas, a lista vazia dava falso PASS).
* **Ledger da gold**: `detalhes.ancoras` = âncoras com peso na edição; `detalhes.radar_itens` = itens do radar presentes na edição (mapa ∩ colunas com dados).
* **Step 6 — pontuação por item**: cada item (6 formatos, escada, 2 grupos, 3 escalonados, `mgov05`) só é construído se TODAS as suas variáveis têm dados na edição — item sem dados sai do denominador (elimina o 0.0 com peso que penalizava o município por pergunta que não existiu no ano); total esperado de âncoras de item derivado do radar ∩ edição (assert sem o literal 13); AVISO de rótulo fora do mapa nos escalonados e AVISO quando `mgov04` não tem dados (exceção do `mgov05` não avaliável).
* **Radar explícito nos escalonados**: valores de "ausência" do questionário 2024 entraram no mapa com 0.0 explícito — `mtic10` ('Em elaboração', 'Não possui página'), `mgov09` ('Não'), `mtic29` ('Não há qualquer modelo de acessibilidade digital') — antes pontuavam 0.0 silenciosamente pelo `otherwise` da regra.

### Decisão (e alternativa descartada)

* **Radar 2024 como definição estrutural única**: dimensões, âncoras e regras valem para toda edição; a presença por edição deriva das colunas com dados (mesmo princípio do contrato do ledger). A renormalização por edição (se houver) é decisão do dono do radar, não do código.
* **Descartado**: mapa/radar por edição no código — duplicaria a configuração e viraria a "sopa de flags" que o desenho evita; a derivação por presença cobre o caso sem perda.

### Evidência (edição 2024, pós-mudança)

* QC 21/21 PASS com os esperados derivados — os mesmos números do run anterior, agora calculados em vez de escritos à mão.
* Step 6: 13/13 âncoras de item, 0 itens pulados, 0 avisos.
* Prova independente: `item_scores` recomputado comparado à `fact_resposta` 2024 persistida — soma de pontos e nº de linhas idênticos nas 13 âncoras (diff 0.0; 5.570 linhas cada). A gold 2024 fica inalterada.

### Cenário 2019 hoje (rodar `reference_year=2019` sem mexer na célula 19) — verificado por leitura da silver 2019

* Cobertura real: 307 indicadores com dados; **D5/LGPD não coletada** (`mgov32`/`mgov34`/`mgov35`/`mgov36` com 0 células não-nulas); Recusa medida nas 360 colunas do schema união: 524 células em **2 municípios**.
* O pipeline executa até a célula 19 **e grava** dim_municipio/dim_indicador/fact_resposta/fact_imdm 2019 (MERGE por chave; o QC da gold fecha DEPOIS das escritas — não desfaz). A `fact_imdm` 2019 nasce com **IMDM NULL para TODOS os municípios**: a soma das 5 dimensões inclui `score_d5` NULL.
* O QC reprova e interrompe o run: "IMDM NULL = municípios com Recusa" (5570 vs 2) e "municípios válidos" (0 vs 5568) FAIL; o check "scores dentro de [0, 100]" em seguida estoura com 0 linhas válidas (min/max = None) — a linha `gold` do ledger NÃO é gravada. Recuperação por re-run após a decisão (MERGE idempotente por chave).
* **Rótulos divergentes 2019 já identificados** (os AVISOs do Step 6 listam ao rodar): `mgov09` — 2019 usa 'Sim, **por** instrumento legal' vs 2024 'Sim, **instituída por** instrumento legal' (é o nível pleno — sem mapeamento pontuaria 0.0 silencioso); `mtic29` — 2019 'Modelo global acessibilidade digital (WCAG/WAI)' vs 2024 'Modelo global **de** acessibilidade digital (WCAG/WAI)'. `mtic10` já bate 100% com o mapa explícito.

### DECISÃO PENDENTE (dono do radar multi-ano): IMDM em edição com dimensão ausente (célula 19)

* **Opção A — média das dimensões presentes (sugerida)**: IMDM = soma dos scores não-nulos ÷ nº de dimensões pontuadas do município. Mesma filosofia do denominador efetivo já usada no nível de item/dimensão; penalizar por dimensão que o IBGE não perguntou mede o questionário, não o município. Sem impacto em 2024 (todo município válido tem as 5 dimensões pontuadas — validável por diff contra a tabela persistida).
* **Opção B — manter a média das 5**: IMDM NULL quando falta dimensão. Preserva a definição estrita; entrega 2019 sem índice global (apenas scores por dimensão).
* **Comparabilidade cross-edição (vale para qualquer opção)**: IMDM 2019 (média de 4) e 2024 (média de 5) não são estritamente comparáveis — comparação entre edições deve usar o score por dimensão ou uma renormalização definida no radar multi-ano. Acompanhar com: registro das dimensões participantes por edição no ledger (`detalhes.dimensoes_edicao`) e proteção do check [0, 100] para o caso de 0 linhas válidas.

---

## Job no bundle DAB + orquestrador multi-edicao (fechamento da branch)

### Mudanças

* **Job como código no Declarative Automation Bundle** — `databricks.yml` + `resources/job_munic_pipeline.yml` definem o `job_munic_pipeline` (5 tasks, DAG, parâmetro `reference_year`, `max_concurrent_runs: 1`, queue); o espelho manual `jobs/` (JSON + script de export) foi removido. O job implantado fica UI_LOCKED: mudanças nascem no repo e propagam por `bundle deploy`. Regras de quando deployar (notebooks e YAMLs exigem; commit/run/docs não) em `resources/README.md`.
* **Novo orquestrador `job_munic_full_refresh`** (`resources/job_munic_full_refresh.yml`) — roda o pipeline COMPLETO para cada edição registrada, em sequência: a task `list_editions` (novo notebook `pipeline/list_editions`) importa o `env_variables`, extrai as **chaves** de `munic_source_url_map` e publica como task value `years`; o `for_each` (`concurrency: 1`) dispara um run do pipeline por ano via `run_job_task` com o `reference_year` da iteração. **Sem lista manual de anos em lugar nenhum** — a fonte da verdade continua sendo o mapa (adicionar edição = 1 linha + deploy; o orquestrador detecta sozinho).
* **Widget `reference_year` do `env_variables` materializado no próprio notebook** — widgets só nascem quando a célula que os cria roda NO notebook; via `%run`, nascem no chamador. Nota registrada na própria célula; default 2024 preservado (edição-base do projeto).
* **Documentação** — `resources/README.md` reescrito com a operação completa (regras de deploy, Run now/troca de ano, Repair Run vs novo Run), seção "Por que uma edição por vez (nunca em paralelo)?" e a semântica de falha do orquestrador; README principal com a nova estrutura (2 YAMLs, `pipeline/list_editions`, `environment/modulos/`, `docs/decisoes/`).

### Decisões (e alternativas descartadas)

* **Anos detectados em runtime no mapa (task value), não em lista manual de parâmetro de job** — alternativa descartada (parâmetro JSON `reference_years`): criaria uma segunda fonte de verdade que dessincroniza silenciosamente do mapa (edição registrada e não executada, ou o contrário).
* **`{{input}}` (e não `{{item}}`) no `job_parameters` do `run_job_task`** — `{{item}}` não é resolvido nesse campo pela plataforma e chega literal ao job filho (sintaxe atual da documentação para o valor da iteração).
* **Sequencial por concorrência, não por disciplina** — as edições compartilham as mesmas tabelas físicas de cada camada (o ano é a COLUNA `ano_edicao`); duas escritas simultâneas na mesma tabela Delta são transações concorrentes sobre os mesmos arquivos: a concorrência otimista rejeita uma (`ConcurrentModificationException`) ou um run lê estado pela metade. `max_concurrent_runs: 1` nos dois jobs + `concurrency: 1` no `for_each`. Tabela por edição permitiria paralelismo, mas fragmentaria a análise cross-edição (UNION em toda comparação) e a governança (N× grants/tags/lineage) — uma tabela por camada com edições como linhas é o trade-off deliberado.
* **Falha de uma edição não bloqueia as demais** — iterações do `for_each` são independentes: a 2019 falhar não impede a 2024 de rodar. O run do orquestrador fica vermelho se QUALQUER edição falhar ("Some iterations failed"), mesmo com as outras bem-sucedidas — o veredito por edição fica sempre na aba Runs do pipeline (um run por edição, trigger "Run job task").

### Execuções e evidência

* Primeiro run do orquestrador (após o deploy): as 2 iterações foram criadas corretamente (o task value do `list_editions` resolveu `['2019', '2024']`), mas ambas falharam na ingest com `ValueError: invalid literal for int(): '{{item}}'` — o template não resolvido chegou literal ao job filho (visível nos parâmetros dos runs).
* Com o fix `{{input}}` deployado, a iteração 2019 executou com `reference_year="2019"` resolvido no run do pipeline (trigger RUN_JOB_TASK) — o loop map-driven funcionando ponta a ponta.
* `bundle validate --strict` OK em todas as mudanças de YAML.

---

## Radar por edição na planilha + gold genérica + camada semantic

> Mudança proposta por Alexandre (branch `feat/radar-catalogo`), resolvendo as pendências "gold 2019 / célula 19 / rótulos 2019" e "camada semantic por edição".

### Mudanças

* **Radar fora do código** — `config/radar/radar_imdm.xlsx` (mantido pelo especialista): abas fixas `Dimensoes`, `Itens`, `Niveis`, cada linha com `edicao`. Cada edição tem o seu radar, independente das outras (nº de dimensões, itens, códigos do IBGE, pesos e faixas de maturidade). `validar_radar.py` valida e gera os CSVs versionados junto da planilha.
* **`pipeline/load_radar_config`** (nova task, depois da silver): revalida o radar da edição contra a silver e grava `config.radar_dimensao|item|variavel|pontuacao|nivel` + linha `radar` no ledger (sha256 da planilha).
* **`silver_to_gold`**: Step 3 lê `config.radar_variavel` (sai a lista fixa de 64 itens); Step 6 genérico por regra com os pontos de `config.radar_pontuacao` (saem os mapas e os códigos fixos; o caso do `mgov05` vira a exceção `NAO_SE_APLICA_SEM_PEDIDO_LAI` declarada na planilha); Step 8 grava **`fact_score_dimensao`** (longa: município × dimensão) e a `fact_imdm_municipio` sem as 5 colunas fixas — IMDM = Σ(peso × score) / Σ peso das dimensões do ano com `entra_no_imdm = sim`, nível pelas faixas da edição; Step 9 com 24 controles, incluindo o recálculo independente do IMDM.
* **`pipeline/gold_to_semantic`** (nova task): 8 views para as telas do dashboard (`vw_painel_municipio`, `vw_score_dimensao`, `vw_radar_dimensao`, `vw_item_municipio`, `agg_adocao_indicador`, `agg_imdm_porte_regiao`, `vw_auditoria_lgpd`, `agg_qualidade_item`), 12 controles de fechamento com a gold e linha `semantic` no ledger.

### Decisões

* **Célula 19 → Opção A, por construção**: o radar de 2019 simplesmente não tem a dimensão de LGPD (4 dimensões); o IMDM de cada edição é a média das dimensões daquele radar. Dentro de uma edição, dimensão do IMDM sem item válido continua deixando o IMDM nulo (`Sem_Item_Valido`).
* **Rótulos 2019** (`mgov09` "Sim, por instrumento legal", `mtic29` "Modelo global acessibilidade…") ficam na pontuação de 2019 da planilha — não no código.
* Supersede a decisão "Radar 2024 como definição estrutural única" (seção "Parametrização da gold multi-edição"): o radar por edição vive como **dados validados**, não como flags no código.

### Evidência (ambiente local Spark com a base MUNIC 2024 — falta rodar no Databricks)

* Gold antiga × gold nova (mesma silver 2024, radar 2024 da planilha): **0 divergências** em `resposta_normalizada`, `classe_preenchimento`, `pontos_obtidos` e `peso_aplicado` nas 2.005.200 linhas da `fact_resposta`; 0 divergências no IMDM, motivo de nulo, nível e nos 5 scores dos 5.570 municípios. QC da gold 24/24; QC da semantic 12/12.
* Radar alternativo (7 dimensões, LGPD com peso 2, uma dimensão fora do IMDM): gold 24/24 e semantic 12/12 sem alteração de código.

### Operação

* **Uma vez, antes do primeiro run**: `DROP TABLE munic_catalog.gold.fact_imdm_municipio` (o esquema mudou; o upsert recria) e `bundle deploy` (job com as 2 tasks novas).

---

## Revisão 1 do dashboard: semantic em tabelas, rótulos de não-resposta e app mais robusto

> Revisão pedida por Alexandre depois do primeiro deploy do app (tema escuro, lentidão, "Não sabe" zerado em 2019 e um erro na tela Dimensões).

### Mudanças

* **`gold_to_semantic`: as 8 views viram tabelas Delta** (mesmos nomes, mesmas colunas) e entra a **`agg_adocao_uf_porte`** (item × UF × porte × edição, com Σ pontos e Σ peso). Antes, cada acesso ao app refazia no warehouse os joins com a `fact_resposta`, os rankings e as agregações; agora o pipeline calcula uma vez e o app só lê. Uma view antiga de mesmo nome é removida antes da gravação. Controles: 12 → 15 (a tabela nova fecha Σ pontos, Σ peso e Σ municípios com a gold).
* **`silver_to_gold` (Step 5): rótulos de não-resposta comparados sem acento e sem caixa**, aceitando variações de redação entre edições (`Não sabe informar`, `Não sabe`, `Não soube informar`). `resposta_normalizada` passa a derivar da classe. Um AVISO lista respostas que ficaram como `Valida` mas começam como rótulo de não-resposta.
* **App** (`apps/imdm_dashboard`):
  * Correção do erro da tela Dimensões: com uma UF escolhida, o ranking por município fazia um `merge` que duplicava a coluna `nome` (`KeyError: 'nome'`) — quebrava em qualquer UF.
  * Filtros com chave própria (`f_*`) e cliques aplicados no início da execução seguinte; o clique no ranking não se repete em loop; seletor de dimensão sempre com uma opção marcada; filtros sem município (ex.: DF + porte pequeno) mostram aviso em vez de gráficos quebrados; divisões por zero e valores nulos tratados.
  * Leitura das tabelas da abertura em paralelo, cache de 12 h com botão "Recarregar dados", reconexão automática se a sessão do warehouse expirar, tempo de cada leitura nos Logs do app (`[dados]`). Se a `agg_adocao_uf_porte` ainda não existir, o app agrega a `vw_item_municipio` como antes.
  * Tema claro e escuro (menu ⋮); cores dos gráficos legíveis nos dois.
  * `use_container_width` (descontinuado) trocado por `width`; versões das dependências fixadas na testada (Streamlit 1.67.0).
  * "Não sabe" zerado numa edição vira mensagem, e não um gráfico de barras vazias.
  * `tests/test_app.py`: abre as 4 telas com todas as combinações de edição × região × UF × porte, municípios-limite e cada dimensão.

### Evidência (ambiente local)

* Gold antes × depois da mudança de classificação (silver 2024): **0 divergências** nas 2.005.200 linhas da `fact_resposta`, nos 5.570 IMDM e nos 27.850 scores de dimensão.
* Semantic em tabelas × views anteriores: conteúdo idêntico nas 8 (diferença só de arredondamento em `soma_imdm`, ~1e-10); QC 15/15.
* App: app antigo com UF escolhida na tela Dimensões → 360 de 360 combinações com erro; app novo → 0 erros em 3.285 combinações (2024 real + 2019 sintética com 4 dimensões e sem "Não sabe").

### Leitura do "Não sabe" em 2019

A consulta na `fact_resposta` 2019 não mostrou nenhum rótulo de "não sabe" entre as respostas mais frequentes. Com a classificação tolerante, se a edição tiver outra redação, ela passa a ser contada; se continuar 0%, é porque a MUNIC 2019 não tem essa opção nas variáveis do radar.

### Operação

* Pull + rodar o job (ou só a task `gold_to_semantic`) uma vez: as views são trocadas por tabelas automaticamente. Para a classificação nova valer em 2019, rodar o job com `reference_year = 2019`.
* Deploy do bundle e Deploy do app (o app novo pede a tabela `agg_adocao_uf_porte`, mas funciona sem ela).

---

## Pendências da branch

* ~~Silver 2019~~ **RESOLVIDO no re-run do zero** (seção “Re-run do zero”): o fail-fast 7/7 passou contra o contrato da bronze 2019 (307 indicadores / 610 recusas).
* ~~Re-run do zero do pipeline (destrutivo: apaga as 14 tabelas)~~ **EXECUTADO** (confirmação do usuário, 14/11/2026) — seção “Re-run do zero” acima.
* **Reconstrução da gold** (as dq_* já foram recriadas nas duas edições): 2024 rodada e revalidada 21/21 após a parametrização (seção “Parametrização da gold multi-edição”); a 2019 depende da **decisão da célula 19** (IMDM em edição com dimensão ausente) e do mapeamento dos rótulos divergentes 2019 (`mgov09`, `mtic29`); camada semantic por edição.
* ~~Varredura de "FAIL" no `bronze_quality_profiling`~~ **RESOLVIDO** — varredura aplicada ao profiling (mesma deprecicação dos demais notebooks: "interrompe o run (fail-fast)").
* reference_year está em 2024 - religar para 2019 ao retomar a gold 2019 (silver das duas edições já está carregada).

## Commits da branch

| Hash | Mensagem |
| --- | --- |
| `4dbb042` | feat: multi-edição em ingest_to_landing |
| `ae8da3b` | feat: multi-edição no landing_to_bronze e dq_* por edição no bronze_quality_profiling |
| `bfc942e` | docs: relatório de decisões da branch feat/multi-edicao |
| `d553edc` | docs: desenho da tabela pipeline_manifest (contrato de execução por etapa e edição) |
| `17da9b5` | feat: ledger pipeline_manifest — contrato por edição nas fronteiras das etapas |
| `c6af379` | refactor: env_functions em módulos (deteccao/upsert/ledger) + colunas_com_dados/celulas_recusa |
| `aff8eed` | refactor: check_igual, profiling em pipeline/ e migrações legadas mortas removidas |