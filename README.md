# TSPE · Mortalidade hospitalar no SUS em Pernambuco

Simulador que, a partir do grupo de doença, da faixa etária e do hospital, mostra a mortalidade e a permanência nas internações do SUS em Pernambuco, diz se o hospital está dentro ou acima do esperado (Random Forest) e aponta os hospitais com menor mortalidade na região e no estado.

Projeto da disciplina WYD6399 Tópicos em Big Data em Python (UniFavip Wyden, 2026).
Equipe: Julio César Batista Silva, Teves Gabriel, Luciano Filho, Jonathas Costa e Anderson Davi.

## Abrir

- **Simulador:** `index.html` (também publicado pelo GitHub Pages)
- **Apresentação:** `apresentacao/slides.html` (setas do teclado, F11 pra tela cheia)
- **Documentação do processo, semana a semana:** [`docs/DOCUMENTACAO.md`](docs/DOCUMENTACAO.md)

## Notebooks no Google Colab

| Notebook | O que faz | Abrir |
|---|---|---|
| `TSPE_1_dados_e_tratamento` | baixa/lê as 58 tabelas do TABNET e trata | [![Abrir no Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/juliobatista04/TSPE-simulador-mortalidade/blob/main/notebooks/TSPE_1_dados_e_tratamento.ipynb) |
| `TSPE_2_objetivos_e_modelo` | checa os objetivos, treina os 3 modelos e gera o JSON do simulador | [![Abrir no Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/juliobatista04/TSPE-simulador-mortalidade/blob/main/notebooks/TSPE_2_objetivos_e_modelo.ipynb) |

No Colab, suba na aba de arquivos o zip de entrada de cada notebook: `brutos.zip` (pasta `dados/brutos` zipada com `scripts/zipar_brutos.ps1`) para o primeiro e `tspe_dados.zip` (saída do primeiro) para o segundo. O TABNET costuma recusar conexões vindas do Colab, por isso o download é feito num computador no Brasil.

## Dados (CSV)

- [`dados/brutos/`](dados/brutos): as 58 tabelas como saíram do TABNET (separador `;`, UTF-8)
- [`dados/processado/`](dados/processado): as 6 tabelas tratadas e `tratamentos.json`
- [`dados/modelo/`](dados/modelo): métricas dos 3 modelos, relatório completo e o `simulador.json`

## Números principais

| | |
|---|---|
| Período | out/2025 a set/2026 (SIH/SUS, TABNET) |
| Internações / óbitos | 679.632 / 27.905 (4,11%) |
| Registros do modelo | 6.492 (hospital × capítulo × faixa, 10+ internações) |
| Modelo escolhido | Random Forest · AUROC 0,866 · acurácia 82,6% |

| Modelo | AUROC CV | AUROC teste | Acurácia |
|---|---|---|---|
| Regressão Logística | 0,812 | 0,806 | 73,1% |
| **Random Forest** | **0,866** | **0,866** | **82,6%** |
| Gradient Boosting | 0,864 | 0,858 | 82,0% |

## Estrutura

```
index.html                 simulador (página única, dados embutidos)
apresentacao/slides.html   apresentação
docs/DOCUMENTACAO.md       documentação interna em 4 semanas
notebooks/                 notebooks do Colab (.ipynb) e o código-fonte (.py)
scripts/                   download do TABNET, zip, conversão de notebook, montagem da página
dados/brutos/              58 tabelas do TABNET
dados/processado/          tabelas tratadas
dados/modelo/              simulador.json, relatorio_modelos.json, metricas_modelos.csv
```

## Aviso

Material acadêmico. Os números descrevem grupos de internações, não pacientes, e não consideram a gravidade de cada caso. Os tratamentos listados são informativos e não substituem avaliação médica.
