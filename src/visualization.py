"""Plotting functions and other visualization helpers."""

import logging
from math import ceil
from typing import Callable, Iterable, Literal, Optional, TypeAlias

import fastf1 as f
import fastf1.plotting as p
import matplotlib
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib import pyplot as plt
from matplotlib import rcParams

# fmt: off
from preprocess import (
    COMPOUND_SELECTION,
    DATA_PATH,
    SESSION_IDS,
    SESSION_NAMES,
    VISUAL_CONFIG,
    Session,
)

# fmt: on

logging.basicConfig(level=logging.INFO, format="%(levelname)s\t%(filename)s\t%(message)s")

Figure: TypeAlias = matplotlib.figure.Figure


def _correct_dtype(df_laps: pd.DataFrame) -> pd.DataFrame:
    """
    Fix incorrectly parsed data types.

    All timing data are cast to timedelta from string.
    `TrackStatus` is cast to string from int.
    `FreshTyre` has its missing values filled with UNKNOWN and then cast to string.

    Requires:
        df_laps has the following columns: [`Time`,
                                            `PitInTime`,
                                            `PitOutTime`,
                                            "TrackStatus`,
                                            `FreshTyre`]
    """
    # convert from object (string) to timedelta
    df_laps[["Time", "PitInTime", "PitOutTime"]] = df_laps[
        ["Time", "PitInTime", "PitOutTime"]
    ].apply(pd.to_timedelta)

    # TrackStatus column makes more sense as strings
    df_laps["TrackStatus"] = df_laps["TrackStatus"].astype(str)
    df_laps["TrackStatus"] = df_laps["TrackStatus"].apply(lambda x: x.rstrip(".0"))

    # Fill FreshTyre column NAs with "Unknown"
    # Then cast to string
    # This ensures rows with missing FreshTyre entry will still be plotted
    df_laps["FreshTyre"] = df_laps["FreshTyre"].fillna("Unknown")
    df_laps["FreshTyre"] = df_laps["FreshTyre"].astype(str)

    return df_laps


def load_laps() -> dict[int, dict[str, pd.DataFrame]]:
    """Load transformed data by season."""
    dfs = {}

    for file in DATA_PATH.glob("**/transformed_*.csv"):
        season = int(file.stem.split("_")[-1])
        session_type = SESSION_NAMES[file.parent.name]
        df = pd.read_csv(
            file,
            header=0,
            true_values=["True"],
            false_values=["False"],
        )
        _correct_dtype(df)

        if season not in dfs:
            dfs[season] = {}

        dfs[season][session_type] = df

    return dfs


DF_DICT = load_laps()


def _find_legend_order(labels: Iterable[str]) -> list[int]:
    """
    Provide the index of a list of compounds sorted from soft to hard.

    Args:
        labels: A list of string representing the tyre compounds.

    Returns:
        A list of ints corresponding to the original index of the
        compound names if they were in sorted order (softest to hardest,
        slick compounds first).

    Examples:
        labels = ["MEDIUM", "HARD", "SOFT"]
        desired = ["SOFT", "MEDIUM", "HARD"]
        return [2, 0, 1]

        labels = ["C3", "C1", "WET"]
        desired = ["C1", "C3", "WET"],
        return [1, 0, 2]
    """
    old_indices = list(range(len(labels)))
    sorted_labels = []

    if any(name in labels for name in ("HYPERSOFT", "ULTRASOFT", "SUPERSOFT", "SUPERHARD")):
        # 2018 absolute compound names
        sorted_labels = VISUAL_CONFIG["absolute"]["labels"]["18"]
    elif any(label.startswith("C") for label in labels):
        # 19_22 absolute compound names
        sorted_labels = VISUAL_CONFIG["absolute"]["labels"]["19_22"]
    else:
        # default to relative names
        sorted_labels = VISUAL_CONFIG["relative"]["labels"]

    pos = [sorted_labels.index(label) for label in labels]

    return [old_index for _, old_index in sorted(zip(pos, old_indices))]


def _filter_round_driver(
    df_laps: pd.DataFrame, round_number: int, drivers: Iterable[str]
) -> pd.DataFrame:
    """
    Filter dataframe by round number and drivers.

    Round number requires exact match.

    Requires:
        df_laps has the following columns: [`RoundNumber`, `Driver`]
    """
    return df_laps[(df_laps["RoundNumber"] == round_number) & (df_laps["Driver"].isin(drivers))]


def _filter_round_driver_upper(
    df_laps: pd.DataFrame,
    round_number: int,
    drivers: Iterable[str],
    upper_bound: int | float,
) -> pd.DataFrame:
    """
    Filter dataframe by round number, drivers, and lap time upper bound.

    Round number requires exact match.
    Upper bound is given as the percentage difference from the fastest lap.

    Requires:
        df_laps has the following columnds: [`RoundNumber`, `Driver`, `PctFromFastest`]
    """
    return df_laps[
        (df_laps["RoundNumber"] == round_number)
        & (df_laps["Driver"].isin(drivers))
        & (df_laps["PctFromFastest"] < upper_bound)
    ]


def _filter_round_compound_valid_upper(
    df_laps: pd.DataFrame,
    round_number: int,
    compounds: Iterable[str],
    upper_bound: int | float,
) -> pd.DataFrame:
    """
    Filter dataframe by round number, validity, compound names, and lap time upper bound.

    Round number requires exact match.

    Requires:
        df_laps has the following columns: [`RoundNumber`,
                                            `IsValid`,
                                            `Compound`,
                                            `PctFromFastest`]
    """
    return df_laps[
        (df_laps["RoundNumber"] == round_number)
        & (df_laps["IsValid"])
        & (df_laps["Compound"].isin(compounds))
        & (df_laps["PctFromFastest"] < upper_bound)
    ]


