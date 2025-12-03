# ai.py
import os
import json
from typing import Dict, Any, List

from openai import OpenAI

def _fallback_trades(tick_payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Simple, safe fallback: STAY on all tickers.
    """
    trades = [
        {"action": "STAY", "ticker": p.get("ticker"), "quantity": 0}
        for p in tick_payload.get("Positions", [])
        if isinstance(p, dict) and "ticker" in p
    ]
    return {
        "trades": trades,
        "rationale": "Fallback: STAY on all positions because AI was unavailable."
    }


# ---- AI configuration ----

# Prefer standard name OPENAI_API_KEY, but also support CHATGPT_API_KEY just in case
API_KEY = os.getenv("OPENAI_API_KEY") or os.getenv("CHATGPT_API_KEY")
MODEL = os.getenv("OPENAI_MODEL", "gpt-5-nano")

SYSTEM_PROMPT = """
You are an AI trading assistant. You receive:
- The current portfolio positions
- Market prices and signals
- News or sentiment

Your job is to propose a *small number* of simple trades:
- BUY, SELL, or STAY
- A reasonable integer quantity
- Never trade symbols that are not in the incoming data.

Always return trades via the `propose_trades` tool only.
Keep the strategy conservative and explain your reasoning.
""".strip()

PROPOSE_TRADES_TOOL = {
    "type": "function",
    "function": {
        "name": "propose_trades",
        "description": "Propose trades for the next tick.",
        "parameters": {
            "type": "object",
            "properties": {
                "trades": {
                    "type": "array",
                    "description": "List of trades to execute.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["BUY", "SELL", "STAY"],
                                "description": "Type of trade"
                            },
                            "ticker": {
                                "type": "string",
                                "description": "Ticker symbol"
                            },
                            "quantity": {
                                "type": "integer",
                                "description": "Number of shares, 0 is allowed for STAY"
                            },
                        },
                        "required": ["action", "ticker", "quantity"],
                    },
                },
                "rationale": {
                    "type": "string",
                    "description": "Short explanation of the strategy."
                },
            },
            "required": ["trades", "rationale"],
        },
    },
}


def _build_user_message(tick_payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Turn the raw tick payload into a user message for the AI.
    """
    positions = tick_payload.get("Positions", [])
    prices = tick_payload.get("Prices", {})
    news = tick_payload.get("News", "")

    text = [
        "Here is the current tick data.",
        "",
        "Positions:",
    ]
    for p in positions:
        if isinstance(p, dict):
            text.append(f"- {p.get('ticker')}: {p.get('quantity')} shares")

    text.append("")
    text.append("Prices:")
    if isinstance(prices, dict):
        for ticker, price in prices.items():
            text.append(f"- {ticker}: {price}")

    if news:
        text.append("")
        text.append("News / Sentiment:")
        text.append(str(news))

    text.append("")
    text.append("Please propose a small set of trades using the tool.")

    return {"role": "user", "content": "\n".join(text)}


def get_trade_recommendations(tick_payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main entry point used by your Flask endpoint.
    Returns a dict:
    {
        "trades": [ { "action": "...", "ticker": "...", "quantity": ... }, ... ],
        "rationale": "..."
    }
    """
    # If no API key, immediately fall back
    if not API_KEY:
        return _fallback_trades(tick_payload)

    try:
        client = OpenAI(api_key=API_KEY)
    except Exception:
        # Could not create client
        return _fallback_trades(tick_payload)

    user_msg = _build_user_message(tick_payload)

    try:
        resp = client.responses.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                user_msg,
            ],
            tools=[PROPOSE_TRADES_TOOL],
            tool_choice="auto",
            temperature=0.2,
        )

        # Expect a tool call in the first output
        output_item = resp.output[0]
        content_item = output_item.content[0]

        tool_calls: List[Any] = getattr(content_item, "tool_calls", []) or []
        if not tool_calls:
            # No tool call -> fall back
            return _fallback_trades(tick_payload)

        tool_call = tool_calls[0]
        # The `arguments` field is a JSON string according to the responses API
        args_json = tool_call.arguments
        tool_args = json.loads(args_json)

        trades = tool_args.get("trades", [])
        rationale = tool_args.get("rationale", "No rationale provided.")

        # Basic sanity check: must be a list
        if not isinstance(trades, list):
            return _fallback_trades(tick_payload)

        return {
            "trades": trades,
            "rationale": rationale,
        }

    except Exception:
        # Any error during the AI call → safe fallback
        return _fallback_trades(tick_payload)
