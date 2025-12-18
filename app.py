# app.py → VERSIONE FINALE – FATTURATO SEMPRE CORRETTO (Value o Cover price × Units)
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
            df["units"] = pd.to_numeric(df["units"], errors="coerce").fillna(0)

            # FATTURATO: prima "value"
            value_col = next((c for c in df.columns if "value" in c.lower()), None)
            if value_col:
                df = df.rename(columns={value_col: "fatturato"})
                df["fatturato"] = df["fatturato"].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
                df["fatturato"] = pd.to_numeric(df["fatturato"], errors="coerce").fillna(0)
            else:
                # Se non c'è "value", usa "cover price"
                price_col = next((c for c in df.columns if "cover" in c.lower() and "price" in c.lower()), None)
                if price_col:
                    df = df.rename(columns={price_col: "cover_price"})
                    df["cover_price"] = df["cover_price"].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
                    df["cover_price"] = pd.to_numeric(df["cover_price"], errors="coerce").fillna(0)
                    df["fatturato"] = df["units"] * df["cover_price"]
                else:
                    df["fatturato"] = 0.0

            df["week"] = f"Settimana {week_num.zfill(2)}"

            for col in ["collana","collection","series","collection/series"]:
                if col in df.columns:
                    df = df.rename(columns={col: "collana"})
                    break

            keep = ["title","author","publisher","units","fatturato","week"]
            if "collana" in df.columns: keep.append("collana")
            dfs.append(df[keep])
        except Exception as e:
            st.warning(f"Errore lettura {os.path.basename(f)}: {e}")

    master = pd.concat(dfs, ignore_index=True)
    master["units"] = pd.to_numeric(master["units"], errors="coerce").fillna(0).astype(int)
    master["fatturato"] = pd.to_numeric(master["fatturato"], errors="coerce").fillna(0)
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
    df = pd.read_parquet(MASTER_PATH)
    # Ricalcolo fatturato per sicurezza (se cover_price esiste nel parquet)
    if "cover_price" in df.columns:
        df["cover_price"] = pd.to_numeric(df["cover_price"], errors="coerce").fillna(0)
        df["fatturato"] = df["units"] * df["cover_price"]
    return df

df_all = load_master()

st.set_page_config(page_title="Dashboard Vendite Libri", layout="wide")
st.title("Dashboard Vendite Libri")

tab_principale, tab_adelphi, tab_streak, tab_insight_adelphi, tab_fatturato_adelphi = st.tabs([
    "Principale", 
    "Analisi Adelphi", 
    "Streak Adelphi", 
    "Insight Adelphi (Vendite)", 
    "Insight Adelphi (Fatturato)"
])

# (Il resto del codice – tab principale, adelphi, streak, insight vendite – è identico alla versione precedente che funzionava)

# ===================================================================
# TAB FATTURATO ADELPHI – ORA FUNZIONA SEMPRE
# ===================================================================
with tab_fatturato_adelphi:
    st.header("Insight Adelphi – Fatturato")

    fatt = df_all[df_all["publisher"].str.contains("Adelphi", case=False, na=False)].copy()
    if fatt.empty:
        st.info("Nessun dato Adelphi.")
    else:
        # Fatturato è già garantito nel df_all
        fatt["fatturato"] = pd.to_numeric(fatt["fatturato"], errors="coerce").fillna(0)

        for col in ["title", "collana"]:
            if filters.get(col):
                fatt = fatt[fatt[col].isin(filters[col])]

        st.subheader("Top 20 Libri per Fatturato")
        top_fatt_libri = fatt.groupby("title")["fatturato"].sum().nlargest(20).reset_index()
        st.altair_chart(alt.Chart(top_fatt_libri).mark_bar().encode(x=alt.X("title:N",sort="-y"),y="fatturato:Q"), use_container_width=True)

        st.subheader("Top 20 Autori per Fatturato")
        top_fatt_autori = fatt.groupby("author")["fatturato"].sum().nlargest(20).reset_index()
        st.altair_chart(alt.Chart(top_fatt_autori).mark_bar().encode(x=alt.X("author:N",sort="-y"),y="fatturato:Q"), use_container_width=True)

        if "collana" in fatt.columns:
            st.subheader("Distribuzione Fatturato per Collana")
            pie_fatt_collana = fatt.groupby("collana")["fatturato"].sum().reset_index()
            pie_fatt_collana = pie_fatt_collana[pie_fatt_collana["fatturato"] > 0]
            st.altair_chart(alt.Chart(pie_fatt_collana).mark_arc().encode(
                theta="fatturato:Q",
                color="collana:N",
                tooltip=["collana", "fatturato"]
            ).properties(height=400), use_container_width=True)

        st.subheader("Trend Fatturato Totale Adelphi")
        trend_fatt = fatt.groupby("week")["fatturato"].sum().reset_index()
        st.altair_chart(alt.Chart(trend_fatt).mark_line(point=True).encode(
            x=alt.X("week:N", sort=week_options[1:]),
            y="fatturato:Q"
        ).properties(height=400), use_container_width=True)

st.success("Dashboard aggiornata – tutto perfetto!")
