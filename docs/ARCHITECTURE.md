# System Architecture

## Overview

Stock Alert is a position trading system that scans for and monitors stock trading opportunities based on three quantitative strategies. The system is organized into modular components with clear separation of concerns.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     ENTRY POINTS (scripts/)                          │
├─────────────────────────────────────────────────────────────────────┤
│  scan.py  │  backtest.py  │  monitor.py  │  manage_positions.py     │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                   CORE MODULES (src/)                                │
├─────────────────────────────────────────────────────────────────────┤
│
│  ┌─────────────────────────────────────────────────────────────┐
│  │ Data Layer (src/data/)                                      │
│  │  - market.py: Market data retrieval                         │
│  │  - validators.py: Data validation                           │
│  └─────────────────────────────────────────────────────────────┘
│
│  ┌─────────────────────────────────────────────────────────────┐
│  │ Strategies Layer (src/strategies/)                          │
│  │  - relative_strength.py: RS Ranker strategy                │
│  │  - high_52_week.py: High 52 Week breakout                 │
│  │  - big_base.py: Big Base consolidation breakout           │
│  └─────────────────────────────────────────────────────────────┘
│
│  ┌─────────────────────────────────────────────────────────────┐
│  │ Scanning Layer (src/scanning/)                              │
│  │  - scanner.py: Strategy signal generation                   │
│  │  - validator.py: Pre-buy filtering & validation            │
│  └─────────────────────────────────────────────────────────────┘
│
│  ┌─────────────────────────────────────────────────────────────┐
│  │ Position Management (src/position_management/)              │
│  │  - tracker.py: Position state management                    │
│  │  - monitor.py: Exit signal detection                        │
│  │  - executor.py: Position actions (open/close)              │
│  └─────────────────────────────────────────────────────────────┘
│
│  ┌─────────────────────────────────────────────────────────────┐
│  │ Analysis Layer (src/analysis/)                              │
│  │  - backtest.py: Historical backtesting                      │
│  │  - metrics.py: Performance metrics                          │
│  └─────────────────────────────────────────────────────────────┘
│
│  ┌─────────────────────────────────────────────────────────────┐
│  │ Indicators (src/indicators/)                                │
│  │  - technical.py: Moving averages, bollinger bands           │
│  │  - momentum.py: RSI, stochastic                             │
│  └─────────────────────────────────────────────────────────────┘
│
│  ┌─────────────────────────────────────────────────────────────┐
│  │ Configuration (src/config/)                                 │
│  │  - settings.py: Global configuration                        │
│  │  - strategies.py: Strategy parameters                       │
│  └─────────────────────────────────────────────────────────────┘
│
│  ┌─────────────────────────────────────────────────────────────┐
│  │ Notifications (src/notifications/)                          │
│  │  - email.py: Email alerts                                   │
│  └─────────────────────────────────────────────────────────────┘
│
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                  EXTERNAL SERVICES                                   │
├─────────────────────────────────────────────────────────────────────┤
│  Market Data: Yahoo Finance, IB, Polygon.io                         │
│  Notifications: SMTP Email                                          │
│  Storage: JSON files, CSV exports                                   │
└─────────────────────────────────────────────────────────────────────┘
```

## Core Modules

### 1. Data Layer (`src/data/`)

**Purpose**: Fetch and validate market data

- **market.py**: Main data provider
  - `get_historical_data()`: Fetch OHLCV data for ticker
  - Caching for performance
  - Handles missing data gracefully

- **validators.py**: Data quality checks
  - Validates OHLCV values
  - Checks volume requirements
  - Price sanity checks

**Key Classes**:
- `DataValidator`: Validates market data
- `DataCache`: Caches downloaded data

### 2. Strategies Layer (`src/strategies/`)

**Purpose**: Implement trading strategies

Three main strategies implemented:

#### a) **RelativeStrength_Ranker_Position** (`relative_strength.py`)
- Ranks stocks by relative strength
- Identifies momentum leaders
- Filters with RSI and moving averages
- Entry: Breakout above 50-MA with rising RSI
- Exit: Close below 50-MA or time-based (150 days)

#### b) **High52_Position** (`high_52_week.py`)
- Finds breakouts near 52-week highs
- Uses Bollinger Bands for confirmation
- Entry: Price near 52-high with tight bands tightening
- Exit: Close outside Bollinger Bands or time-based

#### c) **BigBase_Breakout_Position** (`big_base.py`)
- Identifies large consolidation bases
- Detects breakouts from consolidation
- Entry: Breakout above consolidation with volume
- Exit: Close back into consolidation or time-based

**Strategy Interface**:
```python
class Strategy:
    def scan(self, data: pd.DataFrame, ticker: str) -> List[Signal]
        # Returns list of trading signals
