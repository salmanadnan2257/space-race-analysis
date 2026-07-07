# Space Race Analysis

A data analysis script that explores every space mission launch on record from
the start of the Space Race in 1957 through 2020: 4,324 launches by 56
organisations, cleaned and turned into 17 charts covering launch counts,
cost, geography, and the Cold War rivalry between the USA and the USSR.

## Why it exists

Raw launch logs answer "what happened" one row at a time. This script turns
those rows into answers to the questions people actually ask about the
history of spaceflight: who launches the most, what does a launch cost, has
launching gotten safer over time, and how did the USA and USSR compare during
the Cold War. It's a self-contained example of taking a scraped, messy CSV to
a full descriptive analysis with reproducible charts.

## Features

- Data cleaning: drops duplicate rows and two junk index columns left over
  from the scrape (`Unnamed: 0`, `Unnamed: 0.1`).
- Country extraction: parses the free-text `Location` field ("LC-39A, Kennedy
  Space Center, Florida, USA") down to an ISO alpha-3 country code via
  `pycountry`, with graceful fallback (`None`) for locations it can't match
  (mostly defunct entities like the former USSR launch sites under a country
  name that no longer exists in ISO's list).
- 17 charts in total: bar charts (launches per organisation, per year, per
  month, rocket status, mission status, failures per year), a price
  histogram, line charts (average price over time, top 10 organisations'
  launch cadence over time, USA vs USSR launches over time, failure rate over
  time), a pie chart (USA vs USSR launch share), and two interactive Plotly
  charts (a world choropleth of launches by country, a sunburst of
  country -> organisation -> mission status).
- Every chart is written to `output/` (PNG for matplotlib, HTML for Plotly)
  so the analysis is reproducible without a display; set `SHOW_PLOTS=1` to
  also pop up each chart interactively.
- Spend analysis: total and average price per launch by organisation, for the
  25 organisations that report both launch counts and a non-zero price
  (most organisations in the dataset never disclose a price, so this is
  necessarily a partial view, see Challenges below).
- An interactive Flask dashboard (`app.py`) on top of the same cleaned data:
  filter by organisation, country, and launch-year range and watch five
  charts update live, no page reload, no precomputed combinations. It
  includes a real hover/zoom/click-to-drill-down choropleth and sunburst, not
  static images. See "Interactive dashboard" under Usage.

## Architecture

Single script, `space_race_analysis.py`, structured as:

1. Load `mission_launches.csv` (path resolved relative to the script's own
   location, so it works from any working directory).
2. Clean: drop duplicates and the two scrape artifact columns.
3. Explore: shape, dtypes, null counts, `describe()`.
4. Derive columns: `Country` (from `Location`), `Year` and `Month` (from
   `Date`, parsed with pandas' mixed-format datetime parser since the source
   dates aren't in one consistent format).
5. Produce and save each chart in turn via two small helpers,
   `save_and_maybe_show_mpl` and `save_and_maybe_show_plotly`, that write to
   `output/` and only call `plt.show()` / `fig.show()` when `SHOW_PLOTS=1` is
   set (keeps the script runnable in CI / headless environments without a
   display or a browser).

No classes, no config file: it's a linear analysis script, which matches
what it's for (a one-shot exploratory report, not a service).

On top of that, three more files make up the interactive dashboard:

- `data_loader.py`: the same cleaning and derivation steps as
  `space_race_analysis.py` (drop duplicates, drop the two scrape-artifact
  columns, derive `Country`/`Year`/`Month`), factored into one function,
  `load_data()`, so the dashboard's numbers are identical to the static
  charts by construction. `space_race_analysis.py` itself is untouched and
  still loads and cleans inline (it also prints exploratory NaN/duplicate
  counts before cleaning, which the shared loader intentionally skips since
  the dashboard only needs the final cleaned frame).
- `app.py`: a Flask app that loads the cleaned data once at startup, then
  on every request re-slices the real in-memory dataframe by whatever
  organisations/countries/year range were selected. `/` renders the initial
  unfiltered page (org bar, year line, mission-status bar, choropleth,
  sunburst, all as embedded Plotly figures); `/api/filter` is a JSON POST
  endpoint that takes the current filter selection, filters the dataframe,
  rebuilds all five figures and the summary stats from that filtered slice,
  and returns them as JSON. Nothing is precomputed per filter combination,
  every response is a fresh `pandas` slice and a fresh Plotly figure.
- `templates/index.html`: the page itself. Plotly.js renders the five
  charts client-side; a small amount of vanilla JS reads the filter
  controls, posts to `/api/filter`, and calls `Plotly.react` to update the
  existing charts in place (no reload, no re-fetch of the whole page).

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

No environment variables are required for the analysis itself. `SHOW_PLOTS`
is an optional toggle (see Usage), not a secret, so no `.env.example` is
included.

## Usage

```bash
python space_race_analysis.py
```

Prints the cleaning/exploration steps and the per-organisation spend table to
stdout, and writes 17 chart files into `output/` (15 PNGs, 2 HTMLs). To also
open each chart interactively as it's produced (needs a display for
matplotlib and a browser for the Plotly charts):

```bash
SHOW_PLOTS=1 python space_race_analysis.py
```

`output/` in this repo already contains one verified run's charts as a
sample of what the script produces; rerunning overwrites them.

### Interactive dashboard

```bash
python app.py
```

Opens a Flask server at `http://127.0.0.1:5000/`. The page loads with all
4,324 launches shown across five charts (launches per organisation, launches
per year, mission status breakdown, a world choropleth, and a country ->
organisation -> mission status sunburst). Two multi-select boxes
(organisations, countries) and a year-range pair of inputs let you narrow the
view; hitting "Apply filters" re-slices the real dataset and updates every
chart in place. Three shortcut buttons are included: "Reset" (back to
everything), "USA vs USSR (1957-1991)" (NASA + RVSN USSR, Cold War years),
and "Top 10 organisations" (the 10 organisations with the most launches,
computed from the real counts, not hardcoded). This is a second, interactive
way to explore the same data the static script produces; it doesn't replace
`python space_race_analysis.py`, which still writes the 17 static charts to
`output/` unchanged.

## Challenges

- **`value_counts().reset_index()` column-naming trap.** The original
  version of this script built a `Total_Launches` column with
  `df['Organisation'].value_counts().reset_index()['Organisation']`. In
  current pandas, `reset_index()` on a named `value_counts()` result yields
  columns `['Organisation', 'count']`, so that line silently pulled the
  *organisation names* (strings) into a column meant to hold launch counts.
  It didn't fail until much later, dividing `Price` by `Total_Launches` to
  get an average, which threw `TypeError: unsupported operand type(s) for /:
  'float' and 'str'`. Fixed by mapping counts back onto each row explicitly:
  `money_spent_by_organizations['Organisation'].map(df_data['Organisation'].value_counts())`,
  which is correct regardless of how `value_counts()` names its output
  column in a given pandas version.
- **Inconsistent date formats.** `Date` mixes at least two string formats
  across the scrape (some rows include a UTC offset, others don't; some are
  missing the day-of-week prefix). `pd.to_datetime` with a fixed `format`
  string threw parse errors on a subset of rows; switched to
  `format='mixed', utc=True` so pandas infers the format per row instead of
  assuming one format for the whole column.
- **Country lookup is lossy.** `pycountry.countries.lookup()` only knows
  current ISO country names. A meaningful number of `Location` strings
  reference launch sites in the former USSR, or use informal names, so
  `lookup_country` deliberately returns `None` on a `LookupError` rather than
  crashing, and the choropleth and sunburst charts silently drop those rows
  (`dropna(subset=['Country', ...])`). This means the country-level charts
  undercount USSR-era launches; the year/organisation-level charts do not
  have this problem since they don't depend on the country mapping.
  Documented here rather than hidden, since it directly affects how the
  choropleth should be read.
- **Non-interactive rendering in headless environments.** `plt.show()` on a
  script with no display just warns and silently does nothing (harmless
  locally, but useless for verifying the script actually produces charts).
  For Plotly, `fig.show()` in a plain terminal (no Jupyter, no IPython)
  raises `ValueError: Mime type rendering requires ipython but it is not
  installed` instead of falling back gracefully. Fixed by always saving each
  chart to `output/` (`savefig` / `write_html`) and making the interactive
  popup an opt-in (`SHOW_PLOTS=1`), which is also what let this analysis be
  verified end to end without a GUI.
- **Sparse `Price` column.** Only 964 of 4,324 launches (about 22%) have a
  reported price; the rest are `NaN`. Every price-based chart and the spend
  table explicitly drops the missing rows first (`dropna(subset=['Price'])`)
  rather than treating missing as zero, which would have understated average
  prices and made cheap-looking organisations that just don't report cost.
- **Getting filtered Plotly figures from server to browser.** The dashboard
  needed to send a fresh Plotly figure to the browser on every filter
  change without a full page reload. `fig.to_html()` (used for the static
  Plotly outputs) embeds a full HTML document, not something you can hand to
  an already-running `Plotly.react()` call. Used
  `json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)` instead, which
  serializes the figure's `data`/`layout` to plain JSON (handles numpy
  types, which a bare `json.dumps` chokes on); the page then calls
  `Plotly.newPlot` once on load and `Plotly.react` on every filter change
  with that JSON, updating the existing chart in place.

## What I learned

- `Series.value_counts().reset_index()` is not stable across pandas
  versions in what it names its columns, in older pandas the count column
  took the name of the original series and the index became a column called
  `index`; current pandas names the index column after the series and the
  values column `count`. Code that assumes one or the other breaks silently
  (wrong values, not an exception) rather than loudly, which makes it worse
  than a typical breaking change. Mapping explicitly by key
  (`.map(other_series)`) sidesteps the whole issue.
- Mixed-format date columns from web scrapes are common enough that
  `pd.to_datetime(..., format='mixed')` is worth reaching for by default
  instead of trying to guess a single `strftime` format that will match
  every row.
- A script that only calls `plt.show()` / `fig.show()` has no way to prove
  it worked outside of a human watching a screen. Writing every figure to
  disk first makes "did this actually run" a `ls output/` away instead of a
  judgment call.
- Server-side filtering plus `Plotly.react` on the client is a small amount
  of code for a genuinely different feel than a static chart: the same 15
  countries and 56 organisations, but you can ask "what did just NASA and
  RVSN USSR look like before 1992" and see the real 1,876-launch answer
  (111 NASA, 1,765 RVSN USSR) instead of reading it off a fixed image.

## What I'd do differently

- I'd validate the `Price` column type at load time (`pd.to_numeric` with
  `errors='coerce'`) instead of relying on `dropna` plus an implicit cast
  later; it works here because the CSV happens to be clean, but it's fragile
  against a re-scrape.
