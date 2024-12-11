# --- Do not remove these libs ---
from freqtrade.strategy import IStrategy
from pandas import DataFrame, option_context
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
import statistics


# --------------------------------


class BBAWE(IStrategy):
    """

    author@: Gert Wohlgemuth

    converted from:

    https://github.com/sthewissen/Mynt/blob/master/src/Mynt.Core/Strategies/BbandRsi.cs

    """

    INTERFACE_VERSION: int = 3
    # Minimal ROI designed for the strategy.
    # adjust based on market conditions. We would recommend to keep it low for quick turn arounds
    # This attribute will be overridden if the config file contains "minimal_roi"
    minimal_roi = {"0": 0.1}

    # Optimal stoploss designed for the strategy
    stoploss = -0.25

    # Optimal timeframe for the strategy
    timeframe = "30m"

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        # with option_context(
        #     "display.max_rows", None, "display.max_columns", None
        # ):  # more options can be specified also
        #     print(qtpylib.typical_price(dataframe))

        # Bollinger bands
        bollinger = qtpylib.bollinger_bands(dataframe["close"], window=20, stds=2)
        dataframe["bb_lowerband"] = bollinger["lower"]
        dataframe["bb_middleband"] = bollinger["mid"]
        dataframe["bb_upperband"] = bollinger["upper"]
        dataframe["ema20"] = ta.EMA(dataframe, timeperiod=20)
        dataframe["sma20"] = ta.SMA(dataframe, timeperiod=20)
        dataframe["ema3"] = ta.EMA(dataframe, timeperiod=3)
        dataframe["ao"] = qtpylib.awesome_oscillator(dataframe)
        # with option_context(
        #     "display.max_rows", None, "display.max_columns", None
        # ):  # more options can be specified also
        #     print(dataframe)

        spread = dataframe["bb_upperband"] - dataframe["bb_lowerband"]
        avgspread = ta.SMA(spread, 100)

        bb_squeeze = spread / avgspread * 100
        bb_offset = ta.ATR(dataframe, timeperiod=14) * 0.5
        bb_sqz_upper = dataframe["bb_upperband"] + bb_offset
        bb_sqz_lower = dataframe["bb_lowerband"] - bb_offset
        dataframe["bb_squeeze"] = bb_squeeze
        dataframe["bb_sqz_upper"] = bb_sqz_upper
        dataframe["bb_sqz_lower"] = bb_sqz_lower

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # with option_context(
        #     "display.max_rows", None, "display.max_columns", None
        # ):  # more options can be specified also
        #     print(dataframe)
        # hl2 = (dataframe["high"] - dataframe["low"]) / 2
        # print("-------------------------------------------")
        # print(hl2)
        dataframe.loc[
            (
                (qtpylib.crossed_above(dataframe["ema3"], dataframe["ema20"]))
                & (dataframe["close"] > dataframe["ema20"])
                & (dataframe["ao"] > dataframe["ao"].shift(1))
                & (dataframe["close"] < dataframe["bb_upperband"])
                & (dataframe["bb_squeeze"] > 50)
            ),
            "enter_long",
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (qtpylib.crossed_below(dataframe["ema3"], dataframe["ema20"]))
                & (dataframe["close"] < dataframe["ema20"])
                & (dataframe["ao"] < dataframe["ao"].shift(1))
                & (dataframe["close"] > dataframe["bb_lowerband"])
                & (dataframe["bb_squeeze"] > 50)
            ),
            "exit_long",
        ] = 1
        return dataframe
