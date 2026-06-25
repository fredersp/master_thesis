import pypsa
import pandas as pd


# load network
n = pypsa.Network("base_s_10_elec_no_custom.nc")

# Generators connected to buses containing "DK0"
gens_dk0 = n.generators[
    n.generators.bus.str.contains("DK0", na=False)
]

capacity_by_carrier = (
    gens_dk0
    .groupby("carrier")["p_nom"]
    .sum()
    .sort_values(ascending=False)
)

print(capacity_by_carrier)