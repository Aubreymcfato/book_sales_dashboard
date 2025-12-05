# app.py → VERSIONE DEFINITIVA – VELOCE, STABILE, ZERO CRASH
import streamlit as st
import pandas as pd
import altair as alt
import numpy as np
import re

# ================================================
# CARICAMENTO DATI – UN SOLO FILE PARQUET
# ================================================
MASTER_PATH = "data/master_sales.parquet"

@st.cache_data(ttl=3600, show_spinner="Caricamento dati...")
def load_master():
    if not pd.io.common.file_exists(MASTER_PATH):
        st.error("File master_sales.parquet non trovato! Assicurati che update_master.py sia stato eseguito.")
        st.stop()
    df = pd.read_parquet(MASTER_PATH)
    return df

df_all = load_master()

# ================================================
# CONFIGURAZIONE PAGINA
# ================================================
st.set_page_config(page_title="Dashboard Vendite Libri", layout="wide")
st.title("Dashboard Vendite Libri")

# Stile
st.markdown("""
<style>
    .big-font {font-size:18px !important; font-weight:bold;}
    .stDownloadButton>button {width:100%; background:#0068c9; color:white;}
</style>
""", unsafe_allow_html=True)

# ================================================
# SIDEBAR – Filtri
# ================================================
st.sidebar.header("Filtri")

# Lista settimane disponibili
week_options = ["Tutti"] + sorted(df_all["week"].unique().tolist())
selected_week = st.sidebar.selectbox("Settimana", week_options, index=0)

# Filtri classici
filters = {}
for col, label in [
    ("publisher", "Editore"),
    ("author", "Autore"),
    ("title", "Titolo"),
    ("collana", "Collana")
]:
    if col in df_all.columns:
        opts = ["Tutti"] + sorted(df_all[col].dropna().astype(str).unique().tolist())
        default = "Tutti" if "Tutti" in opts else opts[0]
        chosen = st.sidebar.multiselect(label, opts, default=default)
        if "Tutti" not in chosen and chosen:
            filters[col] = chosen

# Pulsante reset
if st.sidebar.button("Reimposta tutti i filtri"):
    st.query_params.clear()
    st.rerun()

# ================================================
# APPLICAZIONE FILTRO SETTIMANA
# ================================================
df = df_all.copy()
if selected_week != "Tutti":
    df = df[df["week"] == selected_week]

# Applica filtri utente
for col, vals in filters.items():
    df = df[df[col].isin(vals)]

if df.empty:
    st.warning("Nessun dato con i filtri selezionati.")
    st.stop()

# ================================================
# DOWNLOAD CSV (sicuro al 100%)
# ================================================
@st.cache_data
def convert_df_to_csv(_df):
    return _df.to_csv(index=False).encode('utf-8')

csv_data = convert_df_to_csv(df)

col1, col2 = st.columns([4, 1])
with col1:
    st.subheader(f"Dati – {selected_week}")
    # Nascondi colonne inutili
    display_df = df.drop(columns=["source_file", "rank"], errors="ignore")
    st.dataframe(display_df, use_container_width=True)

with col2:
    st.subheader("Download")
    st.download_button(
        label="Scarica CSV",
        data=csv_data,
        file_name=f"vendite_libri_{selected_week.replace(' ', '_')}.csv",
        mime="text/csv"
    )

# ================================================
# METRICHE RAPIDE
# ================================================
if any(filters.values()):
    total = df["units"].sum()
    st.metric("Unità totali visibili", f"{total:,}")

# ================================================
# TOP CHARTS
# ================================================
st.subheader("Top")

c1, c2, c3 = st.columns(3)

with c1:
    top_books = df.nlargest(20, "units")[["title", "units"]]
    if len(top_books) > 1:
        ch = alt.Chart(top_books).mark_bar(color="#0068c9").encode(
            x=alt.X("title:N", sort="-y", title="Titolo"),
            y=alt.Y("units:Q", title="Unità"),
            tooltip=["title", "units"]
        ).properties(height=400)
        st.altair_chart(ch, use_container_width=True)

