# Tabela `pipeline_manifest` — o ledger do pipeline (contrato de execução por etapa e edição)

> **Status: implementado na branch `feat/multi-edicao` (2026-11-13) — itens 1–4 do plano (seção 7) testados em unidade; o re-run do zero (item 5) aguarda confirmação.**
> Este documento descreve o que é, por que existe, o schema, o que cada etapa grava e como será consumido na prática.

## 1. O que é

O **ledger** (livro-razão, do contábil) é uma tabela Delta única no Unity Catalog — **uma linha por `etapa` × `ano_edicao`** — em que cada etapa do pipeline declara o **contrato do que produziu**: quantas linhas, quantos indicadores com dados, quanto de recusa preservou, a partir de qual arquivo-fonte (SHA-256).

Duas características essenciais:

* **É o estado atual, não o histórico.** Cada linha é atualizada por MERGE na chave `(etapa, ano_edicao)` — re-rodar uma etapa atualiza a linha, nunca duplica. O histórico completo das escritas continua morando no `DESCRIBE HISTORY` de cada tabela (e do próprio ledger: cada atualização sua é uma versão dele).
* **É contrato, não evidência.** As colunas de nível superior guardam apenas o que alguma etapa posterior **valida contra** (`validar_*`). Os demais números — de contexto, diagnóstico e relatório, que enriquecem a análise sem pertencer ao núcleo validável — vivem no MAP `detalhes`, cujo papel nas verificações está detalhado na seção 5.5.

### 1.1 Contrato, evidência e auditoria — três conceitos distintos

No escopo da engenharia de dados:

* **Contrato** é a expectativa declarada e verificável entre um produtor e um consumidor de dados, na fronteira de uma etapa: a forma e o conteúdo que **devem valer** para o consumidor prosseguir (quantas linhas, quantos indicadores, quais invariantes). É assertivo e prospectivo — a violação **interrompe o pipeline com instrução clara** (fail-fast), antes que dados ruins se propaguem. É o espírito dos *data contracts*: o produtor declara, o consumidor valida. Aqui, o produtor declara no ledger e o consumidor valida com `validar_*`.
* **Evidência** é o registro do que foi **observado** sobre os dados: descritiva, consultada para análise e relatório — não é algo contra o que se afirma por padrão. As `dq_*` do profiling são evidência: perfil de colunas, drift do dicionário, viés por faixa. Evidência responde *"como estão os dados"*; contrato responde *"o que precisa valer"*.
* **Auditoria** é a reconstrução posterior dos eventos — quem gravou o quê, quando e por quê — para prestação de contas (COBIT, no projeto). Vive no `DESCRIBE HISTORY` + `userMetadata` + relatórios de etapa; é retrospectiva. Auditoria responde *"o que aconteceu"*.

O ledger toca os três papéis em graus diferentes: é **primariamente contrato** (linhas validadas por `validar_*`), **secundariamente auditoria** (as linhas e o histórico da própria tabela são registros consultáveis) e **deliberadamente não é evidência** (isso continua com as dq_*). Em uma frase: contrato falha alto e antes; evidência informa; auditoria reconstrói depois.

### 1.2 Manifest × ledger — conceitos e diferença

* **Manifest** vem da logística: a lista de carga declarada de um embarque — o que exatamente vai dentro dele. Em dados, é a declaração do conteúdo de uma carga/build: origem, linhas, colunas, hash.
* **Ledger** vem da contabilidade: o livro-razão — o registro contínuo, uma entrada por fato, acumulando ao longo do tempo.
* Neste desenho são o **mesmo artefato em granularidades diferentes**: **cada linha é um manifest** (a declaração de carga de uma etapa×edição) e a **tabela inteira é o ledger** (o livro que acumula os manifests). Por isso a tabela se chama `pipeline_manifest` (nomeia a linha) e este documento chama o conjunto de ledger (nomeia o livro).

## 2. Por quê

