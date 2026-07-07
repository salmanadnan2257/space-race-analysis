"""
Space Race Analysis
====================

Analyses ~4,300 space mission launches (1957 to 2020, scraped from
nextspaceflight.com) to answer questions about which organisations launch the
most, how launch cost has moved over time, and how the launch cadence of the
USA and the USSR compared during the Cold War.

Usage:
    python space_race_analysis.py

Every chart is written as a PNG (matplotlib figures) or HTML file (Plotly
figures) into ./output/. Set SHOW_PLOTS=1 to also pop up an interactive
window/browser tab for each chart (requires a display).
"""
import os

import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
import pycountry

MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September',
          'October', 'November', 'December']

BASE_PATH = os.path.abspath(os.path.dirname(__file__))
OUTPUT_DIR = os.path.join(BASE_PATH, 'output')
SHOW_PLOTS = os.environ.get('SHOW_PLOTS', '0') == '1'


def lookup_country(location):
    """Map a free-text 'City, Country' location string to an ISO alpha-3 code."""
    try:
        location = location.split(',')[-1].strip()
        return pycountry.countries.lookup(location).alpha_3
    except LookupError:
        return None


def year(date):
    return date.year


def month(date):
    return MONTHS[date.month - 1]


def save_and_maybe_show_mpl(name):
    """Save the current matplotlib figure to OUTPUT_DIR and optionally display it."""
    path = os.path.join(OUTPUT_DIR, f'{name}.png')
    plt.savefig(path, bbox_inches='tight')
    if SHOW_PLOTS:
        plt.show()
    plt.close()
    print(f'Saved {path}')


