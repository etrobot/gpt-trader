from __future__ import annotations
import logging
from typing import List, Dict, Any, Optional, Tuple
from models import Task, TaskResult
from utils import get_last_completed_task

logger = logging.getLogger(__name__)


def _extract_ranked_pairs_from_task(task: Task, top_n: int = 5) -> List[str]:
    """Extract top N symbol pairs (like "BTC/USDT") from the latest analysis task result.
    We expect task.result['data'] to contain items with 'symbol' and 'name' (e.g., 'BTC/USDT').
    If 'name' is missing, fallback to infer 'BASE/USDT' from symbol (e.g., BTCUSDT -> BTC/USDT).
    """
    if not task or not task.result or not isinstance(task.result, dict):
        return []
    items = task.result.get("data") or []
    if not isinstance(items, list) or not items:
        return []
    pairs: List[str] = []
    for it in items[:top_n]:
        pair = it.get("name") or it.get("symbol")
        if isinstance(pair, str):
            # normalize BTCUSDT -> BTC/USDT when needed
            if pair.isupper() and pair.endswith("USDT") and "/" not in pair:
                pair = pair.replace("USDT", "/USDT")
            pairs.append(pair)
    # deduplicate while keeping order
    seen = set()
    uniq = []
    for p in pairs:
        if p not in seen:
            uniq.append(p)
            seen.add(p)
    return uniq


def generate_buy_sell_signals_from_latest(top_n: int = 5, current_open_positions: Optional[List[str]] = None) -> Dict[str, List[Dict[str, Any]]]:
    """Generate buy/sell signals from the latest analysis result.

    - Take top_n pairs as desired holdings (buy list).
    - If current_open_positions provided (e.g., from Freqtrade open_trades pairs),
      then sell any pair not in top list ("不相关的先卖掉"), and buy pairs in top list not currently held.
    - If not provided, we only output buy signals for top list.
    """
    task = get_last_completed_task()
    if not task:
        logger.warning("No completed analysis task found to generate signals")
        return {"buy": [], "sell": []}

    top_pairs = _extract_ranked_pairs_from_task(task, top_n=top_n)
    buy_signals: List[Dict[str, Any]] = []
    sell_signals: List[Dict[str, Any]] = []

    if current_open_positions is None:
        # only propose buys for top list
        buy_signals = [{"pair": p, "side": "buy"} for p in top_pairs]
        return {"buy": buy_signals, "sell": sell_signals}

    desired = set(top_pairs)
    held = set(current_open_positions)

    # sell anything not desired
    for p in sorted(held - desired):
        sell_signals.append({"pair": p, "side": "sell"})

    # buy anything desired but not currently held
    for p in sorted(desired - held):
        buy_signals.append({"pair": p, "side": "buy"})

    return {"buy": buy_signals, "sell": sell_signals}
