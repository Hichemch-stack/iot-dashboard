import json
from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import os
import requests
import pandas as pd
import numpy as np
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LinearRegression
from datetime import datetime




# ==========================================================
# Chargement configuration
# ==========================================================
load_dotenv()

CHANNEL_ID = os.getenv("THINGSPEAK_CHANNEL_ID", "3406001")
READ_API_KEY = os.getenv("THINGSPEAK_READ_API_KEY")
MONGODB_URI = os.getenv("MONGODB_URI")
FLASK_HOST = os.getenv("FLASK_HOST", "127.0.0.1")
FLASK_PORT = int(os.getenv("FLASK_PORT", "5000"))

THINGSPEAK_URL = (
    f"https://api.thingspeak.com/channels/{CHANNEL_ID}/feeds.json"
    f"?api_key={READ_API_KEY}&results=200"
)

# ==========================================================
# Flask
# ==========================================================
app = Flask(__name__)
CORS(app)

# ==========================================================
# MongoDB Atlas
# ==========================================================
mongo_client = MongoClient(
    MONGODB_URI,
    server_api=ServerApi("1"),
    tls=True,
    tlsAllowInvalidCertificates=True,
    serverSelectionTimeoutMS=30000,
    connectTimeoutMS=30000,
    socketTimeoutMS=30000
)
db = mongo_client["environment_ai_db"]

raw_collection = db["raw_sensor_data"]
processed_collection = db["processed_sensor_data"]
analytics_collection = db["analytics_results"]


# ==========================================================
# Récupération ThingSpeak
# ==========================================================
def fetch_thingspeak_data():
    response = requests.get(THINGSPEAK_URL, timeout=15)
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
        "entry_id",
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
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")

    df = df.dropna(subset=[
        "entry_id",
        "created_at",
        "temp_dht",
        "humidity",
        "temp_lm35",
        "luminosity",
        "motion",
        "distance",
        "risk_score",
        "alert_code"
    ])

    df = df.sort_values("created_at").reset_index(drop=True)

    return df


# ==========================================================
# Qualité des données
# ==========================================================
def compute_data_quality(df):
    if df.empty:
        return 0

    expected_cols = [
        "temp_dht",
        "humidity",
        "temp_lm35",
        "luminosity",
        "motion",
        "distance",
        "risk_score",
        "alert_code"
    ]

    total_values = len(df) * len(expected_cols)
    missing_values = df[expected_cols].isna().sum().sum()

    quality = 100 - ((missing_values / total_values) * 100)

    # pénalité si valeurs hors plages réalistes
    invalid_count = 0

    invalid_count += ((df["temp_dht"] < -20) | (df["temp_dht"] > 80)).sum()
    invalid_count += ((df["humidity"] < 0) | (df["humidity"] > 100)).sum()
    invalid_count += ((df["luminosity"] < 0) | (df["luminosity"] > 100)).sum()
    invalid_count += ((df["distance"] < 0) | (df["distance"] > 500)).sum()
    invalid_count += ((df["risk_score"] < 0) | (df["risk_score"] > 100)).sum()

    quality -= invalid_count * 2

    quality = max(0, min(100, quality))
    return round(float(quality), 2)


# ==========================================================
# Calcul ECI : Environmental Criticality Index
# ==========================================================
def compute_eci(row, anomaly_score):
    risk = float(row.get("risk_score", 0))
    temp = float(row.get("temp_dht", 0))
    hum = float(row.get("humidity", 0))
    light = float(row.get("luminosity", 0))
    motion = float(row.get("motion", 0))
    distance = float(row.get("distance", 999))

    eci = 0

    # poids principal : risk score ESP32
    eci += risk * 0.45

    # température critique
    if temp > 35:
        eci += 15
    if temp > 40:
        eci += 10
    if temp < 5:
        eci += 10

    # humidité anormale
    if hum < 25 or hum > 80:
        eci += 12

    # luminosité anormale
    if light < 15 or light > 90:
        eci += 8

    # mouvement + obstacle proche
    if motion == 1:
        eci += 8

    if distance > 0 and distance < 50:
        eci += 12

    # anomalie IA
    if anomaly_score == -1:
        eci += 20

    return round(min(100, max(0, eci)), 2)


