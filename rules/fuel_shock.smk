configfile: "config/config.fuel_shock.yaml"

SCENARIOS = config["scenarios"]


rule all:
    input:
        expand("results/{scenario}/network_solved.nc", scenario=SCENARIOS.keys())


rule apply_fuel_shock:
    input:
        net=config["network_file"]
    output:
        net="results/{scenario}/network_shocked.nc"
    script:
        "../scripts/add_fuel_shock.py"


rule solve_dispatch:
    input:
        net="results/{scenario}/network_shocked.nc"
    output:
        net="results/{scenario}/network_solved.nc"
    script:
        "../scripts/solve_dispatch.py"