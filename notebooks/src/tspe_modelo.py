# %% [markdown]
# # TSPE · Caderno 2: o que os dados respondem e o primeiro modelo
#
# Entrada: a pasta `data/processado` gerada no Caderno 1 (sobe o `tspe_dados.zip` na aba de arquivos do Colab).
#
# Duas partes:
# 1. **Etapa 4.** Conferir, item por item, se os dados dão conta do que o simulador precisa mostrar.
# 2. **Etapa 5.** Primeiro modelo: dado o hospital, o grupo de doença e a faixa etária, o hospital fica
#    acima ou abaixo da mortalidade esperada pro estado?

# %%
import os, json, zipfile
import numpy as np
import pandas as pd

if not os.path.exists("data/processado/hosp_doenca_idade.csv"):
    with zipfile.ZipFile("tspe_dados.zip") as z:
        z.extractall(".")

ler = lambda n: pd.read_csv(f"data/processado/{n}.csv", sep=";", dtype={"cnes": str})
doenca_idade = ler("doenca_idade")
hospitais = ler("hospitais")
hosp_doenca = ler("hosp_doenca")
hdi = ler("hosp_doenca_idade")
doencas_especificas = ler("doencas_especificas")
with open("data/processado/tratamentos.json", encoding="utf-8") as f:
    tratamentos = json.load(f)

FAIXAS = ["Menor 1 ano", "1 a 4 anos", "5 a 9 anos", "10 a 14 anos", "15 a 19 anos", "20 a 29 anos",
          "30 a 39 anos", "40 a 49 anos", "50 a 59 anos", "60 a 69 anos", "70 a 79 anos", "80 anos e mais"]
print(hdi.shape, hospitais.shape)

# %% [markdown]
# ## Etapa 4 · Os dados cobrem o simulador?
#
# Pra cada coisa que a página vai mostrar, uma conta de verdade com um exemplo:
# Doenças do aparelho circulatório (cap. 9), 60 a 69 anos, no hospital com mais internações desse grupo.

# %%
CAP, FAIXA = 9, "60 a 69 anos"
ref = doenca_idade[(doenca_idade.cap == CAP) & (doenca_idade.faixa_etaria == FAIXA)].iloc[0]
grupo = hdi[(hdi.cap == CAP) & (hdi.faixa_etaria == FAIXA)]
exemplo = grupo.sort_values("internacoes", ascending=False).iloc[0]

print("1. taxa de mortalidade da doença no estado:", ref.tx_mortalidade, "%")
print("2. tempo médio de permanência:", ref.media_permanencia, "dias")
print("3. internações em PE nesse grupo:", int(ref.internacoes))
print(f"4. no hospital {exemplo.hospital}: {int(exemplo.internacoes)} internações, "
      f"mortalidade {exemplo.tx_mortalidade}%, permanência {exemplo.media_permanencia} dias")
print("5. hospitais que atenderam esse grupo:", grupo.cnes.nunique(),
      "| com 30 ou mais internações:", (grupo.internacoes >= 30).sum())
top5 = (doencas_especificas[(doencas_especificas.cap == CAP) & (doencas_especificas.faixa_etaria == FAIXA)]
        .sort_values("internacoes", ascending=False).head(5)[["doenca", "internacoes", "tx_mortalidade"]])
print("6. top 5 doenças do grupo nessa idade:"); print(top5.to_string(index=False))
print("7. tratamentos do grupo:", tratamentos[str(CAP)]["tratamentos"][:2], "...")

# %% [markdown]
# ### Um cuidado antes de comparar hospitais
#
# Hospital pequeno engana. Com 3 internações e 1 óbito a taxa dá 33%; com 3 e nenhum óbito dá 0%.
# Nenhum dos dois números diz muita coisa. Se a gente escolher "o melhor hospital" pela menor taxa crua,
# quem ganha é sempre um hospital que atendeu quase ninguém.
#
# A saída usada aqui é a **taxa ajustada**: junta os óbitos do hospital com um "peso" da taxa do estado.
# Hospital com muito volume fica com a própria taxa; hospital com pouco volume fica perto da média do estado.
#
# `taxa_ajustada = (óbitos + K × taxa_estado) / (internações + K)`, com K = 20 internações.
#
# É o mesmo raciocínio de nota média em app de avaliação: 5 estrelas com 2 votos não vale o mesmo que 4,8 com mil.

# %%
K = 20
ref_estado = doenca_idade[["cap", "faixa_etaria", "tx_mortalidade", "media_permanencia"]].rename(
    columns={"tx_mortalidade": "tx_estado", "media_permanencia": "perm_estado"})
