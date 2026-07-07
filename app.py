"""
Interactive dashboard for the space race analysis.

Loads the same cleaned 4,324-launch / 56-organisation dataset that
space_race_analysis.py produces (via data_loader.load_data, which mirrors
its cleaning steps exactly) and serves it behind a small Flask app with
filters for organisation, country, and launch-year range. Every chart
updates live from the filtered data:

  1. Launches per organisation (bar, top 15 of whatever is selected).
  2. Launches per year (line).
  3. Mission status breakdown (bar): Success / Failure / Partial Failure /
     Prelaunch Failure.
  4. A world choropleth of launches by country, real hover + zoom.
  5. A sunburst of country -> organisation -> mission status, click to
     drill down.

Filtering happens via `/api/filter`, a JSON endpoint that takes the current
filter selection, re-slices the real dataframe, and returns fresh Plotly
figures (as JSON, `fig.to_plotly_json()`) plus recomputed summary stats.
The page calls it on every filter change and re-renders in place with
`Plotly.react`, so a filtered view (say, just NASA and RVSN USSR, 1957 to
1991) is the same numbers you'd get slicing the CSV directly, just live.

Run with `python app.py` and open http://127.0.0.1:5000/.

The original `python space_race_analysis.py` is unchanged and still writes
its 17 static charts to output/; this app is an additional, interactive way
to explore the same data, not a replacement for it.
"""
import json

import plotly.express as px
import plotly.graph_objects as go
import plotly.utils
from flask import Flask, jsonify, render_template, request

from data_loader import country_name, load_data

app = Flask(__name__)

# Load once at startup; reused (and filtered in-memory) by every request.
DF = load_data()

ALL_ORGANISATIONS = sorted(DF['Organisation'].dropna().unique().tolist())
ALL_COUNTRIES = sorted(
    ({'code': c, 'name': country_name(c)} for c in DF['Country'].dropna().unique()),
    key=lambda x: x['name'],
)
YEAR_MIN = int(DF['Year'].min())
YEAR_MAX = int(DF['Year'].max())

STATUS_ORDER = ['Success', 'Failure', 'Partial Failure', 'Prelaunch Failure']
STATUS_COLORS = {
    'Success': '#22c55e',
    'Failure': '#ef4444',
    'Partial Failure': '#f97316',
    'Prelaunch Failure': '#94a3b8',
}


def apply_filters(organisations, countries, year_start, year_end):
    """Slice the real dataframe by the current filter selection. Empty
    organisation/country lists mean 'no restriction' (show everything)."""
    filtered = DF[(DF['Year'] >= year_start) & (DF['Year'] <= year_end)]
    if organisations:
        filtered = filtered[filtered['Organisation'].isin(organisations)]
    if countries:
        filtered = filtered[filtered['Country'].isin(countries)]
    return filtered


def build_stats(filtered):
    total = len(filtered)
    if total == 0:
        return {
            'total_launches': 0, 'organisations': 0, 'success_rate': None,
            'top_organisation': None, 'top_organisation_count': 0,
            'year_range': None,
        }
    success_rate = round((filtered['Mission_Status'] == 'Success').sum() / total * 100, 1)
    top_counts = filtered['Organisation'].value_counts()
    return {
        'total_launches': int(total),
        'organisations': int(filtered['Organisation'].nunique()),
        'success_rate': success_rate,
        'top_organisation': top_counts.index[0],
        'top_organisation_count': int(top_counts.iloc[0]),
        'year_range': f"{int(filtered['Year'].min())}-{int(filtered['Year'].max())}",
    }


def build_org_bar_figure(filtered):
    counts = filtered['Organisation'].value_counts().head(15)
    fig = go.Figure(go.Bar(
        x=counts.index.tolist(), y=counts.values.tolist(),
        marker_color='#3b82f6',
        hovertemplate='%{x}<br>%{y} launches<extra></extra>',
    ))
    fig.update_layout(
        title='Launches per Organisation (top 15 of current selection)',
        xaxis_title='Organisation', yaxis_title='Number of Launches',
        template='plotly_white', margin=dict(l=50, r=20, t=50, b=100),
        xaxis=dict(tickangle=-45),
    )
    return fig


def build_year_line_figure(filtered):
    counts = filtered['Year'].value_counts().sort_index()
    fig = go.Figure(go.Scatter(
        x=counts.index.tolist(), y=counts.values.tolist(), mode='lines+markers',
        line=dict(color='#8b5cf6'), marker=dict(size=5),
        hovertemplate='%{x}<br>%{y} launches<extra></extra>',
    ))
    fig.update_layout(
        title='Launches per Year (current selection)',
        xaxis_title='Year', yaxis_title='Number of Launches',
        template='plotly_white', margin=dict(l=50, r=20, t=50, b=50),
    )
    return fig


