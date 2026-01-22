import pandas as pd
from pathlib import Path
from utils.market_data import get_historical_data

EMA_FOLDER = Path("ema_data")
EMA_FOLDER.mkdir(exist_ok=True)

EMA_PERIODS = [20, 50, 200]


def compute_ema_incremental(ticker):
    """
    Loads cached EMA data (if any), updates with new price data, and saves.
    Returns a DataFrame with Close + EMA20, EMA50, EMA200.
    """
    hist_df = get_historical_data(ticker)
    if hist_df.empty or 'Close' not in hist_df.columns:
        return pd.DataFrame()

    ema_file = EMA_FOLDER / f"{ticker}_ema.csv"

    # Load cached EMA if exists
    if ema_file.exists():
        ema_df = pd.read_csv(ema_file, index_col=0, parse_dates=True)
        last_cached_date = ema_df.index[-1]
        new_data = hist_df[hist_df.index > last_cached_date]
        if new_data.empty:
            return ema_df  # up to date
        df = pd.concat([ema_df, new_data])
    else:
        df = hist_df.copy()

    # Compute or update EMAs
    for period in EMA_PERIODS:
        col = f"EMA{period}"
        alpha = 2 / (period + 1)
        if col in df.columns and ema_file.exists():
            # incremental update
            last_ema = df[col].iloc[-len(new_data) - 1] if len(new_data) > 0 else df[col].iloc[-1]
            for date, row in new_data.iterrows():
                last_ema = (row["Close"] * alpha) + (last_ema * (1 - alpha))
                df.loc[date, col] = last_ema
        else:
            # full recompute (first time)
            df[col] = df["Close"].ewm(span=period, adjust=False).mean()

    # Save updated EMA file
    df.to_csv(ema_file)
    return df

# --- Optimized RSI ---
def compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


# --- Bollinger Bands ---
def compute_bollinger_bands(series, period=20, std_dev=2):
    """
    Calculate Bollinger Bands

    Args:
        series: Price series (typically Close)
        period: Moving average period (default 20)
        std_dev: Number of standard deviations (default 2)

    Returns:
        tuple: (middle_band, upper_band, lower_band, bandwidth)
    """
    middle_band = series.rolling(period).mean()
    std = series.rolling(period).std()

    upper_band = middle_band + (std_dev * std)
    lower_band = middle_band - (std_dev * std)

    # BandWidth: measure of volatility (used for squeeze detection)
    bandwidth = (upper_band - lower_band) / middle_band * 100

    return middle_band, upper_band, lower_band, bandwidth


def compute_percent_b(price, upper_band, lower_band):
    """
    Calculate %B (Percent B)
    Shows where price is relative to Bollinger Bands

    %B = 0: Price at lower band
    %B = 0.5: Price at middle band
    %B = 1: Price at upper band
    %B < 0: Price below lower band (extremely oversold)
    %B > 1: Price above upper band (extremely overbought)

    Args:
        price: Price series
        upper_band: Upper Bollinger Band
        lower_band: Lower Bollinger Band

    Returns:
        %B series
    """
    return (price - lower_band) / (upper_band - lower_band)
