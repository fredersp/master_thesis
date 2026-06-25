configfile: "config/config.fuel_shock.yaml"

SCENARIOS = config["scenarios"]


rule all:
    input:
        expand("results/{scenario}/time_indexed_results.csv", scenario=SCENARIOS.keys())


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

rule save_results:
    input:
        net="results/{scenario}/network_solved.nc"
    output:
        results_csv="results/{scenario}/time_indexed_results.csv"
    script:
        "../scripts/save_results.py"


# rule plot_results:
#     input:
#         results_csv="results/{scenario}/time_indexed_results.csv"
#     output:
#         plot_png="results/{scenario}/plots/"
#     script:
#         "../scripts/plot_results.py"