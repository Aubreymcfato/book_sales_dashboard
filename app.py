# app.py → VERSIONE PULITA – CONFRONTI ANNO SU ANNO MIGLIORATI
import streamlit as st
import pandas as pd
import altair as alt
import numpy as np
import os
import glob
import re

# ================================================
# CREAZIONE PARQUET (se non esiste) – GESTIONE ANNI MULTIPLI
# ================================================
MASTER_PATH = "data/master_sales.parquet"

if not os.path.exists(MASTER_PATH):
    st.info("Creo il database master... (solo la prima volta)")
    dfs = []
    years = ["2025", "2026"]  # Aggiungi nuovi anni qui (es. "2027")
    for year in years:
        files = sorted(glob.glob(f"data/{year}/Classifica week*.xlsx"))
        if not files:
            st.warning(f"Nessun file trovato in data/{year}/ – salto l'anno")
            continue

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

                # Fatturato: prima "value"
                value_col = next((c for c in df.columns if "value" in c.lower()), None)
                if value_col:
                    df = df.rename(columns={value_col: "fatturato"})
                    df["fatturato"] = df["fatturato"].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
                    df["fatturato"] = pd.to_numeric(df["fatturato"], errors="coerce").fillna(0)
                else:
                    price_col = next((c for c in df.columns if "cover" in c.lower() and "price" in c.lower()), None)
                    if price_col:
                        df = df.rename(columns={price_col: "cover_price"})
                        df["cover_price"] = df["cover_price"].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
                        df["cover_price"] = pd.to_numeric(df["cover_price"], errors="coerce").fillna(0)
                        df["fatturato"] = df["units"] * df["cover_price"]
                    else:
                        df["fatturato"] = 0.0

                df["week"] = f"Settimana {week_num.zfill(2)}"
                df["year"] = int(year)

                for col in ["collana","collection","series","collection/series"]:
                    if col in df.columns:
                        df = df.rename(columns={col: "collana"})
                        break

                keep = ["title","author","publisher","units","fatturato","week","year"]
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
    return pd.read_parquet(MASTER_PATH)

df_all = load_master()

st.set_page_config(page_title="Dashboard Vendite Libri", layout="wide")
st.title("Dashboard Vendite Libri")

tab_principale, tab_adelphi, tab_streak, tab_insight_adelphi, tab_confronti = st.tabs([
    "Principale", 
    "Analisi Adelphi", 
    "Streak Adelphi", 
    "Insight Adelphi (Vendite)", 
    "Confronti Anno su Anno"
])

