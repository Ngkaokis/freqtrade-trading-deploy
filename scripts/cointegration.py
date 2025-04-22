from datetime import datetime, timezone
import pandas as pd
import numpy as np
from scipy import stats
from statsmodels.tsa.stattools import coint, adfuller
import matplotlib.pyplot as plt

from pathlib import Path
import argparse
import json


class CryptoPairAnalyzer:
    def __init__(self, data_directory="./data/binance/"):
        """
        Initialize with directory containing feather files
        data_directory: Path to directory containing feather files from freqtrade
        """
        self.data_directory = Path(data_directory)
        self.cointegrated_pairs = []

    def load_data(self, pair1, pair2, timeframe, timerange):
        start_date, end_date = timerange.split("-")

        """Load data from feather files"""
        try:
            file1 = self.data_directory / f"{pair1}-{timeframe}.feather"
            file2 = self.data_directory / f"{pair2}-{timeframe}.feather"

            df1 = pd.read_feather(file1)
            df2 = pd.read_feather(file2)

            if end_date:
                start_date = datetime.strptime(f"{start_date}", "%Y%m%d").replace(
                    tzinfo=timezone.utc
                )
                end_date = datetime.strptime(f"{end_date}", "%Y%m%d").replace(
                    tzinfo=timezone.utc
                )
                df1 = df1.loc[(df1["date"] >= start_date) & (df1["date"] <= end_date)]
                df2 = df2.loc[(df2["date"] >= start_date) & (df2["date"] <= end_date)]
            else:
                start_date = datetime.strptime(f"{start_date}", "%Y%m%d").replace(
                    tzinfo=timezone.utc
                )
                df1 = df1[df1["date"] >= start_date]
                df2 = df2[df2["date"] >= start_date]

            # Ensure both dataframes have same datetime index
            df1.set_index("date", inplace=True)
            df2.set_index("date", inplace=True)

            # Align dates and create combined dataframe
            df = pd.DataFrame(
                {
                    "price1": df1["close"],
                    "price2": df2["close"],
                }
            )

            return df.dropna()

        except FileNotFoundError as e:
            print(f"Error loading data: {e}")
            return None

    def calculate_correlation(self, series1, series2):
        """Calculate Pearson correlation and p-value"""
        correlation, p_value = stats.pearsonr(series1, series2)
        return correlation, p_value

    def calculate_rolling_correlation(self, series1, series2, window=30):
        """Calculate rolling correlation"""
        return series1.rolling(window=window).corr(series2)

    def test_cointegration(self, series1, series2):
        """Test for cointegration between two series"""
        score, pvalue, _ = coint(series1, series2)
        return score, pvalue

    def calculate_zscore(self, series, window=20):
        """Calculate z-score of a series"""
        mean = series.rolling(window=window).mean()
        std = series.rolling(window=window).std()
        return (series - mean) / std

    def analyze_pair(self, pair1, pair2, timeframe, timerange, correlation_window=30):
        """Complete analysis of a crypto pair"""

        # Load data
        df = self.load_data(pair1, pair2, timeframe, timerange)
        if df is None:
            return

        # Calculate returns
        df["returns1"] = np.log(df["price1"]).diff()
        df["returns2"] = np.log(df["price2"]).diff()

        # Calculate price ratio and its z-score
        df["price_ratio"] = df["price1"] / df["price2"]
        df["ratio_zscore"] = self.calculate_zscore(df["price_ratio"])

        # Calculate correlations
        correlation, corr_pvalue = self.calculate_correlation(
            df["returns1"].dropna(), df["returns2"].dropna()
        )

        # Calculate rolling correlation
        df["rolling_corr"] = self.calculate_rolling_correlation(
            df["returns1"], df["returns2"], correlation_window
        )

        # Test cointegration
        coint_score, coint_pvalue = self.test_cointegration(df["price1"], df["price2"])
        if coint_pvalue < 0.05:
            self.cointegrated_pairs.append((pair1, pair2, coint_pvalue))

        # Calculate recent metrics (last 24 hours)
        recent_df = df.last("24H")
        recent_corr = recent_df["rolling_corr"].mean()

        return df

    def plot_analysis(self, df, pair1, pair2):
        """Plot analysis results"""
        fig, axes = plt.subplots(4, 1, figsize=(15, 16))

        # Plot normalized prices
        ax1 = axes[0]
        norm_price1 = df["price1"] / df["price1"].iloc[0]
        norm_price2 = df["price2"] / df["price2"].iloc[0]
        ax1.plot(df.index, norm_price1, label=pair1)
        ax1.plot(df.index, norm_price2, label=pair2)
        ax1.set_title("Normalized Prices")
        ax1.legend()

        # Plot rolling correlation
        ax2 = axes[1]
        ax2.plot(df.index, df["rolling_corr"])
        ax2.set_title("Rolling Correlation")
        ax2.axhline(y=0.7, color="g", linestyle="--", label="0.7 threshold")
        ax2.axhline(y=0, color="r", linestyle="--")
        ax2.legend()

        # Plot price ratio
        ax3 = axes[2]
        ax3.plot(df.index, df["price_ratio"])
        ax3.set_title("Price Ratio")

        # Plot z-score
        ax4 = axes[3]
        ax4.plot(df.index, df["ratio_zscore"])
        ax4.set_title("Z-Score of Price Ratio")
        ax4.axhline(y=2, color="r", linestyle="--", label="±2 SD")
        ax4.axhline(y=-2, color="r", linestyle="--")
        ax4.legend()

        plt.tight_layout()
        plt.savefig(f"/Users/ngkaokis/Desktop/{pair1}-{pair2}.png")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Find cointegrated pairs")
    parser.add_argument(
        "--timerange",
        type=str,
        default="20240101-",
        help="data timerange used to analyze pair",
    )
    parser.add_argument(
        "--timeframe",
        type=str,
        default="1h",
        help="data timefram used to analyze pair",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="./_data/binance/",
        help="data directory",
    )

    args = parser.parse_args()

    # Update this path to your freqtrade data directory
    analyzer = CryptoPairAnalyzer(args.data_dir)

    coins = [
        "BTC_USDT",
        "ETH_USDT",
        "AVAX_USDT",
        "XRP_USDT",
        "ADA_USDT",
        "SOL_USDT",
        "DOGE_USDT",
        "LTC_USDT",
        "SUI_USDT",
        "ATOM_USDT",
        "UNI_USDT",
    ]

    blacklist = set([])

    n = len(coins)
    pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            a = coins[i]
            b = coins[j]
            t = (a, b)
            if t not in blacklist:
                pairs.append(t)

    for i in range(n - 1, -1, -1):
        for j in range(i - 1, -1, -1):
            a = coins[i]
            b = coins[j]
            t = (a, b)
            if t not in blacklist:
                pairs.append(t)

    for pair1, pair2 in pairs:
        df = analyzer.analyze_pair(
            pair1, pair2, timeframe="1h", timerange=args.timerange
        )

    with open("cointegrated.json", "w") as outfile:
        json.dump(analyzer.cointegrated_pairs, outfile)

    for pair in analyzer.cointegrated_pairs:
        print(f"{pair[0]} - {pair[1]}: p-value = {pair[2]:.4f}")
