# Radar IMDM — um radar por edição, definido pelo especialista

O radar não está mais escrito no código. Cada edição da MUNIC tem o **seu** radar, completo e independente das outras: as próprias dimensões (quantas forem), os próprios itens e os códigos do IBGE daquele ano. Nenhuma edição faz referência a outra.

| Quem | Decide | Onde |
|---|---|---|
| Especialista de negócio | dimensões de cada edição (nome, ordem, peso, entra no IMDM), itens e códigos do IBGE, pontuação das respostas, faixas de maturidade | `radar_imdm.xlsx` |
| Time técnico | as regras de cálculo (Sim = 1, escalonado, escada, grupo, exceção do `mgov05`) e as validações | `validar_radar.py` + `pipeline/` |

## A planilha

As abas são **fixas**; cada linha tem a coluna `edicao`. Edição nova = linhas novas, nunca aba nova nem código novo.

| Aba | Uma linha por | Colunas |
|---|---|---|
| Dimensoes | edição × dimensão | `edicao`, `dimensao`, `ordem` (1, 2, 3… sem buracos), `peso`, `entra_no_imdm`, `descricao` |
| Itens | edição × item | `edicao`, `dimensao` (nome igual ao da aba Dimensoes, mesma edição), `item`, `descricao`, `variaveis` (códigos do IBGE separados por `;`, o 1º é a âncora), `regra`, `pontuacao`, `excecao` |
| Niveis | edição × nível | `edicao`, `nivel`, `nome`, `minimo`, `maximo` (0 a 100, sem buracos) |
| Listas, Historico, LEIA-ME | — | regras aceitas, registro de mudanças e instruções |

**Coluna `pontuacao`:**
- `SIM_POSITIVO` e `GRUPO_PROPORCIONAL`: vazia.
- `CATEGORICO_ESCALONADO` com 1 variável: `Ativa=1; Em manutenção ou reestruturação=0,5; Não possui página=0` (resposta exata do IBGE = pontos).
- Várias variáveis (formato de publicação, escada de canais): `mtic172=1; mtic171=0,5; mtic175=0,25` (pontos quando a variável é "Sim"; vale a maior).

**Edição nova (ex.: 2026):** filtrar `edicao = 2024` nas abas Dimensoes, Itens e Niveis, copiar as linhas, colar no fim, trocar o ano e editar o que mudou.

## Validar e gerar os CSVs

```bash
python config/radar/validar_radar.py --dados 2024=caminho/Base_MUNIC_2024_20251107.xlsx --dados 2019=caminho/Base_MUNIC_2019_20210817.xlsx
```

Cada edição é validada isoladamente. Enquanto houver ERRO, nenhum CSV é gerado. A mensagem diz a edição, a aba e a linha do Excel. Exemplos:

```
[ERRO]  2026: a ordem das dimensões deve ser 1, 2, 3… sem buracos nem repetições (encontrado: 1, 4)
[ERRO]  2026, Itens linha 122 ('Alvará online'): usa a dimensão 'Servicos digitais', que não existe em 2026 — você quis dizer 'Serviços digitais'?
[ERRO]  2026: a dimensão 'Governo aberto' entra no IMDM mas não tem nenhum item
[ERRO]  2026, Itens linha 123 ('Página ativa'): pontuação — pontos não numéricos em 'Não possui página=dois'
```

O que é conferido em cada edição:
- **Dimensões:** nomes únicos, ordem 1…n sem buracos, peso maior que 0, `entra_no_imdm` sim/nao, pelo menos uma no IMDM, e toda dimensão do IMDM com pelo menos um item.
- **Itens:**
  - nome único e dimensão existente na mesma edição (com sugestão quando o nome está quase certo);
  - códigos no padrão `mtic…`/`mgov…` e nenhuma variável em dois itens;
  - regra e exceção da lista, número de variáveis compatível com a regra;
  - pontuação bem escrita, entre 0 e 1 e cobrindo todas as variáveis do item.
- **Níveis:** faixas de 0 a 100, sem buracos nem sobreposição.
- **Com `--dados`:** todo código existe na base daquele ano, e toda resposta dos itens escalonados tem pontuação (um rótulo novo do IBGE não vira 0 silencioso).

