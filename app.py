# app.py
import streamlit as st
import pandas as pd
import altair as alt
import numpy as np
import re
from data_utils import (
    load_all_dataframes, filter_data, aggregate_group_data,
    aggregate_all_weeks, normalize_title
)
from viz_utils import (
    create_top_books_chart, create_top_authors_chart,
    create_top_publishers_chart, create_heatmap
)
from statsmodels.tsa.arima.model import ARIMA

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
    st.stop()

tab1, tab3 = st.tabs(["Principale", "Analisi Adelphi"])

# ----------------------------------------------------------------------
#  TAB 1  –  Principale
# ----------------------------------------------------------------------
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
        "Seleziona la Settimana", week_options, index=week_options.index(init_week)
    )
    st.query_params["selected_week"] = selected_week

    is_aggregate = selected_week == "Tutti"
    df = aggregate_all_weeks(dataframes) if is_aggregate else dataframes[selected_week]

    # ---- Filtri (NO rank) ------------------------------------------------
    st.sidebar.header("Filtri")
    filters = {}
    cols = ["publisher", "author", "title", "collana"]
    labels = {"publisher": "Editore", "author": "Autore", "title": "Titolo", "collana": "Collana"}

    for col in cols:
        if col in df.columns:
            uniq = sorted(df[col].dropna().unique())
            init = qp.get(col, [])
            valid_init = [v for v in init if v in uniq]
            filters[col] = st.sidebar.multiselect(labels[col], uniq, default=valid_init)
            st.query_params[col] = filters[col]

    if st.sidebar.button("Reimposta Filtri"):
        st.query_params.clear()
        st.rerun()

    filtered_df = filter_data(df, filters, is_aggregate=is_aggregate)

    if filtered_df is None or filtered_df.empty:
        st.warning("Nessun dato con i filtri selezionati.")
    else:
        # hide rank if it exists
        display_df = filtered_df.drop(columns=["rank"], errors="ignore")

        c1, c2 = st.columns(2)
        with c1:
            st.header(f"Dati – {selected_week}")
            st.dataframe(display_df, use_container_width=True)
        with c2:
            csv = filtered_df.to_csv(index=False).encode()
            st.download_button("Scarica CSV", csv, "dati_filtrati.csv", "text/csv")

        # ---- Statistiche per gruppo ------------------------------------
        for grp in ["author", "publisher", "title", "collana"]:
            vals = filters.get(grp, [])
            if vals:
                st.header(f"Statistiche per {labels[grp]}: {', '.join(map(str, vals))}")
                stats = aggregate_group_data(filtered_df, grp, vals)
                if stats:
                    c1, c2 = st.columns(2)
                    c1.metric("Unità Vendute", stats["Total Units"])
                    c2.metric(
                        f"Numero di {'Libri' if grp in ['author','publisher','collana'] else 'Elementi'}",
                        stats["Items"]
                    )

        # ---- Grafici ----------------------------------------------------
        st.header("Analisi Grafica")
        try:
            if (ch := create_top_books_chart(filtered_df)):
                st.subheader("Top 20 Libri")
                st.altair_chart(ch, use_container_width=True)
            if (ch := create_top_authors_chart(filtered_df)):
                st.subheader("Top 10 Autori")
                st.altair_chart(ch, use_container_width=True)
            if (ch := create_top_publishers_chart(filtered_df)):
                st.subheader("Top 10 Editori")
                st.altair_chart(ch, use_container_width=True)
        except Exception as e:
            st.error(f"Errore nei grafici: {e}")

        # ---- Andamento settimanale (solo “Tutti”) --------------------
        if is_aggregate:
            sel_title = filters.get("title", [])
            sel_author = filters.get("author", [])
            sel_pub = filters.get("publisher", [])
            if sel_title or sel_author or sel_pub:
                st.header("Andamento Settimanale")
                sum_data, book_data = [], []
                for week, wdf in sorted(
                    dataframes.items(),
                    key=lambda x: int(re.search(r'Settimana\s*(\d+)', x[0], re.I).group(1))
                ):
                    wn = int(re.search(r'Settimana\s*(\d+)', week, re.I).group(1))
                    if wdf is None:
                        continue
                    wf = wdf.copy()

                    if sel_title:
                        wf = wf[wf["title"].isin(sel_title)]
                        grp = "title"
                        items = sel_title
                    elif sel_pub:
                        wf = wf[wf["publisher"].isin(sel_pub)]
                        grp = "publisher"
                        items = sel_pub
                    else:  # author
                        wf = wf[wf["author"].isin(sel_author)]
                        grp = "title"
                        items = wf["title"].unique()
                        sum_items = sel_author

                    if wf.empty:
                        continue

                    # somma
                    for it in (sum_items if sel_author else items):
                        sub = wf[wf["author"] == it] if sel_author else wf[wf[grp] == it]
                        if not sub.empty:
                            sum_data.append(
                                {"Settimana": week, "Unità Vendute": sub["units"].sum(),
                                 "Item": it, "Week_Num": wn}
                            )
                    # libri singoli (solo per autore)
                    if sel_author:
                        for it in items:
                            sub = wf[wf[grp] == it]
                            if not sub.empty:
                                book_data.append(
                                    {"Settimana": week, "Unità Vendute": sub["units"].sum(),
                                     "Item": it, "Week_Num": wn}
                                )

                # grafico somma
                if sum_data:
                    df_sum = pd.DataFrame(sum_data).sort_values("Week_Num")
                    sub = ("Titolo" if sel_title else
                           "Autore (Somma)" if sel_author else
                           "Editore (Somma)")
                    st.subheader(f"Andamento per {sub}")
                    ch = alt.Chart(df_sum).mark_line(point=True).encode(
                        x=alt.X("Settimana:N", sort=alt.EncodingSortField("Week_Num", "ascending")),
                        y="Unità Vendute:Q",
                        color=alt.Color("Item:N", legend=alt.Legend(title="Item")),
                        tooltip=["Settimana", "Unità Vendute", "Item"]
                    ).properties(width="container").interactive()
                    st.altair_chart(ch, use_container_width=True)
                    st.dataframe(df_sum)

                # grafico libri autore
                if sel_author and book_data:
                    df_book = pd.DataFrame(book_data).sort_values("Week_Num")
                    st.subheader("Andamento per Libri dell'Autore")
                    ch = alt.Chart(df_book).mark_line(point=True).encode(
                        x=alt.X("Settimana:N", sort=alt.EncodingSortField("Week_Num", "ascending")),
                        y="Unità Vendute:Q",
                        color=alt.Color("Item:N", legend=alt.Legend(title="Libro")),
                        tooltip=["Settimana", "Unità Vendute", "Item"]
                    ).properties(width="container").interactive()
                    st.altair_chart(ch, use_container_width=True)
                    st.dataframe(df_book)

                # top-20 libri editore (solo 1 editore)
                if len(sel_pub) == 1:
                    top20 = (
                        aggregate_all_weeks(dataframes)
                        .query("publisher in @sel_pub")
                        .nlargest(20, "units")["title"]
                        .tolist()
                    )
                    pub_data = []
                    for week, wdf in sorted(
                        dataframes.items(),
                        key=lambda x: int(re.search(r'Settimana\s*(\d+)', x[0], re.I).group(1))
                    ):
                        wn = int(re.search(r'Settimana\s*(\d+)', week, re.I).group(1))
                        if wdf is None:
                            continue
                        wf = wdf[wdf["publisher"].isin(sel_pub)]
                        for t in top20:
                            sub = wf[wf["title"] == t]
                            if not sub.empty:
                                pub_data.append(
                                    {"Settimana": week, "Unità Vendute": sub["units"].sum(),
                                     "Libro": t, "Week_Num": wn}
                                )
                    if pub_data:
                        df_pub = pd.DataFrame(pub_data).sort_values("Week_Num")
                        st.subheader("Andamento Settimanale dei Primi 20 Libri dell'Editore")
                        ch = alt.Chart(df_pub).mark_line(point=True).encode(
                            x=alt.X("Settimana:N", sort=alt.EncodingSortField("Week_Num", "ascending")),
                            y="Unità Vendute:Q",
                            color=alt.Color("Libro:N", legend=alt.Legend(title="Libro")),
                            tooltip=["Settimana", "Unità Vendute", "Libro"]
                        ).properties(width="container").interactive()
                        st.altair_chart(ch, use_container_width=True)
                        st.dataframe(df_pub)

