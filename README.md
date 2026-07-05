# basic-robotics-cookbook
Basic Hobby Robotics Cookbook

## Object Tracker System

## Overview

The Cat Tracker System is a distributed IoT monitoring platform designed to determine the location and activity of a cat using multiple independent sensors. The system combines Bluetooth Low Energy (BLE) beacon detection with computer vision to produce a more reliable picture of where the cat is and what it is doing.

Rather than relying on a single tracking technology, the platform fuses information from several devices that communicate using HTTP and JSON.

## System Components

### BLE Beacon

A BLE beacon is attached to the cat's collar and continuously broadcasts Bluetooth advertisements.

### ESP32 Scanner Nodes

Multiple ESP32 devices are placed throughout the house.

Each ESP32:

* Scans for nearby BLE advertisements.
* Detects known beacon MAC addresses.
* Measures RSSI (signal strength).
* Sends JSON telemetry to the central server.

Example telemetry:

```json
{
  "device": "ESP_32_DEV_1",
  "mac": "dd:34:02:0c:00:6a",
  "rssi": -38,
  "timestamp": "2026-07-05T14:20:11Z"
}
```

### Raspberry Pi Vision Node

A Raspberry Pi with a USB webcam performs periodic computer vision.

The vision node:

* Captures live video.
* Runs YOLO object detection.
* Detects objects such as cats and people.
* Saves annotated screenshots when detections occur.
* Sends detection events to the central server.

Example event:

```json
{
  "device": "PI_CAM_1",
  "event_type": "object_detected",
  "object": "cat",
  "confidence": 0.96,
  "image": "detection_20260705_143012.jpg",
  "timestamp": "2026-07-05T14:30:12Z"
}
```

### Central Python Server

The server receives telemetry from all devices.

Responsibilities include:

* HTTP API endpoints
* JSON event processing
* CSV event logging
* Event history
* Basic web dashboard
* Correlation of BLE and camera events

## System Architecture

```text
                +----------------------+
                |   Python Server      |
                |----------------------|
                | REST API             |
                | Event Log            |
                | CSV Storage          |
                | Dashboard            |
                +----------+-----------+
                           ^
                           |
                 HTTP / JSON Events
                           |
        +------------------+------------------+
        |                                     |
+-------+--------+                  +---------+--------+
| ESP32 Scanner  |                  | Raspberry Pi     |
| BLE Detection  |                  | YOLO Detection   |
+-------+--------+                  +---------+--------+
        |                                     |
        |                                     |
   BLE Advertisements                  USB Webcam
        |                                     |
        +------------------+------------------+
                           |
                     Cat BLE Beacon
```

## Event Flow

1. The BLE beacon advertises its identifier.
2. Nearby ESP32 nodes measure signal strength (RSSI).
3. The Raspberry Pi periodically performs object detection.
4. Each device sends JSON events to the server.
5. The server stores and correlates events.
6. A dashboard displays recent activity and estimated cat location.

## Current Features

* BLE beacon detection
* Multiple ESP32 scanner nodes
* RSSI reporting
* HTTP JSON telemetry
* Python event server
* CSV event database
* Raspberry Pi camera integration
* YOLO object detection
* Detection screenshots
* Basic web dashboard

## Planned Features

* Multiple camera support
* Multi-room tracking
* RSSI triangulation
* Detection confidence scoring
* Historical movement timeline
* Heat maps
* Cat movement analytics
* Push notifications
* Mobile dashboard
* Battery monitoring for sensor nodes

## Technologies

* ESP32
* Arduino IDE
* Bluetooth Low Energy (BLE)
* Raspberry Pi
* Python
* Flask
* OpenCV
* Ultralytics YOLO
* HTTP
* JSON
* CSV
* HTML
