# F1-Data-Visualization
Simple functions to visualize lap time and tyre usage data from all races of the 2021 and 2022 F1 seasons

## Requirements 
Use `pip install -r requirements.txt` to install all dependencies.

## General Information

### Data Freshness
`transformed_laps_2021.csv` covers all 22 races of the 2021 season

`transformed_laps_2022.csv` has coverage up until round 13, the Hungarian Grand Prix. (updated 08/06/22)

These two csv files can be directly ingested by `visualizations.ipynb` for plotting purposes. I will aim to keep the csv updated as much and as soon as possible.

In order to manually refresh the datasets on your device, run both `data_loading.ipynb` and `data_transformation.ipynb`. These files will attepmpt to grab the latest lap time data from the FastF1 API and apply all the needed transformations to prepare them for visualization.

If you have loaded parts of the 2022 season before and is looking to acquire the data for new grand prix only, there is a section in `data_loading.ipynb` titled `Incremental Load` that implements this functionality.

### Usage
There are four plotting functions provided in `visualizations.ipynb`. Their usage will hopefully be clear through the examples provided at the end of the notebook and accompanying documentation. Here is an overview:

- `tyre_usage_pie`: Visualize the frequency of compound usage within a season and allows filtering by events and drivers
- `plot_driver_lap_times`: Visualize driver lap time data within a single event. Allows selecting any number of drivers
- `plot_compounds_lineplot`: Visualize tyre performance over time by compound as line charts. Allows selecting any number of events from either the 2021 or the 2022 season.
- `plot_compounds_boxplot`: Visualize tyre performance over time by compound as boxplots. Allows selecting any number of events from either the 2021 or the 2022 season.

### Metrics Definitions
Detailed metric definitions can be found in the `data_transformation.ipynb` file. Here we present a list of columns available in the csvs.

- All columns provided by the FastF1 [Laps](https://theoehrly.github.io/Fast-F1/core.html?highlight=session#fastf1.core.Laps) object
- `RoundNumber`: (str) Round number of the event that the lap belongs to 
- `EventName`: (str) Short / common name of the Grand Prix that the lap belongs to 
- `IsSlick`: (bool) Whether the lap is completed on slick tyres
- `CompoundName`: (str) The name of the compound used for this lap (C1, C2, C3, C4, C5, INTERMEDIATE, WET)
- `IsValid`: (bool) See documentation
- `DeltaToRep`: (timedelta) Time differential between the current lap time and the representative lap time of the event
- `DeltaToFastest`: (timedelta) Time differential between the current lap time and the fastest lap time of the event
- `PctFromRep`: (float) Percent difference between the current lap time and the representative lap time of the event, accurate to three digits
- `PctFromFastest`: (float) Percent difference between the current lap time and fastest lap time of the event, accurate to three digits
- `DeltaToLapRep`: (timedelta) Time differential between the current lap time and the representative lap time for all laps of the same lap number
- `PctFromLapRep`: (float) Percent difference between the current lap time and the representative lap time for all laps of the same lap number, accurate to three digits
- `sLapTime`: (float) Lap time in seconds, accurate to three digits
- `sDeltaToRep`: (float) `DeltaToRep` in seconds, accurate to three digits
- `sDeltaToFastest`: (float) `DeltaToFastest` in seconds, accurate to three digits
- `sDeltaToLapRep`: (float) `DeltaToLapRep` in seconds, accurate to three digits

### Data Source
All data sourced from the [FastF1](https://github.com/theOehrly/Fast-F1) package.
