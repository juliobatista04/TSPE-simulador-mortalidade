# %% [markdown]
# # TSPE · Mortalidade hospitalar no SUS em Pernambuco
# ## Caderno 1: baixar os dados do TABNET e tratar
#
# Base: SIH/SUS, Morbidade Hospitalar por local de internação, Pernambuco.
# Período: **outubro/2025 a setembro/2026** (os 12 meses mais recentes publicados no TABNET).
#
# O que sai daqui (pasta `data/processado`):
#
# | arquivo | uma linha é | pra que serve |
# |---|---|---|
# | `doenca_idade.csv` | capítulo CID × faixa etária (estado todo) | taxa de mortalidade e permanência de referência |
# | `hosp_doenca.csv` | hospital × capítulo (todas as idades) | melhor hospital por doença |
# | `hosp_doenca_idade.csv` | hospital × capítulo × faixa etária | base do modelo e do simulador |
# | `hospitais.csv` | hospital | região de saúde, macro, microrregião e volume |
# | `doencas_especificas.csv` | doença da Lista de Morbidade × faixa | ranking das 5 principais doenças do grupo |
# | `mensal.csv` | mês × capítulo | evolução no período |
# | `tratamentos.json` | capítulo | causas e tratamentos (texto do grupo) |
#
# A diferença pra versão anterior: agora o TABNET devolve **óbitos e dias de permanência em número absoluto**.
# Com isso a taxa de mortalidade e a média de permanência são recalculadas por nós, sem depender da taxa arredondada,
# e dá pra somar hospital com hospital sem distorcer.

# %%
import os, re, io, json, time, zipfile
import pandas as pd
import requests
from urllib.parse import quote

os.makedirs("data/raw/estado", exist_ok=True)
os.makedirs("data/raw/hospitais/por_faixa", exist_ok=True)
os.makedirs("data/processado", exist_ok=True)

# %% [markdown]
# ## Etapa 1 · Baixar do TABNET
#
# Em vez de clicar no site 50 vezes, a gente manda a mesma consulta que o formulário do TABNET manda.
# Cada tabela vem no formato "colunas separadas por ;" e é salva do jeito que veio, sem mexer, em `data/raw`.
# Se o arquivo já existe, pula. Demora uns 10 minutos (o TABNET é lento e às vezes cai, por isso tem nova tentativa).
#
# **Atenção:** o TABNET costuma derrubar conexões vindas do Colab (os servidores do Google ficam fora do Brasil).
# No nosso teste ele respondeu as primeiras tabelas e depois parou. Por isso o caminho que funciona sempre é:
# rodar `scripts/baixar_tabnet.ps1` num computador aqui no Brasil, zipar a pasta `dados/brutos` como `brutos.zip`
# e subir o zip na aba de arquivos do Colab (ícone de pasta à esquerda). A célula abaixo descompacta e
# a de download só busca o que estiver faltando.

# %%
if os.path.exists("brutos.zip"):
    with zipfile.ZipFile("brutos.zip") as z:
        z.extractall("data/raw")
    print("brutos.zip descompactado em data/raw")
else:
    print("sem brutos.zip, vou tentar baixar direto do TABNET")

# %%
URL = "https://tabnet.datasus.gov.br/cgi/tabcgi.exe?sih/cnv/nipe.def"
MESES = ["2510","2511","2512","2601","2602","2603","2604","2605","2606","2607","2608","2609"]

def enc(s):
    # o TABNET só entende o formulário em latin-1
    return quote(s, safe="", encoding="latin-1")

def baixar_tabnet(linha, coluna, incremento, saida, filtros=None):
    destino = os.path.join("data/raw", saida)
    if os.path.exists(destino):
        return
    partes = [f"Linha={enc(linha)}", f"Coluna={enc(coluna)}", f"Incremento={enc(incremento)}"]
    partes += [f"Arquivos=nipe{m}.dbf" for m in MESES]
    for k, v in (filtros or {}).items():
        partes.append(f"{enc(k)}={enc(v)}")
    partes += ["formato=prn", "mostre=Mostra"]
    corpo = "&".join(partes)
    for tentativa in range(1, 5):
        try:
            r = requests.post(URL, data=corpo, timeout=180,
                              headers={"Content-Type": "application/x-www-form-urlencoded"})
            html = r.content.decode("latin-1")
            ini, fim = html.find("<PRE>"), html.find("</PRE>")
            if ini < 0:
                raise ValueError("resposta sem tabela")
            import html as h
            texto = h.unescape(html[ini + 5:fim]).strip()
            os.makedirs(os.path.dirname(destino), exist_ok=True)
            with open(destino, "w", encoding="utf-8") as f:
                f.write(texto)
            print("ok:", saida)
            time.sleep(0.8)
            return
        except Exception as e:
            print(f"tentativa {tentativa} falhou em {saida}: {e}")
            time.sleep(3 * tentativa)
    raise RuntimeError(f"não consegui baixar {saida}")

