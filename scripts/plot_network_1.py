"""Plot network capacities and compare Danish nodes with Energistyrelsen (ENS).

Place this script in your project's scripts/ or notebooks/ directory. Edit the
paths and settings below, then run it in your existing PyPSA environment.
ENS CSVs must already describe the same year as the network (capacities in MW).
"""

from pathlib import Path
import warnings

import matplotlib.pyplot as plt
import pandas as pd
import pypsa


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
NETWORK_FILE = DATA_DIR / "networks" / "sector_dk_se_ost.nc"
POWER_FILE = DATA_DIR / "powerplants.csv"
HEAT_FILE = DATA_DIR / "existing_chp_heat_capacitites.csv"

POWER_BUSES = ["AC", "low voltage"]
HEAT_BUSES = ["urban central heat", "urban decentral heat", "rural heat"]
CAPACITY_COLUMN = "p_nom_opt"  # Use "p_nom" for an unsolved network.
COMPARE_NODES = ["DK0", "DK1"]  # These are model nodes, not bidding-zone names.

POWER_MAPPING = {
    "Natural Gas": "gas", "Oil": "oil", "Solid Biomass": "biomass",
    "Biogas": "biomass", "Waste": "waste", "Hard Coal": "coal",
    "Wind": "onwind", "Solar": "solar", "Hydro": "ror",
    "Onshore": "onwind", "Offshore": "offwind", "PV": "solar",
}
HEAT_MAPPING = {
    ("ac", "resistive heater"): "urban central resistive heater",
    ("air", "heat pump"): "urban central air heat pump",
    ("gas", "CHP"): "urban central gas CHP",
    ("gas", "boiler"): "urban central gas boiler",
    ("oil", "CHP"): "urban central oil CHP",
    ("oil", "boiler"): "urban central oil boiler",
    ("coal", "CHP"): "urban central coal CHP",
    ("solid biomass", "CHP"): "urban central solid biomass CHP",
    ("solid biomass", "boiler"): "urban central biomass boiler",
    ("waste", "CHP"): "waste CHP",
    ("waste", "boiler"): "urban central waste boiler",
    ("solar thermal", "solar thermal"): "urban central solar thermal",
}
# Combine technologies that the ENS table cannot distinguish.
NETWORK_MAPPING = {
    "OCGT": "gas", "CCGT": "gas", "solid biomass": "biomass",
    "offwind-ac": "offwind", "offwind-dc": "offwind", "offwind-float": "offwind",
    "solar-hsat": "solar",
}


def coords_to_node(lat, lon):
    """Your approximate Danish mapping; check offshore grid connections separately.

    Assumes DK0 = eastern Denmark, DK1 = western Denmark, one node per area.
    For another clustering, provide a 'node' column in the power CSV instead.
    """
    if pd.isna(lat) or pd.isna(lon):
        return None
    if lon >= 13.5 or (lat < 55.6 and lon >= 11.5):
        return "DK0"
    if (lat < 55.2 and lon >= 10.8) or (lon >= 11.3 and lat < 56.3):
        return "DK0"
    if 56.0 <= lat <= 57.2 and 10.3 <= lon < 12.0:
        return "DK1"
    return "DK1" if lon < 10.9 else "DK0"


def capacity_table(rows, node_order=None):
    """Sum MW by node and carrier, using the same labels for both sources."""
    rows = rows.copy()
    rows["node"] = rows["node"].astype("string").str.split().str[0]
    rows["carrier"] = rows["carrier"].replace(NETWORK_MAPPING)
    missing = rows[["node", "carrier"]].isna().any(axis=1)
    if missing.any():
        raise ValueError(f"Missing node/carrier mapping:\n{rows.loc[missing]}")
    table = rows.pivot_table(
        index="node", columns="carrier", values="capacity", aggfunc="sum", fill_value=0
    )
    table = table.mask(table.abs() < 1e-3, 0)
    if node_order is not None:
        table = table.reindex(node_order, fill_value=0)
    return table.loc[:, table.ne(0).any(axis=0)]


