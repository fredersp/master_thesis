import pypsa

if __name__ == "__main__":

    solver = snakemake.config.get("solver", "gurobi")

    n = pypsa.Network(snakemake.input.net)

    n.optimize.fix_optimal_capacities()

    n.optimize(
        snapshots=n.snapshots,
        solver_name=solver,
    )

    n.export_to_netcdf(snakemake.output.net)