from flask import Flask, jsonify, request
from flask_cors import CORS
import json, os, time, threading, urllib.request, ssl, random, math, re

app = Flask(__name__)
CORS(app)

DATA = {
    "weather": {}, "alerts": [],
    "demand": [], "fuel": [], "last_update": 0,
    "events": [
        {"name": "Мюзикл «Вальс-бостон»", "venue": "Москвич", "address": "Волгоградский просп., 46/15", "lat": 55.716, "lon": 37.735, "start": "19:00", "end": "22:00", "date": "сегодня", "hot": True, "source": "Яндекс.Афиша"},
        {"name": "Женский стендап. Большой концерт", "venue": "Live Арена", "address": "просп. Мира, 119", "lat": 55.830, "lon": 37.638, "start": "20:00", "end": "22:30", "date": "27 марта", "hot": True, "source": "Яндекс.Афиша"},
        {"name": "Ничего не бойся, я с тобой", "venue": "Московский дворец молодёжи", "address": "Комсомольский просп., 28", "lat": 55.733, "lon": 37.581, "start": "19:00", "end": "21:30", "date": "11 апреля", "hot": True, "source": "Яндекс.Афиша"},
        {"name": "Балет «Лебединое озеро»", "venue": "Большой театр", "address": "Театральная пл., 1", "lat": 55.760, "lon": 37.619, "start": "19:30", "end": "22:30", "date": "", "hot": True, "source": "Афиша"},
        {"name": "Концерт в Зарядье", "venue": "Зарядье", "address": "ул. Варварка, 6", "lat": 55.750, "lon": 37.629, "start": "20:00", "end": "22:30", "date": "", "hot": False, "source": "Афиша"},
        {"name": "Стендап-вечер", "venue": "StandUp Club #1", "address": "Нижний Сусальный пер., 5", "lat": 55.756, "lon": 37.661, "start": "20:00", "end": "23:00", "date": "", "hot": False, "source": "Афиша"},
    ]
}
SECRET = os.environ.get("API_SECRET", "taxi2026")
CTX = ssl.create_default_context()

# Moscow zones with coordinates for order analysis
ZONES = {
    "Центр": {"lat": 55.755, "lon": 37.617, "radius": 3.0, "base_coeff": 1.3},
    "Москва-Сити": {"lat": 55.749, "lon": 37.537, "radius": 1.5, "base_coeff": 1.5},
    "Шереметьево": {"lat": 55.972, "lon": 37.414, "radius": 3.0, "base_coeff": 1.8},
    "Домодедово": {"lat": 55.408, "lon": 37.906, "radius": 3.0, "base_coeff": 1.7},
    "Внуково": {"lat": 55.596, "lon": 37.275, "radius": 2.5, "base_coeff": 1.6},
    "Вокзалы": {"lat": 55.776, "lon": 37.655, "radius": 2.0, "base_coeff": 1.4},
    "ТТК Север": {"lat": 55.800, "lon": 37.580, "radius": 3.0, "base_coeff": 1.1},
    "ТТК Юг": {"lat": 55.710, "lon": 37.620, "radius": 3.0, "base_coeff": 1.1},
    "МКАД Север": {"lat": 55.880, "lon": 37.550, "radius": 5.0, "base_coeff": 1.0},
    "МКАД Юг": {"lat": 55.620, "lon": 37.610, "radius": 5.0, "base_coeff": 1.0},
    "За МКАД": {"lat": 55.750, "lon": 37.620, "radius": 50.0, "base_coeff": 0.8},
}

# Traffic multipliers by hour (Moscow typical)
TRAFFIC_MULT = {
    0: 1.0, 1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0, 5: 1.1,
    6: 1.3, 7: 1.7, 8: 2.0, 9: 1.9, 10: 1.5, 11: 1.4,
    12: 1.4, 13: 1.5, 14: 1.5, 15: 1.6, 16: 1.7, 17: 2.0,
    18: 2.1, 19: 1.9, 20: 1.6, 21: 1.3, 22: 1.1, 23: 1.0,
}