def network_capacities(network, bus_carriers):
    """Installed output MW: generators directly, links times output efficiency.

    Includes electrical storage discharge power, but excludes heat storage,
    transfer links and artificial load shedding. CHP heat can be on bus2.
    PyPSA-Eur heat pumps run in reverse with heat at bus0: their nominal
    capacity is already MW_th. They consume electricity at bus1.
    """
    buses = network.buses.index[network.buses.carrier.isin(bus_carriers)]
    power_buses = network.buses.index[network.buses.carrier.isin(POWER_BUSES)]
    rows = []
    for component in [network.generators, network.storage_units]:
        selected = component.loc[component.bus.isin(buses)].copy()
        selected["capacity"] = selected[CAPACITY_COLUMN]
        rows.append(selected.rename(columns={"bus": "node"})[["node", "carrier", "capacity"]])

    # Inspect destination ports, rather than assuming every heat output is bus1.
    for port in ["bus1", "bus2"]:
        if port not in network.links.columns:
            continue
        links = network.links.loc[network.links[port].isin(buses)].copy()
        heat_pumps = links.carrier.str.contains("heat pump", case=False, na=False)
        # A heat pump connected to electricity consumes power, even if that
        # electricity bus is called bus1. It is not generating capacity.
        links = links.loc[~(heat_pumps & links[port].isin(power_buses))]
        # Transfers within the selected system are not production capacities.
        links = links.loc[~links.bus0.isin(buses)]
        # Only links able to operate forwards supply an output at bus1/bus2.
        links = links.loc[links.get("p_max_pu", pd.Series(1., index=links.index)) > 0]
        attribute = "efficiency" if port == "bus1" else "efficiency2"
        efficiency = links[attribute].copy()
        varying = network.links_t.get(attribute, pd.DataFrame())
        names = links.index.intersection(varying.columns)
        if len(names):
            weights = network.snapshot_weightings.generators
            efficiency.loc[names] = varying[names].mul(weights, axis=0).sum() / weights.sum()
        # Negative output efficiencies denote consumption at this port.
        links = links.loc[efficiency > 0]
        efficiency = efficiency.loc[links.index]
        links["capacity"] = links[CAPACITY_COLUMN] * efficiency
        rows.append(links.rename(columns={port: "node"})[["node", "carrier", "capacity"]])

    # Reverse-flow heat pumps: bus0 is the heat output and p_nom is MW_th.
    heat_pumps = network.links.carrier.str.contains("heat pump", case=False, na=False)
    heat_bus_names = network.buses.index[network.buses.carrier.isin(HEAT_BUSES)]
    pumps = network.links.loc[
        heat_pumps & network.links.bus0.isin(buses.intersection(heat_bus_names))
    ].copy()
    pumps["capacity"] = pumps[CAPACITY_COLUMN]
    rows.append(pumps.rename(columns={"bus0": "node"})[["node", "carrier", "capacity"]])

    nonempty = [row for row in rows if not row.empty]
    rows = pd.concat(nonempty, ignore_index=True) if nonempty else pd.DataFrame(
        columns=["node", "carrier", "capacity"]
    )
    excluded = rows.carrier.str.contains(
        r"\bload\b|shedding|heat vent|water tanks|distribution|relation",
        case=False, na=False,
    )
    node_order = buses.astype(str).str.split().str[0].drop_duplicates()
    return capacity_table(rows.loc[~excluded], node_order)


def ens_capacities(power, heat):
    """ENS inputs: power uses PPM fields; heat uses node/carrier/set and MW columns.

    All CHP electrical capacities come from the heat CSV. 'Set' in the power
    CSV must identify CHP so the same plants are not counted twice. Your Danish
    power CSV currently contains PP only; CHP comes from the heat CSV.
    Rows without coordinates are retained as DK-unassigned and reported.
    """
    power = power.loc[(power.Country == "Denmark") & (power.Set != "CHP")].copy()
    if "node" not in power.columns:
        power["node"] = power.apply(lambda row: coords_to_node(row.lat, row.lon), axis=1)
    power["carrier"] = power.Fueltype.map(POWER_MAPPING).astype("string").fillna(
        power.Technology.map(POWER_MAPPING).astype("string")
    )
    # Technology distinguishes offshore/onshore wind. Wind with no technology
    # is assumed onshore (small turbines in your register).
    wind = power.Fueltype.eq("Wind")
    power.loc[wind, "carrier"] = power.loc[wind, "Technology"].map(
        POWER_MAPPING
    ).astype("string").fillna("onwind")
    power["capacity"] = power.Capacity
    unassigned = power.node.isna()
    if unassigned.any():
        warnings.warn(
            f"{unassigned.sum()} ENS power entries ({power.loc[unassigned, 'capacity'].sum():.2f} MW) "
            "have no node. Retained as DK-unassigned; excluded from DK0/DK1 comparisons."
        )
        power.loc[unassigned, "node"] = "DK-unassigned"

    heat = heat.copy()
    heat["set"] = heat["set"].str.strip()
    keys = list(zip(heat.carrier.str.strip(), heat["set"]))
    heat["carrier"] = [HEAT_MAPPING.get(key) for key in keys]
    heat_rows = heat.loc[heat.heating_capacity > 0].copy()
    heat_rows["capacity"] = heat_rows.heating_capacity
    chp_rows = heat.loc[(heat["set"] == "CHP") & (heat.power_capacity > 0)].copy()
    chp_rows["capacity"] = chp_rows.power_capacity
    columns = ["node", "carrier", "capacity"]
    return (
        capacity_table(pd.concat([power[columns], chp_rows[columns]], ignore_index=True)),
        capacity_table(heat_rows[columns]),
    )


