"""
Strategy signal generation. Each function takes a pandas DataFrame of OHLCV
bars (columns: open, high, low, close, volume) and returns one of:
    "long"  - open/hold a long position
    "flat"  - close any position / stay out

All strategies are long-only for simplicity and safety (no margin/shorting).
"""

import numpy as np
import pandas as pd


def atr(df: pd.DataFrame, period: int = 14) -> float:
    """Average True Range of the most recent completed bar."""
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return float(tr.rolling(period).mean().iloc[-1])


def mean_reversion_signal(df: pd.DataFrame, params: dict, in_position: bool) -> str:
    """
    15-min index mean reversion: buy when price is stretched far below its
    rolling mean (z-score below -z_entry), exit when it snaps back to mean.
    """
    lookback = params["lookback"]
    closes = df["close"]
    mean = closes.rolling(lookback).mean().iloc[-1]
    std = closes.rolling(lookback).std().iloc[-1]
    if std == 0 or np.isnan(std):
        return "flat" if not in_position else "long"
    z = (closes.iloc[-1] - mean) / std

    if not in_position:
        return "long" if z <= -params["z_entry"] else "flat"
    # exit when price reverts to (near) the mean
    return "flat" if z >= -params["z_exit"] else "long"


def momentum_breakout_signal(df: pd.DataFrame, params: dict, in_position: bool) -> str:
    """
    1-hour crypto momentum: buy a close above the N-bar high (Donchian
    breakout), exit on a close below the M-bar low.
    """
    n, m = params["breakout_lookback"], params["exit_lookback"]
    close = df["close"].iloc[-1]
    # exclude current bar from the channel
    upper = df["high"].iloc[-(n + 1):-1].max()
    lower = df["low"].iloc[-(m + 1):-1].min()

    if not in_position:
        return "long" if close > upper else "flat"
    return "flat" if close < lower else "long"


def trend_following_signal(df: pd.DataFrame, params: dict, in_position: bool) -> str:
    """
    4-hour commodity trend following: long while fast EMA > slow EMA and
    price is above the fast EMA. Exit on EMA cross-down.
    """
    fast = df["close"].ewm(span=params["fast_ema"], adjust=False).mean().iloc[-1]
    slow = df["close"].ewm(span=params["slow_ema"], adjust=False).mean().iloc[-1]
    close = df["close"].iloc[-1]

    if not in_position:
        return "long" if (fast > slow and close > fast) else "flat"
    return "flat" if fast < slow else "long"


SIGNAL_FUNCS = {
    "mean_reversion": mean_reversion_signal,
    "momentum_breakout": momentum_breakout_signal,
    "trend_following": trend_following_signal,
}


def get_signal(strategy: str, df: pd.DataFrame, params: dict, in_position: bool) -> str:
    if len(df) < 60:
        return "flat" if not in_position else "long"  # not enough data
    return SIGNAL_FUNCS[strategy](df, params, in_position)
