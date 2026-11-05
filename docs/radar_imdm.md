# Radar IMDM — Índice de Maturidade Digital Municipal

Base: IBGE MUNIC 2024 (abas `Governanca` e `Informática e comunicação`), 5.570 municípios, 64 itens pontuados (64 pontos possíveis).

## Regras de cálculo

- Cada dimensão = `pontos_obtidos / pontos_possíveis × 100` (escala 0–100).

- **IMDM** = média simples das 5 dimensões (pesos iguais, por enquanto).

- Cada item vale **no máximo 1 ponto**. Itens com mais de dois níveis usam frações (ex.: 1 / 0,5 / 0), conforme a coluna **Regra**.

- `Sim` = 1 ponto (salvo onde indicado na tabela).

- `Não` = 0 (conta no denominador).

- `-` (salto lógico) = 0 (conta no denominador, salvo a exceção em `Mgov05`).

- `Não sabe informar` = **0 pontos e conta no denominador** (declaração de desconhecimento atesta ausência de controle/capacidade institucional e penaliza a maturidade, mantendo o item no divisor para evitar viés otimista).

- `Não informou` = **0 pontos e conta no denominador** (omissão pontual penaliza apenas o quesito específico deixado em branco, evitando incentivo à omissão vantajosa).

- `Não se aplica` = **sai do denominador** (usado só em `Mgov05` quando `Mgov04 = Não`, ver D4).

- Itens em **grupo** (D2, `Mgov081`–`089`) valem a fração de itens `Sim` do grupo (ex.: 3 de 5 = 0,6).

- `Recusa` = IMDM **NULL** (reservado exclusivamente aos 7 municípios com recusa formal censitária documentada pelo IBGE; fora de médias e rankings).


Legenda da coluna **Distribuição**: percentual sobre os 5.570 municípios. "Não sabe" = Não sabe informar; "-" = salto lógico (pergunta não se aplica). Categorias com 0% não aparecem.

---

## [7 pts] D1: Infraestrutura, capacidade de TIC (Tecnologia da Informação e Comunicação) e acesso digital

Mede se a prefeitura tem estrutura, equipe própria e capacidade de desenvolver software, e se leva acesso à internet à população.

| Código     | Significado                                                             | Regra   | Distribuição (n = 5.570)                                                |
| ----------- | ----------------------------------------------------------------------- | ------- | ----------------------------------------------------------------------- |
| `Mtic06`   | Existe estrutura organizacional para a área de TIC?                     | Sim = 1 | Sim 60,0% · Não 39,7% · Não informou 0,1% · Recusa 0,1%                |
| `Mtic08`   | Existe Centro de Processamento de Dados (CPD)?                          | Sim = 1 | Sim 50,4% · Não 49,4% · Não informou 0,1% · Recusa 0,1%                |
| `Mtic071`  | Tem funcionários efetivos da própria prefeitura na TI?                 | Sim = 1 | Sim 32,6% · Não 26,3% · - 40,8% · Não informou 0,1% · Recusa 0,1%       |
| `Mtic091`  | Desenvolveu software (últimos 12 meses) para uso interno / servidores? | Sim = 1 | Sim 24,5% · Não 75,2% · Não informou 0,2% · Recusa 0,1%                |
| `Mtic092`  | Desenvolveu software (últimos 12 meses) para atendimento à sociedade? | Sim = 1 | Sim 11,3% · Não 88,5% · Não informou 0,2% · Recusa 0,1%                |
| `Mtic19`   | Desenvolve programa ou ação de inclusão digital?                      | Sim = 1 | Sim 55,6% · Não 44,2% · Não informou 0,1% · Recusa 0,1%                |
| `Mtic22`   | Disponibiliza acesso à internet por Wi-Fi para a população?          | Sim = 1 | Sim 48,1% · Não 51,7% · Não informou 0,1% · Recusa 0,1%                |

OBSERVAÇÕES:

- `Mtic071`: o `-` vem de quem não tem estrutura de TIC (`Mtic06` = Não), por isso vale 0 e permanece ativo no denominador.

- `Mtic19` e `Mtic22` medem o acesso da população à internet: ensinar a usar e dar acesso.

- `Mtic23` (gratuito ou cobrado) e `Mtic24` (abrangência do Wi-Fi) não pontuam.


---

## [11 pts] D2: Transparência ativa e dados abertos