def classify_decision(eci):
    if eci >= 70:
        return "CRITICAL"
    elif eci >= 35:
        return "WARNING"
    else:
        return "NORMAL"


# ==========================================================
# Analyse Data + IA
# ==========================================================
def analyze_data(df):
    if df.empty:
        return df, None, {}

    df = df.copy()

    # Feature engineering
    df["temp_moving_avg"] = df["temp_dht"].rolling(window=5, min_periods=1).mean()
    df["humidity_moving_avg"] = df["humidity"].rolling(window=5, min_periods=1).mean()
    df["risk_moving_avg"] = df["risk_score"].rolling(window=5, min_periods=1).mean()

    df["temp_variation"] = df["temp_dht"].diff().fillna(0)
    df["humidity_variation"] = df["humidity"].diff().fillna(0)
    df["risk_variation"] = df["risk_score"].diff().fillna(0)

    df["temp_gap_dht_lm35"] = abs(df["temp_dht"] - df["temp_lm35"])

    data_quality_score = compute_data_quality(df)

    # Si données insuffisantes
    if len(df) < 5:
        df["anomaly_code"] = 1
        df["anomaly_label"] = "Normal"
        df["environmental_criticality_index"] = df.apply(
            lambda row: compute_eci(row, 1), axis=1
        )
        df["ai_decision"] = df["environmental_criticality_index"].apply(classify_decision)
        df["data_quality_score"] = data_quality_score

        summary = build_summary(df, None, data_quality_score)
        return df, None, summary

    features = df[[
        "temp_dht",
        "humidity",
        "temp_lm35",
        "luminosity",
        "motion",
        "distance",
        "risk_score",
        "temp_variation",
        "humidity_variation",
        "risk_variation"
    ]].fillna(0)

    # IA 1 : Détection anomalies
    contamination_value = 0.15 if len(df) >= 10 else 0.10

    anomaly_model = IsolationForest(
        contamination=contamination_value,
        random_state=42
    )

    df["anomaly_code"] = anomaly_model.fit_predict(features)
    df["anomaly_label"] = df["anomaly_code"].apply(
        lambda x: "Anomaly" if x == -1 else "Normal"
    )

    # IA 2 : Prédiction température
    df = df.reset_index(drop=True)

    X = df.index.values.reshape(-1, 1)
    y = df["temp_dht"].values

    prediction_model = LinearRegression()
    prediction_model.fit(X, y)

    pred = float(prediction_model.predict([[len(df)]])[0])

    # Borne réaliste pour éviter affichage absurde
    if pred < -20 or pred > 80:
        next_temp_prediction = None
    else:
        next_temp_prediction = round(pred, 2)

    # ECI + décision IA
    df["environmental_criticality_index"] = df.apply(
        lambda row: compute_eci(row, row["anomaly_code"]), axis=1
    )

    df["ai_decision"] = df["environmental_criticality_index"].apply(classify_decision)
    df["data_quality_score"] = data_quality_score

    summary = build_summary(df, next_temp_prediction, data_quality_score)

    return df, next_temp_prediction, summary


