# Radares IMDM — definidos pelo especialista

Os radares não estão escritos no código. Um **radar** (ex.: `A`, `B`) é uma metodologia completa do IMDM e define **todas** as edições da MUNIC (hoje 2019 e 2024) — nunca só um ano. Dentro de um radar, cada edição tem o seu desenho: as próprias dimensões (quantas forem), os próprios itens e os códigos do IBGE daquele ano.

O pipeline calcula **todos os radares** em cada execução, e o dashboard tem um seletor **Radar** (abre no radar com `padrao = sim`). As respostas do IBGE são as mesmas para todos os radares; muda só a forma de pontuar — por isso a comparação entre radares, na mesma edição, mostra só o efeito da metodologia.

| Quem | Decide | Onde |
|---|---|---|
| Especialista de negócio | quais radares existem; em cada radar e edição: dimensões (nome, ordem, peso, entra no IMDM), itens e códigos do IBGE, pontuação das respostas, faixas de maturidade | `radar_imdm.xlsx` |
| Time técnico | as regras de cálculo (Sim = 1, escalonado, escada, grupo, exceção do `mgov05`) e as validações | `validar_radar.py` + `pipeline/` |

## A planilha

As abas são **fixas**; cada linha tem as colunas `radar` e `edicao`. Radar novo ou edição nova = linhas novas, nunca aba nova nem código novo.

| Aba | Uma linha por | Colunas |
|---|---|---|
| Radares | radar | `radar` (código curto: `A`, `B`, `LGPD2`…), `nome`, `descricao`, `padrao` (`sim` em exatamente um) |
| Dimensoes | radar × edição × dimensão | `radar`, `edicao`, `dimensao`, `ordem` (1, 2, 3… sem buracos), `peso`, `entra_no_imdm`, `descricao` |
| Itens | radar × edição × item | `radar`, `edicao`, `dimensao` (nome igual ao da aba Dimensoes, mesmo radar e edição), `item`, `descricao`, `variaveis` (códigos do IBGE separados por `;`, o 1º é a âncora), `regra`, `pontuacao`, `excecao` |
| Niveis | radar × edição × nível | `radar`, `edicao`, `nivel`, `nome`, `minimo`, `maximo` (0 a 100, sem buracos) |
| Listas, Historico, LEIA-ME | — | regras aceitas, registro de mudanças e instruções |

**Coluna `pontuacao`:**
- `SIM_POSITIVO` e `GRUPO_PROPORCIONAL`: vazia.
- `CATEGORICO_ESCALONADO` com 1 variável: `Ativa=1; Em manutenção ou reestruturação=0,5; Não possui página=0` (resposta exata do IBGE = pontos).
- Várias variáveis (formato de publicação, escada de canais): `mtic172=1; mtic171=0,5; mtic175=0,25` (pontos quando a variável é "Sim"; vale a maior).

**Radar novo (ex.: `B`):** na aba Radares, acrescente a linha do `B` (`padrao = nao`). Nas abas Dimensoes, Itens e Niveis, filtre `radar = A`, copie **todas** as linhas (2019 e 2024), cole no fim, troque a coluna `radar` para `B` e edite o que mudou.

**Edição nova (ex.: 2026):** em **cada** radar, filtre a edição 2024 nas abas Dimensoes, Itens e Niveis, copie as linhas, cole no fim, troque o ano e edite o que mudou.

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

1. **Editar** `radar_imdm.xlsx` (as linhas do radar e da edição que mudaram, ou um radar novo inteiro) e registrar a mudança na aba Historico.
2. **Validar e gerar os CSVs** com o comando acima. Corrija até não sobrar nenhum ERRO.
3. **Commit** da planilha **e** da pasta `csv/` (os dois juntos) e push.
4. **No Databricks:** Pull na pasta Git → **Deploy** no painel do foguete (o job lê a cópia publicada, não a pasta Git).
5. **Rodar o job** `job_munic_pipeline` com `reference_year` = cada edição que mudou (um Run now por edição, nunca em paralelo). Cada execução calcula **todos os radares** daquela edição. Radar novo = rodar todas as edições (ou o `job_munic_full_refresh`).
6. **No app:** botão **Recarregar dados** na barra lateral (ou esperar o cache de 12 h).

O que acontece por baixo: o `load_radar_config` regrava as tabelas `config.radar*`; o `silver_to_gold` recalcula pontos, dimensões e IMDM de todos os radares da edição (o que saiu da planilha — radar, item ou dimensão — é apagado da gold daquela edição antes de regravar); o `gold_to_semantic` refaz as tabelas do dashboard. O app não precisa de deploy: ele lê os radares, as dimensões e os itens das tabelas.

## No Databricks