O diagnóstico que motivou o desenho (verificado em 2026-11-13):

* O fail-fast do `bronze_to_silver` hardcoded para 2024 (`== 360` indicadores, `== 5570` municípios, `== 2520` recusas) **estoura nas duas edições** com o schema união da bronze: a união tem 403 colunas de indicadores; com dados são **360 em 2024 e 307 em 2019**. Ou seja, o mesmo notebook quebra para a edição 2019 *e* para um re-run da 2024.
* **De onde vinha o 360** (para o número não parecer mágico): ele estava **correto quando foi escrito** — a bronze então continha apenas a edição 2024, e 360 era o shape real da tabela. Virou armadilha quando a segunda edição entrou na mesma tabela. Cada edição da MUNIC traz um **conjunto de variáveis próprio** (2024: 360 indicadores com dados; 2019: 307; há variáveis que só existem em uma delas), e o total de colunas do schema união cresce a cada edição adicionada (403 hoje, com 2019+2024; maior com uma terceira). Consequência de desenho: **nenhum desses números é constante de projeto** — todos os números citados neste documento são medições verificadas do estado atual (2026-11-13), e a única pergunta hardcoded que restará no código é "a linha desta edição existe no ledger?"
* Numa workspace nova (ex.: colega clonando o repo), a ausência de tabelas upstream gera erros críticos em vez de instrução clara.
* A dependência silenciosa dq_* → gold ficou invisível até a guard `_exigir_dq_da_edicao`; o mesmo padrão precisa valer para as fronteiras landing→bronze→silver→gold.
* A auditoria (COBIT) pede uma trilha de "o que entrou/saiu em cada etapa" consultável — hoje só existe implícita nos logs de execução.

O ledger resolve os quatro: expectativas por edição **auto-registradas no carregamento** (adição de edição nova = uma linha nova, zero manutenção), guards uniformes de fronteira, e um livro-razão consultável por qualquer pessoa.

## 3. Schema

```sql
CREATE TABLE munic_catalog.gold.pipeline_manifest (
  etapa            STRING,              -- 'landing' | 'bronze' | 'profiling' | 'silver' | 'gold' | 'semantic'
  ano_edicao       INT,                 -- chave junto com etapa
  tabela_destino   STRING,              -- tabela(s) gravada(s); volume path na landing
  sha256_xlsx      STRING,              -- amarra à origem (landing e bronze); NULL nas demais
  linhas           BIGINT,              -- municípios carregados/gravados
  indicadores      INT,                 -- indicadores COM DADOS na edição (360 em 2024 / 307 em 2019)
  recusa_total     BIGINT,              -- células 'Recusa' que a etapa declara preservar
  detalhes         MAP<STRING,STRING>,  -- contexto, diagnóstico e relatório; papel nas verificações: seção 5.5
  criado_em        TIMESTAMP
)
USING DELTA
```

**Coluna por coluna:**

| Coluna | Natureza | Papel |
| --- | --- | --- |
| `etapa` + `ano_edicao` | contratual | chave do MERGE — uma linha por par, para sempre |
| `tabela_destino` | informativa | onde a etapa gravou (inspetção rápida; a existência real é confirmada pela guard, não pelo ledger) |
| `sha256_xlsx` | contratual | elo de linhagem: mesma hash na linha landing e na bronze responde "de que arquivo exato saiu isto" |
| `linhas` | contratual | municípios — verificado em cada fronteira (5570 em 2019 e 2024) |
| `indicadores` | contratual | shape da edição — substitui o `== 360` hardcoded (360/307/… automático) |
| `recusa_total` | contratual | invariante da cadeia: nasce no bronze (2520 em 2024), preservado na silver, chega intacto na fact_resposta |
| `detalhes` | contextual | contexto, diagnóstico e relatório: alimenta mensagens de falha, triagem e relatórios — e sobe a coluna contratual quando passa a ser validada (seção 5.5) |
| `criado_em` | informativa | quando a linha foi gravada/atualizada |

