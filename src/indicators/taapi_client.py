"""Client helper for interacting with the TAAPI technical analysis API."""

import requests
import os
import time
import logging


class TAAPIClient:
    """Fetches TA indicators with retry/backoff semantics for resilience."""

    def __init__(self):
        """Initialize TAAPI credentials and base URL."""
        self.api_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJjbHVlIjoiNjkwM2FlYzE4MDZmZjE2NTFlNjQzZmYyIiwiaWF0IjoxNzYxODQ5MjkwLCJleHAiOjMzMjY2MzEzMjkwfQ.7Z44TZQxzpPcuPxF_Km9okrnLRToN0dm8g6mo9Sn4pw"
        self.base_url = "https://api.taapi.io/"

    def _get_with_retry(self, url, params, retries=3, backoff=0.5):
        """Perform a GET request with exponential backoff retry logic."""
        for attempt in range(retries):
            try:
                resp = requests.get(url, params=params, timeout=10)
                resp.raise_for_status()
                return resp.json()

            except requests.HTTPError as e:
                if e.response.status_code == 429:  # Rate Limit
                    logging.warning("TAAPI Rate Limit (429), waiting 15s")
                    time.sleep(15)
                    continue
                if e.response.status_code >= 500 and attempt < retries - 1:
                    wait = backoff * (2 ** attempt)
                    logging.warning(f"TAAPI {e.response.status_code}, retrying in {wait}s")
                    time.sleep(wait)
                else:
                    raise
            except requests.Timeout as e:
                if attempt < retries - 1:
                    wait = backoff * (2 ** attempt)
                    logging.warning(f"TAAPI timeout, retrying in {wait}s")
                    time.sleep(wait)
                else:
                    raise
        raise RuntimeError("Max retries exceeded")

    def get_indicators(self, asset, interval):
        """Return a curated bundle of intraday indicators for ``asset``."""
        params = {
            "secret": self.api_key,
            "exchange": "binance",
            "symbol": f"{asset}/USDT",
            "interval": interval
        }
        rsi_response = self._get_with_retry(f"{self.base_url}rsi", params)
        macd_response = self._get_with_retry(f"{self.base_url}macd", params)
        sma_response = self._get_with_retry(f"{self.base_url}sma", params)
        ema_response = self._get_with_retry(f"{self.base_url}ema", params)
        bbands_response = self._get_with_retry(f"{self.base_url}bbands", params)
        return {
            "rsi": rsi_response.get("value"),
            "macd": macd_response,
            "sma": sma_response.get("value"),
            "ema": ema_response.get("value"),
            "bbands": bbands_response
        }

    def get_historical_indicator(self, indicator, symbol, interval, results=10, params=None):
        """Fetch historical indicator data with optional overrides."""
        base_params = {
            "secret": self.api_key,
            "exchange": "binance",
            "symbol": symbol,
            "interval": interval,
            "results": results
        }
        if params:
            base_params.update(params)
        response = self._get_with_retry(f"{self.base_url}{indicator}", base_params)
        return response

    def fetch_series(self, indicator: str, symbol: str, interval: str, results: int = 10, params: dict | None = None, value_key: str = "value") -> list:
        """Fetch and normalize a historical indicator series.

        Args:
            indicator: TAAPI indicator slug (e.g. ``"ema"``).
            symbol: Market pair identifier (e.g. ``"BTC/USDT"``).
            interval: Candle interval requested from TAAPI.
            results: Number of datapoints to request.
            params: Additional TAAPI query parameters.
            value_key: Key to extract from the TAAPI response payload.
python3.12 --version
        Returns:
            List of floats rounded to 4 decimals, or an empty list on error.
        """
        try:
            data = self.get_historical_indicator(indicator, symbol, interval, results=results, params=params)
            if isinstance(data, dict):
                # Simple indicators: {"value": [1,2,3]}
                if value_key in data and isinstance(data[value_key], list):
                    return [round(v, 4) if isinstance(v, (int, float)) else v for v in data[value_key]]
                # Error response
                if "error" in data:
                    import logging
                    logging.error(f"TAAPI error for {indicator} {symbol} {interval}: {data.get('error')}")
                    return []
            return []
        except Exception as e:
            import logging
            logging.error(f"TAAPI fetch_series exception for {indicator}: {e}")
            return []

    def fetch_value(self, indicator: str, symbol: str, interval: str, params: dict | None = None, key: str = "value"):
        """Fetch a single indicator value for the latest candle."""
        try:
            base_params = {
                "secret": self.api_key,
                "exchange": "binance",
                "symbol": symbol,
                "interval": interval
            }
            if params:
                base_params.update(params)
            data = self._get_with_retry(f"{self.base_url}{indicator}", base_params)
            if isinstance(data, dict):
                val = data.get(key)
                return round(val, 4) if isinstance(val, (int, float)) else val
            return None
        except Exception:
            return None

