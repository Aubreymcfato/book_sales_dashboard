# data_utils.py – PROVEN WORKING
import streamlit as st
import pandas as pd
import os, glob, re
from concurrent.futures import ThreadPoolExecutor

def normalize_title(t):
    if isinstance(t, str):
        s = t.strip()
        if s.lower() in ["l' avversario", "l'avversario"]:
            return "L'avversario"
        return s
    return t

def normalize_publisher(p):
    if isinstance(p, str):
        return p.strip().title()
    return p

@st.cache_data
def load_data(path):
    try:
        df = pd.read_excel(path, sheet_name="Export", engine="openpyxl")
        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]

        rank_col = next((c for c in df.columns if c in ["rank", "rango", "classifica"]), None)
        if not rank_col:
            st.error(f"{os.path.basename(path)} manca colonna rank.")
            return None
        df = df.rename(columns={rank_col: "rank"})
        df = df[pd.notna(df["rank"]) & df["rank"].apply(lambda x: isinstance(x, (int, float)))]

        for c in ["rank", "units"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")

        if "title" in df.columns:
            df["title"] = df["title"].apply(normalize_title)
        if "publisher" in df.columns:
            df["publisher"] = df["publisher"].apply(normalize_publisher)

        collana_col = next((c for c in df.columns if c in ["collection", "series", "collana"]), None)
        if collana_col:
            df = df.rename(columns={collana_col: "collana"})
        return df
    except Exception as e:
        st.error(f"Errore {os.path.basename(path)}: {e}")
        return None

def filter_data(df, filters, is_aggregate=False):
    if df is None:
        return None
    f = df.copy()
    for col, vals in filters.items():
        if vals:
            f = f[f[col].isin(vals)] if isinstance(vals, list) else f[f[col] == vals]
    return f

def aggregate_group_data(df, by, values):
    if not values or df is None:
        return None
    sub = df[df[by].isin(values)] if isinstance(values, list) else df[df[by] == values]
    if sub.empty:
        return None
    return {
        "Total Units": sub["units"].sum(),
        "Items": len(sub["title"].unique()) if by != "title" else (len(values) if isinstance(values, list) else 1)
    }

def aggregate_all_weeks(dfs_dict):
    dfs = [d for d in dfs_dict.values() if d is not None]
    if not dfs:
        return None
    for d in dfs:
        if "title" in d.columns:
            d["title"] = d["title"].apply(normalize_title)
        if "publisher" in d.columns:
            d["publisher"] = d["publisher"].apply(normalize_publisher)
    combined = pd.concat(dfs, ignore_index=True)
    all_cols = set(combined.columns)
    group_cols = [c for c in all_cols if c != "units"]
    return combined.groupby(group_cols, as_index=False, dropna=False)["units"].sum()

def load_all_dataframes(folder):
    out = {}
    if not os.path.isdir(folder):
        st.error(f"Cartella {folder} non trovata.")
        return out
    files = glob.glob(os.path.join(folder, "Classifica week*.xlsx"))
    valid = []
    for f in files:
        m = re.search(r'week\s*(\d+)', os.path.basename(f), re.I)
        if m:
            valid.append((f, int(m.group(1))))
        else:
            st.warning(f"Nome non valido: {os.path.basename(f)}")
    valid.sort(key=lambda x: x[1])
    paths, nums = zip(*valid) if valid else ([], [])
    with ThreadPoolExecutor() as exe:
        loaded = list(exe.map(load_data, paths))
    for n, df in zip(nums, loaded):
        if df is not None:
            out[f"Settimana {n}"] = df
    return out