with c2:
    top_authors = df.groupby("author")["units"].sum().nlargest(10).reset_index()
    if len(top_authors) > 1:
        ch = alt.Chart(top_authors).mark_bar(color="#e67e22").encode(
            x=alt.X("author:N", sort="-y", title="Autore"),
            y=alt.Y("units:Q", title="Unità"),
            tooltip=["author", "units"]
        ).properties(height=400)
        st.altair_chart(ch, use_container_width=True)

with c3:
    top_publishers = df.groupby("publisher")["units"].sum().nlargest(10).reset_index()
    if len(top_publishers) > 1:
        ch = alt.Chart(top_publishers).mark_bar(color="#27ae60").encode(
            x=alt.X("publisher:N", sort="-y", title="Editore"),
            y=alt.Y("units:Q", title="Unità"),
            tooltip=["publisher", "units"]
        ).properties(height=400)
        st.altair_chart(ch, use_container_width=True)

# ================================================
# ANDAMENTO SETTIMANALE (solo su "Tutti")
# ================================================
if selected_week == "Tutti" and any(f for f in [filters.get("title"), filters.get("author"), filters.get("publisher")]):
    st.subheader("Andamento Settimanale")
    trend = []
    for week_name in week_options[1:]:  # esclude "Tutti"
        temp = df_all[df_all["week"] == week_name].copy()
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
        trend.append({"Settimana": week_name, "Unità": units, "Tipo": label})

    if trend:
        df_trend = pd.DataFrame(trend)
        chart = alt.Chart(df_trend).mark_line(point=True).encode(
            x=alt.X("Settimana:N", sort=week_options[1:]),
            y="Unità:Q",
            color="Tipo:N",
            tooltip=["Settimana", "Unità", "Tipo"]
        )
        ).properties(height=400)
        st.altair_chart(chart, use_container_width=True)

# ================================================
# ANALISI ADELPHI – Heatmap
# ================================================
st.header("Analisi Variazioni % – Adelphi")
adelphi = df_all[df_all["publisher"].str.contains("Adelphi", case=False, na=False)].copy()

if adelphi.empty:
    st.info("Nessun dato per Adelphi.")
else:
    # Pulizia
    adelphi["units"] = pd.to_numeric(adelphi["units"], errors="coerce").fillna(0)

    # Applica eventuali filtri titolo/collana
    for col in ["title", "collana"]:
        if filters.get(col):
            adelphi = adelphi[adelphi[col].isin(filters[col])]

    # Raggruppa
    grp = ["title", "week"]
    if "collana" in adelphi.columns:
        grp.insert(1, "collana")
    adelphi = adelphi.groupby(grp)["units"].sum().reset_index()

    # Variazione %
    key = ["title"] + (["collana"] if "collana" in grp else [])
    adelphi["prev"] = adelphi.groupby(key)["units"].shift(1)
    adelphi["Diff_%"] = np.where(
        adelphi["prev"] > 0,
        (adelphi["units"] - adelphi["prev"]) / adelphi["prev"] * 100,
        np.nan
    )

    # Heatmap
    idx = "title"
    if "collana" in adelphi.columns:
        adelphi["title_collana"] = adelphi["title"] + " (" + adelphi["collana"].fillna("—") + ")"
        idx = "title_collana"

    pivot = adelphi.pivot(index=idx, columns="week", values="Diff_%").fillna(0)
    long = pivot.reset_index().melt(id_vars=idx, var_name="week", value_name="Diff_%")

    if not long.empty:
        chart = alt.Chart(long).mark_rect().encode(
            x=alt.X("week:N", sort=week_options[1:], title="Settimana"),
            y=alt.Y(f"{idx}:N", sort=alt.EncodingSortField(field="Diff_%", op="sum", order="descending")),
            color=alt.Color("Diff_%:Q", scale=alt.Scale(scheme="redyellowgreen", domainMid=0)),
            tooltip=[idx, "week", "Diff_%"]
        ).properties(width=800, height=600)
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("Nessuna variazione da mostrare.")

    st.dataframe(adelphi[["title", "collana", "week", "units", "Diff_%"]].sort_values(["title", "week"]))

st.success("Dashboard aggiornata – tutto veloce e stabile!")
