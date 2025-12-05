# app.py – VERSIONE DEFINITIVA, ZERO ERRORI DI SINTASSI
import streamlit as st
import pandas as pd
import altair as alt
import os
import glob
import re

# ================================================
# CREA IL PARQUET SE NON ESISTE (prima di tutto!)
# ================================================
MASTER_PATH = "data/master_sales.parquet"

if not os.path.exists(MASTER_PATH):
    st.info("Creo il database master... (solo la prima volta)")
    files = sorted(glob.glob("data/Classifica week*.xlsx"))
    if not files:
        st.error("Nessun file Excel trovato nella cartella data/")
        st.stop()

    dfs = []
    for f in files:
        m = re.search(r'(?:week|Settimana)\s*(\d+)', f, re.I)
        week_num = m.group(1) if m else "999"
        try:
            df = pd.read_excel(f, sheet_name="Export")
            df["week"] = f"Settimana {week_num}"
            dfs.append(df)
        except Exception as e:
            st.warning(f"Errore lettura {os.path.basename(f)}: {e}")

    master = pd.concat(dfs, ignore_index=True)

    # Pulizia dati
    master["units"] = pd.to_numeric(master["units"], errors="coerce").fillna(0).astype(int)
    if "title" in master.columns:
        master["title"] = master["title"].astype(str).str.strip()
    if "publisher" in master.columns:
        master["publisher"] = master["publisher"].astype(str).str.strip().str.title()

    # Rinomina collana
    for col in ["collana", "collection", "series", "Collection/Series"]:
        if col in master.columns:
            master = master.rename(columns={col: "collana"})
            break

    master.to_parquet(MASTER_PATH, compression="zstd")
    st.success(f"Database creato: {len(master):,} righe")

# ================================================
# CARICA IL DATABASE
# ================================================
@st.cache_data(ttl=3600, show_spinner="Caricamento dati...")
def load_master():
    return pd.read_parquet(MASTER_PATH)

df_all = load_master()

# ================================================
# CONFIGURAZIONE
# ================================================
st.set_page_config(page_title="Dashboard Vendite Libri", layout="wide")
st.title("Dashboard Vendite Libri")

# ================================================
# Filtri
# ================================================
st.sidebar.header("Filtri")

week_options = ["Tutti"] + sorted(df_all["week"].unique())
selected_week = st.sidebar.selectbox("Settimana", week_options, index=0)

filters = {}
for col, label in [("publisher","Editore"), ("author","Autore"), ("title","Titolo"), ("collana","Collana")]:
    if col in df_all.columns:
        opts = ["Tutti"] + sorted(df_all[col].dropna().astype(str).unique().tolist())
        chosen = st.sidebar.multiselect(label, opts, default="Tutti")
        if "Tutti" not in chosen and chosen:
            filters[col] = chosen

if st.sidebar.button("Reimposta filtri"):
    st.rerun()

# ================================================
# Applica filtri
# ================================================
df = df_all.copy()
if selected_week != "Tutti":
    df = df[df["week"] == selected_week]

for col, vals in filters.items():
    df = df[df[col].isin(vals)]

if df.empty:
    st.warning("Nessun dato con i filtri selezionati.")
    st.stop()

# ================================================
# Download + Tabella
# ================================================
csv = df.to_csv(index=False).encode()
c1, c2 = st.columns([4,1])
with c1:
    st.subheader(f"Dati – {selected_week}")
    st.dataframe(df.drop(columns=["rank","source_file"], errors="ignore"), use_container_width=True)
with c2:
    st.download_button("Scarica CSV", csv, f"vendite_{selected_week}.csv", "text/csv")

# ================================================
# Top
# ================================================
st.subheader("Top")
c1,c2,c3 = st.columns(3)
with c1:
    top = df.nlargest(20,"units")[["title","units"]]
    if len(top)>1:
        st.altair_chart(alt.Chart(top).mark_bar().encode(x=alt.X("title:N",sort="-y"),y="units:Q"), use_container_width=True)
with c2:
    top = df.groupby("author")["units"].sum().nlargest(10).reset_index()
    if len(top)>1:
        st.altair_chart(alt.Chart(top).mark_bar().encode(x=alt.X("author:N",sort="-y"),y="units:Q"), use_container_width=True)
with c3:
    top = df.groupby("publisher")["units"].sum().nlargest(10).reset_index()
    if len(top)>1:
        st.altair_chart(alt.Chart(top).mark_bar().encode(x=alt.X("publisher:N",sort="-y"),y="units:Q"), use_container_width=True)

# ================================================
# Andamento (solo "Tutti")
# ================================================
if selected_week == "Tutti" and any(filters.get("title") or filters.get("author") or filters.get("publisher")):
    st.subheader("Andamento Settimanale")
    trend = []
    for w in week_options[1:]:
        temp = df_all[df_all["week"]==w]
        if filters.get("title"):
            temp = temp[temp["title"].isin(filters["title"])]
            label = "Titolo"
        elif filters.get("author"):
            temp = temp[temp["author"].isin(filters["author"])]
            label = "Autore"
        elif filters.get("publisher"):
            temp = temp[temp["publisher"].isin(filters["publisher"])]
            label = "Editore"
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
adelphi = df_all[df_all["publisher"].str.contains("Adelphi", case=False, na=False)].copy()
if not adelphi.empty:
    adelphi["units"] = pd.to_numeric(adelphi["units"], errors="coerce").fillna(0)
    for col in ["title","collana"]:
        if filters.get(col):
            adelphi = adelphi[adelphi[col].isin(filters[col])]

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
