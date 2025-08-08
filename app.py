import streamlit as st
import pandas as pd
try:
    import plotly.express as px
except ImportError as e:
    st.error(f"Errore nell'importazione di plotly.express: {e}")
    st.stop()

st.set_page_config(page_title="Dashboard Vendite Libri", layout="wide")
st.title("📚 Dashboard Interattiva Vendite Libri")

@st.cache_data
def load_data(file):
    try:
        # Prova a leggere il file Excel con controlli aggiuntivi
        df = pd.read_excel(file, sheet_name="Export", skiprows=16, engine="openpyxl")
        # Rimuovi righe con valori aggregati (es. "Total")
        df = df[df["Rank"].apply(lambda x: isinstance(x, (int, float)) and not pd.isna(x))]
        # Converti colonne numeriche
        numeric_cols = ["Rank", "Cover price", "Pages", "Units", "Units since release", "Value", "Value since release"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df
    except Exception as e:
        st.error(f"Errore nel caricamento del file {file.name}: {e}")
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
            except Exception as e:
                st.warning(f"Errore nel filtraggio per {col}: {e}")
    return filtered_df

def aggregate_author_data(df, author):
    if df is None or author == "Tutti":
        return None
    try:
        author_df = df[df["Author"] == author]
        if author_df.empty:
            return None
        return {
            "Total Units": author_df["Units"].sum(),
            "Total Units since release": author_df["Units since release"].sum(),
            "Total Value": author_df["Value"].sum(),
            "Books": len(author_df)
        }
    except Exception as e:
        st.warning(f"Errore nell'aggregazione per autore {author}: {e}")
        return None

st.sidebar.header("Caricamento File")
uploaded_files = st.sidebar.file_uploader("Carica i file Excel", type=["xlsx"], accept_multiple_files=True)

dataframes = {}
if uploaded_files:
    for file in uploaded_files:
        try:
            week = file.name.split("week")[1].split(".")[0].strip()
            df = load_data(file)
            if df is not None:
                dataframes[f"Settimana {week}"] = df
            else:
                st.warning(f"File {file.name} non caricato correttamente.")
        except IndexError:
            st.warning(f"Nome file non valido: {file.name}. Assicurati che contenga 'week' seguito dal numero.")
        except Exception as e:
            st.error(f"Errore durante l'elaborazione del file {file.name}: {e}")

if dataframes:
    selected_week = st.sidebar.selectbox("Seleziona la settimana", list(dataframes.keys()))
    df = dataframes[selected_week]

    st.sidebar.header("Filtri")
    filters = {}
    for col in df.columns:
        try:
            if col in ["Rank", "Cover price", "Pages", "Units", "Units since release"]:
                unique_values = sorted(df[col].dropna().unique())
                filters[col] = st.sidebar.selectbox(f"{col}", ["Tutti"] + [str(val) for val in unique_values], index=0)
            else:
                unique_values = sorted(df[col].dropna().unique())
                filters[col] = st.sidebar.selectbox(f"{col}", ["Tutti"] + unique_values, index=0)
        except Exception as e:
            st.warning(f"Errore nella creazione del filtro per {col}: {e}")

    filtered_df = filter_data(df, filters)
    if filtered_df is not None and not filtered_df.empty:
        st.header(f"Dati - {selected_week}")
        st.dataframe(filtered_df, use_container_width=True)

        # Statistiche per autore selezionato
        selected_author = filters.get("Author", "Tutti")
        if selected_author != "Tutti":
            st.header(f"Statistiche per {selected_author}")
            author_stats = aggregate_author_data(df, selected_author)
            if author_stats:
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Unità Vendute", author_stats["Total Units"])
                with col2:
                    st.metric("Unità Totali (dall'uscita)", author_stats["Total Units since release"])
                with col3:
                    st.metric("Valore Totale (€)", f"{author_stats['Total Value']:.2f}")
                with col4:
                    st.metric("Numero di Libri", author_stats["Books"])
            else:
                st.info(f"Nessun dato disponibile per l'autore {selected_author}.")

        st.header("Analisi Grafica")
        try:
            st.subheader("Top 10 Libri per Unità Vendute")
            top_10 = filtered_df.nlargest(10, "Units")[["Title", "Units"]]
            fig1 = px.bar(top_10, x="Title", y="Units", title="Top 10 Libri per Unità Vendute")
            fig1.update_layout(xaxis_title="Titolo", yaxis_title="Unità Vendute", xaxis_tickangle=45)
            st.plotly_chart(fig1, use_container_width=True)

            st.subheader("Distribuzione per Genere")
            genre_counts = filtered_df["Genre"].value_counts().reset_index()
            genre_counts.columns = ["Genre", "Count"]
            fig2 = px.pie(genre_counts, names="Genre", values="Count", title="Distribuzione dei Libri per Genere")
            st.plotly_chart(fig2, use_container_width=True)

            st.subheader("Prezzo Medio per Editore")
            avg_price = filtered_df.groupby("Publisher")["Cover price"].mean().reset_index()
            fig3 = px.bar(avg_price, x="Publisher", y="Cover price", title="Prezzo Medio per Editore")
            fig3.update_layout(xaxis_title="Editore", yaxis_title="Prezzo Medio (€)", xaxis_tickangle=45)
            st.plotly_chart(fig3, use_container_width=True)

            st.header("Statistiche Riassuntive")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Totale Unità Vendute", filtered_df["Units"].sum())
            with col2:
                st.metric("Prezzo Medio", f"€{filtered_df['Cover price'].mean():.2f}")
            with col3:
                st.metric("Numero di Libri", len(filtered_df))
        except Exception as e:
            st.error(f"Errore nella creazione dei grafici: {e}")
    else:
        st.info("Nessun dato disponibile dopo il filtraggio.")
else:
    st.info("Carica uno o più file Excel per visualizzare i dati.")

st.sidebar.markdown("""
### Istruzioni
1. Carica uno o più file Excel usando il pulsante sopra.
2. Seleziona la settimana desiderata dal menu a tendina.
3. Usa i filtri per esplorare i dati (es. seleziona un autore per vedere le statistiche aggregate).
4. Visualizza i grafici e le statistiche nella sezione principale.
""")
