from flask import Flask, jsonify
from flask_cors import CORS
import json, os

app = Flask(__name__)
CORS(app)  # ✅ This enables cross-origin access

ANALYTICS_PATH = "backend/data/analytics.json"

@app.route("/analytics")
def analytics():
    if not os.path.exists(ANALYTICS_PATH):
        return jsonify({})
    with open(ANALYTICS_PATH, "r") as f:
        data = json.load(f)
    return jsonify(data)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