METRICAS = {"internacoes": "Internações", "obitos": "Óbitos", "dias": "Dias_permanência"}

# visão do estado
for m, nome in METRICAS.items():
    baixar_tabnet("Capítulo_CID-10", "Faixa_Etária_1", nome, f"estado/capitulo_x_faixa_{m}.csv")
    baixar_tabnet("Lista_Morb__CID-10", "Faixa_Etária_1", nome, f"estado/doenca_x_faixa_{m}.csv")
    baixar_tabnet("Ano/mês_processamento", "Capítulo_CID-10", nome, f"estado/mes_x_capitulo_{m}.csv")

# visão por hospital
for m, nome in METRICAS.items():
    baixar_tabnet("Estabelecimento", "Capítulo_CID-10", nome, f"hospitais/hospital_x_capitulo_{m}.csv")
    baixar_tabnet("Estabelecimento", "Faixa_Etária_1", nome, f"hospitais/hospital_x_faixa_{m}.csv")
baixar_tabnet("Estabelecimento", "Região_de_Saúde_(CIR)", "Internações", "hospitais/hospital_x_regiao_saude.csv")
baixar_tabnet("Estabelecimento", "Macrorregião_de_Saúde", "Internações", "hospitais/hospital_x_macrorregiao.csv")
baixar_tabnet("Estabelecimento", "Microrregião_IBGE", "Internações", "hospitais/hospital_x_microrregiao.csv")
baixar_tabnet("Estabelecimento", "Caráter_atendimento", "Internações", "hospitais/hospital_x_carater.csv")

# hospital x capítulo, uma tabela por faixa etária (o TABNET só cruza duas coisas por vez,
# então a terceira, a idade, entra como filtro)
FAIXAS = ["Menor 1 ano", "1 a 4 anos", "5 a 9 anos", "10 a 14 anos", "15 a 19 anos", "20 a 29 anos",
          "30 a 39 anos", "40 a 49 anos", "50 a 59 anos", "60 a 69 anos", "70 a 79 anos", "80 anos e mais"]
APELIDO_FAIXA = ["menor1", "1a4", "5a9", "10a14", "15a19", "20a29", "30a39", "40a49", "50a59", "60a69", "70a79", "80mais"]
for i, ap in enumerate(APELIDO_FAIXA, start=1):
    for m, nome in METRICAS.items():
        baixar_tabnet("Estabelecimento", "Capítulo_CID-10", nome,
                      f"hospitais/por_faixa/hospital_x_capitulo_{m}_faixa{i:02d}_{ap}.csv",
                      {"SFaixa_Etária_1": str(i)})
print("download concluído")

# %% [markdown]
# ## Etapa 3 · Tratamento
#
# Mesma lógica do caderno `tratamento_dados_ML 2` do grupo: ler o CSV do TABNET, tirar a linha e a coluna de Total,
# limpar os códigos na frente dos nomes, converter o número brasileiro pra número do Python e "derreter" a tabela larga
# em formato longo (uma linha por combinação).
#
# Regra pro "-" do TABNET: quer dizer **zero**, não dado faltando. Por isso vira 0.

