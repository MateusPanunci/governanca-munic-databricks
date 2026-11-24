# Dashboard IMDM (Streamlit no Databricks Apps)

Lê **somente** a camada `munic_catalog.semantic` (gerada pelo `pipeline/gold_to_semantic`). Nenhuma regra de pontuação mora aqui: dimensões, itens e pesos vêm do radar de cada edição (`config/radar/radar_imdm.xlsx`). Se o especialista mudar o radar, o dashboard muda junto, sem alteração de código.

| Tela | O que mostra | Tabelas usadas |
|---|---|---|
| Visão geral | KPIs (mudam quando um município é escolhido), radar seleção × referência × Brasil, score por dimensão, LGPD, ranking clicável, distribuição, porte, mapa, níveis, maiores/menores | `vw_painel_municipio`, `vw_score_dimensao`, `vw_radar_dimensao`, `vw_auditoria_lgpd` |
| Perfil do município | Rankings, radar município × UF × Brasil, mapa da UF, lacunas e destaques frente ao porte, todos os itens do radar com a resposta do IBGE | + `vw_item_municipio` (só o município), `agg_adocao_uf_porte` |
| Dimensões | Seletor de dimensão do ano, adoção de cada item × Brasil, score por UF/município, distribuição e porte | `agg_adocao_uf_porte`, `vw_score_dimensao` |
| Qualidade dos dados | IMDM nulo por motivo, "Não sabe" por variável e por UF, saltos lógicos, regras de tratamento e o radar de cada edição | `agg_qualidade_item`, `vw_painel_municipio`, `vw_radar_dimensao` |

Filtros na barra lateral (valem para todas as telas): edição, macrorregião, UF, porte e município.

**Tema claro ou escuro:** menu ⋮ no canto superior direito (Light, Dark ou System).

**Desempenho:** as tabelas da semantic já vêm calculadas pelo pipeline; o app lê as da abertura em paralelo e guarda tudo em cache por 12 h. Depois de rodar o pipeline, clique em **Recarregar dados** na barra lateral. O tempo de cada leitura aparece nos *Logs* do app, com o prefixo `[dados]`. O primeiro acesso do dia pode demorar mais porque o SQL warehouse precisa ligar.

## Publicar no Databricks

1. **Deploy do bundle** (mesmo painel 🚀 do job): o app `imdm-dashboard` é criado a partir de `resources/app_imdm_dashboard.yml`, já ligado ao SQL warehouse. O warehouse é procurado pelo nome `Serverless Starter Warehouse` (variável `warehouse_id` no `databricks.yml`); se o seu tiver outro nome, troque lá.
2. **Dar leitura da semantic ao app.** No seletor de apps (ícone ⋮⋮⋮ no canto superior direito) → *Databricks Apps* → *imdm-dashboard*, copie o **ID do service principal** do app (em *App authorization*) e rode num SQL editor:
   ```sql
   GRANT USE CATALOG ON CATALOG munic_catalog TO `<id-do-service-principal>`;
   GRANT USE SCHEMA  ON SCHEMA  munic_catalog.semantic TO `<id-do-service-principal>`;
   GRANT SELECT      ON SCHEMA  munic_catalog.semantic TO `<id-do-service-principal>`;
   ```
   O app só enxerga a semantic — gold, silver e o ledger continuam fechados para ele (governança: menor privilégio).
3. **Start** no app e abrir o link. Na Free Edition o app para sozinho depois de 24 h: antes de apresentar, clique em *Start* de novo.

## Rodar no seu computador (desenvolvimento)

Exporte as tabelas da semantic para `.parquet` (um arquivo por tabela, com o mesmo nome) e rode:

```bash
pip install -r requirements.txt
IMDM_LOCAL_DIR=<pasta com os parquet> streamlit run app.py
```

## Testes

`tests/test_app.py` abre as 4 telas com todas as combinações de edição × região × UF × porte, municípios-limite (IMDM nulo, maiores, menores, DF) e cada dimensão do radar, e falha se alguma der erro. Usa a mesma pasta de `.parquet`:

```bash
IMDM_LOCAL_DIR=<pasta com os parquet> python tests/test_app.py            # completo (~40 min)
IMDM_LOCAL_DIR=<pasta com os parquet> python tests/test_app.py --rapido   # amostra (~8 min)
```

## Arquivos

- `app.py` — as 4 telas; `dados.py` — leitura da semantic (Databricks SQL ou parquet local), com cache, leitura paralela e reconexão.
- `tests/test_app.py` — teste de todas as telas × filtros.
- `.streamlit/config.toml` — temas claro e escuro.
- `app.yaml` — comando e variáveis do Databricks Apps; `requirements.txt` — dependências.
- `data/coordenadas_municipios.csv` — sede dos municípios para os mapas (fonte: repositório público kelvins/municipios-brasileiros).
