# resources/ — Definição e operação do job MUNIC

Aqui vive a **fonte da verdade** do job do pipeline, como código do Declarative
Automation Bundle (DAB): edita-se aqui (ou em PR) e o `bundle deploy` atualiza o
job no workspace.

## Arquivos

* `job_munic_pipeline.yml` — o job `job_munic_pipeline`: as 5 tarefas, a DAG e o
  parâmetro de edição. Referenciado pelo `databricks.yml` na raiz (include `resources/*.yml`).
* `job_munic_full_refresh.yml` — orquestrador OPCIONAL multi-edicao (`for_each`): detecta
  as edições registradas em `munic_source_url_map` (via task `list_editions`, notebook
  `pipeline/list_editions`) e roda o pipeline completo para cada ano, em sequência.

## Fluxo de trabalho

1. Edite o que precisa (YAML deste bundle ou notebooks em `pipeline/`/`environment/`)
2. **Validate**: painel Deployments → ⋮ → Validate bundle — ou, no terminal, `databricks bundle validate`
3. **Deploy**: botão **Deploy** do painel Deployments — ou, no terminal, `databricks bundle deploy`
4. Commit manual (padrão do projeto)

**Quando deployar (regra geral):** rode o deploy sempre que o repo mudar algo que o job usa — os YAMLs do bundle OU os notebooks (`pipeline/` e `environment/`). Motivo: o job não executa os notebooks da pasta do repo, e sim a cópia sincronizada pelo deploy (`.bundle/.../files`) — enquanto não houver deploy novo, ele continua rodando o código antigo. Em resumo:

| Situação | Deploy? |
| :--- | :--- |
| Pull trouxe mudanças em `pipeline/`, `environment/` ou nos YAMLs do bundle (e você usa o job) | **Sim**, no seu workspace |
| Você alterou qualquer um desses arquivos | **Sim** (antes ou depois do commit, tanto faz) |
| Commit/push de mudanças que JÁ foram deployadas | Não — o deploy não é desfeito pelo commit |
| Só rodar o job com outro `reference_year` (Run now) | Não |
| Mudanças só em `docs/`, `exploration/`, READMEs | Não |
| Rodar um notebook interativamente (fora do job) | Não |

Commit/pull sozinhos NÃO atualizam o job: o Git movimenta arquivos, o deploy é quem publica no workspace. A ordem commit ↔ deploy é livre; só mudança NOVA pede deploy novo.

## Operação

### Como executar (e trocar o ano)

1. Página do job (`job_munic_pipeline`) → botão **Run now** (canto superior direito)
2. No diálogo de execução, ajuste o **`reference_year`** (default 2024, definido em `databricks.yml`)
3. Acompanhe pela aba **Runs** → clique no run para ver a DAG e o log de cada task

Trocar o ano **não exige deploy nem editar código**: o valor vai do run → `base_parameters` das tasks → widget do `env_variables`. Uma execução = uma edição inteira (as tasks filtram por `ano_edicao`).

### Task falhou: Repair Run vs. novo Run

* **Repair run** (menu do run → Repair run) reexecuta **apenas a task que falhou + as downstream** dela; as tasks concluídas com sucesso são reaproveitadas, não rodam de novo. A task reparada **recomeça do zero** — notebook não tem checkpoint, não há "continuar de onde parou". Use-o **somente com o MESMO `reference_year`** (falha transiente ou código corrigido).
* **Trocar o ano dentro de um repair é armadilha:** as tasks concluídas guardam resultados da edição ANTIGA e só as reparadas rodariam com a nova — estado misto de edições num mesmo run. Para processar **outra edição**, faça um **Run now novo** com o parâmetro trocado: a DAG inteira roda para aquela edição, sem duplicar nada (idempotência abaixo).

### Multi-edicao automatizada (opcional)

O job `job_munic_full_refresh` é um orquestrador que roda o `job_munic_pipeline`
**completo** para **cada edição registrada** em `munic_source_url_map` (`env_variables`)
— uma por vez, em sequência (`concurrency: 1`).

