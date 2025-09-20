import configparser
import os
import signal
import sys
from queue import Queue
from threading import Event
from dotenv import load_dotenv

from data_handler import UpstoxDataHandler
from app import start_web_server
from utils import get_instrument_key
from auth import get_access_token, check_market_status # Import auth functions

# --- Global stop event for graceful shutdown ---
stop_event = Event()

def shutdown_handler(signum, frame):
    """Handle Ctrl+C gracefully."""
    print("\n🛑 Shutdown signal received. Cleaning up...")
    stop_event.set()
    sys.exit(0)

def main():
    # --- Setup ---
    signal.signal(signal.SIGINT, shutdown_handler)
    load_dotenv()
    
    config = configparser.ConfigParser()
    config.read('config.ini')

    api_key_env = os.getenv('UPSTOX_API_KEY')
    api_secret_env = os.getenv('UPSTOX_API_SECRET')
    if api_key_env: config.set('UPSTOX', 'API_KEY', api_key_env)
    if api_secret_env: config.set('UPSTOX', 'API_SECRET', api_secret_env)

    # --- Authentication ---
    access_token = get_access_token(config)
    if not access_token:
        print("❌ Authentication failed. Exiting.")
        sys.exit(1)
        
    # --- Market Status Check ---
    status = check_market_status(access_token)
    if status != "NORMAL_OPEN":
        print(f"⚠️ Market is {status}, but will connect to websocket anyway.")
        # Note: No snapshot data is fetched in this version, but you could add it here.

    # --- Load Instruments ---
    try:
        with open('instruments.txt', 'r') as f:
            symbols = [line.strip().upper() for line in f if line.strip()]
        
        instruments = {}
        for symbol in symbols:
            key = get_instrument_key(symbol)
            if key:
                instruments[symbol] = key
            else:
                print(f"⚠️ Warning: Symbol '{symbol}' not found in instrument map. Skipping.")
        
        if not instruments:
            print("❌ No valid instruments to track. Please check instruments.txt. Exiting.")
            sys.exit(1)
            
    except FileNotFoundError:
        print("❌ instruments.txt not found. Please create it. Exiting.")
        sys.exit(1)

    # --- Start Services ---
    data_queue = Queue()

    data_handler = UpstoxDataHandler(config, instruments, data_queue, stop_event, access_token)
    data_handler.start()

    start_web_server(data_queue, stop_event)
    
    data_handler.join()
    print("Application has shut down.")

if __name__ == "__main__":
    main()