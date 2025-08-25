import streamlit as st
import pandas as pd
import altair as alt  # Cambiato da Plotly a Altair per grafiche più estetiche e moderne (Altair è declarativo e produce visualizzazioni belle con temi personalizzabili)
import os
import glob
import re
import io  # Per esportazione CSV
import numpy as np  # Aggiunto per gestire np.where e np.nan

# Sezione: Configurazione iniziale della pagina Streamlit
# Qui impostiamo il titolo, il layout e uno stile personalizzato per un look più moderno
st.set_page_config(page_title="Dashboard Vendite Libri", layout="wide")
st.title("📚 Dashboard Vendite Libri")

# Stile personalizzato per migliorare l'aspetto (sfondo chiaro, font moderni)
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

# Sezione: Definizione della cartella dati
# Mantengo l'idea di una cartella 'data' con file XLSX
DATA_DIR = "data"

# Sezione: Funzione per normalizzare titoli (per congiungere varianti come "L' avversario" e "L'avversario")
def normalize_title(title):
    if isinstance(title, str):
        stripped = title.strip()
        lower_stripped = stripped.lower()
        if lower_stripped in ["l' avversario", "l'avversario"]:
            return "L'avversario"
        return stripped  # Ritorna originale stripped, non lower
    return title

# Sezione: Funzione per caricare i dati da un file XLSX
# Questa funzione legge un singolo file XLSX, standardizza le colonne, filtra righe valide e converte tipi numerici
@st.cache_data
def load_data(file_path):
    try:
        df = pd.read_excel(file_path, sheet_name="Export", header=0, engine="openpyxl")  # Legge XLSX
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
        # Normalizza titoli
        if 'title' in df.columns:
            df['title'] = df['title'].apply(normalize_title)
        return df
    except Exception as e:
        st.error(f"Errore nel caricamento di {os.path.basename(file_path)}: {e}")
        return None

# Sezione: Funzione per filtrare i dati
# Applica filtri basati su un dizionario di filtri; gestisce aggregati ignorando 'rank' se necessario
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

# Sezione: Funzione per aggregare dati per gruppo (autore, editore, titolo)
# Calcola totali unità vendute e numero di items unici
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

# Sezione: Funzione per aggregare tutte le settimane
# Concatena tutti i DataFrame e somma 'units' per combinazioni uniche di publisher, author, title
def aggregate_all_weeks(dataframes):
    all_dfs = []
    for week, df in dataframes.items():
        if df is not None:
            all_dfs.append(df)
    if not all_dfs:
        return None
    combined_df = pd.concat(all_dfs, ignore_index=True)
    # Normalizza titoli nel combined_df
    if 'title' in combined_df.columns:
        combined_df['title'] = combined_df['title'].apply(normalize_title)
    agg_df = combined_df.groupby(["publisher", "author", "title"], as_index=False)["units"].sum()
    return agg_df

# Sezione: Caricamento dei file XLSX dalla cartella 'data'
# Cerca file con pattern 'Classifica week*.xlsx', ordina per numero settimana
dataframes = {}
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
    for file_path, week_num in sorted(valid_files, key=lambda x: x[1]):
        df = load_data(file_path)
        if df is not None:
            dataframes[f"Settimana {week_num}"] = df