# %%
def ler_csv_tabnet(caminho):
    linhas = []
    with open(caminho, encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if not linha:
                continue
            baixo = linha.lower()
            if baixo.startswith(("fonte", "notas", "consulte")):
                break
            if ";" not in linha:   # sobra de HTML no fim da tabela (um "&" solto)
                continue
            linhas.append(linha)
    return pd.read_csv(io.StringIO("\n".join(linhas)), sep=";", quotechar='"', dtype=str)

def limpar_numero(val):
    if pd.isna(val) or str(val).strip() in ["-", "...", ""]:
        return 0.0
    s = str(val).strip().replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None

def limpar_hospital(val):
    # '2345678 HOSPITAL TAL' -> ('2345678', 'HOSPITAL TAL')
    m = re.match(r"^(\d+)\s+(.*)$", str(val).strip())
    return (m.group(1), m.group(2).strip()) if m else ("", str(val).strip())

def derreter(df, col_chave, col_chave_nome, col_valor_nome):
    cols_valor = [c for c in df.columns if c != col_chave and c != "Total"]
    return df.melt(id_vars=[col_chave], value_vars=cols_valor, var_name=col_chave_nome, value_name=col_valor_nome)

def sem_total(df):
    df = df.drop(columns=["Total"], errors="ignore")
    return df[df.iloc[:, 0].str.strip() != "Total"].dropna(subset=[df.columns[0]])

# %% [markdown]
# ### Nome dos capítulos
#
# O TABNET escreve o capítulo de três jeitos diferentes conforme a tabela: "I.   Algumas doenças..." (capítulo × faixa),
# "01 Algumas doenças..." (lista de morbidade) e só "Cap 01" quando o capítulo vira coluna (hospital × capítulo). Aqui tudo vira um número de capítulo (1 a 21)
# e um nome por extenso, que é o que aparece na página.

# %%
ROMANOS = {"I":1,"II":2,"III":3,"IV":4,"V":5,"VI":6,"VII":7,"VIII":8,"IX":9,"X":10,"XI":11,"XII":12,"XIII":13,
           "XIV":14,"XV":15,"XVI":16,"XVII":17,"XVIII":18,"XIX":19,"XX":20,"XXI":21}
NOME_CAPITULO = {
    1: "Algumas doenças infecciosas e parasitárias",
    2: "Neoplasias (tumores)",
    3: "Doenças do sangue e dos órgãos hematopoéticos e alguns transtornos imunitários",
    4: "Doenças endócrinas, nutricionais e metabólicas",
    5: "Transtornos mentais e comportamentais",
    6: "Doenças do sistema nervoso",
    7: "Doenças do olho e anexos",
    8: "Doenças do ouvido e da apófise mastoide",
    9: "Doenças do aparelho circulatório",
    10: "Doenças do aparelho respiratório",
    11: "Doenças do aparelho digestivo",
    12: "Doenças da pele e do tecido subcutâneo",
    13: "Doenças do sistema osteomuscular e do tecido conjuntivo",
    14: "Doenças do aparelho geniturinário",
    15: "Gravidez, parto e puerpério",
    16: "Algumas afecções originadas no período perinatal",
    17: "Malformações congênitas, deformidades e anomalias cromossômicas",
    18: "Sintomas, sinais e achados anormais de exames clínicos e de laboratório",
    19: "Lesões, envenenamentos e algumas outras consequências de causas externas",
    20: "Causas externas de morbidade e mortalidade",
    21: "Contatos com serviços de saúde",
}

def numero_capitulo(rotulo):
    r = str(rotulo).strip()
    m = re.match(r"^([IVXL]+)\.", r)
    if m:
        return ROMANOS.get(m.group(1))
    m = re.match(r"^(?:Cap\s+)?(\d{2})\b", r)   # "01 Algumas..." ou "Cap 01"
    if m:
        return int(m.group(1))
    return None

# %% [markdown]
# ### Doença × faixa etária (estado)

# %%
def tabela_longa(arquivos, chave, col_coluna, tratar_chave=None):
    """Lê as três métricas (internações, óbitos, dias), derrete e junta numa tabela só."""
    partes = []
    for metrica, caminho in arquivos.items():
        df = sem_total(ler_csv_tabnet(caminho))
        col0 = df.columns[0]
        longo = derreter(df, col0, col_coluna, metrica).rename(columns={col0: chave})
        longo[metrica] = longo[metrica].apply(limpar_numero)
        partes.append(longo)
    base = partes[0]
    for p in partes[1:]:
        base = base.merge(p, on=[chave, col_coluna], how="outer")
    base[list(arquivos)] = base[list(arquivos)].fillna(0)
    return base

def taxas(df):
    df["media_permanencia"] = (df["dias"] / df["internacoes"]).where(df["internacoes"] > 0).round(2)
    df["tx_mortalidade"] = (100 * df["obitos"] / df["internacoes"]).where(df["internacoes"] > 0).round(2)
    return df

doenca_idade = tabela_longa(
    {m: f"data/raw/estado/capitulo_x_faixa_{m}.csv" for m in METRICAS}, "rotulo", "faixa_etaria")
doenca_idade["cap"] = doenca_idade["rotulo"].apply(numero_capitulo)
doenca_idade["doenca_cid"] = doenca_idade["cap"].map(NOME_CAPITULO)
doenca_idade = doenca_idade[doenca_idade["faixa_etaria"].isin(FAIXAS)]
doenca_idade = taxas(doenca_idade)[["cap", "doenca_cid", "faixa_etaria", "internacoes", "obitos", "dias",
                                    "media_permanencia", "tx_mortalidade"]].sort_values(["cap", "faixa_etaria"])
print(doenca_idade.shape)
doenca_idade.head()

# %% [markdown]
# ### Hospitais: onde ficam e quanto atendem
#
# O TABNET não cruza estabelecimento com município, mas cruza com região de saúde, macrorregião e microrregião.
# Cada hospital só tem internação na própria região, então a coluna com valor é a região dele.
# É isso que o simulador usa pra achar "o hospital melhor mais perto".

# %%
def regiao_do_hospital(caminho, nome_col):
    df = sem_total(ler_csv_tabnet(caminho))
    col0 = df.columns[0]
    valores = df.drop(columns=[col0]).apply(lambda c: c.map(limpar_numero))
    out = pd.DataFrame({"rotulo": df[col0], nome_col: valores.idxmax(axis=1)})
    out[nome_col] = out[nome_col].str.replace(r"^\d+\s+", "", regex=True).str.strip()
    return out

hospitais = regiao_do_hospital("data/raw/hospitais/hospital_x_regiao_saude.csv", "regiao_saude")
hospitais = hospitais.merge(regiao_do_hospital("data/raw/hospitais/hospital_x_macrorregiao.csv", "macrorregiao"), on="rotulo", how="left")
hospitais = hospitais.merge(regiao_do_hospital("data/raw/hospitais/hospital_x_microrregiao.csv", "microrregiao"), on="rotulo", how="left")

hosp_tot = tabela_longa({m: f"data/raw/hospitais/hospital_x_faixa_{m}.csv" for m in METRICAS}, "rotulo", "faixa_etaria")
hosp_tot = hosp_tot.groupby("rotulo")[list(METRICAS)].sum().reset_index()
hospitais = hospitais.merge(hosp_tot, on="rotulo", how="left")

carater = sem_total(ler_csv_tabnet("data/raw/hospitais/hospital_x_carater.csv"))
c0 = carater.columns[0]
carater_num = carater.drop(columns=[c0]).apply(lambda c: c.map(limpar_numero))
col_urg = [c for c in carater_num.columns if "rg" in c.lower()]  # "Urgência"
carater_df = pd.DataFrame({"rotulo": carater[c0],
                           "pct_urgencia": (100 * carater_num[col_urg].sum(axis=1) / carater_num.sum(axis=1)).round(1)})
hospitais = hospitais.merge(carater_df, on="rotulo", how="left")

hospitais[["cnes", "hospital"]] = hospitais["rotulo"].apply(lambda v: pd.Series(limpar_hospital(v)))
hospitais = taxas(hospitais)
hospitais = hospitais[["cnes", "hospital", "regiao_saude", "macrorregiao", "microrregiao", "internacoes", "obitos",
                       "dias", "media_permanencia", "tx_mortalidade", "pct_urgencia"]].sort_values("internacoes", ascending=False)
print(hospitais.shape)
hospitais.head(10)

# %% [markdown]
# ### Hospital × doença (todas as idades) e hospital × doença × faixa etária

# %%
hosp_doenca = tabela_longa({m: f"data/raw/hospitais/hospital_x_capitulo_{m}.csv" for m in METRICAS}, "rotulo", "rotulo_cap")

partes = []
for i, ap in enumerate(APELIDO_FAIXA, start=1):
    arqs = {m: f"data/raw/hospitais/por_faixa/hospital_x_capitulo_{m}_faixa{i:02d}_{ap}.csv" for m in METRICAS}
    t = tabela_longa(arqs, "rotulo", "rotulo_cap")
    t["faixa_etaria"] = FAIXAS[i - 1]
    partes.append(t)
hosp_doenca_idade = pd.concat(partes, ignore_index=True)

def acabamento_hospital(df):
    df["cap"] = df["rotulo_cap"].apply(numero_capitulo)
    df["doenca_cid"] = df["cap"].map(NOME_CAPITULO)
    df[["cnes", "hospital"]] = df["rotulo"].apply(lambda v: pd.Series(limpar_hospital(v)))
    df = df[df["internacoes"] > 0].copy()   # combinação sem internação não é informação, é célula vazia
    return taxas(df).drop(columns=["rotulo", "rotulo_cap"])

hosp_doenca = acabamento_hospital(hosp_doenca)
hosp_doenca_idade = acabamento_hospital(hosp_doenca_idade)
hosp_doenca_idade = hosp_doenca_idade.merge(hospitais[["cnes", "regiao_saude", "macrorregiao"]], on="cnes", how="left")
print("hosp_doenca:", hosp_doenca.shape, "| hosp_doenca_idade:", hosp_doenca_idade.shape)
hosp_doenca_idade.head()

# %% [markdown]
# ### Doenças específicas (Lista de Morbidade CID-10)
#
# Essa tabela vem "aninhada": uma linha com o capítulo ("01 Algumas doenças...") e embaixo as doenças dele ("..  Cólera").
# Basta lembrar do último capítulo visto pra saber de qual grupo cada doença é.
# Serve pro ranking das 5 principais doenças do grupo selecionado.

# %%
def ler_lista_morb(metrica):
    df = sem_total(ler_csv_tabnet(f"data/raw/estado/doenca_x_faixa_{metrica}.csv"))
    col0 = df.columns[0]
    cap_atual, caps, nomes, eh_cap = None, [], [], []
    for rot in df[col0]:
        r = str(rot).strip()
        if r.startswith(".."):
            caps.append(cap_atual); nomes.append(r.lstrip(". ").strip()); eh_cap.append(False)
        else:
            cap_atual = numero_capitulo(r)
            caps.append(cap_atual); nomes.append(r); eh_cap.append(True)
    df["cap"], df["doenca"], df["eh_cap"] = caps, nomes, eh_cap
    df = df[~df["eh_cap"]].drop(columns=[col0, "eh_cap"])
    longo = df.melt(id_vars=["cap", "doenca"], var_name="faixa_etaria", value_name=metrica)
    longo[metrica] = longo[metrica].apply(limpar_numero)
    return longo

doencas_especificas = ler_lista_morb("internacoes")
for m in ["obitos", "dias"]:
    doencas_especificas = doencas_especificas.merge(ler_lista_morb(m), on=["cap", "doenca", "faixa_etaria"], how="left")
doencas_especificas = doencas_especificas[doencas_especificas["faixa_etaria"].isin(FAIXAS)].fillna(0)
doencas_especificas["doenca_cid"] = doencas_especificas["cap"].map(NOME_CAPITULO)
doencas_especificas = taxas(doencas_especificas)
print(doencas_especificas.shape)

# exemplo: top 5 do capítulo IX (circulatório), todas as idades
(doencas_especificas[doencas_especificas.cap == 9].groupby("doenca")[["internacoes", "obitos"]].sum()
 .sort_values("internacoes", ascending=False).head(5))

# %% [markdown]
# ### Evolução mensal

# %%
mensal = tabela_longa({m: f"data/raw/estado/mes_x_capitulo_{m}.csv" for m in METRICAS}, "mes", "rotulo_cap")
mensal["cap"] = mensal["rotulo_cap"].apply(numero_capitulo)
mensal["doenca_cid"] = mensal["cap"].map(NOME_CAPITULO)
mensal = taxas(mensal.drop(columns=["rotulo_cap"]))
mensal = mensal[(mensal["internacoes"] > 0) & mensal["mes"].str.contains("/")]  # o TABNET mistura subtotais por ano ("2025") no meio dos meses
mensal.groupby("mes")[["internacoes", "obitos"]].sum()

# %% [markdown]
# ### Causas e tratamentos por capítulo
#
# Texto escrito pelo grupo. É informativo, não é recomendação médica. Fica num JSON pra página ler direto.

# %%
TRATAMENTOS = {
 1: {"causas": ["Infecção por vírus, como os causadores da dengue e da hepatite.", "Infecção por bactérias, como as responsáveis pela tuberculose.", "Infecção por parasitas, como os causadores da malária e da esquistossomose.", "Consumo de água ou alimentos contaminados.", "Picadas de vetores infectados, como mosquitos."],
     "tratamentos": ["Antibióticos para determinadas infecções bacterianas.", "Antivirais para infecções virais específicas, como algumas hepatites.", "Antiparasitários para combater vermes e protozoários.", "Hidratação oral ou intravenosa, especialmente em casos de desidratação.", "Tratamento de suporte, com controle da febre, repouso e monitoramento das complicações."]},
 2: {"causas": ["Alterações genéticas que provocam crescimento celular descontrolado.", "Predisposição hereditária e histórico familiar.", "Tabagismo e exposição a substâncias cancerígenas.", "Exposição excessiva à radiação ultravioleta e a outras formas de radiação.", "Infecções associadas ao câncer, como HPV e hepatites B e C."],
     "tratamentos": ["Cirurgia para retirada do tumor.", "Quimioterapia para destruir ou controlar células cancerígenas.", "Radioterapia para atingir células tumorais por meio de radiação.", "Imunoterapia para estimular o sistema imunológico a combater o câncer.", "Terapia-alvo, que atua sobre alterações específicas das células tumorais."]},
 3: {"causas": ["Deficiência de ferro, vitamina B12 ou ácido fólico.", "Alterações genéticas que afetam a produção ou a estrutura das células sanguíneas.", "Doenças autoimunes que atacam células do próprio organismo.", "Infecções que comprometem a medula óssea ou o sistema imunológico.", "Perda excessiva de sangue ou doenças que prejudicam sua produção."],
     "tratamentos": ["Suplementação de ferro, vitamina B12 ou ácido fólico, conforme a deficiência.", "Transfusões de sangue em casos de anemia grave ou perda sanguínea importante.", "Medicamentos imunossupressores para determinadas doenças autoimunes.", "Quimioterapia para alguns cânceres hematológicos.", "Transplante de medula óssea ou de células-tronco hematopoéticas em doenças selecionadas."]},
 4: {"causas": ["Produção insuficiente ou resistência à ação da insulina.", "Alterações hormonais na tireoide, hipófise ou outras glândulas.", "Alimentação inadequada e desequilibrada.", "Predisposição genética e histórico familiar.", "Sedentarismo e alterações no metabolismo energético."],
     "tratamentos": ["Insulinoterapia para pessoas que necessitam de insulina.", "Medicamentos para controle da glicemia, como a metformina em pacientes indicados.", "Reposição hormonal, como levotiroxina no hipotireoidismo.", "Acompanhamento nutricional e reeducação alimentar.", "Atividade física orientada e controle do peso corporal."]},
 5: {"causas": ["Predisposição genética e histórico familiar.", "Alterações biológicas e neuroquímicas relacionadas ao funcionamento cerebral.", "Experiências traumáticas e situações de violência.", "Estresse prolongado e condições sociais desfavoráveis.", "Uso abusivo de álcool e outras substâncias psicoativas."],
     "tratamentos": ["Psicoterapia, como a terapia cognitivo-comportamental.", "Antidepressivos, em casos nos quais são indicados.", "Ansiolíticos, em situações específicas e com acompanhamento médico.", "Estabilizadores de humor para determinados transtornos, como o bipolar.", "Acompanhamento psiquiátrico e programas de reabilitação psicossocial."]},
 6: {"causas": ["Alterações genéticas e hereditárias.", "Infecções que atingem o cérebro e a medula espinhal.", "Acidentes vasculares cerebrais e lesões neurológicas.", "Doenças degenerativas que provocam perda progressiva de neurônios.", "Alterações autoimunes que atacam estruturas do sistema nervoso."],
     "tratamentos": ["Medicamentos anticonvulsivantes para controle da epilepsia.", "Medicamentos dopaminérgicos para controle dos sintomas do Parkinson.", "Medicamentos específicos para controle de sintomas de doenças neurodegenerativas.", "Fisioterapia e reabilitação neurológica.", "Terapias imunomoduladoras para determinadas doenças, como a esclerose múltipla."]},
 7: {"causas": ["Envelhecimento natural das estruturas oculares.", "Infecções bacterianas ou virais.", "Diabetes e suas complicações, como a retinopatia diabética.", "Pressão intraocular elevada, associada ao glaucoma.", "Exposição excessiva à radiação ultravioleta e lesões oculares."],
     "tratamentos": ["Colírios antibióticos para determinadas infecções bacterianas.", "Colírios anti-inflamatórios, quando indicados.", "Medicamentos para reduzir a pressão intraocular no glaucoma.", "Cirurgia de catarata com substituição do cristalino por uma lente artificial.", "Injeções intraoculares e tratamentos a laser para determinadas doenças da retina."]},
 8: {"causas": ["Infecções bacterianas ou virais.", "Acúmulo excessivo de cera no canal auditivo.", "Exposição prolongada a ruídos intensos.", "Envelhecimento e degeneração das estruturas auditivas.", "Alterações no ouvido interno ou nos mecanismos responsáveis pelo equilíbrio."],
     "tratamentos": ["Antibióticos para determinadas infecções bacterianas.", "Medicamentos para aliviar dor e inflamação.", "Remoção profissional de cerume quando necessário.", "Aparelhos auditivos para determinados tipos de perda auditiva.", "Fisioterapia vestibular para alterações do equilíbrio."]},
 9: {"causas": ["Hipertensão arterial não controlada.", "Colesterol elevado e acúmulo de placas de gordura nas artérias.", "Tabagismo.", "Diabetes mellitus.", "Sedentarismo, obesidade e alimentação inadequada."],
     "tratamentos": ["Medicamentos anti-hipertensivos para controle da pressão arterial.", "Estatinas e outros medicamentos para controle do colesterol.", "Anticoagulantes ou antiagregantes plaquetários em situações específicas.", "Procedimentos como angioplastia para desobstrução de artérias.", "Cirurgias cardiovasculares, como revascularização do miocárdio, quando necessárias."]},
 10: {"causas": ["Infecções causadas por vírus e bactérias.", "Tabagismo e exposição à fumaça.", "Poluição atmosférica e exposição a agentes químicos.", "Alergias e exposição a ácaros, poeira e mofo.", "Predisposição genética e alterações estruturais do sistema respiratório."],
      "tratamentos": ["Antibióticos para infecções bacterianas específicas, como algumas pneumonias.", "Broncodilatadores para facilitar a passagem de ar.", "Corticoides inalatórios para controle de determinadas doenças inflamatórias, como a asma.", "Oxigenoterapia para pacientes com níveis insuficientes de oxigênio.", "Fisioterapia respiratória e reabilitação pulmonar."]},
 11: {"causas": ["Infecção pela bactéria Helicobacter pylori.", "Consumo excessivo de álcool.", "Alimentação inadequada e hábitos alimentares prejudiciais.", "Uso prolongado de determinados medicamentos, como anti-inflamatórios.", "Infecções, alterações autoimunes e doenças que comprometem órgãos digestivos."],
      "tratamentos": ["Medicamentos que reduzem a produção de ácido gástrico, como os inibidores da bomba de prótons.", "Antibióticos associados a outros medicamentos para erradicação do H. pylori.", "Mudanças alimentares e acompanhamento nutricional.", "Hidratação e reposição de eletrólitos em casos de vômitos e diarreia.", "Cirurgias e procedimentos endoscópicos para determinadas complicações digestivas."]},
 12: {"causas": ["Infecções por bactérias, fungos e vírus.", "Reações alérgicas a produtos químicos e cosméticos.", "Alterações autoimunes e inflamatórias.", "Predisposição genética.", "Exposição excessiva ao sol e a agentes irritantes."],
      "tratamentos": ["Cremes e pomadas antibióticas para determinadas infecções bacterianas.", "Medicamentos antifúngicos para combater micoses.", "Corticoides tópicos para determinadas inflamações e dermatites.", "Medicamentos imunomoduladores para doenças como a psoríase.", "Hidratantes e produtos dermatológicos para recuperação da barreira cutânea."]},
 13: {"causas": ["Envelhecimento e desgaste das articulações.", "Predisposição genética.", "Movimentos repetitivos e sobrecarga física.", "Doenças autoimunes que provocam inflamações nas articulações.", "Sedentarismo, excesso de peso e alterações posturais."],
      "tratamentos": ["Fisioterapia para recuperar movimentos e fortalecer a musculatura.", "Medicamentos analgésicos para aliviar a dor.", "Anti-inflamatórios em situações específicas e sob orientação médica.", "Medicamentos específicos para osteoporose, como os bisfosfonatos, quando indicados.", "Cirurgias ortopédicas, como a substituição de articulações em casos graves."]},
 14: {"causas": ["Infecções bacterianas do trato urinário.", "Diabetes mellitus, que pode comprometer os rins.", "Hipertensão arterial prolongada.", "Formação de cálculos renais devido a alterações na composição da urina.", "Alterações anatômicas, obstruções urinárias e doenças hereditárias."],
      "tratamentos": ["Antibióticos para infecções urinárias bacterianas.", "Medicamentos para controle da pressão arterial e proteção renal.", "Hidratação orientada e medidas para prevenção de cálculos renais.", "Procedimentos como litotripsia para fragmentar determinados cálculos.", "Diálise ou transplante renal em casos selecionados de insuficiência renal avançada."]},
 15: {"causas": ["Alterações na pressão arterial durante a gestação.", "Resistência à insulina e alterações metabólicas.", "Infecções durante a gravidez ou após o parto.", "Alterações na placenta, como placenta prévia e descolamento prematuro.", "Condições maternas preexistentes, como obesidade, diabetes e doenças cardiovasculares."],
      "tratamentos": ["Acompanhamento pré-natal regular para identificar e controlar complicações.", "Medicamentos anti-hipertensivos para controle da pressão arterial.", "Insulina para controle do diabetes gestacional quando necessária.", "Antibióticos para tratamento de infecções bacterianas.", "Procedimentos obstétricos, como cesariana ou intervenções para controle de hemorragias, quando indicados."]},
 16: {"causas": ["Nascimento prematuro.", "Infecções maternas transmitidas ao bebê durante a gestação ou o parto.", "Insuficiência placentária e falta de oxigenação adequada durante a gestação ou o nascimento.", "Baixo peso ao nascer e restrição do crescimento fetal.", "Complicações respiratórias relacionadas à imaturidade dos pulmões."],
      "tratamentos": ["Incubadoras e cuidados especializados para recém-nascidos prematuros.", "Oxigenoterapia e suporte ventilatório para dificuldades respiratórias.", "Fototerapia para tratamento de determinados casos de icterícia neonatal.", "Antibióticos para infecções bacterianas neonatais.", "Alimentação por sonda ou suporte nutricional especializado para bebês que não conseguem se alimentar adequadamente."]},
 17: {"causas": ["Alterações genéticas herdadas dos pais.", "Alterações cromossômicas durante a formação do embrião.", "Exposição a determinados medicamentos e substâncias teratogênicas durante a gestação.", "Infecções maternas, como a rubéola congênita.", "Deficiências nutricionais durante a gestação, como a deficiência de ácido fólico, associada a defeitos do tubo neural."],
      "tratamentos": ["Cirurgias corretivas para determinadas malformações.", "Fisioterapia para melhorar o desenvolvimento motor e funcional.", "Terapia ocupacional para desenvolver autonomia nas atividades diárias.", "Acompanhamento multidisciplinar com médicos especialistas, fonoaudiólogos e outros profissionais.", "Medicamentos e tratamentos específicos para complicações associadas, como problemas cardíacos e hormonais."]},
 18: {"causas": ["Infecções ainda não identificadas.", "Alterações hormonais e metabólicas.", "Doenças cardiovasculares e respiratórias.", "Distúrbios gastrointestinais.", "Alterações neurológicas e inflamatórias."],
      "tratamentos": ["Exames laboratoriais para identificar possíveis alterações.", "Exames de imagem, como radiografia, ultrassonografia e tomografia.", "Medicamentos para aliviar sintomas, como analgésicos e antitérmicos, quando indicados.", "Tratamento direcionado à doença identificada após investigação clínica.", "Monitoramento e acompanhamento médico para avaliar a evolução dos sintomas."]},
 19: {"causas": ["Acidentes de trânsito.", "Quedas e acidentes domésticos.", "Acidentes de trabalho.", "Exposição a substâncias tóxicas e produtos químicos.", "Agressões físicas e outros episódios de violência."],
      "tratamentos": ["Imobilização de fraturas e lesões ósseas.", "Cirurgias para reparar tecidos e estruturas danificadas.", "Curativos e cuidados especializados para queimaduras e ferimentos.", "Administração de antídotos específicos em determinadas intoxicações.", "Reabilitação física e fisioterapia após traumatismos e lesões."]},
}
tratamentos = {str(k): {"doenca_cid": NOME_CAPITULO[k], **v} for k, v in TRATAMENTOS.items()}

# %% [markdown]
# ## Conferência
#
# Antes de salvar, três checagens simples. Se alguma falhar, o problema está no download ou na leitura, não no modelo.

# %%
total_estado = doenca_idade["internacoes"].sum()
total_hosp = hosp_doenca_idade["internacoes"].sum()
print(f"internações no estado (capítulo × faixa): {total_estado:,.0f}")
print(f"internações somando hospital × capítulo × faixa: {total_hosp:,.0f}")
print(f"óbitos no estado: {doenca_idade['obitos'].sum():,.0f}  | taxa geral: {100*doenca_idade['obitos'].sum()/total_estado:.2f}%")
print(f"hospitais com internação: {hospitais['cnes'].nunique()}  | sem região identificada: {hospitais['regiao_saude'].isna().sum()}")
assert abs(total_estado - total_hosp) / total_estado < 0.01, "soma dos hospitais não bate com o estado"
assert doenca_idade["cap"].notna().all() and hosp_doenca_idade["cap"].notna().all(), "capítulo sem número"

# %% [markdown]
# ## Salvar

# %%
saidas = {"doenca_idade": doenca_idade, "hospitais": hospitais, "hosp_doenca": hosp_doenca,
          "hosp_doenca_idade": hosp_doenca_idade, "doencas_especificas": doencas_especificas, "mensal": mensal}
for nome, df in saidas.items():
    df.to_csv(f"data/processado/{nome}.csv", index=False, sep=";", encoding="utf-8")
    print(f"{nome}: {df.shape}")
with open("data/processado/tratamentos.json", "w", encoding="utf-8") as f:
    json.dump(tratamentos, f, ensure_ascii=False, indent=1)

with zipfile.ZipFile("tspe_dados.zip", "w", zipfile.ZIP_DEFLATED) as z:
    for pasta in ["data/raw", "data/processado"]:
        for raiz, _, arqs in os.walk(pasta):
            for a in arqs:
                z.write(os.path.join(raiz, a))
print("zip pronto: tspe_dados.zip")

# %%
# baixa o zip com tudo (brutos + processados) pro computador
from google.colab import files
files.download("tspe_dados.zip")