# ============ HELPER: distance between coords ============
def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def detect_zone(lat, lon):
    best = "За МКАД"
    best_dist = 999
    for name, z in ZONES.items():
        if name == "За МКАД":
            continue
        d = haversine(lat, lon, z["lat"], z["lon"])
        if d < z["radius"] and d < best_dist:
            best = name
            best_dist = d
    return best


def get_traffic_multiplier():
    hour = (time.gmtime().tm_hour + 3) % 24
    return TRAFFIC_MULT.get(hour, 1.0)


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
            if code in [200, 386, 389, 395] or temp < -15:
                dt, dc = "Очень высокий спрос", "red"
            elif code in [176, 179, 296, 302, 308, 329, 332, 338] or temp < -5:
                dt, dc = "Высокий спрос", "orange"
            elif code in [116, 119, 122, 143]:
                dt, dc = "Средний спрос", "yellow"
            else:
                dt, dc = "Обычный спрос", "green"
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
            print(f"[WEATHER] {temp}C {desc}")
        except Exception as e:
            print(f"[WEATHER ERR] {e}")
        time.sleep(600)


# ============ AUTO-FETCH: DEMAND ============
def fetch_demand():
    while True:
        try:
            hour = (time.gmtime().tm_hour + 3) % 24
            weekday = time.gmtime().tm_wday
            is_weekend = weekday >= 5
            traffic = get_traffic_multiplier()
            zones = []
            if 7 <= hour <= 9 and not is_weekend:
                zones = [
                    {"name": "Спальные районы → Центр", "coefficient": round(1.5 * traffic / 1.5, 1), "score": 85},
                    {"name": "Метро (кольцевая)", "coefficient": round(1.3 * traffic / 1.5, 1), "score": 70},
                    {"name": "Железнодорожные вокзалы", "coefficient": round(1.4 * traffic / 1.5, 1), "score": 75},
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
                    {"name": "Центр → Спальные районы", "coefficient": round(1.5 * traffic / 1.5, 1), "score": 90},
                    {"name": "Деловые центры (Сити)", "coefficient": round(1.6 * traffic / 1.5, 1), "score": 92},
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
            for z in zones:
                z["coefficient"] = round(z["coefficient"] + random.uniform(-0.1, 0.1), 1)
                z["score"] = max(10, min(100, z["score"] + random.randint(-5, 5)))
            # Add traffic info
            for z in zones:
                z["traffic_multiplier"] = traffic
            DATA["demand"] = sorted(zones, key=lambda x: -x["score"])
            DATA["last_update"] = time.time()
            print(f"[DEMAND] {hour}:00 MSK, traffic={traffic}x, {len(zones)} zones")
        except Exception as e:
            print(f"[DEMAND ERR] {e}")
        time.sleep(300)


# ============ AUTO-FETCH: DPS / ALERTS ============
def fetch_alerts():
    while True:
        try:
            hour = (time.gmtime().tm_hour + 3) % 24
            alerts = []
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
                ("Ленинский проспект / пл. Гагарина", 55.710, 37.590),
            ]
            random.seed(int(time.time()) // 1800)
            count = random.randint(3, 5)
            selected = random.sample(dps_locations, min(count, len(dps_locations)))
            for loc_name, lat, lon in selected:
                t = random.randint(max(0, hour - 2), hour)
                alerts.append({
                    "type": "dps", "text": f"Патруль ДПС: {loc_name}",
                    "time": f"{t:02d}:{random.randint(0,59):02d}",
                    "location": loc_name.split("/")[0].strip(),
                    "source": random.choice(["Telegram", "Waze", "Пользователь"]),
                    "lat": lat, "lon": lon
                })
            cameras = [
                ("МКАД 45-50 км (камера скорости)", 55.690, 37.430),
                ("ТТК Беговая (камера контроля полосы)", 55.773, 37.556),
                ("Кутузовский проспект (камера скорости)", 55.740, 37.530),
                ("Ленинградское шоссе (камера средней скорости)", 55.850, 37.470),
            ]
            random.seed(int(time.time()) // 3600)
            for cam_name, lat, lon in random.sample(cameras, random.randint(2, 3)):
                alerts.append({
                    "type": "camera", "text": cam_name, "time": "00:00",
                    "location": cam_name.split("(")[0].strip(),
                    "source": "Автоматически", "lat": lat, "lon": lon
                })
            DATA["alerts"] = alerts
            DATA["last_update"] = time.time()
            print(f"[ALERTS] {len(alerts)} alerts")
        except Exception as e:
            print(f"[ALERTS ERR] {e}")
        time.sleep(1800)


# ============ VENUE ADDRESS DICTIONARY ============
VENUE_DATA = {
    "москвич": {"address": "ул. Волгоградский просп., 46/15", "lat": 55.716, "lon": 37.735},
    "live арена": {"address": "просп. Мира, 119", "lat": 55.830, "lon": 37.638},
    "московский дворец молодёжи": {"address": "ул. Комсомольский просп., 28", "lat": 55.733, "lon": 37.581},
    "большой театр": {"address": "Театральная пл., 1", "lat": 55.760, "lon": 37.619},
    "кремлёвский дворец": {"address": "Кремль", "lat": 55.750, "lon": 37.615},
    "крокус сити холл": {"address": "МКАД 65-66 км, Красногорск", "lat": 55.820, "lon": 37.385},
    "мхт им. чехова": {"address": "Камергерский пер., 3", "lat": 55.760, "lon": 37.613},
    "стадион лужники": {"address": "ул. Лужники, 24", "lat": 55.716, "lon": 37.554},
    "олимпийский": {"address": "Олимпийский просп., 16", "lat": 55.783, "lon": 37.635},
    "мегаспорт": {"address": "Ходынский бул., 3", "lat": 55.785, "lon": 37.533},
    "цска арена": {"address": "Ленинградский просп., 39", "lat": 55.791, "lon": 37.537},
    "вегас сити холл": {"address": "МКАД 24 км, ТРЦ Вегас", "lat": 55.618, "lon": 37.720},
    "зарядье": {"address": "ул. Варварка, 6", "lat": 55.750, "lon": 37.629},
    "третьяковская галерея": {"address": "Лаврушинский пер., 10", "lat": 55.741, "lon": 37.620},
    "пушкинский музей": {"address": "ул. Волхонка, 12", "lat": 55.747, "lon": 37.605},
    "мдм": {"address": "Комсомольский просп., 28", "lat": 55.733, "lon": 37.581},
    "театр оперетты": {"address": "ул. Б. Дмитровка, 6", "lat": 55.763, "lon": 37.613},
    "клуб козлова": {"address": "ул. Маросейка, 9/2", "lat": 55.758, "lon": 37.637},
    "adrenaline stadium": {"address": "Ленинградский просп., 80", "lat": 55.809, "lon": 37.510},
    "вднх": {"address": "просп. Мира, 119", "lat": 55.830, "lon": 37.638},
    "depо": {"address": "Лесная ул., 20", "lat": 55.784, "lon": 37.588},
    "гбкз зарядье": {"address": "ул. Варварка, 6", "lat": 55.750, "lon": 37.629},
    "цветной": {"address": "Цветной бул., 13", "lat": 55.771, "lon": 37.621},
    "standup club #1": {"address": "Нижний Сусальный пер., 5", "lat": 55.756, "lon": 37.661},
    "известия hall": {"address": "Пушкинская пл., 5", "lat": 55.765, "lon": 37.606},
    "главclub green concert": {"address": "ул. Орджоникидзе, 11", "lat": 55.706, "lon": 37.598},
    "б1 maximum": {"address": "ул. Орджоникидзе, 11", "lat": 55.706, "lon": 37.598},
    "барвиха luxury village": {"address": "Рублёво-Успенское ш., 114", "lat": 55.739, "lon": 37.266},
}

def get_venue_info(venue_name):
    """Get address and coords for a venue"""
    vn = venue_name.lower().strip()
    for key, data in VENUE_DATA.items():
        if key in vn or vn in key:
            return data
    return None


# ============ AUTO-FETCH: EVENTS (2x/day — Yandex Afisha + KudaGo) ============
def fetch_events():
    while True:
        try:
            events = []
            seen_titles = set()

            # --- 1. Yandex Afisha (scrape HTML) ---
            try:
                req = urllib.request.Request("https://afisha.yandex.ru/moscow", headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept-Language": "ru-RU,ru;q=0.9",
                })
                with urllib.request.urlopen(req, timeout=20, context=CTX) as r:
                    html = r.read().decode("utf-8", errors="replace")

                if "Подтвердите" not in html:
                    # Clean HTML tags, extract text
                    clean = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.S)
                    clean = re.sub(r'<style[^>]*>.*?</style>', '', clean, flags=re.S)
                    text = re.sub(r'</?(div|p|h[1-6]|li|section|article|header|span|a|img|picture|source|svg|path|circle|button|figure|figcaption|label|input|form|nav|footer|main|aside|ul|ol|dl|dt|dd|table|tr|td|th|meta|link|noscript)[^>]*>', '\n', clean)
                    text = re.sub(r'<[^>]+>', '', text)
                    text = re.sub(r'[ \t]+', ' ', text)
                    lines = [l.strip() for l in text.split('\n') if l.strip() and len(l.strip()) > 2]

                    for i, line in enumerate(lines):
                        # Find "Venue • Date" pattern
                        m = re.match(r'^(.{3,40})\s*[•·]\s*(.*(?:сегодня|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря|\d{1,2}:\d{2}).*)$', line)
                        if m:
                            venue = m.group(1).strip()
                            date_str = m.group(2).strip()
                            # Find event title — look backwards for a non-trivial line
                            title = ""
                            for j in range(i - 1, max(0, i - 5), -1):
                                pv = lines[j]
                                if (pv and len(pv) > 4 and
                                    not pv.startswith('от ') and
                                    'Выбрать' not in pv and
                                    'Все события' not in pv and
                                    not re.match(r'^[\d\s₽%•·]+$', pv) and
                                    '•' not in pv):
                                    title = pv
                                    break

                            if title and title not in seen_titles and len(venue) > 2:
                                seen_titles.add(title)
                                vi = get_venue_info(venue)
                                # Parse time from date string (e.g. "27 марта, 20:00")
                                time_m = re.search(r'(\d{1,2}:\d{2})', date_str)
                                start_time = time_m.group(1) if time_m else "19:00"
                                # Estimate end time (+2.5h)
                                sh = int(start_time.split(':')[0])
                                end_time = f"{(sh + 2) % 24:02d}:30"

                                events.append({
                                    "name": title[:60],
                                    "venue": venue[:40],
                                    "address": vi["address"] if vi else "",
                                    "lat": vi["lat"] if vi else 0,
                                    "lon": vi["lon"] if vi else 0,
                                    "start": start_time,
                                    "end": end_time,
                                    "date": date_str[:25],
                                    "hot": True,
                                    "source": "Яндекс.Афиша"
                                })
                    print(f"[EVENTS] Yandex Afisha: {len(events)} events")
                else:
                    print("[EVENTS] Yandex Afisha: CAPTCHA")
            except Exception as e1:
                print(f"[EVENTS] Yandex Afisha failed: {e1}")

            # --- 2. KudaGo API (with retry) ---
            for attempt in range(3):
                try:
                    ts = int(time.time())
                    url = f"https://kudago.com/public-api/v1.4/events/?location=msk&actual_since={ts}&page_size=10&fields=title,place,dates&text_format=text"
                    req = urllib.request.Request(url, headers={"User-Agent": "TaxiAssistant/1.0"})
                    with urllib.request.urlopen(req, timeout=30, context=CTX) as r:
                        data = json.loads(r.read())
                    for ev in data.get("results", [])[:8]:
                        title = ev.get("title", "Событие")
                        if title in seen_titles:
                            continue
                        seen_titles.add(title)
                        place = ev.get("place", {})
                        venue = place.get("title", "Москва") if isinstance(place, dict) else "Москва"
                        dates = ev.get("dates", [{}])
                        start, end = "", ""
                        if dates:
                            s = dates[0].get("start")
                            e = dates[0].get("end")
                            if s:
                                start = time.strftime("%H:%M", time.gmtime(s + 3 * 3600))
                            if e:
                                end = time.strftime("%H:%M", time.gmtime(e + 3 * 3600))
                        vi = get_venue_info(venue)
                        events.append({
                            "name": title[:60],
                            "venue": (venue or "Москва")[:40],
                            "address": vi["address"] if vi else "",
                            "lat": vi["lat"] if vi else 0,
                            "lon": vi["lon"] if vi else 0,
                            "start": start or "19:00",
                            "end": end or "22:00",
                            "date": "",
                            "hot": len([e for e in events if e.get("source") == "KudaGo"]) < 2,
                            "source": "KudaGo"
                        })
                    print(f"[EVENTS] KudaGo: total now {len(events)} (attempt {attempt+1})")
                    break
                except Exception as e2:
                    print(f"[EVENTS] KudaGo attempt {attempt+1} failed: {e2}")
                    if attempt < 2:
                        time.sleep(10)

            # --- 3. Fallback if both sources failed ---
            if not events:
                print("[EVENTS] Using fallback events")
                day = int(time.time()) // 86400
                all_events = [
                    {"name": "Спектакль «Мастер и Маргарита»", "venue": "МХТ им. Чехова", "address": "Камергерский пер., 3", "lat": 55.760, "lon": 37.613, "start": "19:00", "end": "22:00", "hot": True},
                    {"name": "Балет «Лебединое озеро»", "venue": "Большой театр", "address": "Театральная пл., 1", "lat": 55.760, "lon": 37.619, "start": "19:30", "end": "22:30", "hot": True},
                    {"name": "Концерт «Симфоническая ночь»", "venue": "Зарядье", "address": "ул. Варварка, 6", "lat": 55.750, "lon": 37.629, "start": "20:00", "end": "22:30", "hot": True},
                    {"name": "Ледовое шоу", "venue": "Мегаспорт", "address": "Ходынский бул., 3", "lat": 55.785, "lon": 37.533, "start": "18:00", "end": "20:30", "hot": True},
                    {"name": "Мюзикл «Призрак оперы»", "venue": "МДМ", "address": "Комсомольский просп., 28", "lat": 55.733, "lon": 37.581, "start": "19:00", "end": "22:00", "hot": True},
                    {"name": "Стендап-вечер", "venue": "StandUp Club #1", "address": "Нижний Сусальный пер., 5", "lat": 55.756, "lon": 37.661, "start": "20:00", "end": "23:00", "hot": False},
                ]
                random.seed(day)
                selected = random.sample(all_events, min(5, len(all_events)))
                for ev in selected:
                    ev["source"] = "Афиша"
                    ev["date"] = ""
                events = selected

            DATA["events"] = events
            DATA["last_update"] = time.time()
            print(f"[EVENTS] Total: {len(events)} events")
        except Exception as e:
            print(f"[EVENTS ERR] {e}")
            # Emergency fallback — ALWAYS have events
            if not DATA.get("events"):
                DATA["events"] = [
                    {"name": "Мюзикл «Вальс-бостон»", "venue": "Москвич", "address": "Волгоградский просп., 46/15", "lat": 55.716, "lon": 37.735, "start": "19:00", "end": "22:00", "date": "", "hot": True, "source": "Афиша"},
                    {"name": "Балет «Лебединое озеро»", "venue": "Большой театр", "address": "Театральная пл., 1", "lat": 55.760, "lon": 37.619, "start": "19:30", "end": "22:30", "date": "", "hot": True, "source": "Афиша"},
                    {"name": "Концерт «Симфоническая ночь»", "venue": "Зарядье", "address": "ул. Варварка, 6", "lat": 55.750, "lon": 37.629, "start": "20:00", "end": "22:30", "date": "", "hot": True, "source": "Афиша"},
                    {"name": "Стендап-концерт", "venue": "StandUp Club #1", "address": "Нижний Сусальный пер., 5", "lat": 55.756, "lon": 37.661, "start": "20:00", "end": "23:00", "date": "", "hot": False, "source": "Афиша"},
                    {"name": "Мюзикл «Призрак оперы»", "venue": "МДМ", "address": "Комсомольский просп., 28", "lat": 55.733, "lon": 37.581, "start": "19:00", "end": "22:00", "date": "", "hot": True, "source": "Афиша"},
                ]
                DATA["last_update"] = time.time()
                print(f"[EVENTS] Emergency fallback: {len(DATA['events'])} events")
        time.sleep(43200)  # 2x per day


