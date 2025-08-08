import streamlit as st
import pandas as pd
import plotly.express as px
import os
import glob
import re

st.set_page_config(page_title="Dashboard Vendite Libri", layout="wide")
st.title("📚 Dashboard Vendite Libri")

DATA_DIR = "data"

@st.cache_data
def load_data(file_path):
    try:
        # Prova diverse righe di intestazione
        for skip in range(10, 21):
            try:
                df = pd.read_excel(file_path, sheet_name="Export", skiprows=skip, engine="openpyxl")
                # Converte i nomi delle colonne in stringhe
                df.columns = [str(col).strip().lower().replace(" ", "_") for col in df.columns]
                # Cerca colonna 'Rank' (case-insensitive)
                rank_col = next((col for col in df.columns if col in ["rank", "rango", "classifica"]), None)
                if rank_col:
                    df = df.rename(columns={rank_col: "rank"})
                    # Filtra righe con 'Rank' numerico
                    df = df[df["rank"].apply(lambda x: pd.notna(x) and isinstance(x, (int, float)))]
                    if not df.empty:
                        numeric_cols = ["rank", "units"]  # Commentate: "cover_price", "pages", "units_since_release", "value", "value_since_release"
                        for col in numeric_cols:
                            if col in df.columns:
                                df[col] = pd.to_numeric(df[col], errors="coerce")
                        return df
            except:
                continue
        st.error(f"File {os.path.basename(file_path)} manca colonna 'Rank' o varianti. Colonne trovate: {list(df.columns)}")
        return None
    except Exception as e:
        st.error(f"Errore nel caricamento di {os.path.basename(file_path)}: {e}")
        return None

def filter_data(df, filters):
    if df is None:
        return None
    filtered_df = df.copy()
    for col, value in filters.items():
        if value and value != "Tutti":
            try:
                if col == "rank":
                    filtered_df = filtered_df[filtered_df[col] == float(value)]
                else:
                    filtered_df = filtered_df[filtered_df[col] == value]
            except Exception as e:
                st.warning(f"Errore nel filtraggio per {col}: {e}")
    return filtered_df

def aggregate_author_data(df, author):
    if df is None or author == "Tutti":
        return None
    author_df = df[df["author"] == author]
    if author_df.empty:
        return None
    return {
        "Total Units": author_df["units"].sum(),
        "Books": len(author_df)
    }

# Carica file Excel in ordine numerico
dataframes = {}
if not os.path.exists(DATA_DIR):
    st.error(f"Cartella {DATA_DIR} non trovata.")
else:
    excel_files = glob.glob(os.path.join(DATA_DIR, "Classifica week*.xlsx"))
    valid_files = []
    for file_path in excel_files:
        match = re.search(r'week\s*(\d+)', os.path.basename(file_path), re.IGNORECASE)
        if match:
            valid_files.append((file_path, int(match.group(1))))
        else:
            st.warning(f"Nome file non valido (pattern 'week <numero>' non trovato): {os.path.basename(file_path)}")
    # Ordina per numero settimana
    for file_path, week_num in sorted(valid_files, key=lambda x: x[1]):
        try:
            df = load_data(file_path)
            if df is not None:
                dataframes[f"Settimana {week_num}"] = df
        except Exception as e:
            st.warning(f"Errore nel processing del file: {os.path.basename(file_path)}: {e}")

if dataframes:
    selected_week = st.sidebar.selectbox("Seleziona la settimana", sorted(dataframes.keys(), key=lambda x: int(re.search(r'Settimana\s*(\d+)', x, re.IGNORECASE).group(1))))
    df = dataframes[selected_week]

    st.sidebar.header("Filtri")
    filters = {}
    filter_cols = ["rank", "publisher", "author", "title"]
    for col in filter_cols:
        if col in df.columns:
            unique_values = sorted(df[col].dropna().unique())
            filters[col] = st.sidebar.selectbox(f"{col}", ["Tutti"] + [str(val) for val in unique_values], index=0)
        # Commentate: "author_nationality", "isbn_ean", "cover_price", "pages", "format",
        # "genre_level_1", "genre_level_2", "genre", "release_date",
        # "units", "units_since_release", "value", "value_since_release"

    filtered_df = filter_data(df, filters)
    if filtered_df is not None and not filtered_df.empty:
        st.header(f"Dati - {selected_week}")
        st.dataframe(filtered_df, use_container_width=True)

        # Statistiche autore
        selected_author = filters.get("author", "Tutti")
        if selected_author != "Tutti":
            st.header(f"Statistiche per {selected_author}")
            author_stats = aggregate_author_data(df, selected_author)
            if author_stats:
                col1, col2 = st.columns(2)
                col1.metric("Unità Vendute", author_stats["Total Units"])
                col2.metric("Numero di Libri", author_stats["Books"])

        # Confronto settimane
        st.header("Confronto tra Settimane")
        compare_by = st.sidebar.selectbox("Confronta per", ["title", "author"])
        if compare_by in df.columns:
            items = sorted(df[compare_by].dropna().unique())
            selected_item = st.sidebar.selectbox(f"Seleziona {compare_by}", ["Tutti"] + items)
            if selected_item != "Tutti":
                trend_data = []
                for week, week_df in sorted(dataframes.items(), key=lambda x: int(re.search(r'Settimana\s*(\d+)', x[0], re.IGNORECASE).group(1))):
                    if week_df is not None and compare_by in week_df.columns:
                        item_df = week_df[week_df[compare_by] == selected_item]
                        if not item_df.empty:
                            trend_data.append({"Settimana": week, "Unità Vendute": item_df["units"].sum()})
                if trend_data:
                    trend_df = pd.DataFrame(trend_data)
                    st.subheader(f"Andamento di {selected_item}")
                    fig = px.line(trend_df, x="Settimana", y="Unità Vendute")
                    st.plotly_chart(fig, use_container_width=True)
                    st.dataframe(trend_df)
                else:
                    st.info(f"Nessun dato per {selected_item}.")

        st.header("Analisi Grafica")
        try:
            st.subheader("Top 10 Libri")
            top_10 = filtered_df.nlargest(10, "units")[["title", "units"]]
            fig1 = px.bar(top_10, x="title", y="units")
            fig1.update_layout(xaxis_title="Titolo", yaxis_title="Unità Vendute", xaxis_tickangle=45)
            st.plotly_chart(fig1, use_container_width=True)
        except:
            st.error("Errore nei grafici.")
else:
    st.info("Nessun file Excel valido in data/.")