# """
# TAAPI Market Data Fetcher - Version identique au projet original
# Récupère les indicateurs techniques depuis TAAPI.io
# """

# import requests
# import json
# from datetime import datetime
# import time

# class TaapiClient:
#     """
#     Client pour l'API TAAPI - Identique au projet original
#     Récupère les indicateurs techniques pré-calculés
#     """
    
#     def __init__(self, api_key):
#         """
#         Initialise le client TAAPI
        
#         Args:
#             api_key: Ta clé API TAAPI (depuis taapi.io)
#         """
#         self.api_key = api_key
#         self.base_url = "https://api.taapi.io"
        
#     def get_indicator(self, indicator, symbol="BTC/USDT", exchange="binance", 
#                      interval="1h", **kwargs):
#         """
#         Récupère un indicateur spécifique
        
#         Args:
#             indicator: Nom de l'indicateur (rsi, ema, macd, etc.)
#             symbol: Paire de trading (ex: BTC/USDT, ETH/USDT)
#             exchange: Exchange à utiliser (binance par défaut)
#             interval: Timeframe (1m, 5m, 15m, 1h, 4h, 1d)
#             **kwargs: Paramètres additionnels (ex: period=14 pour RSI)
        
#         Returns:
#             dict: Données de l'indicateur
#         """
#         try:
#             print(f"⏳ Requête {indicator}... (15s entre chaque requête)")
#             time.sleep(15)
#             # Construction de l'URL
#             url = f"{self.base_url}/{indicator}"
            
#             # Paramètres de base
#             params = {
#                 "secret": self.api_key,
#                 "exchange": exchange,
#                 "symbol": symbol,
#                 "interval": interval
#             }
            
#             # Ajoute les paramètres supplémentaires (ex: period, backtrack)
#             params.update(kwargs)
            
#             # Requête à l'API
#             response = requests.get(url, params=params)
#             response.raise_for_status()
            
#             data = response.json()
            
#             return {
#                 "indicator": indicator,
#                 "symbol": symbol,
#                 "interval": interval,
#                 "value": data.get("value"),
#                 "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
#                 "raw_data": data
#             }
            
#         except requests.exceptions.HTTPError as e:
#             if e.response.status_code == 401:
#                 print(f"❌ Erreur 401: Clé API invalide ou expirée")
#             elif e.response.status_code == 429:
#                 print(f"❌ Erreur 429: Limite de requêtes atteinte")
#             else:
#                 print(f"❌ Erreur HTTP {e.response.status_code}: {e}")
#             return None
            
#         except Exception as e:
#             print(f"❌ Erreur lors de la récupération de {indicator}: {e}")
#             return None
    
#     def get_price(self, symbol="BTC/USDT", exchange="binance"):
#         """
#         Récupère le prix actuel
        
#         Returns:
#             dict: Prix actuel et infos
#         """
#         result = self.get_indicator("price", symbol, exchange, interval="1h")
        
#         if result and result['value']:
#             return {
#                 "symbol": symbol,
#                 "price": float(result['value']),
#                 "timestamp": result['timestamp']
#             }
#         return None
    
#     def get_rsi(self, symbol="BTC/USDT", exchange="binance", interval="1h", period=14):
#         """
#         Récupère le RSI (Relative Strength Index)
        
#         RSI > 70 = Surachat (potentiel de baisse)
#         RSI < 30 = Survente (potentiel de hausse)
        
#         Args:
#             period: Période de calcul (standard: 14)
        
