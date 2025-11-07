# app.py – LIGHT, FAST, NO FORECASTING, NO MEMORY ISSUES
import streamlit as st
import pandas as pd
import altair as alt
import re

from data_utils import (
    load_all_dataframes, filter_data, aggregate_group_data,
    aggregate_all_weeks, normalize_title
)
from viz_utils import (
    create_top_books_chart, create_top_authors_chart,
    create_top_publishers_chart, create_heatmap
)

# =============================================
st.set_page_config(page_title="Dashboard Vendite Libri", layout="wide")
st.title("Dashboard Vendite Libri")

st.markdown("""
<style>
    [data-testid="stAppViewContainer"] {background:#f0f4f8;font-family:Arial,sans-serif;}
    .stTab {background:#fff;padding:10px;border-radius:5px;}
</style>
""", unsafe_allow_html=True)

DATA_DIR = "data"
dataframes = load_all_dataframes(DATA_DIR)

if not dataframes:
    st.info("Nessun file XLSX valido in data/.")
    st.stop()

tab1, tab2 = st.tabs(["Principale", "Analisi Adelphi"])

# =============================================
# TAB 1 – PRINCIPALE
# =============================================
with tab1:
    week_options = ["Tutti"] + sorted(
        dataframes.keys(),
        key=lambda x: int(re.search(r'Settimana\s*(\d+)', x, re.I).group(1))
    )
    qp = st.query_params.to_dict()
    init_week = qp.get("selected_week", ["Tutti"])[0]
    if init_week not in week_options:
        init_week = "Tutti"

    selected_week = st.sidebar.selectbox(
        "Seleziona la Settimana",
        week_options,
        index=week_options.index(init_week)
    )
    st.query_params["selected_week"] = selected_week

    is_aggregate = selected_week == "Tutti"
    df = aggregate_all_weeks(dataframes) if is_aggregate else dataframes[selected_week]

    # --- Filtri ---
    st.sidebar.header("Filtri")
    filters = {}
    for col, label in [
        ("publisher", "Editore"),
        ("author", "Autore"),
        ("title", "Titolo"),
        ("collana", "Collana")
    ]:
        if col in df.columns:
            opts = sorted(df[col].dropna().unique())
            init = [v for v in qp.get(col, []) if v in opts]
            filters[col] = st.sidebar.multiselect(label, opts, default=init)
            st.query_params[col] = filters[col]

    if st.sidebar.button("Reimposta Filtri"):
        st.query_params.clear()
        st.rerun()

    filtered_df = filter_data(df, filters)
    if filtered_df.empty:
        st.warning("Nessun dato con i filtri selezionati.")
        st.stop()

    # --- Tabella ---
    display_df = filtered_df.drop(columns=["rank"], errors="ignore")
    c1, c2 = st.columns([3, 1])
    with c1:
        st.header(f"Dati – {selected_week}")
        st.dataframe(display_df, use_container_width=True)
    with c2:
        csv = filtered_df.to_csv(index=False).encode()
        st.download_button("Scarica CSV", csv, "dati_filtrati.csv", "text/csv")

    # --- Statistiche ---
    for col, label in [("author","Autore"), ("publisher","Editore"), ("title","Titolo"), ("collana","Collana")]:
        if filters.get(col):
            st.markdown(f"**{label}:** {', '.join(map(str, filters[col]))}")
            stats = aggregate_group_data(filtered_df, col, filters[col])
            if stats:
                c1, c2 = st.columns(2)
                c1.metric("Unità Vendute", f"{stats['Total Units']:,}")
                c2.metric("Libri", stats["Items"])

    # --- Grafici base ---
    st.header("Top")
    col1, col2, col3 = st.columns(3)
    with col1:
        if ch := create_top_books_chart(filtered_df):
            st.altair_chart(ch, use_container_width=True)
    with col2:
        if ch := create_top_authors_chart(filtered_df):
            st.altair_chart(ch, use_container_width=True)
    with col3:
        if ch := create_top_publishers_chart(filtered_df):
            st.altair_chart(ch, use_container_width=True)

    # --- Andamento settimanale ---
    if is_aggregate and (filters.get("title") or filters.get("author") or filters.get("publisher")):
        st.header("Andamento Settimanale")
        trend_data = []
        for week, wdf in sorted(dataframes.items(),
            key=lambda x: int(re.search(r'Settimana\s*(\d+)', x[0], re.I).group(1))):
            wn = int(re.search(r'Settimana\s*(\d+)', week, re.I).group(1))
            if not wdf is None:
                wf = wdf.copy()
                if filters.get("title"):
                    wf = wf[wf["title"].isin(filters["title"])]
                    item_col = "title"
                    items = filters["title"]
                elif filters.get("publisher"):
                    wf = wf[wf["publisher"].isin(filters["publisher"])]
                    item_col = "publisher"
                    items = filters["publisher"]
                else:  # author
                    wf = wf[wf["author"].isin(filters["author"])]
                    item_col = "title"
                    items = wf["title"].unique()

                if wf.empty: continue

                for it in items:
                    sub = wf[wf[item_col] == it] if item_col != "title" or not filters.get("author") else wf[wf["author"].isin(filters["author"])]
                    if not sub.empty:
                        trend_data.append({
                            "Settimana": week,
                            "Unità": sub["units"].sum(),
                            "Item": it,
                            "Week_Num": wn
                        })

        if trend_data:
            df_trend = pd.DataFrame(trend_data).sort_values("Week_Num")
            st.subheader("Andamento")
            chart = alt.Chart(df_trend).mark_line(point=True).encode(
                x=alt.X("Settimana:N", sort=alt.EncodingSortField(field="Week_Num", order="ascending")),
                y="Unità:Q",
                color="Item:N",
                tooltip=["Settimana", "Unità", "Item"]
            ).properties(width="container").interactive()
            st.altair_chart(chart, use_container_width=True)
            st.dataframe(df_trend)

