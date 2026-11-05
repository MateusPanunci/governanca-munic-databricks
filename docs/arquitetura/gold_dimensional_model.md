# Especificação do Modelo Dimensional, Regras de Pontuação e Camada Semântica (Etapa 3)

- **Projeto:** Índice de Maturidade Digital Municipal (IMDM) — MUNIC 2024 (SGD/MGI)
- **Catálogo Unity Catalog:** `munic_catalog`
- **Schemas Alvo:** `silver` (ajuste de pré-requisito), `gold` e `semantic`
- **Alinhamento de Governança:** COBIT 2019 (APO03.02, APO14.02, APO14.03, APO14.07, BAI03.02, MEA01.03) e CMMI-DMM (Modelo de Maturidade de Dados)

---

## 1. Contexto e Decisões de Arquitetura (Pós-Revisão e Achados da Etapa 2)

A modelagem dimensional da Etapa 3 apoia-se diretamente nas evidências empíricas produzidas na Etapa 2 sobre a base `Base_MUNIC_2024_20251107.xlsx` (**5.570** municípios × **360** variáveis temáticas = **2.005.200** observações, sendo **198** de `Informática e comunicação` e **162** de `Governança`):

1. **Reversão do Cast Destrutivo na Camada Silver (Pré-requisito Crítico de Acurácia e Completude):**

   * Na Etapa 2 (Seção 3.1), comprovou-se que as **2.005.200** células dividem-se em **6 estados mutuamente exclusivos**:
     * Resposta válida (`Sim`, `Não`, categorias ou texto): **1.493.935** (74,50%)
     * Não aplicável (`-`, ausência estrutural por salto lógico/*skip-logic* em 207 colunas): **500.916** (24,98%)
     * `Não informou`: **4.413** (0,22%)
     * `Não sabe informar`: **3.416** (0,17% — concentrado no bloco de LGPD, como `mgov32` com 857 municípios)
     * `Recusa`: **2.520** (0,13% — exatamente os 7 municípios recusantes: Xapuri/AC, Colares/PA, Vigia/PA, Buriti/MA, Carolina/MA, Santa Cecília/SC e Bagé/RS)
     * Nulo técnico: **0** (0,00%)
   * Converter cegamente os códigos de ausência para `NULL` e as respostas para `boolean` na camada Silver apaga a evidência de acurácia validada contra o IBGE e impede distinguir quem **não sabe informar sobre LGPD** (indicador real de baixa maturidade institucional) de quem **sofreu salto lógico (`-`)**. A Silver passa a preservar o texto original limpo.
2. **Separação entre Fato Analítica de BI (`fact_imdm_municipio`) e Fato de Auditoria (`fact_resposta`):**

   * Uma tabela despivotada de **2.005.200** linhas contendo strings (`"Sim"`, `"Não"`) configura um padrão EAV (*Entity-Attribute-Value*) sem medidas aditivas diretas e excede o limite de **100.000** linhas por dataset dos painéis AI/BI do Databricks.
   * Portanto, `fact_imdm_municipio` (**5.570** linhas, com scores numéricos aditivos e cluster) assume o papel de **fato central do dashboard**, enquanto `fact_resposta` (**2.005.200** linhas) assume o papel de **rastreabilidade e auditoria por variável**.
3. **Construção Automatizada da `dim_indicador` a partir dos Artefatos da Etapa 2:**

   * Em vez de montar metadados do zero, a `dim_indicador` reutiliza via `JOIN` os ativos já materializados na Etapa 2 (`silver.munic_clean_dict`, `gold.dq_column_profile` e `gold.dq_skiplogic_candidates`), incorporando as correções documentais descobertas pelo grupo (as 7 variáveis reconstruídas ausentes do dicionário original do IBGE e a correção semântica de `mtic30` de "educação" para "comunicação").

---

## 1.1. Checklist de Reajustes Obrigatórios antes de Codar o `silver_to_gold` (Plano de Transição)

Para que o notebook `pipeline/silver_to_gold` execute sem falhas de tipagem ou perda de linhagem, os seguintes reajustes técnicos devem ser aplicados na infraestrutura atual:

### Ajuste 1: Refatoração da Função `treat_survey_indicators` no Notebook `bronze_to_silver`

* **Como estava na Etapa 2:** As colunas classificadas como binárias (`{"Sim", "Não"}`) sofriam cast para `BooleanType` (`true`/`false`), e os 4 códigos de ausência (`"-"`, `"Recusa"`, `"Não informou"`, `"Não sabe informar"`) eram todos convertidos para `NULL`.
* **O que mudar na Silver agora:**
  1. Manter todas as **360** colunas de indicadores como `StringType` higienizadas com `F.trim()`, preservando os **6 estados textuais originais** (`"Sim"`, `"Não"`, `"-"`, `"Não sabe informar"`, `"Não informou"`, `"Recusa"`).
  2. Converter para `NULL` apenas eventuais strings vazias `""` ou espaços em branco puros.
  3. Reexecutar o `bronze_to_silver` com `.option("overwriteSchema", "true")` e registrar no `userMetadata`: `"Refatoracao Pos-Revisao Etapa 3: Preservacao dos 6 estados originais da MUNIC"`.
  4. **Validação imediata pós-ajuste:** Garantir que a soma de células com valor `"Recusa"` na `silver.munic_clean_data` volte a ser exatamente **2.520** (7 municípios × 360 variáveis).

### Ajuste 2: Consolidação do Dicionário Silver (`silver.munic_clean_dict`) com os Achados de Qualidade

* **Como estava na Etapa 2:** A tabela `silver.munic_clean_dict` continha apenas `cod_variable`, `ano_edicao` e `meaning` extraídos da aba Dicionário da Bronze (onde faltavam 7 variáveis existentes nos dados e sobravam 5 códigos sem coluna), enquanto o perfilamento completo das 360 variáveis reais estava em `gold.dq_column_profile`.
* **O que mudar na passagem para a Gold:**
  1. Na criação da `gold.dim_indicador`, usar a lista oficial das **360 colunas de indicadores presentes em `silver.munic_clean_data`** (via `gold.dq_column_profile`) como base esquerda do `JOIN`.
  2. Garantir que as **7 variáveis reconstruídas na Etapa 2** (`mtic11`, `mtic31`, `mtic331`, `mtic2421`, `mtic2431`, `mgov141`, `mgov142`) e a correção textual de `mtic30` (Comunicação em vez de Educação) estejam preenchidas sem `NULL` na coluna `meaning`.
  3. Descartar os 5 códigos fantasmas do dicionário do IBGE que não possuem coluna nas abas de dados.

### Ajuste 3: Reorganização Lógica do Schema `gold` e Criação do Schema `semantic`

* **Situação atual do catálogo:** O schema `munic_catalog.gold` já armazena as 4 tabelas de diagnóstico da Etapa 2 (`dq_column_profile`, `dq_dimension_summary`, `dq_nonresponse_by_size`, `dq_skiplogic_candidates`).
* **O que preparar no ambiente (`environment/env_variables`):**
  1. Manter as tabelas `dq_*` intactas (pois `dq_column_profile` e `dq_skiplogic_candidates` serão lidas pelo `silver_to_gold` para enriquecer a `dim_indicador` automaticamente).
  2. Garantir a criação do schema `CREATE SCHEMA IF NOT EXISTS munic_catalog.semantic;` no arquivo de configuração de ambiente para receber as views agregadas do notebook `gold_to_semantic`.

---

## 2. Diagrama Entidade-Relacionamento (Modelo Físico/Lógico Gold)

```mermaid
erDiagram
    dim_municipio ||--o{ fact_imdm_municipio : "possui scores (1:N)"
    dim_municipio ||--o{ fact_resposta : "responde (1:N)"
    dim_indicador ||--o{ fact_resposta : "parametriza e explica (1:N)"

    dim_municipio {
        string cod_ibge PK "Codigo IBGE 7 digitos (PK Composta)"
        int ano_edicao PK "Ano da edicao (PK Composta e particao)"
        string nome "Nome do municipio"
        string uf_sigla "Sigla da UF (ex PR, SP)"
        string regiao "Grande Regiao do IBGE"
        long populacao_total "Populacao estimada"
        string faixa_populacao "7 faixas originais do IBGE"
        string porte_municipio "Derivado Pequeno I/II, Medio, Grande I/II"
    }

    dim_indicador {
        string cod_variable PK "Codigo em snake_case (360 variaveis)"
        int ano_edicao PK "Ano da edicao (PK Composta)"
        string meaning "Significado validado (IBGE + 7 reconstruidas na Etapa 2)"
        string origem_significado "Herdado de dq_column_profile (IBGE ou Reconstruido)"
        string tema "Modulo tematico TIC (198) ou GOV (162)"
        string tipo_resposta "Binario (332), Categorico (19) ou Texto livre (9)"
        string grupo_pergunta "Variavel-pai de salto logico (dq_skiplogic_candidates / regex)"
        string dimensao_imdm "Dimensao do indice (D1_Infra_Acesso, D2_Transparencia, D3_Servicos, D4_Controle_Participacao, D5_LGPD, Nao_Pontua)"
        string item_imdm "Item pontuado do radar (agrupa variaveis de um mesmo item; NULL se Nao_Pontua)"
        double peso_indicador "Peso do item na dimensao (1.0 para todos; pesos iguais)"
        string regra_pontuacao "SIM_POSITIVO, CATEGORICO_ESCALONADO, ESCADA_MAIOR_NIVEL, GRUPO_PROPORCIONAL, NAO_PONTUA"
    }

    fact_imdm_municipio {
        string cod_ibge PK,FK "FK para dim_municipio (Grao 5.570 linhas)"
        int ano_edicao PK "Particao e chave temporal (2024)"
        string motivo_imdm_nulo "Recusa, Sem_Item_Valido ou NULL quando o IMDM e calculado"
        double score_d1_infra_acesso "D1 Infraestrutura, capacidade de TIC e acesso digital (0 a 100)"
        double score_d2_transparencia "D2 Transparencia ativa e dados abertos (0 a 100)"
        double score_d3_servicos_digitais "D3 Servicos digitais ao cidadao (0 a 100)"
        double score_d4_controle_participacao "D4 Controle interno e participacao (0 a 100)"
        double score_d5_lgpd "D5 Protecao de dados pessoais LGPD (0 a 100)"
        double score_global_imdm "Indice Geral de Maturidade Digital (0 a 100)"
        string nivel_maturidade_mmd "Estagio MMD (1-Incipiente, 2-Basico, 3-Intermediario, 4-Avancado)"
    }

    fact_resposta {
        string cod_ibge PK,FK "FK para dim_municipio (Grao 2.005.200 linhas)"
        string cod_variable PK,FK "FK para dim_indicador"
        int ano_edicao PK,FK "Particao e FK composta para dim_indicador"
        string resposta_original "Valor bruto preservado (6 estados Sim, Nao, -, Recusa, etc)"
        string resposta_normalizada "Valor padronizado para calculo ('1', '0', categoria ou NULL)"
        string classe_preenchimento "Valida, Nao_Aplicavel_Skip, Nao_Sabe, Nao_Informou, Recusa"
        double pontos_obtidos "Pontuacao calculada apos JOIN com dim_indicador"
        double peso_aplicado "Peso no denominador efetivo (NULL para Nao sabe, Nao se aplica e Recusa)"
    }
```

---

## 3. Especificação Detalhada das Tabelas

### 3.1. Dimensão Município (`munic_catalog.gold.dim_municipio`)

* **Granularidade:** 1 linha por município (5.570 linhas).
* **Origem:** Colunas cadastrais e descritivas de `silver.munic_clean_data`.
* **Regra de Derivação (`porte_municipio`):**
  * `Pequeno I`: até 20.000 habitantes.
  * `Pequeno II`: de 20.001 a 50.000 habitantes.
  * `Médio`: de 50.001 a 100.000 habitantes.
  * `Grande I`: de 100.001 a 500.000 habitantes.
  * `Grande II`: mais de 500.000 habitantes.

---

### 3.2. Dimensão Indicador e Regras de Negócio (`munic_catalog.gold.dim_indicador`)

* **Granularidade:** 1 linha por variável por edição (360 linhas por edição para 2024: 198 de TIC e 162 de GOV).
* **Chave Primária Composta:** `(cod_variable, ano_edicao)`.
* **Papel na Governança:** Atua simultaneamente como Glossário de Negócios Ativo (COBIT APO14.02) e Tabela de Parametrização de Cálculo. Alterar o peso ou a regra de um indicador exige apenas atualizar esta tabela, mantendo o código do pipeline imutável.

#### 3.2.1. Linhagem e Origem de Cada Atributo da `dim_indicador`

| Coluna na `dim_indicador`      | Fonte / Tabela de Origem                                      | Como é Obtida (Regra Técnica)                                                                                                                                                                                                                                                                                                                                                      |
| :------------------------------- | :------------------------------------------------------------ | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **`cod_variable`** (PK)  | `silver.munic_clean_dict` ⋈ `gold.dq_column_profile`     | Código padronizado em minúsculas (`mtic011` a `mgov36`). Garante a cobertura exata das 360 variáveis dos dados.                                                                                                                                                                                                                                                               |
| **`ano_edicao`** (PK)    | `silver.munic_clean_dict`                                   | Inteiro `2024` (compõe a chave primária para suportar evolução semântica entre edições).                                                                                                                                                                                                                                                                                    |
| **`meaning`**            | `gold.dq_column_profile.significado`                        | Incorpora as descrições do IBGE + as **7 variáveis reconstruídas na Etapa 2** (`mtic11`, `mtic31`, `mtic331`, `mtic2421`, `mtic2431`, `mgov141`, `mgov142`) + a correção documental de `mtic30` (Comunicação).                                                                                                                                         |
| **`origem_significado`** | `gold.dq_column_profile.origem_significado`                 | Rastreia se o significado veio do dicionário oficial do IBGE ou da reconstrução analítica da Etapa 2.                                                                                                                                                                                                                                                                            |
| **`tema`**               | Derivada via prefixo de `cod_variable`                      | `WHEN startswith('mtic') THEN 'TIC'` (198 variáveis) `WHEN startswith('mgov') THEN 'GOV'` (162 variáveis).                                                                                                                                                                                                                                                                     |
| **`tipo_detectado`**     | `gold.dq_column_profile.tipo_detectado`                     | Classificação empírica da Etapa 2: `Binário` (332), `Categórico` (19) ou `Texto livre` (9).                                                                                                                                                                                                                                                                               |
| **`grupo_pergunta`**     | `gold.dq_skiplogic_candidates.coluna_pai_candidata` + Regex | Se a variável possui pai confirmado na tabela `dq_skiplogic_candidates` (133 relações determinísticas/confirmadas), usa `coluna_pai_candidata` (ex.: `mgov33` → `mgov32`; `mtic23` → `mtic22`); caso contrário, extrai o radical por regex (`mtic12a1` → `mtic12`).                                                                                          |
| **`dimensao_imdm`**      | Mapeamento de Regra de Negócio (`docs/radar_imdm.md`)      | Classifica cada variável em uma das 5 dimensões do IMDM (D1 a D5) ou `Nao_Pontua`.                                                                                                                                                                                                                                                                                               |
| **`item_imdm`**          | Mapeamento de Regra de Negócio (`docs/radar_imdm.md`)      | Identifica o item pontuado ao qual a variável pertence. A maioria dos itens tem uma variável só; alguns combinam várias: formato de publicação (`mgov0711`–`0715`, …, `mgov0761`–`0765`), canal de solicitação (`mtic171`–`176`), grupos A e B do conteúdo do portal (`mgov081`–`089`) e `mgov05` (que depende de `mgov04`). O radar tem 64 itens. |
| **`peso_indicador`**     | Mapeamento de Regra de Negócio (`docs/radar_imdm.md`)      | Peso do item dentro da sua dimensão. No radar atual, `1.0` para todos (pesos iguais; cada item vale no máximo 1 ponto).                                                                                                                                                                                                                                                          |
| **`regra_pontuacao`**    | Mapeamento baseado em `tipo_detectado` + Semântica         | Define qual das 5 fórmulas matemáticas converte a resposta em pontos.                                                                                                                                                                                                                                                                                                              |

> **Itens com várias variáveis:** o cálculo é feito por `item_imdm` no `silver_to_gold`. Na `fact_resposta`, `pontos_obtidos` e `peso_aplicado` desses itens ficam na primeira variável do item (ex.: `mgov0711`); as demais variáveis do item mantêm o estado original para auditoria, com essas duas colunas em `NULL`.

#### 3.2.2. As 5 Categorias Formais de `regra_pontuacao`

| Categoria (`regra_pontuacao`) | Volume Alvo | Lógica Matemática de Pontuação (`pontos_obtidos`) | Exemplos Reais na Base MUNIC 2024 |
| :--- | :---: | :--- | :--- |
| **1. `SIM_POSITIVO`** | 51 dos 64 itens | • `"Sim"` → 1.0 × peso<br>• `"Não"`, `"-"`, `"Não sabe informar"` e `"Não informou"` → 0.0 (conta no denominador) | • `mgov32` (Responsável pela LGPD)<br>• `mtic06` (Estrutura de TI)<br>• `mtic251` (Consulta pública online) |
| **2. `CATEGORICO_ESCALONADO`** | 10 itens | • Nível pleno → 1.0 × peso<br>• Nível parcial → 0.5 × peso<br>• Ausência / Não / Não sabe / Não informou → 0.0 | • `mgov09`: com instrumento legal = 1; sem = 0,5; Não = 0<br>• `mgov05`: perguntas e respostas = 1; só respostas = 0,5; não publica = 0 (não se aplica se `mgov04` = Não e não publica)<br>• `mtic10`: ativa = 1; em manutenção = 0,5; em elaboração ou não possui = 0<br>• `mtic29`: modelo oficial (federal, global ou estadual) = 1; próprio = 0,5; nenhum = 0<br>• Formato de publicação (`mgov07X1`–`X5`, 6 itens): aberto = 1; só PDF/imagem/outro = 0,5; não publica = 0 |
| **3. `ESCADA_MAIOR_NIVEL`** | 1 item | • Item formado por opções de múltipla escolha; vale o maior nível marcado. | • Canal de solicitação (`mtic171`–`176`): site da prefeitura ou app = 1; telefone ou outro website = 0,5; só redes sociais = 0,25; nenhum = 0 |
| **4. `GRUPO_PROPORCIONAL`** | 2 itens | • Fração de `"Sim"` entre as variáveis do grupo (0 a 1) × peso. | • Grupo A: informações institucionais e atendimento (`mgov081`–`084`, `mgov088`)<br>• Grupo B: execução e controle social (`mgov085`, `086`, `087`, `089`) |
| **5. `NAO_PONTUA`** | Demais variáveis | • `pontos_obtidos` = NULL<br>• `peso_aplicado` = NULL (Fora do denominador do índice) | • `mtic11` (URL do site)<br>• `mtic31` (Nome do órgão de comunicação)<br>• `mgov33` (Localização do responsável pela LGPD — atributo descritivo)<br>• `mtic271` (Portal da transparência — 99,7% têm)<br>• `mgov15` / `mgov16` (Vínculo e formação — proteção ética/LGPD da Seção 5.1) |                                                                                                                                |

---

### 3.3. Fato de Rastreabilidade e Auditoria (`munic_catalog.gold.fact_resposta`)

* **Granularidade:** Município × Variável × Edição (5.570 municípios × 360 variáveis = 2.005.200 linhas).
* **Finalidade no Modelo:** Atua como a camada de detalhamento atômico, auditoria analítica e memória de cálculo do projeto. **Não é consumida diretamente em varreduras massivas pelo dashboard visual de BI**, servindo para responder a consultas analíticas pontuais (*drill-down*) e rastrear como a nota de cada cidade foi composta indicador por indicador.

#### 3.3.1. Papel e Finalidade da Coluna `classe_preenchimento`

A coluna `classe_preenchimento` opera exclusivamente no grão atômico da `fact_resposta` (nível célula/registro) e **não deve ser confundida com a tipagem da variável** (como `tipo_detectado` ou `tema`, que pertencem à dimensão `dim_indicador` e descrevem a pergunta no questionário).

Enquanto a `dim_indicador` caracteriza a *natureza estrutural do indicador*, a `classe_preenchimento` registra o **estado de qualidade do preenchimento observado naquele município específico**, traduzindo o conteúdo de `resposta_original` em uma das 5 categorias mutuamente exclusivas validadas no diagnóstico da Etapa 2:

1. **`Valida`:** O município efetivamente prestou informação utilizável (`"Sim"`, `"Não"`, texto livre ou categoria). Corresponde a 1.493.935 células (74,50% da base).
2. **`Nao_Aplicavel_Skip`:** A pergunta não se aplicava ao município em decorrência de salto lógico (*skip-logic*, assinalado pelo código `"-"` na base original). Corresponde a 500.916 células (24,98% da base), distribuídas em 207 das 360 colunas.
3. **`Nao_Sabe`:** O respondente declarou explicitamente `"Não sabe informar"`. Concentrado em perguntas de governança e dados (857 municípios em `mgov32`).
4. **`Nao_Informou`:** A prefeitura deixou a pergunta sem preenchimento (`"Não informou"`).
5. **`Recusa`:** O município recusou formalmente a pesquisa censitária. Corresponde a exatamente 2.520 células (os 7 municípios recusantes nomeados pelo IBGE × 360 variáveis).

#### 3.3.2. Para que a `classe_preenchimento` é Utilizada na Prática?

A existência dessa coluna na tabela fato atende a duas funções operacionais e de governança:

- **1. Simplificação e Padronização de Consultas SQL de Auditoria:** Desacopla os testes de completude e qualidade do formato da resposta. Em vez de criar rotinas com múltiplos filtros de string (`WHERE resposta = '...' OR resposta IS NULL`), a verificação de taxas de resposta e a auditoria dos dados tornam-se operações diretas:

  ```sql
  -- Exemplo: Diagnóstico de preenchimento por indicador via SQL
  SELECT 
      cod_variable,
      COUNT_IF(classe_preenchimento = 'Valida') AS total_respostas_validas,
      COUNT_IF(classe_preenchimento = 'Nao_Aplicavel_Skip') AS total_saltos_logicos,
      COUNT_IF(classe_preenchimento = 'Nao_Sabe') AS total_desconhecimento,
      COUNT_IF(classe_preenchimento = 'Recusa') AS total_recusas
  FROM munic_catalog.gold.fact_resposta
  GROUP BY cod_variable;
  ```
* **2. Controle Preciso do Denominador Efetivo nas Métricas (Mitigação de Vieses):**

  Na consolidação de taxas de adoção de serviços ou cálculo dos sub-índices na `fact_imdm_municipio`, a coluna orienta o cômputo:

    * **Em saltos lógicos (`Nao_Aplicavel_Skip`):** o `-` decorre da ausência da estrutura-mãe. Como os desdobramentos distorcivos foram expurgados no Radar, a ausência de capacidade pontua 0.0 e o `peso_aplicado` permanece ativo no denominador.
    * **Em declarações de desconhecimento (`Nao_Sabe`):** atesta falta de governança interna; pontua 0.0 e o `peso_aplicado` permanece ativo no denominador, evitando inflar a média de municípios desorganizados.
    * **Em omissões pontuais (`Nao_Informou`):** a pergunta obrigatória não foi respondida; pontua 0.0 e permanece ativa no denominador (`peso_aplicado = peso`), penalizando apenas o quesito omitido sem anular o município inteiro.
    * **Em "não se aplica" legítimo (`mgov05`):** quando o município não recebeu pedido pela LAI (`mgov04 = Não`) e não publica, não havia o que publicar. O item sai do denominador (`peso_aplicado = NULL`).
    * **Em recusas formais ao censo (`Recusa`):** ausência total de coleta; município fica com IMDM NULL (`motivo_imdm_nulo = 'Recusa'`).

#### 3.3.3. Semântica de Pontuação dos 6 Estados e Tratamento do Denominador Efetivo

| `resposta_original` | `classe_preenchimento` | `resposta_normalizada` | `pontos_obtidos` | `peso_aplicado` | Tratamento e Justificativa de Governança |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **`Sim`** | `Valida` | `'1'` | 1.0 × peso | peso | Comprova a existência da capacidade/serviço. |
| **`Não`** | `Valida` | `'0'` | 0.0 | peso | Declaração explícita de ausência da capacidade/serviço. |
| **`Não sabe informar`** | `Nao_Sabe` | `'0'` | 0.0 | peso | Declaração expressa de desconhecimento atesta ausência de controle institucional. Permanece no divisor para mitigar viés otimista. |
| **`Não informou`** | `Nao_Informou` | `'0'` | 0.0 | peso | Omissão pontual em pergunta obrigatória pontua zero no quesito com divisor ativo, eliminando incentivo à não-resposta estratégica. |
| **`-` (Salto Lógico)** | `Nao_Aplicavel_Skip` | `'0'` | 0.0 | peso | Decorre da ausência da infraestrutura-mãe. Como os itens distorcivos foram excluídos no Radar, vale zero e permanece no divisor. |
| **`Recusa`** | `Recusa` | `NULL` | NULL | NULL | Município fica com IMDM NULL (`motivo_imdm_nulo = 'Recusa'`); preserva a evidência externa das 7 recusas formais do censo. |
| **`Não publica` em `mgov05` com `mgov04` = `Não`** | `Valida` | `NULL` | NULL | NULL | "Não se aplica" legítimo: o município não recebeu pedidos pela LAI e não tinha o que publicar; sai do denominador. |                     |

---

### 3.4. Fato Principal do Dashboard (`munic_catalog.gold.fact_imdm_municipio`)

* **Granularidade:** 1 linha por município por edição (5.570 linhas).
* **Finalidade:** Tabela fato analítica principal com medidas numéricas aditivas contínuas (scores de 0 a 100), rótulo do cluster K-Means e estágio de maturidade institucional.
* **Performance:** Com apenas 5.570 registros, opera com máxima fluidez e interatividade instantânea dentro do limite de 100.000 linhas por dataset do Databricks AI/BI Dashboards.
* **Fórmula de Agregação (por dimensão d para o município i):**
  Score_{i, d} = ( Σ pontos_obtidos_{i, d} / Σ peso_aplicado_{i, d} ) × 100
* **Índice Global Consolidado:**
  IMDM_i = ( Score_D1 + Score_D2 + Score_D3 + Score_D4 + Score_D5 ) / 5
* **Casos com IMDM NULL:** Restrito exclusivamente aos 7 municípios com Recusa formal censitária documentada pelo IBGE (`motivo_imdm_nulo = 'Recusa'`). Todos os demais 5.563 municípios recebem pontuação e classificação regular no índice.

---

## 4. Integração com o Modelo de Maturidade de Dados (MMD)

A tabela `fact_imdm_municipio` sintetiza as cinco dimensões do radar IMDM, inspiradas no CMMI-DMM e em diretrizes da SGD/MGI. A lista completa de itens, regras e distribuições está em `docs/radar_imdm.md`, que é a referência única do índice:

1. **D1 — Infraestrutura, capacidade de TIC e acesso digital (`score_d1_infra_acesso`, 7 itens):** estrutura de TI, CPD, equipe própria, desenvolvimento de software, inclusão digital e Wi-Fi público.
2. **D2 — Transparência ativa e dados abertos (`score_d2_transparencia`, 11 itens):** lei de acesso à informação, execução orçamentária em tempo real, formato de publicação dos dados, portal de dados abertos e conteúdo do portal.
3. **D3 — Serviços digitais ao cidadão (`score_d3_servicos_digitais`, 26 itens):** página da prefeitura, serviços online, serviços por celular, autenticação, canais de solicitação e atendimento e acessibilidade.
4. **D4 — Controle interno e participação (`score_d4_controle_participacao`, 16 itens):** estrutura e funções de controle interno, carreira de auditor, publicação de pedidos pela LAI e participação online do cidadão.
5. **D5 — Proteção de dados pessoais / LGPD (`score_d5_lgpd`, 4 itens):** responsável pela LGPD, capacitação, canal ao cidadão e regulamentação municipal.

### Escala de Maturidade (`nivel_maturidade_mmd`) e Mitigação Ética de Vieses

Como 87,88% dos municípios possuem até 50 mil habitantes e a pesquisa possui natureza declaratória, o índice veda ranqueamentos punitivos interportes. A classificação em 4 estágios formais é sempre analisada de forma estratificada por porte populacional:

* **Nível 1 — Incipiente:** Ausência de estrutura formal de TI e desconhecimento/inexistência de controles de LGPD e transparência.
* **Nível 2 — Básico (Iniciado):** Infraestrutura elementar e atendimento inicial, mas governança de dados e LGPD informais ou incompletas.
* **Nível 3 — Intermediário (Gerenciado):** Serviços digitais ativos, regulamentação de LAI/transparência e responsável designado para LGPD.
* **Nível 4 — Avançado (Otimizado):** Alta maturidade transversal nas 5 dimensões (governança institucionalizada, capacitação em segurança, canais de dados pessoais e participação digital).

---

## 5. Camada Semântica (`munic_catalog.semantic`) — Especificação Preliminar

O consumo analítico pelo Databricks AI/BI Dashboard é desenhado para ocorrer a partir do schema `semantic`, preservando a separação de responsabilidades (COBIT APO14/MEA01): os usuários e relatórios consultam métricas de negócio pré-calculadas e visões de consumo, sem varredura direta na base atômica não agregada.

As views abaixo representam o **contrato conceitual inicial sugerido** para guiar a construção do painel, sujeitas a refinamentos operacionais durante a prototipagem no BI:

| View Sugerida                                | Granularidade                | Finalidade Proposta para o Dashboard                                                                                                        |
| :------------------------------------------- | :--------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------ |
| **`semantic.vw_painel_municipio`**   | 5.570 linhas                 | Visão consolidada por prefeitura (scores temáticos, IMDM global, cluster e porte) para compor a tabela e os filtros principais do painel. |
| **`semantic.agg_imdm_porte_regiao`** | Região × Porte             | Agregação por estratos para alimentar gráficos de comparação justa e diagnóstico regional de assimetrias.                             |
| **`semantic.agg_adocao_indicador`**  | Indicador × UF/Região      | Taxa percentual de resposta afirmativa calculada sobre o denominador efetivo de respondentes elegíveis.                                    |
| **`semantic.vw_auditoria_lgpd`**     | Município × Questões LGPD | Recorte específico sobre o bloco MGOV32–36 para monitoramento da variável prioritária de proteção de dados.                           |

> **Nota de Colaboração:** A implementação física dessas views no notebook `gold_to_semantic` e a criação de eventuais consultas adicionais serão fechadas e ajustadas diretamente pelo responsável pela camada de visualização/BI.

---

## 6. Controles Automatizados de Qualidade na Transição `silver_to_gold`

1. **Asserção de Volume de Indicadores:** `COUNT(DISTINCT cod_variable) == 360` em `gold.dim_indicador` (198 `TIC` + 162 `GOV`), com 0 variáveis sem regra ou dimensão.
2. **Conservação Exata de Observações:** `COUNT(*) == 2.005.200` em `gold.fact_resposta`, preservando a distribuição exata das 6 classes da Etapa 2 (1.493.935 válidas; 500.916 não aplicáveis `-`; 4.413 não informou; 3.416 não sabe informar; 2.520 recusas).
3. **Preservação da Evidência da Etapa 2 e Isolamento de Municípios sem IMDM:** Exatamente 2.520 células marcadas com Recusa na `gold.fact_resposta`. Na tabela `gold.fact_imdm_municipio`, exatamente 7 registros com `score_global_imdm IS NULL` (`motivo_imdm_nulo = 'Recusa'`), e 5.563 municípios com scores válidos calculados no intervalo [0, 100], eliminando divisões por zero ou descartes indevidos de prefeituras por desinformação.
4. **Integridade Referencial (FK Checks):** 0 registros órfãos entre `fact_resposta` / `fact_imdm_municipio` e as dimensões `dim_municipio` e `dim_indicador`.
5. **Proteção Ética e Privacidade:** As colunas com dados descritivos de servidores (`mgov15` — vínculo e `mgov16` — formação acadêmica) recebem obrigatoriamente `regra_pontuacao = 'NAO_PONTUA'` e não são expostas individualmente em cruzamentos de pequeno porte no dashboard.