#         Returns:
#             float: Valeur du RSI
#         """
#         result = self.get_indicator("rsi", symbol, exchange, interval, period=period)
#         return float(result['value']) if result and result['value'] else None
    
#     def get_ema(self, symbol="BTC/USDT", exchange="binance", interval="1h", period=20):
#         """
#         Récupère l'EMA (Exponential Moving Average)
#         Moyenne mobile qui réagit plus vite aux changements récents
        
#         Args:
#             period: Période de calcul (ex: 20, 50, 200)
        
#         Returns:
#             float: Valeur de l'EMA
#         """
#         result = self.get_indicator("ema", symbol, exchange, interval, period=period)
#         return float(result['value']) if result and result['value'] else None
    
#     def get_sma(self, symbol="BTC/USDT", exchange="binance", interval="1h", period=20):
#         """
#         Récupère la SMA (Simple Moving Average)
#         Moyenne mobile simple
        
#         Args:
#             period: Période de calcul
        
#         Returns:
#             float: Valeur de la SMA
#         """
#         result = self.get_indicator("sma", symbol, exchange, interval, period=period)
#         return float(result['value']) if result and result['value'] else None
    
#     def get_macd(self, symbol="BTC/USDT", exchange="binance", interval="1h"):
#         """
#         Récupère le MACD (Moving Average Convergence Divergence)
#         Indicateur de tendance et momentum
        
#         Returns:
#             dict: valueMACD, valueMACDSignal, valueMACDHist
#         """
#         result = self.get_indicator("macd", symbol, exchange, interval)
        
#         if result and result['raw_data']:
#             data = result['raw_data']
#             return {
#                 "macd": float(data.get('valueMACD', 0)),
#                 "signal": float(data.get('valueMACDSignal', 0)),
#                 "histogram": float(data.get('valueMACDHist', 0))
#             }
#         return None
    
#     def get_bbands(self, symbol="BTC/USDT", exchange="binance", interval="1h", period=20):
#         """
#         Récupère les Bandes de Bollinger
#         Indicateur de volatilité
        
#         Returns:
#             dict: upper, middle, lower
#         """
#         result = self.get_indicator("bbands", symbol, exchange, interval, period=period)
        
#         if result and result['raw_data']:
#             data = result['raw_data']
#             return {
#                 "upper": float(data.get('valueUpperBand', 0)),
#                 "middle": float(data.get('valueMiddleBand', 0)),
#                 "lower": float(data.get('valueLowerBand', 0))
#             }
#         return None
    
#     def get_volume(self, symbol="BTC/USDT", exchange="binance", interval="1h"):
#         """
#         Récupère le volume
        
#         Returns:
#             float: Volume
#         """
#         result = self.get_indicator("volume", symbol, exchange, interval)
#         return float(result['value']) if result and result['value'] else None
    
#     def get_full_market_analysis(self, symbol="BTC/USDT", exchange="binance", interval="1h"):
#         """
#         Récupère TOUS les indicateurs en une fois
#         Comme dans le projet original pour alimenter l'IA
        
#         Returns:
#             dict: Analyse complète du marché
#         """
#         print(f"\n📊 Analyse complète de {symbol} sur {interval}")
#         print("=" * 70)
#         print("⏳ Récupération des données depuis TAAPI...")
        
#         # Récupère tous les indicateurs
#         price = self.get_price(symbol, exchange)
#         rsi = self.get_rsi(symbol, exchange, interval, period=14)
#         ema_20 = self.get_ema(symbol, exchange, interval, period=20)
#         ema_50 = self.get_ema(symbol, exchange, interval, period=50)
#         ema_200 = self.get_ema(symbol, exchange, interval, period=200)
#         sma_20 = self.get_sma(symbol, exchange, interval, period=20)
#         sma_50 = self.get_sma(symbol, exchange, interval, period=50)
#         macd = self.get_macd(symbol, exchange, interval)
#         bbands = self.get_bbands(symbol, exchange, interval, period=20)
#         volume = self.get_volume(symbol, exchange, interval)
        
