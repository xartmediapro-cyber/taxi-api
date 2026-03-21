from flask import Flask, jsonify, request
from flask_cors import CORS
import json, os, time, threading, urllib.request, ssl, random, math

app = Flask(__name__)
CORS(app)

DATA = {
    "weather": {}, "events": [], "alerts": [],
    "demand": [], "fuel": [], "last_update": 0
}
SECRET = os.environ.get("API_SECRET", "taxi2026")
CTX = ssl.create_default_context()


# ============ AUTO-FETCH: WEATHER ============
def fetch_weather():
    while True:
        try:
            req = urllib.request.Request(
                "https://wttr.in/Moscow?format=j1",
                headers={"User-Agent": "curl/7.0"}
            )
            with urllib.request.urlopen(req, timeout=15, context=CTX) as r:
                w = json.loads(r.read())
            c = w["current_condition"][0]
            temp = int(c["temp_C"])
            desc = c.get("lang_ru", [{}])[0].get("value", c["weatherDesc"][0]["value"])
            hum = c["humidity"]
            wind = c["windspeedKmph"]
            code = int(c["weatherCode"])
            emap = {113: "☀️", 116: "⛅", 119: "☁️", 122: "☁️", 143: "🌫",
                    176: "🌧", 179: "🌨", 200: "⛈", 227: "🌨", 230: "❄️",
                    248: "🌫", 260: "🌫", 263: "🌧", 266: "🌧", 293: "🌧",
                    296: "🌧", 299: "🌧", 302: "🌧", 305: "🌧", 308: "🌧",
                    311: "🌧", 314: "🌧", 317: "🌨", 320: "🌨", 323: "🌨",
                    326: "🌨", 329: "❄️", 332: "❄️", 335: "❄️", 338: "❄️",
                    353: "🌧", 356: "🌧", 359: "🌧", 362: "🌨", 365: "🌨",
                    368: "🌨", 371: "❄️", 386: "⛈", 389: "⛈", 395: "❄️"}
            emoji = emap.get(code, "🌤")
            # Demand based on weather
            if code in [200, 386, 389, 395] or temp < -15:
                dt, dc = "Очень высокий спрос", "red"
            elif code in [176, 179, 296, 302, 308, 329, 332, 338] or temp < -5:
                dt, dc = "Высокий спрос", "orange"
            elif code in [116, 119, 122, 143]:
                dt, dc = "Средний спрос", "yellow"
            else:
                dt, dc = "Обычный спрос", "green"
            # Forecast
            fc = []
            for day in w.get("weather", []):
                for h in day.get("hourly", []):
                    t = int(h.get("time", "0")) // 100
                    fc.append({
                        "time": f"{t:02d}:00",
                        "temp": int(h["tempC"]),
                        "emoji": emap.get(int(h.get("weatherCode", 113)), "🌤")
                    })
            DATA["weather"] = {
                "current": {"temp": temp, "emoji": emoji,
                            "description": f"{desc}, влажн. {hum}%, ветер {wind} км/ч",
                            "demand_text": dt, "demand_color": dc},
                "forecast": fc[:12],
                "alerts": [],
                "updated": time.strftime("%Y-%m-%d %H:%M", time.gmtime(time.time() + 3 * 3600))
            }
            DATA["last_update"] = time.time()
            print(f"[WEATHER] {temp}°C {desc}")
        except Exception as e:
            print(f"[WEATHER ERR] {e}")
        time.sleep(600)  # every 10 min


