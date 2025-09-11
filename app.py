import streamlit as st
import pandas as pd
import re
import os
import glob
from concurrent.futures import ThreadPoolExecutor
from data_utils import normalize_title, load_data, filter_data, aggregate_group_data, aggregate_all_weeks
from viz_utils import create_top_books_chart, create_top_authors_chart, create_top_publishers_chart, create_trend_chart, create_publisher_books_trend_chart, create_heatmap

# Configurazione iniziale della pagina Streamlit
st.set_page_config(page_title="Dashboard Vendite Libri", layout="wide")
st.title("📚 Dashboard Vendite Libri")

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

# Caricamento parallelo dei file XLSX
dataframes = {}
all_publishers = set()
if not os.path.exists(DATA_DIR):
    st.error(f"Cartella {DATA_DIR} non trovata.")
else:
    xlsx_files = glob.glob(os.path.join(DATA_DIR, "Classifica week*.xlsx"))
    valid_files = []
    for file_path in xlsx_files:
        match = re.search(r'week\s*(\d+)', os.path.basename(file_path), re.IGNORECASE)
        if match:
            valid_files.append((file_path, int(match.group(1))))
        else:
            st.warning(f"Nome file non valido: {os.path.basename(file_path)}")
    valid_files = sorted(valid_files, key=lambda x: x[1])

    # Caricamento parallelo
    with ThreadPoolExecutor() as executor:
        dfs = list(executor.map(load_data, [fp for fp, _ in valid_files]))
    for (file_path, week_num), df in zip(valid_files, dfs):
        if df is not None:
            dataframes[f"Settimana {week_num}"] = df
            if 'publisher' in df.columns:
                all_publishers.update(df['publisher'].dropna().unique())
publisher_options = sorted(list(all_publishers))

