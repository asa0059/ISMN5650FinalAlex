"""
Tester for Strategy AI Agent — Part 1 (API Server)
Validates:
- Auth (header 'apikey')
- /healthcheck behavior
- /tick validation & happy path (now requires path param)
- /dashboard renders HTML without auth
"""

import uuid
import requests
from math import isclose

BASE_URL = "http://127.0.0.1:5000"
API_KEY = "dc4cd7e3db66f093c6d2e95c0423071404b3052c169e38ddfddd5b0d10406251"
TIMEOUT = 6

# Unique id required by /tick/<id>
TEST_RUN_ID = uuid.uuid4().hex[:12]
TICK_URL = f"{BASE_URL}/tick/{TEST_RUN_ID}"

def h(ok): return "✅ PASS" if ok else "❌ FAIL"

def j(resp):
    try: return resp.json()
    except Exception: return None

def headers(ok=True):
    return {"apikey": API_KEY if ok else "WRONG_KEY"}

def test_health_auth():
    # Without key -> should be 401
    r1 = requests.get(f"{BASE_URL}/healthcheck", headers=headers(False), timeout=TIMEOUT)
    body1 = j(r1)
    ok1 = (r1.status_code == 401 and isinstance(body1, dict) and body1.get("result") == "failure")

    # With correct key -> should be 200 success
    r2 = requests.get(f"{BASE_URL}/healthcheck", headers=headers(), timeout=TIMEOUT)
    body2 = j(r2)
    ok2 = (r2.status_code == 200 and isinstance(body2, dict) and body2.get("result") == "success")

    print("/healthcheck requires and validates API key:", h(ok1 and ok2))

def test_tick_auth_required():
    # No path parameter -> should error (e.g., 404 or 400), and we also use a bad key to ensure auth would fail regardless
    r = requests.post(f"{BASE_URL}/tick", json={}, headers=headers(False), timeout=TIMEOUT)
    body = j(r)
    ok_error_code = r.status_code in (400, 404, 405)  # frameworks often return 404 for missing path param
    ok = ok_error_code or (isinstance(body, dict) and body.get("result") == "failure")
    print("Auth required on /tick and path param enforced:", h(ok))

def test_tick_validation_errors():
    # Not JSON
    r1 = requests.post(TICK_URL, data="nope", headers=headers(), timeout=TIMEOUT)
    # Missing keys
    r2 = requests.post(TICK_URL, json={"Positions": []}, headers=headers(), timeout=TIMEOUT)
    ok = (r1.status_code == 400 or r1.status_code == 401) and (r2.status_code == 400)
    print("/tick validation errors handled:", h(ok))