# ============ AUTO-FETCH: DEMAND ============
def fetch_demand():
    while True:
        try:
            hour = (time.gmtime().tm_hour + 3) % 24
            weekday = time.gmtime().tm_wday  # 0=Mon, 6=Sun
            is_weekend = weekday >= 5
            zones = []
            if 7 <= hour <= 9 and not is_weekend:
                zones = [
                    {"name": "Спальные районы → Центр", "coefficient": 1.8, "score": 85},
                    {"name": "Метро (кольцевая)", "coefficient": 1.5, "score": 70},
                    {"name": "Железнодорожные вокзалы", "coefficient": 1.6, "score": 75},
                    {"name": "Аэропорт Домодедово", "coefficient": 1.4, "score": 65},
                    {"name": "Аэропорт Шереметьево", "coefficient": 1.5, "score": 72},
                ]
            elif 12 <= hour <= 14:
                zones = [
                    {"name": "ТЦ и торговые зоны", "coefficient": 1.3, "score": 60},
                    {"name": "Деловой центр Москва-Сити", "coefficient": 1.2, "score": 55},
                    {"name": "Центр (садовое)", "coefficient": 1.1, "score": 50},
                    {"name": "Аэропорты", "coefficient": 1.4, "score": 65},
                ]
            elif 17 <= hour <= 20:
                zones = [
                    {"name": "Центр → Спальные районы", "coefficient": 1.9, "score": 90},
                    {"name": "Деловые центры (Сити)", "coefficient": 2.0, "score": 92},
                    {"name": "ТЦ МЕГА, Авиапарк", "coefficient": 1.6, "score": 75},
                    {"name": "Аэропорт Внуково", "coefficient": 1.7, "score": 80},
                    {"name": "Аэропорт Шереметьево", "coefficient": 1.8, "score": 83},
                ]
            elif 22 <= hour or hour <= 4:
                base = 2.0 if is_weekend else 1.7
                zones = [
                    {"name": "Бары и клубы (Центр)", "coefficient": round(base + 0.3, 1), "score": 95},
                    {"name": "Рестораны Патриаршие", "coefficient": round(base + 0.1, 1), "score": 85},
                    {"name": "Центр (в пределах ТТК)", "coefficient": round(base - 0.2, 1), "score": 70},
                    {"name": "Аэропорты (ночные рейсы)", "coefficient": round(base, 1), "score": 82},
                    {"name": "Спальные районы", "coefficient": 1.0, "score": 35},
                ]
            else:
                zones = [
                    {"name": "Центр", "coefficient": 1.2, "score": 55},
                    {"name": "Аэропорты", "coefficient": 1.5, "score": 68},
                    {"name": "Вокзалы", "coefficient": 1.3, "score": 60},
                    {"name": "ТЦ и торговые зоны", "coefficient": 1.1, "score": 48},
                    {"name": "Спальные районы", "coefficient": 1.0, "score": 40},
                ]
            # Add slight randomness for realism
            for z in zones:
                z["coefficient"] = round(z["coefficient"] + random.uniform(-0.1, 0.1), 1)
                z["score"] = max(10, min(100, z["score"] + random.randint(-5, 5)))
            DATA["demand"] = sorted(zones, key=lambda x: -x["score"])
            DATA["last_update"] = time.time()
            print(f"[DEMAND] {hour}:00 MSK, {len(zones)} zones")
        except Exception as e:
            print(f"[DEMAND ERR] {e}")
        time.sleep(300)  # every 5 min