O notebook `pipeline/load_radar_config` lê os CSVs do próprio Git folder e valida **todos os radares** na edição do job (`reference_year`) com as mesmas regras e contra a silver daquele ano. Depois grava as tabelas `munic_catalog.config`:

| Tabela | Uma linha por | Uso |
|---|---|---|
| `radares` | radar | nome, descrição e qual é o padrão do dashboard |
| `radar_dimensao` | radar × edição × dimensão | eixos do radar (nome, ordem, peso, entra no IMDM, `dimensao_codigo`) |
| `radar_item` | radar × edição × item | como na planilha |
| `radar_variavel` | radar × edição × item × variável | o join do `silver_to_gold`: `cod_variable` → item, dimensão, regra, `e_ancora` |
| `radar_pontuacao` | radar × edição × item × variável × resposta | pontos por rótulo |
| `radar_nivel` | radar × edição × nível | faixas do `nivel_maturidade_mmd` |

Toda linha carrega `radar_sha256` (hash da planilha) e `carregado_em`; as versões anteriores ficam no `DESCRIBE HISTORY`. O ledger recebe a linha `radar` × edição (total de itens de todos os radares).

## Versão inicial (Radar A)

- **2024:** igual ao radar fixo do `silver_to_gold` (branch `feat/multi-edicao`): 5 dimensões, 64 itens (7/11/26/16/4), mesmas âncoras, regras e variáveis (conferido item a item).
- **2019:** 4 dimensões (o bloco de LGPD não foi coletado), 55 itens.
  - Serviços online com os códigos de 2019 (`mtic124`–`127`, `mtic1210`–`1218`).
  - Sem `mtic091`/`092` (2019 só tem o `mtic09`) e sem `mtic18a2`/`a3`.
  - Sem o item de WhatsApp: em 2019 o `mtic014` pergunta "atendimento pela Internet".
  - Rótulos de 2019 em `mgov09` e `mtic29`. Os demais rótulos escalonados de 2019 ainda precisam ser conferidos com `--dados 2019=...`.

## Radar B — Seções da MUNIC (IBGE)

Os **mesmos itens, regras e pontuação do Radar A**, só que agrupados pelas seções do questionário da MUNIC/IBGE em vez das 5 dimensões do projeto. Peso 1 em todas as dimensões e as mesmas faixas de nível. Serve para comparar: como o mesmo conjunto de respostas fica quando o índice segue a organização do IBGE. Não é um índice oficial do IBGE.

| Seção do IBGE | Dimensão no Radar B | Itens 2024 | Itens 2019 |
|---|---|---|---|
| 2.1 Formas de atendimento à distância e tipo de conexão | Formas de atendimento à distância | 2 (WhatsApp, telefone exclusivo) | 1 |
| 2.2 Estrutura em TI | Estrutura em TI | 5 | 3 |
| 2.3 Página na internet e redes sociais | Página na internet e redes sociais | 14 | 14 |
| 2.4 Modalidades de atendimento à distância | Atendimento à distância para o cidadão | 9 | 7 |
| 2.5 Programa ou ação de inclusão digital | Inclusão digital | 1 | 1 |
| 2.6 Acesso à internet para a população | Acesso à internet para a população | 1 | 1 |
| 2.7 Formas de participação do cidadão pela internet | Participação do cidadão pela internet | 4 | 4 |
| 2.9 Transparência e acessibilidade digital | Transparência e acessibilidade digital | 2 | 2 |
| 3.1 Acesso à informação | Acesso à informação | 11 | 11 |
| 3.2 Controle interno | Controle interno | 11 | 11 |
| 3.4 LGPD | LGPD | 4 | — (não coletada em 2019) |

Ficam de fora as seções que não têm nenhum item do Radar A: 2.8 (sistemas digitais), 2.10 (comunicação) e 3.3 (conselho de transparência). Para incluí-las, o especialista acrescenta itens dessas seções nas duas edições (conferindo os códigos de 2019 com `--dados 2019=...`). As seções 2.5 e 2.6 têm um item só, então a nota delas é 0 ou 100.

## Como o pipeline usa os radares

Job: `… bronze_to_silver → load_radar_config → silver_to_gold → gold_to_semantic`.

- `fact_resposta`: as respostas do IBGE, **sem radar** (iguais para todos).
- `fact_pontos_item`: pontos e peso de cada item, por **radar × município × item**, calculados por regra com os pontos de `config.radar_pontuacao` (nenhum código de variável fixo no notebook).
- `fact_score_dimensao` (radar × município × dimensão) e `fact_imdm_municipio` (radar × município): IMDM = média ponderada pelos pesos da aba Dimensoes, só das dimensões com `entra_no_imdm = sim`; o nível vem da aba Niveis.
- `gold_to_semantic` publica as tabelas do dashboard, todas com `radar` e `ano_edicao`, mais a `vw_radares` para o seletor.
