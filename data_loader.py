"""
Shared data loading for the interactive dashboard (app.py).

Mirrors the cleaning and derivation steps in space_race_analysis.py exactly:
drop duplicate rows, drop the two scrape-artifact columns (`Unnamed: 0`,
`Unnamed: 0.1`), derive `Country` from `Location` via pycountry, and derive
`Year`/`Month` from `Date` with pandas' mixed-format parser. Doing this once
here (instead of duplicating it inside app.py) keeps the dashboard's numbers
identical to the static charts by construction.

This module only loads and cleans; it does not change or recompute any of
the underlying analysis. space_race_analysis.py is untouched and still does
its own loading inline (it also prints exploratory NaN/duplicate counts
*before* cleaning, which this shared loader intentionally skips since the
dashboard only needs the final cleaned frame).
"""
import os

import pandas as pd
import pycountry

MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September',
          'October', 'November', 'December']

BASE_PATH = os.path.abspath(os.path.dirname(__file__))
CSV_PATH = os.path.join(BASE_PATH, 'mission_launches.csv')


def lookup_country(location):
    """Map a free-text 'City, Country' location string to an ISO alpha-3 code."""
    try:
        location = location.split(',')[-1].strip()
        return pycountry.countries.lookup(location).alpha_3
    except LookupError:
        return None


def country_name(alpha3):
    """Map an ISO alpha-3 code back to a human-readable country name for the UI."""
    try:
        return pycountry.countries.get(alpha_3=alpha3).name
    except AttributeError:
        return alpha3


def load_data(csv_path=CSV_PATH):
    """Load and clean mission_launches.csv, returning the same rows/values
    space_race_analysis.py operates on (4,324 launches, 56 organisations)."""
    df = pd.read_csv(csv_path)
    df.drop_duplicates(inplace=True)
    df.drop(columns=['Unnamed: 0', 'Unnamed: 0.1'], inplace=True)
    df['Country'] = df['Location'].apply(lookup_country)
    df['Date'] = pd.to_datetime(df['Date'], format='mixed', utc=True)
    df['Year'] = df['Date'].dt.year
    df['Month'] = df['Date'].dt.month.apply(lambda m: MONTHS[m - 1])
    return df
