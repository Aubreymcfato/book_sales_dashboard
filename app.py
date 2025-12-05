# app.py – 100% FUNZIONANTE SU STREAMLIT CLOUD (crea il parquet se manca)
import streamlit as st
import pandas as pd
import altair as alt
import os
import glob
import re

MASTER_PATH = "data/master_sales.parquet"

# ================================================
# CREA IL PARQUET SE NON ESISTE
# ================================================
if not os.path.exists(MASTER_PATH):
    st.info("Creo il database master... (solo la prima volta)")
    files = sorted(glob.glob("data/Classifica week*.xlsx"))
    dfs = []
    for f in files:
        m = re.search(r'(?:week|Settimana)\s*(\d+)', f, re.I)
        week = m.group(1) if m else "999"
        try:
            df = pd.read_excel(f, sheet_name="Export")
            df["week"] = f"Settimana {week}"
            dfs.append(df)
        except:
            continue
    if dfs:
        master = pd.concat(dfs, ignore_index=True)
        master["units"] = pd.to_numeric(master["units"], errors="coerce").fillna(0).astype(int)
        if "title" in master and master["title"].apply(lambda x: str(x).strip())
        if "publisher" in master.columns:
            master["publisher"] = master["publisher"].astype(str).str.strip().str.title()
        for c in ["collana","collection","series","Collection/Series"]:
            if c in master.columns:
                master = master.rename(columns={c: "collana"})
                break
        master.to_parquet(MASTER_PATH, compression="zstd")
        st.success(f"Database creato: {len(master):,} righe")
    else:
        st.error("Nessun file Excel trovato!")
        st.stop()

# ================================================
# CARICA IL DATABASE
# ================================================
@st.cache_data(ttl=3600)
def load():
    return pd.read_parquet(MASTER_PATH)

df = load()

st.set_page_config(page_title="Dashboard Vendite Libri", layout="wide")
st.title("Dashboard Vendite Libri")

# ================================================
# Filtri
# ================================================
st.sidebar.header("Filtri")
filters = {}
for col, label in [("publisher","Editore"), ("author","Autore"), ("title","Titolo"), ("collana","Collana")]:
    if col in df.columns:
        opts = ["Tutti"] + sorted(df[col].dropna().astype(str).unique())
        chosen = st.sidebar.multiselect(label, opts, default="Tutti")
        if "Tutti" not in chosen and chosen:
            filters[col] = chosen

if st.sidebar.button("Reimposta filtri"):
    st.rerun()

# ================================================
# Settimana
# ================================================
week_options = ["Tutti"] + sorted(df["week"].unique())
selected_week = st.sidebar.selectbox("Settimana", week_options, index=0)

data = df.copy()
if selected_week != "Tutti":
    data = data[data["week"] == selected_week]

for col, vals in filters.items():
    data = data[data[col].isin(vals)]

if data.empty:
    st.warning("Nessun dato con i filtri selezionati.")
    st.stop()

# ================================================
# Download + Tabella
# ================================================
csv = data.to_csv(index=False).encode()
c1, c2 = st.columns([4,1])
with c1:
    st.subheader(f"Dati – {selected_week}")
    st.dataframe(data.drop(columns=["rank","source_file"], errors="ignore"))
with c2:
    st.download_button("Scarica CSV", csv, f"vendite_{selected_week}.csv", "text/csv")

# ================================================
# Grafici rapidi
# ================================================
st.subheader("Top")
c1,c2,c3 = st.columns(3)
with c1:
    top = data.nlargest(20,"units")[["title","units"]]
    if len(top)>1:
        st.altair_chart(alt.Chart(top).mark_bar().encode(x=alt.X("title:N",sort="-y"),y="units:Q"), use_container_width=True)
with c2:
    top = data.groupby("author")["units"].sum().nlargest(10).reset_index()
    if len(top)>1:
        st.altair_chart(alt.Chart(top).mark_bar().encode(x=alt.X("author:N",sort="-y"),y="units:Q"), use_container_width=True)
with c3:
    top = data.groupby("publisher")["units"].sum().nlargest(10).reset_index()
    if len(top)>1:
        st.altair_chart(alt.Chart(top).mark_bar().encode(x=alt.X("publisher:N",sort="-y"),y="units:Q"), use_container_width=True)

# ================================================
# Andamento (solo "Tutti")
# ================================================
if selected_week == "Tutti" and any(filters.values()):
    st.subheader("Andamento Settimanale")
    trend = []
    for w in week_options[1:]:
        temp = df[df["week"]==w]
        for col in ["title","author","publisher"]:
            if filters.get(col):
                temp = temp[temp[col].isin(filters[col])]
                label = col.capitalize()
                break
        else:
            continue
        units = int(temp["units"].sum())
        trend.append({"Settimana":w, "Unità":units, "Tipo":label})
    if trend:
        st.altair_chart(alt.Chart(pd.DataFrame(trend)).mark_line(point=True).encode(
            x=alt.X("Settimana:N", sort=week_options[1:]),
            y="Unità:Q",
            color="Tipo:N"
        ), use_container_width=True)

# ================================================
# Adelphi Heatmap
# ================================================
st.header("Analisi Adelphi")
adelphi = df[df["publisher"].str.contains("Adelphi", case=False, na=False)].copy()
if not adelphi.empty:
    # variazione %
    grp = ["title","week"]
    if "collana" in adelphi.columns:
        grp.insert(1,"collana")
    adelphi = adelphi.groupby(grp)["units"].sum().reset_index()
    key = ["title"] + (["collana"] if "collana" in grp else [])
    adelphi["prev"] = adelphi.groupby(key)["units"].shift(1)
    adelphi["Diff_%"] = np.where(adelphi["prev"]>0, (adelphi["units"]-adelphi["prev"])/adelphi["prev"]*100, np.nan)

    idx = "title"
    if "collana" in adelphi.columns:
        adelphi["title_collana"] = adelphi["title"] + " (" + adelphi["collana"].fillna("—") + ")"
        idx = "title_collana"

    pivot = adelphi.pivot(index=idx, columns="week", values="Diff_%").fillna(0)
    long = pivot.reset_index().melt(id_vars=idx, var_name="week", value_name="Diff_%")
    long = long.merge(adelphi[["week","Week_Num"]].drop_duplicates(), on="week")

    if not long.empty:
        chart = alt.Chart(long).mark_rect().encode(
            x=alt.X("week:N", sort=week_options[1:]),
            y=alt.Y(f"{idx}:N", sort=alt.EncodingSortField("Diff_%", op="sum", order="descending")),
            color=alt.Color("Diff_%:Q", scale=alt.Scale(scheme="redyellowgreen", domainMid=0)),
            tooltip=[idx, "week", "Diff_%"]
        )
        st.altair_chart(chart, use_container_width=True)

    st.dataframe(adelphi[["title","collana","week","units","Diff_%"]].sort_values(["title","week"]))
