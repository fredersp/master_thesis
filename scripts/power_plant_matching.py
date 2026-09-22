import pandas as pd
import numpy as np
import requests

from pathlib import Path
from shapely.geometry import shape
from pyproj import Transformer


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"

END_2025 = pd.Timestamp("2025-12-31")


# ------------------------------------------------------------------
# Mappings
# ------------------------------------------------------------------

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


# ------------------------------------------------------------------
# Manually specified offshore wind farm coordinates
#
# Format:
# "Name": (latitude, longitude)
# ------------------------------------------------------------------

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


# ------------------------------------------------------------------
# Coordinate transformer
#
# ENS UTM coordinates:
# ETRS89 / UTM zone 32N = EPSG:25832
#
# Output:
# WGS84 longitude / latitude = EPSG:4326
# ------------------------------------------------------------------

UTM_TO_WGS84 = Transformer.from_crs(
    "EPSG:25832",
    "EPSG:4326",
    always_xy=True,
)


# ------------------------------------------------------------------
# Functions
# ------------------------------------------------------------------

def postcode_to_coords(postcode):
    """
    Return centroid coordinates for a Danish postcode.

    Returns
    -------
    dict
        {
            "longitude": ...,
            "latitude": ...
        }
    """

    if pd.isna(postcode):
        return {
            "longitude": np.nan,
            "latitude": np.nan,
        }

    postcode = str(postcode).strip()

    url = (
        f"https://api.dataforsyningen.dk/postnumre/"
        f"{postcode}?format=geojson&landpostnumre"
    )

    try:
        response = requests.get(
            url,
            timeout=10,
        )

    except requests.RequestException:

        print(
            f"Could not retrieve postcode: "
            f"{postcode}"
        )

        return {
            "longitude": np.nan,
            "latitude": np.nan,
        }

    if response.status_code != 200:

        print(
            f"Could not find postcode: "
            f"{postcode}"
        )

        return {
            "longitude": np.nan,
            "latitude": np.nan,
        }

    data = response.json()

    if not data.get("geometry"):

        print(
            f"No geometry for postcode: "
            f"{postcode}"
        )

        return {
            "longitude": np.nan,
            "latitude": np.nan,
        }

    centroid = shape(
        data["geometry"]
    ).centroid

    return {
        "longitude": centroid.x,
        "latitude": centroid.y,
    }


