# data_utils.py – MINIMAL & CACHED
import streamlit as st
import pandas as pd
import os, glob, re
from concurrent.futures import ThreadPoolExecutor

def normalize_title(t):
    if isinstance(t, str):
        s = t.strip()
        if s.lower() in ["l'avversario", "l' avversario"]:
            return "L'avversario"
        return s
    return t

def normalize_publisher(p):
    return p.strip().title() if isinstance(p, str) else p

@st.cache_data
def load_data(path):
    try:
        df = pd.read_excel(path, sheet_name="Export", engine="openpyxl")
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

        rank_col = next((c for c in df.columns if c in ["rank","rango","classifica"]), None)
        if not rank_col: return None
        df = df.rename(columns={rank_col: "rank"})
        df = df[pd.notna(df["rank"])]

        for c in ["rank", "units"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")

        if "title" in df.columns:
            df["title"] = df["title"].apply(normalize_title)
        if "publisher" in df.columns:
            df["publisher"] = df["publisher"].apply(normalize_publisher)
        if any(c in df.columns for c in ["collana","collection","series"]):
            col = next(c for c in ["collana","collection","series"] if c in df.columns)
            df = df.rename(columns={col: "collana"})

        return df
    except:
        return None

def filter_data(df, filters):
    if df is None: return df
    f = df.copy()
    for col, vals in filters.items():
        if vals:
            f = f[f[col].isin(vals)]
    return f

def aggregate_group_data(df, by, values):
    sub = df[df[by].isin(values)] if isinstance(values,list) else df[df[by]==values]
    return {
        "Total Units": int(sub["units"].sum()),
        "Items": len(sub) if by == "title" else len(sub["title"].unique())
    }

@st.cache_data
def aggregate_all_weeks(dfs_dict):
    dfs = [d for d in dfs_dict.values() if d is not None]
    if not dfs: return None
    for d in dfs:
        if "title" in d.columns:
            d["title"] = d["title"].apply(normalize_title)
        if "publisher" in d.columns:
            d["publisher"] = d["publisher"].apply(normalize_publisher)
    combined = pd.concat(dfs, ignore_index=True)
    group_cols = [c for c in combined.columns if c != "units"]
    return combined.groupby(group_cols, dropna=False)["units"].sum().reset_index()

def load_all_dataframes(folder):
    out = {}
    files = glob.glob(os.path.join(folder, "Classifica week*.xlsx"))
    valid = []
    for f in files:
        m = re.search(r'week\s*(\d+)', os.path.basename(f), re.I)
        if m:
            valid.append((f, int(m.group(1))))
    valid.sort(key=lambda x: x[1])
    paths, nums = zip(*valid) if valid else ([], [])
    with ThreadPoolExecutor() as exe:
        loaded = list(exe.map(load_data, paths))
    for n, df in zip(nums, loaded):
        if df is not None:
            out[f"Settimana {n}"] = df
    return out
