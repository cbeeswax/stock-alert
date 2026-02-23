# API Reference

This document provides detailed API reference for key modules in the Stock Alert system.

## Table of Contents

1. [Data Module](#data-module)
2. [Scanning Module](#scanning-module)
3. [Position Management](#position-management)
4. [Strategies](#strategies)
5. [Analysis Module](#analysis-module)
6. [Configuration](#configuration)

---

## Data Module

### `src.data.market`

Provides market data retrieval and caching.

#### Functions

##### `get_historical_data(ticker, start_date=None, end_date=None)`

Fetch historical OHLCV data for a ticker.

**Parameters:**
- `ticker` (str): Stock ticker symbol (e.g., 'AAPL')
- `start_date` (datetime, optional): Start date. Default: 2 years ago
- `end_date` (datetime, optional): End date. Default: today

**Returns:**
- `pd.DataFrame`: DataFrame with columns [Date, Open, High, Low, Close, Volume]

**Example:**
```python
from src.data.market import get_historical_data

data = get_historical_data('AAPL', start_date='2023-01-01', end_date='2023-12-31')
print(data.head())
print(f"Downloaded {len(data)} rows")
```

**Notes:**
- Data is cached to avoid repeated downloads
- Returns sorted by date (oldest first)
- May return fewer rows if data unavailable

##### `get_multiple_tickers(tickers, start_date=None, end_date=None)`

Fetch data for multiple tickers.

**Parameters:**
- `tickers` (list): List of ticker symbols
- `start_date` (datetime, optional): Start date
- `end_date` (datetime, optional): End date

**Returns:**
- `dict`: {ticker: DataFrame} for each ticker

**Example:**
```python
tickers = ['AAPL', 'MSFT', 'GOOGL']
data = get_multiple_tickers(tickers)
for ticker, df in data.items():
    print(f"{ticker}: {len(df)} rows")
```

---

## Scanning Module

### `src.scanning.scanner`

Main scanning engine for generating trading signals.

#### Functions

##### `run_scan(tickers, date=None)`

Run all strategies on given tickers for a specific date.

**Parameters:**
- `tickers` (list): List of ticker symbols
- `date` (datetime, optional): Scan date. Default: today

**Returns:**
- `list`: List of signal dictionaries

**Signal Format:**
```python
{
    'Ticker': 'AAPL',
    'Date': datetime(2023, 6, 15),
    'Strategy': 'RelativeStrength_Ranker_Position',
    'Entry': 150.25,
    'StopLoss': 145.00,
    'Target': 165.50,
    'Score': 7.8,  # 0-10 scale
    'Confidence': 0.82,  # 0-1 scale
    'Reason': 'Breakout above 50-MA with rising RSI',
}
```

**Example:**
```python
from src.scanning.scanner import run_scan

signals = run_scan(['AAPL', 'MSFT', 'GOOGL'])
print(f"Found {len(signals)} signals")
for signal in signals:
    print(f"{signal['Ticker']}: ${signal['Entry']:.2f}")
```

##### `run_scan_as_of(date, tickers)`

Run scan for historical date (used in backtesting).

**Parameters:**
- `date` (datetime): Historical date to scan
- `tickers` (list): Ticker symbols

**Returns:**
- `list`: Signal list as of that date

**Example:**
```python
from datetime import datetime
from src.scanning.scanner import run_scan_as_of

date = datetime(2022, 6, 15)
signals = run_scan_as_of(date, ['AAPL', 'MSFT'])
```

### `src.scanning.validator`

Pre-buy signal validation and filtering.

#### Functions

##### `pre_buy_check(signals, benchmark='QQQ', min_score=6.0)`

Validate and format signals for trading.

**Parameters:**
- `signals` (list): Raw signals from scanner
- `benchmark` (str): Benchmark for regime check (default: 'QQQ')
- `min_score` (float): Minimum score threshold (default: 6.0)

**Returns:**
- `pd.DataFrame`: Validated signals with format:
  - Ticker, Date, Strategy, Entry, StopLoss, Target, Score, Confidence, Reason

**Example:**
```python
from src.scanning.validator import pre_buy_check

validated = pre_buy_check(signals, min_score=7.0)
print(f"Valid signals: {len(validated)}")
```

**Validation Checks:**
- Score > min_score
- Price relationships valid (stop < entry < target)
- Risk/reward ratio acceptable
- Deduplication (only highest score kept per ticker)

---

## Position Management

### `src.position_management.tracker`

Track open positions and trade history.

#### Class: `PositionTracker`

**Constructor:**
```python
PositionTracker(mode='live', file='data/open_positions.json')
```

**Parameters:**
- `mode` (str): 'live' or 'backtest'
- `file` (str): Path to positions JSON file

**Methods:**

##### `add_position(ticker, entry_price, entry_date, strategy, stop_loss, target, max_days=150)`

Add new position.

**Parameters:**
- `ticker` (str): Stock ticker
- `entry_price` (float): Entry price
- `entry_date` (datetime): Entry date
- `strategy` (str): Strategy name
- `stop_loss` (float): Stop loss price
- `target` (float): Target/profit price
- `max_days` (int): Maximum days to hold (default: 150)

**Returns:**
- `bool`: Success

**Example:**
```python
from datetime import datetime
from src.position_management.tracker import PositionTracker

tracker = PositionTracker()
success = tracker.add_position(
    ticker='AAPL',
    entry_price=150.25,
    entry_date=datetime.now(),
    strategy='RelativeStrength_Ranker_Position',
    stop_loss=145.00,
    target=165.50
)
```

##### `get_position(ticker)`

Get position details.

**Parameters:**
- `ticker` (str): Stock ticker

**Returns:**
- `dict`: Position details or None if not found

**Position Format:**
```python
{
    'entry_price': 150.25,
    'entry_date': datetime(2023, 6, 15),
    'strategy': 'RelativeStrength_Ranker_Position',
    'stop_loss': 145.00,
    'target': 165.50,
    'max_days': 150,
    'status': 'open'
}
```

##### `get_all_positions()`

Get all open positions.

**Returns:**
- `dict`: {ticker: position_dict} for each position

##### `get_position_count()`

Get number of open positions.

**Returns:**
- `int`: Number of positions

##### `close_position(ticker, exit_price)`

Close position.

**Parameters:**
- `ticker` (str): Stock ticker
- `exit_price` (float): Exit price

**Returns:**
- `bool`: Success

##### `save_positions()`

Save positions to JSON file.

##### `load_positions()`

Load positions from JSON file.

**Example:**
```python
tracker = PositionTracker()
positions = tracker.get_all_positions()

for ticker, pos in positions.items():
    entry = pos['entry_price']
    current = 155.00  # Current price
    profit = current - entry
    pct = (profit / entry) * 100
    print(f"{ticker}: {entry:.2f} → {current:.2f} ({pct:+.1f}%)")
```

### `src.position_management.monitor`

Monitor positions for exit signals.

#### Functions

##### `monitor_positions(tracker)`

Check all positions for action signals.

**Parameters:**
- `tracker` (PositionTracker): Position tracker instance

**Returns:**
- `dict`: Action signals with keys:
  - `exits`: Positions to close
  - `partials`: Partial profit opportunities
  - `pyramids`: Add-on opportunities
  - `warnings`: Risk warnings

**Example:**
```python
from src.position_management.monitor import monitor_positions

signals = monitor_positions(tracker)

for exit in signals['exits']:
    print(f"EXIT {exit['ticker']}: {exit['reason']}")

for partial in signals['partials']:
    print(f"PARTIAL {partial['ticker']}: {partial['reason']}")
```

**Signal Format:**
```python
{
    'ticker': 'AAPL',
    'type': 'stop_loss',  # or 'profit_target', 'time_based'
    'reason': 'Stop loss hit at $145.00',
    'action': 'Sell all shares at market',
    'price': 144.95
}
```

---

## Strategies

### Base Strategy Interface

All strategies implement this interface:

#### Class: `Strategy`

**Methods:**

##### `scan(data, ticker=None, as_of_date=None)`

Generate signals from market data.

**Parameters:**
- `data` (pd.DataFrame): OHLCV data
- `ticker` (str, optional): Ticker name
- `as_of_date` (datetime, optional): Scan date

**Returns:**
- `list`: List of signal dictionaries

**Signal Format:**
```python
{
    'Ticker': 'AAPL',
    'Date': datetime(2023, 6, 15),
    'Entry': 150.25,
    'StopLoss': 145.00,
    'Target': 165.50,
    'Score': 7.8,
    'Confidence': 0.82,
    'Reason': 'Brief explanation'
}
```

### `src.strategies.relative_strength`

#### Class: `RelativeStrengthRanker`

Ranks stocks by relative strength momentum.

**Parameters:**
- `lookback_weeks` (int): Historical lookback (default: 52)
- `ma_period` (int): Moving average period (default: 50)
- `rsi_period` (int): RSI period (default: 14)

**Entry Criteria:**
- Price above 50-day MA
- RSI > 40 (not overbought before breakout)
- Price at new highs relative to consolidation
- Volume confirmation

**Exit Criteria:**
- Close below 50-day MA
- Reached profit target
- Exceeded 150 days

### `src.strategies.high_52_week`

#### Class: `High52WeekBreakout`

Finds breakouts near 52-week highs.

**Parameters:**
- `lookback_weeks` (int): Historical lookback (default: 52)
- `bb_length` (int): Bollinger Band period (default: 20)
- `bb_std` (float): Bollinger Band std dev (default: 2)

**Entry Criteria:**
- Price within 2% of 52-week high
- Bollinger Bands tightening (consolidation)
- Breakout above upper band
- Volume confirmation

**Exit Criteria:**
- Close outside Bollinger Bands
- Reached profit target
- Exceeded 150 days

### `src.strategies.big_base`

#### Class: `BigBaseBreakout`

Identifies large consolidation bases and breakouts.

**Parameters:**
- `consolidation_length` (int): Base size (default: 20)
- `bb_length` (int): Bollinger Band period (default: 20)
- `bb_std` (float): Bollinger Band std dev (default: 2)

**Entry Criteria:**
- Long consolidation period (>10 days)
- Tight price range (< 5% range)
- Breakout above consolidation
- Volume surge on breakout

**Exit Criteria:**
- Close back into consolidation
- Reached profit target
- Exceeded 100 days

---

## Analysis Module

### `src.analysis.backtest`

#### Functions

##### `run_backtest(start_date, end_date, strategies=None, initial_equity=100000)`

Run historical backtest.

**Parameters:**
- `start_date` (datetime): Backtest start date
- `end_date` (datetime): Backtest end date
- `strategies` (str or list, optional): Specific strategies to test
- `initial_equity` (float): Starting capital (default: 100000)

**Returns:**
- `dict`: Backtest results with keys:
  - `total_return_pct`: Total return percentage
  - `win_rate`: Percentage of winning trades
  - `profit_factor`: Total wins / Total losses
  - `trades`: List of individual trade results
  - `metrics`: Dictionary of performance metrics

**Example:**
```python
from src.analysis.backtest import run_backtest
from datetime import datetime

results = run_backtest(
    start_date=datetime(2022, 1, 1),
    end_date=datetime(2023, 1, 1),
    strategies='RelativeStrength_Ranker_Position'
)

print(f"Return: {results['total_return_pct']:.2f}%")
print(f"Win Rate: {results['win_rate']:.1%}")
print(f"Profit Factor: {results['profit_factor']:.2f}")
```

**Trade Format:**
```python
{
    'ticker': 'AAPL',
    'entry_date': datetime(2023, 6, 15),
    'exit_date': datetime(2023, 7, 20),
    'entry_price': 150.25,
    'exit_price': 165.50,
    'strategy': 'RelativeStrength_Ranker_Position',
    'exit_reason': 'profit_target',
    'profit_pct': 10.15,
    'profit_amount': 2275.00,
    'bars_held': 21
}
```

### `src.analysis.metrics`

#### Functions

##### `calculate_metrics(trades)`

Calculate performance metrics from trade list.

**Parameters:**
- `trades` (list): List of trade dictionaries

**Returns:**
- `dict`: Metrics dictionary with keys:
  - `total_return_pct`: Total return %
  - `win_rate`: Percentage of winning trades
  - `profit_factor`: Gross profit / Gross loss
  - `avg_winner`: Average winning trade %
  - `avg_loser`: Average losing trade %
  - `expectancy`: Average P/L per trade
  - `max_consecutive_wins`: Longest win streak
  - `max_consecutive_losses`: Longest loss streak

---

## Configuration

### `src.config.settings`

Global configuration constants.

**Key Settings:**

```python
# Position Sizing
POSITION_MAX_TOTAL = 20  # Max concurrent positions
POSITION_MAX_PER_STRATEGY = {
    'RelativeStrength_Ranker_Position': 10,
    'High52_Position': 6,
    'BigBase_Breakout_Position': 4,
}

# Risk Management
POSITION_RISK_PER_TRADE_PCT = 2.0  # Risk % of equity per trade
POSITION_INITIAL_EQUITY = 100000  # Starting capital for backtests

# Market Regime
REGIME_INDEX = 'QQQ'  # Index for bull/bear regime
UNIVERSAL_QQQ_BULL_MA = 100  # MA period for regime check

# Data Filters
MIN_VOLUME = 500000  # Minimum daily volume
MIN_PRICE = 5.0  # Minimum stock price
```

### `src.config.strategies`

Strategy-specific parameters. Each strategy has:

```python
{
    'lookback_weeks': 52,
    'ma_period': 50,
    'rsi_period': 14,
    'score_threshold': 6.0,
    'max_days': 150,
    # ... strategy-specific params
}
```

---

## Examples

### Complete Scanning Example

```python
from src.scanning.scanner import run_scan
from src.scanning.validator import pre_buy_check
from src.position_management.tracker import PositionTracker

# Load S&P 500 tickers
tickers = pd.read_csv('data/sp500_constituents.csv')['Symbol'].tolist()

# Run scanner
signals = run_scan(tickers)
print(f"Raw signals: {len(signals)}")

# Validate signals
trade_ready = pre_buy_check(signals, min_score=7.0)
print(f"Trade-ready: {len(trade_ready)}")

# Manage positions
tracker = PositionTracker()
for _, trade in trade_ready.iterrows():
    tracker.add_position(
        ticker=trade['Ticker'],
        entry_price=trade['Entry'],
        strategy=trade['Strategy'],
        stop_loss=trade['StopLoss'],
        target=trade['Target'],
    )

# Monitor positions
from src.position_management.monitor import monitor_positions
signals = monitor_positions(tracker)
for exit in signals['exits']:
    print(f"EXIT: {exit['ticker']}")
```

### Backtesting Example

```python
from src.analysis.backtest import run_backtest
from datetime import datetime

# Run backtest
results = run_backtest(
    start_date=datetime(2021, 1, 1),
    end_date=datetime(2023, 1, 1),
    strategies=['RelativeStrength_Ranker_Position'],
)

# Display results
print(f"Total Return: {results['total_return_pct']:.2f}%")
print(f"Win Rate: {results['win_rate']:.1%}")
print(f"Profit Factor: {results['profit_factor']:.2f}")
print(f"Trades: {len(results['trades'])}")
```

---

## Notes

- All prices are in USD
- All dates are datetime objects (timezone-aware where applicable)
- DataFrames use lowercase column names (open, high, low, close, volume)
- Configuration can be overridden via environment variables
- Detailed logging available via standard Python logging