def make_payload():
    # Note: 'Day' field is now a YYYY-MM-DD string (capital D), not an integer.
    return {'Positions': [{'ticker': 'AUTX', 'quantity': 15.0, 'purchase_price': 141.71}, 
                          {'ticker': 'CASH', 'quantity': 962.09, 'purchase_price': 1.0}, 
                          {'ticker': 'EVGO', 'quantity': 10.0, 'purchase_price': 177.67}, 
                          {'ticker': 'HOMR', 'quantity': 1.0, 'purchase_price': 78.42}, 
                          {'ticker': 'MEDC', 'quantity': 1.0, 'purchase_price': 57.14}], 
        'Market_Summary': [{'ticker': 'HOMR', 'current_price': 78.42, 'category': 'low'}, 
                           {'ticker': 'SNAC', 'current_price': 73.08, 'category': 'low'}, 
                           {'ticker': 'MEDC', 'current_price': 57.14, 'category': 'low'}, 
                           {'ticker': 'AUTX', 'current_price': 141.71, 'category': 'medium'}, 
                           {'ticker': 'TECH', 'current_price': 145.51, 'category': 'medium'}, 
                           {'ticker': 'RETL', 'current_price': 119.83, 'category': 'medium'}, 
                           {'ticker': 'SPCX', 'current_price': 219.07, 'category': 'high'}, 
                           {'ticker': 'CRYP', 'current_price': 199.34, 'category': 'high'}, 
                           {'ticker': 'EVGO', 'current_price': 177.67, 'category': 'high'}], 
        'market_history': [{'ticker': 'HOMR', 'price': 78.3, 'day': '2025-04-02'}, 
                           {'ticker': 'HOMR', 'price': 78.42, 'day': '2025-04-03'}, 
                           {'ticker': 'SNAC', 'price': 73.21, 'day': '2025-04-02'}, 
                           {'ticker': 'SNAC', 'price': 73.08, 'day': '2025-04-03'}, 
                           {'ticker': 'MEDC', 'price': 57.35, 'day': '2025-04-02'}, 
                           {'ticker': 'MEDC', 'price': 57.14, 'day': '2025-04-03'}, 
                           {'ticker': 'AUTX', 'price': 140.97, 'day': '2025-04-02'}, 
                           {'ticker': 'AUTX', 'price': 141.71, 'day': '2025-04-03'}, 
                           {'ticker': 'TECH', 'price': 146.58, 'day': '2025-04-02'}, 
                           {'ticker': 'TECH', 'price': 145.51, 'day': '2025-04-03'}, 
                           {'ticker': 'RETL', 'price': 119.52, 'day': '2025-04-02'}, 
                           {'ticker': 'RETL', 'price': 119.83, 'day': '2025-04-03'}, 
                           {'ticker': 'SPCX', 'price': 217.89, 'day': '2025-04-02'}, 
                           {'ticker': 'SPCX', 'price': 219.07, 'day': '2025-04-03'}, 
                           {'ticker': 'CRYP', 'price': 197.92, 'day': '2025-04-02'}, 
                           {'ticker': 'CRYP', 'price': 199.34, 'day': '2025-04-03'}, 
                           {'ticker': 'EVGO', 'price': 174.95, 'day': '2025-04-02'}, 
                           {'ticker': 'EVGO', 'price': 177.67, 'day': '2025-04-03'}]}

def expected_pnl(payload):
    curr = {r["ticker"]: float(r["current_price"]) for r in payload["Market_Summary"]}
    pnl = 0.0
    for p in payload["Positions"]:
        t = p["ticker"]; q = float(p["quantity"]); cost = float(p["purchase_price"])
        if t in curr:
            pnl += (curr[t] - cost) * q
    return pnl

def test_tick_success():
    payload = make_payload()
    print("/tick succss test called...This test could take several seconds.  Please wait...")
    r = requests.post(TICK_URL, json=payload, headers=headers())
    body = j(r)
    if r.status_code != 200 or not isinstance(body, dict):
        print("/tick success:", h(False))
        print(r.json())
        return

    # Check structure
    has_fields = body.get("result") == "success" and "summary" in body and "decisions" in body
    if not has_fields:
        print("/tick success (shape):", h(False)); return

    # Check P&L approximately
    got = float(body["summary"].get("unrealized_pnl", 999999))
    exp = expected_pnl(payload)
    ok = isclose(got, exp, rel_tol=1e-9, abs_tol=1e-9)
    print("/tick success (math):", h(ok))

def test_dashboard_public_html():
    # No headers: page should render without auth
    r = requests.get(f"{BASE_URL}/dashboard", timeout=TIMEOUT)
    content_type = r.headers.get("Content-Type", "").lower()
    looks_html = "text/html" in content_type or ("<html" in r.text.lower() if hasattr(r, "text") else False)
    ok = (r.status_code == 200) and looks_html
    print("/dashboard is public and renders HTML:", h(ok))

def main():
    print("== Strategy AI Agent — Part 3 Tester ==")
    if API_KEY == "SET TO YOUR KEY FROM THE GEN_KEY SITE":
        print("WARNING: Set API_KEY TO YOUR KEY FROM THE GEN_KEY SITE.\n")

    # ping server root (optional)
    try:
        requests.get(f"{BASE_URL}/", timeout=TIMEOUT)
    except Exception as e:
        print(f"Could not reach server at {BASE_URL}. Is it running?\nDetails: {e}")
        return

    test_health_auth()
    test_dashboard_public_html()
    test_tick_auth_required()
    test_tick_validation_errors()
    test_tick_success()
    print("\nDone.")

if __name__ == "__main__":
    main()
