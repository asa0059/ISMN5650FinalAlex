# app.py
from flask import Flask, request, jsonify, render_template
from config import API_KEY
from validators import validate_tick_payload
from business import analyze_tick, load_dashboard_data

# single app object, with templates folder
app = Flask(__name__, template_folder="templates")


# ---------- Helpers ----------

def unauthorized():
    return jsonify({"result": "failure", "message": "Unauthorized"}), 401


def require_apikey() -> bool:
    """Checks if request header 'apikey' matches the value in .env."""
    header_val = request.headers.get("apikey", "")
    # DEBUG: show what we got vs what we expect
    print(f"[auth] header apikey='{header_val}' | expected='{API_KEY}'")
    return header_val.strip() == API_KEY


# ---------- Routes ----------

@app.route("/", methods=["GET"])
def root():
    """Root endpoint — open to anyone."""
    return jsonify({"result": "success", "message": "Strategy API Server running."})


@app.route("/healthcheck", methods=["GET"])
def healthcheck():
    """
    Authenticated route for system health.
    Must still work exactly like Assignment 5.
    """
    if not require_apikey():
        return unauthorized()
    try:
        return jsonify({"result": "success", "message": "Ready to Trade"}), 200
    except Exception as e:
        # Keep the 200 status per original assignment expectations
        return jsonify({"result": "failure", "message": str(e)}), 200


@app.route("/tick/<string:trade_id>", methods=["POST"])
def tick(trade_id: str):
    """
    Authenticated POST route that:
      - Validates payload (with DAY now as 'yyyy-mm-dd' string inside market_history)
      - Calls business.analyze_tick(payload, trade_id)
      - Business layer logs AI recommendations, updates files,
        and posts to mothership /make_trade using the given trade_id.
    """
    if not require_apikey():
        return unauthorized()

    if not request.is_json:
        return jsonify({
            "result": "failure",
            "message": "Invalid payload: Content-Type must be application/json"
        }), 400

    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({
            "result": "failure",
            "message": "Invalid payload: malformed JSON"
        }), 400

    ok, msg = validate_tick_payload(payload)
    if not ok:
        return jsonify({"result": "failure", "message": msg}), 400

    try:
        result = analyze_tick(payload, trade_id)

        # Ensure minimum required structure
        result.setdefault("result", "success")
        result.setdefault("summary", {"positions_evaluated": 0, "unrealized_pnl": 0.0})
        result.setdefault("decisions", [])

        return jsonify(result), 200
    except Exception as e:
        return jsonify({
            "result": "failure",
            "message": f"Processing error: {e}"
        }), 500


@app.route("/dashboard", methods=["GET"])
def dashboard():
    """
    Public dashboard (NO API KEY REQUIRED).
    Uses Jinja template to display current positions and trading history.
    """
    positions, trades = load_dashboard_data()
    return render_template("dashboard.html", positions=positions, trades=trades)


# ---------- Error handlers ----------

@app.errorhandler(404)
def not_found(_):
    return jsonify({"result": "failure", "message": "Not Found"}), 404


@app.errorhandler(405)
def method_not_allowed(_):
    return jsonify({"result": "failure", "message": "Method Not Allowed"}), 405


@app.errorhandler(500)
def internal_error(_):
    # Let Flask's default logs capture the original exception; return generic JSON
    return jsonify({"result": "failure", "message": "Internal Server Error"}), 500


# ---------- Local run ----------

if __name__ == "__main__":
    # For local / container / Azure dev: listen on all interfaces, port 8000
    app.run(host="0.0.0.0", port=8000, debug=False)
