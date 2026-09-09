import pandas as pd
import numpy as np
import requests

from pathlib import Path
from shapely.geometry import shape


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"

END_2025 = pd.Timestamp("2025-12-31")


FUELTYPE_MAPPING = {
    "olie": "Oil",
    "naturgas": "Natural Gas",
    "fast biomasse": "Solid Biomass",
    "biogas": "Biogas",
    "affald": "Waste",
    "vandkraft": "Hydro",
    "kul": "Hard Coal",
}


TECHNOLOGY_MAPPING = {
    "Gasturbine": "OCGT",
    "Forbrændingsmotor": "Combustion Engine",
    "Dampturbine": "Steam Turbine",
    "Kombianlæg": "CCGT",
    "Bioforgasn. m. FM": "Combustion Engine",
    "Vandkraft": "Run-Of-River",
    "Nødstrømsanlæg": "Combustion Engine",
    "Organic Rankine (ORC)": np.nan,
}


WINDFARM_COORDS = {
    "Middelgrundens Havvindmøllepark": (55.6923, 12.6708),
    "Horns Rev 2": (55.6024, 7.5902),
    "Rødsand 2": (54.5265, 11.6170),
    "Anholt havvindmøllepark 1": (56.6015, 11.2291),
    "Tunø Knob Vindmøllepark": (55.9693, 10.3553),
    "MIDDELGRUNDEN": (55.6923, 12.6708),
    "Rønland Havvindmøllepark 2": (56.6704, 8.2162),
    "Rødsand": (54.5254, 11.7597),
    "Horns Rev 1": (55.4882, 7.8407),
    "Rønland Havvindmøllepark 1": (56.6704, 8.2162),
    "Horns Rev 3": (55.6876, 7.6677),
    "Kriegers Flak A": (55.0194, 12.8299),
    "Kriegers Flak B": (55.0382, 12.9926),
    "Vesterhav Nord Mølle 1 til 21": (56.6999, 8.0446),
    "Vesterhav Syd TA31 Ringkøbing": (56.0329, 8.0267),
    "Nissum Bredning Vindpark": (56.6771, 8.2518),
}


def postcode_to_coords(postcode):
    """Return centroid coordinates for a Danish postcode."""

    if pd.isna(postcode):
        return {"longitude": np.nan, "latitude": np.nan}

    postcode = str(postcode).strip()

    url = (
        f"https://api.dataforsyningen.dk/postnumre/"
        f"{postcode}?format=geojson&landpostnumre"
    )

    try:
        response = requests.get(url, timeout=10)
    except requests.RequestException:
        print(f"Could not retrieve postcode: {postcode}")
        return {"longitude": np.nan, "latitude": np.nan}

    if response.status_code != 200:
        print(f"Could not find postcode: {postcode}")
        return {"longitude": np.nan, "latitude": np.nan}

    data = response.json()

    if not data.get("geometry"):
        print(f"No geometry for postcode: {postcode}")
        return {"longitude": np.nan, "latitude": np.nan}

    centroid = shape(data["geometry"]).centroid

    return {
        "longitude": centroid.x,
        "latitude": centroid.y,
    }


def normalize_postcode(series):
    """Convert postcodes to four-character strings."""

    return (
        pd.to_numeric(series, errors="coerce")
        .astype("Int64")
        .astype("string")
        .str.zfill(4)
    )


