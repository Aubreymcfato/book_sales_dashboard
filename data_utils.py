import streamlit as st
import pandas as pd
import numpy as np

def normalize_title(title):
    if isinstance(title, str):
        stripped = title.strip()
        lower_stripped = stripped.lower()
        if lower_stripped in ["l' avversario", "l'avversario"]:
            return "L'avversario"
        return stripped
    return title

@st.cache_data
def load_data(file_path):
    try:
        df = pd.read_excel(file_path, sheet_name="Export", header=0, engine="openpyxl")
        df.columns = [str(col).strip().lower().replace(" ", "_") for col in df.columns]
        rank_variants = ["rank", "rango", "classifica"]
        rank_col = next((col for col in df.columns if col in rank_variants), None)
        if not rank_col:
            st.error(f"File {os.path.basename(file_path)} manca colonna 'Rank' o varianti. Colonne trovate: {list(df.columns)}")
            return None
        df = df.rename(columns={rank_col: "rank"})
        df = df[df["rank"].apply(lambda x: pd.notna(x) and isinstance(x, (int, float)))]
        if df.empty:
            st.error(f"File {os.path.basename(file_path)} non contiene righe valide per 'Rank'.")
            return None
        numeric_cols = ["rank", "units"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        if 'title' in df.columns:
            df['title'] = df['title'].apply(normalize_title)
        return df
    except Exception as e:
        st.error(f"Errore nel caricamento di {os.path.basename(file_path)}: {e}")
        return None

def filter_data(df, filters, is_aggregate=False):
    if df is None:
        return None
    filtered_df = df.copy()
    for col, value in filters.items():
        if value and value != "Tutti":
            if isinstance(value, list):
                filtered_df = filtered_df[filtered_df[col].isin(value)]
            else:
                if col == "rank" and is_aggregate:
                    continue
                if col == "rank":
                    filtered_df = filtered_df[filtered_df[col] == float(value)]
                else:
                    filtered_df = filtered_df[filtered_df[col] == value]
    return filtered_df

def aggregate_group_data(df, group_by, values):
    if df is None or not values:
        return None
    group_df = df[df[group_by].isin(values)] if isinstance(values, list) else df[df[group_by] == values]
    if group_df.empty:
        return None
    return {
        "Total Units": group_df["units"].sum(),
        "Items": len(group_df["title"].unique()) if group_by != "title" else len(values) if isinstance(values, list) else 1
    }

def aggregate_all_weeks(dataframes):
    all_dfs = [df for df in dataframes.values() if df is not None]
    if not all_dfs:
        return None
    combined_df = pd.concat(all_dfs, ignore_index=True)
    if 'title' in combined_df.columns:
        combined_df['title'] = combined_df['title'].apply(normalize_title)
    agg_df = combined_df.groupby(["publisher", "author", "title"], as_index=False)["units"].sum()
    return agg_df
