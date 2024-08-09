"""Dash app layout and callbacks."""

from typing import TypeAlias

import dash_bootstrap_components as dbc
import fastf1 as f
import pandas as pd
from dash import Dash, Input, Output, State, callback
from plotly import graph_objects as go

import f1_visualization.plotly_dash.graphs as pg
from f1_visualization._consts import CURRENT_SEASON, SPRINT_FORMATS
from f1_visualization.plotly_dash.layout import app_layout, line_y_options, scatter_y_options
from f1_visualization.visualization import add_gap, get_session_info, load_laps

Session_info: TypeAlias = tuple[int, str, list[str]]

# must not be modified
DF_DICT = load_laps()


def df_convert_timedelta(df: pd.DataFrame) -> pd.DataFrame:
    """
    Assumes df follows transformed_laps schema.

    The pd.Timedelta type is not JSON serializable.
    Columns with this data type need to be dropped or converted.
    """
    timedelta_columns = ["Time", "PitInTime", "PitOutTime"]
    # usually the Time column has no NaT values
    # it is included here for consistency
    df[timedelta_columns] = df[timedelta_columns].fillna(pd.Timedelta(0, unit="ms"))

    for column in timedelta_columns:
        df[column] = df[column].dt.total_seconds()
    return df


def configure_lap_numbers_slider(data: dict) -> tuple[int, list[int], dict[int, str]]:
    """Configure range slider based on the number of laps in a session."""
    if not data:
        return 60, [1, 60], {i: str(i) for i in [1] + list(range(5, 61, 5))}
    df = pd.DataFrame.from_dict(data)
    num_laps = df["LapNumber"].max()

    marks = {i: str(i) for i in [1] + list(range(5, num_laps + 1, 5))}
    return num_laps, [1, num_laps], marks


app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.SANDSTONE],
    title="Armchair Strategist - A F1 Strategy Dashboard",
    update_title="Crunching numbers...",
)
server = app.server
app.layout = app_layout


@callback(
    Output("plotly-warning", "is_open"),
    Input("plotly-warning-toggle", "n_clicks"),
    prevent_initial_call=True,
)
def toggle_plotly_warning(n_clicks: int) -> bool:
    """Toggle the visibility of the Plotly warning."""
    # start with n_clicks = 0 and open
    # so odd n_clicks imply the warning should be closed
    return (n_clicks % 2) != 1


@callback(
    Output("event", "options"),
    Output("event", "value"),
    Output("event-schedule", "data"),
    Input("season", "value"),
    prevent_initial_call=True,
)
def set_event_options(
    season: int | None,
) -> tuple[list[str], None, dict]:
    """Get the names of all events in the selected season."""
    if season is None:
        return [], None, None

    schedule = f.get_event_schedule(season, include_testing=False)

    if season == CURRENT_SEASON:
        # only include events for which we have processed data
        last_round = DF_DICT[CURRENT_SEASON]["R"]["RoundNumber"].max()
        schedule = schedule[schedule["RoundNumber"] <= last_round]

    return (
        list(schedule["EventName"]),
        None,
        schedule.set_index("EventName").to_dict(orient="index"),
    )


@callback(
    Output("session", "options"),
    Output("session", "value"),
    Input("event", "value"),
    State("event-schedule", "data"),
    prevent_initial_call=True,
)
def set_session_options(event: str | None, schedule: dict) -> tuple[list[dict], None]:
    """
    Return the sessions contained in an event.

    Event schedule is passed in as a dictionary with the event names as keys. The values map
    column labels to the corresponding entry.
    """
    if event is None:
        return [], None

    return [
        {"label": "Race", "value": "R"},
        {
            "label": "Sprint",
            "value": "S",
            "disabled": schedule[event]["EventFormat"] not in SPRINT_FORMATS,
        },
    ], None


@callback(
    Output("load-session", "disabled"),
    Input("season", "value"),
    Input("event", "value"),
    Input("session", "value"),
    prevent_initial_call=True,
)
def enable_load_session(season: int | None, event: str | None, session: str | None) -> bool:
    """Toggles load session button on when the previous three fields are filled."""
    return not (season is not None and event is not None and session is not None)