# Sezione: Logica principale della dashboard
if dataframes:
    # Crea schede (tabs) come richiesto: una principale con filtri, una per analisi Adelphi (rimossa "Comparazioni")
    tab1, tab3 = st.tabs(["Principale", "Analisi Adelphi"])

    # Sezione: Scheda Principale - Gestisce selezione settimana, filtri in italiano, dati e statistiche
    with tab1:
        week_options = ["Tutti"] + sorted(dataframes.keys(), key=lambda x: int(re.search(r'Settimana\s*(\d+)', x, re.IGNORECASE).group(1)))
        # Sincronizza con query_params
        query_params = st.query_params.to_dict()
        initial_week = query_params.get('selected_week', ["Tutti"])[0]
        if initial_week not in week_options:
            initial_week = "Tutti"
        selected_week = st.sidebar.selectbox("Seleziona la Settimana", week_options, index=week_options.index(initial_week))  # Filtro in italiano
        st.query_params['selected_week'] = selected_week
        
        is_aggregate = selected_week == "Tutti"
        if is_aggregate:
            df = aggregate_all_weeks(dataframes)
        else:
            df = dataframes[selected_week]

        if df is not None:
            st.sidebar.header("Filtri")  # Header in italiano
            filters = {}
            filter_cols = ["rank", "publisher", "author", "title"]
            filter_labels = {"rank": "Classifica", "publisher": "Editore", "author": "Autore", "title": "Titolo"}  # Etichette in italiano
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

            filtered_df = filter_data(df, filters, is_aggregate=is_aggregate)
            if filtered_df is not None and not filtered_df.empty:
                col1, col2 = st.columns(2)
                with col1:
                    st.header(f"Dati - {selected_week}")
                    st.dataframe(filtered_df, use_container_width=True)
                with col2:
                    csv = filtered_df.to_csv(index=False).encode('utf-8')
                    st.download_button("Scarica CSV", data=csv, file_name="dati_filtrati.csv", mime="text/csv")

                # Statistiche aggregate per gruppi selezionati
                for group_by in ["author", "publisher", "title"]:
                    selected_values = filters.get(group_by, [])
                    if selected_values:
                        st.header(f"Statistiche per {filter_labels[group_by]}: {', '.join(map(str, selected_values))}")
                        stats = aggregate_group_data(filtered_df, group_by, selected_values)
                        if stats:
                            col1, col2 = st.columns(2)
                            col1.metric("Unità Vendute", stats["Total Units"])
                            col2.metric(f"Numero di { 'Libri' if group_by in ['author', 'publisher'] else 'Elementi' }", stats["Items"])

                # Sezione: Analisi Grafica nella scheda principale (usando Altair per grafiche più belle)
                st.header("Analisi Grafica")
                try:
                    # Top 20 Libri - Gestisci singolo valore con metric invece di chart
                    st.subheader("Top 20 Libri")
                    top_books = filtered_df.nlargest(20, "units")[["title", "units"]]
                    if len(top_books) == 1:
                        st.metric(label=top_books['title'].iloc[0], value=top_books['units'].iloc[0])
                    else:
                        chart1 = alt.Chart(top_books).mark_bar(color='#4c78a8').encode(
                            x=alt.X('title:N', sort='-y', title='Titolo'),
                            y=alt.Y('units:Q', title='Unità Vendute'),
                            tooltip=['title', 'units']
                        ).properties(width='container').interactive()
                        st.altair_chart(chart1, use_container_width=True)

                    # Top 10 Autori - Gestisci singolo valore con metric
                    st.subheader("Top 10 Autori")
                    author_units = filtered_df.groupby("author")["units"].sum()
                    author_units = author_units[author_units.index != 'AA.VV.']  # Escludi "AA.VV." (con punto)
                    top_authors = author_units.nlargest(10).reset_index()
                    if len(top_authors) == 1:
                        st.metric(label=top_authors['author'].iloc[0], value=top_authors['units'].iloc[0])
                    else:
                        chart2 = alt.Chart(top_authors).mark_bar(color='#54a24b').encode(
                            x=alt.X('author:N', sort='-y', title='Autore'),
                            y=alt.Y('units:Q', title='Unità Vendute'),
                            tooltip=['author', 'units']
                        ).properties(width='container').interactive()
                        st.altair_chart(chart2, use_container_width=True)

                    # Top 10 Editori - Gestisci singolo valore con metric
                    st.subheader("Top 10 Editori")
                    top_publishers = filtered_df.groupby("publisher")["units"].sum().nlargest(10).reset_index()
                    if len(top_publishers) == 1:
                        st.metric(label=top_publishers['publisher'].iloc[0], value=top_publishers['units'].iloc[0])
                    else:
                        chart3 = alt.Chart(top_publishers).mark_bar(color='#e45756').encode(
                            x=alt.X('publisher:N', sort='-y', title='Editore'),
                            y=alt.Y('units:Q', title='Unità Vendute'),
                            tooltip=['publisher', 'units']
                        ).properties(width='container').interactive()
                        st.altair_chart(chart3, use_container_width=True)
                except Exception as e:
                    st.error(f"Errore nei grafici: {e}")

                # Sezione: Grafico Andamento Settimanale (solo se settimana == "Tutti" e selezione di titolo, autore o editore)
                if is_aggregate:
                    selected_title = filters.get('title', [])
                    selected_author = filters.get('author', [])
                    selected_publisher = filters.get('publisher', [])
                    if selected_title or selected_author or selected_publisher:
                        st.header("Andamento Settimanale")
                        trend_data_books = []  # Per libri singoli (se autore)
                        trend_data_sum = []    # Per somma (autore, editore, titolo)
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
                                    group_by = 'title'  # Per autori, aggrega per titolo per linee multiple
                                    selected_items_books = week_filtered['title'].unique().tolist()  # Tutti i libri dell'autore
                                    selected_items_sum = selected_author  # Per somma per autore

                                if not week_filtered.empty:
                                    # Per somma (per titolo, editore, o autore)
                                    for item in selected_items_sum:
                                        item_df = week_filtered[week_filtered['author' if selected_author else group_by] == item] if selected_author else week_filtered[week_filtered[group_by] == item]
                                        if not item_df.empty:
                                            trend_data_sum.append({"Settimana": week, "Unità Vendute": item_df["units"].sum(), "Item": item, "Week_Num": week_num})

                                    # Per libri singoli (solo per autore)
                                    if selected_author and selected_items_books:
                                        for item in selected_items_books:
                                            item_df = week_filtered[week_filtered[group_by] == item]
                                            if not item_df.empty:
                                                trend_data_books.append({"Settimana": week, "Unità Vendute": item_df["units"].sum(), "Item": item, "Week_Num": week_num})

                        # Grafico per somma
                        if trend_data_sum:
                            trend_df_sum = pd.DataFrame(trend_data_sum)
                            trend_df_sum.sort_values('Week_Num', inplace=True)
                            if selected_title:
                                subheader_sum = "Andamento per Titolo"
                            elif selected_author:
                                subheader_sum = "Andamento per Autore (Somma)"
                            elif selected_publisher:
                                subheader_sum = "Andamento per Editore (Somma)"
                            st.subheader(subheader_sum)
                            chart_sum = alt.Chart(trend_df_sum).mark_line(point=True).encode(
                                x=alt.X('Settimana:N', sort=alt.EncodingSortField(field='Week_Num', order='ascending'), title='Settimana'),
                                y=alt.Y('Unità Vendute:Q', title='Unità Vendute'),
                                color=alt.Color('Item:N', legend=alt.Legend(title="Item")),
                                tooltip=['Settimana', 'Unità Vendute', 'Item']
                            ).properties(width='container').interactive()
                            st.altair_chart(chart_sum, use_container_width=True)
                            st.dataframe(trend_df_sum)

                        # Grafico per libri singoli (solo se autore)
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

    # Sezione: Scheda Analisi Adelphi - Analisi specifica per l'editore 'Adelphi', con heatmap delle variazioni settimanali
    with tab3:
        st.header("Analisi Variazioni Settimanali per Adelphi")
        
        # Raccolgo i dati solo per publisher == 'Adelphi'
        adelphi_data = []
        for week, week_df in sorted(dataframes.items(), key=lambda x: int(re.search(r'Settimana\s*(\d+)', x[0], re.IGNORECASE).group(1))):
            week_num = int(re.search(r'Settimana\s*(\d+)', week, re.IGNORECASE).group(1))
            if week_df is not None:
                adelphi_df = week_df[week_df['publisher'].str.contains('Adelphi', case=False, na=False)]  # Filtra per 'Adelphi' (case-insensitive)
                if not adelphi_df.empty:
                    adelphi_df = adelphi_df[['title', 'author', 'units']].copy()  # Aggiunto 'author' per filtraggio
                    adelphi_df['Settimana'] = week
                    adelphi_df['Week_Num'] = week_num
                    adelphi_data.append(adelphi_df)
        
        if adelphi_data:
            adelphi_df = pd.concat(adelphi_data, ignore_index=True)
            # Aggrega per titolo e settimana per gestire duplicati
            adelphi_df = adelphi_df.groupby(['title', 'author', 'Settimana', 'Week_Num'])['units'].sum().reset_index()
            # Applica filtri globali (autore, titolo) alla heatmap
            if filters.get('title', []):
                adelphi_df = adelphi_df[adelphi_df['title'].isin(filters['title'])]
            if filters.get('author', []):
                adelphi_df = adelphi_df[adelphi_df['author'].isin(filters['author'])]
            adelphi_df.sort_values(['title', 'Week_Num'], inplace=True)
            
            # Calcola le differenze percentuali rispetto alla settimana precedente per ogni titolo
            adelphi_df['Previous_Units'] = adelphi_df.groupby('title')['units'].shift(1)
            adelphi_df['Diff_pct'] = np.where(
                adelphi_df['Previous_Units'] > 0,
                (adelphi_df['units'] - adelphi_df['Previous_Units']) / adelphi_df['Previous_Units'] * 100,
                0  # Imposta a 0 per la prima settimana o se previous <= 0
            )
            
            # Calcola il totale venduto per titolo per ordinare i titoli da most sold a least sold
            total_units_per_title = adelphi_df.groupby('title')['units'].sum().sort_values(ascending=False).index.tolist()
            
            # Pivot per heatmap: righe = title, colonne = Settimana, valori = Diff_pct (per colori), units per tooltip
            pivot_diff_pct = adelphi_df.pivot(index='title', columns='Settimana', values='Diff_pct')
            pivot_units = adelphi_df.pivot(index='title', columns='Settimana', values='units')
            # Per formato long, melt entrambi e merge
            pivot_diff_pct_long = pivot_diff_pct.reset_index().melt(id_vars='title', var_name='Settimana', value_name='Diff_pct')
            pivot_units_long = pivot_units.reset_index().melt(id_vars='title', var_name='Settimana', value_name='units')
            pivot_df = pd.merge(pivot_diff_pct_long, pivot_units_long, on=['title', 'Settimana'])
            pivot_df = pivot_df.merge(adelphi_df[['Settimana', 'Week_Num']].drop_duplicates(), on='Settimana')  # Aggiungi Week_Num per sort
            
            # Heatmap con Altair: colori basati su Diff_pct (rosso per negativo, verde per positivo)
            st.subheader("Heatmap Variazioni Percentuali (%) - Verde: Crescita, Rosso: Calo")
            heatmap = alt.Chart(pivot_df).mark_rect().encode(
                x=alt.X('Settimana:O', sort=alt.EncodingSortField(field='Week_Num', order='ascending')),
                y=alt.Y('title:O', sort=total_units_per_title),
                color=alt.Color('Diff_pct:Q', scale=alt.Scale(scheme='redyellowgreen', domainMid=0), title='Variazione %'),
                tooltip=['title', 'Settimana', 'units', 'Diff_pct']
            ).properties(width='container').interactive(bind_y=True)  # Abilita zoom su y (titoli)
            st.altair_chart(heatmap, use_container_width=True)
            
            # Mostra anche il dataframe raw per riferimento (per CTRL+F sui titoli)
            st.dataframe(adelphi_df[['title', 'Settimana', 'units', 'Diff_pct']])
        else:
            st.info("Nessun dato disponibile per l'editore 'Adelphi'.")
else:
    st.info("Nessun file XLSX valido in data/.")
