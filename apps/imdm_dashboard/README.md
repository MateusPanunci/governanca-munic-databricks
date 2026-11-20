# Dashboard IMDM (Streamlit no Databricks Apps)

Lê **somente** a camada `munic_catalog.semantic` (gerada pelo `pipeline/gold_to_semantic`). Nenhuma regra de pontuação mora aqui: dimensões, itens e pesos vêm do radar de cada edição (`config/radar/radar_imdm.xlsx`). Se o especialista mudar o radar, o dashboard muda junto, sem alteração de código.

| Tela | O que mostra | Views usadas |
|---|---|---|
| Visão geral | KPIs (mudam quando um município é escolhido), radar seleção × referência × Brasil, score por dimensão, LGPD, ranking clicável, distribuição, porte, mapa, níveis, maiores/menores | `vw_painel_municipio`, `vw_score_dimensao`, `vw_radar_dimensao`, `vw_auditoria_lgpd` |
| Perfil do município | Rankings, radar município × UF × Brasil, mapa da UF, lacunas e destaques frente ao porte, todos os itens do radar com a resposta do IBGE | + `vw_item_municipio` |
| Dimensões | Seletor de dimensão do ano, adoção de cada item × Brasil, score por UF/município, distribuição e porte | `vw_item_municipio` (agregada), `vw_score_dimensao` |
| Qualidade dos dados | IMDM nulo por motivo, "Não sabe" por variável e por UF, saltos lógicos, regras de tratamento e o radar de cada edição | `agg_qualidade_item`, `vw_painel_municipio`, `vw_radar_dimensao` |

Filtros na barra lateral (valem para todas as telas): edição, macrorregião, UF, porte e município.

## Publicar no Databricks

1. **Deploy do bundle** (mesmo painel 🚀 do job): o app `imdm-dashboard` é criado a partir de `resources/app_imdm_dashboard.yml`, já ligado ao SQL warehouse. O warehouse é procurado pelo nome `Serverless Starter Warehouse` (variável `warehouse_id` no `databricks.yml`); se o seu tiver outro nome, troque lá.
2. **Dar leitura da semantic ao app.** Em *Compute → Apps → imdm-dashboard*, copie o **ID do service principal** do app (aba *Authorization*/*Permissions*) e rode num SQL editor:
   ```sql
   GRANT USE CATALOG ON CATALOG munic_catalog TO `<id-do-service-principal>`;
   GRANT USE SCHEMA  ON SCHEMA  munic_catalog.semantic TO `<id-do-service-principal>`;
   GRANT SELECT      ON SCHEMA  munic_catalog.semantic TO `<id-do-service-principal>`;
   ```
   O app só enxerga a semantic — gold, silver e o ledger continuam fechados para ele (governança: menor privilégio).
3. **Start** no app e abrir o link. Na Free Edition o app para sozinho depois de 24 h: antes de apresentar, clique em *Start* de novo.

## Rodar no seu computador (desenvolvimento)

Exporte as views para `.parquet` (um arquivo por view, com o mesmo nome) e rode:

```bash
pip install -r requirements.txt
IMDM_LOCAL_DIR=<pasta com os parquet> streamlit run app.py
```

## Arquivos

- `app.py` — as 4 telas; `dados.py` — leitura da semantic (Databricks SQL ou parquet local), com cache.
- `app.yaml` — comando e variáveis do Databricks Apps; `requirements.txt` — dependências.
- `data/coordenadas_municipios.csv` — sede dos municípios para os mapas (fonte: repositório público kelvins/municipios-brasileiros).
