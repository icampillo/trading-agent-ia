import sys
import pathlib
sys.path.append(str(pathlib.Path(__file__).parent.parent))
import argparse
import logging
from collections import deque
import asyncio
import json
from collections import deque, OrderedDict
import math

from datetime import datetime, timezone
from src.trading.hyperliquid_api import HyperliquidAPI
from src.indicators.taapi_client import TAAPIClient
from src.agents.agent import TradingAgent

from src.utils.prompt_utils import json_default, round_or_none, round_series

def get_interval_seconds(interval_str):
    """Convert interval strings like '5m' or '1h' to seconds."""
    if interval_str.endswith('m'):
        return int(interval_str[:-1]) * 60
    elif interval_str.endswith('h'):
        return int(interval_str[:-1]) * 3600
    elif interval_str.endswith('d'):
        return int(interval_str[:-1]) * 86400
    else:
        raise ValueError(f"Unsupported interval: {interval_str}")

def main():
    """Entry point for fetching and logging TAAPI indicators for given assets."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    parser = argparse.ArgumentParser(description="Fetch TAAPI indicators for assets.")
    parser.add_argument("--assets", type=str, nargs="+", required=True, help="Assets to fetch, e.g., BTC ETH")
    parser.add_argument("--interval", type=str, required=True, help="Interval period, e.g., 1h")
    args = parser.parse_args()

    taapi = TAAPIClient()
    hyperliquid = HyperliquidAPI()
    agent = TradingAgent()
    logging.info(f"Fetching indicators for assets: {args.assets} at interval: {args.interval}")

    start_time = datetime.now(timezone.utc)
    invocation_count = 0
    trade_log = []  # For Sharpe: list of returns
    active_trades = []  # {'asset','is_long','amount','entry_price','tp_oid','sl_oid','exit_plan'}
    recent_events = deque(maxlen=200)
    diary_path = "diary.jsonl"
    initial_account_value = None
    # Perp mid-price history sampled each loop (authoritative, avoids spot/perp basis mismatch)
    price_history = {}

    def add_event(msg: str):
        """Log an informational event and push it into the recent events deque."""
        logging.info(msg)
        
    async def run_loop():
        """Main trading loop that gathers data, calls the agent, and executes trades."""
        nonlocal invocation_count, initial_account_value
        while True:
            # Gather data for ALL assets first
            market_sections = []
            asset_prices = {}
            invocation_count += 1
            minutes_since_start = (datetime.now(timezone.utc) - start_time).total_seconds() / 6
            
            # Global account state
            state = await hyperliquid.get_user_state()
            add_event(f"Account state: {state}")
            total_value = state.get('total_value') or state['balance'] + sum(p.get('pnl', 0) for p in state['positions'])
            sharpe = calculate_sharpe(trade_log)
            
            account_value = total_value
            if initial_account_value is None:
                initial_account_value = account_value
            total_return_pct = ((account_value - initial_account_value) / initial_account_value * 100.0) if initial_account_value else 0.0

            positions = []
            for pos_wrap in state['positions']:
                pos = pos_wrap
                coin = pos.get('coin')
                current_px = await hyperliquid.get_current_price(coin) if coin else None
                positions.append({
                    "symbol": coin,
                    "quantity": round_or_none(pos.get('szi'), 6),
                    "entry_price": round_or_none(pos.get('entryPx'), 2),
                    "current_price": round_or_none(current_px, 2),
                    "liquidation_price": round_or_none(pos.get('liquidationPx') or pos.get('liqPx'), 2),
                    "unrealized_pnl": round_or_none(pos.get('pnl'), 4),
                    "leverage": pos.get('leverage')
                })
            
            recent_diary = []
            try:
                with open(diary_path, "r") as f:
                    lines = f.readlines()
                    for line in lines[-10:]:
                        entry = json.loads(line)
                        recent_diary.append(entry)
            except Exception:
                pass
            
            open_orders_struct = []
            try:
                open_orders = await hyperliquid.get_open_orders()
                for o in open_orders[:50]:
                    open_orders_struct.append({
                        "coin": o.get('coin'),
                        "oid": o.get('oid'),
                        "is_buy": o.get('isBuy'),
                        "size": round_or_none(o.get('sz'), 6),
                        "price": round_or_none(o.get('px'), 2),
                        "trigger_price": round_or_none(o.get('triggerPx'), 2),
                        "order_type": o.get('orderType')
                    })
            except Exception:
                open_orders = []
            
            # Reconcile active trades
            try:
                assets_with_positions = set()
                for pos in state['positions']:
                    try:
                        if abs(float(pos.get('szi') or 0)) > 0:
                            assets_with_positions.add(pos.get('coin'))
                    except Exception:
                        continue
                assets_with_orders = {o.get('coin') for o in (open_orders or []) if o.get('coin')}
                for tr in active_trades[:]:
                    asset = tr.get('asset')
                    if asset not in assets_with_positions and asset not in assets_with_orders:
                        add_event(f"Reconciling stale active trade for {asset} (no position, no orders)")
                        active_trades.remove(tr)
                        with open(diary_path, "a") as f:
                            f.write(json.dumps({
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "asset": asset,
                                "action": "reconcile_close",
                                "reason": "no_position_no_orders",
                                "opened_at": tr.get('opened_at')
                            }) + "\n")
            except Exception:
                pass

            recent_fills_struct = []
            try:
                fills = await hyperliquid.get_recent_fills(limit=50)
                for f_entry in fills[-20:]:
                    try:
                        t_raw = f_entry.get('time') or f_entry.get('timestamp')
                        timestamp = None
                        if t_raw is not None:
                            try:
                                t_int = int(t_raw)
                                if t_int > 1e12:
                                    timestamp = datetime.fromtimestamp(t_int / 1000, tz=timezone.utc).isoformat()
                                else:
                                    timestamp = datetime.fromtimestamp(t_int, tz=timezone.utc).isoformat()
                            except Exception:
                                timestamp = str(t_raw)
                        recent_fills_struct.append({
                            "timestamp": timestamp,
                            "coin": f_entry.get('coin') or f_entry.get('asset'),
                            "is_buy": f_entry.get('isBuy'),
                            "size": round_or_none(f_entry.get('sz') or f_entry.get('size'), 6),
                            "price": round_or_none(f_entry.get('px') or f_entry.get('price'), 2)
                        })
                    except Exception:
                        continue
            except Exception:
                pass


            dashboard = {
                "total_return_pct": round(total_return_pct, 2),
                "balance": round_or_none(state['balance'], 2),
                "account_value": round_or_none(account_value, 2),
                "sharpe_ratio": round_or_none(sharpe, 3),
                "positions": positions,
                "active_trades": [
                    {
                        "asset": tr.get('asset'),
                        "is_long": tr.get('is_long'),
                        "amount": round_or_none(tr.get('amount'), 6),
                        "entry_price": round_or_none(tr.get('entry_price'), 2),
                        "tp_oid": tr.get('tp_oid'),
                        "sl_oid": tr.get('sl_oid'),
                        "exit_plan": tr.get('exit_plan'),
                        "opened_at": tr.get('opened_at')
                    }
                    for tr in active_trades
                ],
                "open_orders": open_orders_struct,
                "recent_diary": recent_diary,
                "recent_fills": recent_fills_struct,
            }
            logging.info(f"Dashboard: {dashboard}")

            # Gather market data for the asset
            market_sections = []
            asset_prices = {}
            for asset in args.assets:
                try:
                    current_price = await hyperliquid.get_current_price(asset)
                    asset_prices[asset] = current_price
                    if asset not in price_history:
                        price_history[asset] = deque(maxlen=60)
                    price_history[asset].append({"t": datetime.now(timezone.utc).isoformat(), "mid": round_or_none(current_price, 2)})
                    oi = await hyperliquid.get_open_interest(asset)
                    funding = await hyperliquid.get_funding_rate(asset)

                    intraday_tf = "5m"
                    ema_series = taapi.fetch_series("ema", f"{asset}/USDT", intraday_tf, results=10, params={"period": 20}, value_key="value")
                    add_event(f"Fetched EMA series for {asset}: {ema_series}")
                    macd_series = taapi.fetch_series("macd", f"{asset}/USDT", intraday_tf, results=10, value_key="valueMACD")
                    add_event(f"Fetched MACD series for {asset}: {macd_series}")
                    rsi7_series = taapi.fetch_series("rsi", f"{asset}/USDT", intraday_tf, results=10, params={"period": 7}, value_key="value")
                    add_event(f"Fetched RSI7 series for {asset}: {rsi7_series}")
                    rsi14_series = taapi.fetch_series("rsi", f"{asset}/USDT", intraday_tf, results=10, params={"period": 14}, value_key="value")
                    add_event(f"Fetched RSI14 series for {asset}: {rsi14_series}")
                    
                    lt_ema20 = taapi.fetch_value("ema", f"{asset}/USDT", "4h", params={"period": 20}, key="value")
                    add_event(f"Fetched LT EMA20 for {asset}: {lt_ema20}")
                    lt_ema50 = taapi.fetch_value("ema", f"{asset}/USDT", "4h", params={"period": 50}, key="value")
                    add_event(f"Fetched LT EMA50 for {asset}: {lt_ema50}")
                    lt_atr3 = taapi.fetch_value("atr", f"{asset}/USDT", "4h", params={"period": 3}, key="value")
                    add_event(f"Fetched LT ATR3 for {asset}: {lt_atr3}")
                    lt_atr14 = taapi.fetch_value("atr", f"{asset}/USDT", "4h", params={"period": 14}, key="value")
                    add_event(f"Fetched LT ATR14 for {asset}: {lt_atr14}")
                    lt_macd_series = taapi.fetch_series("macd", f"{asset}/USDT", "4h", results=10, value_key="valueMACD")
                    add_event(f"Fetched LT MACD series for {asset}: {lt_macd_series}")
                    lt_rsi_series = taapi.fetch_series("rsi", f"{asset}/USDT", "4h", results=10, params={"period": 14}, value_key="value")
                    add_event(f"Fetched LT RSI series for {asset}: {lt_rsi_series}")

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
                except Exception as e:
                    add_event(f"Data gather error {asset}: {e}")
                    continue
                
            # Single LLM call with all assets
            context_payload = OrderedDict([
                ("invocation", {
                    "minutes_since_start": round(minutes_since_start, 2),
                    "current_time": datetime.now(timezone.utc).isoformat(),
                    "invocation_count": invocation_count
                }),
                ("account", dashboard),
                ("market_data", market_sections),
                ("instructions", {
                    "assets": args.assets,
                    "requirement": "Decide actions for all assets and return a strict JSON array matching the schema."
                })
            ])
            context = json.dumps(context_payload, default=json_default)
            add_event(f"Combined prompt length: {len(context)} chars for {len(args.assets)} assets")
            with open("prompts.log", "a") as f:
                f.write(f"\n\n--- {datetime.now()} - ALL ASSETS ---\n{json.dumps(context_payload, indent=2, default=json_default)}\n")
                
            def _is_failed_outputs(outs):
                """Return True when outputs are missing or clearly invalid."""
                if not isinstance(outs, dict):
                    return True
                decisions = outs.get("trade_decisions")
                if not isinstance(decisions, list) or not decisions:
                    return True
                try:
                    return all(
                        isinstance(o, dict)
                        and (o.get('action') == 'hold')
                        and ('parse error' in (o.get('rationale', '').lower()))
                        for o in decisions
                    )
                except Exception:
                    return True
                
                
            # try:
            #     outputs = agent.decide_trade(args.assets, context)
            #     if not isinstance(outputs, dict):
            #         add_event(f"Invalid output format (expected dict): {outputs}")
            #         outputs = {}
            # except Exception as e:
            #     import traceback
            #     add_event(f"Agent error: {e}")
            #     add_event(f"Traceback: {traceback.format_exc()}")
            #     outputs = {}
                
                
            # # Retry once on failure/parse error with a stricter instruction prefix
            # if _is_failed_outputs(outputs):
            #     add_event("Retrying LLM once due to invalid/parse-error output")
            #     context_retry_payload = OrderedDict([
            #         ("retry_instruction", "Return ONLY the JSON array per schema with no prose."),
            #         ("original_context", context_payload)
            #     ])
            #     context_retry = json.dumps(context_retry_payload, default=json_default)
            #     try:
            #         outputs = agent.decide_trade(args.assets, context_retry)
            #         if not isinstance(outputs, dict):
            #             add_event(f"Retry invalid format: {outputs}")
            #             outputs = {}
            #     except Exception as e:
            #         import traceback
            #         add_event(f"Retry agent error: {e}")
            #         add_event(f"Retry traceback: {traceback.format_exc()}")
            #         outputs = {}
                    
            # reasoning_text = outputs.get("reasoning", "") if isinstance(outputs, dict) else ""
            # if reasoning_text:
            #     add_event(f"LLM reasoning summary: {reasoning_text}")
            
            
            
            await asyncio.sleep(get_interval_seconds(args.interval))
                
    def calculate_sharpe(returns):
        """Compute a naive Sharpe-like ratio from the trade log."""
        if not returns:
            return 0
        vals = [r.get('pnl', 0) if 'pnl' in r else 0 for r in returns]
        if not vals:
            return 0
        mean = sum(vals) / len(vals)
        var = sum((v - mean) ** 2 for v in vals) / len(vals)
        std = math.sqrt(var) if var > 0 else 0
        return mean / std if std > 0 else 0            
                
    async def main_async():
        """Start the aiohttp server and kick off the trading loop."""
        await run_loop()
        
    asyncio.run(main_async())
        
if __name__ == "__main__":
    main()