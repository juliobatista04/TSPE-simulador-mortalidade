# Documentação interna · TSPE

Mortalidade hospitalar no SUS em Pernambuco, com aprendizado de máquina.
Disciplina WYD6399 Tópicos em Big Data em Python · Prof. Me. Flávio Morais · UniFavip Wyden, 2026.

Equipe: Julio César Batista Silva, Teves Gabriel, Luciano Filho, Jonathas Costa e Anderson Davi.

Este documento registra o que foi feito, em que ordem, por quê, o que deu errado e como foi resolvido. A divisão em quatro semanas é a organização que o grupo adotou pra apresentar o trabalho.

---

## Visão geral

| Item | Valor |
|---|---|
| Fonte | SIH/SUS, Morbidade Hospitalar do SUS por local de internação, Pernambuco (TABNET/DATASUS) |
| Período | outubro/2025 a setembro/2026 (arquivos `nipe2510` a `nipe2609`, por mês de processamento) |
| Internações | 679.632 |
| Óbitos | 27.905 (mortalidade geral de 4,11%) |
| Hospitais | 255 com internação (231 entram no modelo) |
| Tabelas baixadas | 58 |
| Registros hospital × capítulo × faixa | 17.890 |
| Registros do modelo | 6.492 (10 ou mais internações) |
| Modelo escolhido | Random Forest · AUROC 0,866 · acurácia 82,6% |

Fluxo:

```
TABNET ──(scripts/baixar_tabnet.ps1)──> dados/brutos (58 CSV)
       ──(zip)──> Colab: TSPE_1_dados_e_tratamento ──> tspe_dados.zip (7 arquivos tratados)
       ──> Colab: TSPE_2_objetivos_e_modelo ──> simulador.json + relatorio_modelos.json
       ──(scripts/montar_pagina.ps1)──> pagina/simulador.html
```

---

## Semana 1 · Busca da base, coleta e tratamento

### 1.1 Escolha da base

O grupo já trabalhava com o SIH/SUS no TABNET numa primeira versão, que tinha 12 CSVs e 239 linhas (capítulo × faixa etária). Essa versão tinha dois problemas:

- a taxa de mortalidade vinha pronta e arredondada em 2 casas, e os óbitos eram estimados a partir dela;
- não dava pra comparar hospitais dentro de um mesmo grupo e idade, que é o centro do simulador.

Decisão: baixar de novo, com **óbitos e dias de permanência em número absoluto**, e no nível **hospital × capítulo CID × faixa etária**.

### 1.2 Como o TABNET funciona e como foi automatizado

O TABNET monta uma tabela de duas dimensões (linha × coluna) para uma medida, com filtros opcionais. O formulário envia um POST para `https://tabnet.datasus.gov.br/cgi/tabcgi.exe?sih/cnv/nipe.def` com os campos:

| Campo | Exemplo |
|---|---|
| `Linha` | `Estabelecimento` |
| `Coluna` | `Capítulo_CID-10` |
| `Incremento` | `Internações`, `Óbitos` ou `Dias_permanência` |
| `Arquivos` | um por mês: `nipe2510.dbf` ... `nipe2609.dbf` |
| `S<variável>` | filtro, ex.: `SFaixa_Etária_1=9` (60 a 69 anos) |
| `formato` | `prn` (texto separado por `;`) |

O script `scripts/baixar_tabnet.ps1` manda exatamente esse pedido, extrai o bloco `<PRE>` da resposta e salva como CSV em UTF-8. Ele pula arquivos que já existem, então pode ser rodado de novo quantas vezes for preciso.

### 1.3 O que foi baixado (58 tabelas)

**Estado** (`dados/brutos/estado`), cada uma em internações, óbitos e dias:
- `capitulo_x_faixa_*`: capítulo CID × faixa etária
- `doenca_x_faixa_*`: Lista de Morbidade (317 doenças) × faixa etária
- `mes_x_capitulo_*`: mês × capítulo
- mais `capitulo_x_faixa_taxa_mortalidade`, `capitulo_x_faixa_media_permanencia` (só pra conferência) e `doenca_x_capitulo_internacoes`

