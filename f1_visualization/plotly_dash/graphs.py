"""Produce Plotly graphs to be inserted with callbacks."""

from math import ceil
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import tomli
from plotly.subplots import make_subplots

from f1_visualization.visualization import _find_sc_laps, pick_driver_color

with open(Path(__file__).absolute().parent / "visualization_config.toml", "rb") as toml:
    VISUAL_CONFIG = tomli.load(toml)


def _plot_args() -> tuple:
    """
    Get plotting arguments based on the season and compound type.

    Returns:
        (hue, palette, marker, labels)
    """
    return (
        "Compound",
        VISUAL_CONFIG["relative"]["palette"],
        VISUAL_CONFIG["relative"]["markers"],
        VISUAL_CONFIG["relative"]["labels"],
    )


def shade_sc_periods(fig: go.Figure, sc_laps: np.ndarray, vsc_laps: np.ndarray):
    """Shade SC and VSC periods."""
    sc_laps = np.append(sc_laps, [-1])
    vsc_laps = np.append(vsc_laps, [-1])

    def plot_periods(laps):
        start = 0
        end = 1

        while end < len(laps):
            # check if the current SC period is still ongoing
            if laps[end] == laps[end - 1] + 1:
                end += 1
            else:
                if end - start > 1:
                    # the latest SC period lasts for more than one lap
                    fig.add_vrect(
                        x0=laps[start] - 1,
                        x1=laps[end - 1] - 1,
                        opacity=0.5,
                        fillcolor="yellow",
                        annotation_text="SC",
                        annotation_position="top",
                        annotation={"font_size": 20, "font_color": "black"},
                    )
                else:
                    # end = start + 1, the latest SC period lasts only one lap
                    fig.add_vrect(
                        x0=laps[start] - 1,
                        x1=laps[end - 1] - 1,
                        opacity=0.5,
                        fillcolor="yellow",
                        annotation_text="VSC",
                        annotation_position="top",
                        annotation={"font_size": 20, "font_color": "black"},
                    )
                start = end
                end += 1

    plot_periods(sc_laps)
    plot_periods(vsc_laps)
    return fig


def strategy_barplot(
    included_laps: pd.DataFrame,
    drivers: list[str],
) -> go.Figure:
    """Make horizontal stacked barplot of driver strategies."""
    fig = go.Figure()

    driver_stints = (
        included_laps[["Driver", "Stint", "Compound", "CompoundName", "FreshTyre", "LapNumber"]]
        .groupby(["Driver", "Stint", "Compound", "CompoundName", "FreshTyre"])
        .count()
        .reset_index()
    )
    driver_stints = driver_stints.rename(columns={"LapNumber": "StintLength"})
    driver_stints = driver_stints.sort_values(by=["Stint"])

    args = _plot_args()

    # plotly puts the first trace at the bottom
    # so we need to reverse the list of the drivers to get them ordered by finishing position
    for driver in reversed(drivers):
        stints = driver_stints.loc[driver_stints["Driver"] == driver]
        stint_num = 1
        for _, stint in stints.iterrows():
            fig.add_trace(
                go.Bar(
                    y=[driver],
                    x=[stint["StintLength"]],
                    orientation="h",
                    marker={"color": args[1][stint[args[0]]]},
                    marker_pattern_shape=VISUAL_CONFIG["fresh"]["hatch"][stint["FreshTyre"]],
                    name=f"{driver} stint {stint_num}",
                )
            )
            stint_num += 1

    num_laps = included_laps["LapNumber"].max()
    fig = shade_sc_periods(fig, *_find_sc_laps(included_laps))
    fig.update_layout(
        barmode="stack",
        template="plotly_dark",
        xaxis={
            "tickmode": "array",
            "tickvals": list(range(5, num_laps, 5)),
            "title": "Lap Number",
        },
        yaxis={"type": "category"},
        showlegend=False,
        autosize=False,
        width=1250,
        height=max(300, 50 * len(drivers)),
    )
    return fig


def stats_scatterplot(
    included_laps: pd.DataFrame,
    drivers: list[str],
    y: str,
) -> go.Figure:
    """Make scatterplots showing a statistic, one subplot for each driver."""
    args = _plot_args()

    # LapRep columns have outliers that can skew the graph y-axis
    # The high outlier values are filtered by upper_bound
    # Using a lower bound of -5 on PctFromLapRep will retain 95+% of all laps
    if y in {"PctFromLapRep", "DeltaToLapRep"}:
        included_laps = included_laps[included_laps["PctFromLapRep"] > -5]

    num_row = ceil(len(drivers) / 4)
    num_col = len(drivers) if len(drivers) < 4 else 4
    fig = make_subplots(
        rows=num_row,
        cols=num_col,
        horizontal_spacing=0.1 / num_row,
        vertical_spacing=0.1 / num_col,
        shared_xaxes="all",
        shared_yaxes="all",
        subplot_titles=drivers,
        x_title="Lap Number",
        y_title=y,
    )

    for index, driver in enumerate(drivers):
        driver_laps = included_laps[(included_laps["Driver"] == driver)]

        # the top left subplot is indexed (1, 1)
        row, col = divmod(index, 4)
        row += 1
        col += 1

        fig.add_trace(
            go.Scatter(
                x=driver_laps["LapNumber"],
                y=driver_laps[y],
                mode="markers",
                marker={
                    "color": driver_laps[args[0]].map(args[1]),
                    "symbol": driver_laps["FreshTyre"].map(VISUAL_CONFIG["fresh"]["markers"]),
                },
                name=driver,
            ),
            row=row,
            col=col,
        )

    fig.update_layout(
        template="plotly_dark",
        showlegend=False,
        autosize=False,
        width=1250,
        height=400 if num_row == 1 else (300 * num_row),
    )
    return fig


