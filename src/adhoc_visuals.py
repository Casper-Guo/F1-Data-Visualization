"""Visualization playground."""

import warnings

import matplotlib as mpl
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

mpl.use("Agg")
# uncomment this
# import visualization as viz # noqa: ERA001


def main():
    """Set up visualizations."""
    # plotting setup
    sns.set_theme(rc={"figure.dpi": 300, "savefig.dpi": 300})
    plt.style.use("dark_background")

    # Suppress pandas SettingWithCopy warning
    pd.options.mode.chained_assignment = None

    # Suppress Seaborn false positive warnings
    # TODO: This is dangerous
    warnings.filterwarnings("ignore")

    # Visualizations below


if __name__ == "__main__":
    main()
