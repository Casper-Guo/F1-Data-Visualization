"""Dash app static layout specifications."""

import dash_bootstrap_components as dbc
from dash import dcc, html

from f1_visualization._consts import CURRENT_SEASON


def upper_bound_slider(slider_id: str, **kwargs) -> dcc.Slider:
    """Generate generic slider for setting upper bound."""
    return dcc.Slider(
        min=100,
        max=150,
        marks={i: str(i) for i in range(100, 116, 5)} | {150: "Show All"},
        value=107,
        tooltip={"placement": "top"},
        id=slider_id,
        **kwargs,
    )


def lap_numbers_slider(slider_id: str, **kwargs) -> dcc.RangeSlider:
    """Generate generic range slider for setting lap numbers."""
    return dcc.RangeSlider(
        min=1, step=1, allowCross=False, tooltip={"placement": "bottom"}, id=slider_id, **kwargs
    )


strategy_tab = dbc.Tab(
    dbc.Card(dbc.CardBody(dcc.Loading(dcc.Graph(id="strategy-plot")))), label="strategy"
)

scatterplot_tab = dbc.Tab(
    dbc.Card(
        dbc.CardBody(
            [
                dbc.Row(
                    dcc.Dropdown(
                        options=[
                            {"label": "Lap Time", "value": "LapTime"},
                            {"label": "Seconds to Median", "value": "DeltaToRep"},
                            {"label": "Percent from Median", "value": "PctFromRep"},
                            {"label": "Seconds to Fastest", "value": "DeltaToFastest"},
                            {"label": "Percent from Fastest", "value": "PctFromFastest"},
                            {
                                "label": "Seconds to Adjusted Representative Time",
                                "value": "DeltaToLapRep",
                            },
                            {
                                "label": "Percent from Adjusted Representative Time",
                                "value": "PctFromLapRep",
                            },
                        ],
                        value="LapTime",
                        placeholder="Select the variable to put in y-axis",
                        clearable=False,
                        id="scatter-y",
                    )
                ),
                html.Br(),
                dbc.Row(dcc.Loading(dcc.Graph(id="scatterplot"))),
                html.Br(),
                html.P("Filter out slow laps (default is 107% of the fastest lap):"),
                dbc.Row(upper_bound_slider(slider_id="upper-bound-scatter")),
                html.Br(),
                html.P("Select the range of lap numbers to include:"),
                dbc.Row(lap_numbers_slider(slider_id="lap-numbers-scatter")),
            ]
        )
    ),
    label="scatterplot",
)

lineplot_tab = dbc.Tab(
    dbc.Card(
        dbc.CardBody(
            [
                dbc.Row(
                    dcc.Dropdown(
                        options=[
                            {"label": "Position", "value": "Position"},
                            {"label": "Lap Time", "value": "LapTime"},
                            {"label": "Seconds to Median", "value": "DeltaToRep"},
                            {"label": "Percent from Median", "value": "PctFromRep"},
                            {"label": "Seconds to Fastest", "value": "DeltaToFastest"},
                            {"label": "Percent from Fastest", "value": "PctFromFastest"},
                            {
                                "label": "Seconds to Adjusted Representative Time",
                                "value": "DeltaToLapRep",
                            },
                            {
                                "label": "Percent from Adjusted Representative Time",
                                "value": "PctFromLapRep",
                            },
                        ],
                        value="Position",
                        placeholder="Select the variable to put in y-axis",
                        clearable=False,
                        id="line-y",
                    )
                ),
                html.Br(),
                dbc.Row(dcc.Loading(dcc.Graph(id="lineplot"))),
                html.Br(),
                html.P("Filter out slow laps (default is 107% of the fastest lap):"),
                dbc.Row(upper_bound_slider(slider_id="upper-bound-line")),
                html.Br(),
                html.P("Select the range of lap numbers to include:"),
                dbc.Row(lap_numbers_slider(slider_id="lap-numbers-line")),
            ]
        )
    ),
    label="lineplot",
)

distplot_tab = dbc.Tab(
    dbc.Card(
        dbc.CardBody(
            [
                dbc.Row(
                    dcc.Dropdown(
                        options=[
                            {"label": " Show boxplot", "value": True},
                            {"label": " Show violin plot", "value": False},
                        ],
                        value=True,
                        clearable=False,
                        id="boxplot",
                    )
                ),
                html.Br(),
                dbc.Row(dcc.Loading(dcc.Graph(id="distplot"))),
                html.Br(),
                html.P("Filter out slow laps (default is 107% of the fastest lap):"),
                dbc.Row(upper_bound_slider(slider_id="upper-bound-dist")),
            ]
        )
    ),
    label="Distribution Plot",
)

compound_plot_explanation = dbc.Alert(
    [
        html.H4("Methodology", className="alert-heading"),
        html.P(
            "The metric behind this graph is delta to lap representative time (DLRT). "
            "It is a measure of how good a lap time is compared to other cars on track "
            "at the same time, thus accounting for fuel load and track evolution."
        ),
        html.Hr(),
        html.P(
            "Since this metric is relative, this plot is best used for understanding "
            "how different compounds degrade at different rates."
        ),
    ],
    color="info",
    dismissable=True,
)