def _plot_args(season: int, absolute_compound: bool) -> tuple:
    """
    Get plotting arguments based on the season and compound type.

    Args:
        season: Championship season

        absolute_compound: If true, use absolute compound names
                           (C1, C2 ...) in legend
                           Else, use relative compound names
                           (SOFT, MEDIUM, HARD) in legend

    Returns:
        (hue, palette, marker, labels)
    """
    # TODO: this depends on the assumption that the C0 compound is not used
    if absolute_compound:
        if season == 2018:
            return (
                "CompoundName",
                VISUAL_CONFIG["absolute"]["palette"]["18"],
                VISUAL_CONFIG["absolute"]["markers"]["18"],
                VISUAL_CONFIG["absolute"]["labels"]["18"],
            )
        return (
            "CompoundName",
            VISUAL_CONFIG["absolute"]["palette"]["19_22"],
            VISUAL_CONFIG["absolute"]["markers"]["19_22"],
            VISUAL_CONFIG["absolute"]["labels"]["19_22"],
        )

    return (
        "Compound",
        VISUAL_CONFIG["relative"]["palette"],
        VISUAL_CONFIG["relative"]["markers"],
        VISUAL_CONFIG["relative"]["labels"],
    )


def get_drivers(
    session: Session,
    drivers: Iterable[str | int] | str | int,
    by: str = "Position",
) -> list[str]:
    """
    Find driver three-letter abbreviations.

    Assumes:
        session.results is sorted by finishing position

    Args:
        session: The race session object, relevant for determining finishing order.

        drivers: The following argument formats are accepted:
            - A single integer retrieve the highest ordered drivers
              e.g. drivers = 10 with by = "Position" will fetch the point finishiers

              drivers = 20 will return all available drivers
            - A string representing either the driver's three letter abbreviation
              or driver number.
              e.g. "VER" or "44"
            - A list of integers and/or strings representing either the driver's
              three letter abbreviation or driver number.
              e.g. ["VER", "44", 14]

        by: The key by which the drivers are sorted. Default is sorting by finishing position.
            See all available options in FastF1 `Session.results` documentation.

    Returns:
        The drivers' three-letter abbreviations, in the order requested.
        (Or in the case of int argument, in the finishing order.)
    """
    if isinstance(drivers, int):
        result = session.results.sort_values(by=by, kind="stable")
        drivers = result["Abbreviation"].unique()[:drivers]
        return list(drivers)
    if isinstance(drivers, str):
        drivers = [drivers]

    ret = []
    for driver in drivers:
        if isinstance(driver, (int, float)):
            driver = str(int(driver))
        ret.append(session.get_driver(driver)["Abbreviation"])

    return ret


def get_session_info(
    season: int,
    event: int | str,
    session_type: str,
    drivers: Iterable[str | int] | str | int = 3,
    teammate_comp: bool = False,
) -> tuple[int, str, list[str]]:
    """
    Retrieve session information based on season, event number/name, and session identifier.

    If event is provided as a string, then the name fuzzy matching is done by Fastf1.

    If teammate_comp is True, then the drivers are returned in the order of increasing team
    names (higher finishing teammate first) instead of by finishing position.
    """
    session = f.get_session(season, event, session_type)
    session.load(laps=False, telemetry=False, weather=False, messages=False)
    round_number = session.event["RoundNumber"]
    event_name = session.event["EventName"]

    if teammate_comp:
        drivers = get_drivers(session, drivers, by="TeamName")
    else:
        drivers = get_drivers(session, drivers)

    return round_number, event_name, drivers


def pick_driver_color(driver: str) -> str:
    """
    Find the driver's color.

    If the driver is currently active, use his FastF1 color.
    Else, default to gray.
    """
    if p.DRIVER_TRANSLATE.get(driver, "NA") in p.DRIVER_COLORS:
        return p.DRIVER_COLORS[p.DRIVER_TRANSLATE[driver]]

    return "#808080"


def add_gap(season: int, driver: str):
    """Calculate the gap to a certain driver for all laps in a season."""

    def calculate_gap(row):
        round_number = row.loc["RoundNumber"]
        lap = row.loc["LapNumber"]

        if lap not in driver_laptimes[round_number]:
            laptime = df_driver[
                (df_driver["RoundNumber"] == round_number) & (df_driver["LapNumber"] == lap)
            ]["Time"]

            if laptime.empty:
                driver_laptimes[round_number][lap] = pd.NaT
            else:
                driver_laptimes[round_number][lap] = laptime.iloc[0]

        return (row.loc["Time"] - driver_laptimes[round_number][lap]).total_seconds()

    for session_type in SESSION_IDS:
        df_laps = DF_DICT[season].get(session_type)

        if df_laps is None:
            continue

        assert driver.upper() in df_laps["Driver"].unique()
        df_driver = df_laps[df_laps["Driver"] == driver]

        # start a memo
        driver_laptimes = {i: {} for i in df_driver["RoundNumber"].unique()}
        df_laps[f"GapTo{driver}"] = df_laps.apply(calculate_gap, axis=1)

        DF_DICT[season][session_type] = df_laps