hdi = hdi.merge(ref_estado, on=["cap", "faixa_etaria"], how="left")
hdi["tx_ajustada"] = (100 * (hdi.obitos + K * hdi.tx_estado / 100) / (hdi.internacoes + K)).round(2)

# quanto hospital fica igual ou abaixo do estado no exemplo
g = hdi[(hdi.cap == CAP) & (hdi.faixa_etaria == FAIXA) & (hdi.internacoes >= 30)]
print(g.sort_values("tx_ajustada")[["hospital", "regiao_saude", "internacoes", "tx_mortalidade", "tx_ajustada"]].head(8).to_string(index=False))

# %% [markdown]
# ### Resultado da etapa 4
#
# | o simulador mostra | dá pra fazer? | de onde vem |
# |---|---|---|
# | taxa de mortalidade da doença | sim | `doenca_idade` (óbitos ÷ internações, estado) |
# | tempo médio de permanência | sim | `doenca_idade` e `hosp_doenca_idade` (dias ÷ internações) |
# | internações em PE e no hospital | sim | `doenca_idade` e `hosp_doenca_idade` |
# | melhor hospital pro tratamento | sim, com a taxa ajustada e volume mínimo | `hosp_doenca_idade` |
# | o hospital atual é bom? | sim, é o que o modelo responde | modelo da etapa 5 |
# | hospital melhor mais próximo | **aproximado**: mesma região de saúde, depois mesma macrorregião | `hospitais` |
# | top 5 doenças do grupo | sim | `doencas_especificas` (Lista de Morbidade) |
# | top 5 tratamentos | sim, mas é texto do grupo, não sai do DATASUS | `tratamentos.json` |
# | acerto e acurácia | sim | avaliação do modelo abaixo |
#
# Dois limites que precisam aparecer na apresentação:
# - "Mais próximo" é por região de saúde, não por distância em km. O TABNET não dá endereço do hospital.
#   Se o grupo quiser km de verdade, dá pra puxar as coordenadas pelo CNES numa próxima etapa.
# - Os tratamentos não são previstos pelo modelo. O DATASUS registra o diagnóstico, não qual remédio foi dado.
#   O ranking de tratamentos é a lista do grupo pra cada capítulo, e a página tem que deixar isso claro.

# %% [markdown]
# ## Etapa 5 · Primeiro modelo
#
# **Pergunta:** num hospital, pra um grupo de doença e uma faixa etária, a mortalidade fica **acima do esperado** pro estado?
#
# - Uma linha = hospital × capítulo CID × faixa etária, só com 10 ou mais internações (abaixo disso a taxa é ruído).
# - Alvo `acima_esperado` = 1 se a taxa do hospital passa da taxa do estado pra mesma doença e idade.
#   (Usar a taxa crua ou a ajustada aqui dá no mesmo: a correção puxa o número pra perto do estado, mas não troca o lado.
#   A ajustada serve mesmo é pro ranking de "melhor hospital".)
# - Atributos: o grupo de doença, a faixa etária (ordem natural, 0 a 11), a permanência média no hospital,
#   o volume (log), a taxa e a permanência de referência do estado, o porte do hospital, o % de internação de urgência
#   e a macrorregião.
# - Fica de fora tudo que é a própria resposta: óbitos, taxa do hospital e taxa ajustada.
#
# A diretriz pede pelo menos três modelos. Começamos com Regressão Logística (base simples), Random Forest e
# Gradient Boosting, todos com validação cruzada estratificada em 5 partes, e o teste (25%) só no fim.

# %%
from sklearn.model_selection import train_test_split, StratifiedKFold, GridSearchCV
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.metrics import (accuracy_score, roc_auc_score, f1_score, precision_score, recall_score,
                             confusion_matrix)

base = hdi[hdi.internacoes >= 10].copy()
base = base.merge(hospitais[["cnes", "internacoes", "pct_urgencia"]].rename(columns={"internacoes": "porte_hospital"}),
                  on="cnes", how="left")
base["acima_esperado"] = (base.tx_mortalidade > base.tx_estado).astype(int)
base["pct_urgencia"] = base["pct_urgencia"].fillna(base["pct_urgencia"].median())
base["faixa_ord"] = base.faixa_etaria.map({f: i for i, f in enumerate(FAIXAS)})
base["log_internacoes"] = np.log1p(base.internacoes)
base["log_porte"] = np.log1p(base.porte_hospital)
base["cap"] = base["cap"].astype(int).astype(str)

NUM = ["faixa_ord", "media_permanencia", "log_internacoes", "tx_estado", "perm_estado", "log_porte", "pct_urgencia"]
CAT = ["cap", "macrorregiao"]
X, y = base[NUM + CAT], base["acima_esperado"]
print(f"{len(base)} linhas | {base.cnes.nunique()} hospitais | acima do esperado: {y.mean():.1%}")

