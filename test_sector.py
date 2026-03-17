from src.scanning.scanner import get_ticker_sector

sector = get_ticker_sector('WDC')
print(f"WDC Sector: {sector}")

from src.config.settings import RS_RANKER_SECTORS
print(f"RS_RANKER_SECTORS: {RS_RANKER_SECTORS}")
print(f"Match: {sector in RS_RANKER_SECTORS}")