# Logica principale
if dataframes:
    tab1, tab3 = st.tabs(["Principale", "Analisi Editore"])

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
            filter_cols = ["rank", "publisher", "author", "title"]
            filter_labels = {"rank": "Classifica", "publisher": "Editore", "author": "Autore", "title": "Titolo"}
            for col in filter_cols:
                if col in df.columns:
                    unique_values = sorted(df[col].dropna().unique())
                    initial_value = query_params.get(col, [])
                    if col == "rank":
                        initial_value = initial_value[0] if initial_value else "Tutti"
                        filters[col] = st.sidebar.selectbox(filter_labels[col], ["Tutti"] + [str(val) for val in unique_values], index=0 if initial_value == "Tutti" else unique_values.index(float(initial_value)) + 1)
                        st.query_params[col] = str(filters[col]) if filters[col] != "Tutti" else []
                    else:
                        filters[col] = st.sidebar.multiselect(filter_labels[col], unique_values, default=initial_value)
                        st.query_params[col] = filters[col]

            if st.sidebar.button("Reimposta Filtri"):
                st.query_params.clear()
                st.rerun()

            filtered_df = filter_data(df, filters, is_aggregate=is_aggregate)
            if filtered_df is not None and not filtered_df.empty:
                col1, col2 = st.columns(2)
                with col1:
                    st.header(f"Dati - {selected_week}")
                    st.dataframe(filtered_df, use_container_width=True)
                with col2:
                    csv = filtered_df.to_csv(index=False).encode('utf-8')
                    st.download_button("Scarica CSV", data=csv, file_name="dati_filtrati.csv", mime="text/csv")

                for group_by in ["author", "publisher", "title"]:
                    selected_values = filters.get(group_by, [])
                    if selected_values:
                        st.header(f"Statistiche per {filter_labels[group_by]}: {', '.join(map(str, selected_values))}")
                        stats = aggregate_group_data(filtered_df, group_by, selected_values)
                        if stats:
                            col1, col2 = st.columns(2)
                            col1.metric("Unità Vendute", stats["Total Units"])
                            col2.metric(f"Numero di { 'Libri' if group_by in ['author', 'publisher'] else 'Elementi' }", stats["Items"])

                st.header("Analisi Grafica")
                try:
                    top_books_chart = create_top_books_chart(filtered_df)
                    if top_books_chart:
                        st.subheader("Top 20 Libri")
                        st.altair_chart(top_books_chart, use_container_width=True)

                    top_authors_chart = create_top_authors_chart(filtered_df)
                    if top_authors_chart:
                        st.subheader("Top 10 Autori")
                        st.altair_chart(top_authors_chart, use_container_width=True)

                    top_publishers_chart = create_top_publishers_chart(filtered_df)
                    if top_publishers_chart:
                        st.subheader("Top 10 Editori")
                        st.altair_chart(top_publishers_chart, use_container_width=True)
                except Exception as e:
                    st.error(f"Errore nei grafici: {e}")

                if is_aggregate:
                    selected_title = filters.get('title', [])
                    selected_author = filters.get('author', [])
                    selected_publisher = filters.get('publisher', [])
                    if selected_title or selected_author or selected_publisher:
                        st.header("Andamento Settimanale")
                        trend_data_sum, trend_data_books = [], []
                        for week, week_df in sorted(dataframes.items(), key=lambda x: int(re.search(r'Settimana\s*(\d+)', x[0], re.IGNORECASE).group(1))):
                            week_num = int(re.search(r'Settimana\s*(\d+)', week, re.IGNORECASE).group(1))
                            if week_df is not None:
                                week_filtered = week_df.copy()
                                if selected_title:
                                    week_filtered = week_filtered[week_filtered['title'].isin(selected_title)]
                                    group_by = 'title'
                                    selected_items_sum = selected_title
                                elif selected_publisher:
                                    week_filtered = week_filtered[week_filtered['publisher'].isin(selected_publisher)]
                                    group_by = 'publisher'
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

                                    if selected_author and 'selected_items_books' in locals():
                                        for item in selected_items_books:
                                            item_df = week_filtered[week_filtered[group_by] == item]
                                            if not item_df.empty:
                                                trend_data_books.append({"Settimana": week, "Unità Vendute": item_df["units"].sum(), "Item": item, "Week_Num": week_num})

                        if trend_data_sum:
                            trend_df_sum = pd.DataFrame(trend_data_sum)
                            trend_df_sum.sort_values('Week_Num', inplace=True)
                            subheader_sum = "Andamento per " + ("Titolo" if selected_title else "Editore (Somma)" if selected_publisher else "Autore (Somma)")
                            st.subheader(subheader_sum)
                            chart_sum = create_trend_chart(trend_df_sum, 'Item')
                            st.altair_chart(chart_sum, use_container_width=True)
                            st.dataframe(trend_df_sum)

                        if selected_author and trend_data_books:
                            trend_df_books = pd.DataFrame(trend_data_books)
                            trend_df_books.sort_values('Week_Num', inplace=True)
                            st.subheader("Andamento per Libri dell'Autore")
                            chart_books = create_trend_chart(trend_df_books, 'Libro')
                            st.altair_chart(chart_books, use_container_width=True)
                            st.dataframe(trend_df_books)

                        if len(selected_publisher) == 1:
                            trend_df_publisher_books = create_publisher_books_trend_chart(dataframes, selected_publisher)
                            if trend_df_publisher_books is not None:
                                st.subheader(f"Andamento Settimanale dei Primi 20 Libri dell'Editore")
                                chart_publisher_books = create_trend_chart(trend_df_publisher_books, 'Libro')
                                st.altair_chart(chart_publisher_books, use_container_width=True)
                                st.dataframe(trend_df_publisher_books)

    with tab3:
        st.header("Analisi Variazioni Settimanali per Editore")
        selected_publisher = st.selectbox(
            "Seleziona Editore",
            publisher_options,
            index=publisher_options.index('Adelphi') if 'Adelphi' in publisher_options else 0
        )

        publisher_df = None
        publisher_data = []
        for week, week_df in sorted(dataframes.items(), key=lambda x: int(re.search(r'Settimana\s*(\d+)', x[0], re.IGNORECASE).group(1))):
            week_num = int(re.search(r'Settimana\s*(\d+)', week, re.IGNORECASE).group(1))
            if week_df is not None:
                pub_df = week_df[week_df['publisher'].str.contains(selected_publisher, case=False, na=False)]
                if not pub_df.empty:
                    pub_df = pub_df[['title', 'author', 'units']].copy()
                    pub_df['Settimana'] = week
                    pub_df['Week_Num'] = week_num
                    publisher_data.append(pub_df)

        if publisher_data:
            publisher_df = pd.concat(publisher_data, ignore_index=True)
            publisher_df['title'] = publisher_df['title'].apply(normalize_title)
            publisher_df = publisher_df.groupby(['title', 'author', 'Settimana', 'Week_Num'])['units'].sum().reset_index()

            if filters.get('title', []):
                publisher_df = publisher_df[publisher_df['title'].isin(filters['title'])]
            if filters.get('author', []):
                publisher_df = publisher_df[publisher_df['author'].isin(filters['author'])]

            publisher_df['title_author'] = publisher_df['title'] + ' (' + publisher_df['author'] + ')'

            week_nums = sorted(publisher_df['Week_Num'].unique())
            if len(week_nums) > 1 and not all(week_nums[i] + 1 == week_nums[i + 1] for i in range(len(week_nums) - 1)):
                st.warning(f"Dati settimanali non consecutivi per {selected_publisher}: i calcoli delle variazioni potrebbero essere imprecisi.")

            publisher_df.sort_values(['title_author', 'Week_Num'], inplace=True)
            publisher_df['Previous_Units'] = publisher_df.groupby('title_author')['units'].shift(1)
            publisher_df['Diff_pct'] = np.where(
                publisher_df['Previous_Units'] > 0,
                (publisher_df['units'] - publisher_df['Previous_Units']) / publisher_df['Previous_Units'] * 100,
                np.nan
            )

            duplicates = publisher_df.duplicated(subset=['title_author', 'Settimana'], keep=False)
            if duplicates.any():
                st.error(f"Trovati dati duplicati per {selected_publisher}. Elementi con duplicati: {publisher_df[duplicates]['title_author'].unique().tolist()}")
                st.dataframe(publisher_df[duplicates])
                st.stop()

            try:
                heatmap = create_heatmap(publisher_df)
                st.subheader(f"Heatmap Variazioni Percentuali (%) per {selected_publisher} - Verde: Crescita, Rosso: Calo")
                st.altair_chart(heatmap, use_container_width=True)
                st.subheader("Dati Raw")
                st.dataframe(publisher_df[['title', 'author', 'Settimana', 'units', 'Diff_pct']])
            except Exception as e:
                st.error(f"Errore nella creazione della heatmap: {e}")
                st.dataframe(publisher_df)
        else:
            st.info(f"Nessun dato disponibile per l'editore '{selected_publisher}'.")
else:
    st.info("Nessun file XLSX valido in data/.")
