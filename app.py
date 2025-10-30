# app.py (FINAL MERGED VERSION – ALL FIXES APPLIED)

import streamlit as st
import pandas as pd
import altair as alt
import io
import numpy as np
import re
from data_utils import load_all_dataframes, filter_data, aggregate_group_data, aggregate_all_weeks, normalize_title
from viz_utils import create_top_books_chart, create_top_authors_chart, create_top_publishers_chart, create_heatmap
from statsmodels.tsa.arima.model import ARIMA

# Configurazione iniziale
st.set_page_config(page_title="Dashboard Vendite Libri", layout="wide")
st.title("Dashboard Vendite Libri")

# Stile personalizzato
st.markdown("""
<style>
    [data-testid="stAppViewContainer"] {
        background-color: #f0f4f8;
        font-family: 'Arial', sans-serif;
    }
    .stTab { 
        background-color: #ffffff; 
        padding: 10px; 
        border-radius: 5px; 
    }
</style>
""", unsafe_allow_html=True)

DATA_DIR = "data"

# Caricamento dati
dataframes = load_all_dataframes(DATA_DIR)

if dataframes:
    tab1, tab3 = st.tabs(["Principale", "Analisi Adelphi"])

    with tab1:
        week_options = ["Tutti"] + sorted(dataframes.keys(), key=lambda x: int(re.search(r'Settimana\s*(\d+)', x, re.IGNORECASE).group(1)))
        query_params = st.query_params.to_dict()
        initial_week = query_params.get('selected_week', ["Tutti"])[0]
        if initial_week not in week_options:
            initial_week = "Tutti"
        selected_week = st.sidebar.selectbox("Seleziona la Settimana", week_options, index=week_options.index(initial_week))
        st.query_params['selected_week'] = selected_week
        
        is_aggregate = selected_week == "Tutti"
        if is_aggregate:
            df = aggregate_all_weeks(dataframes)
        else:
            df = dataframes[selected_week]

        if df is not None:
            st.sidebar.header("Filtri")
            filters = {}
            filter_cols = ["publisher", "author", "title", "collana"]
            filter_labels = {"publisher": "Editore", "author": "Autore", "title": "Titolo", "collana": "Collana"}

            for col in filter_cols:
                if col in df.columns:
                    unique_values = sorted(df[col].dropna().unique())
                    initial_value = query_params.get(col, [])
                    # Only keep valid defaults
                    valid_initial = [v for v in initial_value if v in unique_values]
                    filters[col] = st.sidebar.multiselect(filter_labels[col], unique_values, default=valid_initial)
                    st.query_params[col] = filters[col]

            if st.sidebar.button("Reimposta Filtri"):
                st.query_params.clear()
                st.rerun()

            filtered_df = filter_data(df, filters, is_aggregate=is_aggregate)
            if filtered_df is not None and not filtered_df.empty:
                # Optional: hide rank column in display
                display_df = filtered_df.drop(columns=["rank"], errors="ignore")

                col1, col2 = st.columns(2)
                with col1:
                    st.header(f"Dati - {selected_week}")
                    st.dataframe(display_df, use_container_width=True)
                with col2:
                    csv = filtered_df.to_csv(index=False).encode('utf-8')
                    st.download_button("Scarica CSV", data=csv, file_name="dati_filtrati.csv", mime="text/csv")

                for group_by in ["author", "publisher", "title", "collana"]:
                    selected_values = filters.get(group_by, [])
                    if selected_values:
                        st.header(f"Statistiche per {filter_labels[group_by]}: {', '.join(map(str, selected_values))}")
                        stats = aggregate_group_data(filtered_df, group_by, selected_values)
                        if stats:
                            col1, col2 = st.columns(2)
                            col1.metric("Unità Vendute", stats["Total Units"])
                            col2.metric(f"Numero di { 'Libri' if group_by in ['author', 'publisher', 'collana'] else 'Elementi' }", stats["Items"])

                st.header("Analisi Grafica")
                try:
                    chart1 = create_top_books_chart(filtered_df)
                    if chart1:
                        st.subheader("Top 20 Libri")
                        st.altair_chart(chart1, use_container_width=True)

                    chart2 = create_top_authors_chart(filtered_df)
                    if chart2:
                        st.subheader("Top 10 Autori")
                        st.altair_chart(chart2, use_container_width=True)

                    chart3 = create_top_publishers_chart(filtered_df)
                    if chart3:
                        st.subheader("Top 10 Editori")
                        st.altair_chart(chart3, use_container_width=True)
                except Exception as e:
                    st.error(f"Errore nei grafici: {e}")

                if is_aggregate:
                    selected_title = filters.get('title', [])
                    selected_author = filters.get('author', [])
                    selected_publisher = filters.get('publisher', [])
                    if selected_title or selected_author or selected_publisher:
                        st.header("Andamento Settimanale")
                        trend_data_books = []
                        trend_data_sum = []
                        for week, week_df in sorted(dataframes.items(), key=lambda x: int(re.search(r'Settimana\s*(\d+)', x[0], re.IGNORECASE).group(1))):
                            week_num = int(re.search(r'Settimana\s*(\d+)', week, re.IGNORECASE).group(1))
                            if week_df is not None:
                                week_filtered = week_df.copy()
                                if selected_title:
                                    week_filtered = week_filtered[week_filtered['title'].isin(selected_title)]
                                    group_by = 'title'
                                    selected_items = selected_title
                                    selected_items_sum = selected_title
                                elif selected_publisher:
                                    week_filtered = week_filtered[week_filtered['publisher'].isin(selected_publisher)]
                                    group_by = 'publisher'
                                    selected_items = selected_publisher
                                    selected_items_sum = selected_publisher
                                elif selected_author:
                                    week_filtered = week_filtered[week_filtered['author'].isin(selected_author)]
                                    group_by = 'title'
                                    selected_items_books = week_filtered['title'].unique().tolist()
                                    selected_items_sum = selected_author

                                if not week_filtered.empty:
                                    for item in selected_items_sum:
                                        item_df = week_filtered[week_filtered['author' if selected_author else group_by] == item] if selected_author else week_filtered[week_filtered[group_by] == item]
                                        if not item_df.empty:
                                            trend_data_sum.append({"Settimana": week, "Unità Vendute": item_df["units"].sum(), "Item": item, "Week_Num": week_num})

                                    if selected_author and selected_items_books:
                                        for item in selected_items_books:
                                            item_df = week_filtered[week_filtered[group_by] == item]
                                            if not item_df.empty:
                                                trend_data_books.append({"Settimana": week, "Unità Vendute": item_df["units"].sum(), "Item": item, "Week_Num": week_num})

                        if trend_data_sum:
                            trend_df_sum = pd.DataFrame(trend_data_sum)
                            trend_df_sum.sort_values('Week_Num', inplace=True)
                            subheader_sum = "Andamento per " + ("Titolo" if selected_title else "Autore (Somma)" if selected_author else "Editore (Somma)")
                            st.subheader(subheader_sum)
                            chart_sum = alt.Chart(trend_df_sum).mark_line(point=True).encode(
                                x=alt.X('Settimana:N', sort=alt.EncodingSortField(field='Week_Num', order='ascending'), title='Settimana'),
                                y=alt.Y('Unità Vendute:Q', title='Unità Vendute'),
                                color=alt.Color('Item:N', legend=alt.Legend(title="Item")),
                                tooltip=['Settimana', 'Unità Vendute', 'Item']
                            ).properties(width='container').interactive()
                            st.altair_chart(chart_sum, use_container_width=True)
                            st.dataframe(trend_df_sum)

                        if selected_author and trend_data_books:
                            trend_df_books = pd.DataFrame(trend_data_books)
                            trend_df_books.sort_values('Week_Num', inplace=True)
                            st.subheader("Andamento per Libri dell'Autore")
                            chart_books = alt.Chart(trend_df_books).mark_line(point=True).encode(
                                x=alt.X('Settimana:N', sort=alt.EncodingSortField(field='Week_Num', order='ascending'), title='Settimana'),
                                y=alt.Y('Unità Vendute:Q', title='Unità Vendute'),
                                color=alt.Color('Item:N', legend=alt.Legend(title="Libro")),
                                tooltip=['Settimana', 'Unità Vendute', 'Item']
                            ).properties(width='container').interactive()
                            st.altair_chart(chart_books, use_container_width=True)
                            st.dataframe(trend_df_books)

                        if len(selected_publisher) == 1 and is_aggregate:
                            trend_data_publisher_books = []
                            publisher_books = aggregate_all_weeks(dataframes)
                            publisher_books = publisher_books[publisher_books['publisher'].isin(selected_publisher)]
                            top_20_titles = publisher_books.nlargest(20, 'units')['title'].tolist()
                            for week, week_df in sorted(dataframes.items(), key=lambda x: int(re.search(r'Settimana\s*(\d+)', x[0], re.IGNORECASE).group(1))):
                                week_num = int(re.search(r'Settimana\s*(\d+)', week, re.IGNORECASE).group(1))
                                if week_df is not None:
                                    week_filtered = week_df[week_df['publisher'].isin(selected_publisher)]
                                    if not week_filtered.empty:
                                        for title in top_20_titles:
                                            title_df = week_filtered[week_filtered['title'] == title]
                                            if not title_df.empty:
                                                trend_data_publisher_books.append({"Settimana": week, "Unità Vendute": title_df["units"].sum(), "Libro": title, "Week_Num": week_num})
                            if trend_data_publisher_books:
                                trend_df_publisher_books = pd.DataFrame(trend_data_publisher_books)
                                trend_df_publisher_books.sort_values('Week_Num', inplace=True)
                                st.subheader(f"Andamento Settimanale dei Primi 20 Libri dell'Editore")
                                chart_publisher_books = alt.Chart(trend_df_publisher_books).mark_line(point=True).encode(
                                    x=alt.X('Settimana:N', sort=alt.EncodingSortField(field='Week_Num', order='ascending'), title='Settimana'),
                                    y=alt.Y('Unità Vendute:Q', title='Unità Vendute'),
                                    color=alt.Color('Libro:N', legend=alt.Legend(title="Libro")),
                                    tooltip=['Settimana', 'Unità Vendute', 'Libro']
                                ).properties(width='container').interactive()
                                st.altair_chart(chart_publisher_books, use_container_width=True)
                                st.dataframe(trend_df_publisher_books)

    with tab3:
        st.header("Analisi Variazioni Settimanali per Adelphi")
        
        adelphi_data = []
        for week, week_df in sorted(dataframes.items(), key=lambda x: int(re.search(r'Settimana\s*(\d+)', x[0], re.IGNORECASE).group(1))):
            week_num = int(re.search(r'Settimana\s*(\d+)', week, re.IGNORECASE).group(1))
            if week_df is not None:
                adelphi_df = week_df[week_df['publisher'].str.contains('Adelphi', case=False, na=False)]
                if not adelphi_df.empty:
                    columns = ['title', 'author', 'units']
                    has_collana = 'collana' in week_df.columns
                    if has_collana:
                        columns.append('collana')
                    adelphi_df = adelphi_df[columns].copy()
                    adelphi_df['Settimana'] = week
                    adelphi_df['Week_Num'] = week_num
                    adelphi_data.append(adelphi_df)
        
        if adelphi_data:
            adelphi_df = pd.concat(adelphi_data, ignore_index=True)
            adelphi_df = adelphi_df.dropna(subset=['title'])
            adelphi_df['title'] = adelphi_df['title'].apply(normalize_title)
            group_cols = ['title', 'author', 'Settimana', 'Week_Num']
            dup_subset = ['title', 'Settimana']
            if has_collana and 'collana' in adelphi_df.columns:
                group_cols.append('collana')
                dup_subset.append('collana')
            adelphi_df = adelphi_df.groupby(group_cols)['units'].sum().reset_index()
            if filters.get('title', []):
                adelphi_df = adelphi_df[adelphi_df['title'].isin(filters['title'])]
            if filters.get('author', []):
                adelphi_df = adelphi_df[adelphi_df['author'].isin(filters['author'])]
            if filters.get('collana', []):
                adelphi_df = adelphi_df[adelphi_df['collana'].isin(filters['collana'])]
            adelphi_df.sort_values(['title', 'Week_Num'], inplace=True)
            
            adelphi_df['Previous_Units'] = adelphi_df.groupby(['title'] + (['collana'] if has_collana else []))['units'].shift(1)
            adelphi_df['Diff_pct'] = np.where(
                adelphi_df['Previous_Units'] > 0,
                (adelphi_df['units'] - adelphi_df['Previous_Units']) / adelphi_df['Previous_Units'] * 100,
                np.nan
            )
            
            duplicates = adelphi_df.duplicated(subset=dup_subset, keep=False)
            if duplicates.any():
                st.error(f"Trovati dati duplicati per Adelphi. Titoli con duplicati: {adelphi_df[duplicates]['title'].unique().tolist()}")
                st.dataframe(adelphi_df[duplicates][group_cols + ['units']])
                st.stop()
            
            pivot_index = 'title'
            if has_collana and 'collana' in adelphi_df.columns:
                adelphi_df['title_collana'] = adelphi_df['title'] + ' (' + adelphi_df['collana'].fillna('Sconosciuta') + ')'
                pivot_index = 'title_collana'
            pivot_diff_pct = adelphi_df.pivot(index=pivot_index, columns='Settimana', values='Diff_pct')
            pivot_units = adelphi_df.pivot(index=pivot_index, columns='Settimana', values='units')
            pivot_diff_pct = pivot_diff_pct.fillna(0)
            pivot_units = pivot_units.fillna(0)
            pivot_diff_pct_long = pivot_diff_pct.reset_index().melt(id_vars=pivot_index, var_name='Settimana', value_name='Diff_pct')
            pivot_units_long = pivot_units.reset_index().melt(id_vars=pivot_index, var_name='Settimana', value_name='units')
            pivot_df = pd.merge(pivot_diff_pct_long, pivot_units_long, on=[pivot_index, 'Settimana'])
            pivot_df = pivot_df.merge(adelphi_df[['Settimana', 'Week_Num']].drop_duplicates(), on='Settimana')
            pivot_df = pivot_df[pivot_df['Diff_pct'].notna()]
            
            if not pivot_df.empty:
                st.subheader("Heatmap Variazioni Percentuali (%) - Verde: Crescita, Rosso: Calo")
                heatmap = create_heatmap(pivot_df, pivot_index=pivot_index)
                st.altair_chart(heatmap, use_container_width=True)
            else:
                st.warning("Nessun dato valido per la heatmap dopo il filtraggio.")
            
            display_cols = ['title', 'Settimana', 'units', 'Diff_pct']
            if has_collana and 'collana' in adelphi_df.columns:
                display_cols.insert(1, 'collana')
            st.dataframe(adelphi_df[display_cols])

            st.header("Previsione Vendite per Collana (Adelphi)")
            if has_collana and 'collana' in adelphi_df.columns:
                collana_groups = adelphi_df.groupby('collana')
            else:
                collana_groups = [('Tutti', adelphi_df)]
                st.warning("Colonna 'collana' non trovata. Previsione aggregata per tutti i titoli Adelphi.")
            for collana, group_df in collana_groups:
                st.subheader(f"Collana: {collana}")
                sales_data = group_df.groupby('Week_Num')['units'].sum().reset_index().set_index('Week_Num')
                if len(sales_data) >= 3:
                    try:
                        model = ARIMA(sales_data['units'], order=(1, 1, 1))
                        model_fit = model.fit()
                        forecast_steps = 4
                        forecast = model_fit.forecast(steps=forecast_steps)
                        forecast_df = pd.DataFrame({
                            'Settimana': [f"Settimana {group_df['Week_Num'].max() + i + 1}" for i in range(forecast_steps)],
                            'Previsione Unità Vendute': forecast.round().astype(int)
                        })
                        st.dataframe(forecast_df)
                        forecast_chart = alt.Chart(forecast_df).mark_line(point=True, color='red').encode(
                            x='Settimana:N',
                            y='Previsione Unità Vendute:Q',
                            tooltip=['Settimana', 'Previsione Unità Vendute']
                        ).properties(width='container').interactive()
                        st.altair_chart(forecast_chart, use_container_width=True)
                    except Exception as e:
                        st.warning(f"Impossibile generare previsione per {collana}: {e}")
                else:
                    st.warning(f"Dati insufficienti per la previsione in {collana} (richiesti almeno 3 settimane).")

else:
    st.info("Nessun file XLSX valido in data/.")