**Hospitais** (`dados/brutos/hospitais`):
- `hospital_x_capitulo_*` e `hospital_x_faixa_*` (internações, óbitos, dias)
- `hospital_x_regiao_saude`, `hospital_x_macrorregiao`, `hospital_x_microrregiao`, `hospital_x_carater`
- `por_faixa/hospital_x_capitulo_<medida>_faixaNN_*`: 36 tabelas (12 faixas × 3 medidas)

### 1.4 Tratamento (notebook `TSPE_1_dados_e_tratamento`)

Segue a lógica do caderno `tratamento_dados_ML 2` do grupo, com as mesmas funções (`ler_csv_tabnet`, `limpar_numero`, `limpar_hospital`, `derreter`).

1. **Leitura:** ignora cabeçalho e rodapé, descarta linhas sem `;` (sobra de HTML), remove linha e coluna `Total`.
2. **Números:** `1.234,5` vira `1234.5`. O `-` do TABNET vira **0** (no TABNET, traço é zero, não ausente).
3. **Formato longo:** cada tabela larga é "derretida" (uma linha por combinação).
4. **Junção:** internações, óbitos e dias são unidos pela chave; a região de saúde, macro e micro do hospital vêm da coluna em que ele tem internação (cada hospital só aparece na própria região).
5. **Capítulo padronizado:** os três formatos do TABNET viram número de 1 a 21 e nome por extenso.
6. **Taxas recalculadas:** `tx_mortalidade = 100 × óbitos ÷ internações`, `media_permanencia = dias ÷ internações`.
7. **Combinações sem internação removidas** (não são informação).
8. **Conferência automática:** soma dos hospitais (679.456) contra o estado (679.632). A diferença de 176 é a faixa "idade ignorada". O notebook para com erro se a diferença passar de 1%.

Saída (`data/processado`):

| Arquivo | Linha = | Linhas |
|---|---|---|
| `doenca_idade.csv` | capítulo × faixa (estado) | 240 |
| `hospitais.csv` | hospital | 255 |
| `hosp_doenca.csv` | hospital × capítulo | 3.096 |
| `hosp_doenca_idade.csv` | hospital × capítulo × faixa | 17.890 |
| `doencas_especificas.csv` | doença × faixa (estado) | 3.804 |
| `mensal.csv` | mês × capítulo | 240 (a primeira rodada saiu com 280 por causa dos subtotais por ano, já corrigido) |
| `tratamentos.json` | capítulo | 19 |

### 1.5 Dificuldades da semana 1

| Problema | Sintoma | Solução |
|---|---|---|
| TABNET só cruza 2 variáveis | Não existe hospital × doença × idade numa consulta | 36 consultas com a faixa etária como filtro, empilhadas depois |
| Taxa arredondada | Óbitos estimados distorciam somas | Baixar óbitos e dias em número absoluto |
| Colab bloqueado | O TABNET respondeu 6 tabelas e depois deu timeout de conexão (servidor do Google fora do Brasil) | Baixar no PC, zipar (`scripts/zipar_brutos.ps1`) e subir no Colab |
| Instabilidade do TABNET | "Impossível conectar-se ao servidor remoto" no meio do lote | 4 tentativas com espera crescente e várias passadas até completar 58 arquivos |
| Acentuação | PowerShell 5.1 lê script UTF-8 sem BOM como ANSI e estraga "Capítulo" | Salvar o `.ps1` com BOM; formulário codificado em latin-1 |
| Capítulo em 3 formatos | `I.   Algumas...`, `01 Algumas...`, `Cap 01` | Função `numero_capitulo` trata os três |
| Sobra de HTML | Linha `&` no fim de cada tabela | Ignorar linhas sem `;` |
| Subtotais por ano | Tabela mensal com linhas "2025" e "2026" | Manter só linhas no formato mês/ano |

---

## Semana 2 · Aprendizado de máquina (notebook `TSPE_2_objetivos_e_modelo`)

### 2.1 Pergunta e variável-alvo

Pra cada hospital, grupo de doença e faixa etária: **a mortalidade ficou acima da mortalidade do estado pra mesma doença e idade?**

`acima_esperado = 1` se `tx_mortalidade_hospital > tx_mortalidade_estado`, senão 0.