compound_plot_caveats = dbc.Alert(
    [
        html.H4("Caveats", className="alert-heading"),
        html.P(
            "The above driver selection does not apply to this plot. "
            "This plot always considers laps driven by all drivers."
        ),
        html.Hr(),
        html.P(
            "Tyre life does not always correspond to stint length. "
            "As the same tyre may have been used in qualifying sessions."
        ),
        html.Hr(),
        html.P("Only compounds that completed at least one sixth of all laps are shown."),
        html.Hr(),
        html.P(
            "For each compound, the range of shown tyre life is limited by "
            "the number of drivers who complete a stint of that length. This is to avoid "
            "the plot being stretched by one driver doing a very long stint."
        ),
    ],
    color="info",
    dismissable=True,
)

compound_plot_tab = dbc.Tab(
    dbc.Card(
        dbc.CardBody(
            [
                compound_plot_explanation,
                compound_plot_caveats,
                html.Br(),
                dbc.Row(
                    [
                        dbc.Col(
                            dcc.Dropdown(
                                options=["lineplot", "boxplot", "violinplot"],
                                value="lineplot",
                                clearable=False,
                                placeholder="Select a plot type",
                                id="compound-type",
                            ),
                            width=6,
                        ),
                        dbc.Col(
                            dcc.Dropdown(
                                options=[
                                    {"label": "Show as seconds", "value": True},
                                    {"label": "Show as percentage", "value": False},
                                ],
                                value=True,
                                clearable=False,
                                placeholder="Select a unit",
                                id="compound-unit",
                            ),
                            width=6,
                        ),
                    ]
                ),
                html.Br(),
                dbc.Row(
                    dcc.Loading(
                        dcc.Dropdown(
                            options=[],
                            value=[],
                            placeholder="Select compounds",
                            disabled=True,
                            multi=True,
                            id="compounds",
                        )
                    )
                ),
                html.Br(),
                dbc.Row(dcc.Loading(dcc.Graph(id="compound-plot"))),
            ]
        )
    ),
    label="Compound Performance Plot",
)

plotly_js_warning = dbc.Toast(
    dcc.Markdown("""
       You should see an empty plot in the tab below. If not:
       * Make sure javascript is enabled
       * Try accessing the page with a different browser
    """),
    id="plotly-warning",
    header="How to fix plots not loading",
)

external_links = dbc.Alert(
    [
        "All data provided by ",
        html.A(
            "FastF1",
            href="https://github.com/theOehrly/Fast-F1",
            className="alert-link",
        ),
        html.Hr(),
        "Feature requests and bug reports etc. are welcome at the ",
        html.A(
            "source repository",
            href="https://github.com/Casper-Guo/Armchair-Strategist",
            className="alert-link",
        ),
    ],
    color="info",
)

app_layout = dbc.Container(
    [
        html.H1("Armchair Strategist"),
        dbc.Row(
            [
                dbc.Col(
                    dcc.Dropdown(
                        options=list(range(CURRENT_SEASON, 2017, -1)),
                        placeholder="Select a season",
                        value=None,
                        id="season",
                    )
                ),
                dbc.Col(
                    dcc.Dropdown(
                        options=[],
                        placeholder="Select a event",
                        value=None,
                        id="event",
                    ),
                ),
                dbc.Col(
                    dcc.Dropdown(
                        options=[],
                        placeholder="Select a session",
                        value=None,
                        id="session",
                    ),
                ),
                dbc.Col(
                    dcc.Dropdown(
                        options=[
                            {"label": "Finishing order", "value": False},
                            {"label": "Teammate side-by-side", "value": True},
                        ],
                        value=False,
                        clearable=False,
                        id="teammate-comp",
                    )
                ),
                dbc.Col(
                    dbc.Button(
                        children="Load Session / Reorder Drivers",
                        n_clicks=0,
                        disabled=True,
                        color="success",
                        id="load-session",
                    )
                ),
                dcc.Store(id="event-schedule"),
                dcc.Store(id="session-info"),
                dcc.Store(id="laps"),
            ],
        ),
        html.Br(),
        dbc.Row(
            dcc.Loading(
                dcc.Dropdown(
                    options=[],
                    value=[],
                    placeholder="Select drivers",
                    disabled=True,
                    multi=True,
                    id="drivers",
                )
            )
        ),
        html.Br(),
        dbc.Row(
            dbc.Col(
                [
                    plotly_js_warning,
                    dbc.Button(
                        "Toggle Instruction",
                        color="primary",
                        id="plotly-warning-toggle",
                    ),
                ],
                width=4,
            )
        ),
        html.Br(),
        dbc.Tabs(
            [strategy_tab, scatterplot_tab, lineplot_tab, distplot_tab, compound_plot_tab]
        ),
        html.Br(),
        dbc.Row(external_links),
    ]
)
