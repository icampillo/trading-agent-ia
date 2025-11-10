# import sys
# import pathlib
# sys.path.insert(0, str(pathlib.Path(__file__).parent))

# import asyncio
# import os
# import json
# import logging
# from datetime import datetime, timedelta
# from flask import Flask, jsonify
# from flask_cors import CORS
# from src.config_loader import CONFIG
# from src.trading.hyperliquid_api import HyperliquidAPI

# app = Flask(__name__)
# CORS(app)

# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
#     stream=sys.stdout,
#     force=True
# )

# # --- ROUTES API UNIQUEMENT ---

# async def fetch_portfolio_data():
#     try:
#         api = HyperliquidAPI()
#         state = await api.get_user_state()
#         INITIAL_CAPITAL = 100.0
#         total_pnl = sum(float(pos.get('pnl', 0)) for pos in state['positions'])
#         total_return_pct = ((state['total_balance'] - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100.0)
#         positions_enriched = [
#             {
#                 'coin': pos.get('coin'),
#                 'size': float(pos.get('szi', 0)),
#                 'entry_price': float(pos.get('entryPx', 0)),
#                 'current_price': await api.get_current_price(pos.get('coin')),
#                 'pnl': float(pos.get('pnl', 0)),
#                 'side': 'LONG' if float(pos.get('szi', 0)) > 0 else 'SHORT'
#             }
#             for pos in state['positions']
#         ]
#         return {
#             'balance': state['balance'],
#             'total_value': state['total_balance'],
#             'total_balance': state['total_balance'],
#             'total_pnl': total_pnl,
#             'total_return_pct': round(total_return_pct, 2),
#             'positions': positions_enriched,
#             'last_update': datetime.now().isoformat()
#         }
#     except Exception as e:
#         logging.error(f"Error fetching portfolio: {e}")
#         import traceback
#         traceback.print_exc()
#         return {}

# import asyncio

# @app.route('/api/portfolio')
# async def get_portfolio():
#     data = await fetch_portfolio_data()
#     return jsonify(data if data else {})

# @app.route('/api/trades/completed')
# async def get_completed_trades():
#     try:
#         api = HyperliquidAPI()
#         fills = await api.get_trade_history(limit=200)
#         # Tu peux ajouter ici le calcul des stats si besoin
#         return jsonify({'trades': fills})
#     except Exception as e:
#         logging.error(f"Error in get_completed_trades: {e}")
#         import traceback
#         traceback.print_exc()
#         return jsonify({'error': str(e)}), 500

# if __name__ == '__main__':
#     port = int(os.getenv('PORT', 3000))
#     app.run(host='0.0.0.0', port=port)
    
    
    
"""Flask app for real-time portfolio monitoring with AI reasoning."""
import sys
import logging

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
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', secrets.token_hex(32))
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading', allow_unsafe_werkzeug=True, max_http_buffer_size=10000000)

# Global state
portfolio_history = []  # Liste des valeurs historiques du portefeuille
ai_reasoning_log = []   # Log des raisonnements de l'IA
trades_history = []     # Historique des trades

diary = TradeDiary()

# Configure logging AVANT tout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout,
    force=True
)

# Force flush immédiat
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

