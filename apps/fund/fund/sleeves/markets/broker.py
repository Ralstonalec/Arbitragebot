"""
Thin wrapper around Alpaca for market data + order execution.

Stocks/ETFs: orders are submitted with an attached stop-loss (OTO order),
so the stop lives ON THE EXCHANGE — it triggers even if the bot dies.

Crypto: Alpaca doesn't support attached stops on crypto, so the sleeve
enforces the stop in software every poll cycle.
"""

import logging

import pandas as pd

from ... import config

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, StopLossRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass
from alpaca.data.historical import StockHistoricalDataClient, CryptoHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

log = logging.getLogger("fund.markets")


def timeframe_from_minutes(minutes: int) -> TimeFrame:
    if minutes < 60:
        return TimeFrame(minutes, TimeFrameUnit.Minute)
    return TimeFrame(minutes // 60, TimeFrameUnit.Hour)


class Broker:
    def __init__(self):
        if not config.ALPACA_API_KEY or not config.ALPACA_SECRET_KEY:
            raise RuntimeError(
                "Missing API keys. Set ALPACA_API_KEY and ALPACA_SECRET_KEY "
                "environment variables (get free paper keys at alpaca.markets)."
            )
        self.trading = TradingClient(
            config.ALPACA_API_KEY, config.ALPACA_SECRET_KEY, paper=config.PAPER
        )
        self.stock_data = StockHistoricalDataClient(
            config.ALPACA_API_KEY, config.ALPACA_SECRET_KEY
        )
        self.crypto_data = CryptoHistoricalDataClient(
            config.ALPACA_API_KEY, config.ALPACA_SECRET_KEY
        )

    # ------------------------------------------------------------- account
    def equity(self) -> float:
        return float(self.trading.get_account().equity)

    def open_positions(self) -> dict:
        """Returns {symbol: {qty, avg_entry_price, unrealized_pl}}"""
        out = {}
        for p in self.trading.get_all_positions():
            sym = p.symbol if "/" in p.symbol else self._normalize(p.symbol)
            out[sym] = {
                "qty": float(p.qty),
                "avg_entry_price": float(p.avg_entry_price),
                "unrealized_pl": float(p.unrealized_pl),
            }
        return out

    @staticmethod
    def _normalize(symbol: str) -> str:
        return "BTC/USD" if symbol == "BTCUSD" else symbol

    def market_open(self) -> bool:
        return self.trading.get_clock().is_open

    # ---------------------------------------------------------------- data
    def get_bars(self, symbol: str, asset_class: str, timeframe_min: int,
                 limit: int = config.HISTORY_BARS) -> pd.DataFrame:
        tf = timeframe_from_minutes(timeframe_min)
        if asset_class == "crypto":
            req = CryptoBarsRequest(symbol_or_symbols=symbol, timeframe=tf, limit=limit)
            bars = self.crypto_data.get_crypto_bars(req)
        else:
            req = StockBarsRequest(symbol_or_symbols=symbol, timeframe=tf, limit=limit)
            bars = self.stock_data.get_stock_bars(req)
        df = bars.df
        if isinstance(df.index, pd.MultiIndex):
            df = df.xs(symbol, level="symbol")
        return df[["open", "high", "low", "close", "volume"]]

    def last_price(self, symbol: str) -> float | None:
        try:
            if "/" in symbol:
                from alpaca.data.requests import CryptoLatestTradeRequest
                req = CryptoLatestTradeRequest(symbol_or_symbols=symbol)
                return float(self.crypto_data.get_crypto_latest_trade(req)[symbol].price)
            from alpaca.data.requests import StockLatestTradeRequest
            req = StockLatestTradeRequest(symbol_or_symbols=symbol)
            return float(self.stock_data.get_stock_latest_trade(req)[symbol].price)
        except Exception as e:
            log.info("%s: no price (%s)", symbol, e)
            return None

    # -------------------------------------------------------------- orders
    def buy_with_stop(self, symbol: str, asset_class: str, qty: float,
                      stop_price: float):
        """Market buy. Stocks get an exchange-side stop attached (OTO)."""
        if asset_class == "crypto":
            order = MarketOrderRequest(
                symbol=symbol, qty=qty,
                side=OrderSide.BUY, time_in_force=TimeInForce.GTC,
            )
        else:
            order = MarketOrderRequest(
                symbol=symbol, qty=qty,
                side=OrderSide.BUY, time_in_force=TimeInForce.DAY,
                order_class=OrderClass.OTO,
                stop_loss=StopLossRequest(stop_price=stop_price),
            )
        result = self.trading.submit_order(order)
        log.info("BUY %s %s (stop %s)", qty, symbol, stop_price)
        return result

    def close_position(self, symbol: str):
        api_symbol = symbol.replace("/", "")
        self.trading.close_position(api_symbol)
        log.info("CLOSED %s", symbol)