#         # Construit l'analyse complète
#         analysis = {
#             "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
#             "symbol": symbol,
#             "exchange": exchange,
#             "interval": interval,
#             "price": price['price'] if price else None,
#             "rsi": rsi,
#             "moving_averages": {
#                 "ema_20": ema_20,
#                 "ema_50": ema_50,
#                 "ema_200": ema_200,
#                 "sma_20": sma_20,
#                 "sma_50": sma_50
#             },
#             "macd": macd,
#             "bollinger_bands": bbands,
#             "volume": volume
#         }
        
#         # Affiche l'analyse
#         self._print_analysis(analysis)
        
#         return analysis
    
#     def _print_analysis(self, analysis):
#         """Affiche l'analyse formatée - Style du projet original"""
        
#         print(f"\n⏰ Timestamp: {analysis['timestamp']}")
#         print(f"🔗 Exchange: {analysis['exchange']}")
        
#         # Prix
#         if analysis['price']:
#             print(f"\n💰 PRIX ACTUEL")
#             print(f"  {analysis['symbol']}: ${analysis['price']:,.2f}")
        
#         # RSI
#         if analysis['rsi']:
#             rsi = analysis['rsi']
#             if rsi > 70:
#                 rsi_status = "⚠️  SURACHAT - Potentiel de baisse"
#                 emoji = "🔴"
#             elif rsi < 30:
#                 rsi_status = "✅ SURVENTE - Potentiel de hausse"
#                 emoji = "🟢"
#             else:
#                 rsi_status = "⚖️  NEUTRE"
#                 emoji = "🟡"
            
#             print(f"\n🎯 RSI (14): {rsi:.2f} {emoji}")
#             print(f"  Status: {rsi_status}")
        
#         # Moyennes mobiles
#         ma = analysis['moving_averages']
#         if ma['ema_20'] and ma['ema_50']:
#             trend = "🟢 HAUSSIÈRE" if ma['ema_20'] > ma['ema_50'] else "🔴 BAISSIÈRE"
#             print(f"\n📐 MOYENNES MOBILES - Tendance {trend}")
#             print(f"  EMA 20:  ${ma['ema_20']:,.2f}")
#             print(f"  EMA 50:  ${ma['ema_50']:,.2f}")
#             print(f"  EMA 200: ${ma['ema_200']:,.2f}" if ma['ema_200'] else "")
#             print(f"  SMA 20:  ${ma['sma_20']:,.2f}" if ma['sma_20'] else "")
#             print(f"  SMA 50:  ${ma['sma_50']:,.2f}" if ma['sma_50'] else "")
        
#         # MACD
#         if analysis['macd']:
#             macd = analysis['macd']
#             macd_trend = "🟢 HAUSSIER" if macd['histogram'] > 0 else "🔴 BAISSIER"
#             print(f"\n📊 MACD {macd_trend}")
#             print(f"  MACD:      {macd['macd']:,.2f}")
#             print(f"  Signal:    {macd['signal']:,.2f}")
#             print(f"  Histogram: {macd['histogram']:,.2f}")
        
#         # Bollinger Bands
#         if analysis['bollinger_bands']:
#             bb = analysis['bollinger_bands']
#             print(f"\n📏 BANDES DE BOLLINGER")
#             print(f"  Upper:  ${bb['upper']:,.2f}")
#             print(f"  Middle: ${bb['middle']:,.2f}")
#             print(f"  Lower:  ${bb['lower']:,.2f}")
            
#             if analysis['price']:
#                 if analysis['price'] >= bb['upper']:
#                     print(f"  ⚠️  Prix touche la bande haute (potentiel retournement)")
#                 elif analysis['price'] <= bb['lower']:
#                     print(f"  ✅ Prix touche la bande basse (potentiel rebond)")
        
#         # Volume
#         if analysis['volume']:
#             print(f"\n📊 VOLUME: {analysis['volume']:,.0f}")
        
#         print("\n" + "=" * 70)
    
#     def monitor_continuous(self, symbols=["BTC/USDT", "ETH/USDT"], 
#                           exchange="binance", interval="1h", refresh_minutes=5):
#         """
#         Surveille plusieurs cryptos en continu - Comme l'agent de trading
        
#         Args:
#             symbols: Liste des paires à surveiller
#             exchange: Exchange à utiliser
#             interval: Timeframe
#             refresh_minutes: Minutes entre chaque refresh
#         """
#         print(f"\n🔄 MODE SURVEILLANCE CONTINUE")
#         print(f"📊 Assets: {', '.join(symbols)}")
#         print(f"⏱️  Refresh: toutes les {refresh_minutes} minutes")
#         print(f"⌨️  Press Ctrl+C pour arrêter\n")
        
