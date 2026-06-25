import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import datetime




def plot_bus_prices_heat_map(results_df: DataFrame, bus_id: str,
                            days: int = 60, vmin: float | None = None, vmax: float | None = None):
    """
    Plots a heat map of bus prices over time for a specific bus.
    """
    df = results_df.copy()

    df["snapshot"] = pd.to_datetime(df["snapshot"])


    # Format dates like 01-01
    df["date_label"] = df["snapshot"].dt.strftime("%d-%m")

    # Keep only the first 'days' rows for the heat map
    df = df.head(days)

    # One row: the selected bus
    heatmap_data = df.set_index("date_label")[[bus_id]].T

    plt.figure(figsize=(16, 3))

    sns.heatmap(
        heatmap_data,
        cmap="YlGnBu",
        annot=False,
        fmt=".1f",
        vmin = vmin,
        vmax = vmax,
        cbar_kws={"label": "Price"}
    )

    plt.title(f"Bus Prices Heatmap for {bus_id} - First {days} Days")
    plt.xlabel("Date")
    plt.ylabel("Bus")
    plt.xticks(rotation=45)
    plt.yticks(rotation=0)
    plt.tight_layout()
    plt.show()



def get_shared_price_scale(
    base_df: pd.DataFrame,
    shock_df: pd.DataFrame,
    bus_id: str,
    days: int = 60
):
    """
    Gets common vmin and vmax for base and shock scenarios.
    """

    base_prices = base_df.head(days)[bus_id]
    shock_prices = shock_df.head(days)[bus_id]

    vmin = min(base_prices.min(), shock_prices.min())
    vmax = max(base_prices.max(), shock_prices.max())

    return vmin, vmax


if __name__ == "__main__":
    # Load the results from the CSV file
    results_df_scenario = pd.read_csv("../results/GAS_150_30D/time_indexed_results.csv")
    results_df_base = pd.read_csv("../results/BASE/time_indexed_results.csv")

    vmin, vmax = get_shared_price_scale(results_df_base, results_df_scenario, bus_id="price_DK2 0AC", days = 60)


    plot_bus_prices_heat_map(results_df_scenario, bus_id="price_DK2 0AC", days = 60, vmin=vmin, vmax=vmax)
    # Plot the heat map for a specific bus ID
    plot_bus_prices_heat_map(results_df_base, bus_id="price_DK2 0AC", days = 60, vmin=vmin, vmax=vmax)
