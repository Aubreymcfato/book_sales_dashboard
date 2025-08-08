import streamlit as st
import pandas as pd
import plotly.express as px
import os
import glob

st.set_page_config(page_title="Dashboard Vendite Libri", layout="wide")
st.title("📚 Dashboard Vendite Libri")

DATA_DIR = "data"

@st.cache_data
def load_data(file_path):
    try:
        df = pd.read_excel(file_path, sheet_name="Export", skiprows=16, engine="openpyxl")
        df = df[df["Rank"].apply(lambda x: isinstance(x, (int, float)) and not pd.isna(x))]
        numeric_cols = ["Rank", "Cover price", "Pages", "Units", "Units since release", "Value"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df
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
                if col in ["Rank", "Cover price", "Pages", "Units", "Units since release"]:
                    filtered_df = filtered_df[filtered_df[col] == float(value)]
                else:
                    filtered_df = filtered_df[filtered_df[col] == value]
            except:
                pass
    return filtered_df

def aggregate_author_data(df, author):
    if df is None or author == "Tutti":
        return None
    author_df = df[df["Author"] == author]
    if author_df.empty:
        return None
    return {
        "Total Units": author_df["Units"].sum(),
        "Books": len(author_df)
    }

# Carica tutti i file Excel dalla cartella data/
dataframes = {}
if not os.path.exists(DATA_DIR):
    st.error(f"Cartella {DATA_DIR} non trovata nel repository.")
else:
    excel_files = glob.glob(os.path.join(DATA_DIR, "Classifica week*.xlsx"))
    for file_path in excel_files:
        try:
            week = os.path.basename(file_path).split("week")[1].split(".")[0].strip()
            df = load_data(file_path)
            if df is not None:
                dataframes[f"Settimana {week}"] = df
        except:
            st.warning(f"Nome file non valido: {os.path.basename(file_path)}")

if dataframes:
    selected_week = st.sidebar.selectbox("Seleziona la settimana", list(dataframes.keys()))
    df = dataframes[selected_week]

    st.sidebar.header("Filtri")
    filters = {}
    for col in df.columns:
        if col in ["Rank", "Cover price", "Pages", "Units", "Units since release"]:
            unique_values = sorted(df[col].dropna().unique())
            filters[col] = st.sidebar.selectbox(f"{col}", ["Tutti"] + [str(val) for val in unique_values], index=0)
        else:
            unique_values = sorted(df[col].dropna().unique())
            filters[col] = st.sidebar.selectbox(f"{col}", ["Tutti"] + unique_values, index=0)

    filtered_df = filter_data(df, filters)
    if filtered_df is not None and not filtered_df.empty:
        st.header(f"Dati - {selected_week}")
        st.dataframe(filtered_df, use_container_width=True)

        # Statistiche per autore
        selected_author = filters.get("Author", "Tutti")
        if selected_author != "Tutti":
            st.header(f"Statistiche per {selected_author}")
            author_stats = aggregate_author_data(df, selected_author)
            if author_stats:
                col1, col2 = st.columns(2)
                col1.metric("Unità Vendute", author_stats["Total Units"])
                col2.metric("Numero di Libri", author_stats["Books"])

        # Confronto tra settimane
        st.header("Confronto tra Settimane")
        compare_by = st.sidebar.selectbox("Confronta per", ["Titolo", "Autore"])
        if compare_by == "Titolo":
            items = sorted(df["Title"].dropna().unique())
        else:
            items = sorted(df["Author"].dropna().unique())
        selected_item = st.sidebar.selectbox(f"Seleziona {compare_by}", ["Tutti"] + items)
        
        if selected_item != "Tutti":
            trend_data = []
            for week, week_df in dataframes.items():
                if week_df is not None:
                    item_df = week_df[week_df[compare_by] == selected_item]
                    if not item_df.empty:
                        units = item_df["Units"].sum()
                        trend_data.append({"Settimana": week, "Unità Vendute": units})
            if trend_data:
                trend_df = pd.DataFrame(trend_data)
                st.subheader(f"Andamento di {selected_item}")
                fig = px.line(trend_df, x="Settimana", y="Unità Vendute", title=f"Vendite di {selected_item} per Settimana")
                st.plotly_chart(fig, use_container_width=True)
                st.dataframe(trend_df, use_container_width=True)
            else:
                st.info(f"Nessun dato trovato per {selected_item}.")

        st.header("Analisi Grafica")
        try:
            st.subheader("Top 10 Libri per Unità Vendute")
            top_10 = filtered_df.nlargest(10, "Units")[["Title", "Units"]]
            fig1 = px.bar(top_10, x="Title", y="Units")
            fig1.update_layout(xaxis_title="Titolo", yaxis_title="Unità Vendute", xaxis_tickangle=45)
            st.plotly_chart(fig1, use_container_width=True)

            st.subheader("Distribuzione per Genere")
            genre_counts = filtered_df["Genre"].value_counts().reset_index()
            genre_counts.columns = ["Genre", "Count"]
            fig2 = px.pie(genre_counts, names="Genre", values="Count")
            st.plotly_chart(fig2, use_container_width=True)

            st.subheader("Prezzo Medio per Editore")
            avg_price = filtered_df.groupby("Publisher")["Cover price"].mean().reset_index()
            fig3 = px.bar(avg_price, x="Publisher", y="Cover price")
            fig3.update_layout(xaxis_title="Editore", yaxis_title="Prezzo Medio (€)", xaxis_tickangle=45)
            st.plotly_chart(fig3, use_container_width=True)
        except:
            st.error("Errore nella creazione dei grafici.")
else:
    st.info("Nessun file Excel valido trovato nella cartella data/.")
