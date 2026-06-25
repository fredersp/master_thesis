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
            
            marginal_cost_t = n.generators_t.marginal_cost

            # Make sure time-dependent marginal_cost exists
            if n.generators_t.marginal_cost.empty:
                n.generators_t.marginal_cost = pd.DataFrame(index=n.snapshots)
            

            # Find affected generators that are missing as time-dependent columns
            missing_generators = affected_generators.difference(marginal_cost_t.columns)

            if len(missing_generators) > 0:
                # Create all missing columns at once
                missing_costs = pd.DataFrame(
                    {
                        generator: n.generators.loc[generator, "marginal_cost"]
                        for generator in missing_generators
                    },
                    index=n.snapshots,
                )

                marginal_cost_t = pd.concat(
                    [marginal_cost_t, missing_costs],
                    axis=1,
                )

            # Defragment dataframe
            marginal_cost_t = marginal_cost_t.copy()

            # Apply shock only to affected generators and affected snapshots
            marginal_cost_t.loc[
                shock_snapshots, affected_generators
            ] *= shock_factor

            # Put it back into the network
            n.generators_t.marginal_cost = marginal_cost_t



    n.export_to_netcdf(snakemake.output.net)