X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.25, stratify=y, random_state=42)
prep = ColumnTransformer([("num", StandardScaler(), NUM),
                          ("cat", OneHotEncoder(handle_unknown="ignore"), CAT)])
cv = StratifiedKFold(5, shuffle=True, random_state=42)

modelos = {
    "Regressão Logística": (LogisticRegression(max_iter=2000, class_weight="balanced"),
                            {"m__C": [0.1, 1, 10]}),
    "Random Forest": (RandomForestClassifier(random_state=42, class_weight="balanced", n_jobs=-1),
                      {"m__n_estimators": [300], "m__max_depth": [6, 10, None], "m__min_samples_leaf": [1, 5]}),
    "Gradient Boosting": (GradientBoostingClassifier(random_state=42),
                          {"m__n_estimators": [200, 400], "m__learning_rate": [0.05, 0.1], "m__max_depth": [2, 3]}),
}

resultados, ajustados = [], {}
for nome, (est, grade) in modelos.items():
    busca = GridSearchCV(Pipeline([("prep", prep), ("m", est)]), grade, scoring="roc_auc", cv=cv, n_jobs=-1)
    busca.fit(X_tr, y_tr)
    p = busca.predict_proba(X_te)[:, 1]
    pred = (p >= 0.5).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_te, pred).ravel()
    resultados.append({"modelo": nome, "auroc_cv": round(busca.best_score_, 3),
                       "auroc_teste": round(roc_auc_score(y_te, p), 3),
                       "acuracia": round(accuracy_score(y_te, pred), 3),
                       "precisao": round(precision_score(y_te, pred), 3),
                       "sensibilidade": round(recall_score(y_te, pred), 3),
                       "especificidade": round(tn / (tn + fp), 3),
                       "f1": round(f1_score(y_te, pred), 3),
                       "melhores_parametros": busca.best_params_})
    ajustados[nome] = busca.best_estimator_
    from sklearn.metrics import roc_curve
    fpr, tpr, _ = roc_curve(y_te, p)
    idx = np.linspace(0, len(fpr) - 1, 60).astype(int)
    resultados[-1].update({"matriz": {"vn": int(tn), "fp": int(fp), "fn": int(fn), "vp": int(tp)},
                           "roc": {"fpr": fpr[idx].round(3).tolist(), "tpr": tpr[idx].round(3).tolist()},
                           "combinacoes": int(np.prod([len(v) for v in grade.values()])),
                           "grade": {k.replace("m__", ""): v for k, v in grade.items()}})
tabela = pd.DataFrame(resultados).set_index("modelo")[["auroc_cv", "auroc_teste", "acuracia", "precisao",
                                                        "sensibilidade", "especificidade", "f1", "melhores_parametros"]]
tabela

# %% [markdown]
# ### Leitura dos números
#
# - **Acurácia** é a fração de acertos no teste. Como as classes não são 50/50, olhar só ela engana;
#   por isso a escolha do modelo é pela **AUROC da validação cruzada** (quanto o modelo separa as duas classes), não pelo teste.
# - Se a AUROC do teste ficar bem abaixo da validação cruzada, o modelo decorou o treino.
# - A linha de base é 50% de AUROC (chute). Na primeira rodada (nov/2026) deu 0,81 na Regressão Logística,
#   0,87 no Random Forest e 0,86 no Gradient Boosting, com teste e validação cruzada praticamente iguais: não decorou.
# - O ponto fraco é a **sensibilidade** (~49% no Random Forest): de cada dois hospitais que de fato ficaram acima
#   do esperado, o modelo pega um. A especificidade é alta (~94%), então quando ele diz "acima", costuma estar certo.
#   Dá pra trocar um pelo outro mexendo no corte de 0,5; isso fica pra próxima etapa.
# - A variável que mais pesa é a permanência média no próprio hospital. Faz sentido (internação longa costuma ser caso
#   grave), mas é medida nas mesmas internações. O modelo descreve o histórico do hospital, não prevê um paciente novo.

# %%
melhor = tabela["auroc_cv"].idxmax()
modelo_final = ajustados[melhor]
print("modelo escolhido:", melhor)

from sklearn.inspection import permutation_importance
imp = permutation_importance(modelo_final, X_te, y_te, scoring="roc_auc", n_repeats=20, random_state=42)
importancias = pd.Series(imp.importances_mean, index=NUM + CAT).sort_values(ascending=False).round(4)