**Por que uma tabela UC e não outra coisa:** o `DESCRIBE HISTORY` descreve a *escrita* (quem/quando), não o *conteúdo* por edição; `TBLPROPERTIES` é metadado da tabela inteira (multi-edição numa tabela só não tem propriedade "por edição"); arquivo JSON no volume não é pesquisável/juntável. Tabela Delta com `ano_edicao` na chave dá versionamento e upsert de graça.

**Por que não as dq_***: são evidência de governança produzidas pelo profiling, rodado em cadência própria; fazer a silver depender delas inverte a ordem do pipeline e acopla evidência a controle. A gold continua consumindo dq_* (como já faz) — o ledger é o contrato entre etapas estruturais.

## 4. O que cada etapa grava

Números reais verificados (2024) para tornar concreto:

| Etapa | Colunas contratuais | `detalhes` (exemplos) |
| --- | --- | --- |
| **landing** | `sha256_xlsx` preenchido; linhas/indicadores/recusa NULL (é arquivo, não tabela) | `{arquivo, tamanho_mb, url_origem, baixado_em, ja_existia}` — e `sha_anterior_divergente` quando o SHA recalculado difere do último declarado (seção 5.6) |
| **bronze** | linhas 5570, indicadores 360, recusa 2520 | `{info_com_dados: "198", gov_com_dados: "162", dict_linhas: "358", schema_uniao: "221+182"}` |
| **profiling** | indicadores 406 (colunas perfiladas); recusa NULL | `{funil_mantidas, saltos_candidatos: "171", drift: "86", faixas_vies: "7", lgpd: "coletada"}` |
| **silver** | linhas 5570, indicadores 360 (shape da edição), recusa 2520 preservada | `{schema_total: "372", estados_preservados: "6", tipo_resposta: "StringType"}` |
| **gold** | linhas 5570 (dim_municipio), indicadores 360 (dim_indicador), recusa 2520 (fact_resposta) | `{checks_pass: "20/20", fact_resposta_linhas: "2005200", fact_imdm_linhas: "5570", ancoras: "13", radar_itens: "64"}` |
| **semantic** | a definir quando a etapa existir | `{views_publicadas, validacoes}` |

Observação sobre a edição 2019: indicadores com dados = **307** (134 info + 173 gov); `recusa_total` será apurado na primeira carga. O profiling perfilou **406** colunas por edição porque o schema bronze é a união das edições — o ledger registra as duas coisas sem ambiguidade (`indicadores` = com dados; `detalhes.colunas_perfiladas` = universo perfilado). Nota: 406 (universo perfilado nas dq) e 403 (schema união atual) divergem em 3 colunas — ponta aberta registrada no relatório da branch.

## 5. Como será usado na prática

### 5.1 As funções de verificação (em `modulos/ledger`, via hub `env_functions`)

Família `validar_*` — validar = conferir contra o contrato e **interromper** se reprovar:

```python
def contrato_da_edicao(etapa, ano_edicao):
    """Retorna a linha do ledger (o contrato) da etapa×edição; aborta com
    instrução clara se não existir (padrão da _exigir_dq_da_edicao da gold).
    Também confirma tableExists e linhas da edição na tabela física —
    o ledger declara, a guard confere."""

def check_igual(obtido, esperado, nome_check, contexto=""):
    """Confere igualdade contra o contrato; falhas acumulam e estouram
    juntas no resumo (padrão do Step 9 do silver_to_gold: checks PASS/FAIL)."""
```

### 5.2 O fail-fast do bronze_to_silver, reescrito

Antes (hardcoded, quebra com qualquer edição ≠ 2024):

```python
assert len(indicator_cols_final) == 360   # AssertionError pelado no dia 12/11
```

Depois:

