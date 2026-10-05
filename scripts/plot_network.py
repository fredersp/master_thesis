import pypsa
import pandas as pd
from pathlib import Path
import matplotlib.pyplot as plt

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"


def color_by_carrier(network):
    
    return network.carriers.color


def plot_installed_power_capacities_by_node(network, buses, color_palette):
    
    # relevant power buses
    power_bus_names = network.buses.index[network.buses.carrier.isin(buses)]

    generators = network.generators.loc[network.generators.bus.isin(power_bus_names), ["bus", "carrier", "p_nom_opt"]].rename(columns={"p_nom_opt": "capacity"})

    links = network.links.loc[network.links.bus1.isin(power_bus_names),["bus1", "carrier", "p_nom_opt", "efficiency"],].copy()
    
    link_names = links.index.astype(str)
    exclude = link_names.str.contains("heat pump|CC|distribution|relation", case=False, regex=True)
    links = links.loc[~exclude].rename(columns={"bus1": "bus"})
    links["capacity"] = links["p_nom_opt"] * links["efficiency"]

    storage_units = network.storage_units.loc[
        network.storage_units.bus.isin(power_bus_names), ["bus", "carrier", "p_nom_opt"]
    ].rename(columns={"p_nom_opt": "capacity"})

    capacities = pd.concat(
        [generators, links[["bus", "carrier", "capacity"]], storage_units]
    )
    capacities["node"] = capacities["bus"].astype(str).str.split().str[0]
    
    # remove negligible capacities
    capacities.loc[capacities["capacity"] < 1e-3, "capacity"] = 0
    
    
    capacity_by_node = capacities.pivot_table(
        index="node", columns="carrier", values="capacity", aggfunc="sum", fill_value=0
    )

    # Keep nodes in the same order they appear in the network's selected buses.
    node_order = pd.Index(power_bus_names.astype(str).str.split().str[0]).drop_duplicates()
    capacity_by_node = capacity_by_node.reindex(node_order, fill_value=0)
    capacity_by_node = capacity_by_node.loc[
        capacity_by_node.ne(0).any(axis=1), capacity_by_node.ne(0).any(axis=0)
    ]
    if capacity_by_node.empty:
        return capacity_by_node

    carriers = capacity_by_node.columns
    colors = []
    for carrier in carriers:
        color = color_palette.get(carrier)
        colors.append(color if isinstance(color, str) and color else "#9b9b9b")
    ax = capacity_by_node.plot(
        kind="bar", stacked=True, color=colors, figsize=(10, 6), width=0.75
    )
    ax.set_title("Installed Power Capacity by Node")
    ax.set_xlabel("Node")
    ax.set_ylabel("Capacity (MW)")
    ax.legend(title="Carrier", bbox_to_anchor=(1.02, 1), loc="upper left")
    ax.grid(axis="y", alpha=0.25)
    ax.set_axisbelow(True)
    plt.tight_layout()
    plt.show()

    return capacity_by_node
    

def plot_installed_heat_capacities_by_node(network, buses, color_palette):
    
    # relevant heat buses
    heat_bus_names = network.buses.index[network.buses.carrier.isin(buses)]

    generators = network.generators.loc[network.generators.bus.isin(heat_bus_names), ["bus", "carrier", "p_nom_opt"]].rename(columns={"p_nom_opt": "capacity"})

    links = network.links.loc[network.links.bus1.isin(heat_bus_names),["bus1", "carrier", "p_nom_opt", "efficiency"],].copy()
    
    link_names = links.index.astype(str)
    exclude = link_names.str.contains("CC|distribution|relation", case=False, regex=True)
    links = links.loc[~exclude].rename(columns={"bus1": "bus"})
    
    if link_names.str.contains('chp').any():
        links["capacity"] = links["p_nom_opt"] * links["efficiency2"]
    else:
        links["capacity"] = links["p_nom_opt"] * links["efficiency"]

    storage_units = network.storage_units.loc[
        network.storage_units.bus.isin(heat_bus_names), ["bus", "carrier", "p_nom_opt"]
    ].rename(columns={"p_nom_opt": "capacity"})

    capacities = pd.concat(
        [generators, links[["bus", "carrier", "capacity"]], storage_units]
    )
    capacities["node"] = capacities["bus"].astype(str).str.split().str[0]
    
    # remove negligible capacities
    capacities.loc[capacities["capacity"] < 1e-3, "capacity"] = 0

    capacity_by_node = capacities.pivot_table(
        index="node", columns="carrier", values="capacity", aggfunc="sum", fill_value=0
    )

    # Keep nodes in the same order they appear in the network's selected buses.
    node_order = pd.Index(heat_bus_names.astype(str).str.split().str[0]).drop_duplicates()
    capacity_by_node = capacity_by_node.reindex(node_order, fill_value=0)
    capacity_by_node = capacity_by_node.loc[
        capacity_by_node.ne(0).any(axis=1), capacity_by_node.ne(0).any(axis=0)
    ]
    if capacity_by_node.empty:
        return capacity_by_node

    carriers = capacity_by_node.columns
    colors = []
    for carrier in carriers:
        color = color_palette.get(carrier)
        colors.append(color if isinstance(color, str) and color else "#9b9b9b")
    ax = capacity_by_node.plot(
        kind="bar", stacked=True, color=colors, figsize=(10, 6), width=0.75
    )
    ax.set_title("Installed Heat Capacity by Node")
    ax.set_xlabel("Node")
    ax.set_ylabel("Capacity (MW)")
    ax.legend(title="Carrier", bbox_to_anchor=(1.02, 1), loc="upper left")
    ax.grid(axis="y", alpha=0.25)
    ax.set_axisbelow(True)
    plt.tight_layout()
    plt.show()

    return capacity_by_node


if __name__ == "__main__":
    
    # Load network
    network = pypsa.Network(DATA_DIR / "networks" / "base_s_3_myopic.nc")
    
    
    
    
    
    # Get color mapping for carriers
    color_palette = color_by_carrier(network)
    
    # Power buses
    power_buses = ['AC', 'low voltage']
    
    # heat buses
    heat_buses = ['urban central heat', 'urban decentral heat', 'rural heat']
    
    # Plot installed power capacities by node
    capacity_by_node = plot_installed_power_capacities_by_node(
        network, power_buses, color_palette
    )

    # Plot installed heat capacities by node
    heat_capacity_by_node = plot_installed_heat_capacities_by_node(
        network, heat_buses, color_palette
    )
    
    
    