Só entram combinações com **10 ou mais internações** (17.890 → 6.492 registros, 231 hospitais). Abaixo disso a taxa é ruído.

Distribuição: **1.584 acima (24,4%)** e **4.908 dentro (75,6%)**.

### 2.2 Atributos (9, ou 31 colunas após o one-hot)

| Atributo | Tipo | Descrição |
|---|---|---|
| `cap` | categórico (one-hot) | capítulo CID-10 |
| `faixa_ord` | ordinal 0 a 11 | faixa etária |
| `media_permanencia` | numérico | dias médios no hospital, nesse grupo e idade |
| `log_internacoes` | numérico | log(1 + internações do grupo no hospital) |
| `tx_estado` | numérico | mortalidade do estado na mesma doença e idade |
| `perm_estado` | numérico | permanência do estado na mesma doença e idade |
| `log_porte` | numérico | log(1 + internações totais do hospital) |
| `pct_urgencia` | numérico | % de internações de urgência no hospital (faltante: mediana) |
| `macrorregiao` | categórico (one-hot) | macrorregião de saúde |

Excluídos por serem a própria resposta: óbitos, taxa do hospital e taxa ajustada.

### 2.3 Preparação

- Divisão **75% treino / 25% teste**, estratificada, semente 42: treino 4.869 (1.188 acima), teste 1.623 (396 acima).
- **Balanceamento:** sem reamostragem. `class_weight="balanced"` na Regressão Logística e no Random Forest, e estratificação.
- `StandardScaler` nos numéricos e `OneHotEncoder` nos categóricos, dentro de um `Pipeline` (ajustados só no treino de cada parte da validação).

### 2.4 Busca de hiperparâmetros

Técnica **GridSearchCV**, métrica **AUROC**, validação **StratifiedKFold com K = 5**.

| Modelo | Grade | Combinações | Melhor configuração | AUROC CV |
|---|---|---|---|---|
| Regressão Logística | `C` ∈ {0,1; 1; 10} | 3 | `C = 1` | 0,812 |
| Random Forest | `n_estimators` = 300; `max_depth` ∈ {6; 10; None}; `min_samples_leaf` ∈ {1; 5} | 6 | `max_depth = None`, `min_samples_leaf = 1` | 0,866 |
| Gradient Boosting | `n_estimators` ∈ {200; 400}; `learning_rate` ∈ {0,05; 0,1}; `max_depth` ∈ {2; 3} | 8 | `n_estimators = 400`, `learning_rate = 0,1`, `max_depth = 3` | 0,864 |

### 2.5 Resultados no teste

| Modelo | AUROC teste | Acurácia | Precisão | Sensibilidade | Especificidade | F1 |
|---|---|---|---|---|---|---|
| Regressão Logística | 0,806 | 73,1% | 46,8% | 73,0% | 73,2% | 0,570 |
| **Random Forest** | **0,866** | **82,6%** | **70,8%** | 48,5% | **93,6%** | 0,576 |
| Gradient Boosting | 0,858 | 82,0% | 67,0% | 51,8% | 91,8% | 0,584 |

Matrizes de confusão (VN / FP / FN / VP):
- Regressão Logística: 898 / 329 / 107 / 289
- Random Forest: 1.148 / 79 / 204 / 192
- Gradient Boosting: 1.126 / 101 / 191 / 205

Importância por permutação no Random Forest (queda de AUROC): permanência média 0,151; porte 0,066; mortalidade do estado 0,041; % urgência 0,035; macrorregião 0,022; volume no grupo 0,021; capítulo 0,016; faixa 0,006; permanência do estado 0,005.

### 2.6 Escolha

**Random Forest**, pela maior AUROC na validação cruzada (critério definido antes de ver o teste). Teste igual à validação (0,866), então não houve sobreajuste. Tem a maior precisão e especificidade, o que importa no simulador: classificar um hospital como "acima" sem que ele esteja é o erro mais caro. O Gradient Boosting ficou praticamente empatado.

Ponto fraco: sensibilidade de 48,5% no corte 0,5.

---

## Semana 3 · Alinhamentos

### 3.1 Checagem dos objetivos, item por item

