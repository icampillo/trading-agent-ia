import asyncio
import logging  # ✅ AJOUTE L'IMPORT
from src.trading.hyperliquid_api import HyperliquidAPI

# ✅ CONFIGURE LE LOGGING AVANT TOUT
logging.basicConfig(
    level=logging.INFO,  # ou DEBUG pour encore plus de détails
    format='%(asctime)s - %(levelname)s - %(message)s'
)

async def quick_test():
    api = HyperliquidAPI()
    state = await api.get_user_state()
    
    print("=" * 80)
    print("User State:")
    print("=" * 80)
    print(state)

asyncio.run(quick_test())