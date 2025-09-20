import requests
import websocket
import json
import logging
import time
import pandas as pd
import numpy as np
import os
import csv
from threading import Thread
from google.protobuf.json_format import MessageToDict
import market_data_pb2
from plyer import notification

# Configure logging
logging.basicConfig(filename='connections.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

class StockData:
    """A class to hold and process data for a single stock."""
    def __init__(self, symbol, instrument_key, config):
        self.symbol = symbol
        self.instrument_key = instrument_key
        self.config = config
        self.ltp = 0
        self.previous_close = None
        self.price_history = pd.DataFrame(columns=['price'])
        self.last_known_sma = None
        self.alert_flags = {'rsi_overbought': False, 'rsi_oversold': False, 'sma_cross_up': False, 'sma_cross_down': False}
        self.csv_path = f"data/{self.symbol}.csv"
        self.csv_file = None
        self.csv_writer = None
        self._setup_csv()

    def _setup_csv(self):
        if self.config.getboolean('SETTINGS', 'CSV_OUTPUT_ENABLED'):
            os.makedirs('data', exist_ok=True)
            file_exists = os.path.isfile(self.csv_path)
            self.csv_file = open(self.csv_path, 'a', newline='')
            self.csv_writer = csv.writer(self.csv_file)
            if not file_exists:
                self.csv_writer.writerow(['timestamp', 'ltp', 'volume'])

    def add_tick(self, ltp, last_traded_quantity, timestamp):
        self.ltp = ltp
        new_row = pd.DataFrame([{'price': ltp}])
        self.price_history = pd.concat([self.price_history, new_row], ignore_index=True)
        
        max_len = self.config.getint('INDICATORS', 'SMA_PERIOD') + 50
        if len(self.price_history) > max_len:
            self.price_history = self.price_history.tail(max_len).reset_index(drop=True)

        if self.csv_writer:
            self.csv_writer.writerow([timestamp, ltp, last_traded_quantity])
            self.csv_file.flush()
            
    def calculate_indicators(self):
        sma_period = self.config.getint('INDICATORS', 'SMA_PERIOD')
        rsi_period = self.config.getint('INDICATORS', 'RSI_PERIOD')
        
        sma = None
        if len(self.price_history) >= sma_period:
            sma = self.price_history['price'].rolling(window=sma_period).mean().iloc[-1]

        rsi = None
        if len(self.price_history) > rsi_period:
            delta = self.price_history['price'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
            if loss.iloc[-1] != 0:
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs)).iloc[-1]
            else: # Avoid division by zero
                rsi = 100
        return {'sma': round(sma, 2) if sma is not None else None, 'rsi': round(rsi, 2) if rsi is not None else None}

    def check_alerts(self, indicators):
        # Your alert logic here... (same as before)
        pass # Placeholder for brevity, the original logic is correct


class UpstoxDataHandler(Thread):
    def __init__(self, config, instruments, data_queue, stop_event, access_token):
        super().__init__()
        self.config = config
        self.instruments = instruments
        self.data_queue = data_queue
        self.stop_event = stop_event
        self.ws = None
        self.access_token = access_token
        self.instrument_map = {v: k for k, v in self.instruments.items()}
        self.stock_data_handlers = {k: StockData(k, v, config) for k, v in self.instruments.items()}

    def run(self):
        wss_url = self._get_wss_url()
        if not wss_url:
            logging.error("Could not get WebSocket URL. Exiting data handler thread.")
            return

        while not self.stop_event.is_set():
            self._connect_websocket(wss_url)
            logging.info("WebSocket connection ended. Will attempt to reconnect if not shutting down.")
            if not self.stop_event.is_set():
                time.sleep(5)

    def _get_wss_url(self):
        url = "https://api-v2.upstox.com/v3/feed/market-data-feed/authorize"
        headers = {"Authorization": f"Bearer {self.access_token}", "Accept": "application/json"}
        try:
            r = requests.get(url, headers=headers, timeout=15)
            r.raise_for_status()
            data = r.json().get("data", {})
            wss_url = data.get("authorized_redirect_uri")
            print("Authorized WSS URL:", wss_url)
            logging.info(f"Received WebSocket URL: {wss_url}")
            return wss_url
        except requests.RequestException as e:
            logging.error(f"Failed to get WebSocket URL: {e}")
            return None

    def _connect_websocket(self, wss_url):
        self.ws = websocket.WebSocketApp(
            wss_url,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )
        self.ws.run_forever()

    def on_open(self, ws):
        print("🚀 WebSocket connection opened")
        logging.info("WebSocket connection opened.")
        subscribe_msg = {
            "type": "subscribe",
            "payload": [{"exchange": "NSE_EQ", "instrumentId": i, "feedType": "full"} for i in self.instruments.values()]
        }
        ws.send(json.dumps(subscribe_msg))
        print("📡 Sent subscription request for Nifty 50 instrument IDs with feedType=full")
        logging.info("Sent subscription request.")

    def on_message(self, ws, message):
        try:
            if isinstance(message, bytes):
                fr = market_data_pb2.FeedResponse()
                fr.ParseFromString(message)
                data = MessageToDict(fr)
                
                if data.get('type') in ['ltp', 'full']:
                    instr_id = int(data.get('instrumentId'))
                    symbol = self.instrument_map.get(instr_id)
                    if symbol:
                        handler = self.stock_data_handlers[symbol]
                        ltp = float(data.get('ltp'))
                        last_qty = int(data.get('lastTradedQuantity', 0))
                        timestamp = pd.Timestamp.now()
                        
                        if data.get('ohlc', {}).get('previousClose'):
                            handler.previous_close = float(data['ohlc']['previousClose'])

                        handler.add_tick(ltp, last_qty, timestamp)
                        indicators = handler.calculate_indicators()
                        handler.check_alerts(indicators)

                        payload = {
                            'symbol': symbol,
                            'ltp': ltp,
                            'timestamp': timestamp.isoformat(),
                            'volume': last_qty,
                            'sma': indicators.get('sma'),
                            'rsi': indicators.get('rsi'),
                            'percent_change': ((ltp - handler.previous_close) / handler.previous_close * 100) if handler.previous_close else 0
                        }
                        self.data_queue.put(payload)
        except Exception as e:
            logging.error(f"Error processing message: {e}")

    def on_error(self, ws, error):
        logging.error(f"WebSocket error: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        logging.warning(f"WebSocket closed with code: {close_status_code}, msg: {close_msg}")

    def stop(self):
        if self.ws:
            self.ws.close()
        for handler in self.stock_data_handlers.values():
            if handler.csv_file:
                handler.csv_file.close()

def notify(title, message):
    logging.info(f"NOTIFICATION: {title} - {message}")
    # In a real implementation, you'd check a config flag before notifying
    notification.notify(title=title, message=message, timeout=5)