def analyze_completed_trades(fills):
    """Analyse les fills pour créer des trades complets (entry → exit).
    
    Utilise start_position pour tracker correctement LONG et SHORT.
    
    Args:
        fills: Liste des fills bruts de get_trade_history()
        
    Returns:
        Liste de trades complétés avec P&L
    """
    from collections import defaultdict
    from datetime import datetime
    
    # Groupe par coin
    positions_tracker = defaultdict(lambda: {'entry': None, 'fills': []})
    completed_trades = []
    
    for fill in sorted(fills, key=lambda x: x.get('timestamp', '')):
        coin = fill.get('coin')
        side = fill.get('side')  # 'BUY' ou 'SELL'
        size = fill.get('size', 0)
        price = fill.get('price', 0)
        timestamp = fill.get('timestamp')
        closed_pnl = fill.get('closed_pnl', 0)
        start_pos = fill.get('start_position', 0)  # Position AVANT ce fill
        
        tracker = positions_tracker[coin]
        
        # Détermine la position après ce fill
        if side == 'BUY':
            end_pos = start_pos + size
        else:  # SELL
            end_pos = start_pos - size
        
        # Cas 1: Ouvre une nouvelle position
        if start_pos == 0 and end_pos != 0:
            tracker['entry'] = {
                'timestamp': timestamp,
                'price': price,
                'side': 'LONG' if end_pos > 0 else 'SHORT',
                'size': abs(end_pos)
            }
            tracker['fills'] = [fill]
        
        # Cas 2: Ferme complètement une position
        elif start_pos != 0 and end_pos == 0:
            if tracker['entry']:
                entry = tracker['entry']
                entry_time = datetime.fromisoformat(entry['timestamp'])
                exit_time = datetime.fromisoformat(timestamp)
                holding_time = exit_time - entry_time
                
                hours = int(holding_time.total_seconds() // 3600)
                minutes = int((holding_time.total_seconds() % 3600) // 60)
                
                # Calcule P&L selon le côté
                if entry['side'] == 'LONG':
                    pnl = (price - entry['price']) * abs(start_pos)
                else:  # SHORT
                    pnl = (entry['price'] - price) * abs(start_pos)
                
                completed_trades.append({
                    'coin': coin,
                    'side': entry['side'],
                    'entry_time': entry['timestamp'],
                    'entry_price': entry['price'],
                    'exit_time': timestamp,
                    'exit_price': price,
                    'size': abs(start_pos),
                    'notional_entry': abs(start_pos) * entry['price'],
                    'notional_exit': abs(start_pos) * price,
                    'holding_hours': hours,
                    'holding_minutes': minutes,
                    'pnl': pnl,
                    'closed_pnl': closed_pnl,
                    'status': 'completed'
                })
                
                # Reset tracker
                tracker['entry'] = None
                tracker['fills'] = []
        
        # Cas 3: Réduit une position (fermeture partielle)
        elif (start_pos > 0 and end_pos > 0 and end_pos < start_pos) or \
             (start_pos < 0 and end_pos < 0 and abs(end_pos) < abs(start_pos)):
            if tracker['entry']:
                entry = tracker['entry']
                entry_time = datetime.fromisoformat(entry['timestamp'])
                exit_time = datetime.fromisoformat(timestamp)
                holding_time = exit_time - entry_time
                
                hours = int(holding_time.total_seconds() // 3600)
                minutes = int((holding_time.total_seconds() % 3600) // 60)
                
                # Taille fermée
                closed_size = abs(start_pos - end_pos)
                
                # P&L
                if entry['side'] == 'LONG':
                    pnl = (price - entry['price']) * closed_size
                else:  # SHORT
                    pnl = (entry['price'] - price) * closed_size
                
                completed_trades.append({
                    'coin': coin,
                    'side': entry['side'],
                    'entry_time': entry['timestamp'],
                    'entry_price': entry['price'],
                    'exit_time': timestamp,
                    'exit_price': price,
                    'size': closed_size,
                    'notional_entry': closed_size * entry['price'],
                    'notional_exit': closed_size * price,
                    'holding_hours': hours,
                    'holding_minutes': minutes,
                    'pnl': pnl,
                    'closed_pnl': closed_pnl,
                    'status': 'completed'
                })
        
        # Cas 4: Flip de position (LONG → SHORT ou SHORT → LONG)
        elif (start_pos > 0 and end_pos < 0) or (start_pos < 0 and end_pos > 0):
            if tracker['entry']:
                entry = tracker['entry']
                entry_time = datetime.fromisoformat(entry['timestamp'])
                exit_time = datetime.fromisoformat(timestamp)
                holding_time = exit_time - entry_time
                
                hours = int(holding_time.total_seconds() // 3600)
                minutes = int((holding_time.total_seconds() % 3600) // 60)
                
                # P&L sur la position fermée
                if entry['side'] == 'LONG':
                    pnl = (price - entry['price']) * abs(start_pos)
                else:  # SHORT
                    pnl = (entry['price'] - price) * abs(start_pos)
                
                completed_trades.append({
                    'coin': coin,
                    'side': entry['side'],
                    'entry_time': entry['timestamp'],
                    'entry_price': entry['price'],
                    'exit_time': timestamp,
                    'exit_price': price,
                    'size': abs(start_pos),
                    'notional_entry': abs(start_pos) * entry['price'],
                    'notional_exit': abs(start_pos) * price,
                    'holding_hours': hours,
                    'holding_minutes': minutes,
                    'pnl': pnl,
                    'closed_pnl': closed_pnl,
                    'status': 'completed'
                })
                
                # Nouvelle position dans le sens opposé
                tracker['entry'] = {
                    'timestamp': timestamp,
                    'price': price,
                    'side': 'LONG' if end_pos > 0 else 'SHORT',
                    'size': abs(end_pos)
                }
                tracker['fills'] = [fill]
    
    # Tri par date décroissante
    completed_trades.sort(key=lambda x: x['exit_time'], reverse=True)
    
    return completed_trades

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
        
        INITIAL_CAPITAL = 100.0
        
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
        
        balance = float(state.get('balance', 0))
        total_value = balance + total_pnl
        total_return_pct = ((state['total_balance'] - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100.0)
        
        # Add to portfolio history
        timestamp = datetime.now()
        portfolio_history.append({
            'timestamp': timestamp.isoformat(),
            'value': state['total_balance'],
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
            'total_value': state['total_balance'],  # ✅ Utilise total_balance
            'total_balance': state['total_balance'],  # ✅ Ajoute aussi ce champ pour clarté
            'total_pnl': total_pnl,
            'total_return_pct': round(total_return_pct, 2),  # ✅ Arrondi
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
        
        socketio.sleep(30) 

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

@app.route('/api/trades/completed')
def get_completed_trades(): 
    """API endpoint pour les trades complétés avec P&L."""
    try:
        # Crée un event loop comme pour les autres routes
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Récupère les fills
        api = HyperliquidAPI()
        fills = loop.run_until_complete(api.get_trade_history(limit=200))
        
        completed = analyze_completed_trades(fills)
        
        cutoff_date = datetime(2025, 11, 1, 0, 0, 0)
        completed = [
            t for t in completed 
            if datetime.fromisoformat(t['exit_time']) >= cutoff_date
        ]
        
        # Stats
        total_pnl = sum(t['pnl'] for t in completed)
        winning_trades = len([t for t in completed if t['pnl'] > 0])
        losing_trades = len([t for t in completed if t['pnl'] < 0])
        
        return jsonify({
            'trades': completed[:50],  # Limite à 50
            'stats': {
                'total_trades': len(completed),
                'total_pnl': total_pnl,
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'win_rate': (winning_trades / len(completed) * 100) if completed else 0
            }
        })
    except Exception as e:
        logging.error(f"Error in get_completed_trades: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

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
        print("="*80, flush=True)
        print("🤖 DÉMARRAGE DU BOT DE TRADING", flush=True)
        print("="*80, flush=True)
        
        # Récupère les assets depuis l'env
        assets_str = os.getenv('TRADING_ASSETS', 'BTC,ETH')
        assets = assets_str.split(',')
        interval = os.getenv('TRADING_INTERVAL', '5m')
        
        print(f"📊 Assets: {assets}", flush=True)
        print(f"⏱️  Interval: {interval}", flush=True)
        print(f"🔑 API Keys présentes:", flush=True)
        print(f"  - OPENROUTER_API_KEY: {'✅' if os.getenv('OPENROUTER_API_KEY') else '❌'}", flush=True)
        print(f"  - TAAPI_API_KEY: {'✅' if os.getenv('TAAPI_API_KEY') else '❌'}", flush=True)
        print(f"  - HYPERLIQUID_PRIVATE_KEY: {'✅' if os.getenv('HYPERLIQUID_PRIVATE_KEY') else '❌'}", flush=True)
        print("="*80, flush=True)
        
        # Lance le bot
        print("🚀 Lancement de run_trading_bot()...", flush=True)
        asyncio.run(run_trading_bot(assets, interval))
        
    except Exception as e:
        print("="*80, flush=True)
        print(f"💥 ERREUR FATALE DANS LE BOT", flush=True)
        print("="*80, flush=True)
        print(f"❌ {type(e).__name__}: {e}", flush=True)
        import traceback
        traceback.print_exc()
        print("="*80, flush=True)

if __name__ == '__main__':
    print("\n" + "="*80, flush=True)
    print("🏁 INITIALISATION DE L'APPLICATION", flush=True)
    print("="*80 + "\n", flush=True)
    
    # Lance le bot dans un thread séparé
    print("📌 Création du thread pour le bot...", flush=True)
    bot_thread = threading.Thread(target=start_trading_bot, daemon=True)
    bot_thread.start()
    print("✅ Thread bot créé et démarré", flush=True)
    
    # Donne du temps au bot
    import time
    print("⏳ Attente 5s pour le démarrage du bot...", flush=True)
    time.sleep(5)
    
    print("\n" + "="*80, flush=True)
    print("🌐 DÉMARRAGE DE L'API FLASK", flush=True)
    print("="*80 + "\n", flush=True)
    
    # Lance l'API Flask
    socketio.start_background_task(update_portfolio)
    port = int(os.getenv('PORT', 3000))
    socketio.run(app, debug=os.getenv('DEBUG', 'False') == 'True', host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)