def save_and_maybe_show_plotly(fig, name):
    """Save a Plotly figure to OUTPUT_DIR as HTML and optionally open it."""
    path = os.path.join(OUTPUT_DIR, f'{name}.html')
    fig.write_html(path)
    if SHOW_PLOTS:
        fig.show()
    print(f'Saved {path}')


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    pd.options.display.float_format = '{:,.2f}'.format
    df_data = pd.read_csv(os.path.join(BASE_PATH, 'mission_launches.csv'))

    # Preliminary Data Exploration
    print('Shape:', df_data.shape)
    print(df_data.info())
    print('Columns:', df_data.columns.tolist())
    print('Any NaN values:', df_data.isna().values.any())
    print('Any duplicated rows:', df_data.duplicated().values.any())

    # Data Cleaning - Check for Missing Values and Duplicates
    print('NaN per column:\n', df_data.isna().sum())
    print('Duplicated rows:', df_data.duplicated().sum())

    # Data Cleaning - Drop Duplicates and the two junk index columns scraped in by mistake
    df_data.drop_duplicates(inplace=True)
    df_data.drop(columns=['Unnamed: 0', 'Unnamed: 0.1'], inplace=True)

    # Descriptive Statistics
    print(df_data.describe())

    # Number of Launches per Company
    plt.figure(figsize=(8, 5), dpi=120)
    df_data['Organisation'].value_counts().plot(kind='bar')
    plt.subplots_adjust(bottom=0.35)
    save_and_maybe_show_mpl('01_launches_per_organisation')

    # Number of Active versus Retired Rockets
    plt.figure(figsize=(8, 5), dpi=120)
    df_data['Rocket_Status'].value_counts().plot(kind='bar')
    plt.xticks(rotation=0)
    save_and_maybe_show_mpl('02_rocket_status')

    # Distribution of Mission Status
    plt.figure(figsize=(8, 5), dpi=120)
    df_data['Mission_Status'].value_counts().plot(kind='bar')
    plt.xticks(rotation=0)
    save_and_maybe_show_mpl('03_mission_status')

    # How Expensive are the Launches?
    histo_price = df_data.dropna(subset=['Price']).copy()
    histo_price['Price'] = histo_price['Price'].astype(float)

    plt.figure(figsize=(8, 5), dpi=120)
    histo_price['Price'].plot(kind='hist', bins=20)
    plt.xlabel('Price in Millions')
    plt.ylabel('Number of Launches')
    plt.xlim(0, 1000)
    save_and_maybe_show_mpl('04_price_histogram')

    # Convert countries in Location to ISO3 in the column Country
    df_data['Country'] = df_data['Location'].apply(lookup_country)

    # Choropleth of the Number of Launches by Country
    country_counts = df_data['Country'].value_counts().reset_index()
    country_counts.columns = ['Country', 'Country_Appear']

    fig = px.choropleth(country_counts, locations='Country', color='Country',
                         scope='world', color_continuous_scale='matter',
                         title='Number of Launches by Country',
                         labels={'Country_Appear': 'Number of Launches'},
                         hover_data=['Country_Appear'])
    save_and_maybe_show_plotly(fig, '05_launches_by_country_choropleth')

    # Sunburst Chart of countries, organisations, and mission status
    filtered_data = df_data.dropna(subset=['Country', 'Organisation', 'Mission_Status'])

    fig = px.sunburst(filtered_data, path=['Country', 'Organisation', 'Mission_Status'],
                       title='Number of Launches by Country, Organisation, and Mission Status',
                       color='Country', color_discrete_sequence=px.colors.sequential.Plasma_r)
    save_and_maybe_show_plotly(fig, '06_country_org_status_sunburst')

    # Total Amount of Money Spent by Organisation on Space Missions
    money_spent_by_organizations = df_data.groupby('Organisation')['Price'].sum().reset_index()

    # Amount of Money Spent by Organisation per Launch
    money_spent_by_organizations['Total_Launches'] = money_spent_by_organizations['Organisation'].map(
        df_data['Organisation'].value_counts()
    )
    money_spent_by_organizations = money_spent_by_organizations[
        (money_spent_by_organizations['Total_Launches'] != 0) &
        (money_spent_by_organizations['Price'] != 0.00)
    ]

    money_spent_by_organizations['Average_Price_Per_Launch'] = (
        money_spent_by_organizations['Price'] / money_spent_by_organizations['Total_Launches']
    )
    print('Spend by organisation:\n', money_spent_by_organizations)

    # Chart the Number of Launches per Year
    df_data['Date'] = pd.to_datetime(df_data['Date'], format='mixed', utc=True)
    df_data['Year'] = df_data['Date'].apply(year)

    plt.figure(figsize=(8, 5), dpi=120)
    df_data['Year'].value_counts().plot(kind='bar')
    plt.xlabel('Year')
    plt.ylabel('Number of Launches')
    xtick_positions = range(len(df_data['Year'].value_counts()))
    xtick_labels = df_data['Year'].value_counts().index.tolist()
    plt.xticks(list(xtick_positions)[::3], xtick_labels[::3], rotation=45)
    plt.subplots_adjust(bottom=0.15)
    save_and_maybe_show_mpl('07_launches_per_year')

    # Chart the Number of Launches Month-on-Month
    df_data['Month'] = df_data['Date'].apply(month)

    plt.figure(figsize=(8, 5), dpi=120)
    df_data['Month'].value_counts().plot(kind='bar')
    plt.xlabel('Month')
    plt.ylabel('Number of Launches')
    plt.xticks(rotation=45)
    plt.subplots_adjust(bottom=0.15)
    save_and_maybe_show_mpl('08_launches_per_month')

    # How has the Launch Price varied Over Time?
    filtered_data = df_data.dropna(subset=['Price'])

    plt.figure(figsize=(8, 5), dpi=120)
    filtered_data.groupby('Year')['Price'].mean().plot(kind='line')
    plt.xlabel('Year')
    plt.ylabel('Average Price ($M)')
    save_and_maybe_show_mpl('09_average_price_over_time')

    top_10_organizations = df_data['Organisation'].value_counts().sort_values(ascending=False).head(10)

    plt.figure(figsize=(8, 5), dpi=120)
    top_10_organizations.plot(kind='bar')
    print('Top 10 organisations by launch count:\n', top_10_organizations)
    plt.xlabel('Organisation')
    plt.ylabel('Number of Launches')
    plt.subplots_adjust(bottom=0.32)
    save_and_maybe_show_mpl('10_top_10_organisations')

    # Number of Launches over Time by the Top 10 Organisations
    filtered_data = df_data.dropna(subset=['Organisation'])
    organization_values = top_10_organizations.index.to_list()
    filtered_data_organization = filtered_data[filtered_data['Organisation'].isin(organization_values)]

    plt.figure(figsize=(8, 5), dpi=120)
    filtered_data_organization.groupby(['Year', 'Organisation'])['Organisation'].count().unstack().plot(kind='line', ax=plt.gca())
    plt.xlabel('Year')
    plt.ylabel('Number of Launches')
    save_and_maybe_show_mpl('11_top_10_organisations_over_time')

    # Cold War Space Race: USA vs USSR
    filtered_data_space_race = filtered_data[filtered_data['Organisation'].isin(['NASA', 'RVSN USSR'])]

    plt.figure(figsize=(8, 5), dpi=120)
    filtered_data_space_race.groupby(['Year', 'Organisation'])['Organisation'].count().unstack().plot(kind='line', ax=plt.gca())
    plt.xlabel('Year')
    plt.ylabel('Number of Launches')
    save_and_maybe_show_mpl('12_usa_vs_ussr_over_time')

    # Pie Chart comparing the total number of launches of the USSR and the USA
    plt.figure(figsize=(8, 5), dpi=120)
    filtered_data_space_race['Organisation'].value_counts().plot(kind='pie', autopct='%1.1f%%', startangle=90)
    save_and_maybe_show_mpl('13_usa_vs_ussr_pie')

    # Total Number of Mission Failures Year on Year
    mission_fails = df_data[df_data['Mission_Status'] == 'Failure']['Year'].value_counts().sort_index()
    plt.figure(figsize=(8, 5))
    mission_fails.plot(kind='bar')
    plt.xlabel('Year')
    plt.ylabel('Number of Mission Failures')
    xtick_positions = range(len(mission_fails))
    xtick_labels = mission_fails.index.tolist()
    plt.xticks(list(xtick_positions)[::3], xtick_labels[::3], rotation=45)
    save_and_maybe_show_mpl('14_mission_failures_per_year')

    # Percentage of Failures over Time
    filtered_data = df_data.dropna(subset=['Mission_Status'])

    plt.figure(figsize=(8, 5), dpi=120)
    filtered_data.groupby('Year')['Mission_Status'].apply(
        lambda x: ((x == 'Failure').sum() / len(x)) * 100
    ).plot(kind='line')
    plt.xlabel('Year')
    plt.ylabel('Percentage of Failures (%)')
    plt.ylim(0, 100)
    save_and_maybe_show_mpl('15_failure_rate_over_time')

    # Number of Launches per Year, sorted
    plt.figure(figsize=(8, 5))
    launches_per_year = df_data['Year'].value_counts().sort_index()
    launches_per_year.plot(kind='bar')
    plt.xlabel('Year')
    plt.ylabel('Number of Launches')
    xtick_positions = range(len(df_data['Year'].value_counts()))
    xtick_labels = sorted(df_data['Year'].value_counts().index.tolist())
    plt.xticks(list(xtick_positions)[::3], xtick_labels[::3], rotation=45)
    plt.subplots_adjust(bottom=0.15)
    save_and_maybe_show_mpl('16_launches_per_year_sorted')

    # Year-on-Year Chart Showing the Organisation Doing the Most Launches
    plt.figure(figsize=(8, 5), dpi=120)
    filtered_data.groupby(['Year', 'Organisation'])['Organisation'].count().unstack().plot(kind='line', ax=plt.gca())
    plt.xlabel('Year')
    plt.ylabel('Number of Launches')
    save_and_maybe_show_mpl('17_organisation_leader_by_year')

    print(f'\nDone. {len(os.listdir(OUTPUT_DIR))} chart files written to {OUTPUT_DIR}')


if __name__ == '__main__':
    main()
