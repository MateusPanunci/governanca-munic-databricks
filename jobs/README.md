# jobs/ — definições de jobs versionadas

Job é um objeto do **workspace** (não do repositório): o Git versiona os notebooks, mas não o
job em si. Esta pasta fecha essa lacuna mantendo a definição JSON dos jobs do pipeline para
que qualquer branch/collega consiga recriar o mesmo desenho de DAG.

## job_munic_pipeline

Pipeline ponta a ponta de **uma edição da MUNIC** por execução, idempotente (MERGE por
`ano_edicao` + `replaceWhere`):

```
ingest_to_landing_task          baixa TODAS as edições do mapa de URLs (idempotente)
        |
landing_to_bronze_task          bronze da edição escolhida
        |
   +----------------+
   |                |
bronze_quality_    bronze_to_silver_task      (paralelo: só leem a bronze)
profiling_task     grava dq_* por edição       grava a silver da edição
   |                |
   +-------+--------+
           |
silver_to_gold_task            dim/fact da edição (guard do ledger: exige
                               silver + dq_* da edição no manifest)
```

O nome do job descreve o modo de operação: o pipeline inteiro, UMA edição por execução.

### Parâmetro de edição

* `reference_year` (default `2024`) — parâmetro do job, entregue às tarefas via widget de
  mesmo nome (definido em `environment/env_variables`). Uma execução = uma edição inteira.
* Rodar outra edição: `databricks jobs run-now <job_id> --json '{"job_id": <job_id>, "job_parameters": {"reference_year": "2019"}}'`
* Full refresh de 2 edições: rodar 2× (2019, depois 2024). Se um dia houver um `for_each`, as
  iterações devem ser **sequenciais** — as edições compartilham as mesmas tabelas físicas
  (MERGE concorrente no Delta).

### Recriar o job em outro usuário/workspace

Os caminhos das tarefas são absolutos no workspace. Para recriar em outro clone do repo,
ajuste o prefixo `/Users/mateus.panunci@uel.br/` para o seu usuário e rode:

```
databricks jobs create --json @jobs/job_munic_pipeline.json
```

> Espelho manual: este JSON é um export das settings do job. Editar o job pela UI NÃO
> atualiza o arquivo — ao mudar algo no job, reexporte/atualize o JSON e commite.
> Caminho robusto de longo prazo: Declarative Automation Bundle (DAB), que resolve
> caminhos relativos e permite `bundle deploy`. Este JSON é a solução leve enquanto o
> projeto não adota DAB.