```

### 3. Scanning Layer (`src/scanning/`)

**Purpose**: Coordinate strategy execution and signal generation

- **scanner.py**: Main scanning engine
  - `run_scan()`: Execute all strategies
  - `run_scan_as_of()`: Historical scanning for backtesting
  - Parallelized execution

- **validator.py**: Post-scan filtering
  - `pre_buy_check()`: Format and deduplicate signals
  - Quality score filtering
  - Deduplication across strategies

### 4. Position Management (`src/position_management/`)

**Purpose**: Track and manage open positions

- **tracker.py**: Position state management
  - `add_position()`: Record new trade
  - `close_position()`: Close trade with exit price
  - `get_position()`: Retrieve position details
  - Persistent JSON storage

- **monitor.py**: Exit signal detection
  - `monitor_positions()`: Check all positions for exits
  - Stop loss hits
  - Profit targets reached
  - Time-based exits
  - Pyramid opportunities

- **executor.py**: Position actions
  - Send orders (mock/real)
  - Record fills
  - Update position tracker

### 5. Analysis Layer (`src/analysis/`)

**Purpose**: Historical testing and performance analysis

- **backtest.py**: Full historical backtesting
  - Simulates trading from historical data
  - Tracks P&L per trade
  - Calculates metrics
  - Returns detailed trade log

- **metrics.py**: Performance metrics
  - Win rate
  - Profit factor
  - Sharpe ratio
  - Max drawdown
  - CAGR

### 6. Indicators (`src/indicators/`)

**Purpose**: Technical analysis indicators

- **technical.py**: Standard indicators
  - Simple Moving Average (SMA)
  - Exponential Moving Average (EMA)
  - Bollinger Bands
  - Standard Deviation

- **momentum.py**: Momentum indicators
  - RSI (Relative Strength Index)
  - Stochastic
  - Rate of Change (ROC)

### 7. Configuration (`src/config/`)

**Purpose**: Centralized configuration

- **settings.py**: Global settings
  - Position sizing parameters
  - Risk limits
  - Market regime filter
  - API keys (from environment)

- **strategies.py**: Strategy-specific parameters
  - Lookback periods
  - Indicator parameters
  - Entry/exit thresholds

### 8. Notifications (`src/notifications/`)

**Purpose**: Send alerts

- **email.py**: Email notifications
  - Formats trading signals
  - Sends to configured recipients
  - Includes P/L for closed positions

## Entry Points

All entry points are located in `scripts/`:

### 1. **scan.py** - Live Scanner
- Scans S&P 500 for new trading opportunities
- Monitors open positions for exit signals
- Records trades to position tracker
- Sends email alerts
- **Usage**: `python scripts/scan.py`

### 2. **backtest.py** - Backtester
- Historical performance testing
- Walk-forward testing
- Strategy comparison
- **Usage**: `python scripts/backtest.py --start-date 2022-01-01`

### 3. **monitor.py** - Position Monitor
- Check open positions for action signals
- Show P/L
- Display position allocation
- **Usage**: `python scripts/monitor.py`

### 4. **manage_positions.py** - Position Manager
- Interactive CLI for position management
- Add/close positions manually
- View position details
- Export position history
- **Usage**: `python scripts/manage_positions.py`

### 5. **download_data.py** - Data Downloader
- Download historical market data
- Bulk downloads for backtesting
- Save to CSV files
- **Usage**: `python scripts/download_data.py --tickers AAPL,MSFT`

## Data Flow

### Scanning Flow
```
User runs scan.py
    ↓
