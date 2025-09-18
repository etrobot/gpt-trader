from __future__ import annotations
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from freqtrade_client import health, forceentry, forceexit_by_pair

logger = logging.getLogger(__name__)


def execute_signals(signals: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Execute a batch of signals against Freqtrade API.

    signals: List of { pair: "BTC/USDT", side: "buy"|"sell", stake_amount?: number }
    Returns summary dict.
    """
    # Wait for Freqtrade API to be ready (retry a few times on cold start)
    ok = health()
    if not ok:
        import time
        retries = 6  # ~60s total
        for i in range(retries):
            time.sleep(10)
            if health():
                ok = True
                break
    if not ok:
        logger.error("Freqtrade API is not healthy or not reachable after retries")
        return {"success": False, "executed": 0, "errors": ["api_unhealthy"]}

    executed = 0
    errors: List[str] = []

    for sig in signals:
        pair = sig.get("pair")
        side = sig.get("side")
        stake = sig.get("stake_amount")
        if not pair or side not in ("buy", "sell"):
            errors.append(f"invalid_signal:{sig}")
            continue

        try:
            if side == "buy":
                if forceentry(pair, stake_amount=stake):
                    executed += 1
            else:  # sell
                closed = forceexit_by_pair(pair)
                executed += closed
        except Exception as e:
            logger.error(f"Execute signal failed for {pair} {side}: {e}")
            errors.append(str(e))

    return {"success": len(errors) == 0, "executed": executed, "errors": errors}
