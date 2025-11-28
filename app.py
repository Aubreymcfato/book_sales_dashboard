import streamlit as st
import pandas as pd
import altair as alt
import numpy as np
import re
import io
from data_utils import load_all_dataframes, filter_data, aggregate_group_data, aggregate_all_weeks, normalize_title
from viz_utils import create_top_books_chart, create_top_authors_chart, create_top_publishers_chart, create_heatmap

st.set_page_config(page_title="Dashboard Vendite Libri", layout="wide")
st.title("Dashboard Vendite Libri")

st.markdown("""
<style>
    .big-font {font-size:18px !important; font-weight:bold;}
    .stDownloadButton>button {width:100%;}
</style>
""", unsafe_allow_html=True)

DATA_DIR = "data"
dataframes = load_all_dataframes(DATA_DIR)

if not dataframes:
    st.error("Nessun file trovato nella cartella 'data/'")
    st.stop()

tab1, tab2 = st.tabs(["Principale", "Analisi Adelphi"])

# ===================================================================
# TAB 1 – PRINCIPALE
# ===================================================================
with tab1:
    week_options = ["Tutti"] + sorted(
        dataframes.keys(),
        key=lambda x: int(re.search(r'Settimana\s*(\d+)', x, re.I).group(1))
    )

    qp = st.query_params.to_dict()
    init_week = qp.get("week", ["Tutti"])[0]
    if init_week not in week_options:
        init_week = "Tutti"

    selected_week = st.sidebar.selectbox("Settimana", week_options, index=week_options.index(init_week))
    st.query_params["week"] = selected_week

    is_all_weeks = selected_week == "Tutti"
    df = aggregate_all_weeks(dataframes) if is_all_weeks else dataframes[selected_week]

    # Filtri
    st.sidebar.header("Filtri")
    filters = {}
    for col, label in [("publisher","Editore"), ("author","Autore"), ("title","Titolo"), ("collana","Collana")]:
        if col in df.columns:
            opts = sorted(df[col].dropna().astype(str).unique())
            current = qp.get(col, [])
            valid = [v for v in current if v in opts]
            chosen = st.sidebar.multiselect(label, opts, default=valid)
            filters[col] = chosen
            if chosen:
                st.query_params[col] = chosen
            else:
                st.query_params.pop(col, None)

    if st.sidebar.button("Reimposta tutti i filtri"):
        st.query_params.clear()
        st.rerun()

    filtered_df = filter_data(df, filters)

    if filtered_df.empty:
        st.warning("Nessun dato con i filtri selezionati.")
        st.stop()

    filtered_df = filtered_df.copy()
    filtered_df["units"] = pd.to_numeric(filtered_df["units"], errors="coerce").fillna(0).astype(int)

    def get_csv_bytes(df):
        df_clean = df.copy()
        df_clean = df_clean.fillna("")
        df_clean = df_clean.astype(str)
        df_clean = df_clean.replace({"nan": "", "-": "0", "None": ""})
        buffer = io.BytesIO()
        df_clean.to_csv(buffer, index=False, encoding="utf-8")
        return buffer.getvalue()

    csv_bytes = get_csv_bytes(filtered_df)

    col1, col2 = st.columns([3,1])
    with col1:
        st.subheader(f"Dati {selected_week}")
        st.dataframe(filtered_df.drop(columns=["rank"], errors="ignore"), use_container_width=True)
    with col2:
        st.subheader("Download")
        st.download_button(
            label="Scarica CSV",
            data=csv_bytes,
            file_name=f"vendite_libri_{selected_week.replace(' ', '_')}.csv",
            mime="text/csv",
            use_container_width=True
        )

    if any(filters.values()):
        total_units = filtered_df["units"].sum()
        st.metric("Unità totali visibili", f"{total_units:,}")

    st.subheader("Top")
    c1, c2, c3 = st.columns(3)
    with c1:
        ch = create_top_books_chart(filtered_df)
        if ch: st.altair_chart(ch, use_container_width=True)
    with c2:
        ch = create_top_authors_chart(filtered_df)
        if ch: st.altair_chart(ch, use_container_width=True)
    with c3:
        ch = create_top_publishers_chart(filtered_df)
        if ch: st.altair_chart(ch, use_container_width=True)

    if is_all_weeks and any(f for f in [filters.get("title"), filters.get("author"), filters.get("publisher")]):
        st.subheader("Andamento settimanale")
        trend = []
        for week_name, wdf in sorted(dataframes.items(),
            key=lambda x: int(re.search(r'\d+', x[0]).group())):
            if wdf is None: continue
            temp = wdf.copy()
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
            trend.append({"Settimana": week_name, "Unità": units, "Filtro": label})

        if trend:
            trend_df = pd.DataFrame(trend)
            chart = alt.Chart(trend_df).mark_line(point=True).encode(
                x=alt.X("Settimana:N", sort=list(dataframes.keys())),
                y="Unità:Q",
                color="Filtro:N",
                tooltip=["Settimana", "Unità", "Filtro"]
            ).properties(height=400)
            st.altair_chart(chart, use_container_width=True)

