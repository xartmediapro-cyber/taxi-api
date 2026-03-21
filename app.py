from flask import Flask, jsonify, request
from flask_cors import CORS
import json, os, time

app = Flask(__name__)
CORS(app)

DATA = {
    "weather": {"current": {"temp": 0, "emoji": "sun", "description": "Loading...", "demand_text": "Loading...", "demand_color": "green"}, "forecast": [], "alerts": [], "updated": "-"},
    "events": [{"name": "Loading...", "venue": "-", "start": "-", "end": "-", "hot": False}],
    "alerts": [{"type": "dps", "text": "Loading...", "time": "-", "location": "Moscow", "source": "System"}],
    "demand": [{"name": "Loading...", "coefficient": 1.0, "score": 50}],
    "fuel": [{"name": "Loading...", "address": "-", "lat": 55.75, "lon": 37.61, "p92": 0, "p95": 0, "dt": 0, "gas": 0}],
    "last_update": 0
}

SECRET = os.environ.get("API_SECRET", "taxi2026")


@app.route("/api/weather", methods=["GET"])
def get_weather():
    return jsonify(DATA["weather"])


@app.route("/api/events", methods=["GET"])
def get_events():
    return jsonify(DATA["events"])


@app.route("/api/alerts", methods=["GET"])
def get_alerts():
    return jsonify(DATA["alerts"])


@app.route("/api/demand", methods=["GET"])
def get_demand():
    return jsonify(DATA["demand"])


@app.route("/api/fuel", methods=["GET"])
def get_fuel():
    return jsonify(DATA["fuel"])


@app.route("/api/status", methods=["GET"])
def get_status():
    ago = int(time.time() - DATA["last_update"]) if DATA["last_update"] else -1
    return jsonify({"status": "ok", "last_update_seconds_ago": ago})


@app.route("/api/push", methods=["POST"])
def push_data():
    auth = request.headers.get("X-API-Secret", "")
    if auth != SECRET:
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "no json"}), 400
    for key in ["weather", "events", "alerts", "demand", "fuel"]:
        if key in data:
            DATA[key] = data[key]
    DATA["last_update"] = time.time()
    return jsonify({"status": "updated", "keys": list(data.keys())}), 200


@app.route("/", methods=["GET"])
def index():
    return jsonify({"service": "Taxi Assistant API", "endpoints": ["/api/weather", "/api/events", "/api/alerts", "/api/demand", "/api/fuel", "/api/status"]})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