# ===================================================================
# TAB PRINCIPALE
# ===================================================================
with tab_principale:
    week_options = ["Tutti"] + sorted(df_all["week"].unique(), key=lambda x: int(x.split()[-1]))
    selected_week = st.sidebar.selectbox("Settimana", week_options, index=0)

    # Filtro Anno – default 2026
    available_years = sorted(df_all["year"].unique())
    default_year = [2026] if 2026 in available_years else available_years[-1:]
    selected_years = st.sidebar.multiselect("Anno", ["Tutti"] + available_years, default=default_year)

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

    df = df_all.copy()
    if "Tutti" not in selected_years:
        df = df[df["year"].isin(selected_years)]

    if selected_week != "Tutti":
        df = df[df["week"] == selected_week]
    for col, vals in filters.items():
        df = df[df[col].isin(vals)]

    if df.empty:
        st.warning("Nessun dato con i filtri selezionati.")
        st.stop()

    csv = df.to_csv(index=False).encode()
    c1, c2 = st.columns([4,1])
    with c1:
        st.subheader(f"Dati – {selected_week}")
        st.dataframe(df.drop(columns=["source_file"], errors="ignore"), use_container_width=True)
    with c2:
        st.download_button("Scarica CSV", csv, f"vendite_{selected_week}.csv", "text/csv")

    st.subheader("Top – Totali filtrati")
    c1,c2,c3 = st.columns(3)
    with c1:
        top = df.nlargest(20,"units")[["title","units"]]
        st.altair_chart(alt.Chart(top).mark_bar().encode(x=alt.X("title:N",sort="-y"),y="units:Q"), use_container_width=True)
    with c2:
        top = df.groupby("author")["units"].sum().nlargest(10).reset_index()
        st.altair_chart(alt.Chart(top).mark_bar().encode(x=alt.X("author:N",sort="-y"),y="units:Q"), use_container_width=True)
    with c3:
        top = df.groupby("publisher")["units"].sum().nlargest(10).reset_index()
        st.altair_chart(alt.Chart(top).mark_bar().encode(x=alt.X("publisher:N",sort="-y"),y="units:Q"), use_container_width=True)

    if selected_week == "Tutti" and any(filters.values()):
        st.subheader("Andamento Settimanale")
        trend_cum = []
        filter_type = None
        filter_values = None
        for col in ["author", "publisher", "collana", "title"]:
            if filters.get(col):
                filter_type = col.capitalize()
                filter_values = filters[col]
                break

        if filter_type and filter_values:
            for w in week_options[1:]:
                temp = df_all[df_all["week"]==w]
                for val in filter_values:
                    temp_val = temp[temp[col] == val]
                    units = int(temp_val["units"].sum())
                    trend_cum.append({"Settimana": w, "Unità": units, "Item": val})

            if trend_cum:
                df_cum = pd.DataFrame(trend_cum)
                st.subheader(f"Andamento cumulativo per {filter_type}")
                st.altair_chart(alt.Chart(df_cum).mark_line(point=True).encode(
                    x=alt.X("Settimana:N", sort=week_options[1:]),
                    y="Unità:Q",
                    color="Item:N",
                    tooltip=["Settimana", "Unità", "Item"]
                ).properties(height=500), use_container_width=True)

        if filters.get("author") or filters.get("collana"):
            trend_books = []
            for w in week_options[1:]:
                temp = df_all[df_all["week"]==w]
                for col, vals in filters.items():
                    if col in ["author", "collana"]:
                        temp = temp[temp[col].isin(vals)]
                for title in temp["title"].unique():
                    temp_title = temp[temp["title"] == title]
                    units = int(temp_title["units"].sum())
                    trend_books.append({"Settimana": w, "Unità": units, "Libro": title})

            if trend_books:
                df_books = pd.DataFrame(trend_books)
                st.subheader("Andamento per singolo libro")
                st.altair_chart(alt.Chart(df_books).mark_line(point=True).encode(
                    x=alt.X("Settimana:N", sort=week_options[1:]),
                    y="Unità:Q",
                    color="Libro:N",
                    tooltip=["Settimana", "Unità", "Libro"]
                ).properties(height=600), use_container_width=True)

# ===================================================================
# TAB ANALISI ADELPHI – HEATMAP % (20px)
# ===================================================================
with tab_adelphi:
    st.header("Analisi Variazioni Settimanali – Adelphi")

    adelphi = df_all[df_all["publisher"].str.contains("Adelphi", case=False, na=False)].copy()
    if adelphi.empty:
        st.info("Nessun dato Adelphi trovato.")
    else:
        adelphi["units"] = pd.to_numeric(adelphi["units"], errors="coerce").fillna(0)

        for col in ["title", "collana"]:
            if filters.get(col):
                adelphi = adelphi[adelphi[col].isin(filters[col])]

        grp = ["title", "week"]
        if "collana" in adelphi.columns:
            grp.insert(1, "collana")
        adelphi = adelphi.groupby(grp)["units"].sum().reset_index()

        key = ["title"] + (["collana"] if "collana" in grp else [])
        adelphi["prev"] = adelphi.groupby(key)["units"].shift(1)
        adelphi["Diff_%"] = np.where(
            adelphi["prev"] > 0,
            (adelphi["units"] - adelphi["prev"]) / adelphi["prev"] * 100,
            np.nan
        )

        idx = "title"
        if "collana" in adelphi.columns:
            adelphi["title_collana"] = adelphi["title"] + " (" + adelphi["collana"].fillna("—") + ")"
            idx = "title_collana"

        pivot = adelphi.pivot(index=idx, columns="week", values="Diff_%").fillna(0)
        long = pivot.reset_index().melt(id_vars=idx, var_name="week", value_name="Diff_%")
        long = long.merge(adelphi[[idx, "week", "units"]], on=[idx, "week"], how="left")

        if not long.empty:
            num_books = long[idx].nunique()
            dynamic_height = max(600, num_books * 20)  # 20px per libro

            chart = alt.Chart(long).mark_rect(
                stroke='gray',
                strokeWidth=0.5
            ).encode(
                x=alt.X("week:N", sort=week_options[1:], title="Settimana"),
                y=alt.Y(f"{idx}:N", sort=alt.EncodingSortField(field="units", op="sum", order="descending")),
                color=alt.Color("Diff_%:Q", scale=alt.Scale(scheme="redyellowgreen", domainMid=0), title="Variazione %"),
                tooltip=[idx, "week", alt.Tooltip("units:Q", title="Unità vendute"), alt.Tooltip("Diff_%:Q", format=".1f", title="Variazione %")]
            ).properties(
                width=900,
                height=dynamic_height
            ).configure_axis(labelFontSize=11, titleFontSize=13)

            st.altair_chart(chart, use_container_width=True)

        st.dataframe(adelphi[["title","collana","week","units","Diff_%"]].sort_values(["title","week"]))

