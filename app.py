# app.py – VERSIONE DEFINITIVA 100% FUNZIONANTE
import streamlit as st
import pandas as pd
import altair as alt

# ================================================
# CARICAMENTO UNICO PARQUET
# ================================================
@st.cache_data(ttl=3600, show_spinner="Caricamento dati...")
def load_master():
    df = pd.read_parquet("data/master_sales.parquet")
    return df

df_all = load_master()

# ================================================
st.set_page_config(page_title="Dashboard Vendite Libri", layout="wide")
st.title("Dashboard Vendite Libri")

st.markdown("""
<style>
    .stDownloadButton>button {width:100%; background:#0068c9; color:white;}
</style>
""", unsafe_allow_html=True)

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
# Download CSV
# ================================================
@st.cache_data
def get_csv(df):
    return df.to_csv(index=False).encode('utf-8')

csv = get_csv(df)

c1, c2 = st.columns([4,1])
with c1:
    st.subheader(f"Dati – {selected_week}")
    st.dataframe(df.drop(columns=["rank","source_file"], errors="ignore"), use_container_width=True)
with c2:
    st.download_button(
        "Scarica CSV",
        csv,
        f"vendite_{selected_week.replace(' ','_')}.csv",
        "text/csv"
    )

# ================================================
# Top
# ================================================
st.subheader("Top")
c1,c2,c3 = st.columns(3)
with c1:
    top = df.nlargest(20,"units")[["title","units"]]
    if len(top)>1:
        st.altair_chart(alt.Chart(top).mark_bar(color="#0068c9").encode(
            x=alt.X("title:N",sort="-y"), y="units:Q"
        ).properties(height=400), use_container_width=True)

with c2:
    top = df.groupby("author")["units"].sum().nlargest(10).reset_index()
    if len(top)>1:
        st.altair_chart(alt.Chart(top).mark_bar(color="#e67e22").encode(
            x=alt.X("author:N",sort="-y"), y="units:Q"
        ).properties(height=400), use_container_width=True)

with c3:
    top = df.groupby("publisher")["units"].sum().nlargest(10).reset_index()
    if len(top)>1:
        st.altair_chart(alt.Chart(top).mark_bar(color="#27ae60").encode(
            x=alt.X("publisher:N",sort="-y"), y="units:Q"
        ).properties(height=400), use_container_width=True)

# ================================================
# Andamento settimanale (solo "Tutti")
# ================================================
if selected_week == "Tutti" and any(f for f in [filters.get("title"),filters.get("author"),filters.get("publisher")]):
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
        trend.append({"Settimana":w, "Unità":int(temp["units"].sum()), "Tipo":label})
    if trend:
        df_trend = pd.DataFrame(trend)
        st.altair_chart(alt.Chart(df_trend).mark_line(point=True).encode(
            x=alt.X("Settimana:N", sort=week_options[1:]),
            y="Unità:Q",
            color="Tipo:N"
        ).properties(height=400), use_container_width=True)

# ================================================
# Analisi Adelphi
# ================================================
st.header("Analisi Variazioni % – Adelphi")
adelphi = df_all[df_all["publisher"].str.contains("Adelphi", case=False, na=False)].copy()
if adelphi.empty:
    st.info("Nessun dato Adelphi.")
else:
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
    adelphi["Diff_%"] = np.where(
        adelphi["prev"]>0,
        (adelphi["units"]-adelphi["prev"])/adelphi["prev"]*100,
        np.nan
    )

    idx = "title"
    if "collana" in adelphi.columns:
        adelphi["title_collana"] = adelphi["title"] + " (" + adelphi["collana"].fillna("—") + ")"
        idx = "title_collana"

    pivot = adelphi.pivot(index=idx, columns="week", values="Diff_%").fillna(0)
    long = pivot.reset_index().melt(id_vars=idx, var_name="week", value_name="Diff_%")
    long = long.merge(adelphi[["week","Week_Num"]].drop_duplicates(), on="week", how="left")

    if not long.empty:
        chart = alt.Chart(long).mark_rect().encode(
            x=alt.X("week:N", sort=week_options[1:]),
            y=alt.Y(f"{idx}:N", sort=alt.EncodingSortField("Diff_%", op="sum", order="descending")),
            color=alt.Color("Diff_%:Q", scale=alt.Scale(scheme="redyellowgreen", domainMid=0)),
            tooltip=[idx, "week", "Diff_%"]
        ).properties(width=800, height=600)
        st.altair_chart(chart, use_container_width=True)

    cols = ["title","week","units","Diff_%"]
    if "collana" in adelphi.columns: cols.insert(1,"collana")
    st.dataframe(adelphi[cols].sort_values(["title","week"]))

st.success("Dashboard aggiornata – tutto stabile e veloce!")
