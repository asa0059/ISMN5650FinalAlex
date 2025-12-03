# business.py
from typing import Dict, Any, List, Tuple
from pathlib import Path
import json
import os
import requests

from ai import get_trade_recommendations

POSITIONS_FILE = Path(__file__).resolve().with_name("current_positions.json")
TRADES_FILE = Path(__file__).resolve().with_name("trading_history.json")

MOTHERSHIP_URL = os.getenv("MOTHERSHIP_URL", "https://mothership-crg7hzedd6ckfegv.eastus-01.azurewebsites.net")
TRADE_ENDPOINT = f"{MOTHERSHIP_URL}/make_trade"
TRADE_API_KEY = os.getenv("MOTHERSHIP_X_API_KEY", "SET_ME")  # generated from genkey site

def _read_json_list(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        return []
    except Exception:
        return []

def _write_json_list(path: Path, data: List[Dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def _build_positions_snapshot(positions: List[Dict[str, Any]], market_summary: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    price_by_ticker = {m["ticker"]: float(m["current_price"]) for m in market_summary}
    snapshot: List[Dict[str, Any]] = []
    for pos in positions:
        ticker = pos["ticker"]
        qty = int(pos["quantity"])
        purchase_price = float(pos["purchase_price"])
        current_price = price_by_ticker.get(ticker)
        snapshot.append(
            {
                "ticker": ticker,
                "quantity": qty,
                "purchase_price": purchase_price,
                "current_price": current_price,
            }
        )
    return snapshot

def _append_trade_log(trade_recs: List[Dict[str, Any]], rationale: str) -> None:
    """
    Append recommendations to trading_history.json (as the assignment asks to store AI recs).
    """
    history = _read_json_list(TRADES_FILE)
    entry = {
        "ai_recommendations": trade_recs,
        "rationale": rationale
    }
    history.append(entry)
    _write_json_list(TRADES_FILE, history)

def _post_trades_to_mothership(trade_id: str, trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    POST to /make_trade with x-api-key header.
    Returns parsed JSON.
    """
    headers = {
        "Content-Type": "application/json",
        "x-api-key": TRADE_API_KEY
    }
    payload = {
        "id": trade_id,
        "trades": trades
    }
    r = requests.post(TRADE_ENDPOINT, headers=headers, json=payload, timeout=20)
    try:
        data = r.json()
    except Exception:
        data = {"error": f"Non-JSON response from mothership (status {r.status_code})"}
    if r.status_code == 200:
        data["_http_status"] = 200
    else:
        data["_http_status"] = r.status_code
    return data

def analyze_tick(payload: Dict[str, Any], trade_id: str) -> Dict[str, Any]:
    """
    - Join data to compute unrealized P&L.
    - Build and write positions snapshot.
    - Ask AI for recommendations (tool/function format).
    - Store recommendations in trading_history.json.
    - POST recommendations to mothership /make_trade.
    - If 200, update local positions file from returned 'Positions'.
    """
    positions: List[Dict[str, Any]] = payload.get("Positions", [])
    market_summary: List[Dict[str, Any]] = payload.get("Market_Summary", [])

    price_by_ticker = {m["ticker"]: float(m["current_price"]) for m in market_summary}

    evaluated = 0
    total_unrealized = 0.0
    for pos in positions:
        ticker = pos["ticker"]
        qty = int(pos["quantity"])
        purchase_price = float(pos["purchase_price"])
        if ticker in price_by_ticker:
            current = price_by_ticker[ticker]
            pnl = (current - purchase_price) * qty
            total_unrealized += pnl
            evaluated += 1

    # Build snapshot with current prices and save
    snapshot = _build_positions_snapshot(positions, market_summary)
    _write_json_list(POSITIONS_FILE, snapshot)

    # --- AI step ---
    ai_out = get_trade_recommendations(payload)
    trades = ai_out.get("trades", [])
    rationale = ai_out.get("rationale", "")

    # Store the AI recommendations (not applying locally; mothership will apply)
    _append_trade_log(trades, rationale)

    # --- POST to mothership ---
    mothership_resp = _post_trades_to_mothership(trade_id, trades)

    # If successful, overwrite local positions with returned Positions (if present)
    if mothership_resp.get("_http_status") == 200 and "Positions" in mothership_resp:
        returned_positions = mothership_resp["Positions"]
        # try to reattach current_price using today's market_summary if tickers match
        price_by_ticker = {m["ticker"]: float(m["current_price"]) for m in market_summary}
        merged = []
        for p in returned_positions:
            cp = price_by_ticker.get(p["ticker"])
            merged.append({
                "ticker": p["ticker"],
                "quantity": int(p["quantity"]),
                "purchase_price": float(p["purchase_price"]),
                "current_price": cp
            })
        _write_json_list(POSITIONS_FILE, merged)

    result = {
        "summary": {
            "positions_evaluated": evaluated,
            "unrealized_pnl": round(total_unrealized, 4),
        },
        "decisions": trades,
        "mothership_response": {k: v for k, v in mothership_resp.items() if k != "_http_status"},
        "http_status_mothership": mothership_resp.get("_http_status"),
    }
    return result

def load_dashboard_data() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    positions = _read_json_list(POSITIONS_FILE)
    trades = _read_json_list(TRADES_FILE)
    return positions, trades