Check market regime (QQQ > 100-MA)
    ↓
Load S&P 500 tickers
    ↓
For each ticker:
  - Fetch historical data (last 252 days)
  - Run all 3 strategies
  - Collect signals
    ↓
Pre-buy validation:
  - Check signal quality (score > 6.0)
  - Remove duplicates across strategies
  - Check position limits
    ↓
Monitor existing positions:
  - Check stop losses (exit if hit)
  - Check profit targets (exit if hit)
  - Check max days (exit if exceeded)
  - Check pyramid opportunities (add if conditions met)
    ↓
Record new trades to tracker
    ↓
Send email alert (if actionable signals)
```

### Backtesting Flow
```
User runs backtest.py
    ↓
Load historical data for date range
    ↓
For each date in range:
  - Run scanner as of that date
  - Get trade-ready signals
  - Update position tracker
  - Process exits
  - Update metrics
    ↓
Calculate performance:
  - Total return %
  - Win rate
  - Profit factor
  - Sharpe ratio
  - Max drawdown
    ↓
Output results
```

## Key Design Decisions

### 1. **Modular Architecture**
- Each module has single responsibility
- Easy to test and modify independently
- Clear interfaces between modules

### 2. **Strategy Pattern**
- Strategies implement common interface
- Easy to add new strategies
- Strategies can be mixed in scanning

### 3. **Configuration-Driven**
- All parameters in config files
- No magic numbers in code
- Easy to adjust parameters for different market conditions

### 4. **Persistent Position Tracking**
- Positions stored in JSON file
- Survives restarts
- Can be manually edited if needed

### 5. **Separate Entry Points**
- Each main function has dedicated script
- Can be scheduled independently
- Can be called from other systems

## Testing Architecture

Tests organized in `tests/`:
- **tests/unit/**: Unit tests for individual modules
- **tests/integration/**: Integration tests (backtests, full workflows)
- **tests/fixtures/**: Shared test data and mocks
- **conftest.py**: Pytest configuration and shared fixtures

## Dependencies

**Key External Libraries**:
- `pandas`: Data manipulation
- `numpy`: Numerical computing
- `yfinance`: Market data
- `ta-lib`: Technical indicators (optional)
- `pytest`: Testing framework

## Performance Considerations

1. **Caching**: Market data cached to avoid repeated downloads
2. **Parallelization**: Ticker scanning can be parallelized
3. **Lazy Loading**: Indicators calculated only when needed
4. **Efficient Backtesting**: Vectorized operations where possible

## Security Considerations

1. **API Keys**: Stored in environment variables
2. **Email Credentials**: Stored in environment variables  
3. **Position Files**: Can be encrypted if sensitive
4. **No Hardcoded Secrets**: All credentials externalized

## Extension Points

### Adding New Strategies
1. Create new module in `src/strategies/`
2. Implement `Strategy` interface
3. Register in `scanner.py`

### Adding New Indicators
1. Add to `src/indicators/`
2. Implement calculation function
3. Use in strategies

### Adding New Exit Conditions
1. Modify `src/position_management/monitor.py`
2. Add new check in `monitor_positions()`
3. Return action signal

### Adding New Metrics
1. Add to `src/analysis/metrics.py`
2. Implement calculation
3. Call from backtest results

## Configuration Files

- `src/config/settings.py`: Main configuration
- `src/config/strategies.py`: Strategy parameters
- `data/sp500_constituents.csv`: S&P 500 ticker list
- `data/open_positions.json`: Current open positions

## Logging and Monitoring

- Console output for interactive use
- Detailed scanning/backtesting logs
- Position tracker maintains trade history
- Email alerts for important signals

## Future Enhancements

1. **Real-time Data**: Replace historical with streaming data
2. **Order Execution**: Integration with broker APIs
3. **Risk Management**: Dynamic position sizing based on volatility
4. **Portfolio Analysis**: Multi-position P/L tracking
5. **Advanced Filtering**: Machine learning signal filtering
6. **Web Dashboard**: Real-time monitoring UI
