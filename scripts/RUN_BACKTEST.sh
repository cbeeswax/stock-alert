#!/bin/bash
# Quick script to run backtests after fixes

echo "=============================================="
echo "🔧 Stock Alert Backtester - Fixed Version"
echo "=============================================="
echo ""

# Check if dependencies are installed
echo "📦 Checking dependencies..."
python3 -c "import pandas, yfinance, numpy" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️  Dependencies not installed. Installing..."
    pip3 install -r requirements.txt
fi

echo ""
echo "=============================================="
echo "🧪 OPTION 1: Quick Test (5 tickers, 1 year)"
echo "=============================================="
echo "Run: python3 test_backtest.py"
echo ""
echo "This tests with AAPL, MSFT, GOOGL, NVDA, TSLA"
echo "Quick validation that fixes are working"
echo ""

echo "=============================================="
echo "📊 OPTION 2: Full Backtest (S&P 500, 4+ years)"
echo "=============================================="
echo "Run: python3 backtester_walkforward.py"
echo ""
echo "Full backtest from 2022-01-01 to present"
echo "⏱️  This will take 15-30 minutes"
echo ""

echo "=============================================="
echo "📖 Documentation"
echo "=============================================="
echo "See BACKTEST_FIXES.md for complete details"
echo ""

# Ask user which to run
read -p "Which option? (1=quick test, 2=full backtest, q=quit): " choice

case $choice in
    1)
        echo ""
        echo "🧪 Running quick test..."
        python3 test_backtest.py
        ;;
    2)
        echo ""
        echo "📊 Running full backtest..."
        echo "⏱️  This may take 15-30 minutes..."
        python3 backtester_walkforward.py
        ;;
    q|Q)
        echo "Exiting..."
        exit 0
        ;;
    *)
        echo "Invalid option"
        exit 1
        ;;
esac