Mede se a prefeitura publica informação, o que publica no portal e, principalmente, se publica em formato legível por máquina.

| Código             | Significado                                                                                         | Regra                                                    | Distribuição (n = 5.570)                                                                            |
| ------------------- | --------------------------------------------------------------------------------------------------- | -------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| `Mgov01`           | Existe legislação municipal específica sobre acesso à informação (LAI)                         | Sim = 1                                                  | Sim 58,0% · Não 41,7% · Não informou 0,2% · Recusa 0,1%                                            |
| `Mgov061`          | Disponibiliza informações de execução orçamentária e financeira em tempo real                  | Sim = 1                                                  | Sim 66,1% · Não 33,2% · - 0,3% · Não informou 0,3% · Recusa 0,1%                                    |
| `Mgov0711`–`0715`  | Formato de publicação do orçamento                                                                | Aberto = 1; só PDF/imagem/outro = 0,5; não publica = 0   | Aberto 40,1% · Só PDF/imagem/outro 58,3% · Não publica 1,2% · Não informou 0,3% · Recusa 0,1%       |
| `Mgov0721`–`0725`  | Formato de publicação das receitas                                                                 | Aberto = 1; só PDF/imagem/outro = 0,5; não publica = 0   | Aberto 49,4% · Só PDF/imagem/outro 49,1% · Não publica 1,1% · Não informou 0,3% · Recusa 0,1%       |
| `Mgov0731`–`0735`  | Formato de publicação das despesas                                                                 | Aberto = 1; só PDF/imagem/outro = 0,5; não publica = 0   | Aberto 49,6% · Só PDF/imagem/outro 49,1% · Não publica 0,9% · Não informou 0,3% · Recusa 0,1%       |
| `Mgov0741`–`0745`  | Formato de publicação dos balanços                                                                 | Aberto = 1; só PDF/imagem/outro = 0,5; não publica = 0   | Aberto 38,2% · Só PDF/imagem/outro 58,5% · Não publica 2,9% · Não informou 0,3% · Recusa 0,1%       |
| `Mgov0751`–`0755`  | Formato de publicação da prestação de contas (LRF)                                              | Aberto = 1; só PDF/imagem/outro = 0,5; não publica = 0   | Aberto 36,4% · Só PDF/imagem/outro 60,8% · Não publica 2,4% · Não informou 0,3% · Recusa 0,1%       |
| `Mgov0761`–`0765`  | Formato de publicação de compras e licitações                                                   | Aberto = 1; só PDF/imagem/outro = 0,5; não publica = 0   | Aberto 43,7% · Só PDF/imagem/outro 54,9% · Não publica 1,0% · Não informou 0,3% · Recusa 0,1%       |
| `Mtic272`          | Possui portal de dados abertos                                                                      | Sim = 1                                                  | Sim 27,7% · Não 72,0% · - 0,1% · Não informou 0,1% · Recusa 0,1%                                    |
| Grupo A             | Conteúdo do portal: informações institucionais e atendimento (`Mgov081`–`084`, `Mgov088`)          | Fração de Sim dos 5 itens (0 a 1)                       | ver tabela abaixo                                                                                   |
| Grupo B             | Conteúdo do portal: execução e controle social (`Mgov085`, `086`, `087`, `089`)           | Fração de Sim dos 4 itens (0 a 1)                       | ver tabela abaixo                                                                                   |

Legenda do formato: Aberto = `MgovXX1` (CSV, ODS, XLS, DOC); só PDF/imagem/outro = `MgovXX2` ou `MgovXX3` **sem** `MgovXX1`; não publica = `MgovXX5`.

Itens dos grupos (conteúdo da página na internet e/ou portal da transparência):