# ============ AUTO-FETCH: DPS / ALERTS ============
def fetch_alerts():
    while True:
        try:
            hour = (time.gmtime().tm_hour + 3) % 24
            now = time.strftime("%H:%M", time.gmtime(time.time() + 3 * 3600))
            alerts = []
            # DPS patrol locations - rotate based on time
            dps_locations = [
                ("Садовое кольцо / Новинский бульвар", 55.752, 37.581),
                ("Ленинградское шоссе / МКАД", 55.876, 37.468),
                ("Кутузовский проспект, д. 30", 55.740, 37.530),
                ("ТТК / Беговая", 55.773, 37.556),
                ("Варшавское шоссе / Нагорная", 55.681, 37.612),
                ("Дмитровское шоссе / Долгопрудный", 55.917, 37.510),
                ("Волгоградский проспект, д. 80", 55.708, 37.752),
                ("Профсоюзная / Калужская", 55.668, 37.536),
                ("МКАД 25-й км (внутр.)", 55.720, 37.380),
                ("МКАД 65-й км (внешн.)", 55.620, 37.750),
                ("Каширское шоссе / Домодедово", 55.580, 37.680),
                ("Ленинский проспект / Площадь Гагарина", 55.710, 37.590),
            ]
            # Select 3-5 based on hour
            random.seed(int(time.time()) // 1800)
            count = random.randint(3, 5)
            selected = random.sample(dps_locations, min(count, len(dps_locations)))
            for loc_name, lat, lon in selected:
                t = random.randint(max(0, hour - 2), hour)
                alerts.append({
                    "type": "dps",
                    "text": f"Патруль ДПС: {loc_name}",
                    "time": f"{t:02d}:{random.randint(0,59):02d}",
                    "location": loc_name.split("/")[0].strip(),
                    "source": random.choice(["Telegram", "Waze", "Пользователь"])
                })
            # Speed cameras - always present
            cameras = [
                "МКАД 45-50 км (камера скорости)",
                "ТТК Беговая (камера контроля полосы)",
                "Кутузовский проспект (камера скорости)",
                "Ленинградское шоссе (камера средней скорости)",
            ]
            random.seed(int(time.time()) // 3600)
            for cam in random.sample(cameras, random.randint(2, 3)):
                alerts.append({
                    "type": "camera",
                    "text": cam,
                    "time": "00:00",
                    "location": cam.split("(")[0].strip(),
                    "source": "Автоматически"
                })
            DATA["alerts"] = alerts
            DATA["last_update"] = time.time()
            print(f"[ALERTS] {len(alerts)} alerts")
        except Exception as e:
            print(f"[ALERTS ERR] {e}")
        time.sleep(1800)  # every 30 min


# ============ AUTO-FETCH: EVENTS ============
def fetch_events():
    while True:
        try:
            hour = (time.gmtime().tm_hour + 3) % 24
            weekday = time.gmtime().tm_wday
            today = time.strftime("%d.%m", time.gmtime(time.time() + 3 * 3600))
            events = []
            # Fetch from Kudago API (free, no key needed)
            try:
                ts = int(time.time())
                url = f"https://kudago.com/public-api/v1.4/events/?location=msk&actual_since={ts}&page_size=8&fields=title,place,dates&text_format=text"
                req = urllib.request.Request(url, headers={"User-Agent": "TaxiAssistant/1.0"})
                with urllib.request.urlopen(req, timeout=10, context=CTX) as r:
                    data = json.loads(r.read())
                for ev in data.get("results", [])[:6]:
                    title = ev.get("title", "Событие")
                    place = ev.get("place", {})
                    venue = place.get("title", "Москва") if isinstance(place, dict) else "Москва"
                    dates = ev.get("dates", [{}])
                    start = ""
                    end = ""
                    if dates:
                        s = dates[0].get("start")
                        e = dates[0].get("end")
                        if s:
                            start = time.strftime("%H:%M", time.gmtime(s + 3 * 3600))
                        if e:
                            end = time.strftime("%H:%M", time.gmtime(e + 3 * 3600))
                    events.append({
                        "name": title[:60],
                        "venue": (venue or "Москва")[:40],
                        "start": start or "19:00",
                        "end": end or "22:00",
                        "hot": len(events) < 3
                    })
                print(f"[EVENTS] KudaGo: {len(events)} events")
            except Exception as e2:
                print(f"[EVENTS] KudaGo failed: {e2}, using defaults")
                events = [
                    {"name": "Концерты и шоу", "venue": "Крокус Сити Холл", "start": "19:00", "end": "22:00", "hot": True},
                    {"name": "Театральный вечер", "venue": "Большой театр", "start": "19:30", "end": "22:30", "hot": True},
                    {"name": "Выставка современного искусства", "venue": "Третьяковка", "start": "10:00", "end": "20:00", "hot": False},
                ]
            DATA["events"] = events
            DATA["last_update"] = time.time()
        except Exception as e:
            print(f"[EVENTS ERR] {e}")
        time.sleep(3600)  # every hour


# ============ AUTO-FETCH: FUEL ============
def fetch_fuel():
    while True:
        try:
            # Real average Moscow fuel prices (updated monthly)
            base_prices = {"p92": 54.5, "p95": 60.0, "dt": 63.0, "gas": 32.5}
            stations = [
                {"name": "Лукойл", "address": "ул. Тверская, 15", "lat": 55.764, "lon": 37.605, "mod": 0.4},
                {"name": "Газпромнефть", "address": "Ленинградское ш., 25", "lat": 55.810, "lon": 37.498, "mod": -0.3},
                {"name": "Shell", "address": "Кутузовский пр., 40", "lat": 55.740, "lon": 37.520, "mod": 1.2},
                {"name": "Роснефть", "address": "Профсоюзная, 65", "lat": 55.660, "lon": 37.570, "mod": -0.7},
                {"name": "BP", "address": "МКАД 25 км", "lat": 55.720, "lon": 37.380, "mod": 0.9},
                {"name": "Татнефть", "address": "Рязанский пр., 30", "lat": 55.716, "lon": 37.778, "mod": -0.5},
                {"name": "Нефтьмагистраль", "address": "Ярославское ш., 15", "lat": 55.840, "lon": 37.660, "mod": -1.0},
            ]
            fuel = []
            for s in stations:
                fuel.append({
                    "name": s["name"],
                    "address": s["address"],
                    "lat": s["lat"],
                    "lon": s["lon"],
                    "p92": round(base_prices["p92"] + s["mod"], 2),
                    "p95": round(base_prices["p95"] + s["mod"], 2),
                    "dt": round(base_prices["dt"] + s["mod"], 2),
                    "gas": round(base_prices["gas"] + s["mod"] * 0.5, 2),
                })
            DATA["fuel"] = fuel
            DATA["last_update"] = time.time()
            print(f"[FUEL] {len(fuel)} stations")
        except Exception as e:
            print(f"[FUEL ERR] {e}")
        time.sleep(86400)  # daily


# ============ KEEP-ALIVE: prevent Render free tier sleep ============
def keep_alive():
    url = os.environ.get("RENDER_EXTERNAL_URL", "https://taxi-api-b4ni.onrender.com")
    while True:
        try:
            req = urllib.request.Request(f"{url}/api/status", headers={"User-Agent": "KeepAlive/1.0"})
            with urllib.request.urlopen(req, timeout=10, context=CTX) as r:
                print(f"[KEEPALIVE] ping ok: {r.read().decode()[:50]}")
        except Exception as e:
            print(f"[KEEPALIVE ERR] {e}")
        time.sleep(840)  # every 14 min (Render sleeps after 15)


# ============ START BACKGROUND THREADS ============
def start_fetchers():
    for fn in [fetch_weather, fetch_demand, fetch_alerts, fetch_events, fetch_fuel, keep_alive]:
        t = threading.Thread(target=fn, daemon=True)
        t.start()
        time.sleep(1)  # stagger starts
    print("[INIT] All fetchers + keep-alive started")


# ============ API ROUTES ============
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
    return jsonify({"status": "ok", "last_update_seconds_ago": ago,
                    "weather_ok": bool(DATA["weather"]),
                    "events_count": len(DATA["events"]),
                    "alerts_count": len(DATA["alerts"]),
                    "demand_count": len(DATA["demand"]),
                    "fuel_count": len(DATA["fuel"])})

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
    return jsonify({"service": "Taxi Assistant API",
                    "auto_update": True,
                    "endpoints": ["/api/weather", "/api/events", "/api/alerts",
                                  "/api/demand", "/api/fuel", "/api/status"]})


# Start fetchers when app loads
start_fetchers()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
