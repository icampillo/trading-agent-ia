import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))

import asyncio
import os
import json
import logging
from datetime import datetime, timedelta
from flask import Flask, jsonify
from flask_cors import CORS
from src.config_loader import CONFIG
from src.trading.hyperliquid_api import HyperliquidAPI

app = Flask(__name__)
CORS(app)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout,
    force=True
)

# --- ROUTES API UNIQUEMENT ---

async def fetch_portfolio_data():
    try:
        api = HyperliquidAPI()
        state = await api.get_user_state()
        INITIAL_CAPITAL = 100.0
        total_pnl = sum(float(pos.get('pnl', 0)) for pos in state['positions'])
        total_return_pct = ((state['total_balance'] - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100.0)
        positions_enriched = [
            {
                'coin': pos.get('coin'),
                'size': float(pos.get('szi', 0)),
                'entry_price': float(pos.get('entryPx', 0)),
                'current_price': await api.get_current_price(pos.get('coin')),
                'pnl': float(pos.get('pnl', 0)),
                'side': 'LONG' if float(pos.get('szi', 0)) > 0 else 'SHORT'
            }
            for pos in state['positions']
        ]
        return {
            'balance': state['balance'],
            'total_value': state['total_balance'],
            'total_balance': state['total_balance'],
            'total_pnl': total_pnl,
            'total_return_pct': round(total_return_pct, 2),
            'positions': positions_enriched,
            'last_update': datetime.now().isoformat()
        }
    except Exception as e:
        logging.error(f"Error fetching portfolio: {e}")
        import traceback
        traceback.print_exc()
        return {}

import asyncio

@app.route('/api/portfolio')
def get_portfolio():
    """API endpoint to get current portfolio data."""
    try:
        loop = asyncio.get_event_loop()
        data = loop.run_until_complete(fetch_portfolio_data())
        return jsonify(data if data else {})
    except RuntimeError:
        # Si l'event loop est déjà en cours (cas sur Railway), utilise asyncio.run
        data = asyncio.run(fetch_portfolio_data())
        return jsonify(data if data else {})
    except Exception as e:
        logging.error(f"Error in /api/portfolio: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/trades/completed')
def get_completed_trades():
    try:
        loop = asyncio.get_event_loop()
        api = HyperliquidAPI()
        fills = loop.run_until_complete(api.get_trade_history(limit=200))
        return jsonify({'trades': fills})
    except RuntimeError:
        fills = asyncio.run(api.get_trade_history(limit=200))
        return jsonify({'trades': fills})
    except Exception as e:
        logging.error(f"Error in get_completed_trades: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 3000))
    app.run(host='0.0.0.0', port=port)