# ===================================================================
# TAB STREAK ADELPHI – CLASSIFICA SOPRA + HEATMAP VERDE/ROSSO/BIANCO (20px)
# ===================================================================
with tab_streak:
    st.header("Streak Adelphi – Crescita/Declino Continuo")

    streak_data = df_all[df_all["publisher"].str.contains("Adelphi", case=False, na=False)].copy()
    if streak_data.empty:
        st.info("Nessun dato Adelphi trovato.")
    else:
        streak_data["units"] = pd.to_numeric(streak_data["units"], errors="coerce").fillna(0)

        for col in ["title", "collana"]:
            if filters.get(col):
                streak_data = streak_data[streak_data[col].isin(filters[col])]

        grp = ["title", "week"]
        if "collana" in streak_data.columns:
            grp.insert(1, "collana")
        streak_data = streak_data.groupby(grp)["units"].sum().reset_index()

        key = ["title"] + (["collana"] if "collana" in grp else [])
        streak_data = streak_data.sort_values(key + ["week"])
        streak_data["diff"] = streak_data.groupby(key)["units"].diff()

        streak_data["color"] = np.where(streak_data["diff"] > 0, "green",
                              np.where(streak_data["diff"] < 0, "red", "white"))

        idx = "title"
        if "collana" in streak_data.columns:
            streak_data["title_collana"] = streak_data["title"] + " (" + streak_data["collana"].fillna("—") + ")"
            idx = "title_collana"

        st.subheader("Top 20 Streak Positive (settimane consecutive di crescita)")
        streak_calc = streak_data.copy()
        streak_calc["is_up"] = (streak_calc["diff"] > 0).astype(int)
        streak_calc["streak_group"] = (streak_calc["is_up"] != streak_calc["is_up"].shift()).cumsum()
        streaks = streak_calc[streak_calc["is_up"] == 1].groupby([idx, "streak_group"]).agg(
            streak_length=("week", "count"),
            last_units=("units", "last"),
            last_week=("week", "last")
        ).reset_index()
        streaks = streaks.sort_values("streak_length", ascending=False).head(20)

        if not streaks.empty:
            st.dataframe(streaks[[idx, "streak_length", "last_units", "last_week"]])
        else:
            st.info("Nessuna streak positiva trovata.")

        pivot_color = streak_data.pivot(index=idx, columns="week", values="color").fillna("white")
        long_color = pivot_color.reset_index().melt(id_vars=idx, var_name="week", value_name="color")
        long_color = long_color.merge(streak_data[[idx, "week", "units"]], on=[idx, "week"], how="left")

        if not long_color.empty:
            num_books = long_color[idx].nunique()
            dynamic_height = max(600, num_books * 20)  # 20px per libro

            chart_streak = alt.Chart(long_color).mark_rect(
                stroke='gray',
                strokeWidth=0.5
            ).encode(
                x=alt.X("week:N", sort=week_options[1:], title="Settimana"),
                y=alt.Y(f"{idx}:N", sort=alt.EncodingSortField(field="units", op="sum", order="descending")),
                color=alt.Color("color:N", scale=alt.Scale(domain=["green","white","red"], range=["green","white","red"]), legend=None),
                tooltip=[idx, "week", alt.Tooltip("units:Q", title="Unità vendute")]
            ).properties(
                width=900,
                height=dynamic_height
            )

            st.altair_chart(chart_streak, use_container_width=True)

