# validators.py
from typing import Dict, Any, Tuple


def validate_tick_payload(payload: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Basic structural validation for the /tick payload.

    Requirements (aligned with tester's make_payload()):
      - Top-level must be a dict
      - Required keys: 'Positions', 'Market_Summary', 'market_history'
      - Each of these must be a list
      - Minimal field checks on list items
      - 'market_history.day' must be a date string (YYYY-MM-DD),
        but we don't enforce exact format, just that it's a string.
    """
    if not isinstance(payload, dict):
        return False, "Payload must be a JSON object"

    required_lists = ["Positions", "Market_Summary", "market_history"]
    for key in required_lists:
        if key not in payload:
            return False, f"Missing required field: {key}"
        if not isinstance(payload[key], list):
            return False, f"{key} must be a list"

    # --- Positions checks ---
    for idx, pos in enumerate(payload["Positions"]):
        if not isinstance(pos, dict):
            return False, f"Positions[{idx}] must be an object"
        for field in ("ticker", "quantity", "purchase_price"):
            if field not in pos:
                return False, f"Positions[{idx}] missing '{field}'"

    # --- Market_Summary checks ---
    for idx, row in enumerate(payload["Market_Summary"]):
        if not isinstance(row, dict):
            return False, f"Market_Summary[{idx}] must be an object"
        for field in ("ticker", "current_price", "category"):
            if field not in row:
                return False, f"Market_Summary[{idx}] missing '{field}'"

    # --- market_history checks ---
    for idx, row in enumerate(payload["market_history"]):
        if not isinstance(row, dict):
            return False, f"market_history[{idx}] must be an object"
        for field in ("ticker", "price", "day"):
            if field not in row:
                return False, f"market_history[{idx}] missing '{field}'"
        # Tester uses 'day' as a string like '2025-04-03'
        if not isinstance(row["day"], str):
            return False, "market_history.day must be a date string"

    # If we get here, payload looks good
    return True, "OK"