| Código     | Grupo | Significado                                                              | Distribuição (n = 5.570)                                     |
| ----------- | ----- | ------------------------------------------------------------------------ | ------------------------------------------------------------ |
| `Mgov081`   | A     | Registro de competências                                                | Sim 60,8% · Não 38,9% · Não informou 0,3% · Recusa 0,1%      |
| `Mgov082`   | A     | Estrutura organizacional                                                 | Sim 82,9% · Não 16,8% · Não informou 0,3% · Recusa 0,1%      |
| `Mgov083`   | A     | Endereços e telefones das unidades                                      | Sim 89,9% · Não 9,7% · Não informou 0,3% · Recusa 0,1%       |
| `Mgov084`   | A     | Horários de atendimento ao público                                     | Sim 85,2% · Não 14,4% · Não informou 0,3% · Recusa 0,1%      |
| `Mgov088`   | A     | Respostas às perguntas mais frequentes (FAQ)                            | Sim 47,4% · Não 52,2% · Não informou 0,3% · Recusa 0,1%      |
| `Mgov085`   | B     | Quantitativo do pessoal ocupado por vínculo                             | Sim 67,2% · Não 32,4% · Não informou 0,3% · Recusa 0,1%      |
| `Mgov086`   | B     | Dados gerais para acompanhamento de programas, ações, projetos e obras | Sim 58,2% · Não 41,4% · Não informou 0,3% · Recusa 0,1%      |
| `Mgov087`   | B     | Procedimentos licitatórios (editais e resultados) e contratos            | Sim 90,1% · Não 9,5% · Não informou 0,3% · Recusa 0,1%       |
| `Mgov089`   | B     | Registro de repasses ou transferências de recursos financeiros          | Sim 72,9% · Não 26,7% · Não informou 0,3% · Recusa 0,1%      |

OBSERVAÇÕES:

- **Portal da transparência (`Mtic271`) fora do índice:** 99,7% dos municípios têm, então não diferencia ninguém. Todo município com portal de dados abertos também tem portal da transparência; por isso só o `Mtic272` pontua.

- `Mtic272`: os 3 casos com `-` decorrem de salto por desconhecimento na pergunta-mãe (`Mtic273` = "Não sabe informar"); pontuam 0 e contam no denominador.

- **Grupos A e B:** pontuação proporcional, e não "pelo menos um", porque quase todo município publica algum item.


---

## [26 pts] D3: Serviços digitais ao cidadão

Mede o que o cidadão consegue resolver online ou pelo celular, por quais canais e com qual acessibilidade.