def carrier_colors(carriers, palette):
    # Combined carriers inherit a color from one of their original technologies.
    combined = {"gas": "OCGT", "biomass": "solid biomass", "offwind": "offwind-ac"}
    colors = []
    for carrier in carriers:
        color = palette.get(carrier, palette.get(combined.get(carrier), ""))
        colors.append(color if isinstance(color, str) and color else "#9b9b9b")
    return colors


def plot_by_node(table, title, unit, palette):
    if table.empty:
        return
    ax = table.plot.bar(
        stacked=True, color=carrier_colors(table.columns, palette), figsize=(11, 6), width=0.75
    )
    ax.set(title=title, xlabel="Node / source", ylabel=f"Capacity ({unit})")
    ax.legend(title="Carrier", bbox_to_anchor=(1.02, 1), loc="upper left")
    ax.grid(axis="y", alpha=0.25)
    ax.set_axisbelow(True)
    plt.xticks(rotation=0)
    plt.tight_layout()
    plt.show()


def plot_comparison(network_table, ens_table, nodes, title, unit, palette):
    """Paired stacked bars by node, then grouped bars by carrier for each node.

    Returns a numeric comparison. ENS covers Denmark only; non-Danish nodes
    belong in the network-only plots, not in these comparisons.
    """
    missing = set(nodes) - set(network_table.index)
    if missing:
        raise ValueError(f"Comparison nodes absent from network: {sorted(missing)}")
    missing_ens = set(nodes) - set(ens_table.index)
    if missing_ens:
        raise ValueError(f"No ENS data for comparison nodes: {sorted(missing_ens)}")
    carriers = network_table.columns.union(ens_table.columns, sort=False)
    net = network_table.reindex(index=nodes, columns=carriers, fill_value=0)
    ens = ens_table.reindex(index=nodes, columns=carriers, fill_value=0)
    paired = pd.concat({"Network": net, "ENS": ens}, names=["source", "node"])
    paired = paired.reorder_levels(["node", "source"]).reindex(
        pd.MultiIndex.from_product([nodes, ["Network", "ENS"]], names=["node", "source"])
    )
    paired = paired.loc[:, paired.ne(0).any(axis=0)]
    paired.index = [f"{node}\n{source}" for node, source in paired.index]
    plot_by_node(paired, title, unit, palette)

    comparisons = {}
    for node in nodes:
        table = pd.DataFrame({"Network": net.loc[node], "ENS": ens.loc[node]})
        table = table.loc[table.ne(0).any(axis=1)]
        if not table.empty:
            ax = table.plot.bar(figsize=(11, 6), color=["#4477aa", "#ee9933"])
            ax.set(title=f"{title} — {node}", xlabel="Carrier", ylabel=f"Capacity ({unit})")
            ax.grid(axis="y", alpha=0.25)
            ax.set_axisbelow(True)
            plt.xticks(rotation=45, ha="right")
            plt.tight_layout()
            plt.show()
        table["Difference (Network - ENS)"] = table.Network - table.ENS
        comparisons[node] = table
    return pd.concat(comparisons, names=["node", "carrier"])


if __name__ == "__main__":
    network = pypsa.Network(NETWORK_FILE)
    power = pd.read_csv(POWER_FILE)
    heat = pd.read_csv(HEAT_FILE)
    palette = network.carriers.color

    network_power = network_capacities(network, POWER_BUSES)
    network_heat = network_capacities(network, HEAT_BUSES)
    ens_power, ens_heat = ens_capacities(power, heat)

    plot_by_node(network_power, "Installed power capacity by node", "MW_el", palette)
    plot_by_node(network_heat, "Installed heat capacity by node", "MW_th", palette)
    power_comparison = plot_comparison(
        network_power, ens_power, COMPARE_NODES, "Power capacity: Network vs ENS", "MW_el", palette
    )
    heat_comparison = plot_comparison(
        network_heat, ens_heat, COMPARE_NODES,
        "Heat capacity: Network vs ENS", "MW_th", palette
    )
    print("\nPower capacity comparison [MW_el]:\n", power_comparison.round(1))
    print("\nHeat capacity comparison [MW_th]:\n", heat_comparison.round(1))