# =============================================
# TAB 2 – ANALISI ADELPHI (heatmap only)
# =============================================
with tab2:
    st.header("Analisi Variazioni Settimanali – Adelphi")

    adelphi_weeks = []
    for week, wdf in sorted(dataframes.items(),
        key=lambda x: int(re.search(r'Settimana\s*(\d+)', x[0], re.I).group(1))):
        wn = int(re.search(r'Settimana\s*(\d+)', week, re.I).group(1))
        if wdf is None: continue
        adf = wdf[wdf["publisher"].str.contains("Adelphi", case=False, na=False)]
        if adf.empty: continue
        cols = ["title", "author", "units"]
        if "collana" in wdf.columns:
            cols.append("collana")
        adf = adf[cols].copy()
        adf["Settimana"] = week
        adf["Week_Num"] = wn
        adelphi_weeks.append(adf)

    if not adelphi_weeks:
        st.info("Nessun dato Adelphi trovato.")
        st.stop()

    df_adelphi = pd.concat(adelphi_weeks, ignore_index=True)
    df_adelphi["title"] = df_adelphi["title"].apply(normalize_title)

    # apply current filters
    for col in ["title", "author", "collana"]:
        if filters.get(col):
            df_adelphi = df_adelphi[df_adelphi[col].isin(filters[col])]

    # group
    group_cols = ["title", "Settimana", "Week_Num"]
    if "collana" in df_adelphi.columns:
        group_cols.append("collana")
    df_adelphi = df_adelphi.groupby(group_cols)["units"].sum().reset_index()

    # % change
    key = ["title"] + (["collana"] if "collana" in df_adelphi.columns else [])
    df_adelphi["prev"] = df_adelphi.groupby(key)["units"].shift(1)
    df_adelphi["Diff_pct"] = df_adelphi.apply(
        lambda r: (r["units"] - r["prev"]) / r["prev"] * 100 if pd.notna(r["prev"]) and r["prev"] > 0 else None,
        axis=1
    )

    # pivot for heatmap
    idx = "title"
    if "collana" in df_adelphi.columns:
        df_adelphi["title_collana"] = df_adelphi["title"] + " (" + df_adelphi["collana"].fillna("—") + ")"
        idx = "title_collana"

    pivot = df_adelphi.pivot(index=idx, columns="Settimana", values="Diff_pct").fillna(0)
    long = pivot.reset_index().melt(id_vars=idx, var_name="Settimana", value_name="Diff_pct")
    long = long.merge(df_adelphi[["Settimana", "Week_Num"]].drop_duplicates(), on="Settimana")

    if not long.empty:
        st.subheader("Heatmap Variazioni % (verde = crescita)")
        chart = create_heatmap(long, pivot_index=idx)
        st.altair_chart(chart, use_container_width=True)
    else:
        st.warning("Nessun dato per la heatmap.")

    # table
    show_cols = ["title", "Settimana", "units", "Diff_pct"]
    if "collana" in df_adelphi.columns:
        show_cols.insert(1, "collana")
    st.dataframe(df_adelphi[show_cols].sort_values(["title", "Week_Num"]))
