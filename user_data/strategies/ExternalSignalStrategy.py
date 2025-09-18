# Minimal external-signal-friendly strategy for Freqtrade
# This strategy intentionally does not generate buy/sell signals itself.
# You can use Freqtrade API (forcebuy/forcesell) to manage trades externally.

from freqtrade.strategy import IStrategy
import pandas as pd


class ExternalSignalStrategy(IStrategy):
    # Dynamic timeframe - reads from config file
    timeframe = "5m"  # Default fallback
    
    def __init__(self, config: dict):
        super().__init__(config)
        # Override timeframe from config if available
        if 'timeframe' in config:
            self.timeframe = config['timeframe']

    # Large ROI and deep stoploss so the bot does nothing automatically.
    minimal_roi = {"0": 1.0}  # 100% profit target to avoid auto-selling
    stoploss = -0.99  # Very wide stoploss to avoid auto-stoploss

    # Other safe defaults
    process_only_new_candles = True
    use_exit_signal = False
    exit_profit_only = False
    ignore_buying_expired_candle_after = 0
    startup_candle_count = 50
    position_adjustment_enable = False

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        # No indicators - external control
        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe["enter_long"] = 0
        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe["exit_long"] = 0
        return dataframe