| Código              | Significado                                                                     | Regra                                                                                                               | Distribuição (n = 5.570)                                                                                           |
| -------------------- | ------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `Mtic10`            | Página da prefeitura na internet está ativa                                    | Ativa = 1; em manutenção = 0,5; em elaboração ou não possui = 0                                                     | Ativa 97,7% · Em manutenção 0,9% · Em elaboração 0,3% · Não possui 0,8% · Não informou 0,1% · Recusa 0,1%         |
| `Mtic12b1`          | Ouvidoria e serviços de atendimento ao cidadão                                 | Sim = 1                                                                                                             | Sim 85,9% · Não 12,7% · - 1,1% · Não informou 0,3% · Recusa 0,1%                                                   |
| `Mtic12b2`          | Download de documentos ou formulários                                         | Sim = 1                                                                                                             | Sim 76,3% · Não 22,3% · - 1,1% · Não informou 0,3% · Recusa 0,1%                                                   |
| `Mtic12b3`          | Consulta a processos / acompanhamento de protocolos                             | Sim = 1                                                                                                             | Sim 44,9% · Não 53,6% · - 1,1% · Não informou 0,3% · Recusa 0,1%                                                   |
| `Mtic12b4`          | Consulta prévia                                                                 | Sim = 1                                                                                                             | Sim 28,3% · Não 70,2% · - 1,1% · Não informou 0,3% · Recusa 0,1%                                                   |
| `Mtic12b5`          | Cadastramento de fornecedores                                                  | Sim = 1                                                                                                             | Sim 25,8% · Não 72,7% · - 1,1% · Não informou 0,3% · Recusa 0,1%                                                   |
| `Mtic12b6`          | Emissão de certidão negativa de débito                                        | Sim = 1                                                                                                             | Sim 58,1% · Não 40,5% · - 1,1% · Não informou 0,3% · Recusa 0,1%                                                   |
| `Mtic12b7`          | Emissão de alvará                                                             | Sim = 1                                                                                                             | Sim 33,2% · Não 65,4% · - 1,1% · Não informou 0,3% · Recusa 0,1%                                                   |
| `Mtic12b8`          | Emissão de Nota Fiscal Eletrônica                                             | Sim = 1                                                                                                             | Sim 75,0% · Não 23,6% · - 1,1% · Não informou 0,3% · Recusa 0,1%                                                   |
| `Mtic12b9`          | Matrícula escolar online na rede pública                                      | Sim = 1                                                                                                             | Sim 8,8% · Não 89,7% · - 1,1% · Não informou 0,3% · Recusa 0,1%                                                    |
| `Mtic12b10`         | Agendamento de consulta e exame na rede pública de saúde                      | Sim = 1                                                                                                             | Sim 6,1% · Não 92,4% · - 1,1% · Não informou 0,3% · Recusa 0,1%                                                    |
| `Mtic12b11`         | Emissão de guia de pagamento de tributos                                       | Sim = 1                                                                                                             | Sim 56,0% · Não 42,5% · - 1,1% · Não informou 0,3% · Recusa 0,1%                                                   |
| `Mtic12b12`         | Emissão de documentos (licenças, certidões, permissões etc.)                 | Sim = 1                                                                                                             | Sim 37,1% · Não 61,4% · - 1,1% · Não informou 0,3% · Recusa 0,1%                                                   |
| `Mtic12b13`         | Pesquisa de satisfação sobre os serviços da prefeitura                       | Sim = 1                                                                                                             | Sim 23,0% · Não 75,5% · - 1,1% · Não informou 0,3% · Recusa 0,1%                                                   |
| `Mtic161`           | Envio de SMS para o cidadão                                                   | Sim = 1                                                                                                             | Sim 7,9% · Não 91,9% · Não informou 0,1% · Recusa 0,1%                                                             |
| `Mtic162`           | Recebimento de SMS do cidadão                                                 | Sim = 1                                                                                                             | Sim 5,9% · Não 93,8% · Não informou 0,1% · Recusa 0,1%                                                             |
| `Mtic163`           | Aplicativos criados pela prefeitura ou outros organismos                        | Sim = 1                                                                                                             | Sim 10,3% · Não 89,4% · Não informou 0,1% · Recusa 0,1%                                                            |
| `Mtic164`           | Aplicativos criados por terceiros/cidadãos a partir de dados da prefeitura     | Sim = 1                                                                                                             | Sim 7,6% · Não 92,1% · Não informou 0,1% · Recusa 0,1%                                                             |
| `Mtic165`           | Website adaptado para dispositivos móveis (versão mobile)                     | Sim = 1                                                                                                             | Sim 39,0% · Não 60,8% · Não informou 0,1% · Recusa 0,1%                                                            |
| `Mtic166`           | Emissão de boletos de tributos ou outras guias de pagamento                    | Sim = 1                                                                                                             | Sim 27,8% · Não 71,9% · Não informou 0,1% · Recusa 0,1%                                                            |
| `Mtic18a2`          | Cadastro unificado para todos os serviços da prefeitura                        | Sim = 1                                                                                                             | Sim 10,7% · Não 56,1% · - 32,9% · Não informou 0,2% · Recusa 0,1%                                                   |
| `Mtic18a3`          | Acesso a alguns serviços com a conta GOV.BR                                    | Sim = 1                                                                                                             | Sim 9,4% · Não 57,5% · - 32,9% · Não informou 0,2% · Recusa 0,1%                                                    |
| `Mtic171`–`175`     | Canal para o cidadão solicitar serviços à distância (substitui `Mtic172`) | Site da prefeitura ou app = 1; telefone ou outro website (sem site/app) = 0,5; só redes sociais = 0,25; nenhum = 0 | Site/app 40,5% · Telefone/outro website 31,4% · Só redes sociais 4,8% · Nenhum 23,0% · Não informou 0,1% · Recusa 0,1% |
| `Mtic014`           | Atendimento à distância ao cidadão por WhatsApp                              | Sim = 1                                                                                                             | Sim 52,9% · Não 46,8% · Não informou 0,1% · Recusa 0,1%                                                            |
| `Mtic016`           | Atendimento à distância por telefone exclusivo                                | Sim = 1                                                                                                             | Sim 23,9% · Não 75,8% · Não informou 0,1% · Recusa 0,1%                                                            |
| `Mtic29`            | Modelo de acessibilidade digital usado no website ou portal                     | Federal (e-MAG), global (WCAG/WAI) ou estadual = 1; próprio = 0,5; nenhum = 0                                      | Nenhum 33,5% · Próprio 32,2% · Federal 17,4% · Global 11,5% · Estadual 4,8% · - 0,3% · Não informou 0,2% · Recusa 0,1% |

OBSERVAÇÕES:

- `Mtic10`: página em manutenção vale 0,5 porque continua existindo; em elaboração vale 0 porque ainda não oferece nenhum serviço.

- **Canal de solicitação:** conta o maior nível alcançado (o município pode marcar vários canais).

- `Mtic29`: o modelo próprio vale 0,5 porque mostra preocupação com acessibilidade, mas sem seguir um padrão reconhecido. O `-` corresponde a municípios sem página e vale 0 com peso ativo no denominador.


---

## [16 pts] D4: Controle interno e participação

Mede controle, integridade e canais de escuta do cidadão.

| Código     | Significado                                                                      | Regra                                                                                                              | Distribuição (n = 5.570)                                                                             |
| ----------- | -------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------- |
| `Mgov09`   | Existe estrutura organizacional para o controle interno                          | Com instrumento legal = 1; sem = 0,5; Não = 0                                                                      | Sim c/ instrumento legal 85,1% · Sim s/ instrumento legal 10,3% · Não 4,3% · Não informou 0,3% · Recusa 0,1%|
| `Mgov17`   | Existe carreira específica de auditor/controlador interno                        | Sim = 1                                                                                                            | Sim 37,8% · Não 61,8% · Não informou 0,3% · Recusa 0,1%                                              |
| `Mgov191`  | Controle interno exerce auditoria governamental                                  | Sim = 1                                                                                                            | Sim 46,2% · Não 53,4% · Não informou 0,3% · Recusa 0,1%                                              |
| `Mgov192`  | Controle interno exerce controladoria                                            | Sim = 1                                                                                                            | Sim 89,1% · Não 10,5% · Não informou 0,3% · Recusa 0,1%                                              |
| `Mgov193`  | Controle interno exerce corregedoria                                             | Sim = 1                                                                                                            | Sim 17,3% · Não 82,4% · Não informou 0,3% · Recusa 0,1%                                              |
| `Mgov194`  | Controle interno exerce ouvidoria                                                | Sim = 1                                                                                                            | Sim 34,5% · Não 65,1% · Não informou 0,3% · Recusa 0,1%                                              |
| `Mgov195`  | Controle interno promove integridade / combate à corrupção                     | Sim = 1                                                                                                            | Sim 35,9% · Não 63,7% · Não informou 0,3% · Recusa 0,1%                                              |
| `Mgov201`  | Controle prévio                                                                 | Sim = 1                                                                                                            | Sim 68,7% · Não 30,9% · Não informou 0,3% · Recusa 0,1%                                              |
| `Mgov202`  | Controle concomitante                                                            | Sim = 1                                                                                                            | Sim 69,5% · Não 30,1% · Não informou 0,3% · Recusa 0,1%                                              |
| `Mgov203`  | Controle posterior                                                               | Sim = 1                                                                                                            | Sim 61,0% · Não 38,6% · Não informou 0,3% · Recusa 0,1%                                              |
| `Mgov23`   | Controle interno possui informação na internet                                  | Sim = 1                                                                                                            | Sim 56,3% · Não 43,3% · Não informou 0,3% · Recusa 0,1%                                              |
| `Mgov05`   | Publica perguntas e respostas feitas pela LAI                                    | Perguntas e respostas = 1; só respostas = 0,5; não publica = 0; **não publica e `Mgov04` = Não → não se aplica** | Perguntas e respostas 22,3% · Só respostas 4,4% · Não publica 38,8% · Não se aplica 34,1% · Não informou 0,3% · Recusa 0,1% |
| `Mtic251`  | Consulta pública online (contribuições para leis, orçamentos e planos)       | Sim = 1                                                                                                            | Sim 31,5% · Não 68,3% · Não informou 0,2% · Recusa 0,1%                                              |
| `Mtic252`  | Grupos de discussão (fóruns ou comunidades na internet)                        | Sim = 1                                                                                                            | Sim 7,0% · Não 92,7% · Não informou 0,2% · Recusa 0,1%                                               |
| `Mtic253`  | Enquete online sobre assuntos de interesse da prefeitura                         | Sim = 1                                                                                                            | Sim 20,1% · Não 79,7% · Não informou 0,2% · Recusa 0,1%                                              |
| `Mtic254`  | Votação online para orientar decisões (políticas públicas, orçamento etc.) | Sim = 1                                                                                                            | Sim 10,3% · Não 89,4% · Não informou 0,2% · Recusa 0,1%                                              |

