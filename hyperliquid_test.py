"""Script de test pour vérifier la configuration Hyperliquid."""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent))

import asyncio
import logging
import json
from src.config_loader import CONFIG
from src.trading.hyperliquid_api import HyperliquidAPI

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

async def test_hyperliquid():
    """Test les fonctionnalités de base de l'API Hyperliquid."""
    
    print("\n" + "="*60)
    print("TEST HYPERLIQUID API - GET_USER_STATE")
    print("="*60 + "\n")
    
    # Initialisation
    print("1️⃣ Initialisation de l'API...")
    try:
        api = HyperliquidAPI()
        print(f"✅ Agent wallet address: {api.wallet.address}")
        print(f"✅ Vault address: {CONFIG.get('hyperliquid_vault_address')}")
        print(f"✅ Base URL: {api.base_url}")
    except Exception as e:
        print(f"❌ Erreur d'initialisation: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Récupérer l'état du compte
    print("\n2️⃣ Récupération de l'état du compte (get_user_state)...")
    print("="*60)
    try:
        state = await api.get_user_state()
        
        # Affiche TOUT le state en JSON formaté
        print("\n📦 CONTENU COMPLET DU STATE:")
        print(json.dumps(state, indent=2, default=str))
        
        print("\n" + "="*60)
        print("📊 ANALYSE DU STATE:")
        print("="*60)
        
        # Balance
        print(f"\n💰 Balance: ${state.get('balance', 0):.2f}")
        print(f"💰 Total value: ${state.get('total_value', 0):.2f}")
        
        # Positions
        positions = state.get('positions', [])
        print(f"\n📈 Positions ouvertes: {len(positions)}")
        if positions:
            print("\n   Détails des positions:")
            for i, pos in enumerate(positions, 1):
                print(f"\n   Position {i}:")
                print(f"   {json.dumps(pos, indent=6, default=str)}")
        else:
            print("   Aucune position ouverte")
        
        # Ordres
        orders = state.get('open_orders', [])
        print(f"\n📋 Ordres ouverts: {len(orders)}")
        if orders:
            print("\n   Détails des ordres:")
            for i, order in enumerate(orders, 1):
                print(f"\n   Ordre {i}:")
                print(f"   {json.dumps(order, indent=6, default=str)}")
        else:
            print("   Aucun ordre ouvert")
        
        # Fills récents
        fills = state.get('fills', [])
        print(f"\n📜 Fills récents: {len(fills)}")
        if fills:
            print(f"\n   Les 5 derniers fills:")
            for i, fill in enumerate(fills[:5], 1):
                print(f"\n   Fill {i}:")
                print(f"   {json.dumps(fill, indent=6, default=str)}")
        else:
            print("   Aucun fill récent")
        
        # Autres clés présentes
        print(f"\n🔑 Toutes les clés présentes dans state:")
        for key in state.keys():
            value_type = type(state[key]).__name__
            if isinstance(state[key], (list, dict)):
                length = len(state[key])
                print(f"   - {key}: {value_type} (length: {length})")
            else:
                print(f"   - {key}: {value_type} = {state[key]}")
                
        print("\n📜 Testing get_trade_history...")
        trades = await api.get_trade_history(limit=10)
        
        print(f"✅ Retrieved {len(trades)} trades")
        
        if trades:
            print("\n📊 Sample trade:")
            print(json.dumps(trades, indent=2))
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n" + "="*60)
    print("✅ Tests terminés!")
    print("="*60 + "\n")

if __name__ == "__main__":
    asyncio.run(test_hyperliquid())