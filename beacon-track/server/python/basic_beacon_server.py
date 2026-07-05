## Basic beacon server

from flask import Flask, request, jsonify
import csv
import html as html_lib
import os
from datetime import datetime
import pytz

app = Flask(__name__)

CSV_FILE = "esp32_log.csv"
MAX_CSV_LINES = 60000
PAGE_SIZE = 20
JUMP_SIZE = 1000
NODE_LABELS = {
    "ESP_32_DEV_1": "Upstairs Room 1",
    "ESP_32_DEV_2": "Downstairs Area 1",
    "ESP_32_DEV_3": "Downstairs Area 2 Kitchen"
}
CSV_HEADER = [
    "id",
    "timestamp_eastern",
    "mac",
    "name",
    "node",
    "rssi",
    "raw_json"
]
counter = 0

eastern = pytz.timezone("US/Eastern")


# -----------------------
# init CSV
# -----------------------
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADER)


def line_count(path):
    if not os.path.exists(path):
        return 0

    with open(path, "r") as f:
        return sum(1 for _ in f)


def reset_csv_file(path):
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADER)


def to_eastern_timestamp(value):
    if not value:
        return datetime.now(eastern).isoformat()

    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = pytz.utc.localize(parsed)
        return parsed.astimezone(eastern).isoformat()
    except Exception:
        return datetime.now(eastern).isoformat()


# -----------------------
# POST endpoint (ESP32)
# -----------------------
@app.route("/beacon", methods=["POST"])
def beacon():
    global counter

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

    if line_count(CSV_FILE) >= MAX_CSV_LINES:
        reset_csv_file(CSV_FILE)

    counter += 1

    now = to_eastern_timestamp(data.get("timestamp"))

    # Existing BLE beacon payload.
    if "mac" in data or "curDevName" in data:
        mac = data.get("mac", "")
        name = data.get("name", "")
        node = data.get("curDevName", "")
        rssi = data.get("rssi", "")
    # Alternate camera/object-detected payload.
    elif "device" in data and "event_type" in data:
        mac = data.get("image", "")
        name = data.get("object", "")
        node = data.get("device", "")
        rssi = data.get("confidence", "")
    else:
        mac = data.get("mac", data.get("device", ""))
        name = data.get("name", data.get("object", ""))
        node = data.get("curDevName", data.get("event_type", ""))
        rssi = data.get("rssi", data.get("confidence", ""))

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


def read_page(start=0, page_size=PAGE_SIZE):
    if not os.path.exists(CSV_FILE):
        return [], 0

    with open(CSV_FILE, "r") as f:
        rows = list(csv.reader(f))

    if not rows:
        return [], 0

    data_rows = rows[1:]
    total_rows = len(data_rows)

    if total_rows == 0:
        return [], 0

    safe_start = max(0, min(start, max(total_rows - page_size, 0)))
    safe_end = min(safe_start + page_size, total_rows)

    return data_rows[safe_start:safe_end], total_rows


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


def node_location_label(node_name):
    return NODE_LABELS.get(node_name.upper(), "") if node_name else ""


# -----------------------
# GET dashboard
# -----------------------
@app.route("/", methods=["GET"])
def dashboard():
    requested_start = request.args.get("start", type=int)
    page_size = request.args.get("page_size", default=PAGE_SIZE, type=int) or PAGE_SIZE
    page_size = max(1, page_size)

    if requested_start is None:
        _, total_rows = read_page(0, page_size)
        start = max(total_rows - page_size, 0)
    else:
        start = max(requested_start, 0)

    rows, total_rows = read_page(start, page_size)

    if total_rows > 0:
        start = max(0, min(start, max(total_rows - page_size, 0)))
    else:
        start = 0

    prev_page_start = max(start - page_size, 0)
    next_page_start = min(start + page_size, max(total_rows - page_size, 0))
    prev_jump_start = max(start - JUMP_SIZE, 0)
    next_jump_start = min(start + JUMP_SIZE, max(total_rows - page_size, 0))

    showing_from = start + 1 if total_rows > 0 else 0
    showing_to = min(start + page_size, total_rows)

    page_html = """
    <html>
    <head>
        <title>ESP32 Tracker</title>
        <meta http-equiv="refresh" content="10">
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
            .nav { margin-top: 16px; display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
            .nav a, .nav span { padding: 8px 12px; border: 1px solid #999; text-decoration: none; color: #222; background: #f5f5f5; }
            .nav .disabled { color: #888; background: #eee; border-color: #ccc; }
            .status { margin-top: 12px; }
            .node-label { display: block; margin-top: 4px; color: #555; font-size: 12px; }
        </style>
    </head>
    <body>
        <h2>ESP32 BLE Tracker</h2>
        <div class="status">Showing rows """

    page_html += f"""{showing_from} to {showing_to} of {total_rows} (page size {page_size})</div>
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

    for row in rows:
        if len(row) < 6:
            continue

        rid = html_lib.escape(row[0])
        ts = html_lib.escape(row[1])
        mac = html_lib.escape(row[2])
        name = html_lib.escape(row[3])
        node = html_lib.escape(row[4])
        rssi = html_lib.escape(row[5])
        node_label = html_lib.escape(node_location_label(row[4]))

        cls = rssi_class(rssi)

        node_display = node
        if node_label:
            node_display += f'<span class="node-label">{node_label}</span>'

        page_html += f"""
            <tr class="{cls}">
                <td>{rid}</td>
                <td>{ts}</td>
                <td>{mac}</td>
                <td>{name}</td>
                <td>{node_display}</td>
                <td>{rssi}</td>
            </tr>
        """

    page_html += """
        </table>
    """

    if start > 0:
        page_html += f'<div class="nav"><a href="/?start={prev_jump_start}&page_size={page_size}">&laquo; Back 1000</a>'
        page_html += f'<a href="/?start={prev_page_start}&page_size={page_size}">&larr; Back {page_size}</a>'
    else:
        page_html += '<div class="nav"><span class="disabled">&laquo; Back 1000</span>'
        page_html += f'<span class="disabled">&larr; Back {page_size}</span>'

    if start < max(total_rows - page_size, 0):
        page_html += f'<a href="/?start={next_page_start}&page_size={page_size}">Forward {page_size} &rarr;</a>'
        page_html += f'<a href="/?start={next_jump_start}&page_size={page_size}">Forward 1000 &raquo;</a></div>'
    else:
        page_html += f'<span class="disabled">Forward {page_size} &rarr;</span>'
        page_html += '<span class="disabled">Forward 1000 &raquo;</span></div>'

    page_html += """
    </body>
    </html>
    """

    return page_html


# -----------------------
# start server
# -----------------------
if __name__ == "__main__":
    print("Beacon server running at http://0.0.0.0:8000")
    app.run(host="0.0.0.0", port=8000, debug=True)