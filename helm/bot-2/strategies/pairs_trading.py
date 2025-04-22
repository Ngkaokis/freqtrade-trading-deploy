from freqtrade.strategy import IStrategy, DecimalParameter, IntParameter
from pandas import DataFrame
import talib.abstract as ta
import pandas as pd
import numpy as np
from functools import reduce
import logging
import freqtrade.vendor.qtpylib.indicators as qtpylib
import statsmodels.api as sm
from statsmodels.regression.rolling import RollingOLS

logger = logging.getLogger(__name__)


class PairTradingStrategy(IStrategy):
    INTERFACE_VERSION = 3

    # Strategy parameters
    minimal_roi = {}

    stoploss = -0.10

    timeframe = "1h"

    # Hyperopt parameters
    window = IntParameter(20, 100, default=30, space="buy")
    long_zscore_threshold = DecimalParameter(1.5, 3.0, default=2.0, space="buy")
    short_buy_zscore_threshold = DecimalParameter(1.5, 3.0, default=2.0, space="sell")
    long_rsi_period = IntParameter(10, 20, default=14, space="buy")
    short_rsi_period = IntParameter(10, 20, default=14, space="sell")

    # Strategy settings
    use_exit_signal = True
    can_short = True
    process_only_new_candles = True
    startup_candle_count: int = 100

    cointegrations = {
        # "BTC/USDT:USDT": "SUI/USDT:USDT",
        # "ADA/USDT:USDT": "DOGE/USDT:USDT",
        "LTC/USDT:USDT": "XRP/USDT:USDT",
        "SOL/USDT:USDT": "DOGE/USDT:USDT",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Create reverse mapping for hedge pairs
        self.hedge_pairs = {v: k for k, v in self.cointegrations.items()}

    def informative_pairs(self):
        pairs = self.dp.current_whitelist()
        # Assign tf to each pair so they can be downloaded and cached for strategy.
        informative_pairs = [(pair, self.timeframe) for pair in pairs]
        return informative_pairs

    def calculate_hedge_ratio(
        self, price1: pd.Series, price2: pd.Series, window: int
    ) -> pd.Series:
        # Rolling regression to find hedge ratio
        rolling_model = RollingOLS(price1, sm.add_constant(price2), window).fit()
        hedge_ratio = rolling_model.params.iloc[:, 0]
        return hedge_ratio

    def zscore(self, series: pd.Series, window: int) -> pd.Series:
        """Calculate z-score of a price series"""
        mean = series.rolling(window=window).mean()
        std = series.rolling(window=window).std()
        return (series - mean) / std

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """Generate indicators for trading decisions"""
        # Calculate price ratios and z-scores
        if (
            metadata["pair"] not in self.cointegrations
            and metadata["pair"] not in self.hedge_pairs
        ):
            return dataframe

        pair = metadata["pair"]

        if pair in self.cointegrations:
            informative = self.dp.get_pair_dataframe(
                self.cointegrations[pair], self.timeframe
            )
            df_1 = dataframe
            df_2 = informative
        else:
            informative = self.dp.get_pair_dataframe(
                self.hedge_pairs[pair], self.timeframe
            )
            df_2 = dataframe
            df_1 = informative

        hedge_ratio = self.calculate_hedge_ratio(
            df_1["close"], df_2["close"], self.window.value
        )
        dataframe["hedge_ratio"] = hedge_ratio
        dataframe["spread"] = df_1["close"] - (hedge_ratio * df_2["close"])
        dataframe["zscore"] = self.zscore(dataframe["spread"], self.window.value)

        # Add RSI for additional confirmation
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """Generate entry signals for trades"""
        if (
            metadata["pair"] not in self.cointegrations
            and metadata["pair"] not in self.hedge_pairs
        ):
            return dataframe

        conditions_long = [(dataframe["rsi"] < 30)]
        conditions_short = [(dataframe["rsi"] > 70)]

        if metadata["pair"] in self.cointegrations:
            conditions_long.append(
                (dataframe["zscore"] < -self.long_zscore_threshold.value)
            )
            conditions_short.append(
                (dataframe["zscore"] > self.short_buy_zscore_threshold.value)
            )
        else:
            conditions_long.append(
                (dataframe["zscore"] > self.short_buy_zscore_threshold.value)
            )
            conditions_short.append(
                (dataframe["zscore"] < -self.long_zscore_threshold.value)
            )

        dataframe.loc[reduce(lambda x, y: x & y, conditions_long), "enter_long"] = 1
        dataframe.loc[reduce(lambda x, y: x & y, conditions_short), "enter_short"] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """Generate exit signals for trades"""
        if (
            metadata["pair"] not in self.cointegrations
            and metadata["pair"] not in self.hedge_pairs
        ):
            return dataframe

        conditions_exit_long = [(dataframe["rsi"] > 70)]
        conditions_exit_short = [(dataframe["rsi"] < 30)]

        if metadata["pair"] in self.cointegrations:
            conditions_exit_long.append((dataframe["zscore"] > 0))
            conditions_exit_short.append((dataframe["zscore"] < 0))
        else:
            conditions_exit_long.append((dataframe["zscore"] < 0))
            conditions_exit_short.append(dataframe["zscore"] > 0)

        dataframe.loc[reduce(lambda x, y: x & y, conditions_exit_long), "exit_long"] = 1
        dataframe.loc[
            reduce(lambda x, y: x & y, conditions_exit_short), "exit_short"
        ] = 1
        return dataframe