def main():

    # ------------------------------------------------------------------
    # Load data
    # ------------------------------------------------------------------

    power_plants = pd.read_csv(
        DATA_DIR / "ENS_power_plant_register.csv",
        sep=";",
        decimal=",",
    )

    wind_and_solar = pd.read_csv(
        DATA_DIR / "ENS_wind_&_solar_register.csv",
        sep=";",
        decimal=",",
    )

    powerplantmatching = pd.read_csv(
        DATA_DIR / "powerplants_PPM.csv"
    )

    # ------------------------------------------------------------------
    # Existing PPM capacities in 2025
    # ------------------------------------------------------------------

    active_ppm = (
        (powerplantmatching["DateOut"].isna())
        | (powerplantmatching["DateOut"] > 2025)
    ) & (
        (powerplantmatching["DateIn"].isna())
        | (powerplantmatching["DateIn"] <= 2025)
    )

    df_ppm = powerplantmatching.loc[active_ppm].copy()

    total_ppm_capacity = df_ppm.loc[
        df_ppm["Country"] == "Denmark",
        "Capacity",
    ].sum()

    print(
        f"Total capacity in Denmark in PPM dataset: "
        f"{total_ppm_capacity:.2f} MW"
    )

    # ------------------------------------------------------------------
    # Prepare ENS dates and capacities
    # ------------------------------------------------------------------

    wind_and_solar["Afmeldt dato"] = pd.to_datetime(
        wind_and_solar["Afmeldt dato"],
        errors="coerce",
    )

    wind_and_solar["Idriftsdato"] = pd.to_datetime(
        wind_and_solar["Idriftsdato"],
        errors="coerce",
    )

    power_plants["skrotdato"] = pd.to_datetime(
        power_plants["skrotdato"],
        errors="coerce",
    )

    power_plants["idriftdato"] = pd.to_datetime(
        power_plants["idriftdato"],
        errors="coerce",
    )

    power_plants["elkapacitet_MW"] = pd.to_numeric(
        power_plants["elkapacitet_MW"],
        errors="coerce",
    )

    power_plants["varmekapacitet_MW"] = pd.to_numeric(
        power_plants["varmekapacitet_MW"],
        errors="coerce",
    )

    wind_and_solar["InstalleretkW"] = pd.to_numeric(
        wind_and_solar["InstalleretkW"],
        errors="coerce",
    )

    # ------------------------------------------------------------------
    # Select installations existing at the end of 2025
    # ------------------------------------------------------------------

    active_wind_solar = (
        (
            wind_and_solar["Idriftsdato"].isna()
            | (wind_and_solar["Idriftsdato"] <= END_2025)
        )
        &
        (
            wind_and_solar["Afmeldt dato"].isna()
            | (wind_and_solar["Afmeldt dato"] > END_2025)
        )
    )

    df_w_pv = wind_and_solar.loc[active_wind_solar].copy()

    active_power_plants = (
        (
            power_plants["idriftdato"].isna()
            | (power_plants["idriftdato"] <= END_2025)
        )
        &
        (
            power_plants["skrotdato"].isna()
            | (power_plants["skrotdato"] > END_2025)
        )
        &
        (
            power_plants["Hovedbrændselsgruppe"]
            != "Ej i drift i 2025"
        )
    )

    df_pp = power_plants.loc[active_power_plants].copy()

    # Only retain plants with electricity generation capacity
    df_pp = df_pp.loc[df_pp["elkapacitet_MW"] > 0].copy()

    # ------------------------------------------------------------------
    # Capacity check
    # ------------------------------------------------------------------

    total_wind_solar_capacity = (
        df_w_pv["InstalleretkW"].sum() / 1000
    )

    total_pp_capacity = df_pp["elkapacitet_MW"].sum()

    total_ens_capacity = (
        total_wind_solar_capacity + total_pp_capacity
    )

    print(
        f"Total wind and solar capacity in Denmark in ENS dataset: "
        f"{total_wind_solar_capacity:.2f} MW"
    )

    print(
        f"Total other power plant capacity in Denmark in ENS dataset: "
        f"{total_pp_capacity:.2f} MW"
    )

    print(
        f"Total capacity in Denmark in ENS dataset: "
        f"{total_ens_capacity:.2f} MW"
    )

    # ------------------------------------------------------------------
    # Process conventional / other power plants
    # ------------------------------------------------------------------

    df_pp["vaerk_postnr"] = normalize_postcode(
        df_pp["vaerk_postnr"]
    )

    # All plants already have electricity capacity > 0.
    # Therefore plants with heat capacity > 0 are CHP;
    # all others are PP.
    df_pp["Set"] = np.where(
        df_pp["varmekapacitet_MW"].fillna(0) > 0,
        "CHP",
        "PP",
    )

    df_pp["Hovedbrændselsgruppe"] = (
        df_pp["Hovedbrændselsgruppe"]
        .str.lower()
        .map(FUELTYPE_MAPPING)
    )

    df_pp["anlaegstype_navn"] = (
        df_pp["anlaegstype_navn"]
        .map(TECHNOLOGY_MAPPING)
    )

    # ------------------------------------------------------------------
    # Process wind and solar
    # ------------------------------------------------------------------

    df_w_pv["Postnr."] = normalize_postcode(
        df_w_pv["Postnr."]
    )

    # Convert ENS categories to PPM fuel types
    df_w_pv["Kategori"] = np.where(
        df_w_pv["Kategori"] == "Solcelle",
        "Solar",
        "Wind",
    )

    # Determine technology
    df_w_pv["Technology"] = np.select(
    [
        (df_w_pv["Kategori"] == "Wind")
        & (df_w_pv["Placering"] == "HAV"),

        (df_w_pv["Kategori"] == "Wind")
        & (df_w_pv["Placering"] == "LAND"),

        df_w_pv["Kategori"] == "Solar",
    ],
    [
        "Offshore",
        "Onshore",
        "PV",
    ],
    default=pd.NA,
    )

    df_w_pv["Set"] = "PP"

    # ------------------------------------------------------------------
    # Coordinates
    # ------------------------------------------------------------------

    # Use postcodes occurring in either ENS dataset
    postcodes = pd.unique(
        pd.concat(
            [
                df_pp["vaerk_postnr"],
                df_w_pv["Postnr."],
            ]
        ).dropna()
    )

    postcode_coords = {
        postcode: postcode_to_coords(postcode)
        for postcode in postcodes
    }

    df_pp["lon"] = df_pp["vaerk_postnr"].map(
        lambda p: postcode_coords.get(
            p, {}
        ).get("longitude", np.nan)
    )

    df_pp["lat"] = df_pp["vaerk_postnr"].map(
        lambda p: postcode_coords.get(
            p, {}
        ).get("latitude", np.nan)
    )

    df_w_pv["lon"] = df_w_pv["Postnr."].map(
        lambda p: postcode_coords.get(
            p, {}
        ).get("longitude", np.nan)
    )

    df_w_pv["lat"] = df_w_pv["Postnr."].map(
        lambda p: postcode_coords.get(
            p, {}
        ).get("latitude", np.nan)
    )

    # Override postcode centroids with actual offshore wind-farm coordinates
    windfarm_overrides = df_w_pv["Navn"].map(
        WINDFARM_COORDS
    )

    mask = windfarm_overrides.notna()

    df_w_pv.loc[mask, "lat"] = (
        windfarm_overrides.loc[mask].str[0]
    )

    df_w_pv.loc[mask, "lon"] = (
        windfarm_overrides.loc[mask].str[1]
    )

    # ------------------------------------------------------------------
    # Convert ENS datasets to PPM structure
    # ------------------------------------------------------------------

    df_pp_final = pd.DataFrame({
        "Name": (
            df_pp["fv_net_navn"].fillna("")
            + " ("
            + df_pp["vrkanl_ny"].fillna("")
            + ")"
        ),
        "Fueltype": df_pp["Hovedbrændselsgruppe"],
        "Technology": df_pp["anlaegstype_navn"],
        "Set": df_pp["Set"],
        "Country": "Denmark",
        "Capacity": df_pp["elkapacitet_MW"],
        "Efficiency": np.nan,
        "DateIn": df_pp["idriftdato"].dt.year,
        "DateRetrofit": np.nan,
        "DateOut": df_pp["skrotdato"].dt.year,
        "lat": df_pp["lat"],
        "lon": df_pp["lon"],
        "Duration": np.nan,
        "Volume_Mm3": np.nan,
        "DamHeight_m": np.nan,
        "StorageCapacity_MWh": np.nan,
        "EIC": "{}",
        "projectID": "{}",
    })

    df_w_pv_final = pd.DataFrame({
        "Name": (
            df_w_pv["Navn"].fillna("").astype(str)
            + " ("
            + df_w_pv["Stamdata GSRN"].fillna("").astype(str)
            + ")"
        ),
        "Fueltype": df_w_pv["Kategori"],
        "Technology": df_w_pv["Technology"],
        "Set": df_w_pv["Set"],
        "Country": "Denmark",
        "Capacity": df_w_pv["InstalleretkW"] / 1000,
        "Efficiency": np.nan,
        "DateIn": df_w_pv["Idriftsdato"].dt.year,
        "DateRetrofit": np.nan,
        "DateOut": df_w_pv["Afmeldt dato"].dt.year,
        "lat": df_w_pv["lat"],
        "lon": df_w_pv["lon"],
        "Duration": np.nan,
        "Volume_Mm3": np.nan,
        "DamHeight_m": np.nan,
        "StorageCapacity_MWh": np.nan,
        "EIC": "{}",
        "projectID": "{}",
    })

    # ------------------------------------------------------------------
    # Replace Denmark in PPM dataset with ENS data
    # ------------------------------------------------------------------

    df_ppm = df_ppm.loc[
        df_ppm["Country"] != "Denmark"
    ].copy()

    df_ppm = pd.concat(
        [
            df_ppm,
            df_pp_final,
            df_w_pv_final,
        ],
        ignore_index=True,
    )

    df_ppm["id"] = df_ppm.index

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    output_path = DATA_DIR / "powerplants.csv"

    df_ppm.to_csv(
        output_path,
        index=False,
    )

    print(f"Saved processed dataset to: {output_path}")


if __name__ == "__main__":
    main()