```python
manifest = contrato_da_edicao(etapa="bronze", ano_edicao=ano_edicao)
check_igual(info_count,                manifest["linhas"],       "linhas_info")
check_igual(len(indicator_cols_final), manifest["indicadores"],  "indicadores_com_dados")
check_igual(recusa_final,              manifest["recusa_total"], "recusa_preservada")
```

**Ordem de execução** — os checks do fail-fast (`check_igual` + `resumo_validacoes`) rodam **antes de qualquer escrita na silver**, inclusive da migração de schema (`CHANGE COLUMN` boolean→StringType). Assim, um run reprovado morre sem deixar a tabela em estado meio-migrado. (No dia do desenho, 13/11, era o contrário — a migração tocava a silver primeiro e o fail-fast só validava depois; corrigido em 14/11 e verificado no re-run do zero: fail-fast 7/7 antes da primeira escrita.)

### 5.3 Fronteiras cobertas

* **bronze → silver**: fail-fast lê a linha `bronze/edição` (substitui 360/5570/2520).
* **profiling → gold**: a guard `_exigir_dq_da_edicao` pode passar a ler também `profiling/edição` (contrato) mantendo a leitura das dq_* (evidência).
* **silver → gold**: Step 1 pode validar contra `silver/edição` (shape 360/307, recusa preservada).
* **Re-run do zero**: cada etapa re-executada redeclara sua linha (MERGE, sem duplicar) — o ledger populado de ponta a ponta é o próprio artefato de validação da re-execução.

### 5.4 O que o ledger NÃO faz

* Não substitui `DESCRIBE HISTORY`/`userMetadata` (trilha de escritas) — complementa.
* Não substitui as guards de existência — o ledger pode afirmar algo que a tabela física já não confirma (DROP manual); a guard sempre confere `tableExists` + linhas + contrato.
* Não substitui as dq_* — evidência de qualidade continua com elas.

### 5.5 O papel do MAP `detalhes` nas verificações

O `detalhes` **não entra nos asserts por padrão** — por desenho: o núcleo do fail-fast permanece enxuto e determinístico (só o contrato), enquanto o contexto evolui livre, sem migração de schema. Mas ele **participa** da verificação em três frentes concretas:

1. **Triagem quando algo reprova**: a mensagem de erro dos `validar_*` cita os valores de `detalhes` da linha para localizar o desvio. Ex.: `indicadores` divergiu → `detalhes.info_com_dados` e `detalhes.gov_com_dados` mostram em qual das duas fontes está a diferença — sem segunda consulta.
2. **Checks pontuais**: qualquer verificação pode ler o MAP durante investigação (`check_igual(obtido, manifest["detalhes"]["gov_com_dados"], ...)`). O MAP é acessível ao `contrato_da_edicao` como qualquer campo; apenas não integra o contrato por padrão.
3. **Promoção a contrato**: quando uma cifra do MAP passa a ser sistematicamente validada (ex.: `checks_pass` da gold virando critério de bloqueio), ela **sobe para coluna contratual**. A fronteira entre contexto e contrato é móvel — e movê-la é explícito e rastreável.

Em resumo: o MAP não é depósito de números inúteis — é onde mora o **diagnóstico** que torna as falhas do contrato rapidamente explicáveis.

### 5.6 Integridade do insumo da landing (aviso de divergência)

A ingestão verifica o arquivo com `verificar_arquivo_landing` (em `env_functions`, junto da família do ledger): recalcula o SHA-256 em **todo** run (mesmo de arquivo já existente) e o compara com o último declarado na linha `landing/edição`, retornando os valores prontos — quem grava é o `gravar_linha_manifest`, chamado pela própria ingestão, no mesmo padrão de declaração de todas as etapas. Se divergiu — arquivo excluído e baixado de novo com outro conteúdo, origem alterada no IBGE ou arquivo substituído manualmente — imprime um **AVISO** com os dois hashes e grava o anterior em `detalhes.sha_anterior_divergente`: a linha é atualizada com o SHA novo, mas **nunca em silêncio** (é o sinal de que o insumo da cadeia — bronze e silver amarradas à mesma hash — precisa de reprocessamento consciente). Se o re-download após exclusão traz o mesmo conteúdo, o caso normal do IBGE, o SHA bate: `ja_existia` vira "false", sem aviso — só divergência de **conteúdo** importa.

