import webbrowser
import requests
import sys
import logging

def open_auth_browser(config):
    """Opens the Upstox login dialog in the user's browser."""
    api_key = config.get('UPSTOX', 'API_KEY')
    redirect_uri = config.get('UPSTOX', 'REDIRECT_URI')
    auth_url = f"https://api-v2.upstox.com/v2/login/authorization/dialog?response_type=code&client_id={api_key}&redirect_uri={redirect_uri}"
    
    print("🌐 Opening browser for Upstox login...")
    logging.info(f"Opening browser for authorization at {auth_url}")
    webbrowser.open(auth_url)
    print("👉 After login, copy the 'code' from the redirected URL (http://127.0.0.1/?code=...)")

def get_token_from_code(config, code):
    """Exchanges the authorization code for a final access token."""
    api_key = config.get('UPSTOX', 'API_KEY')
    api_secret = config.get('UPSTOX', 'API_SECRET')
    redirect_uri = config.get('UPSTOX', 'REDIRECT_URI')
    
    payload = {
        "code": code,
        "client_id": api_key,
        "client_secret": api_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code"
    }
    
    token_url = "https://api-v2.upstox.com/login/authorization/token"
    logging.info(f"Requesting access token from {token_url}")
    
    try:
        r = requests.post(token_url, data=payload)
        r.raise_for_status()
        data = r.json()
        
        if "access_token" in data:
            print("✅ Got access_token")
            logging.info("Successfully received access token.")
            return data["access_token"]
        else:
            print("❌ Token error:", data)
            logging.error(f"Failed to get access token. Response: {data}")
            return None
    except requests.RequestException as e:
        print(f"❌ HTTP Request failed: {e}")
        logging.error(f"HTTP Request failed while getting token: {e}")
        return None

def get_access_token(config):
    """Orchestrates the entire authentication flow."""
    open_auth_browser(config)
    auth_code = input("📋 Paste your AUTH_CODE from browser (fresh): ").strip()
    if not auth_code:
        return None
    
    return get_token_from_code(config, auth_code)

def check_market_status(token):
    """Checks the current status of the NSE equity market."""
    market_status_url = "https://api-v2.upstox.com/v2/market/status"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(market_status_url, headers=headers)
        r.raise_for_status()
        data = r.json().get("data", {})
        status = data.get("NSE_EQ", "UNKNOWN")
        logging.info(f"Market status for NSE_EQ is {status}")
        return status
    except requests.RequestException as e:
        logging.error(f"Failed to check market status: {e}")
        return "UNKNOWN"