@callback(
    Output("session-info", "data"),
    Input("load-session", "n_clicks"),
    State("season", "value"),
    State("event", "value"),
    State("session", "value"),
    State("teammate-comp", "value"),
    prevent_initial_call=True,
)
def get_session_metadata(
    _: int,  # ignores actual value of n_clicks
    season: int,
    event: str,
    session: str,
    teammate_comp: bool,
) -> tuple[list[str], list, bool, Session_info]:
    """
    Store round number, event name, and the list of drivers into browser cache.

    Can assume that season, event, and session are all set (not None).
    """
    round_number, event_name, drivers = get_session_info(
        season, event, session, teammate_comp=teammate_comp
    )

    return (round_number, event_name, drivers)


@callback(
    Output("laps", "data"),
    Input("load-session", "n_clicks"),
    State("season", "value"),
    State("event", "value"),
    State("session", "value"),
    prevent_initial_call=True,
)
def get_session_laps(
    _: int,  # ignores actual_value of n_clicks
    season: int,
    event: str,
    session: str,
) -> dict:
    """
    Save the laps of the selected session into browser cache.

    Can assume that season, event, and session are all set (not None).
    """
    included_laps = DF_DICT[season][session]
    included_laps = included_laps[included_laps["EventName"] == event]
    included_laps = df_convert_timedelta(included_laps)

    return included_laps.to_dict()


@callback(
    Output("drivers", "options"),
    Output("drivers", "value"),
    Output("drivers", "disabled"),
    Output("gap-drivers", "options"),
    Output("gap-drivers", "value"),
    Output("gap-drivers", "disabled"),
    Input("session-info", "data"),
    prevent_initial_call=True,
)
def set_driver_dropdowns(session_info: Session_info):
    """Configure driver dropdowns."""
    drivers = session_info[2]
    return drivers, drivers, False, drivers, None, False


@callback(
    Output("scatter-y", "options"),
    Output("line-y", "options"),
    Input("laps", "data"),
    prevent_initial_call=True,
)
def set_y_axis_dropdowns(data: dict) -> list[dict[str, str]]:
    """Update y axis options based on the columns in the laps dataframe."""

    def readable_gap_col_name(col: str) -> str:
        """Convert Pandas GapTox column names to the more readable Gap to x."""
        return f"Gap to {col[-3:]} (s)"

    gap_cols = filter(lambda x: x.startswith("Gap"), data.keys())
    gap_col_options = [{"label": readable_gap_col_name(col), "value": col} for col in gap_cols]
    return scatter_y_options.extend(gap_col_options), line_y_options.extend(gap_col_options)


@callback(
    Output("laps", "data", allow_duplicate=True),
    Input("add-gap", "n_clicks"),
    State("gap-drivers", "value"),
    State("laps", "data"),
    running=[
        (Output("gap-drivers", "disabled"), True, False),
        (Output("add-gap", "disabled"), True, False),
        (Output("add-gap", "children"), "Calculating...", "Add Gap"),
        (Output("add-gap", "color"), "warning", "success"),
    ],
    prevent_initial_call=True,
)
def add_gap_to_driver(_: int, drivers: list[str], data: dict) -> dict:
    """Amend the dataframe in cache and add driver gap columns."""
    laps = pd.DataFrame.from_dict(data)
    for driver in drivers:
        if f"GapTo{driver}" not in laps.columns:
            laps = add_gap(driver, laps)

    return laps.to_dict()


@callback(
    Output("lap-numbers-scatter", "max"),
    Output("lap-numbers-scatter", "value"),
    Output("lap-numbers-scatter", "marks"),
    Input("laps", "data"),
)
def set_scatterplot_slider(data: dict) -> tuple[int, list[int], dict[int, str]]:
    """Set up scatterplot tab lap numbers slider."""
    return configure_lap_numbers_slider(data)


@callback(
    Output("lap-numbers-line", "max"),
    Output("lap-numbers-line", "value"),
    Output("lap-numbers-line", "marks"),
    Input("laps", "data"),
)
def set_lineplot_slider(data: dict) -> tuple[int, list[int], dict[int, str]]:
    """Set up lineplot tab lap numbers slider."""
    return configure_lap_numbers_slider(data)