def stats_lineplot(
    included_laps: pd.DataFrame, drivers: list[str], y: str, upper_bound: int
) -> go.Figure:
    """Make lineplots showing a statistic."""
    # Identify SC and VSC laps before filtering for upper bound
    sc_laps, vsc_laps = _find_sc_laps(included_laps)

    # keep all laps if y is position to eliminate any implicit gaps
    if y != "Position":
        included_laps = included_laps[included_laps["PctFromFastest"] <= (upper_bound - 100)]

    fig = go.Figure()

    # LapRep columns have outliers that can skew the graph y-axis
    # The high outlier values are filtered by upper_bound
    # Using a lower bound of -5 on PctFromLapRep will retain 95+% of all laps
    if y in {"PctFromLapRep", "DeltaToLapRep"}:
        included_laps = included_laps[included_laps["PctFromLapRep"] > -5]

    for _, driver in enumerate(reversed(drivers)):
        driver_laps = included_laps[(included_laps["Driver"] == driver)]

        fig.add_trace(
            go.Scatter(
                x=driver_laps["LapNumber"],
                y=driver_laps[y],
                mode="lines",
                line={"color": pick_driver_color(driver)},
                name=driver,
            )
        )

    fig = shade_sc_periods(fig, sc_laps, vsc_laps)
    if y == "Position":
        fig.update_yaxes(autorange="reversed")

    num_laps = included_laps["LapNumber"].max()
    fig.update_layout(
        template="plotly_dark",
        xaxis={
            "tickmode": "array",
            "tickvals": list(range(5, num_laps, 5)),
            "title": "Lap Number",
        },
        yaxis_title=y,
        autosize=False,
        width=1250,
        height=max(50 * len(drivers), 500),
        legend_traceorder="reversed",
    )
    return fig


def stats_distplot(
    included_laps: pd.DataFrame,
    drivers: list[str],
    boxplot: bool,
) -> go.Figure:
    """Make distribution plot of lap times, either as boxplot or as violin plot."""
    fig = go.Figure()

    for driver in drivers:
        driver_laps = included_laps[included_laps["Driver"] == driver]
        if boxplot:
            fig.add_trace(
                go.Box(
                    y=driver_laps["LapTime"],
                    boxmean=True,
                    boxpoints="outliers",
                    pointpos=0,
                    fillcolor=pick_driver_color(driver),
                    line={"color": "dimgray"},
                    name=driver,
                    showwhiskers=True,
                )
            )
        else:
            fig.add_trace(
                go.Violin(
                    y=driver_laps["LapTime"],
                    fillcolor=pick_driver_color(driver),
                    line={"color": pick_driver_color(driver)},
                    name=driver,
                    opacity=1,
                )
            )

    fig.update_layout(
        template="plotly_dark",
        xaxis_title="Driver",
        yaxis_title="Lap Time (s)",
        showlegend=False,
        autosize=False,
        width=1250,
        height=500,
    )
    return fig


def compounds_lineplot(included_laps: pd.DataFrame, y: str, compounds: list[str]) -> go.Figure:
    """Plot compound degradation curve as a lineplot."""
    fig = go.Figure()
    yaxis_title = "Seconds to LRT" if y == "DeltaToLapRep" else "Percent from LRT"

    # TODO: remove this hard-coded value
    _, palette, marker, _ = _plot_args(2024)

    for compound in compounds:
        compound_laps = included_laps[included_laps["Compound"] == compound]
        # clip tyre life range to where there are at least three records
        tyre_life_range = compound_laps.groupby("TyreLife").size()
        tyre_life_range = tyre_life_range[tyre_life_range >= 3].index
        median_LRT = compound_laps.groupby("TyreLife")[y].median(numeric_only=True)  # noqa: N806
        median_LRT = median_LRT.loc[tyre_life_range]  # noqa: N806

        fig.add_trace(
            go.Scatter(
                x=tyre_life_range,
                y=median_LRT,
                line={"color": palette[compound]},
                marker={
                    # TODO: tune these parameters
                    "line": {"width": 1, "color": "white"},
                    "color": palette[compound],
                    "symbol": marker[compound],
                    "size": 8,
                },
                mode="lines+markers",
                name=compound,
            )
        )

    fig.update_layout(
        template="plotly_dark",
        xaxis_title="Tyre Age",
        yaxis_title=yaxis_title,
        showlegend=False,
        autosize=False,
        width=1250,
        height=500,
    )
    return fig


def compounds_distplot(
    included_laps: pd.DataFrame, y: str, compounds: list[str], violin_plot: bool
) -> go.Figure:
    """PLot compound performance vs tyre age as either a boxplot or violin plot."""
    fig = go.Figure()
    yaxis_title = "Seconds to LRT" if y == "DeltaToLapRep" else "Percent from LRT"

    fig.update_layout(
        template="plotly_dark",
        xaxis_title="Tyre Age",
        yaxis_title=yaxis_title,
        showlegend=False,
        autosize=False,
        width=1250,
        height=500,
    )
    return fig
