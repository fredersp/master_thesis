import pandas as pd
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
PEAK_HEAT = 0.006
DK1_DK2_RATIO = 0.5

MAPPING = {
    'Liquified petroleum gas (LPG)': 'gas boiler',
    'Diesel oil': 'oil boiler',
    'Natural gas': 'gas boiler',
    'Biomass': 'biomass boiler',
    'Advanced electric heating': 'air heat pump',
    'Conventional electric heating': 'resitive heater'
    
}



if __name__ == "__main__":
    
    # Load the residential heating data from the 'RES_hh_num' worksheet.
    df = pd.read_excel(
        DATA_DIR / "JRC-IDEES-2023_Residential_DK.xlsx",
        sheet_name="RES_hh_num",
    )
    
    # Extract row 3 to 12 and the column 2023 
    df_extracted = df.iloc[3:12,[df.columns.get_loc('DK - Number of households'), df.columns.get_loc(2023)]]    
    
    # New column where peak demand is mulitplied with 2023 number
    df_extracted['Peak Demand'] = df_extracted[2023] * PEAK_HEAT
    
    
    # Remove the original 2023 column and the row where 'DK - Number of households' is 'Distributed heat'
    df_extracted = df_extracted.drop(columns=[2023])
    df_extracted = df_extracted[df_extracted['DK - Number of households'] != 'Distributed heat']
    df_extracted = df_extracted[df_extracted['DK - Number of households'] != 'Geothermal']
    df_extracted = df_extracted[df_extracted['DK - Number of households'] != 'Solids']
    
    # Map the 'DK - Number of households' column to the corresponding heating technology using the MAPPING dictionary.
    df_extracted['Heating Technology'] = df_extracted['DK - Number of households'].map(MAPPING)
    
    
    
    
    # Make new dataframe with the columns node, heat_system, set, heating_capacity
    df_new = pd.DataFrame({
        'node': '',
        'heat_system': 'residential rural',
        'set': df_extracted['Heating Technology'],
        'heating_capacity': df_extracted['Peak Demand']
    })
    
    # Add new column called node for each heating technology and for both DK1 and DK0
    df_new['node'] = 'DK1 0AC'
    df_new_DK0 = df_new.copy()
    df_new_DK0['node'] = df_new_DK0['node'].str.replace('DK1 0AC', 'DK0 0AC')
    df_new = pd.concat([df_new, df_new_DK0], ignore_index=True)
    
    # use the DK1_DK2_RATIO to adjust the heating capacity for each row
    df_new['heating_capacity'] *= DK1_DK2_RATIO
    
    # Save as csv file
    df_new.to_csv(DATA_DIR / "existing_rural_heat.csv", index=False)
    
    