# ===================================================================
# TAB INSIGHT ADELPHI (VENDITE)
# ===================================================================
with tab_insight_adelphi:
    st.header("Insight Adelphi – Vendite")

    insight = df_all[df_all["publisher"].str.contains("Adelphi", case=False, na=False)].copy()
    if insight.empty:
        st.info("Nessun dato Adelphi.")
    else:
        insight["units"] = pd.to_numeric(insight["units"], errors="coerce").fillna(0)

        for col in ["title", "collana"]:
            if filters.get(col):
                insight = insight[insight[col].isin(filters[col])]

        st.subheader("Top 20 Libri più venduti")
        top_libri = insight.groupby("title")["units"].sum().nlargest(20).reset_index()
        st.altair_chart(alt.Chart(top_libri).mark_bar().encode(x=alt.X("title:N",sort="-y"),y="units:Q"), use_container_width=True)

        st.subheader("Top 20 Autori più venduti")
        top_autori = insight.groupby("author")["units"].sum().nlargest(20).reset_index()
        st.altair_chart(alt.Chart(top_autori).mark_bar().encode(x=alt.X("author:N",sort="-y"),y="units:Q"), use_container_width=True)

        if "collana" in insight.columns:
            st.subheader("Distribuzione Vendite per Collana")
            pie_collana = insight.groupby("collana")["units"].sum().reset_index()
            pie_collana = pie_collana[pie_collana["units"] > 0]
            st.altair_chart(alt.Chart(pie_collana).mark_arc().encode(
                theta="units:Q",
                color="collana:N",
                tooltip=["collana", "units"]
            ).properties(height=400), use_container_width=True)

        st.subheader("Trend Vendite Totali Adelphi")
        trend_total = insight.groupby("week")["units"].sum().reset_index()
        st.altair_chart(alt.Chart(trend_total).mark_line(point=True).encode(
            x=alt.X("week:N", sort=week_options[1:]),
            y="units:Q"
        ).properties(height=400), use_container_width=True)

# ===================================================================
# TAB CONFRONTI ANNO SU ANNO – MIGLIORATA
# ===================================================================
with tab_confronti:
    st.header("Confronti Anno su Anno – Settimana per Settimana")

    confronto = df_all[df_all["publisher"].str.contains("Adelphi", case=False, na=False)].copy()
    if confronto.empty:
        st.info("Nessun dato Adelphi.")
    else:
        for col in ["title", "collana"]:
            if filters.get(col):
                confronto = confronto[confronto[col].isin(filters[col])]

        # Grafico totale vendite anno su anno
        st.subheader("Trend Vendite Totali – Confronto Anni")
        trend_total = confronto.groupby(["year", "week"])["units"].sum().reset_index()
        st.altair_chart(alt.Chart(trend_total).mark_line(point=True).encode(
            x=alt.X("week:N", sort=week_options[1:]),
            y="units:Q",
            color="year:N"
        ).properties(height=500), use_container_width=True)

        # Tabella per titoli con confronto, differenza, %, colori
        st.subheader("Confronto per Titolo")
        if confronto["title"].nunique() > 0:
            pivot = confronto.pivot_table(index="title", columns="year", values="units", aggfunc="sum").fillna(0)
            years_list = sorted(pivot.columns)
            if len(years_list) >= 2:
                pivot["Diff"] = pivot[years_list[-1]] - pivot[years_list[-2]]
                pivot["Diff_%"] = np.where(pivot[years_list[-2]] > 0, (pivot["Diff"] / pivot[years_list[-2]]) * 100, np.nan)

                def style_df(val, col):
                    if col in ["Diff", "Diff_%"]:
                        if val > 0:
                            return 'background-color: green'
                        elif val < 0:
                            return 'background-color: red'
                    return ''

                styled_pivot = pivot.style.applymap(style_df, subset=["Diff", "Diff_%"])
                st.dataframe(styled_pivot)

            # Grafico per titolo (top 10 per vendite)
            st.subheader("Trend Vendite per Titolo – Confronto Anni")
            top_titles = confronto.groupby("title")["units"].sum().nlargest(10).index
            top_confronto = confronto[confronto["title"].isin(top_titles)]
            chart_title = alt.Chart(top_confronto).mark_line(point=True).encode(
                x=alt.X("week:N", sort=week_options[1:]),
                y="units:Q",
                color="year:N",
                detail="title:N",
                tooltip=["title", "week", "year", "units"]
            ).properties(height=500)
            st.altair_chart(chart_title, use_container_width=True)

        else:
            st.info("Nessun titolo da confrontare.")

st.success("Dashboard aggiornata – tutto perfetto!")
