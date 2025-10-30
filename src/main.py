import sys
import pathlib
sys.path.append(str(pathlib.Path(__file__).parent.parent))
import argparse
import logging
from collections import deque
import asyncio

from datetime import datetime, timezone
from src.trading.hyperliquid_api import HyperliquidAPI
from src.indicators.taapi_client import TAAPIClient

from src.utils.prompt_utils import round_or_none, round_series

def main():
    """Entry point for fetching and logging TAAPI indicators for given assets."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    parser = argparse.ArgumentParser(description="Fetch TAAPI indicators for assets.")
    parser.add_argument("--assets", type=str, nargs="+", required=True, help="Assets to fetch, e.g., BTC ETH")
    parser.add_argument("--interval", type=str, required=True, help="Interval period, e.g., 1h")
    args = parser.parse_args()

    taapi = TAAPIClient()
    hyperliquid = HyperliquidAPI()
    logging.info(f"Fetching indicators for assets: {args.assets} at interval: {args.interval}")

    price_history = {}
    
    def add_event(msg: str):
        """Log an informational event and push it into the recent events deque."""
        logging.info(msg)
        
    async def run_loop():
        """Main trading loop that gathers data, calls the agent, and executes trades."""
        while True:
            # Gather data for ALL assets first
            market_sections = []
            asset_prices = {}
            for asset in args.assets:
                try:
                    current_price = await hyperliquid.get_current_price(asset)
                    logging.info(f"Current price: {asset} = {current_price}")
                    asset_prices[asset] = current_price
                    if asset not in price_history:
                        price_history[asset] = deque(maxlen=60)
                    price_history[asset].append({"t": datetime.now(timezone.utc).isoformat(), "mid": round_or_none(current_price, 2)})
                    oi = await hyperliquid.get_open_interest(asset)
                    logging.info(f"Current open interest: {asset} = {oi}")
                    funding = await hyperliquid.get_funding_rate(asset)
                    logging.info(f"Current funding rate: {asset} = {funding}")
                    intraday_tf = "5m"
                    ema_series = taapi.fetch_series("ema", f"{asset}/USDT", intraday_tf, results=10, params={"period": 20}, value_key="value")
                    logging.info(f"Fetched EMA series for {asset}: {ema_series}")
                    macd_series = taapi.fetch_series("macd", f"{asset}/USDT", intraday_tf, results=10, value_key="valueMACD")
                    logging.info(f"Fetched MACD series for {asset}: {macd_series}")
                    rsi7_series = taapi.fetch_series("rsi", f"{asset}/USDT", intraday_tf, results=10, params={"period": 7}, value_key="value")
                    logging.info(f"Fetched RSI7 series for {asset}: {rsi7_series}")
                    rsi14_series = taapi.fetch_series("rsi", f"{asset}/USDT", intraday_tf, results=10, params={"period": 14}, value_key="value")
                    logging.info(f"Fetched RSI14 series for {asset}: {rsi14_series}")
                    lt_ema20 = taapi.fetch_value("ema", f"{asset}/USDT", "4h", params={"period": 20}, key="value")
                    logging.info(f"Fetched LT EMA20 for {asset}: {lt_ema20}")
                    lt_ema50 = taapi.fetch_value("ema", f"{asset}/USDT", "4h", params={"period": 50}, key="value")
                    logging.info(f"Fetched LT EMA50 for {asset}: {lt_ema50}")
                    lt_atr3 = taapi.fetch_value("atr", f"{asset}/USDT", "4h", params={"period": 3}, key="value")
                    logging.info(f"Fetched LT ATR3 for {asset}: {lt_atr3}")
                    lt_atr14 = taapi.fetch_value("atr", f"{asset}/USDT", "4h", params={"period": 14}, key="value")
                    logging.info(f"Fetched LT ATR14 for {asset}: {lt_atr14}")
                    lt_macd_series = taapi.fetch_series("macd", f"{asset}/USDT", "4h", results=10, value_key="valueMACD")
                    logging.info(f"Fetched LT MACD series for {asset}: {lt_macd_series}")
                    lt_rsi_series = taapi.fetch_series("rsi", f"{asset}/USDT", "4h", results=10, params={"period": 14}, value_key="value")
                    logging.info(f"Fetched LT RSI series for {asset}: {lt_rsi_series}")
                    recent_mids = [entry["mid"] for entry in list(price_history.get(asset, []))[-10:]]
                    funding_annualized = round(funding * 24 * 365 * 100, 2) if funding else None
                    market_sections.append({
                        "asset": asset,
                        "current_price": round_or_none(current_price, 2),
                        "intraday": {
                            "ema20": round_or_none(ema_series[-1], 2) if ema_series else None,
                            "macd": round_or_none(macd_series[-1], 2) if macd_series else None,
                            "rsi7": round_or_none(rsi7_series[-1], 2) if rsi7_series else None,
                            "rsi14": round_or_none(rsi14_series[-1], 2) if rsi14_series else None,
                            "series": {
                                "ema20": round_series(ema_series, 2),
                                "macd": round_series(macd_series, 2),
                                "rsi7": round_series(rsi7_series, 2),
                                "rsi14": round_series(rsi14_series, 2)
                            }
                        },
                        "long_term": {
                            "ema20": round_or_none(lt_ema20, 2),
                            "ema50": round_or_none(lt_ema50, 2),
                            "atr3": round_or_none(lt_atr3, 2),
                            "atr14": round_or_none(lt_atr14, 2),
                            "macd_series": round_series(lt_macd_series, 2),
                            "rsi_series": round_series(lt_rsi_series, 2)
                        },
                        "open_interest": round_or_none(oi, 2),
                        "funding_rate": round_or_none(funding, 8),
                        "funding_annualized_pct": funding_annualized,
                        "recent_mid_prices": recent_mids
                    })
                    logging.info(f"Gathered data for {asset}: {market_sections[-1]}")
                except Exception as e:
                    add_event(f"Data gather error {asset}: {e}")
                    continue
                
    
    async def main_async():
        """Start the aiohttp server and kick off the trading loop."""
        await run_loop()
        
    asyncio.run(main_async())
        
if __name__ == "__main__":
    main()