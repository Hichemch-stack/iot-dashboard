from flask import Flask, jsonify
from flask_cors import CORS
import requests
import pandas as pd
from pymongo import MongoClient
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LinearRegression
from datetime import datetime

# ==========================
# Configuration ThingSpeak
# ==========================
CHANNEL_ID = "3406001"
READ_API_KEY = "UDJ2JHLMJ2UMKP81"

THINGSPEAK_URL = (
    f"https://api.thingspeak.com/channels/{CHANNEL_ID}/feeds.json"
    f"?api_key={READ_API_KEY}&results=100"
)

# ==========================
# Flask API
# ==========================
app = Flask(__name__)
CORS(app)

# ==========================
# MongoDB local
# ==========================
mongo_client = MongoClient("mongodb+srv://admin:admin123@cluster-sujet7.zqxwwjx.mongodb.net/?appName=Cluster-Sujet7")
db = mongo_client["environment_ai_db"]
collection = db["sensor_data"]


def fetch_thingspeak_data():
    response = requests.get(THINGSPEAK_URL, timeout=10)
    response.raise_for_status()

    data = response.json()
    feeds = data.get("feeds", [])

    df = pd.DataFrame(feeds)

    if df.empty:
        return df

    df = df.rename(columns={
        "field1": "temp_dht",
        "field2": "humidity",
        "field3": "temp_lm35",
        "field4": "luminosity",
        "field5": "motion",
        "field6": "distance",
        "field7": "risk_score",
        "field8": "alert_code"
    })

    numeric_cols = [
        "temp_dht",
        "humidity",
        "temp_lm35",
        "luminosity",
        "motion",
        "distance",
        "risk_score",
        "alert_code"
    ]

    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")

    df = df.dropna(subset=[
        "temp_dht",
        "humidity",
        "temp_lm35",
        "luminosity",
        "motion",
        "distance"
    ])

    return df


def analyze_data(df):
    if df.empty:
        return df, None

    if len(df) < 5:
        df["anomaly_code"] = 1
        df["anomaly_label"] = "Normal"
        return df, None

    features = df[[
        "temp_dht",
        "humidity",
        "temp_lm35",
        "luminosity",
        "motion",
        "distance"
    ]]

    # IA 1 : détection d'anomalies environnementales
    anomaly_model = IsolationForest(
        contamination=0.10,
        random_state=42
    )

    df["anomaly_code"] = anomaly_model.fit_predict(features)
    df["anomaly_label"] = df["anomaly_code"].apply(
        lambda x: "Anomaly" if x == -1 else "Normal"
    )

    # IA 2 : prédiction simple de la prochaine température
    df = df.reset_index(drop=True)

    X = df.index.values.reshape(-1, 1)
    y = df["temp_dht"].values

    prediction_model = LinearRegression()
    prediction_model.fit(X, y)

    next_index = [[len(df)]]
    next_temp_prediction = float(prediction_model.predict(next_index)[0])

    return df, next_temp_prediction


def save_to_mongodb(df, next_temp_prediction):
    if df.empty:
        return 0

    df["processed_at"] = datetime.now().isoformat()
    df["next_temp_prediction"] = next_temp_prediction

    records = df.to_dict("records")

    collection.delete_many({})
    collection.insert_many(records)

    return len(records)


@app.route("/")
def home():
    return jsonify({
        "message": "AI Smart Environmental Monitoring API is running on Windows",
        "channel_id": CHANNEL_ID,
        "endpoints": [
            "/api/analyze",
            "/api/latest",
            "/api/stats"
        ]
    })


@app.route("/api/analyze")
def api_analyze():
    try:
        df = fetch_thingspeak_data()
        analyzed_df, next_temp_prediction = analyze_data(df)
        inserted_count = save_to_mongodb(analyzed_df, next_temp_prediction)

        anomaly_count = 0
        if not analyzed_df.empty and "anomaly_label" in analyzed_df.columns:
            anomaly_count = int((analyzed_df["anomaly_label"] == "Anomaly").sum())

        return jsonify({
            "status": "success",
            "records_analyzed": int(len(analyzed_df)),
            "records_saved_mongodb": int(inserted_count),
            "anomalies_detected": anomaly_count,
            "next_temp_prediction": next_temp_prediction,
            "processed_at": datetime.now().isoformat()
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route("/api/latest")
def api_latest():
    latest = collection.find_one(sort=[("entry_id", -1)])

    if not latest:
        return jsonify({
            "status": "empty",
            "message": "No data found in MongoDB. Run /api/analyze first."
        })

    latest["_id"] = str(latest["_id"])

    return jsonify({
        "status": "success",
        "data": latest
    })


@app.route("/api/stats")
def api_stats():
    records = list(collection.find({}, {"_id": 0}))

    if not records:
        return jsonify({
            "status": "empty",
            "message": "No data found in MongoDB. Run /api/analyze first."
        })

    df = pd.DataFrame(records)

    stats = {
        "total_records": int(len(df)),
        "avg_temp_dht": float(df["temp_dht"].mean()),
        "avg_humidity": float(df["humidity"].mean()),
        "avg_luminosity": float(df["luminosity"].mean()),
        "avg_risk_score": float(df["risk_score"].mean()),
        "max_risk_score": float(df["risk_score"].max()),
        "min_distance": float(df["distance"].min()),
        "anomalies_detected": int((df["anomaly_label"] == "Anomaly").sum())
        if "anomaly_label" in df.columns else 0
    }

    return jsonify({
        "status": "success",
        "stats": stats
    })


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)