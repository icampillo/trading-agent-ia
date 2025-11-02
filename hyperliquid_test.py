# """Script de test pour vérifier la configuration Hyperliquid."""
# import sys
# import pathlib

# sys.path.insert(0, str(pathlib.Path(__file__).parent))

# import asyncio
# import logging
# from src.config_loader import CONFIG
# from src.trading.hyperliquid_api import HyperliquidAPI

# logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# async def test_hyperliquid():
#     """Test les fonctionnalités de base de l'API Hyperliquid."""
    
#     print("\n" + "="*60)
#     print("TEST HYPERLIQUID API")
#     print("="*60 + "\n")
    
#     # 1. Initialisation
#     print("1️⃣ Initialisation de l'API...")
#     try:
#         api = HyperliquidAPI()
#         print(f"✅ Agent wallet address: {api.wallet.address}")
#         print(f"✅ Vault address: {CONFIG.get('hyperliquid_vault_address')}")
#         print(f"✅ Base URL: {api.base_url}")
#     except Exception as e:
#         print(f"❌ Erreur d'initialisation: {e}")
#         return
    
#     # 2. Récupérer l'état du compte
#     print("\n2️⃣ Récupération de l'état du compte...")
#     try:
#         state = await api.get_user_state()
#         print(f"✅ Balance: ${state['balance']:.2f}")
#         print(f"✅ Total value: ${state['total_value']:.2f}")
#         print(f"✅ Positions ouvertes: {len(state['positions'])}")
        
#         if state['positions']:
#             print("\n   Positions:")
#             for pos in state['positions']:
#                 print(f"   - {pos.get('coin')}: {pos.get('szi')} (PnL: ${pos.get('pnl', 0):.2f})")
#     except Exception as e:
#         print(f"❌ Erreur: {e}")
#         return
    
#     # 3. Récupérer les prix actuels
#     print("\n3️⃣ Récupération des prix...")
#     try:
#         btc_price = await api.get_current_price("BTC")
#         eth_price = await api.get_current_price("ETH")
#         print(f"✅ BTC: ${btc_price:,.2f}")
#         print(f"✅ ETH: ${eth_price:,.2f}")
#     except Exception as e:
#         print(f"❌ Erreur: {e}")
    
#     # 4. Récupérer les ordres ouverts
#     print("\n4️⃣ Récupération des ordres ouverts...")
#     try:
#         orders = await api.get_open_orders()
#         print(f"✅ Ordres ouverts: {len(orders)}")
        
#         if orders:
#             print("\n   Ordres:")
#             for order in orders[:5]:
#                 print(f"   - {order.get('coin')}: {order.get('side')} {order.get('sz')} @ ${order.get('limitPx')}")
#     except Exception as e:
#         print(f"❌ Erreur: {e}")
    
#     # 5. Récupérer funding et OI
#     print("\n5️⃣ Récupération funding & open interest...")
#     try:
#         btc_funding = await api.get_funding_rate("BTC")
#         btc_oi = await api.get_open_interest("BTC")
#         print(f"✅ BTC Funding: {btc_funding:.6%}")
#         print(f"✅ BTC Open Interest: ${btc_oi:,.0f}")
#     except Exception as e:
#         print(f"❌ Erreur: {e}")
    
#     # 6. Test d'ordre
#     print("\n6️⃣ Test d'ordre...")
#     try:
#         # Petit ordre de test: 0.0001 ETH (~$0.38)
#         result = await api.place_buy_order("ETH", 0.0001, slippage=0.02)
#         print(f"✅ Ordre passé: {result}")
        
#         # Annuler immédiatement
#         oids = api.extract_oids(result)
#         if oids:
#             await api.cancel_order("ETH", oids[0])
#             print(f"✅ Ordre annulé: {oids[0]}")
#     except Exception as e:
#         print(f"❌ Erreur d'ordre: {e}")
    
#     print("\n" + "="*60)
#     print("✅ Tests terminés!")
#     print("="*60 + "\n")

# if __name__ == "__main__":
#     asyncio.run(test_hyperliquid())

"""Script de test pour vérifier la configuration Hyperliquid."""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent))

import asyncio
import logging
from src.config_loader import CONFIG
from src.trading.hyperliquid_api import HyperliquidAPI

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

async def test_hyperliquid():
    """Test les fonctionnalités de base de l'API Hyperliquid."""
    
    print("\n" + "="*60)
    print("TEST HYPERLIQUID API")
    print("="*60 + "\n")
    
    # DEBUG : Affiche TOUTES les adresses
    print("🔍 DEBUG - Configuration actuelle:")
    api = HyperliquidAPI()
    print(f"   Wallet agent utilisé: {api.wallet.address}")
    print(f"   Vault configuré: {CONFIG.get('hyperliquid_vault_address')}")
    print(f"\n   Agents autorisés sur Hyperliquid:")
    print(f"   - 0xcf53de1d22ce94ba285275c61931ffec82a23db6 (agent)")
    print(f"   - 0x4125992b8d859e1edaad428238ec0fa65ec8e5f1 (app.hyperliquid.xyz)")
    print("\n")
    
    # Test d'ordre
    print("6️⃣ Test d'ordre...")
    try:
        result = await api.place_buy_order("ETH", 0.0027, slippage=0.02)
        print(f"✅ Ordre passé: {result}")
        
        oids = api.extract_oids(result)
        if oids:
            await api.cancel_order("ETH", oids[0])
            print(f"✅ Ordre annulé: {oids[0]}")
    except Exception as e:
        print(f"❌ Erreur d'ordre: {e}")
    
    print("\n" + "="*60)
    print("✅ Tests terminés!")
    print("="*60 + "\n")

if __name__ == "__main__":
    asyncio.run(test_hyperliquid())