OBSERVAÇÕES:

- **`Mgov05` e "não se aplica":** município que não recebeu pedido pela LAI em 2023 (`Mgov04` = Não) e não publica não tinha o que publicar, então o item sai do denominador (`peso_aplicado = NULL`). Quem publica mesmo sem ter recebido pedido mantém a pontuação.

- `Mgov09` e `Mgov05` seguem a padronização de no máximo 1 ponto por item.


---

## [4 pts] D5: Proteção de dados pessoais / LGPD

Eixo central do trabalho. Mede se a prefeitura tem estrutura mínima para cumprir a LGPD.

| Código    | Significado                                                                                         | Regra   | Distribuição (n = 5.570)                                                       |
| ---------- | --------------------------------------------------------------------------------------------------- | ------- | ------------------------------------------------------------------------------- |
| `Mgov32`   | Existe área ou pessoa responsável pela LGPD (coleta, armazenamento e uso de dados pessoais)        | Sim = 1 | Sim 27,8% · Não 56,4% · Não sabe 15,4% · Não informou 0,3% · Recusa 0,1%         |
| `Mgov34`   | Ofereceu cursos de segurança da informação e proteção de dados a servidores (últimos 24 meses) | Sim = 1 | Sim 18,1% · Não 67,5% · Não sabe 14,0% · Não informou 0,3% · Recusa 0,1%         |
| `Mgov35`   | Disponibiliza canal na internet para o cidadão enviar mensagens sobre o uso de seus dados           | Sim = 1 | Sim 28,4% · Não 56,5% · Não sabe 14,7% · Não informou 0,3% · Recusa 0,1%         |
| `Mgov36`   | Existe regulamentação ou lei municipal específica sobre LGPD (papéis e responsabilidades)        | Sim = 1 | Sim 23,9% · Não 62,4% · Não sabe 13,3% · Não informou 0,3% · Recusa 0,1%         |

OBSERVAÇÕES:

- "Não sabe informar" e "Não informou" recebem nota 0.0 e permanecem no denominador. Essa abordagem reflete a ausência formal de controles institucionais (particularmente crítica no bloco de LGPD, onde o desconhecimento atinge cerca de 15% dos municípios) e impede a criação de um viés artificialmente positivo em prefeituras que não implementaram a governança.

- `Mgov33` (onde fica o responsável pela LGPD) não pontua: vira atributo descritivo e gráfico próprio.


---

## Fora do índice (de propósito)

| Código                                             | Motivo                                                                                                             |
| -------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `Mtic271`                                         | Portal da transparência: 99,7% têm, não diferencia (ver D2)                                                       |
| `Mgov0811`                                        | Só 5 "Sim"                                                                                                         |
| `Mgov33`                                          | Onde fica o responsável pela LGPD (TI, jurídico etc.). Não pontua; vira atributo descritivo e gráfico próprio       |
| `Mtic342`                                         | Filha de `Mtic30`: quem não tem área de comunicação recebe `-` e seria penalizado por outro motivo                 |
| `Mtic30`                                          | Área de comunicação: funciona como marcador de porte (21% nos até 5 mil hab., 98% acima de 500 mil)             |
| `Mgov26`                                          | Conselho de transparência: só 116 municípios (2,1%)                                                               |
| `Mtic04`                                          | 94,5% fibra/cabo, não diferencia municípios                                                                        |
| `Mtic011`–`013`, `015`, `017`, `018`                | Bloco 2.1: só WhatsApp (`Mtic014`) e telefone exclusivo (`Mtic016`) entraram                                       |
| `Mtic172` (isolado)                               | Substituído pela escada de canais de solicitação (`Mtic171`–`175`)                                                 |
| `Mtic181`–`185`                                   | Canais de acompanhamento: repetem os de solicitação                                                               |
| `Mtic23`, `Mtic24`                                | Wi-Fi gratuito em quase todos; cobertura total só em 2,0%                                                         |
| `Mtic284`                                         | Libras isolada: o `Mtic29` cobre acessibilidade de forma mais ampla                                               |
| `Mgov06`, `Mgov13`, `Mtic12a3`, `Mtic12a5`        | Quase constantes (~91% a 99,3% Sim)                                                                                |
| `Mtic12b14`, `Mtic18a4`                           | Muito raras (~2% Sim)
