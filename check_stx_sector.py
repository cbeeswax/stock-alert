import pandas as pd
from utils.sector_utils import get_ticker_sector
from src.config.settings import RS_RANKER_SECTORS

# Check STX sector
stx_sector = get_ticker_sector('STX')
print(f"STX Sector: {stx_sector}")
print(f"RS_RANKER_SECTORS: {RS_RANKER_SECTORS}")
print(f"STX in accepted sectors: {stx_sector in RS_RANKER_SECTORS}")