def build_status_figure(filtered):
    counts = filtered['Mission_Status'].value_counts()
    ordered = [s for s in STATUS_ORDER if s in counts.index]
    fig = go.Figure(go.Bar(
        x=ordered, y=[int(counts[s]) for s in ordered],
        marker_color=[STATUS_COLORS[s] for s in ordered],
        hovertemplate='%{x}<br>%{y} launches<extra></extra>',
    ))
    fig.update_layout(
        title='Mission Status Breakdown (current selection)',
        xaxis_title='Mission Status', yaxis_title='Number of Launches',
        template='plotly_white', margin=dict(l=50, r=20, t=50, b=50),
    )
    return fig


def build_choropleth_figure(filtered):
    country_counts = filtered['Country'].dropna().value_counts().reset_index()
    country_counts.columns = ['Country', 'Launches']
    if country_counts.empty:
        fig = go.Figure()
        fig.update_layout(title='Launches by Country (no countries in current selection)')
        return fig
    fig = px.choropleth(
        country_counts, locations='Country', color='Launches',
        scope='world', color_continuous_scale='matter',
        title='Launches by Country (current selection)',
        hover_data=['Launches'],
    )
    fig.update_layout(template='plotly_white', margin=dict(l=10, r=10, t=50, b=10))
    return fig


def build_sunburst_figure(filtered):
    data = filtered.dropna(subset=['Country', 'Organisation', 'Mission_Status'])
    if data.empty:
        fig = go.Figure()
        fig.update_layout(title='Country -> Organisation -> Mission Status (no data in current selection)')
        return fig
    fig = px.sunburst(
        data, path=['Country', 'Organisation', 'Mission_Status'],
        title='Country -> Organisation -> Mission Status (current selection, click to drill down)',
        color='Country', color_discrete_sequence=px.colors.sequential.Plasma_r,
    )
    fig.update_layout(margin=dict(l=10, r=10, t=50, b=10))
    return fig


def figures_for(filtered):
    return {
        'org_bar': json.loads(json.dumps(build_org_bar_figure(filtered), cls=plotly.utils.PlotlyJSONEncoder)),
        'year_line': json.loads(json.dumps(build_year_line_figure(filtered), cls=plotly.utils.PlotlyJSONEncoder)),
        'status_bar': json.loads(json.dumps(build_status_figure(filtered), cls=plotly.utils.PlotlyJSONEncoder)),
        'choropleth': json.loads(json.dumps(build_choropleth_figure(filtered), cls=plotly.utils.PlotlyJSONEncoder)),
        'sunburst': json.loads(json.dumps(build_sunburst_figure(filtered), cls=plotly.utils.PlotlyJSONEncoder)),
    }


TOP_10_ORGANISATIONS = DF['Organisation'].value_counts().head(10).index.tolist()


@app.route('/')
def index():
    figures = figures_for(DF)
    stats = build_stats(DF)
    return render_template(
        'index.html',
        organisations=ALL_ORGANISATIONS,
        countries=ALL_COUNTRIES,
        year_min=YEAR_MIN, year_max=YEAR_MAX,
        figures_json=json.dumps(figures),
        stats=stats,
        top_10_organisations_json=json.dumps(TOP_10_ORGANISATIONS),
    )


@app.route('/api/filter', methods=['POST'])
def api_filter():
    """JSON API: {"organisations": [...], "countries": [...], "year_start": 1957,
    "year_end": 2020} -> {"figures": {...}, "stats": {...}}. Every number
    comes from re-slicing the real dataframe, nothing is precomputed per
    filter combination."""
    payload = request.get_json(silent=True) or {}
    organisations = payload.get('organisations') or []
    countries = payload.get('countries') or []
    try:
        year_start = int(payload.get('year_start', YEAR_MIN))
        year_end = int(payload.get('year_end', YEAR_MAX))
    except (TypeError, ValueError):
        return jsonify({'error': 'year_start/year_end must be integers'}), 400

    filtered = apply_filters(organisations, countries, year_start, year_end)
    return jsonify({
        'figures': figures_for(filtered),
        'stats': build_stats(filtered),
    })


if __name__ == '__main__':
    app.run(debug=False, host='127.0.0.1', port=5000)