# ===================================================================
# TAB 2 – ANALISI ADELPHI
# ===================================================================
with tab2:
    st.header("Variazioni % Settimanali – Adelphi")

    adelphi_weeks = []
    for week_name, wdf in sorted(dataframes.items(),
        key=lambda x: int(re.search(r'\d+', x[0]).group())):
        if wdf is None: continue
        adf = wdf[wdf["publisher"].str.contains("Adelphi", case=False, na=False)].copy()
        if adf.empty: continue
        adf["units"] = pd.to_numeric(adf["units"], errors="coerce").fillna(0)
        adf["Settimana"] = week_name
        adf["Week_Num"] = int(re.search(r'\d+', week_name).group())
        adelphi_weeks.append(adf[["title", "collana", "units", "Settimana", "Week_Num"]])

    if not adelphi_weeks:
        st.info("Nessun dato Adelphi trovato.")
        st.stop()

    adelphi = pd.concat(adelphi_weeks, ignore_index=True)
    adelphi["title"] = adelphi["title"].apply(normalize_title)

    # Applica i filtri globali anche qui
    for col in ["title", "collana"]:
        if filters.get(col):
            adelphi = adelphi[adelphi[col].isin(filters[col])]

    group_cols = ["title", "Settimana", "Week_Num"]
    if "collana" in adelphi.columns:
        group_cols.insert(1, "collana")
    adelphi = adelphi.groupby(group_cols)["units"].sum().reset_index()

    key_cols = ["title"] + (["collana"] if "collana" in group_cols else [])
    adelphi["prev"] = adelphi.groupby(key_cols)["units"].shift(1)
    adelphi["Diff_%"] = adelphi.apply(
        lambda r: (r["units"] - r["prev"]) / r["prev"] * 100 if pd.notna(r["prev"]) and r["prev"] > 0 else None,
        axis=1
    )

    idx = "title"
    if "collana" in adelphi.columns:
        adelphi["title_collana"] = adelphi["title"] + " (" + adelphi["collana"].fillna("—") + ")"
        idx = "title_collana"

    long = adelphi.pivot(index=idx, columns="Settimana", values="Diff_%").stack(dropna=False).reset_index()
    long = long.rename(columns={0: "Diff_%"})
    long = long.merge(adelphi[["Settimana", "Week_Num"]].drop_duplicates(), on="Settimana")

    if not long.empty and long["Diff_%"].notna().any():
        chart = create_heatmap(long, pivot_index=idx)
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("Nessuna variazione calcolabile con i dati attuali.")

    display_cols = ["title", "Settimana", "units", "Diff_%"]
    if "collana" in adelphi.columns:
        display_cols.insert(1, "collana")
    st.dataframe(
        adelphi[display_cols].sort_values(["title", "Week_Num"]),
        use_container_width=True
    )

st.success("Dashboard caricata correttamente!")
