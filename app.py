import streamlit as st
import pandas as pd
import altair as alt  # Cambiato da Plotly a Altair per grafiche più estetiche e moderne (Altair è declarativo e produce visualizzazioni belle con temi personalizzabili)
import os
import glob
import re
import io  # Per esportazione CSV

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
# Mantengo l'idea di una cartella 'data' con file CSV (cambiato da .xlsx a .csv come richiesto)
DATA_DIR = "data"

# Sezione: Funzione per caricare i dati da un file CSV
# Questa funzione legge un singolo file CSV, standardizza le colonne, filtra righe valide e converte tipi numerici
@st.cache_data
def load_data(file_path):
    try:
        df = pd.read_csv(file_path)  # Cambiato da read_excel a read_csv
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
    agg_df = combined_df.groupby(["publisher", "author", "title"], as_index=False)["units"].sum()
    return agg_df

# Sezione: Caricamento dei file CSV dalla cartella 'data'
# Cerca file con pattern 'Classifica week*.csv', ordina per numero settimana
dataframes = {}
if not os.path.exists(DATA_DIR):
    st.error(f"Cartella {DATA_DIR} non trovata.")
else:
    csv_files = glob.glob(os.path.join(DATA_DIR, "Classifica week*.csv"))  # Cambiato da .xlsx a .csv
    valid_files = []
    for file_path in csv_files:
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
    # Crea schede (tabs) come richiesto: una principale con filtri, una per comparazioni
    tab1, tab2 = st.tabs(["Principale", "Comparazioni"])

    # Sezione: Scheda Principale - Gestisce selezione settimana, filtri in italiano, dati e statistiche
    with tab1:
        week_options = ["Tutti"] + sorted(dataframes.keys(), key=lambda x: int(re.search(r'Settimana\s*(\d+)', x, re.IGNORECASE).group(1)))
        selected_week = st.sidebar.selectbox("Seleziona la Settimana", week_options)  # Filtro in italiano
        
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
                    if col == "rank":
                        filters[col] = st.sidebar.selectbox(filter_labels[col], ["Tutti"] + [str(val) for val in unique_values], index=0)
                    else:
                        filters[col] = st.sidebar.multiselect(filter_labels[col], unique_values)  # Multi-select per confronti multipli

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
                    # Top 20 Libri - Grafico a barre con Altair (più estetico, con tooltips e tema)
                    st.subheader("Top 20 Libri")
                    top_books = filtered_df.nlargest(20, "units")[["title", "units"]]
                    chart1 = alt.Chart(top_books).mark_bar(color='#4c78a8').encode(
                        x=alt.X('title:N', sort='-y', title='Titolo'),
                        y=alt.Y('units:Q', title='Unità Vendute'),
                        tooltip=['title', 'units']
                    ).properties(width='container').interactive()
                    st.altair_chart(chart1, use_container_width=True)

                    # Top 10 Autori
                    st.subheader("Top 10 Autori")
                    top_authors = filtered_df.groupby("author")["units"].sum().nlargest(10).reset_index()
                    chart2 = alt.Chart(top_authors).mark_bar(color='#54a24b').encode(
                        x=alt.X('author:N', sort='-y', title='Autore'),
                        y=alt.Y('units:Q', title='Unità Vendute'),
                        tooltip=['author', 'units']
                    ).properties(width='container').interactive()
                    st.altair_chart(chart2, use_container_width=True)

                    # Top 10 Editori
                    st.subheader("Top 10 Editori")
                    top_publishers = filtered_df.groupby("publisher")["units"].sum().nlargest(10).reset_index()
                    chart3 = alt.Chart(top_publishers).mark_bar(color='#e45756').encode(
                        x=alt.X('publisher:N', sort='-y', title='Editore'),
                        y=alt.Y('units:Q', title='Unità Vendute'),
                        tooltip=['publisher', 'units']
                    ).properties(width='container').interactive()
                    st.altair_chart(chart3, use_container_width=True)
                except Exception as e:
                    st.error(f"Errore nei grafici: {e}")

    # Sezione: Scheda Comparazioni - Solo per confronti tra settimane, senza filtri generali
    with tab2:
        st.header("Confronto tra Settimane")
        compare_by = st.sidebar.selectbox("Confronta per", ["title", "author", "publisher"], format_func=lambda x: {"title": "Titolo", "author": "Autore", "publisher": "Editore"}[x])  # Etichette in italiano
        if compare_by in df.columns:  # Usa l'ultimo df caricato per opzioni
            items = sorted(df[compare_by].dropna().unique())
            selected_items = st.sidebar.multiselect(f"Seleziona { {'title': 'Titoli', 'author': 'Autori', 'publisher': 'Editori'}[compare_by] }", items)  # Multi-select in italiano
            if selected_items:
                trend_data = []
                for week, week_df in sorted(dataframes.items(), key=lambda x: int(re.search(r'Settimana\s*(\d+)', x[0], re.IGNORECASE).group(1))):
                    if week_df is not None and compare_by in week_df.columns:
                        for item in selected_items:
                            item_df = week_df[week_df[compare_by] == item]
                            if not item_df.empty:
                                trend_data.append({"Settimana": week, "Unità Vendute": item_df["units"].sum(), "Item": item})
                if trend_data:
                    trend_df = pd.DataFrame(trend_data)
                    st.subheader(f"Andamento per { {'title': 'Titolo', 'author': 'Autore', 'publisher': 'Editore'}[compare_by] }")
                    # Grafico linea con Altair per confronti (più bello, con colori, tooltips e interattività)
                    chart = alt.Chart(trend_df).mark_line(point=True).encode(
                        x=alt.X('Settimana:N', title='Settimana'),
                        y=alt.Y('Unità Vendute:Q', title='Unità Vendute'),
                        color=alt.Color('Item:N', legend=alt.Legend(title="Item")),
                        tooltip=['Settimana', 'Unità Vendute', 'Item']
                    ).properties(width='container').interactive()
                    st.altair_chart(chart, use_container_width=True)
                    st.dataframe(trend_df)
                else:
                    st.info(f"Nessun dato per i selezionati.")
else:
    st.info("Nessun file CSV valido in data/.")