def normalize_postcode(series):
    """
    Convert Danish postcodes to four-character strings.

    Example:
        800 -> "0800"
        2100 -> "2100"
    """

    return (
        pd.to_numeric(
            series,
            errors="coerce",
        )
        .astype("Int64")
        .astype("string")
        .str.zfill(4)
    )


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def main():

    # Load data

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
        (
            powerplantmatching["DateOut"].isna()
            | (powerplantmatching["DateOut"] > 2025)
        )
        &
        (
            powerplantmatching["DateIn"].isna()
            | (powerplantmatching["DateIn"] <= 2025)
        )
    )

    df_ppm = (
        powerplantmatching
        .loc[active_ppm]
        .copy()
    )

    total_ppm_capacity = (
        df_ppm.loc[
            df_ppm["Country"] == "Denmark",
            "Capacity",
        ]
        .sum()
    )

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
            | (
                wind_and_solar["Idriftsdato"]
                <= END_2025
            )
        )
        &
        (
            wind_and_solar["Afmeldt dato"].isna()
            | (
                wind_and_solar["Afmeldt dato"]
                > END_2025
            )
        )
    )

    df_w_pv = (
        wind_and_solar
        .loc[active_wind_solar]
        .copy()
    )


    active_power_plants = (
        (
            power_plants["idriftdato"].isna()
            | (
                power_plants["idriftdato"]
                <= END_2025
            )
        )
        &
        (
            power_plants["skrotdato"].isna()
            | (
                power_plants["skrotdato"]
                > END_2025
            )
        )
        &
        (
            power_plants["Hovedbrændselsgruppe"]
            != "Ej i drift i 2025"
        )
    )

    df_pp = (
        power_plants
        .loc[active_power_plants]
        .copy()
    )


    # Only retain plants with electricity generation capacity
    df_pp = (
        df_pp
        .loc[
            df_pp["elkapacitet_MW"] > 0
        ]
        .copy()
    )


    # ------------------------------------------------------------------
    # Capacity check
    # ------------------------------------------------------------------

    total_wind_solar_capacity = (
        df_w_pv["InstalleretkW"].sum()
        / 1000
    )

    total_pp_capacity = (
        df_pp["elkapacitet_MW"].sum()
    )

    total_ens_capacity = (
        total_wind_solar_capacity
        + total_pp_capacity
    )


    print(
        f"Total wind and solar capacity in Denmark "
        f"in ENS dataset: "
        f"{total_wind_solar_capacity:.2f} MW"
    )

    print(
        f"Total other power plant capacity in Denmark "
        f"in ENS dataset: "
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
    #
    # Therefore:
    #
    # heat capacity > 0 -> CHP
    # heat capacity = 0 -> PP

    df_pp["Set"] = np.where(
        df_pp[
            "varmekapacitet_MW"
        ].fillna(0) > 0,
        "CHP",
        "PP",
    )

    df_pp = df_pp.loc[
        df_pp["Set"].eq("PP")
    ].copy()
    df_pp["Set"] = "PP"


    # Map fuel types

    df_pp["Hovedbrændselsgruppe"] = (
        df_pp["Hovedbrændselsgruppe"]
        .str.lower()
        .map(FUELTYPE_MAPPING)
    )


    # Map technologies

    df_pp["anlaegstype_navn"] = (
        df_pp["anlaegstype_navn"]
        .map(TECHNOLOGY_MAPPING)
    )

    # If the technology is CCGT or OCGT and the fuel type is not Natural Gas, then set Technology to steam turbine
    df_pp["anlaegstype_navn"] = np.where(
        (df_pp["anlaegstype_navn"].isin(["CCGT", "OCGT"]))
        & (df_pp["Hovedbrændselsgruppe"] != "natural gas"),
        "Steam Turbine",
        df_pp["anlaegstype_navn"],
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
            (
                (df_w_pv["Kategori"] == "Wind")
                &
                (df_w_pv["Placering"] == "HAV")
            ),

            (
                (df_w_pv["Kategori"] == "Wind")
                &
                (df_w_pv["Placering"] == "LAND")
            ),

            (
                df_w_pv["Kategori"]
                == "Solar"
            ),
        ],
        [
            "Offshore",
            "Onshore",
            "PV",
        ],
        default=pd.NA,
    )


    df_w_pv["Set"] = "PP"


    # ==================================================================
    # COORDINATES
    # ==================================================================

    # ------------------------------------------------------------------
    # Conventional power plants
    #
    # Use postcode centroid
    # ------------------------------------------------------------------

    postcodes_pp = (
        df_pp["vaerk_postnr"]
        .dropna()
        .unique()
    )


    postcode_coords_pp = {
        postcode: postcode_to_coords(postcode)
        for postcode in postcodes_pp
    }


    df_pp["lon"] = (
        df_pp["vaerk_postnr"]
        .map(
            lambda p:
            postcode_coords_pp
            .get(p, {})
            .get(
                "longitude",
                np.nan,
            )
        )
    )


    df_pp["lat"] = (
        df_pp["vaerk_postnr"]
        .map(
            lambda p:
            postcode_coords_pp
            .get(p, {})
            .get(
                "latitude",
                np.nan,
            )
        )
    )


    # ------------------------------------------------------------------
    # Wind and solar
    #
    # Coordinate priority:
    #
    # 1. Manual wind farm coordinates
    # 2. UTM coordinates
    # 3. Postcode centroid
    # 4. NaN if nothing is available
    # ------------------------------------------------------------------


    # ------------------------------------------------------------------
    # Convert UTM coordinate columns to numeric
    # ------------------------------------------------------------------

    for col in ["UTM x-koordinat", "UTM y-koordinat"]:
        df_w_pv[col] = (
            df_w_pv[col]
            .astype("string")
            .str.replace(".", "", regex=False)
            .str.replace(",", ".", regex=False)
        )

        df_w_pv[col] = pd.to_numeric(
            df_w_pv[col],
            errors="coerce"
        )


    # ------------------------------------------------------------------
    # Identify rows where both UTM coordinates are available
    # ------------------------------------------------------------------

    mask_utm = (
        df_w_pv["UTM x-koordinat"].notna()
        & df_w_pv["UTM y-koordinat"].notna()
    )


    # ------------------------------------------------------------------
    # Convert UTM -> longitude / latitude
    # ------------------------------------------------------------------

    if mask_utm.any():

        lon, lat = UTM_TO_WGS84.transform(
            df_w_pv.loc[
                mask_utm,
                "UTM x-koordinat"
            ].to_numpy(dtype=float),

            df_w_pv.loc[
                mask_utm,
                "UTM y-koordinat"
            ].to_numpy(dtype=float),
        )

        df_w_pv.loc[mask_utm, "lon"] = lon
        df_w_pv.loc[mask_utm, "lat"] = lat

    # ------------------------------------------------------------------
    # If UTM coordinates are missing:
    # use postcode centroid
    # ------------------------------------------------------------------

    mask_postcode = (
        ~mask_utm
        &
        df_w_pv[
            "Postnr."
        ].notna()
    )


    postcodes_w_pv = (
        df_w_pv.loc[
            mask_postcode,
            "Postnr.",
        ]
        .dropna()
        .unique()
    )


    postcode_coords_w_pv = {
        postcode: postcode_to_coords(postcode)
        for postcode in postcodes_w_pv
    }


    df_w_pv.loc[
        mask_postcode,
        "lon",
    ] = (
        df_w_pv.loc[
            mask_postcode,
            "Postnr.",
        ]
        .map(
            lambda p:
            postcode_coords_w_pv
            .get(p, {})
            .get(
                "longitude",
                np.nan,
            )
        )
    )


    df_w_pv.loc[
        mask_postcode,
        "lat",
    ] = (
        df_w_pv.loc[
            mask_postcode,
            "Postnr.",
        ]
        .map(
            lambda p:
            postcode_coords_w_pv
            .get(p, {})
            .get(
                "latitude",
                np.nan,
            )
        )
    )


    # ------------------------------------------------------------------
    # Manual wind farm coordinates
    #
    # These override BOTH:
    #
    # - UTM coordinates
    # - postcode coordinates
    #
    # Therefore the manually specified wind farm coordinates
    # always have highest priority.
    # ------------------------------------------------------------------

    windfarm_overrides = (
        df_w_pv["Navn"]
        .map(WINDFARM_COORDS)
    )


    mask_windfarm = (
        windfarm_overrides
        .notna()
    )


    df_w_pv.loc[
        mask_windfarm,
        "lat",
    ] = (
        windfarm_overrides
        .loc[mask_windfarm]
        .str[0]
    )


    df_w_pv.loc[
        mask_windfarm,
        "lon",
    ] = (
        windfarm_overrides
        .loc[mask_windfarm]
        .str[1]
    )


    # ------------------------------------------------------------------
    # Record where coordinates came from
    # ------------------------------------------------------------------

    df_w_pv["coordinate_source"] = np.select(
        [
            mask_windfarm,
            mask_utm,
            mask_postcode,
        ],
        [
            "Manual wind farm",
            "UTM",
            "Postcode",
        ],
        default="Missing",
    )


    # ------------------------------------------------------------------
    # Coordinate checks
    # ------------------------------------------------------------------

    print(
        "\n-------------------------------------"
    )

    print(
        "Wind / solar coordinate sources"
    )

    print(
        "-------------------------------------"
    )

    print(
        df_w_pv[
            "coordinate_source"
        ].value_counts()
    )


    print(
        "\nCapacity by coordinate source [MW]:"
    )

    capacity_by_coordinate_source = (
        df_w_pv
        .groupby(
            "coordinate_source"
        )[
            "InstalleretkW"
        ]
        .sum()
        .div(1000)
    )

    print(
        capacity_by_coordinate_source
    )


    # ------------------------------------------------------------------
    # Check remaining installations without coordinates
    # ------------------------------------------------------------------

    missing_coordinates = (
        df_w_pv[
            df_w_pv["lat"].isna()
            |
            df_w_pv["lon"].isna()
        ]
        .copy()
    )


    print(
        "\nInstallations without coordinates:"
    )

    print(
        len(
            missing_coordinates
        )
    )


    print(
        "Capacity without coordinates:"
    )

    print(
        f"{missing_coordinates['InstalleretkW'].sum() / 1000:.2f} MW"
    )


    # Optional detailed check

    if not missing_coordinates.empty:

        print(
            "\nInstallations still missing coordinates:"
        )

        print(
            missing_coordinates[
                [
                    "Navn",
                    "Kategori",
                    "Technology",
                    "Postnr.",
                    "UTM x-koordinat",
                    "UTM y-koordinat",
                    "InstalleretkW",
                ]
            ]
        )


    # ------------------------------------------------------------------
    # Convert ENS datasets to PPM structure
    # ------------------------------------------------------------------

    df_pp_final = pd.DataFrame(
        {
            "Name": (
                df_pp[
                    "fv_net_navn"
                ].fillna("")
                + " ("
                + df_pp[
                    "vrkanl_ny"
                ].fillna("")
                + ")"
            ),

            "Fueltype":
                df_pp[
                    "Hovedbrændselsgruppe"
                ],

            "Technology":
                df_pp[
                    "anlaegstype_navn"
                ],

            "Set":
                df_pp["Set"].astype(str),

            "Country":
                "Denmark",

            "Capacity":
                df_pp[
                    "elkapacitet_MW"
                ],

            "Efficiency":
                np.nan,

            "DateIn":
                df_pp[
                    "idriftdato"
                ].dt.year,

            "DateRetrofit":
                np.nan,

            "DateOut":
                df_pp[
                    "skrotdato"
                ].dt.year,

            "lat":
                df_pp["lat"],

            "lon":
                df_pp["lon"],

            "Duration":
                np.nan,

            "Volume_Mm3":
                np.nan,

            "DamHeight_m":
                np.nan,

            "StorageCapacity_MWh":
                np.nan,

            "EIC":
                "{}",

            "projectID":
                "{}",
        }
    )


    df_w_pv_final = pd.DataFrame(
        {
            "Name": (
                df_w_pv[
                    "Navn"
                ]
                .fillna("")
                .astype(str)
                + " ("
                + df_w_pv[
                    "Stamdata GSRN"
                ]
                .fillna("")
                .astype(str)
                + ")"
            ),

            "Fueltype":
                df_w_pv[
                    "Kategori"
                ],

            "Technology":
                df_w_pv[
                    "Technology"
                ],

            "Set":
                df_w_pv[
                    "Set"
                ],

            "Country":
                "Denmark",

            "Capacity":
                df_w_pv[
                    "InstalleretkW"
                ] / 1000,

            "Efficiency":
                np.nan,

            "DateIn":
                df_w_pv[
                    "Idriftsdato"
                ].dt.year,

            "DateRetrofit":
                np.nan,

            "DateOut":
                df_w_pv[
                    "Afmeldt dato"
                ].dt.year,

            "lat":
                df_w_pv[
                    "lat"
                ],

            "lon":
                df_w_pv[
                    "lon"
                ],

            "Duration":
                np.nan,

            "Volume_Mm3":
                np.nan,

            "DamHeight_m":
                np.nan,

            "StorageCapacity_MWh":
                np.nan,

            "EIC":
                "{}",

            "projectID":
                "{}",
        }
    )


    # ------------------------------------------------------------------
    # Replace Denmark in PPM dataset with ENS data
    # ------------------------------------------------------------------

    df_ppm = (
        df_ppm.loc[
            df_ppm["Country"]
            != "Denmark"
        ]
        .copy()
    )


    df_ppm = pd.concat(
        [
            df_ppm,
            df_pp_final,
            df_w_pv_final,
        ],
        ignore_index=True,
    )


    df_ppm["id"] = (
        df_ppm.index
    )


    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    output_path = (
        DATA_DIR
        / "powerplants.csv"
    )


    df_ppm.to_csv(
        output_path,
        index=False,
    )


    print(
        f"\nSaved processed dataset to: "
        f"{output_path}"
    )


# ------------------------------------------------------------------
# Run
# ------------------------------------------------------------------

if __name__ == "__main__":
    main()