# ----------------------------------------------------------------------
#  TAB 3  –  Analisi Adelphi  (unchanged, only tiny safety tweaks)
# ----------------------------------------------------------------------
with tab3:
    st.header("Analisi Variazioni Settimanali per Adelphi")
    adelphi_data = []
    for week, wdf in sorted(
        dataframes.items(),
        key=lambda x: int(re.search(r'Settimana\s*(\d+)', x[0], re.I).group(1))
    ):
        wn = int(re.search(r'Settimana\s*(\d+)', week, re.I).group(1))
        if wdf is None:
            continue
        adf = wdf[wdf["publisher"].str.contains("Adelphi", case=False, na=False)]
        if adf.empty:
            continue
        cols = ["title", "author", "units"]
        has_collana = "collana" in wdf.columns
        if has_collana:
            cols.append("collana")
        adf = adf[cols].copy()
        adf["Settimana"] = week
        adf["Week_Num"] = wn
        adelphi_data.append(adf)

    if not adelphi_data:
        st.info("Nessun dato Adelphi trovato.")
        st.stop()

    adelphi_df = pd.concat(adelphi_data, ignore_index=True)
    adelphi_df = adelphi_df.dropna(subset=["title"])
    adelphi_df["title"] = adelphi_df["title"].apply(normalize_title)

    grp_cols = ["title", "author", "Settimana", "Week_Num"]
    dup_chk = ["title", "Settimana"]
    if has_collana and "collana" in adelphi_df.columns:
        grp_cols.append("collana")
        dup_chk.append("collana")

    adelphi_df = adelphi_df.groupby(grp_cols)["units"].sum().reset_index()

    # apply current sidebar filters (if any)
    for fcol in ["title", "author", "collana"]:
        if filters.get(fcol):
            adelphi_df = adelphi_df[adelphi_df[fcol].isin(filters[fcol])]

    adelphi_df.sort_values(["title", "Week_Num"], inplace=True)

    # % variation
    grp_for_shift = ["title"] + (["collana"] if has_collana else [])
    adelphi_df["Previous_Units"] = adelphi_df.groupby(grp_for_shift)["units"].shift(1)
    adelphi_df["Diff_pct"] = np.where(
        adelphi_df["Previous_Units"] > 0,
        (adelphi_df["units"] - adelphi_df["Previous_Units"]) / adelphi_df["Previous_Units"] * 100,
        np.nan,
    )

    # duplicate check
    if adelphi_df.duplicated(subset=dup_chk, keep=False).any():
        dup_titles = adelphi_df[adelphi_df.duplicated(subset=dup_chk, keep=False)]["title"].unique()
        st.error(f"Duplicati trovati: {', '.join(map(str, dup_titles))}")
        st.stop()

    # ----- Heatmap -------------------------------------------------
    pivot_idx = "title"
    if has_collana and "collana" in adelphi_df.columns:
        adelphi_df["title_collana"] = (
            adelphi_df["title"] + " (" + adelphi_df["collana"].fillna("Sconosciuta") + ")"
        )
        pivot_idx = "title_collana"

    p_diff = adelphi_df.pivot(index=pivot_idx, columns="Settimana", values="Diff_pct").fillna(0)
    p_units = adelphi_df.pivot(index=pivot_idx, columns="Settimana", values="units").fillna(0)

    long_diff = p_diff.reset_index().melt(id_vars=pivot_idx, var_name="Settimana", value_name="Diff_pct")
    long_units = p_units.reset_index().melt(id_vars=pivot_idx, var_name="Settimana", value_name="units")
    pivot_df = pd.merge(long_diff, long_units, on=[pivot_idx, "Settimana"])
    pivot_df = pivot_df.merge(
        adelphi_df[["Settimana", "Week_Num"]].drop_duplicates(), on="Settimana"
    )
    pivot_df = pivot_df[pivot_df["Diff_pct"].notna()]

    if not pivot_df.empty:
        st.subheader("Heatmap Variazioni Percentuali (%) – Verde: crescita, Rosso: calo")
        heatmap = create_heatmap(pivot_df, pivot_index=pivot_idx)
        st.altair_chart(heatmap, use_container_width=True)
    else:
        st.warning("Nessun dato per la heatmap dopo i filtri.")

    # ----- Tabella dati -------------------------------------------
    disp_cols = ["title", "Settimana", "units", "Diff_pct"]
    if has_collana and "collana" in adelphi_df.columns:
        disp_cols.insert(1, "collana")
    st.dataframe(adelphi_df[disp_cols])

    # ----- Previsione ---------------------------------------------
    st.header("Previsione Vendite per Collana (Adelphi)")
    if has_collana and "collana" in adelphi_df.columns:
        groups = adelphi_df.groupby("collana")
    else:
        groups = [("Tutti", adelphi_df)]
        st.warning("Colonna 'collana' mancante → previsione aggregata.")

    for name, gdf in groups:
        st.subheader(f"Collana: {name}")
        sales = gdf.groupby("Week_Num")["units"].sum().reset_index().set_index("Week_Num")
        if len(sales) < 3:
            st.warning("Dati insufficienti (≥3 settimane).")
            continue
        try:
            model = ARIMA(sales["units"], order=(1, 1, 1)).fit()
            fc = model.forecast(steps=4).round().astype(int)
            fc_df = pd.DataFrame(
                {
                    "Settimana": [f"Settimana {gdf['Week_Num'].max() + i + 1}" for i in range(4)],
                    "Previsione Unità Vendute": fc,
                }
            )
            st.dataframe(fc_df)
            ch = alt.Chart(fc_df).mark_line(point=True, color="red").encode(
                x="Settimana:N", y="Previsione Unità Vendute:Q",
                tooltip=["Settimana", "Previsione Unità Vendute"]
            ).properties(width="container").interactive()
            st.altair_chart(ch, use_container_width=True)
        except Exception as e:
            st.warning(f"Previsione fallita: {e}")
