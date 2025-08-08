import streamlit as st
import pandas as pd
import plotly.express as px
import os
import glob
import re

st.set_page_config(page_title="Dashboard Vendite Libri", layout="wide")
st.title("📚 Dashboard Vendite Libri")

DATA_DIR = "data"

@st.cache_data
def load_data(file_path):
    try:
        df = pd.read_excel(file_path, sheet_name="Export", skiprows=16, engine="openpyxl")
        df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
        # Cerca colonna 'Rank' (case-insensitive)
        rank_col = next((col for col in df.columns if col.lower() in ["rank", "rango", "classifica"]), None)
        if not rank_col:
            st.error(f"File {os.path.basename(file_path)} manca colonna 'Rank' o varianti. Colonne trovate: {list(df.columns)}")
            return None
        df = df.rename(columns={rank_col: "rank"})
        # Filtra righe con 'Rank' numerico
        df = df[df["rank"].apply(lambda x: pd.notna(x) and isinstance(x, (int, float)))]
        if df.empty:
            st.error(f"File {os.path.basename(file_path)} non contiene righe valide per 'Rank'.")
            return None
        numeric_cols = ["rank", "units"]  # Commentate: "cover_price", "pages", "units_since_release", "value", "value_since_release"
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df
    except Exception as e:
        st.error(f"Errore nel caricamento di {os.path.basename(file_path)}: {e}")
        return None

def filter_data(df, filters):
    if df is None:
        return None
    filtered_df = df.copy()
    for col, value in filters.items():
        if value and value != "Tutti":
            try:
                if col == "rank":
                    filtered