| O simulador mostra | Atendido? | Origem |
|---|---|---|
| Taxa de mortalidade do grupo | sim | `doenca_idade` |
| Tempo médio de permanência | sim | `doenca_idade`, `hosp_doenca_idade` |
| Internações em PE e no hospital | sim | `doenca_idade`, `hosp_doenca_idade` |
| Acerto e acurácia | sim | avaliação do modelo |
| Melhor hospital pro tratamento | sim, pela taxa ajustada com mínimo de 30 internações | `hosp_doenca_idade` |
| O hospital atual é bom? | sim | modelo |
| Hospital melhor mais próximo | aproximado: mesma região de saúde, depois macrorregião | `hospitais` |
| Top 5 doenças do grupo | sim | `doencas_especificas` |
| Top 5 tratamentos | sim, como texto da equipe | `tratamentos.json` |

### 3.2 Decisões tomadas

- **Taxa ajustada pro ranking:** `(óbitos + 20 × taxa do estado) ÷ (internações + 20)`. Sem isso, um hospital com 3 internações e 0 óbito virava "o melhor". Com muito volume, a taxa ajustada fica igual à crua.
- **Mínimo de 30 internações** pra aparecer no ranking de melhor hospital, e de 10 pra receber classificação do modelo.
- **"Mais perto" por região de saúde:** o TABNET não traz endereço. Pra distância em km, seria preciso buscar as coordenadas pelo CNES (fica como melhoria).
- **Tratamentos como texto informativo:** o DATASUS registra diagnóstico, não remédio. A página deixa isso claro.
- **Limite do modelo:** a permanência média vem das mesmas internações, então o modelo descreve o histórico do hospital e não prevê o desfecho de um paciente novo.

### 3.3 Revisão contra a diretriz

A apresentação (`apresentacao/slides.html`) segue as 4 partes pedidas: introdução e objetivo; metodologia e preparação (base original, pré-processamento, atributos, registros finais, distribuição do alvo, balanceamento, divisão); construção e otimização dos 3 modelos (escopo, técnica, métrica, K, melhor configuração, desempenho); comparação e justificativa.

---

## Semana 4 · Criação e últimos passos

### 4.1 Simulador (`pagina/simulador.html`)

- **Tela 1:** só as escolhas. Busca por sintoma ou doença (ex.: "pneumonia" leva a Doenças do aparelho respiratório), faixa etária em botões, hospital com busca por nome. Botão "Continuar" só libera com os três preenchidos.
- **Tela 2:** mortalidade, permanência, internações no estado e no hospital; veredito do modelo com medidor; ranking dos hospitais com menor mortalidade na região e no estado; 5 principais doenças e tratamentos com "ver mais".
- **Painel "Dados em detalhe"** (canto superior direito): grupo por faixa etária, todos os hospitais do grupo com taxa crua, ajustada e probabilidade do modelo, os 3 modelos comparados, fonte e limites.
- A página é estática: o modelo roda uma vez no Colab e o resultado vai num JSON embutido no HTML. Funciona no GitHub Pages sem servidor.

### 4.2 Como reproduzir do zero

1. No Windows: `powershell -File scripts\baixar_tabnet.ps1` (rode de novo se alguma tabela falhar).
2. `powershell -File scripts\zipar_brutos.ps1` gera `brutos.zip`.
3. No Colab, abra `notebooks/TSPE_1_dados_e_tratamento.ipynb`, suba `brutos.zip` na aba de arquivos e execute tudo. Baixa `tspe_dados.zip`.
4. Abra `notebooks/TSPE_2_objetivos_e_modelo.ipynb`, suba `tspe_dados.zip` e execute tudo. Baixa `tspe_modelo_saidas.zip`.
5. Extraia o `simulador.json` e rode `powershell -File scripts\montar_pagina.ps1 -json <caminho>\simulador.json`.

Para editar os notebooks, altere o `.py` em `notebooks/src` e converta com `scripts/py_para_ipynb.ps1`.

### 4.3 Próximos passos possíveis

- Ajustar o corte do modelo (hoje 0,5) pra subir a sensibilidade.
- Coordenadas pelo CNES pra "mais perto" em km.
- Testar o modelo em outro período (ex.: 2024) pra ver se se mantém.
