import pandas as pd
df = pd.read_csv('sp500_constituents.csv')
wdc = df[df['Symbol'] == 'WDC']
if not wdc.empty:
    print(f"WDC Sector: {wdc['GICS Sector'].iloc[0]}")
else:
    print("WDC not found in SP500 constituents")

# Also check RS_RANKER_SECTORS config
from src.config.settings import RS_RANKER_SECTORS
print(f"RS_RANKER_SECTORS: {RS_RANKER_SECTORS}")
