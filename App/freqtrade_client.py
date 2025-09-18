from __future__ import annotations
import os
import logging
from typing import Optional, Dict, Any, List
import requests

logger = logging.getLogger(__name__)

# Environment-based configuration
API_BASE_URL = os.getenv("FREQTRADE_API_URL", "http://freqtrade-bot01:8080")  # default to docker service
API_USERNAME = os.getenv("FREQTRADE_API_USERNAME")
API_PASSWORD = os.getenv("FREQTRADE_API_PASSWORD")
API_TOKEN = os.getenv("FREQTRADE_API_TOKEN")  # If provided and valid (JWT), preferred over username/password
REQUEST_TIMEOUT = int(os.getenv("FREQTRADE_API_TIMEOUT", "15"))


def _api_url(path: str) -> str:
    path = path if path.startswith("/") else f"/{path}"
    # Freqtrade usually serves under /api/v1
    if not path.startswith("/api/"):
        path = f"/api/v1{path}"
    return f"{API_BASE_URL.rstrip('/')}{path}"


def _get_headers(token: Optional[str]) -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _load_creds_from_config() -> Optional[tuple]:
    """Try to load API basic-auth credentials from a Freqtrade config file.
    Searches common paths mounted into the app container.
    Returns (username, password) or None.
    """
    import json
    import os

    candidates = [
        os.getenv("FREQTRADE_CONFIG_PATH", "/app/user_data/config_external_signals.json"),
        os.path.join(os.getcwd(), "user_data", "config_external_signals.json"),
        os.path.join(os.getcwd(), "user_data", "config.json"),
        os.path.join(os.getcwd(), "user_data", "config_external_signals.json.backup"),
    ]
    for path in candidates:
        try:
            if not path:
                continue
            if not os.path.exists(path):
                continue
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            api = cfg.get("api_server") or {}
            user = api.get("username")
            pwd = api.get("password")
            if user and pwd:
                logger.info(f"Loaded Freqtrade API credentials from {path}")
                return (user, pwd)
        except Exception as e:
            logger.warning(f"Failed reading Freqtrade config at {path}: {e}")
    return None


def _get_auth() -> Optional[tuple]:
    """Get basic authentication credentials."""
    global API_USERNAME, API_PASSWORD
    if API_USERNAME and API_PASSWORD:
        return (API_USERNAME, API_PASSWORD)
    # Fallback: try to load from mounted Freqtrade config
    creds = _load_creds_from_config()
    if creds:
        API_USERNAME, API_PASSWORD = creds  # cache for later
        return creds
    return None


def obtain_token() -> Optional[str]:
    """Freqtrade API uses basic authentication, not JWT tokens.
    This function is kept for compatibility but returns None since we use basic auth.
    """
    global API_TOKEN
    # Freqtrade doesn't use JWT tokens - it uses basic auth
    # Return None to force basic auth usage
    logger.info("Freqtrade API uses basic authentication, not JWT tokens")
    return None


def _get_token_if_needed(token: Optional[str] = None) -> Optional[str]:
    """Helper function for token compatibility. Freqtrade uses basic auth, so returns None."""
    # Freqtrade uses basic authentication, not tokens
    return None


def get_api_credentials() -> Dict[str, Optional[str]]:
    """Get current API credentials configuration."""
    return {
        "api_url": API_BASE_URL,
        "username": API_USERNAME,
        "password": "***" if API_PASSWORD else None,  # Hide password
        "has_token": bool(API_TOKEN),
        "timeout": REQUEST_TIMEOUT
    }


def test_credentials() -> Dict[str, Any]:
    """Test Freqtrade API credentials and connection."""
    result = {
        "api_url": API_BASE_URL,
        "credentials_available": bool(API_USERNAME and API_PASSWORD),
        "connection_healthy": False,
        "basic_auth_working": False,
        "error": None
    }
    
    try:
        # Test connection with basic auth
        if health():
            result["connection_healthy"] = True
            result["basic_auth_working"] = True
        
    except Exception as e:
        result["error"] = str(e)
        logger.error(f"Credential test failed: {e}")
    
    return result


def refresh_token() -> Optional[str]:
    """Freqtrade uses basic auth, no token refresh needed."""
    return None


