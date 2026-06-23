import pypsa
import pandas as pd

if __name__ == "__main__":

    scenario = snakemake.wildcards.scenario
    scenario_config = snakemake.config["scenarios"][scenario]

    fuels = scenario_config["fuels"] # from config get the list of fuels to apply the shock to
    shock_factor = float(scenario_config["shock_factor"]) # from config get the shock factor to apply to the marginal cost
    duration = int(scenario_config["duration"]) # from config get the duration of the shock in days

    
    # Load the base network
    n = pypsa.Network(snakemake.input.net)


    if fuels:
        fuel_mask = n.generators["carrier"].isin(fuels)
        
        affected_generators = n.generators.index[fuel_mask]

        if fuel_mask.sum() == 0:
            print("Available generator carriers:")
            print(sorted(n.generators["carrier"].dropna().unique()))
        else:
            # Determine the snapshots during which the shock will be applied
            start = n.snapshots[0]
            end = start + pd.Timedelta(days=duration)

            shock_snapshots = n.snapshots[
                (n.snapshots >= start) & (n.snapshots < end)
                ]
            
            # Make sure time-dependent marginal_cost exists
            if n.generators_t.marginal_cost.empty:
                n.generators_t.marginal_cost = pd.DataFrame(index=n.snapshots)
            
            # Add baseline marginal costs for affected generators
            for generator in affected_generators:
                if generator not in n.generators_t.marginal_cost.columns:
                    n.generators_t.marginal_cost[generator] = n.generators.loc[
                        generator, "marginal_cost"
                    ]

            # Apply shock only during selected snapshots
            n.generators_t.marginal_cost.loc[
                shock_snapshots, affected_generators
            ] *= shock_factor


    n.export_to_netcdf(snakemake.output.net)
