# Governança de Dados e BI: Perfil dos Municípios Brasileiros (MUNIC - IBGE)

[![Databricks](https://img.shields.io/badge/Databricks-Lakehouse-E25A1C?logo=databricks&logoColor=white)](https://databricks.com)
[![PySpark](https://img.shields.io/badge/Apache_Spark-PySpark-E25A1C?logo=apachespark&logoColor=white)](https://spark.apache.org/)
[![Delta Lake](https://img.shields.io/badge/Delta_Lake-Medallion-00ADD8?logo=delta&logoColor=white)](https://delta.io)
[![Governance](https://img.shields.io/badge/Governance-COBIT_2019_|_ISO_38500-blue)](https://www.isaca.org/resources/cobit)

---

## Visão Geral do Projeto

Este projeto é desenvolvido no âmbito da disciplina de Governança de TI e Dados do curso de **Ciência de Dados e Inteligência Artificial da Universidade Estadual de Londrina (UEL)**.

O objetivo é projetar e implementar um pipeline de dados analítico e governado utilizando a arquitetura **Lakehouse Medallion** no **Databricks**. A partir dos microdados da **Pesquisa de Informações Básicas Municipais (MUNIC - IBGE)**, a solução viabiliza a criação de uma camada analítica e semântica voltada a apoiar a tomada de decisão em políticas públicas de gestão e tecnologia municipal.

* **Organização-Alvo (Cliente Institucional):** Secretaria de Governo Digital (SGD/MGI) – Ministério da Gestão e da Inovação em Serviços Públicos.
* **Proposta de Valor:** Transformar pesquisas públicas seccionais do IBGE em um ativo governado, padronizado e auditável, preparado para séries temporais, modelos de maturidade institucional e painéis executivos de BI.
* **Design Multi-Ano (DataOps):** O pipeline foi concebido de forma agnóstica em relação ao ano da pesquisa. Por meio de parametrização dinâmica de execução, a arquitetura permite processar diferentes edições da MUNIC, garantindo rastreabilidade e validação contínua de DataOps.

---

## Alinhamento com Modelos de Governança

A arquitetura e os controles operacionais atendem aos padrões de Governança Corporativa e de Dados:

* **COBIT 2019:**
  * **APO14.02 / APO14.03 (Glossário e Repositório de Metadados):** Extração automatizada e persistência do dicionário de variáveis operacional diretamente na camada Bronze (`bronze.munic_raw_dict`).
  * **APO14.05 / APO14.06 (Diagnóstico e Evidências de Qualidade):** Perfilamento sistemático de qualidade (Completude, Unicidade, Validade e Consistência) executado antes da publicação na camada Silver.
  * **APO14.07 / BAI07.02 (Higienização e Rastreabilidade):** Preservação dos 6 estados originais de resposta da MUNIC (`Sim`, `Não`, `-`, `Não sabe informar`, `Não informou`, `Recusa`) em `StringType` e chaves municipais (`cod_ibge` com 7 dígitos), com histórico de commits registrado via Delta Lake (`userMetadata`).
  * **APO14.08 / DSS06.05 (Ciclo de Vida e Auditoria):** Metadados de proveniência (`ano_referencia`, `_source_file`, `_ingestion_timestamp`) anexados a cada registro para suporte a cargas históricas sem colisão.
* **ISO/IEC 38500 (§4.1.3):** Responsabilidade sobre o ciclo de vida dos ativos analíticos públicos e transparência de processamento.
* **LGPD e Ética:** Tratamento exclusivo de dados públicos de pessoas jurídicas de direito público (prefeituras), sem coleta de dados pessoais sensíveis ou identificáveis.

### Governança nativa da plataforma (Databricks + Unity Catalog)

Além dos controles implementados em código, a própria plataforma já fornece governança de base:

* **Organização e permissões:** o Unity Catalog organiza os dados em camadas (`munic_catalog.bronze | silver | gold`) e controla quem pode ler ou escrever cada tabela via permissões concedidas na plataforma (*grants*) — sem lógica de acesso no nosso código (DSS05);
* **Rastreabilidade (lineage):** o Databricks registra automaticamente a origem de cada dado — qualquer métrica do IMDM pode ser rastreada até o arquivo original do IBGE (APO14.08);
* **Histórico de alterações:** cada escrita fica registrada no Delta Lake com autor, data e conteúdo (`DESCRIBE HISTORY`), e versões anteriores da tabela permanecem consultáveis e utilizáveis (*time travel*);
* **Fonte preservada:** o XLSX original do IBGE fica guardado em um Volume do Unity Catalog, permitindo reprocessar tudo do zero de forma idêntica;
* **Metadados de negócio:** o dicionário de variáveis é tratado como ativo de dados governado (tabelas `bronze.munic_raw_dict` e `silver.munic_clean_dict`), e cada operação de escrita registra sua descrição no histórico Delta (`userMetadata`) — apoiando o repositório de metadados (APO14.02/03).

---

## Arquitetura do Pipeline e Orquestração

O fluxo analítico segue a arquitetura Medallion (landing → bronze → silver → gold); as quatro primeiras etapas são orquestradas pelo job `job_munic_full_refresh` no Databricks Jobs, a etapa gold executa via notebook e a camada semântica é o próximo passo:

```text
 ┌─────────────────────────┐
 │ Ingest_to_landing_task  │  Download do artefato original (XLSX) direto da fonte pública
 │ [ingest_to_landing]     │  Armazenamento imutável em /Volumes/munic_catalog/landing/raw_files/
 └────────────┬────────────┘
              │
 ┌────────────▼────────────┐
 │ landing_to_bronze_task  │  Conversão das planilhas para tabelas Delta soberanas
 │ [landing_to_bronze]     │  Preservação do dado bruto + metadados operacionais de auditoria
 │                         │  ➔ bronze.munic_raw_info_data | bronze.munic_raw_gov_data
 │                         │  ➔ bronze.munic_raw_dict (Glossário extraído via Regex)
 └────────────┬────────────┘
              │
 ┌────────────▼────────────┐
 │ bronze_quality_profiling│  Diagnóstico empírico das 6 dimensões de qualidade de dados (Etapa 2)
 │ [governance notebook]   │  Auditoria de completude, validade de domínios, unicidade e skip-logic; gera as tabelas gold.dq_*
 └────────────┬────────────┘
              │
 ┌────────────▼────────────┐
 │ bronze_to_silver_task   │  Ajuste 1: preservação dos 6 estados originais; consolidação TIC + GOV (5.570 x 360)
 │ [bronze_to_silver]      │  ➔ silver.munic_clean_data (Ativo analítico consolidado)
 |                         |  ➔ silver.munic_clean_dict (Glossário analítico)
 └────────────┬────────────┘
              │
 ┌────────────▼──────────────┐
 │ silver_to_gold (notebook) │  Etapa 3: modelo dimensional, Radar IMDM e pontuação
 │ [pipeline/silver_to_gold] │  ➔ gold.dim_municipio | gold.dim_indicador (360 variáveis)
 │                           │  ➔ gold.fact_resposta (2.005.200 linhas) | gold.fact_imdm_municipio
 └────────────┬──────────────┘
              │
 ┌────────────▼──────────────────┐
 │ gold_to_semantic (planejado)  │  Camada semântica para BI 
 │ [gold_to_semantic]            │  ➔ semantic.vw_painel_municipio | semantic.agg_imdm_porte_regiao
 │                               │  ➔ semantic.agg_adocao_indicador | semantic.vw_auditoria_lgpd
 └───────────────────────────────┘
```

---

## Estrutura do Repositório

```text
governanca-munic-databricks/
│
├── README.md                        # Visão geral, diagrama do pipeline e mapa de entregáveis
├── .gitignore
│
├── environment/                     # Configuração compartilhada — carregada via %run
│   ├── env_variables                # Catálogo/schemas, ano de referência e fontes por edição
│   ├── env_functions                # upsert_delta_table: MERGE compartilhado (bronze → gold)
│   └── env_setup_scripts            # Scripts de setup inicial do ambiente
│
├── pipeline/                        # Camadas Medallion — execução em ordem
│   ├── ingest_to_landing            # Etapa 1: download do XLSX oficial → Volume landing
│   ├── landing_to_bronze            # Etapa 1: XLSX → tabelas Delta brutas + dicionário
│   ├── bronze_to_silver             # Etapa 2/3: higienização, ajustes para etapa 3 (6 estados) e consolidação
│   └── silver_to_gold               # Etapa 3: modelo dimensional, Radar IMDM e pontuação
│
├── governance/                      # Auditoria de qualidade (Etapa 2)
│   └── bronze_quality_profiling     # Perfilamento das 360 variáveis → tabelas gold.dq_*
│
├── exploration/                     # Análises exploratórias (fora do pipeline oficial)
│   ├── munic_exploring_xlsx         # Primeira exploração do XLSX original do IBGE
│   └── layer_tables_view            # Inspeção das tabelas por camada (landing → gold)
│
└── docs/
    ├── negocio/
    │   └── radar_imdm.md            # Documentação do Radar IMDM — a ser implementado no dashboard final na Etapa 4
    ├── arquitetura/
    │   └── gold_dimensional_model.md  # Especificação da Etapa 3: dimensional, pontuação e semantic
    └── entregas/
        ├── ProjetoFinal_Etapa1.pdf  # Entregável formal da Etapa 1
        └── ProjetoFinal_Etapa2.pdf  # Entregável formal da Etapa 2
```

---

## Entregáveis por Etapa

Cada etapa possui **três evidências complementares**, permitindo avaliar o documento formal, a implementação executável e o resultado auditável:

1. **Documento formal:** PDF em `docs/entregas/` (Etapas 1 e 2) ou especificação em `.md` (Etapa 3) — entregável oficial de cada etapa;
2. **Código executável:** notebooks versionados no repositório, reproduzíveis ponta a ponta;
3. **Tabelas auditáveis no Unity Catalog** (`munic_catalog`): o resultado de cada etapa pode ser conferido consultando as tabelas e o histórico Delta (`DESCRIBE HISTORY`), incluindo o `userMetadata` que registra as refatorações.

| Etapa | Entregável formal (PDF) | Código / especificação no repositório | Tabelas de conferência no Unity Catalog |
| :--- | :--- | :--- | :--- |
| **Etapa 1** — Ingestão e Bronze | `docs/entregas/ProjetoFinal_Etapa1.pdf` | `pipeline/ingest_to_landing`, `pipeline/landing_to_bronze`, `environment/` | Volume `landing.raw_files` e `bronze.munic_raw_*` |
| **Etapa 2** — Qualidade e Silver | `docs/entregas/ProjetoFinal_Etapa2.pdf` | `governance/bronze_quality_profiling`, `pipeline/bronze_to_silver`, `exploration/` | `gold.dq_*` e `silver.munic_clean_*` |
| **Etapa 3** — Gold dimensional e IMDM | Os próprios arquivos `.md`: `docs/arquitetura/gold_dimensional_model.md` e `docs/negocio/radar_imdm.md` | `pipeline/silver_to_gold` (+ Ajuste 1 em `bronze_to_silver`) | `gold.dim_municipio`, `gold.dim_indicador`, `gold.fact_resposta`, `gold.fact_imdm_municipio` |
| **Etapa 4** (planejada) — Semântica e multi-edição | — | Notebook `gold_to_semantic` (Seção 5 do spec) e parametrização por edição | `munic_catalog.semantic` |

---

## Declaração sobre Uso de IA

Ferramentas de IA generativa foram utilizadas para auxiliar na redação de textos, no desenvolvimento e revisão de código, no brainstorming técnico e na formatação da documentação. Todas as decisões de arquitetura, chaves dimensionais, lógica ETL e controles de governança foram revisadas, executadas e validadas pelos membros do grupo, em conformidade com as normas do curso.