def _teammate_comp_order(included_laps: pd.DataFrame, drivers: list[str], by: str) -> list[str]:
    """
    Reorder teammates by the median gap in some metric in descending order.

    For example, if by is LapTime, then the teammates with the biggest median laptime
    difference will appear first.

    Assumes:
        by is a column in included_laps.
    """
    metric_median = included_laps.groupby("Driver").median(numeric_only=True)[by]
    laps_recorded = included_laps.groupby("Driver").size()
    drivers_to_plot = laps_recorded.loc[lambda x: x > 5].index
    team_median_gaps = []

    for i in range(0, len(drivers) - 1, 2):
        teammates = drivers[i], drivers[i + 1]

        # Some drivers not have any valid data!
        # and thus will not be in the team_median_gaps dictionary
        # in that case, do not plot the teammate with no valid data
        if teammates[0] in drivers_to_plot and teammates[1] in drivers_to_plot:
            median_gap = abs(metric_median[teammates[0]] - metric_median[teammates[1]])
            team_median_gaps.append([teammates, median_gap])
        else:
            for driver in teammates:
                if driver in drivers_to_plot:
                    team_median_gaps.append([tuple([driver]), 0])
                else:
                    logging.warning(
                        "%s has less than 5 laps of data and will not be plotted",
                        driver,
                    )

    team_median_gaps.sort(key=lambda x: x[1], reverse=True)

    # handles odd number of drivers case
    standout = drivers[-1:] if len(drivers) % 2 == 1 else []

    drivers = [driver for team in team_median_gaps for driver in team[0]]
    drivers.extend(standout)

    return drivers


def _lap_filter_sc(row: pd.Series) -> bool:
    """
    Check if any part of a lap is ran under safety car.

    Track status 4 stands for safety car.

    Caveats:
        Unsure if the lap after "safety car in this lap" will be included.
    """
    return "4" in row.loc["TrackStatus"]


def _lap_filter_vsc(row: pd.Series) -> bool:
    """
    Check if any part of a lap is ran under virtual safety car.

    A lap is only counted if none of it is ran under full safety car

    Track status 6 is VSC deployed.
    Track status 7 is VSC ending.

    Caveats:
        Might double count with the `_lap_filter_sc` function.
    """
    return (("6" in row.loc["TrackStatus"]) or ("7" in row.loc["TrackStatus"])) and (
        "4" not in row.loc["TrackStatus"]
    )


