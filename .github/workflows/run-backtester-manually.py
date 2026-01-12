name: Run Backtester Manually

on:
  workflow_dispatch:   # Manual trigger from GitHub UI

jobs:
  backtest:
    runs-on: ubuntu-latest

    steps:
      # 1️⃣ Checkout the repo
      - name: Checkout repository
        uses: actions/checkout@v3

      # 2️⃣ Setup Python
      - name: Set up Python 3.11
        uses: actions/setup-python@v4
        with:
          python-version: 3.11

      # 3️⃣ Install dependencies
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install yfinance pandas numpy

      # 4️⃣ Run the backtester
      - name: Run Backtester
        env:
          EMAIL_SENDER: ${{ secrets.EMAIL_SENDER }}
          EMAIL_RECEIVER: ${{ secrets.EMAIL_RECEIVER }}
          EMAIL_PASSWORD: ${{ secrets.EMAIL_PASSWORD }}
        run: |
          python backtester.py
