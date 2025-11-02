"""Flask app for real-time portfolio monitoring with AI reasoning."""
import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))

import asyncio
import json
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from src.config_loader import CONFIG
from src.trading.hyperliquid_api import HyperliquidAPI
from src.utils.diary import TradeDiary
import secrets

import threading
import os
from src.main import run_trading_bot


app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(32)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Global state
portfolio_history = []  # Liste des valeurs historiques du portefeuille
ai_reasoning_log = []   # Log des raisonnements de l'IA
trades_history = []     # Historique des trades

diary = TradeDiary()

async def fetch_portfolio_data():
    """Fetch latest portfolio data from Hyperliquid."""
    try:
        api = HyperliquidAPI()
        
        # Get user state
        state = await api.get_user_state()
        
        # Get open orders
        orders = await api.get_open_orders()
        
        # Get recent fills
        fills = await api.get_recent_fills(limit=50)
        
        # Get current prices for positions
        positions_enriched = []
        total_pnl = 0
        
        for pos in state['positions']:
            coin = pos.get('coin')
            current_price = await api.get_current_price(coin)
            pnl = float(pos.get('pnl', 0))
            total_pnl += pnl
            
            positions_enriched.append({
                'coin': coin,
                'size': float(pos.get('szi', 0)),
                'entry_price': float(pos.get('entryPx', 0)),
                'current_price': current_price,
                'pnl': pnl,
                'pnl_pct': (pnl / float(pos.get('notional_entry', 1))) * 100 if pos.get('notional_entry') else 0,
                'side': 'LONG' if float(pos.get('szi', 0)) > 0 else 'SHORT'
            })
        
        # Add to portfolio history
        timestamp = datetime.now()
        portfolio_history.append({
            'timestamp': timestamp.isoformat(),
            'value': state['total_value'],
            'pnl': total_pnl
        })
        
        # Keep only last 24 hours
        cutoff = datetime.now() - timedelta(hours=24)
        portfolio_history[:] = [p for p in portfolio_history 
                               if datetime.fromisoformat(p['timestamp']) > cutoff]
        
        # Get AI reasoning from diary (JSONL format)
        try:
            from pathlib import Path
            
            diary_file = Path("diary.jsonl")
            if diary_file.exists():
                diary_entries = []
                with open(diary_file, 'r') as f:
                    for line in f:
                        try:
                            entry = json.loads(line.strip())
                            diary_entries.append(entry)
                        except json.JSONDecodeError:
                            continue
                
                print(f"📝 Loaded {len(diary_entries)} diary entries from JSONL")
                
                # Take last 20 entries
                for entry in diary_entries[-20:]:
                    if not any(r.get('timestamp') == entry.get('timestamp') for r in ai_reasoning_log):
                        ai_reasoning_log.insert(0, {
                            'timestamp': entry.get('timestamp'),
                            'asset': entry.get('asset'),
                            'action': entry.get('action'),
                            'rationale': entry.get('rationale', '')
                        })
            else:
                print("⚠️ No diary.jsonl found")
        except Exception as e:
            print(f"❌ Error loading diary: {e}")
            import traceback
            traceback.print_exc()
        
        # Keep only last 50 reasoning entries
        ai_reasoning_log[:] = ai_reasoning_log[:50]
        
        # Keep only last 50 reasoning entries
        ai_reasoning_log[:] = ai_reasoning_log[:50]
        
        # Process fills into trades history
        for fill in fills:
            fill_id = f"{fill.get('time')}_{fill.get('coin')}_{fill.get('px')}"
            if not any(t['id'] == fill_id for t in trades_history):
                trades_history.insert(0, {
                    'id': fill_id,
                    'timestamp': datetime.fromtimestamp(fill.get('time', 0) / 1000).isoformat() if fill.get('time') else datetime.now().isoformat(),
                    'coin': fill.get('coin'),
                    'side': 'BUY' if fill.get('isBuy') else 'SELL',
                    'size': float(fill.get('sz', 0)),
                    'price': float(fill.get('px', 0)),
                    'total': float(fill.get('sz', 0)) * float(fill.get('px', 0))
                })
        
        # Keep only last 100 trades
        trades_history[:] = trades_history[:100]
        
        return {
            'balance': state['balance'],
            'total_value': state['total_value'],
            'total_pnl': total_pnl,
            'positions': positions_enriched,
            'open_orders': [{
                'coin': o.get('coin'),
                'side': 'BUY' if o.get('isBuy') else 'SELL',
                'size': float(o.get('sz', 0)),
                'price': float(o.get('px', 0)),
                'type': o.get('orderType', {}).get('limit', {}).get('tif', 'MARKET') if isinstance(o.get('orderType'), dict) else 'MARKET'
            } for o in orders],
            'portfolio_history': portfolio_history,
            'ai_reasoning': ai_reasoning_log,
            'trades': trades_history,
            'last_update': datetime.now().isoformat()
        }
    except Exception as e:
        print(f"Error fetching portfolio: {e}")
        import traceback
        traceback.print_exc()
        return None

def update_portfolio():
    """Background task to update portfolio data."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    while True:
        data = loop.run_until_complete(fetch_portfolio_data())
        if data:
            # ❌ AVANT: broadcast=True (pas supporté)
            # socketio.emit('portfolio_update', data, broadcast=True)
            
            # ✅ APRÈS: utilise namespace='/'
            socketio.emit('portfolio_update', data, namespace='/')
        
        socketio.sleep(10) 

@app.route('/')
def index():
    """Serve the main dashboard page."""
    return render_template('dashboard.html')

@app.route('/api/portfolio')
def get_portfolio():
    """API endpoint to get current portfolio data."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    data = loop.run_until_complete(fetch_portfolio_data())
    return jsonify(data if data else {})

@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    print('Client connected')
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    data = loop.run_until_complete(fetch_portfolio_data())
    if data:
        emit('portfolio_update', data)

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    print('Client disconnected')


def start_trading_bot():
    """Lance le bot de trading en arrière-plan."""
    try:
        # Récupère les assets depuis l'env ou utilise des valeurs par défaut
        assets_str = os.getenv('TRADING_ASSETS', 'BTC,ETH')
        assets = assets_str.split(',')  # Convertit "BTC,ETH" en ['BTC', 'ETH']
        interval = os.getenv('TRADING_INTERVAL', '5m')
        
        print(f"🤖 Démarrage du bot pour {assets} avec intervalle {interval}")
        
        # Lance le bot avec les bons arguments
        asyncio.run(run_trading_bot(assets, interval))
    except Exception as e:
        print(f"❌ Erreur bot: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    # Lance le bot dans un thread séparé
    bot_thread = threading.Thread(target=start_trading_bot, daemon=True)
    bot_thread.start()
    print("🤖 Trading bot démarré en arrière-plan")
    
    # Donne un peu de temps au bot pour démarrer
    import time
    time.sleep(2)
    
    # Lance l'API Flask
    socketio.start_background_task(update_portfolio)
    port = int(os.getenv('PORT', 3000))
    socketio.run(app, debug=os.getenv('DEBUG', 'False') == 'True', host='0.0.0.0', port=port)