# tudo que a apresentação precisa, num arquivo só
relatorio = {
    "base_linhas": int(len(base)), "base_hospitais": int(base.cnes.nunique()),
    "combinacoes_totais": int(len(hdi)), "corte_min_internacoes": 10,
    "classes": {"acima": int(y.sum()), "dentro": int((1 - y).sum())},
    "treino": int(len(X_tr)), "teste": int(len(X_te)),
    "treino_classes": {"acima": int(y_tr.sum()), "dentro": int((1 - y_tr).sum())},
    "teste_classes": {"acima": int(y_te.sum()), "dentro": int((1 - y_te).sum())},
    "atributos_numericos": NUM, "atributos_categoricos": CAT,
    "n_colunas_apos_onehot": int(modelo_final.named_steps["prep"].transform(X_tr.head(1)).shape[1]),
    "modelos": resultados, "melhor": melhor,
    "importancias": importancias.to_dict(),
}
with open("relatorio_modelos.json", "w", encoding="utf-8") as f:
    json.dump(relatorio, f, ensure_ascii=False, indent=1, default=str)
importancias

# %% [markdown]
# ## Saída pro simulador
#
# A página é estática (GitHub Pages), então em vez de chamar uma API a cada clique, o modelo roda aqui uma vez
# pra todas as combinações e o resultado vai num JSON só: `simulador.json`.

# %%
base["prob_acima"] = modelo_final.predict_proba(base[NUM + CAT])[:, 1].round(3)
base["cap"] = base["cap"].astype(int)

def melhores_do_grupo(cap, faixa, n=5, min_int=30):
    g = base[(base.cap == cap) & (base.faixa_etaria == faixa) & (base.internacoes >= min_int)]
    return g.sort_values("tx_ajustada").head(n)

sim = {
    "periodo": "out/2025 a set/2026",
    "metricas_modelo": {"modelo": melhor, **{k: v for k, v in tabela.loc[melhor].items() if k != "melhores_parametros"}},
    "todos_modelos": tabela.drop(columns=["melhores_parametros"]).to_dict("index"),
    "faixas": FAIXAS,
    "capitulos": {}, "hospitais": {}, "grupos": [],
}
for _, r in doenca_idade.iterrows():
    c = str(int(r.cap))
    sim["capitulos"].setdefault(c, {"nome": r.doenca_cid, "por_faixa": {},
                                    "tratamentos": tratamentos.get(c, {}).get("tratamentos", []),
                                    "causas": tratamentos.get(c, {}).get("causas", [])})
    top = (doencas_especificas[(doencas_especificas.cap == r.cap) & (doencas_especificas.faixa_etaria == r.faixa_etaria)]
           .sort_values("internacoes", ascending=False))
    sim["capitulos"][c]["por_faixa"][r.faixa_etaria] = {
        "internacoes": int(r.internacoes), "obitos": int(r.obitos),
        "tx_mortalidade": r.tx_mortalidade, "media_permanencia": r.media_permanencia,
        "top_doencas": top[["doenca", "internacoes", "tx_mortalidade"]].head(10).to_dict("records"),
    }
for _, h in hospitais.iterrows():
    sim["hospitais"][h.cnes] = {"nome": h.hospital, "regiao": h.regiao_saude, "macro": h.macrorregiao,
                                "internacoes": int(h.internacoes)}
for _, r in hdi[hdi.internacoes >= 1].iterrows():
    sim["grupos"].append([r.cnes, int(r.cap), FAIXAS.index(r.faixa_etaria), int(r.internacoes), int(r.obitos),
                          r.media_permanencia, r.tx_ajustada])
prob = base.set_index(["cnes", "cap", "faixa_etaria"])["prob_acima"]
sim["prob_acima"] = {f"{c}|{k}|{FAIXAS.index(f)}": float(v) for (c, k, f), v in prob.items()}
sim["colunas_grupos"] = ["cnes", "cap", "faixa", "internacoes", "obitos", "media_permanencia", "tx_ajustada"]

def limpa(o):
    # NaN não existe em JSON; vira null (acontece quando o grupo não teve internação, ex.: parto em criança)
    if isinstance(o, dict):
        return {k: limpa(v) for k, v in o.items()}
    if isinstance(o, list):
        return [limpa(v) for v in o]
    if isinstance(o, (float, np.floating)):
        return None if np.isnan(o) else float(o)
    if isinstance(o, np.integer):
        return int(o)
    return o

with open("simulador.json", "w", encoding="utf-8") as f:
    json.dump(limpa(sim), f, ensure_ascii=False, separators=(",", ":"))
tabela.to_csv("metricas_modelos.csv", sep=";")
print("simulador.json:", round(os.path.getsize("simulador.json") / 1024), "KB")

# %%
from google.colab import files
with zipfile.ZipFile("tspe_modelo_saidas.zip", "w") as z:
    for a in ["simulador.json", "metricas_modelos.csv", "relatorio_modelos.json"]:
        z.write(a)
files.download("tspe_modelo_saidas.zip")
