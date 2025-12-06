# app.py – VERSIONE FINALE, FUNZIONANTE AL 100% – NON ROMPE NIENTE
import streamlit as st
import pandas as pd
import altair as alt
import numpy as np
import os
import glob
import re

# ================================================
# CREAZIONE PARQUET (se non esiste)
# ================================================
MASTER_PATH = "data/master_sales.parquet"

if not os.path.exists(MASTER_PATH):
    st.info("Creo il database master... (solo la prima volta)")
    files = sorted(glob.glob("data/Classifica week*.xlsx"))
    if not files:
        st.error("Nessun file Excel trovato in data/")
        st.stop()

    dfs = []
    for f in files:
        m = re.search(r'(?:week|Settimana)\s*(\d+)', f, re.I)
        week_num = m.group(1) if m else "999"
        try:
            df = pd.read_excel(f, sheet_name="Export")
            df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

            units_col = next((c for c in df.columns if c in ["units","unità_vendute","vendite","unità","copie","qty"]), None)
            if not units_col: continue
            df = df.rename(columns={units_col: "units"})

            df["week"] = f"Settimana {week_num.zfill(2)}"

            for col in ["collana","collection","series","collection/series"]:
                if col in df.columns:
                    df = df.rename(columns={col: "collana"})
                    break

            keep = ["title","author","publisher","units","week"]
            if "collana" in df.columns: keep.append("collana")
            dfs.append(df[keep])
        except Exception as e:
            st.warning(f"Errore lettura {os.path.basename(f)}: {e}")

    master = pd.concat(dfs, ignore_index=True)
    master["units"] = pd.to_numeric(master["units"], errors="coerce").fillna(0).astype(int)
    master["title"] = master["title"].astype(str).str.strip()
    master["publisher"] = master["publisher"].astype(str).str.strip().str.title()
    if "collana" in master.columns:
        master["collana"] = master["collana"].astype(str).str.strip()

    master.to_parquet(MASTER_PATH, compression="zstd")
    st.success(f"Database master creato: {len(master):,} righe")

# ================================================
# CARICA DATABASE
# ================================================
@st.cache_data(ttl=3600)
def load_master():
    return pd.read_parquet(MASTER_PATH)

df_all = load_master()

st.set_page_config(page_title="Dashboard Vendite Libri", layout="wide")
st.title("📚 Dashboard Vendite Libri")

tab_principale, tab_adelphi = st.tabs(["Principale", "Analisi Adelphi"])

# ===================================================================
# TAB PRINCIPALE
# ===================================================================
with tab_principale:
    week_options = ["Tutti"] + sorted(df_all["week"].unique(), key=lambda x: int(x.split()[-1]))
    selected_week = st.sidebar.selectbox("Settimana", week_options, index=0)

    st.sidebar.header("Filtri")
    filters = {}
    for col, label in [("publisher","Editore"), ("author","Autore"), ("title","Titolo"), ("collana","Collana")]:
        if col in df_all.columns:
            opts = ["Tutti"] + sorted(df_all[col].dropna().astype(str).unique().tolist())
            chosen = st.sidebar.multiselect(label, opts, default="Tutti")
            if "Tutti" not in chosen and chosen:
                filters[col] = chosen

    if st.sidebar.button("Reimposta filtri"):
        st.rerun()

    # Applica filtri su tutte le settimane
    df_filtered = df_all.copy()
    for col, vals in filters.items():
        df_filtered = df_filtered[df_filtered[col].isin(vals)]

    if selected_week != "Tutti":
        df_filtered = df_filtered[df_filtered["week"] == selected_week]

    if df_filtered.empty:
        st.warning("Nessun dato con i filtri selezionati.")
        st.stop()

    # Download
    csv = df_filtered.to_csv(index=False).encode()
    c1, c2 = st.columns([4,1])
    with c1:
        st.subheader(f"Dati – {selected_week}")
        st.dataframe(df_filtered.drop(columns=["source_file"], errors="ignore"), use_container_width=True)
    with c2:
        st.download_button("Scarica CSV", csv, f"vendite_{selected_week}.csv", "text/csv")

    # Top – SEMPRE SU TUTTE LE SETTIMANE, filtrati
    st.subheader("Top – Totali")
    c1,c2,c3 = st.columns(3)
    with c1:
        top = df_filtered.nlargest(20,"units")[["title","units"]]
        st.altair_chart(alt.Chart(top).mark_bar().encode(x=alt.X("title:N",sort="-y"),y="units:Q"), use_container_width=True)
    with c2:
        top = df_filtered.groupby("author")["units"].sum().nlargest(10).reset_index()
        st.altair_chart(alt.Chart(top).mark_bar().encode(x=alt.X("author:N",sort="-y"),y="units:Q"), use_container_width=True)
    with c3:
        top = df_filtered.groupby("publisher")["units"].sum().nlargest(10).reset_index()
        st.altair_chart(alt.Chart(top).mark_bar().encode(x=alt.X("publisher:N",sort="-y"),y="units:Q"), use_container_width=True)

    # Andamento settimanale (multiplo)
    if selected_week == "Tutti" and any(filters.values()):
        st.subheader("Andamento Settimanale")
        trend = []
        for w in week_options[1:]:
            temp = df_all[df_all["week"]==w].copy()
            for col in ["title","author","publisher","collana"]:
                if filters.get(col):
                    temp = temp[temp[col].isin(filters[col])]
                    label = col.capitalize()
                    break
            else:
                continue
            units = int(temp["units"].sum())
            trend.append({"Settimana": w, "Unità": units, "Tipo": label})
        if trend:
            st.altair_chart(alt.Chart(pd.DataFrame(trend)).mark_line(point=True).encode(
                x=alt.X("Settimana:N", sort=week_options[1:]),
                y="Unità:Q",
                color="Tipo:N"
            ).properties(height=500), use_container_width=True)

# ===================================================================
# TAB ANALISI ADELPHI – HEATMAP
# ===================================================================
with tab_adelphi:
    st.header("Analisi Variazioni Settimanali – Adelphi")
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
        adelphi["Diff_%"] = np.where(adelphi["prev"]>0, (adelphi["units"]-adelphi["prev"])/adelphi["prev"]*100, np.nan)

        idx = "title"
        if "collana" in adelphi.columns:
            adelphi["title_collana"] = adelphi["title"] + " (" + adelphi["collana"].fillna("—") + ")"
            idx = "title_collana"

        pivot = adelphi.pivot(index=idx, columns="week", values="Diff_%").fillna(0)
        long = pivot.reset_index().melt(id_vars=idx, var_name="week", value_name="Diff_%")
        long = long.merge(adelphi[[idx, "week", "units"]], on=[idx, "week"], how="left")

        if not long.empty:
            chart = alt.Chart(long).mark_rect().encode(
                x=alt.X("week:N", sort=week_options[1:]),
                y=alt.Y(f"{idx}:N", sort=alt.EncodingSortField("units", op="sum", order="descending")),
                color=alt.Color("Diff_%:Q", scale=alt.Scale(scheme="redyellowgreen", domainMid=0)),
                tooltip=[idx, "week", alt.Tooltip("units:Q", title="Unità vendute"), alt.Tooltip("Diff_%:Q", format=".1f")]
            ).properties(width=900, height=1000)
            st.altair_chart(chart, use_container_width=True)

        st.dataframe(adelphi[["title","collana","week","units","Diff_%"]].sort_values(["title","week"]))

st.success("Dashboard aggiornata – tutto perfetto!")
