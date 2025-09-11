import altair as alt
import pandas as pd
import re

def create_top_books_chart(filtered_df):
    top_books = filtered_df.nlargest(20, "units")[["title", "units"]]
    if len(top_books) <= 1:
        return None
    return alt.Chart(top_books).mark_bar(color='#4c78a8').encode(
        x=alt.X('title:N', sort='-y', title='Titolo'),
        y=alt.Y('units:Q', title='Unità Vendute'),
        tooltip=['title', 'units']
    ).properties(width='container').interactive()

def create_top_authors_chart(filtered_df):
    author_units = filtered_df.groupby("author")["units"].sum()
    author_units = author_units[author_units.index != 'AA.VV.']
    top_authors = author_units.nlargest(10).reset_index()
    if len(top_authors) <= 1:
        return None
    return alt.Chart(top_authors).mark_bar(color='#54a24b').encode(
        x=alt.X('author:N', sort='-y', title='Autore'),
        y=alt.Y('units:Q', title='Unità Vendute'),
        tooltip=['author', 'units']
    ).properties(width='container').interactive()

def create_top_publishers_chart(filtered_df):
    top_publishers = filtered_df.groupby("publisher")["units"].sum().nlargest(10).reset_index()
    if len(top_publishers) <= 1:
        return None
    return alt.Chart(top_publishers).mark_bar(color='#e45756').encode(
        x=alt.X('publisher:N', sort='-y', title='Editore'),
        y=alt.Y('units:Q', title='Unità Vendute'),
        tooltip=['publisher', 'units']
    ).properties(width='container').interactive()

def create_trend_chart(trend_df, legend_title):
    return alt.Chart(trend_df).mark_line(point=True).encode(
        x=alt.X('Settimana:N', sort=alt.EncodingSortField(field='Week_Num', order='ascending'), title='Settimana'),
        y=alt.Y('Unità Vendute:Q', title='Unità Vendute'),
        color=alt.Color('Item:N', legend=alt.Legend(title=legend_title)),
        tooltip=['Settimana', 'Unità Vendute', 'Item']
    ).properties(width='container').interactive()

def create_publisher_books_trend_chart(dataframes, selected_publisher):
    trend_data_publisher_books = []
    publisher_books = dataframes[0] if dataframes else None  # Assumes aggregate_all_weeks is called, but for simplicity
    if publisher_books is None:
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
    if not trend_data_publisher_books:
        return None
    trend_df_publisher_books = pd.DataFrame(trend_data_publisher_books)
    trend_df_publisher_books.sort_values('Week_Num', inplace=True)
    return trend_df_publisher_books

def create_heatmap(publisher_df):
    pivot_diff_pct = publisher_df.pivot(index='title_author', columns='Settimana', values='Diff_pct')
    pivot_units = publisher_df.pivot(index='title_author', columns='Settimana', values='units')
    total_units_per_title = publisher_df.groupby('title_author')['units'].sum().sort_values(ascending=False).index.tolist()
    pivot_diff_pct_long = pivot_diff_pct.reset_index().melt(id_vars='title_author', var_name='Settimana', value_name='Diff_pct')
    pivot_units_long = pivot_units.reset_index().melt(id_vars='title_author', var_name='Settimana', value_name='units')
    pivot_df = pd.merge(pivot_diff_pct_long, pivot_units_long, on=['title_author', 'Settimana'])
    pivot_df = pivot_df.merge(publisher_df[['Settimana', 'Week_Num']].drop_duplicates(), on='Settimana')
    return alt.Chart(pivot_df).mark_rect().encode(
        x=alt.X('Settimana:O', sort=alt.EncodingSortField(field='Week_Num', order='ascending'), title='Settimana'),
        y=alt.Y('title_author:O', sort=total_units_per_title, title='Titolo (Autore)'),
        color=alt.Color('Diff_pct:Q', scale=alt.Scale(scheme='redyellowgreen', domainMid=0), title='Variazione %'),
        tooltip=['title_author', 'Settimana', 'units', alt.Tooltip('Diff_pct:Q', format='.2f')]
    ).properties(width='container').interactive(bind_y=True)