O que o script **não** pega é um erro de conteúdo que parece válido, como um código que existe mas é o errado ou um item na dimensão errada. Isso fica para a revisão no PR, apoiada pela aba Historico.

Precisa de `pandas` e `openpyxl`. Os CSVs em `csv/` são **gerados, não edite à mão**; faça commit deles junto com a planilha.

## Mudou o radar? O passo a passo

1. **Editar** `radar_imdm.xlsx` (só as linhas da edição que mudou) e registrar a mudança na aba Historico.
2. **Validar e gerar os CSVs** com o comando acima. Corrija até não sobrar nenhum ERRO.
3. **Commit** da planilha **e** da pasta `csv/` (os dois juntos) e push.
4. **No Databricks:** Pull na pasta Git → **Deploy** no painel do foguete (o job lê a cópia publicada, não a pasta Git).
5. **Rodar o job** `job_munic_pipeline` com `reference_year` = cada edição que mudou (um Run now por edição, nunca em paralelo). As outras edições não precisam rodar.
6. **No app:** botão **Recarregar dados** na barra lateral (ou esperar o cache de 12 h).

O que acontece por baixo: o `load_radar_config` regrava as tabelas `config.radar_*`; o `silver_to_gold` recalcula itens, dimensões e IMDM da edição (dimensões que saíram ou mudaram de nome são removidas da gold daquela edição); o `gold_to_semantic` refaz as tabelas do dashboard. O app não precisa de deploy: ele lê o número de dimensões, os nomes e os itens das tabelas.

## No Databricks

O notebook `pipeline/load_radar_config` lê os CSVs do próprio Git folder e valida o radar da edição do job (`reference_year`) com as mesmas regras e contra a silver daquele ano. Depois grava as tabelas `munic_catalog.config`:

| Tabela | Uma linha por | Uso |
|---|---|---|
| `radar_dimensao` | edição × dimensão | eixos do radar (nome, ordem, peso, entra no IMDM, `dimensao_codigo`) |
| `radar_item` | edição × item | como na planilha |
| `radar_variavel` | edição × item × variável | o join do `silver_to_gold`: `cod_variable` → item, dimensão, regra, `e_ancora` |
| `radar_pontuacao` | edição × item × variável × resposta | pontos por rótulo |
| `radar_nivel` | edição × nível | faixas do `nivel_maturidade_mmd` |

Toda linha carrega `radar_sha256` (hash da planilha) e `carregado_em`; as versões anteriores ficam no `DESCRIBE HISTORY`. O ledger recebe a linha `radar` × edição.

## Versão inicial

- **2024:** igual ao radar fixo do `silver_to_gold` (branch `feat/multi-edicao`): 5 dimensões, 64 itens (7/11/26/16/4), mesmas âncoras, regras e variáveis (conferido item a item).
- **2019:** 4 dimensões (o bloco de LGPD não foi coletado), 55 itens.
  - Serviços online com os códigos de 2019 (`mtic124`–`127`, `mtic1210`–`1218`).
  - Sem `mtic091`/`092` (2019 só tem o `mtic09`) e sem `mtic18a2`/`a3`.
  - Sem o item de WhatsApp: em 2019 o `mtic014` pergunta "atendimento pela Internet".
  - Rótulos de 2019 em `mgov09` e `mtic29`. Os demais rótulos escalonados de 2019 ainda precisam ser conferidos com `--dados 2019=...`.

## Como o pipeline usa o radar

Job: `… bronze_to_silver → load_radar_config → silver_to_gold → gold_to_semantic`.

- `silver_to_gold` (Step 3) lê os itens da edição em `config.radar_variavel`; o Step 6 calcula os itens por regra com os pontos de `config.radar_pontuacao` (nenhum código de variável fixo no notebook).
- A gold grava `fact_score_dimensao` (município × dimensão da edição) e a `fact_imdm_municipio` com o IMDM = média ponderada pelos pesos da aba Dimensoes, só das dimensões com `entra_no_imdm = sim`; o nível vem da aba Niveis.
- `gold_to_semantic` publica as views do dashboard, todas com `ano_edicao` e sem número fixo de dimensões.