@callback(
    Output("strategy-plot", "figure"),
    Input("drivers", "value"),
    State("laps", "data"),
    State("session-info", "data"),
)
def render_strategy_plot(
    drivers: list[str],
    included_laps: dict,
    session_info: Session_info,
) -> go.Figure:
    """Filter laps and configure strategy plot title."""
    # return empty figure on startup
    if not included_laps or not drivers:
        return go.Figure()

    included_laps = pd.DataFrame.from_dict(included_laps)
    included_laps = included_laps[included_laps["Driver"].isin(drivers)]

    event_name = session_info[1]
    fig = pg.strategy_barplot(included_laps, drivers)
    fig.update_layout(title=event_name)
    return fig


@callback(
    Output("scatterplot", "figure"),
    Input("drivers", "value"),
    Input("scatter-y", "value"),
    Input("upper-bound-scatter", "value"),
    Input("lap-numbers-scatter", "value"),
    State("laps", "data"),
    State("session-info", "data"),
)
def render_scatterplot(
    drivers: list[str],
    y: str,
    upper_bound: float,
    lap_numbers: list[int],
    included_laps: dict,
    session_info: Session_info,
) -> go.Figure:
    """Filter laps and configure scatterplot title."""
    if not included_laps or not drivers:
        return go.Figure()

    minimum, maximum = lap_numbers
    lap_interval = range(minimum, maximum + 1)
    included_laps = pd.DataFrame.from_dict(included_laps)
    included_laps = included_laps[
        (included_laps["Driver"].isin(drivers))
        & (included_laps["PctFromFastest"] < (upper_bound - 100))
        & (included_laps["LapNumber"].isin(lap_interval))
    ]

    fig = pg.stats_scatterplot(included_laps, drivers, y)
    event_name = session_info[1]
    fig.update_layout(title=event_name)

    return fig


@callback(
    Output("lineplot", "figure"),
    Input("drivers", "value"),
    Input("line-y", "value"),
    Input("upper-bound-line", "value"),
    Input("lap-numbers-line", "value"),
    State("laps", "data"),
    State("session-info", "data"),
)
def render_lineplot(
    drivers: list[str],
    y: str,
    upper_bound: float,
    lap_numbers: list[int],
    included_laps: dict,
    session_info: Session_info,
) -> go.Figure:
    """Filter laps and configure lineplot title."""
    if not included_laps or not drivers:
        return go.Figure()

    minimum, maximum = lap_numbers
    lap_interval = range(minimum, maximum + 1)
    included_laps = pd.DataFrame.from_dict(included_laps)

    # upper bound not filtered here because we need to identify SC/VSC laps
    # inside the function
    included_laps = included_laps[
        (included_laps["Driver"].isin(drivers))
        & (included_laps["LapNumber"].isin(lap_interval))
    ]

    fig = pg.stats_lineplot(included_laps, drivers, y, upper_bound)
    event_name = session_info[1]
    fig.update_layout(title=event_name)

    return fig


@callback(
    Output("distplot", "figure"),
    Input("drivers", "value"),
    Input("upper-bound-dist", "value"),
    Input("boxplot", "value"),
    State("laps", "data"),
    State("session-info", "data"),
)
def render_distplot(
    drivers: list[str],
    upper_bound: int,
    boxplot: bool,
    included_laps: dict,
    session_info: Session_info,
) -> go.Figure:
    """Filter laps and render distribution plot."""
    if not included_laps or not drivers:
        return go.Figure()

    included_laps = pd.DataFrame.from_dict(included_laps)
    included_laps = included_laps[
        (included_laps["Driver"].isin(drivers))
        & (included_laps["PctFromFastest"] < (upper_bound - 100))
    ]

    fig = pg.stats_distplot(included_laps, drivers, boxplot)
    event_name = session_info[1]
    fig.update_layout(title=event_name)

    return fig


if __name__ == "__main__":
    # app.run(host="0.0.0.0", port=8000)
    app.run(debug=True)