# ==========================================================
# Résumé Analytics
# ==========================================================
def build_summary(df, next_temp_prediction, data_quality_score):
    if df.empty:
        return {}

    latest = df.iloc[-1]

    total = len(df)
    anomalies = int((df["anomaly_label"] == "Anomaly").sum()) if "anomaly_label" in df.columns else 0

    decision_counts = {}
    if "ai_decision" in df.columns:
        decision_counts = df["ai_decision"].value_counts().to_dict()

    summary = {
        "total_records": int(total),
        "anomalies_detected": anomalies,
        "next_temp_prediction": next_temp_prediction,
        "data_quality_score": float(data_quality_score),

        "latest_entry_id": int(latest["entry_id"]),
        "latest_temp_dht": float(latest["temp_dht"]),
        "latest_humidity": float(latest["humidity"]),
        "latest_risk_score": float(latest["risk_score"]),
        "latest_eci": float(latest["environmental_criticality_index"]),
        "latest_ai_decision": str(latest["ai_decision"]),

        "avg_temp_dht": round(float(df["temp_dht"].mean()), 2),
        "avg_humidity": round(float(df["humidity"].mean()), 2),
        "avg_luminosity": round(float(df["luminosity"].mean()), 2),
        "avg_risk_score": round(float(df["risk_score"].mean()), 2),
        "avg_eci": round(float(df["environmental_criticality_index"].mean()), 2),

        "max_temp_dht": round(float(df["temp_dht"].max()), 2),
        "max_risk_score": round(float(df["risk_score"].max()), 2),
        "max_eci": round(float(df["environmental_criticality_index"].max()), 2),
        "min_distance": round(float(df["distance"].min()), 2),

        "normal_count": int(decision_counts.get("NORMAL", 0)),
        "warning_count": int(decision_counts.get("WARNING", 0)),
        "critical_count": int(decision_counts.get("CRITICAL", 0)),

        "processed_at": datetime.now().isoformat()
    }

    return summary


# ==========================================================
# Sauvegarde MongoDB
# ==========================================================
def save_to_mongodb(raw_df, processed_df, summary):
    if raw_df.empty or processed_df.empty:
        return {
            "storage_mode": "none",
            "records_saved": 0,
            "message": "No data to save"
        }

    raw_records = raw_df.copy()
    raw_records["ingested_at"] = datetime.now().isoformat()

    processed_records = processed_df.copy()
    processed_records["processed_at"] = datetime.now().isoformat()

    try:
        # Test connexion Atlas
        mongo_client.admin.command("ping")

        raw_collection.delete_many({})
        processed_collection.delete_many({})
        analytics_collection.delete_many({})

        raw_collection.insert_many(raw_records.to_dict("records"))
        processed_collection.insert_many(processed_records.to_dict("records"))
        analytics_collection.insert_one(summary)

        return {
            "storage_mode": "mongodb_atlas",
            "records_saved": len(processed_records),
            "message": "Data saved successfully to MongoDB Atlas"
        }

    except Exception as e:
        # Fallback JSON local si Atlas indisponible
        fallback_payload = {
            "storage_mode": "local_json_fallback",
            "error": str(e),
            "saved_at": datetime.now().isoformat(),
            "summary": summary,
            "processed_data": processed_records.to_dict("records")
        }

        with open("analytics_cache.json", "w", encoding="utf-8") as f:
            json.dump(fallback_payload, f, ensure_ascii=False, indent=2, default=str)

        return {
            "storage_mode": "local_json_fallback",
            "records_saved": len(processed_records),
            "message": "MongoDB Atlas unavailable. Data saved to analytics_cache.json"
        }
# ==========================================================
# API Routes
# ==========================================================
@app.route("/")
def home():
    return jsonify({
        "message": "AI Smart Environmental Monitoring Backend v2 is running",
        "channel_id": CHANNEL_ID,
        "database": "MongoDB Atlas",
        "endpoints": [
            "/api/health",
            "/api/analyze",
            "/api/latest",
            "/api/stats",
            "/api/analytics",
            "/api/timeseries",
            "/api/alerts"
        ]
    })


@app.route("/api/health")
def health():
    try:
        mongo_client.admin.command("ping")
        mongo_status = "connected"
    except Exception as e:
        mongo_status = f"error: {str(e)}"

    return jsonify({
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "thingspeak_channel_id": CHANNEL_ID,
        "mongodb_status": mongo_status
    })


