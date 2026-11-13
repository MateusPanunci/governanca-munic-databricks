# Relatório de decisões e mudanças — branch `feat/multi-edicao`

> **Documento vivo (parcial)** — cobre TODO o trabalho da branch `feat/multi-edicao`, do primeiro commit `4dbb042` (2026-11-09) até 2026-11-13. Será finalizado quando a funcionalidade fechar (silver/gold multi-edição completas).
>
> Fontes: sessões de trabalho com o agente (com evidências verificadas), `git diff main..HEAD` + árvore de trabalho, e histórico da conversa do grupo.

## Contexto

Objetivo da branch: o pipeline MUNIC operar **por edição**, com 2019 e 2024 coexistindo em bronze/silver/gold e nos artefatos de qualidade `dq_*` — sem duplicar código nem reconfigurar nada por mão a cada ano.

---

## 2026-11-09 — Commit `4dbb042`: multi-edição na ingestão

### Mudanças (3 arquivos)

* **`environment/env_variables`** — o mapa `munic_source_url_map` passa a carregar as edições **2019 e 2024** (2019 entra no lugar de 2022); novo `munic_file_paths`, **derivado das URLs** por comprehension (caminho da landing nunca é digitado manualmente); variáveis da edição corrente (`munic_source_url`, `munic_file_name`, `munic_file`) definidas a partir de `reference_year` e consumidas pelos notebooks do pipeline; nota md explicitando que só a ingestão usa `munic_file_paths` — o restante do pipeline seleciona tabela por `reference_year`.
* **`pipeline/ingest_to_landing`** — download e hash refatorados em funções: `download_file()` (idempotente — se o XLSX já existe na landing, ignora) e `get_file_sha256()` (SHA-256 do arquivo baixado como evidência de integridade por edição); prints de origem/destino desativados.
* **`pipeline/landing_to_bronze`** — adaptado para consumir as variáveis de edição do env em vez de configuração própria.

### Decisões (e alternativas descartadas)

* **Fonte única da verdade por edição**: a edição é definida uma única vez no mapa URL do env; adicionar uma edição nova = uma linha no mapa, e caminhos/variáveis derivam disso. Alternativa descartada: manter URLs/caminhos espalhados por notebook.
* **Download idempotente + SHA-256 por arquivo**: reexecutar a ingestão não baixa de novo e sempre evidencia o hash do insumo — auditoria da origem dos dados.

---

## 2026-11-12 — Fundação da multi-edição (bronze + profiling)

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

## 2026-11-12/13 — Item 2.1: drift do dicionário entre edições

### Mudanças

* Nova seção no `bronze_quality_profiling`: **`dq_dict_drift`** — divergência de significado dos códigos comuns entre edições, classificada por tipo (reescrita editorial, ano de referência embutido, reformulação parcial, suspeita de reutilização do código).
* Endurecimento da seção: lista de colunas fixada, fallback da edição B, ordenação determinística, dedup na classificação, labels em md e concatenação via StringBuilder.

### Evidência

* 86 códigos com significado divergente em 2019×2024 — aviso registrado a quem escreve a configuração do radar de uma edição.

---

## 2026-11-13 — Profiling por edição, vereditos e LGPD

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

## 2026-11-13 — Dependência dq_* → gold corrigida e gold 2024 revalidada

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

## 2026-11-13 — Decisões de processo (não-técnicas)

* **Relatório de decisões por branch no fechamento** (este arquivo) em vez de CHANGELOG incremental por commit — decisão do grupo, priorizando baixo atrito; commit messages decentes continuam como registro atômico.
* Fluxo de trabalho: o agente registra sessões na memória interna automaticamente; o relatório final será gerado cruzando memória + `git diff main..HEAD` + histórico da conversa.

---

## Pendências da branch

* **Silver 2019**: investigar o fail-fast que recusou o `bronze_to_silver` (provável causa: dicionário 2019 — 307 linhas — não cobre colunas de identidade renomeadas em relação a 2024).
* Gold 2019 (após silver) e camada semantic por edição.
* Re-run read-only do profiling 2024 para atualizar os outputs do notebook (hoje exibindo 2019 — cosmético; o mecanismo já foi verificado).
* Célula de debug `print(ano_edicao)` no bronze_to_silver (nuid fb101c39) — remover antes do commit?
* Flowchart do modelo gold adicionado pelo usuário ao profiling — avaliar mudança para o silver_to_gold.
* `reference_year` está em **2024** — religar para 2019 ao retomar a Etapa 4 (silver/gold 2019).

## Commits da branch

| Hash | Data | Mensagem |
| --- | --- | --- |
| `4dbb042` | 2026-11-09 | feat: multi-edição em ingest_to_landing |
| (pendente) | 2026-11-12/13 | feat: multi-edição no landing_to_bronze e dq_* por edição no bronze_quality_profiling — acúmulo de 7 arquivos descrito acima |