import pypsa
import pandas as pd

if __name__ == "__main__":
    n = pypsa.Network(snakemake.input.net)
    #n = pypsa.Network("../results/GAS_150_30D/network_solved.nc")

    # Save the results to a CSV file
    results_df = pd.DataFrame()

    # Save each generators dispatch results to the DataFrame
    for generator in n.generators.index:
        results_df[generator] = n.generators_t.p[generator]
    
    # Save for each bus the electricity price (shadow price)
    for bus in n.buses.index:
        results_df[f"price_{bus}"] = n.buses_t.marginal_price[bus]
    
    # Save the DataFrame to a CSV file
    results_df.to_csv(snakemake.output.results_csv)