@app.route("/api/analyze")
def api_analyze():
    try:
        raw_df = fetch_thingspeak_data()
        processed_df, next_temp_prediction, summary = analyze_data(raw_df)
        storage_result = save_to_mongodb(raw_df, processed_df, summary)

        return jsonify({
            "status": "success",
            "records_analyzed": int(len(processed_df)),
            "records_saved": int(storage_result.get("records_saved", 0)),
	    "storage_mode": storage_result.get("storage_mode"),
            "storage_message": storage_result.get("message"),
            "anomalies_detected": int(summary.get("anomalies_detected", 0)),
            "next_temp_prediction": summary.get("next_temp_prediction"),
            "latest_eci": summary.get("latest_eci"),
            "latest_ai_decision": summary.get("latest_ai_decision"),
            "data_quality_score": summary.get("data_quality_score"),
            "processed_at": datetime.now().isoformat()
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e),
            "processed_at": datetime.now().isoformat()
        }), 500


@app.route("/api/latest")
def api_latest():
    latest = processed_collection.find_one(sort=[("entry_id", -1)])

    if not latest:
        return jsonify({
            "status": "empty",
            "message": "No processed data found. Run /api/analyze first."
        })

    latest["_id"] = str(latest["_id"])

    return jsonify({
        "status": "success",
        "data": latest
    })


@app.route("/api/stats")
def api_stats():
    summary = analytics_collection.find_one(sort=[("processed_at", -1)])

    if not summary:
        return jsonify({
            "status": "empty",
            "message": "No analytics found. Run /api/analyze first."
        })

    summary["_id"] = str(summary["_id"])

    return jsonify({
        "status": "success",
        "stats": summary
    })


@app.route("/api/analytics")
def api_analytics():
    records = list(processed_collection.find({}, {"_id": 0}).sort("entry_id", 1))

    if not records:
        return jsonify({
            "status": "empty",
            "message": "No processed data found. Run /api/analyze first."
        })

    df = pd.DataFrame(records)

    analytics = {
        "temperature": {
            "avg": round(float(df["temp_dht"].mean()), 2),
            "min": round(float(df["temp_dht"].min()), 2),
            "max": round(float(df["temp_dht"].max()), 2),
            "std": round(float(df["temp_dht"].std()), 2) if len(df) > 1 else 0
        },
        "humidity": {
            "avg": round(float(df["humidity"].mean()), 2),
            "min": round(float(df["humidity"].min()), 2),
            "max": round(float(df["humidity"].max()), 2),
            "std": round(float(df["humidity"].std()), 2) if len(df) > 1 else 0
        },
        "risk": {
            "avg": round(float(df["risk_score"].mean()), 2),
            "max": round(float(df["risk_score"].max()), 2)
        },
        "eci": {
            "avg": round(float(df["environmental_criticality_index"].mean()), 2),
            "max": round(float(df["environmental_criticality_index"].max()), 2)
        }
    }

    return jsonify({
        "status": "success",
        "analytics": analytics
    })


@app.route("/api/timeseries")
def api_timeseries():
    records = list(processed_collection.find({}, {"_id": 0}).sort("entry_id", 1))

    if not records:
        return jsonify({
            "status": "empty",
            "message": "No processed data found. Run /api/analyze first."
        })

    return jsonify({
        "status": "success",
        "count": len(records),
        "data": records
    })


@app.route("/api/alerts")
def api_alerts():
    records = list(processed_collection.find({
        "$or": [
            {"anomaly_label": "Anomaly"},
            {"ai_decision": {"$in": ["WARNING", "CRITICAL"]}},
            {"environmental_criticality_index": {"$gte": 35}}
        ]
    }, {"_id": 0}).sort("entry_id", -1))

    return jsonify({
        "status": "success",
        "alerts_count": len(records),
        "alerts": records[:20]
    })


if __name__ == "__main__":
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=False, use_reloader=False)