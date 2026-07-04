## Basic beacon server

from flask import Flask, request, jsonify
import csv
import os
from datetime import datetime
import pytz

app = Flask(__name__)

CSV_FILE = "esp32_log.csv"
counter = 0

eastern = pytz.timezone("US/Eastern")


# -----------------------
# init CSV
# -----------------------
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "id",
            "timestamp_eastern",
            "mac",
            "name",
            "node",
            "rssi",
            "raw_json"
        ])


# -----------------------
# POST endpoint (ESP32)
# -----------------------
@app.route("/beacon", methods=["POST"])
def beacon():
    global counter
    counter += 1

    data = request.get_json(silent=True)

    print("\n====================")
    print("📡 POST RECEIVED")
    print("====================")

    print("HEADERS:")
    for k, v in request.headers.items():
        print(f"{k}: {v}")

    print("\nJSON BODY:")
    print(data)

    if data is None:
        return jsonify({"error": "invalid json"}), 400

    now = datetime.now(eastern).isoformat()

    mac = data.get("mac", "")
    name = data.get("name", "")
    node = data.get("curDevName", "")
    rssi = data.get("rssi", "")

    # write CSV
    with open(CSV_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            counter,
            now,
            mac,
            name,
            node,
            rssi,
            str(data)
        ])

    return jsonify({"status": "ok", "id": counter})


# -----------------------
# helper: read last N rows
# -----------------------
def read_last_n(n=10):
    if not os.path.exists(CSV_FILE):
        return []

    with open(CSV_FILE, "r") as f:
        rows = list(csv.reader(f))

    return rows[-n:] if len(rows) > 1 else []


# -----------------------
# RSSI color mapping
# -----------------------
def rssi_class(rssi):
    try:
        r = int(rssi)
    except:
        return "gray"

    if r >= -45:
        return "green"
    elif r >= -55:
        return "yellow"
    elif r >= -65:
        return "orange"
    else:
        return "red"


# -----------------------
# GET dashboard
# -----------------------
@app.route("/", methods=["GET"])
def dashboard():
    rows = read_last_n(10)

    html = """
    <html>
    <head>
        <title>ESP32 Tracker</title>
        <style>
            body { font-family: Arial; margin: 20px; }
            table { border-collapse: collapse; width: 100%; }
            th, td { border: 1px solid #ccc; padding: 8px; }
            th { background: #eee; }
            .green { background: #b6f2b6; }
            .yellow { background: #f7f7a1; }
            .orange { background: #ffd08a; }
            .red { background: #ffb3b3; }
            .gray { background: #ddd; }
        </style>
    </head>
    <body>
        <h2>ESP32 BLE Tracker - Last 10 Messages</h2>
        <table>
            <tr>
                <th>ID</th>
                <th>Timestamp (ET)</th>
                <th>MAC</th>
                <th>Name</th>
                <th>Node</th>
                <th>RSSI</th>
            </tr>
    """

    # skip header row
    for row in rows[1:]:
        if len(row) < 6:
            continue

        rid = row[0]
        ts = row[1]
        mac = row[2]
        name = row[3]
        node = row[4]
        rssi = row[5]

        cls = rssi_class(rssi)

        html += f"""
            <tr class="{cls}">
                <td>{rid}</td>
                <td>{ts}</td>
                <td>{mac}</td>
                <td>{name}</td>
                <td>{node}</td>
                <td>{rssi}</td>
            </tr>
        """

    html += """
        </table>
    </body>
    </html>
    """

    return html


# -----------------------
# start server
# -----------------------
if __name__ == "__main__":
    print("Beacon server running at http://0.0.0.0:8000")
    app.run(host="0.0.0.0", port=8000, debug=True)