- I'd move the country-code lookup to a small cached dictionary keyed on the
  raw `Location` string instead of calling `pycountry.countries.lookup()`
  per row; on 4,324 rows it's fast enough not to matter, but it doesn't
  scale and it's the kind of thing that's cheap to fix once and easy to
  forget.
- The dashboard has no price filter or price chart, even though the static
  script's price histogram and spend-by-organisation table are some of the
  more interesting analysis; I'd add a price range slider and a filtered
  price histogram/spend table if I extended this further, gated on the
  usual sparse-`Price` caveat (only ~22% of launches report one).
- I'd split this into a couple of functions (load/clean, then one function
  per chart group) instead of one long `main()`. It reads fine top to bottom
  right now precisely because it's linear, but that also means there's no
  way to regenerate a single chart without rerunning everything, and no way
  to unit test the cleaning step in isolation.
- I'd add a couple of basic assertions after cleaning (e.g. no duplicate
  rows remain, `Price` is numeric where present) so a bad rerun on updated
  data fails fast with a clear message instead of producing a subtly wrong
  chart, which is exactly what the `Total_Launches` bug above did until it
  happened to hit a type error downstream.

## Notes

This started as an exercise notebook template (`Space_Missions_Analysis_(start).ipynb`
in the original course material) with the analysis code cells left blank; the
actual completed analysis was written as this standalone script instead of
filling in the notebook, so the notebook itself isn't included here since it
carries no completed work. `mission_launches.csv` (scraped from
nextspaceflight.com) ships with this repo since the script needs it and it's
small enough to include directly; regenerating it would require re-scraping
the source site.