**Como os anos são detectados:** primeiro o task `list_editions` (notebook
`pipeline/list_editions`) importa o `env_variables`, extrai as **chaves** do
`munic_source_url_map` e publica a lista como *task value* `years`; o `for_each` lê
esse valor (`{{tasks.list_editions.values.years}}`) e dispara um run do pipeline por
ano. **Não existe lista manual de anos em nenhum lugar** — a fonte da verdade é o
mapa: registrar uma nova edição = adicionar 1 linha no `munic_source_url_map` (+
deploy); o orquestrador a executa sozinho na próxima vez.

* **Rodar:** página do orquestrador → **Run now** — sem parâmetros para ajustar, os anos
  vêm do mapa. Para rodar apenas algumas edições, prefira o pipeline direto (Run now com
  `reference_year`) por ano
* Cada edição vira um **run próprio do pipeline** na aba Runs dele — diagnóstico isolado
* **Se uma edição falha, as demais continuam:** as iterações do `for_each` são
  independentes — a 2019 falhar não impede a 2024 de rodar em seguida. Mas o run do
  orquestrador fica **vermelho se QUALQUER edição falhar** ("Some iterations failed"),
  mesmo que as outras tenham sucesso — o veredito por edição está sempre na aba Runs do
  pipeline (um run por edição, trigger "Run job task")
* Para UMA edição, prefira rodar o `job_munic_pipeline` direto (menos camadas)
* O orquestrador referencia o pipeline pelo bundle (`${resources.jobs.munic_pipeline.id}`)
  — os dois jobs implantam juntos pelo mesmo deploy

### Por que uma edição por vez (nunca em paralelo)?

Decisão de arquitetura: **todas as edições vivem nas mesmas tabelas físicas** de cada
camada (bronze/silver/gold) — o ano é apenas uma **coluna** (`ano_edicao`), não um
schema ou tabela separada. Isso traz uma única schema por camada, consultas
cross-edição sem `UNION` e governança centralizada (grants, tags, ledger
`pipeline_manifest`, lineage num ponto só). O preço é que **escritas na mesma tabela
física precisam ser serializadas** — é concorrência, exatamente:

* Cada task do pipeline grava na MESMA tabela via `MERGE` por `ano_edicao` /
  `replaceWhere`. Duas edições simultâneas = duas transações concorrentes sobre os
  mesmos arquivos/tabela. O Delta resolve isso por concorrência otimista: um dos runs
  **falha** com conflito de transação (`ConcurrentModificationException`) — ou pior,
  lê um estado pela metade enquanto o outro escreve, misturando edições e confundindo
  o ledger do manifest;
* Por isso `max_concurrent_runs: 1` nos DOIS jobs (runs paralelos entram em fila em vez
  de falhar) e `concurrency: 1` no `for_each` — a proteção é estrutural, não disciplinar.

Não é que "tabelas físicas" sejam frágeis — é que a arquitetura escolhida (uma tabela
por camada, edições como linhas) só é segura com escrita exclusiva por vez. Se cada
edição tivesse tabela própria, paralelo seria possível; o custo seria outro (N tabelas,
`UNION` em toda análise cross-edição).

### Regras que valem para qualquer execução

* **Multi-edição:** full refresh de todas as edições = uma execução por edição, em sequência — as edições compartilham as mesmas tabelas físicas e escritas concorrentes na mesma tabela Delta conflitam (ver "Por que uma edição por vez" acima; `max_concurrent_runs: 1` já impõe a fila).
* **Idempotência:** MERGE por `ano_edicao` + replaceWhere, regido pelo ledger `pipeline_manifest` (a gold só roda com silver + dq_* da edição prontas). Rodar de novo não duplica dados.
* **UI_LOCKED:** o job implantado não é editável pela UI — mudanças nascem no repo (PR) e se propagam por deploy.

## Estado

* Jobs do bundle implantados e validados: `job_munic_pipeline` (id 942686881595863) e
  orquestrador `job_munic_full_refresh` (id 990310545519445).
* Job antigo criado pela UI (id 504984352586216) descontinuado e excluído.