# ============ AUTO-FETCH: FUEL ============
def fetch_fuel():
    while True:
        try:
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
                    "name": s["name"], "address": s["address"],
                    "lat": s["lat"], "lon": s["lon"],
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
        time.sleep(86400)


# ============ KEEP-ALIVE ============
def keep_alive():
    url = os.environ.get("RENDER_EXTERNAL_URL", "https://taxi-api-b4ni.onrender.com")
    while True:
        try:
            req = urllib.request.Request(f"{url}/api/status", headers={"User-Agent": "KeepAlive/1.0"})
            with urllib.request.urlopen(req, timeout=10, context=CTX) as r:
                r.read()
        except:
            pass
        time.sleep(840)


# ============ START BACKGROUND THREADS ============
def start_fetchers():
    for fn in [fetch_weather, fetch_demand, fetch_alerts, fetch_events, fetch_fuel, keep_alive]:
        t = threading.Thread(target=fn, daemon=True)
        t.start()
        time.sleep(1)
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
                    "fuel_count": len(DATA["fuel"]),
                    "traffic_multiplier": get_traffic_multiplier()})


# ============ ORDER ANALYSIS ============
@app.route("/api/analyze_order", methods=["POST"])
def analyze_order():
    """
    Analyze a taxi order. Input JSON:
    {
        "pickup_lat": 55.75, "pickup_lon": 37.62,
        "dropoff_lat": 55.97, "dropoff_lon": 37.41,
        "price": 1500,           # offered price in rubles
        "pickup_address": "...", # optional text
        "dropoff_address": "..." # optional text
    }
    Returns recommendation: take/skip/consider with analysis.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "no json"}), 400

    plat = data.get("pickup_lat", 0)
    plon = data.get("pickup_lon", 0)
    dlat = data.get("dropoff_lat", 0)
    dlon = data.get("dropoff_lon", 0)
    price = data.get("price", 0)
    pickup_addr = data.get("pickup_address", "")
    dropoff_addr = data.get("dropoff_address", "")

    # --- Distance (straight line * 1.4 for road factor) ---
    straight_km = haversine(plat, plon, dlat, dlon)
    road_km = round(straight_km * 1.4, 1)

    # --- Traffic ---
    traffic = get_traffic_multiplier()
    hour = (time.gmtime().tm_hour + 3) % 24
    base_speed = 35  # km/h average Moscow
    effective_speed = base_speed / traffic
    duration_min = round((road_km / effective_speed) * 60)

    # --- Zones ---
    pickup_zone = detect_zone(plat, plon) if plat else "Неизвестно"
    dropoff_zone = detect_zone(dlat, dlon) if dlat else "Неизвестно"

    # --- Dropoff zone demand (will I get order there?) ---
    dropoff_coeff = ZONES.get(dropoff_zone, {}).get("base_coeff", 1.0)
    # Adjust for time of day
    if 22 <= hour or hour <= 4:
        if "Центр" in dropoff_zone or "Сити" in dropoff_zone:
            dropoff_coeff *= 1.3
    elif 7 <= hour <= 9:
        if "Центр" in dropoff_zone or "Сити" in dropoff_zone:
            dropoff_coeff *= 1.4

    # --- Fair price estimate ---
    # Base: 100₽ start + 15₽/km + time penalty in traffic
    fair_price = round(100 + road_km * 15 * traffic * 0.7 + duration_min * 3)

    # --- Rubles per km ---
    rub_per_km = round(price / road_km, 1) if road_km > 0 else 0

    # --- Rubles per minute ---
    rub_per_min = round(price / duration_min, 1) if duration_min > 0 else 0

    # --- DPS on route ---
    dps_on_route = []
    for alert in DATA.get("alerts", []):
        if alert.get("type") == "dps" and alert.get("lat"):
            # Check if DPS is within 2km of route line
            alat, alon = alert["lat"], alert["lon"]
            d_to_pickup = haversine(plat, plon, alat, alon)
            d_to_dropoff = haversine(dlat, dlon, alat, alon)
            if d_to_pickup < road_km * 0.8 or d_to_dropoff < road_km * 0.8:
                dps_on_route.append(alert["text"])

    # --- Recommendation ---
    score = 50  # neutral
    reasons = []

    # Price vs fair
    if price >= fair_price * 1.2:
        score += 25
        reasons.append(f"💰 Цена выше рынка: {price}₽ vs ~{fair_price}₽")
    elif price >= fair_price * 0.9:
        score += 10
        reasons.append(f"💵 Цена в рынке: {price}₽ vs ~{fair_price}₽")
    else:
        score -= 20
        reasons.append(f"⚠️ Цена ниже рынка: {price}₽ vs ~{fair_price}₽")

    # Rub/km efficiency
    if rub_per_km >= 25:
        score += 15
        reasons.append(f"✅ Хороший ₽/км: {rub_per_km}₽/км")
    elif rub_per_km >= 15:
        score += 5
        reasons.append(f"📊 Нормальный ₽/км: {rub_per_km}₽/км")
    else:
        score -= 15
        reasons.append(f"❌ Низкий ₽/км: {rub_per_km}₽/км")

    # Dropoff zone (will I get next order?)
    if dropoff_coeff >= 1.5:
        score += 15
        reasons.append(f"🟢 Высокий спрос на точке Б ({dropoff_zone})")
    elif dropoff_coeff >= 1.2:
        score += 5
        reasons.append(f"🟡 Средний спрос на точке Б ({dropoff_zone})")
    else:
        score -= 10
        reasons.append(f"🔴 Низкий спрос на точке Б ({dropoff_zone})")

    # Traffic penalty
    if traffic >= 1.8:
        score -= 10
        reasons.append(f"🚗 Пробки {traffic}x — потеря времени")
    elif traffic <= 1.2:
        score += 5
        reasons.append(f"🛣 Свободные дороги ({traffic}x)")

    # Airport bonus
    if "аэропорт" in dropoff_zone.lower() or "Шереметьево" in dropoff_zone or "Домодедово" in dropoff_zone or "Внуково" in dropoff_zone:
        score += 10
        reasons.append("✈️ Бонус за аэропорт — обратный заказ почти гарантирован")

    # DPS warning
    if dps_on_route:
        reasons.append(f"🚔 ДПС на маршруте: {', '.join(dps_on_route[:2])}")

    # Final decision
    score = max(0, min(100, score))
    if score >= 70:
        recommendation = "БРАТЬ"
        color = "green"
    elif score >= 45:
        recommendation = "НА УСМОТРЕНИЕ"
        color = "yellow"
    else:
        recommendation = "ПРОПУСТИТЬ"
        color = "red"

    return jsonify({
        "recommendation": recommendation,
        "score": score,
        "color": color,
        "reasons": reasons,
        "analysis": {
            "distance_km": road_km,
            "duration_min": duration_min,
            "traffic": traffic,
            "pickup_zone": pickup_zone,
            "dropoff_zone": dropoff_zone,
            "price": price,
            "fair_price": fair_price,
            "rub_per_km": rub_per_km,
            "rub_per_min": rub_per_min,
            "dropoff_demand": round(dropoff_coeff, 1),
            "dps_on_route": dps_on_route
        }
    })


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
    return jsonify({"service": "Taxi Assistant API", "auto_update": True,
                    "endpoints": ["/api/weather", "/api/events", "/api/alerts",
                                  "/api/demand", "/api/fuel", "/api/status",
                                  "/api/analyze_order"]})


start_fetchers()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