#         try:
#             cycle = 1
#             while True:
#                 print(f"\n{'='*70}")
#                 print(f"🔄 CYCLE #{cycle} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
#                 print(f"{'='*70}")
                
#                 for symbol in symbols:
#                     analysis = self.get_full_market_analysis(symbol, exchange, interval)
                    
#                     # Pause entre chaque asset pour ne pas surcharger l'API
#                     time.sleep(3)
                
#                 cycle += 1
#                 print(f"\n⏳ Prochain cycle dans {refresh_minutes} minutes...")
#                 time.sleep(refresh_minutes * 60)
                
#         except KeyboardInterrupt:
#             print(f"\n\n👋 Surveillance arrêtée après {cycle-1} cycles")


# # ============================================
# # CONFIGURATION ET EXEMPLES
# # ============================================

# # ⚠️ REMPLACE PAR TA CLÉ API TAAPI
# TAAPI_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJjbHVlIjoiNjkwM2FlYzE4MDZmZjE2NTFlNjQzZmYyIiwiaWF0IjoxNzYxODQ5MjkwLCJleHAiOjMzMjY2MzEzMjkwfQ.7Z44TZQxzpPcuPxF_Km9okrnLRToN0dm8g6mo9Sn4pw"

# if __name__ == "__main__":
    
#     print("🚀 TAAPI Market Data Fetcher")
#     print("=" * 70)
    
#     # Vérifie que la clé API est configurée
#     if TAAPI_API_KEY == "TU_METS_TA_CLE_ICI":
#         print("\n❌ ERREUR: Tu dois configurer ta clé API TAAPI !")
#         print("\n📝 Étapes:")
#         print("   1. Va sur https://taapi.io/")
#         print("   2. Créer un compte gratuit")
#         print("   3. Copie ta clé API")
#         print("   4. Remplace 'TU_METS_TA_CLE_ICI' dans le code\n")
#         exit(1)
    
#     # Crée le client TAAPI
#     client = TaapiClient(TAAPI_API_KEY)
    
#     # ============================================
#     # EXEMPLE 1: Prix actuel
#     # ============================================
#     print("\n📍 EXEMPLE 1: Prix actuel")
#     price = client.get_price("BTC/USDT")
#     if price:
#         print(f"✅ Prix BTC: ${price['price']:,.2f}")
    
#     time.sleep(2)
    
#     # ============================================
#     # EXEMPLE 2: RSI uniquement
#     # ============================================
#     print("\n📍 EXEMPLE 2: RSI uniquement")
#     rsi = client.get_rsi("BTC/USDT", interval="1h")
#     if rsi:
#         print(f"✅ RSI BTC: {rsi:.2f}")
    
#     time.sleep(2)
    
#     # ============================================
#     # EXEMPLE 3: Analyse complète BTC
#     # ============================================
#     print("\n📍 EXEMPLE 3: Analyse complète BTC")
#     btc_analysis = client.get_full_market_analysis("BTC/USDT", interval="1h")
    
#     time.sleep(2)
    
#     # ============================================
#     # EXEMPLE 4: Analyse complète ETH
#     # ============================================
#     print("\n📍 EXEMPLE 4: Analyse complète ETH")
#     eth_analysis = client.get_full_market_analysis("ETH/USDT", interval="1h")
    
#     # ============================================
#     # EXEMPLE 5: Surveillance continue (décommenter pour activer)
#     # ============================================
#     # print("\n📍 EXEMPLE 5: Surveillance continue")
#     # client.monitor_continuous(
#     #     symbols=["BTC/USDT", "ETH/USDT", "SOL/USDT"],
#     #     interval="1h",
#     #     refresh_minutes=5
#     # )
    
#     print("\n✅ Démonstration terminée!")
#     print("\n💡 PROCHAINE ÉTAPE:")
#     print("   → Décommente 'monitor_continuous' pour surveiller en continu")
#     print("   → Ces données seront envoyées à l'IA pour décider (prochaine étape)\n")