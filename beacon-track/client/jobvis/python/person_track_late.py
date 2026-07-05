from ultralytics import YOLO

import cv2
import requests
from datetime import datetime, timezone
import time

model = YOLO("yolov8n.pt")

SERVER_URL = "http://10.0.0.142:8000/beacon"
DEVICE_NAME = "PI_CAM_1"

RUN_TIME = 22      # seconds ON
SLEEP_TIME = 30    # seconds OFF

last_sent = 0
MIN_INTERVAL = 1.0

def send_json(obj_name, conf):
    global last_sent

    now = time.time()
    if now - last_sent < MIN_INTERVAL:
        return

    payload = {
        "device": DEVICE_NAME,
        "event_type": "object_detected",
        "object": obj_name,
        "confidence": conf,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    print("SEND:", payload)

    try:
        requests.post(SERVER_URL, json=payload, timeout=2)
    except Exception as e:
        print("POST error:", e)

    last_sent = now


def run_detection():
    cap = cv2.VideoCapture(0)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    start = time.time()

    while time.time() - start < RUN_TIME:

        ret, frame = cap.read()
        if not ret:
            break

        results = model(frame, verbose=False)
        r = results[0]

        for box in r.boxes:
            cls = int(box.cls[0])
            name = model.names[cls]
            conf = float(box.conf[0])

            print(name, conf)
            
            # Add saving image also
            try:
                annotated = r.plot()
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"imgs/detection_{ts}.jpg"
                print("Writing file ->", filename)
                cv2.imwrite(filename, annotated)
            except:
                print("Error Found at image save")
            send_json(name, conf)

        annotated = r.plot()
        cv2.imshow("YOLO Active Window", annotated)

        if cv2.waitKey(1) == ord('q'):
            cap.release()
            cv2.destroyAllWindows()
            exit()

    cap.release()
    cv2.destroyAllWindows()


# -------------------------
# MAIN DUTY CYCLE LOOP
# -------------------------
while True:
    print("Sleeping...")
    time.sleep(SLEEP_TIME)

    print("Running detection window...")
    run_detection()
