from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
import numpy as np
from sklearn.ensemble import RandomForestRegressor


app = Flask(__name__)
CORS(app)
from flask_socketio import SocketIO
users = {
    "demo@metro.in": "metro123",
    "admin@metro.in": "admin123"
}

emergency_mode = False

# ── REGISTER ─────────────────────────
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    email = data.get("email")
    password = data.get("password")

    if email in users:
        return jsonify({"msg": "User already exists"}), 400

    users[email] = password
    return jsonify({"msg": "Registered successfully"})


# ── LOGIN ────────────────────────────
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data.get("email")
    password = data.get("password")

    if email in users and users[email] == password:
        return jsonify({
            "msg": "Success",
            "role": "admin" if "admin" in email else "user"
        })

    return jsonify({"msg": "Invalid credentials"}), 401


# ── EMERGENCY MODE ───────────────────
@app.route('/emergency', methods=['POST'])
def emergency():
    global emergency_mode
    emergency_mode = not emergency_mode
    return jsonify({"emergency": emergency_mode})


# ── HISTORY DATA (GRAPH) ─────────────
@app.route('/history')
def history():
    return jsonify({
        "labels": ["10:00", "10:10", "10:20", "10:30", "10:40"],
        "crowd": [80, 120, 200, 160, 220]
    })


# ── ML DATA ───────────────────────────
station_data = {
    "Miyapur":  [20, 30, 50, 80, 120],
    "Ameerpet": [100, 150, 200, 250, 300],
    "LB Nagar": [80, 110, 150, 200, 260]
}


def create_features(data):
    X, y = [], []
    for i in range(2, len(data)):
        X.append([data[i - 1], data[i - 2]])
        y.append(data[i])
    return np.array(X), np.array(y)


def predict_crowd(data):
    if len(data) < 3:
        return data[-1]

    X, y = create_features(data)
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X, y)

    return int(model.predict([data[-2:]])[0])


def predict_delay(crowd_value, hour, station):
    delay = 0

    # Peak hours → more delay
    if 8 <= hour <= 10 or 17 <= hour <= 20:
        delay += 3

    # High crowd → more delay
    if crowd_value > 200:
        delay += 5
    elif crowd_value > 120:
        delay += 2

    # Interchange stations → congestion
    if station in ["Ameerpet", "MGBS"]:
        delay += 2

    return delay


def explain_ai(crowd):
    if crowd > 200:
        return "High passenger density detected → Probability congestion ↑"
    elif crowd > 100:
        return "Moderate flow → Train load stable but rising"
    return "Low density → Normal operating conditions"


def get_station(lat, lng):
    if abs(lat - 17.4968) < 0.01:
        return "Miyapur"
    elif abs(lat - 17.4375) < 0.01:
        return "Ameerpet"
    return "LB Nagar"


# ── MAIN API ──────────────────────────
@app.route('/predict_gps', methods=['POST'])
def predict_gps():
    req = request.json
    station = get_station(req.get('lat', 0), req.get('lng', 0))

    crowd = predict_crowd(station_data[station])
    delay = predict_delay(crowd, req.get('hour', 12), station)

    return jsonify({
        "station": station,
        "crowd": crowd,
        "delay": delay,
        "level": "Heavy" if crowd > 200 else "Moderate" if crowd > 100 else "Low",
        "emergency": emergency_mode,
        "ai_explanation": explain_ai(crowd)
    })
import time
from threading import Thread
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

def push_updates():
    while True:
        socketio.emit('live', {
            "time": time.strftime("%H:%M:%S")
        })
        time.sleep(3)



@app.route("/predict", methods=["POST"])
def predict():
    data = request.json
    hour = data.get("hour")
    station = data.get("station")

    # Get historical data for station
    history = station_data.get(station, [50, 60, 70, 80])

    # Add time effect (simulate peak hours)
    if 8 <= hour <= 10 or 17 <= hour <= 20:
        history = [x + 50 for x in history]   # boost crowd in peak
    elif 11 <= hour <= 16:
        history = [x + 20 for x in history]

    # ML prediction
    crowd_value = predict_crowd(history)
    delay = predict_delay(crowd_value, hour, station)

    # Convert to level
    if crowd_value > 200:
        level = "Heavy"
    elif crowd_value > 100:
        level = "Moderate"
    else:
        level = "Low"

    return jsonify({
        "prediction": level,
        "value": crowd_value,
        "delay": delay,
        "confidence": round(min(1.0, crowd_value / 300), 2),
        "ai_explanation": explain_ai(crowd_value)
    })
# ── METRO STATIONS FOR TICKET BOOKING ────────────────
METRO_LINES_DATA = {
    "red": ["Miyapur", "JNTU College", "KPHB Colony", "Kukatpally", "Ameerpet", "MGBS", "LB Nagar"],
    "blue": ["Raidurg", "Hitech City", "Madhapur", "Jubilee Hills", "Ameerpet", "Begumpet", "Nagole"],
    "green": ["JBS Parade Ground", "Secunderabad West", "RTC X Roads", "MGBS"]
}

@app.route('/api/stations', methods=['GET'])
def get_stations():
    line = request.args.get('line', 'red')
    stations = METRO_LINES_DATA.get(line, METRO_LINES_DATA['red'])
    return jsonify({"stations": stations})

@app.route('/api/calculate_fare', methods=['POST'])
def calculate_fare():
    data = request.json
    from_st = data.get("from_station")
    to_st = data.get("to_station")
    pax = int(data.get("passengers", 1))
    ticket_type = data.get("ticket_type", "single")
    line = data.get("line", "red")
    
    stations = METRO_LINES_DATA.get(line, [])
    
    try:
        idx1 = stations.index(from_st)
        idx2 = stations.index(to_st)
        distance_stations = abs(idx1 - idx2)
    except ValueError:
        distance_stations = 1
        
    # Mock fare algorithm matching UI rules
    base_fare = 10 if ticket_type == "single" else 18 if ticket_type == "return" else 80
    per_station = 5 if ticket_type != "day" else 0
    
    fare_per_passenger = base_fare + (distance_stations * per_station)
    subtotal = fare_per_passenger * pax
    cgst = round(subtotal * 0.09, 2)
    sgst = round(subtotal * 0.09, 2)
    total = round(subtotal + cgst + sgst, 2)
    
    return jsonify({
        "from_station": from_st,
        "to_station": to_st,
        "passengers": pax,
        "ticket_type": ticket_type.upper(),
        "fare_per_pax": fare_per_passenger,
        "subtotal": subtotal,
        "cgst": cgst,
        "sgst": sgst,
        "total": total
    })
@app.route('/')
def home():
    return send_file("index.html")


if __name__ == '__main__':
    socketio.start_background_task(push_updates)
    socketio.run(app, debug=True, use_reloader=False)