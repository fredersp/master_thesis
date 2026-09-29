import pandas as pd
import numpy as np
import pypsa
from pathlib import Path
import matplotlib.pyplot as plt


# Carrier naming used in the existing CHP/heat capacity dataset
CARRIER_MAPPING = {
    "Natural Gas": "gas",
    "Oil": "oil",
    "Solid Biomass": "biomass",
    "Biogas": "biomass",
    "Waste": "waste",
    "Hydro": "hydro",
    "Hard Coal": "coal",
    "Onshore": "onwind",
    "Offshore": "offwind-ac",
    "PV": "solar",
    "Hydro": "ror"
}

CHP_TO_HEAT = {
    "oil": "urban central oil CHP",
    "gas": "urban central gas CHP",
    "coal": "urban central coal CHP",
    "solid biomass": "urban central solid biomass CHP",
    "waste": "waste CHP"
}

HEAT_CARRIER_MAPPING = {
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


def coords_to_zone(lat, lon):
    """
    Approximate mapping to:
        DK1 = Western Denmark
        DK0 = Eastern Denmark / DK2

    Intended for Danish onshore + offshore generation data.
    """

    if pd.isna(lat) or pd.isna(lon):
        return None

    # ---------------------------------
    # Bornholm
    # ---------------------------------
    if lon >= 13.5:
        return "DK0"

    # ---------------------------------
    # Baltic Sea / east of Zealand
    # Kriegers Flak etc.
    # ---------------------------------
    if lat < 55.6 and lon >= 11.5:
        return "DK0"

    # ---------------------------------
    # Lolland-Falster / Rødsand / Nysted
    # ---------------------------------
    if lat < 55.2 and lon >= 10.8:
        return "DK0"

    # ---------------------------------
    # Zealand and waters immediately
    # surrounding Zealand
    # ---------------------------------
    if lon >= 11.3 and lat < 56.3:
        return "DK0"

    # ---------------------------------
    # Kattegat / Anholt area
    # Electrically connected towards Jutland
    # ---------------------------------
    if 56.0 <= lat <= 57.2 and 10.3 <= lon < 12.0:
        return "DK1"

    # ---------------------------------
    # North Sea
    # Horns Rev, Thor, Vesterhav etc.
    # ---------------------------------
    if lon < 10.3:
        return "DK1"

    # ---------------------------------
    # Onshore fallback:
    # Jutland + Funen west,
    # Zealand east
    # ---------------------------------
    if lon < 10.9:
        return "DK1"

    return "DK0"




def plot_power_comparison(df_ens_power, df_ens_heat, network, zone='DK0'):
    
    # include only powerplants in df_ens_power where country = 'Denmark'
    df_ens_power = df_ens_power[df_ens_power['Country'] == 'Denmark']
    df_ens_power = df_ens_power[df_ens_power['zone'] == zone]
    
    # map Fueltype or Technology to carrier names using CARRIER_MAPPING
    # if the column 'Fueltype' is equal the mapping, map, else map via 'Technology'
    df_ens_power['carrier'] = df_ens_power['Fueltype'].map(CARRIER_MAPPING)
    df_ens_power.loc[df_ens_power['carrier'].isna(), 'carrier'] = df_ens_power['Technology'].map(CARRIER_MAPPING)
    
    # include only CHP plants from df_ens_heat, where power_capacity > 0
    df_ens_heat = df_ens_heat[df_ens_heat['power_capacity'] > 0]
    df_ens_heat = df_ens_heat[df_ens_heat['node'].str.contains(zone)]
    
    # map df_ens_heat carrier to CHP_TO_HEAT
    df_ens_heat['carrier'] = df_ens_heat['carrier'].map(CHP_TO_HEAT)
    
    # Compare electrical capacity only; heat-bus outputs are thermal capacity.
    power_buses = network.buses.index[
        network.buses.carrier.str.contains("AC|DC|electricity|power|bev|low voltage", case=False, na=False)
        & network.buses.index.to_series().str.contains(zone, case=False, na=False).to_numpy()
    ]
    
    power_generators = network.generators.loc[
        network.generators.bus.isin(power_buses)
    ].copy()
    
    power_generators["capacity_MW"] = power_generators["p_nom_opt"]
    gen_power = power_generators.groupby("carrier")["capacity_MW"].sum()
    
    # Links delivering power to an electrical bus through bus1.
    links_power = network.links.loc[network.links.bus1.isin(power_buses)].copy()
    links_power["capacity_MW"] = links_power["p_nom_opt"] * links_power["efficiency"]
    links_power = links_power.groupby("carrier")["capacity_MW"].sum()
            
    

    
    # make comparison dataframe with df_ens_power['Capacity'] and df_ens_heat['power_capacity']
    # combined in one column and network capacities in another column for each carrier
    df_ens_power_capacity = df_ens_power.groupby("carrier")["Capacity"].sum()
    # power_capacity is the CHP electrical output; do not include heating_capacity.
    df_ens_heat_capacity = df_ens_heat.groupby("carrier")["power_capacity"].sum()
    df_ens_capacity = df_ens_power_capacity.add(df_ens_heat_capacity, fill_value=0)
    
    df_network_capacity = gen_power.add(links_power, fill_value=0)

    
    df_comparison = pd.DataFrame({
        "ENS Power": df_ens_capacity,
        "Network": df_network_capacity
    }).fillna(0)
    
    ### PLOT
    df_comparison.plot(kind='bar', figsize=(10, 6))
    plt.title(f"Power Comparison for Zone {zone}")
    plt.ylabel("Capacity (MW)")
    plt.show()
     
    
    
def plot_heat_comparison(df_ens_heat, network, zone='DK0'):
    # Match the zone as a node token (not an arbitrary substring), and work on a copy.
    df_ens_heat = df_ens_heat.loc[
        df_ens_heat["node"].astype("string").str.contains(
            rf"(?<![A-Za-z0-9]){zone}(?![A-Za-z0-9])", case=False, na=False, regex=True
        )
    ].copy()

    df_ens_heat["carrier"] = df_ens_heat.apply(
        lambda row: HEAT_CARRIER_MAPPING.get((row["carrier"], row["set"])), axis=1
    )
    df_ens_heat = df_ens_heat.dropna(subset=["carrier"])
    df_ens_heat_capacity = df_ens_heat.groupby("carrier")["heating_capacity"].sum()

    # Only include heat buses belonging to this zone.
    heat_buses = network.buses.index[
        network.buses.carrier.str.contains("heat", case=False, na=False)
        & network.buses.index.to_series().str.contains(
            rf"(?<![A-Za-z0-9]){zone}(?![A-Za-z0-9])", case=False, na=False, regex=True
        ).to_numpy()
    ]

    # Convert input-side nominal capacity to delivered heat capacity.
    generators_power = network.generators.loc[
        network.generators.bus.isin(heat_buses)
    ].copy()
    generators_power["capacity_MW"] = generators_power["p_nom_opt"] * generators_power["efficiency"]
    gen_power = generators_power.groupby("carrier")["capacity_MW"].sum()

    # Normal heat links output on bus1, CHP heat may be on bus2, and heat pumps
    # are named accordingly and output on bus0.
    chp_links = network.links.index.to_series().str.contains("chp", case=False, na=False)
    heat_pump_links = network.links.index.to_series().str.contains(
        "heat pump", case=False, na=False
    )
    heat_link_mask = network.links.bus1.isin(heat_buses) | (
        chp_links & network.links.bus2.isin(heat_buses)
    ) | (heat_pump_links & network.links.bus0.isin(heat_buses))
    links_power = network.links.loc[heat_link_mask].copy()
    efficiency = links_power["efficiency"].copy()
    bus2_heat_chp = (
        links_power.index.to_series().str.contains("chp", case=False, na=False)
        & links_power.bus2.isin(heat_buses)
    )
    efficiency.loc[bus2_heat_chp] = links_power.loc[bus2_heat_chp, "efficiency2"]
    links_power["capacity_MW"] = links_power["p_nom_opt"] * efficiency
    links_power = links_power.groupby("carrier")["capacity_MW"].sum()

    df_comparison = pd.DataFrame({
        "ENS Heat": df_ens_heat_capacity,
        "Network": gen_power.add(links_power, fill_value=0)
    }).fillna(0)

    df_comparison.plot(kind="bar", figsize=(10, 6))
    plt.title(f"Heat Capacity Comparison for Zone {zone}")
    plt.ylabel("Heat capacity (MW)")
    plt.show()

    return df_comparison
    
    


    
    
    
    
    
    
    




if __name__ == "__main__":

    # The notebook is located in the "notebooks" directory
    ROOT_DIR = Path(__file__).resolve().parents[1]
    DATA_DIR = ROOT_DIR / "data"
    NET_DIR = DATA_DIR / "networks"


    # Load powerplant data
    df_ens_power = pd.read_csv(DATA_DIR / "powerplants.csv")

    # Load heat plant data
    df_ens_heat = pd.read_csv(DATA_DIR / "existing_chp_heat_capacitites.csv")

    # Load network
    network = pypsa.Network(NET_DIR / "sector_w_co2_price.nc") 
    
    # add a column 'zone' based on the coordinates
    df_ens_power['zone'] = df_ens_power.apply(lambda row: coords_to_zone(row['lat'], row['lon']), axis=1)
        
    
    
    plot_power_comparison(df_ens_power, df_ens_heat, network, zone='DK0')
    
    df_comparison_heat = plot_heat_comparison(df_ens_heat, network, zone='DK0')