def _find_sc_laps(df_laps: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """
    Find the unique lap numbers that is ran under SC or VSC.

    The resulting arrays are sorted before they are returned.
    """
    sc_laps = np.sort(df_laps[df_laps.apply(_lap_filter_sc, axis=1)]["LapNumber"].unique())
    vsc_laps = np.sort(df_laps[df_laps.apply(_lap_filter_vsc, axis=1)]["LapNumber"].unique())

    return sc_laps, vsc_laps


def _shade_sc_periods(sc_laps: np.ndarray, vsc_laps: np.ndarray):
    """
    Shade SC and VSC periods.

    Args:
        sc_laps: Sorted array of integers indicating laps under safety car

        vsc_laps: sorted array of integers indicating laps under virtual safety car
    """
    sc_laps = np.append(sc_laps, [-1])
    vsc_laps = np.append(vsc_laps, [-1])

    def plot_periods(laps, label, hatch=None):
        start = 0
        end = 1

        while end < len(laps):
            # check if the current SC period is still ongoing
            if laps[end] == laps[end - 1] + 1:
                end += 1
            else:
                if end - start > 1:
                    # the latest SC period lasts for more than one lap
                    plt.axvspan(
                        # minus one to correct for zero indexing on the plot
                        # but one indexing in the data
                        xmin=laps[start] - 1,
                        xmax=laps[end - 1] - 1,
                        alpha=0.5,
                        color="orange",
                        # only produce one label in legend
                        label=label if start == 0 else "_",
                        hatch=hatch,
                    )
                else:
                    # end = start + 1, the latest SC period lasts only one lap
                    plt.axvspan(
                        xmin=laps[start] - 1,
                        xmax=laps[start],
                        alpha=0.5,
                        color="orange",
                        label=label if start == 0 else "_",
                        hatch=hatch,
                    )
                start = end
                end += 1

    plot_periods(sc_laps, "SC")
    plot_periods(vsc_laps, "VSC", "-")


def _convert_compound_name(
    season: int, round_number: int, compounds: Iterable[str]
) -> tuple[str]:
    """
    Convert relative compound names to absolute compound names.

    Args:
        season: Championship season

        round_number: Grand Prix round number.

        compounds: Relative compound names to convert.

    Examples:
        2023 round 1 selects C1, C2, C3 compounds.

        Then _convert_compound_name(
        2023, 1, ["SOFT", "HARD"]
        ) = ["C1", "C3"]
    """
    compound_to_index = {"SOFT": 2, "MEDIUM": 1, "HARD": 0}
    if season == 2018:
        compound_to_index = {"SOFT": 0, "MEDIUM": 1, "HARD": 2}

    return_vals = []

    for compound in compounds:
        return_vals.append(
            COMPOUND_SELECTION[str(season)][str(round_number)][compound_to_index[compound]]
        )

    return tuple(return_vals)


def _process_input(
    seasons: int | Iterable[int],
    events: int | str | Iterable[str | int],
    session_types: str | Iterable[str],
    y: str,
    compounds: Iterable[str],
    x: str,
    upper_bound: int | float,
    absolute_compound: bool,
) -> tuple[list[f.events.Event], list[pd.DataFrame]]:
    """
    Sanitize input parameters to compound plots.

    Returns:
        event_objects: List of event objects corresponding to each requested race

        included_laps_list: List of dataframes corresponding to each requested race
    """
    # unpack
    compounds = [compound.upper() for compound in compounds]

    for compound in compounds:
        assert compound in {
            "SOFT",
            "MEDIUM",
            "HARD",
        }, f"requested compound {compound} is not valid"

    if x not in {"LapNumber", "TyreLife"}:
        logging.warning(
            "Using %s as the x-axis is not recommended. (Recommended x: LapNumber, TyreLife)",
            x,
        )

    if not absolute_compound and len(events) > 1:
        logging.warning(
            """
            Different events may use different compounds under the same name!
            e.g. SOFT may be any of C3 to C5 dependinging on the event
            """
        )

    if isinstance(seasons, (int, str)):
        seasons = [seasons]

    if isinstance(events, (int, str)):
        events = [events]

    if isinstance(session_types, str):
        session_types = [session_types]

    if session_types is None:
        session_types = ["R" for i in range(len(seasons))]

    assert (
        len(seasons) == len(events) == len(session_types)
    ), f"Arguments {seasons}, {events}, {session_types} have different lengths."

    # Combine seasons and events and get FastF1 event objects
    event_objects = [f.get_event(seasons[i], events[i]) for i in range(len(seasons))]

    included_laps_list = []

    for season, event, session_type in zip(seasons, event_objects, session_types):
        df_laps = _filter_round_compound_valid_upper(
            DF_DICT[season][session_type], event["RoundNumber"], compounds, upper_bound
        )

        # LapRep columns have outliers that can skew the graph y-axis
        # The high outlier values are filtered by upper_bound
        # Using a lower bound of -5 on PctFromLapRep will retain 95+% of all laps
        if y in {"PctFromLapRep", "DeltaToLapRep"}:
            df_laps = df_laps[df_laps["PctFromLapRep"] > -5]

        included_laps_list.append(df_laps)

    return event_objects, included_laps_list


def _make_autopct(values: pd.DataFrame | pd.Series) -> Callable:
    """Format group sizes as percentages of the total."""

    def my_autopct(pct):
        total = sum(values)

        # additional call to int is for type conversion
        # not duplicated rounding
        val = int(round(pct * total / 100.0))
        return "{p:.1f}%  ({v:d})".format(p=pct, v=val)

    return my_autopct


def _get_pie_palette(season: int, absolute: bool, labels: Iterable[str]) -> list[str]:
    """Get the tyre compound palette needed for the pie chart."""
    # TODO: Find ways to unify this with _plot_args or similar
    if absolute:
        if season == 2018:
            return [VISUAL_CONFIG["absolute"]["palette"]["18"][label] for label in labels]

        return [VISUAL_CONFIG["absolute"]["palette"]["19_22"][label] for label in labels]

    return [VISUAL_CONFIG["relative"]["palette"][label] for label in labels]


def _make_pie_title(season: int, slick_only: bool) -> str:
    """Compose the pie chart title."""
    if slick_only:
        return f"Slick Compound Usage in the {season} Season"

    return f"All Compound Usage in the {season} Season"


def tyre_usage_pie(
    season: int,
    session_type: str = "R",
    title: Optional[str] = None,
    events: Optional[list[int | str]] = None,
    drivers: Optional[list[str]] = None,
    slick_only: bool = True,
    absolute_compound: bool = True,
) -> Figure:
    """
    Visualize tyre usage trends by compound with a pie chart.

    The arguments configure the range of data from which
    the tyre usage frequency is calculated.

    Args:
        season: Championship season

        session_type: Follow Fastf1 session identifier convention.

        title: Use default argument to use an automatically formatted title.
        Only available when events and drivers are None.

        events: A list containing the round numbers (as int) or the names of events.
        Examples: [1, "Hungary", "British Grand Prix", "Monza"]
        Name fuzzy matched by fastf1.get_event().
        Leave empty will select all events in the season.

        drivers: A list containing three-letter driver abbreviations.
        Examples: ["VER", "HAM"]
        Leave empty to select all drivers.

        slick_only: If true, only laps raced on slick tyres are counted.
        If false, all laps are counted.

        absolute_compound: If true, group tyres by absolute compound names (C1, C2 etc.).
        Else, group tyres by relative compound names (SOFT, MEDIUM, HARD).

    Examples:
        Using the following arguments:
            events = [1, 2, 3, 4, 5]
            drivers = ["VER", "HAM"]
            slick_only = True
        Will plot the tyre compounds used by Hamilton and Verstappan
        in the first 5 Grand Prix only.
    """
    included_laps = DF_DICT[season][session_type]

    if title is None and events is None and drivers is None:
        title = _make_pie_title(season, slick_only)

    if events is None:
        events = pd.unique(included_laps["RoundNumber"])
    else:
        events = [
            (f.get_event(season, event)["RoundNumber"] if isinstance(event, str) else event)
            for event in events
        ]

    if drivers is None:
        drivers = pd.unique(included_laps["Driver"])

    if slick_only:
        included_laps = included_laps[included_laps["IsSlick"]]

    included_laps = included_laps[
        (included_laps["RoundNumber"].isin(events)) & (included_laps["Driver"].isin(drivers))
    ]

    fig, ax = plt.subplots(figsize=(10, 6))
    plt.style.use("default")

    lap_counts = None
    if absolute_compound:
        lap_counts = included_laps.groupby("CompoundName").size()
    else:
        lap_counts = included_laps.groupby("Compound").size()

    labels = lap_counts.index
    palette = _get_pie_palette(season, absolute_compound, labels)

    _, _, autotexts = ax.pie(
        x=lap_counts.values,
        labels=labels,
        colors=palette,
        autopct=_make_autopct(lap_counts),
        counterclock=False,
        startangle=90,
    )

    handles, labels = ax.get_legend_handles_labels()
    label_order = _find_legend_order(labels)
    ax.legend(
        handles=[handles[i] for i in label_order],
        labels=[labels[i] for i in label_order],
        title="Compound Names",
        loc="best",
    )

    ax.axis("equal")
    ax.set_title(title)
    plt.setp(autotexts, size=12)

    return fig


def driver_stats_scatterplot(
    season: int,
    event: int | str,
    session_type: str = "R",
    drivers: Iterable[str | int] | str | int = 3,
    y: str = "LapTime",
    upper_bound: int | float = 10,
    absolute_compound: bool = False,
    teammate_comp: bool = False,
    lap_numbers: Optional[list[int]] = None,
) -> Figure:
    """
    Visualize driver data during a race as a scatterplot.

    Args:
        season: Championship season

        event: Round number or name of the event.
        Name is fuzzy matched by fastf1.get_event().

        session_type: Follow Fastf1 session identifier convention.

        drivers: See `get_drivers` for all accepted formats.
        By default, the podium finishers are plotted.

        y: Name of the column to be used as the y-axis.

        upper_bound: The upper bound on included laps as a percentage of the fastest lap.
        By default, only laps that are within 110% of the fastest lap are plotted.

        absolute_compound: If true, group tyres by absolute compound names (C1, C2 etc.).
        Else, group tyres by relative compound names (SOFT, MEDIUM, HARD).

        teammate_comp: Toggles teammate comparison mode. See _teammate_comp_order
        for explanation. If False, the drivers are plotted by finishing order
        (higher finishing to the left).

        lap_numbers: A list of consecutive lap numbers representing a segment of the event.
        Recommend constructing this argument from a range object.

    Caveat:
        Providing a list of numbers that is not consecutive as lap_numbers will cause
        undefined behavior.
    """
    plt.style.use("dark_background")
    fontdict = {
        "fontsize": rcParams["axes.titlesize"],
        "fontweight": rcParams["axes.titleweight"],
        "color": rcParams["axes.titlecolor"],
        "verticalalignment": "baseline",
        "horizontalalignment": "center",
    }

    round_number, event_name, drivers = get_session_info(
        season, event, session_type, drivers, teammate_comp
    )
    included_laps = DF_DICT[season][session_type]
    included_laps = _filter_round_driver(included_laps, round_number, drivers)

    if teammate_comp:
        drivers = _teammate_comp_order(included_laps, drivers, y)

    if lap_numbers is not None:
        assert sorted(lap_numbers) == list(range(lap_numbers[0], lap_numbers[-1] + 1))
        included_laps = included_laps[included_laps["LapNumber"].isin(lap_numbers)]

    max_width = 4 if teammate_comp else 5
    num_row = ceil(len(drivers) / max_width)
    num_col = len(drivers) if len(drivers) < max_width else max_width
    fig, axes = plt.subplots(
        nrows=num_row,
        ncols=num_col,
        sharey=True,
        sharex=True,
        figsize=(5 * num_col, 5 * num_row),
    )

    args = _plot_args(season, absolute_compound)

    # Prevent TypeError when only one driver is plotted
    if len(drivers) == 1:
        axes = np.array([axes])

    # LapRep columns have outliers that can skew the graph y-axis
    # The high outlier values are filtered by upper_bound
    # Using a lower bound of -5 on PctFromLapRep will retain 95+% of all laps
    if y in {"PctFromLapRep", "DeltaToLapRep"}:
        included_laps = included_laps[included_laps["PctFromLapRep"] > -5]

    for index, driver in enumerate(drivers):
        row, col = divmod(index, max_width)

        ax = axes[row][col] if num_row > 1 else axes[col]

        driver_laps = included_laps[included_laps["Driver"] == driver]
        pit_in_laps = driver_laps[driver_laps["PitInTime"].notna()]["LapNumber"].to_numpy()

        # After pitstops are identified,
        # filter out laps that doesn't meet the upper_bound
        driver_laps = driver_laps[driver_laps["PctFromFastest"] < upper_bound]

        if driver_laps.shape[0] < 5:
            logging.warning("%s HAS LESS THAN 5 LAPS ON RECORD FOR THIS EVENT", driver)

        sns.scatterplot(
            data=driver_laps,
            x="LapNumber",
            y=y,
            ax=ax,
            hue=args[0],
            palette=args[1],
            hue_order=args[3],
            style="FreshTyre",
            style_order=["True", "False", "Unknown"],
            markers=VISUAL_CONFIG["fresh"]["markers"],
            legend="auto" if index == num_col - 1 else False,
        )
        ax.vlines(
            ymin=plt.yticks()[0][1],
            ymax=plt.yticks()[0][-2],
            x=pit_in_laps,
            label="Pitstop",
            linestyle="dashed",
        )

        driver_color = pick_driver_color(driver)
        fontdict["color"] = driver_color
        ax.set_title(label=driver, fontdict=fontdict, fontsize=12)

        ax.grid(color=driver_color, which="both", axis="both")
        sns.despine(left=True, bottom=True)

    fig.suptitle(t=f"{season} {event_name}", fontsize=20)
    axes.flatten()[num_col - 1].legend(loc="best", fontsize=8, framealpha=0.5)

    return fig


def driver_stats_lineplot(
    season: int,
    event: int | str,
    session_type: str = "R",
    drivers: Iterable[str | int] | str | int = 20,
    y: str = "Position",
    upper_bound: Optional[int | float] = None,
    grid: Optional[Literal["both", "x", "y"]] = None,
    lap_numbers: Optional[list[int]] = None,
) -> Figure:
    """
    Visualize driver data during a race as a lineplot.

    Args:
        season: Championship season

        event: Round number or name of the event.
        Name is fuzzy matched by fastf1.get_event().

        session_type: Follow Fastf1 session identifier convention.

        drivers: See `get_drivers` for all accepted formats.
        By default, all drivers are plotted.

        y: Name of the column to be used as the y-axis.

        upper_bound: The upper bound on included laps as a percentage of the fastest lap.
        Defaults to none in signature to enable checking whether a value is explicitly passed.
        Usually, the value is set to 10 in function body.

        grid: Provided to plt.grid() axis argument.
        Leave empty to plot no grid.

        lap_numbers: A list of consecutive lap numbers representing a segment of the event.
        Recommend constructing this argument from a range object.

    Caveat:
        Providing a list of numbers that is not consecutive as lap_numbers will cause
        undefined behavior.
    """
    plt.style.use("dark_background")

    round_number, event_name, drivers = get_session_info(season, event, session_type, drivers)
    included_laps = DF_DICT[season][session_type]
    included_laps = _filter_round_driver(included_laps, round_number, drivers)

    if lap_numbers is not None:
        assert sorted(lap_numbers) == list(range(lap_numbers[0], lap_numbers[-1] + 1))
        included_laps = included_laps[included_laps["LapNumber"].isin(lap_numbers)]

    sc_laps, vsc_laps = _find_sc_laps(included_laps)

    if upper_bound is None:
        if y == "Position" or y.startswith("GapTo"):
            upper_bound = 100
        else:
            upper_bound = 10

    # do upper bound filtering after SC periods are identified
    included_laps = _filter_round_driver_upper(
        included_laps, round_number, drivers, upper_bound
    )

    # adjust plot size based on number of laps
    num_laps = included_laps["LapNumber"].nunique()
    fig, ax = plt.subplots(figsize=(ceil(num_laps * 0.25), 8))

    if y == "Position":
        plt.yticks(range(2, 21, 2))

    if y == "Position" or y.startswith("GapTo"):
        ax.invert_yaxis()

    if len(drivers) > 10:
        ax.grid(which="major", axis="x")
    else:
        ax.grid(which="major", axis="both")

    for driver in drivers:
        driver_laps = included_laps[included_laps["Driver"] == driver]

        if driver_laps[y].count() == 0:
            # nothing to plot for this driver
            logging.warning("%s has no data entry for %s", driver, y)
            continue

        driver_color = pick_driver_color(driver)

        sns.lineplot(driver_laps, x="LapNumber", y=y, ax=ax, color=driver_color, errorbar=None)
        last_lap = driver_laps["LapNumber"].max()
        last_pos = driver_laps[y][driver_laps["LapNumber"] == last_lap].iloc[0]

        ax.annotate(
            xy=(last_lap + 1, last_pos + 0.25),
            text=driver,
            color=driver_color,
            fontsize=12,
        )
        sns.despine(left=True, bottom=True)

    # shade SC periods
    _shade_sc_periods(sc_laps, vsc_laps)

    if grid in {"both", "x", "y"}:
        plt.grid(axis=grid)
    else:
        plt.grid(visible=False)

    plt.legend(loc="lower right", fontsize=10)

    fig.suptitle(t=f"{season} {event_name}", fontsize=20)

    return fig


def driver_stats_distplot(
    season: int,
    event: int | str,
    session_type: str = "R",
    drivers: Iterable[str | int] | str | int = 10,
    y: str = "LapTime",
    upper_bound: float | int = 10,
    swarm: bool = True,
    violin: bool = True,
    absolute_compound: bool = False,
    teammate_comp: bool = False,
) -> Figure:
    """
    Visualize race data distribution as a violinplot or boxplot + optional swarmplot.

    Args:
        season: Championship season

        event: Round number or name of the event.
        Name is fuzzy matched by fastf1.get_event().

        session_type: Follow Fastf1 session identifier convention.

        drivers: See `get_drivers` for all accepted formats.
        By default, the point finishers are plotted.

        y: Name of the column to be used as the y-axis.

        upper_bound: The upper bound on included laps as a percentage of the fastest lap.
        By default, only laps that are less than 10% slower than the fastest lap are plotted.

        swarm: Toggle swarmplot visibility.

        violin: Toggles between violinplot and boxplot.

        absolute_compound: If true, group tyres by absolute compound names (C1, C2 etc.).
        Else, group tyres by relative compound names (SOFT, MEDIUM, HARD).

        teammate_comp: Toggles teammate comparison mode. See _teammate_comp_order
        for explanation. If False, the drivers are plotted by finishing order
        (higher finishing to the left).
    """
    plt.style.use("dark_background")

    round_number, event_name, drivers = get_session_info(
        season, event, session_type, drivers, teammate_comp
    )

    included_laps = DF_DICT[season][session_type]
    included_laps = _filter_round_driver_upper(
        included_laps, round_number, drivers, upper_bound
    )

    if teammate_comp:
        drivers = _teammate_comp_order(included_laps, drivers, y)

    # Adjust plot size based on number of drivers plotted
    fig, ax = plt.subplots(figsize=(len(drivers) * 1.5, 10))
    args = _plot_args(season, absolute_compound)

    driver_colors = [pick_driver_color(driver) for driver in drivers]

    if violin:
        sns.violinplot(
            data=included_laps,
            x="Driver",
            y=y,
            inner=None,
            scale="area",
            palette=driver_colors,
            order=drivers,
        )
    else:
        sns.boxplot(
            data=included_laps,
            x="Driver",
            y=y,
            palette=driver_colors,
            order=drivers,
            whiskerprops={"color": "white"},
            boxprops={"edgecolor": "white"},
            medianprops={"color": "white"},
            capprops={"color": "white"},
            showfliers=False,
        )

    if swarm:
        sns.swarmplot(
            data=included_laps,
            x="Driver",
            y=y,
            hue=args[0],
            palette=args[1],
            order=drivers,
            linewidth=0,
            size=5,
        )

        handles, labels = ax.get_legend_handles_labels()
        order = _find_legend_order(labels)
        ax.legend(
            handles=[handles[idx] for idx in order],
            labels=[labels[idx] for idx in order],
            loc="best",
            title=args[0],
            frameon=True,
            fontsize=10,
            framealpha=0.5,
        )

    ax.grid(visible=False)

    fig.suptitle(t=f"{season} {event_name}", fontsize=20)

    return fig


def strategy_barplot(
    season: int,
    event: int | str,
    session_type: str = "R",
    drivers: Iterable[str] | int = 20,
    absolute_compound: bool = False,
) -> Figure:
    """
    Visualize tyre strategies as a horizontal barplot.

    Args:
        season: Championship season

        event: Round number or name of the event.
        Name is fuzzy matched by fastf1.get_event().

        session_type: Follow Fastf1 session identifier convention.

        drivers: See `get_drivers` for all accepted formats.
        By default, all drivers are plotted.

        absolute_compound: If true, group tyres by absolute compound names (C1, C2 etc.).
        Else, group tyres by relative compound names (SOFT, MEDIUM, HARD).
    """
    round_number, event_name, drivers = get_session_info(season, event, session_type, drivers)
    included_laps = DF_DICT[season][session_type]
    included_laps = _filter_round_driver(included_laps, round_number, drivers)

    fig, ax = plt.subplots(figsize=(5, len(drivers) // 3 + 1))
    plt.style.use("dark_background")

    driver_stints = (
        included_laps[["Driver", "Stint", "Compound", "CompoundName", "FreshTyre", "LapNumber"]]
        .groupby(["Driver", "Stint", "Compound", "CompoundName", "FreshTyre"])
        .count()
        .reset_index()
    )
    driver_stints = driver_stints.rename(columns={"LapNumber": "StintLength"})
    driver_stints = driver_stints.sort_values(by=["Stint"])

    args = _plot_args(season, absolute_compound)

    for driver in drivers:
        stints = driver_stints.loc[driver_stints["Driver"] == driver]

        previous_stint_end = 0
        for _, stint in stints.iterrows():
            plt.barh(
                [driver],
                stint["StintLength"],
                left=previous_stint_end,
                color=args[1][stint[args[0]]],
                edgecolor="black",
                fill=True,
                hatch=VISUAL_CONFIG["fresh"]["hatch"][stint["FreshTyre"]],
            )

            previous_stint_end += stint["StintLength"]

    _shade_sc_periods(*_find_sc_laps(included_laps))

    plt.title(f"{season} {event_name}", fontsize=16)
    plt.xlabel("Lap Number")
    plt.grid(False)

    handles, labels = ax.get_legend_handles_labels()
    if labels:
        deduplicate_labels_handles = dict(zip(labels, handles))
        plt.legend(
            handles=deduplicate_labels_handles.values(),
            labels=deduplicate_labels_handles.keys(),
            loc="lower right",
            fontsize=10,
        )

    # Invert y-axis
    ax.invert_yaxis()

    # Remove frame from plot
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)

    return fig


def compounds_lineplot(
    seasons: int | Iterable[int],
    events: int | str | Iterable[int | str],
    session_types: Optional[str | Iterable[str]] = None,
    y: str = "LapTime",
    compounds: Iterable[str] = ["SOFT", "MEDIUM", "HARD"],
    x: str = "TyreLife",
    upper_bound: int | float = 10,
    absolute_compound: bool = True,
) -> Figure:
    """
    Visualize compound performances as a lineplot.

    Caveats:
        Only laps with `IsValid=True` are considered

    Args:
        seasons: Championship seasons of the events

        events: A mix of round numbers or names of the events
        Name is fuzzy matched by fastf1.get_event()

        Each (season, event) pair should uniquely identify an event.

        session_types: Follow Fastf1 session identifier convention.

        y: The column to use as the y-axis.

        compounds: The compounds to plot.

        x: The column to use as the x-axis.
        `TyreLife` or `LapNumber` recommended.

        upper_bound: The upper bound on included laps as a percentage of the fastest lap.
        By default, only laps that are less than 10% slower than the fastest lap are plotted.

        absolute_compound: If true, group tyres by absolute compound names (C1, C2 etc.).
        Else, group tyres by relative compound names (SOFT, MEDIUM, HARD).
    """
    plt.style.use("dark_background")

    if isinstance(seasons, int):
        seasons = [seasons]

    event_objects, included_laps_list = _process_input(
        seasons, events, session_types, y, compounds, x, upper_bound, absolute_compound
    )

    fig, axes = plt.subplots(
        nrows=len(event_objects),
        sharex=True,
        ncols=1,
        figsize=(5, 5 * len(event_objects)),
    )

    # Prevent TypeError when only one event is plotted
    if len(event_objects) == 1:
        axes = [axes]

    # Copy compounds values
    # May need to convert from relative to absolute names when plotting
    compounds_copy = compounds.copy()

    for idx, event in enumerate(event_objects):
        ax = axes[idx]
        args = _plot_args(seasons[idx], absolute_compound)
        included_laps = included_laps_list[idx]
        medians = included_laps.groupby([args[0], x])[y].median(numeric_only=True)

        round_number = event["RoundNumber"]
        event_name = event["EventName"]

        if absolute_compound:
            compounds_copy = _convert_compound_name(seasons[idx], round_number, compounds)

        for compound in compounds_copy:
            if compound in medians.index:
                sns.lineplot(
                    x=medians.loc[compound].index,
                    y=medians.loc[compound].values,
                    ax=ax,
                    color=args[1][compound],
                    marker=args[2][compound],
                    markersize=4,
                    label=compound,
                )
            else:
                logging.warning(
                    (
                        "%s is not plotted for %s %s because there is not enough data",
                        compounds[idx],
                        seasons[idx],
                        event_name,
                    )
                )

        ax.set_ylabel(y, fontsize=12)

        handles, labels = ax.get_legend_handles_labels()
        order = _find_legend_order(labels)
        ax.legend(
            handles=[handles[i] for i in order],
            labels=[labels[i] for i in order],
            loc="best",
            title=args[0],
            frameon=True,
            fontsize=10,
            framealpha=0.5,
        )

        ax.set_title(label=f"{seasons[idx]} {event_name}", fontsize=12)
        ax.grid(which="both", axis="y")
        sns.despine(left=True, bottom=True)

    # reorder compound names for title
    compounds = [compounds[i] for i in _find_legend_order(compounds)]

    fig.suptitle(t=" VS ".join(compounds), fontsize=14)

    return fig


def compounds_distribution(
    seasons: int | Iterable[int],
    events: int | str | Iterable[int | str],
    session_types: Optional[str | Iterable[str]] = None,
    y: str = "LapTime",
    compounds: Iterable[str] = ["SOFT", "MEDIUM", "HARD"],
    violin_plot: bool = False,
    x: str = "TyreLife",
    upper_bound: int | float = 10,
    absolute_compound: bool = True,
) -> Figure:
    """
    Visualize compound performance as a boxplot or violinplot.

    Caveats:
        Only laps with `IsValid=True` are considered

    Args:
        seasons: Championship seasons of the events

        events: A mix of round numbers or names of the events
        Name is fuzzy matched by fastf1.get_event()

        Each (season, event) pair should uniquely identify an event.

        session_types: Follow Fastf1 session identifier convention.

        y: The column to use as the y-axis.

        compounds: The compounds to plot.

        violin_plot: Toggles violinplot and boxplot.

        x: The column to use as the x-axis.
        `TyreLife` or `LapNumber` recommended.

        upper_bound: The upper bound on included laps as a percentage of the fastest lap.
        By default, only laps that are less than 10% slower than the fastest lap are plotted.

        absolute_compound: If true, group tyres by absolute compound names (C1, C2 etc.).
        Else, group tyres by relative compound names (SOFT, MEDIUM, HARD).
    """
    plt.style.use("dark_background")

    if isinstance(seasons, int):
        seasons = [seasons]

    event_objects, included_laps_list = _process_input(
        seasons, events, session_types, y, compounds, x, upper_bound, absolute_compound
    )

    # adjust plot size based on the chosen x-axis
    x_ticks = max(laps[x].nunique() for laps in included_laps_list)
    fig, axes = plt.subplots(
        nrows=len(event_objects),
        sharex=True,
        ncols=1,
        figsize=(ceil(x_ticks * 0.75), 5 * len(event_objects)),
    )

    # Prevent TypeError when only one event is plotted
    if len(event_objects) == 1:
        axes = [axes]

    # Copy compounds values
    # May need to convert from relative to absolute names when plotting
    compounds_copy = compounds.copy()

    for idx, event in enumerate(event_objects):
        ax = axes[idx]
        args = _plot_args(seasons[idx], absolute_compound)
        included_laps = included_laps_list[idx]

        plotted_compounds = included_laps[args[0]].unique()
        event_name = event["EventName"]
        round_number = event["RoundNumber"]

        if absolute_compound:
            compounds_copy = _convert_compound_name(seasons[idx], round_number, compounds)

        for compound in compounds_copy:
            if compound not in plotted_compounds:
                logging.warning(
                    (
                        "%s is not plotted for %s %s because there is not enough data",
                        compounds[idx],
                        seasons[idx],
                        event_name,
                    )
                )

        if violin_plot:
            sns.violinplot(data=included_laps, x=x, y=y, ax=ax, hue=args[0], palette=args[1])
        else:
            sns.boxplot(data=included_laps, x=x, y=y, ax=ax, hue=args[0], palette=args[1])

        ax.set_ylabel(y, fontsize=12)
        xticks = ax.get_xticks()
        xticks = [tick + 1 for tick in xticks if tick % 5 == 0]
        ax.set_xticks(xticks)
        ax.grid(which="both", axis="y")

        handles, labels = ax.get_legend_handles_labels()
        order = _find_legend_order(labels)
        ax.legend(
            handles=[handles[i] for i in order],
            labels=[labels[i] for i in order],
            loc="best",
            title=args[0],
            frameon=True,
            fontsize=12,
            framealpha=0.5,
        )

        ax.set_title(label=f"{seasons[idx]} {event_name}", fontsize=12)
        sns.despine(left=True, bottom=True)

    # reorder compound names for title
    compounds = [compounds[i] for i in _find_legend_order(compounds)]

    fig.suptitle(t=" VS ".join(compounds), fontsize="16")

    return fig
