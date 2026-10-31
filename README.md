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
  * **APO14.02 / APO14.03 (Glossário e Repositório de Metadados):** Extração automatizada e persistência do dicionário de variáveis operacional diretamente na camada Bronze (`bronze.munic_metadata_dict`).
  * **APO14.05 / APO14.06 (Diagnóstico e Evidências de Qualidade):** Perfilamento sistemático de qualidade (Completude, Unicidade, Validade e Consistência) executado antes da publicação na camada Silver.
  * **APO14.07 / BAI07.02 (Higienização e Rastreabilidade):** Padronização vetorial das respostas do questionário (`Sim/Não` $\rightarrow$ `1/0/NULL`) e chaves municipais (`cod_ibge` com 7 dígitos), com histórico de commits registrado via Delta Lake (`userMetadata`).
  * **APO14.08 / DSS06.05 (Ciclo de Vida e Auditoria):** Metadados de proveniência (`ano_referencia`, `_source_file`, `_ingestion_timestamp`) anexados a cada registro para suporte a cargas históricas sem colisão.
* **ISO/IEC 38500 (§4.1.3):** Responsabilidade sobre o ciclo de vida dos ativos analíticos públicos e transparência de processamento.
* **LGPD e Ética:** Tratamento exclusivo de dados públicos de pessoas jurídicas de direito público (prefeituras), sem coleta de dados pessoais sensíveis ou identificáveis (PII).

---

## Arquitetura do Pipeline e Orquestração

O fluxo analítico é orquestrado de ponta a ponta pelo job `job_munic_full_refresh` no Databricks Workflows, dividindo as responsabilidades de ingestão, auditoria de qualidade e higienização analítica:

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
 │ [governance notebook]   │  Auditoria de completude, validade de domínios e unicidade municipal
 └────────────┬────────────┘
              │
 ┌────────────▼────────────┐
 │ bronze_to_silver_task   │  Padronização, tipagem, integridade relacional e consolidação final
 │ [bronze_to_silver]      │  ➔ silver.munic_clean_data (Ativo analítico consolidado)
 |                         |  ➔ silver.munic_clean_dict (Glossário analítico)
 └─────────────────────────┘