def health(token: Optional[str] = None) -> bool:
    """Check if Freqtrade API is healthy."""
    try:
        url = _api_url("/ping")
        auth = _get_auth()
        # Try with auth first if available
        if auth:
            resp = requests.get(url, auth=auth, timeout=REQUEST_TIMEOUT, proxies=None)
            if resp.ok:
                return True
            # If unauthorized, fall back to unauthenticated ping (some setups allow it)
            if resp.status_code not in (401, 403):
                return False
        # Try without auth as fallback
        resp2 = requests.get(url, timeout=REQUEST_TIMEOUT, proxies=None)
        return resp2.ok
    except Exception as e:
        logger.warning(f"Freqtrade API health check failed: {e}")
        return False


def list_open_trades(token: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get list of open trades from Freqtrade."""
    try:
        auth = _get_auth()
        if not auth:
            logger.error("No Freqtrade API credentials available")
            return []
            
        url = _api_url("/status")
        resp = requests.get(url, auth=auth, timeout=REQUEST_TIMEOUT, proxies=None)
        resp.raise_for_status()
        
        data = resp.json()
        if isinstance(data, dict) and "trades" in data:
            return data.get("trades", [])
        return data if isinstance(data, list) else []
    except Exception as e:
        logger.error(f"Failed to list open trades: {e}")
        return []


def forceentry(pair: str, stake_amount: Optional[float] = None, token: Optional[str] = None) -> bool:
    """Force entry (buy) for a trading pair.
    Tries multiple Freqtrade API endpoints for compatibility across versions.
    """
    payload: Dict[str, Any] = {"pair": pair}
    if stake_amount is not None:
        payload["stake_amount"] = stake_amount
    try:
        auth = _get_auth()
        if not auth:
            logger.error("No Freqtrade API credentials available")
            return False

        # Preferred endpoint
        endpoints = ["/forcebuy", "/forceenter"]
        last_err = None
        for ep in endpoints:
            try:
                url = _api_url(ep)
                resp = requests.post(url, json=payload, auth=auth, timeout=REQUEST_TIMEOUT, proxies=None)
                if resp.ok:
                    logger.info(f"Force buy sent for {pair} via {ep}")
                    return True
                else:
                    # If 404, try next endpoint
                    if resp.status_code == 404:
                        last_err = f"{resp.status_code} {resp.text}"
                        continue
                    logger.error(f"Force buy failed for {pair} via {ep}: {resp.status_code} {resp.text}")
                    last_err = f"{resp.status_code} {resp.text}"
            except Exception as ex:
                last_err = str(ex)
                logger.warning(f"Force buy attempt via {ep} raised: {ex}")
        if last_err:
            logger.error(f"Force buy failed for {pair}: {last_err}")
    except Exception as e:
        logger.error(f"Force buy exception for {pair}: {e}")
    return False


def forceexit_by_pair(pair: str, token: Optional[str] = None) -> int:
    """Force-exit all open trades for a given pair. Returns number of closes attempted."""
    auth = _get_auth()
    if not auth:
        logger.error("No Freqtrade API credentials available")
        return 0

    # Try direct forcesell by pair (newer API), fallback to closing by trade id
    try:
        url = _api_url("/forcesell")
        resp = requests.post(url, json={"pair": pair}, auth=auth, timeout=REQUEST_TIMEOUT, proxies=None)
        if resp.ok:
            logger.info(f"Force sell sent for pair {pair}")
            return 1
        elif resp.status_code != 404:
            logger.error(f"Force sell failed for {pair}: {resp.status_code} {resp.text}")
    except Exception as e:
        logger.warning(f"Force sell by pair failed for {pair}: {e}")

    # Fallback: iterate open trades and close those matching the pair
    trades = list_open_trades(token)
    count = 0
    for t in trades:
        if t.get("pair") == pair:
            trade_id = t.get("trade_id") or t.get("id")
            if trade_id is None:
                continue
            try:
                # Try both endpoints for compatibility
                for ep in (f"/forcesell/{trade_id}", f"/forceexit/{trade_id}"):
                    try:
                        url = _api_url(ep)
                        resp = requests.post(url, auth=auth, timeout=REQUEST_TIMEOUT, proxies=None)
                        if resp.ok:
                            count += 1
                            logger.info(f"Force sell/exit succeeded for trade {trade_id} via {ep}")
                            break
                        elif resp.status_code == 404:
                            continue
                        else:
                            logger.error(f"Force sell/exit failed for trade {trade_id} via {ep}: {resp.status_code} {resp.text}")
                    except Exception as e2:
                        logger.warning(f"Force sell/exit attempt via {ep} raised: {e2}")
            except Exception as e:
                logger.error(f"Force exit exception for trade {trade_id} ({pair}): {e}")
    return count


# Note: Function uses /forceenter endpoint but keeps forceentry name for backward compatibility