O `detalhes.baixado_em` segue a mesma honestidade: é o momento em que o arquivo **chegou ao volume** — `now()` quando este run baixou, ou o **mtime do arquivo** quando ele já existia. Nunca um "agora" fabricado para um arquivo que não baixamos.

Semântica de exclusão: enquanto o arquivo está apagado, o ledger mantém o último estado declarado (é declarativo — não monitora o volume em tempo real); no re-run a ingestão re-baixa e o MERGE atualiza a mesma linha.

## 6. Correção irmã (mesma iniciativa)

O `userMetadata` não está chegando nos MERGEs do `upsert_delta_table` (histórico mostra `None` em todos, inclusive pós-refatoração). O caminho `df.write.option("userMetadata")` funciona para saveAsTable; o MERGE pela API do Delta exige a conf de sessão `spark.databricks.delta.commitInfo.userMetadata` — a setar no passo 6 do upsert. Sem isso, a trilha "quem gravou e por quê" fica furada, e o ledger cobre só metade da auditoria.

**Implementado (2026-11-13), com uma limitação descoberta em execução**: em compute **serverless** essa conf de sessão é `CONFIG_NOT_AVAILABLE` (SQLSTATE 42K0I) — nem `spark.conf.set` nem `SET` SQL funcionam (o `userMetadata` só chega ao histórico em clusters clássicos). O passo 6 do upsert e o `gravar_linha_manifest` usam o helper `_set_user_metadata`, que tenta setar, avisa **uma única vez** quando indisponível e segue sem interromper. Nesses MERGEs a trilha fica com operation/timestamp do `DESCRIBE HISTORY`; a auditoria declarativa completa (quem, quê, a partir de qual SHA-256) é o papel do próprio ledger.

## 7. Plano de implementação

> **Status (2026-11-13): itens 1–4 implementados e testados em unidade** — funções do ledger no `env_functions`, linha `landing` para 2024 e 2019 com SHA-256 real, MERGE idempotente confirmado, ramos da guard verificados (contrato ausente → instrução; tabela dropada → "contrato desmentido"; fail-fast em bloco no `resumo_validacoes`). O item 5 (re-run do zero, destrutivo: apaga as 14 tabelas) aguarda confirmação do usuário.

1. Funções de verificação `check_igual`/`contrato_da_edicao` no `env_functions` (padrão do Step 9 generalizado).
2. `landing_to_bronze` grava a linha `bronze` do ledger (e `ingest_to_landing` a linha `landing` com SHA-256 — já calculado na ingestão).
3. `bronze_to_silver`: fail-fast migra para funções + ledger; descarte das colunas 100% nulas na edição (silver por edição, 360/307); validação antes da migração de schema; remover célula debug `print(ano_edicao)`.
4. `silver_to_gold` grava a linha `gold` (e o profiling, a sua); guards passam a ler o ledger.
5. **Re-run do zero** (apagar as 14 tabelas, recarregar as duas edições): valida o pipeline de ponta a ponta e popula o ledger limpo — virando a evidência de auditoria da execução.

## 8. Verificação

* Cada fronteira falha com instrução clara quando a edição não tem linha no ledger (mesma filosofia da guard dq).
* Números conhecidos devem bater: 2024 → 5570/360/2520; 2019 → 5570/307/recusa a apurar; invariante recusa 2520 constante bronze→silver→gold.
* Re-executar uma etapa não duplica linhas (MERGE na chave).
* DROP manual de tabela + guard deve barrar execução apesar do ledger afirmar o contrário.