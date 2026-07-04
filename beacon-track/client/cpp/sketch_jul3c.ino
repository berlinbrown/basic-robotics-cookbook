//
// Berlin Brown - Copyright 2026 
// Jul, 2026
// Basic ESP32 - Read Blue Tooth Tracker
// Write JSON
// sketch_jul3c.ino - Built with Arduino IDE
// 
#include <WiFi.h>
#include <BLEDevice.h>
#include <BLEScan.h>
#include <BLEAdvertisedDevice.h>
#include <HTTPClient.h>

BLEScan* pBLEScan;

const char* ssid = "SSID";
const char* password = "PASSWORD";

// replace with your Mac IP
const char* serverUrl = "http://10.0.0.101:8000";

// ----------------------
// Target MAC addresses (fake examples for now)
// ----------------------
const String DEVICE_1_MAC = "dd:34:02:0c:00:6a";
const String DEVICE_2_MAC = "42:f9:c2:0d:1d:80";

// ----------------------
// runtime variables
// ----------------------
String selectedMac = "";
String deviceName = "";
int rssiValue = 0;

// ----------------------
void sendJson() {
  if (WiFi.status() != WL_CONNECTED) return;

  HTTPClient http;
  http.begin(serverUrl);
  http.addHeader("Content-Type", "application/json");

  String json = "{";
  json += "\"mac\":\"" + selectedMac + "\",";
  json += "\"name\":\"" + deviceName + "\",";
  json += "\"rssi\":" + String(rssiValue);
  json += "}";

  int code = http.POST(json);
  Serial.print("HTTP code: ");
  Serial.println(code);

  http.end();
}

/**
 * Continue with Class
 */
class MyAdvertisedDeviceCallbacks: public BLEAdvertisedDeviceCallbacks {

  void onResult(BLEAdvertisedDevice device) override {

    Serial.println("---- Device ----");

    // Name (if present)
    if (device.haveName()) {
      Serial.print("Name: ");
      Serial.println(device.getName().c_str());
    }

    // Address (VERY important for identification)
    Serial.print("MAC: ");
    Serial.println(device.getAddress().toString().c_str());

    String mac = device.getAddress().toString().c_str();

    // RSSI (your main tracking signal)
    Serial.print("RSSI: ");
    Serial.println(device.getRSSI());

    // Manufacturer data (raw BLE payload)
    if (device.haveManufacturerData()) {

      String mfg = device.getManufacturerData();

      Serial.print("MFG data length: ");
      Serial.println(mfg.length());

      // Print first few bytes in HEX (safe debugging)
      Serial.print("MFG HEX: ");
      for (int i = 0; i < mfg.length(); i++) {
        Serial.print((uint8_t)mfg[i], HEX);
        Serial.print(" ");
      }
      Serial.println();
    }

    // filter only your target devices
    if (mac == DEVICE_1_MAC || mac == DEVICE_2_MAC) {
      selectedMac = mac;
      rssiValue = device.getRSSI();
      if (device.haveName()) {
        deviceName = device.getName().c_str();
      } else {
        deviceName = "unknown";
      }

      Serial.println("---- TARGET FOUND ---- [ sending message ] ");
      Serial.println("MAC: " + selectedMac);
      Serial.println("NAME: " + deviceName);
      Serial.println("RSSI: " + String(rssiValue));

      sendJson();
    }

    Serial.println("-------------------");
  }
};

void setup() {

  // Setup
  Serial.begin(115200);

  // Connect WIFI
  WiFi.begin(ssid, password);

  Serial.print("Connecting");

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("");
  Serial.println("WiFi connected!");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());

  // Continue with blue tooth integration
  BLEDevice::init("");
  pBLEScan = BLEDevice::getScan();

  pBLEScan->setActiveScan(true);
  pBLEScan->setAdvertisedDeviceCallbacks(new MyAdvertisedDeviceCallbacks());
  pBLEScan->setInterval(100);
  pBLEScan->setWindow(99);

  Serial.println("BLE Scanner started...");
}

void loop() {
  Serial.println("Still alive [scanning]... [ internet version ] 0");

  // Continue with blue tooth integration
  BLEScanResults* results = pBLEScan->start(3, false);

  int count = results->getCount();

  Serial.print("Devices found: ");
  Serial.println(count);

  for (int i = 0; i < count; i++) {
    BLEAdvertisedDevice device = results->getDevice(i);    
    Serial.print("Name: ");
    Serial.print(device.getName().c_str());

    Serial.print(" | RSSI: ");    
    Serial.print(device.getRSSI());   

    Serial.print(" | Address: ");
    Serial.println(device.getAddress().toString().c_str());
  }
  pBLEScan->clearResults();
  
  // Continue to write RSI Data
  if (WiFi.status() == WL_CONNECTED) {

    HTTPClient http;
    http.begin(serverUrl);
    http.addHeader("Content-Type", "application/json");
    String json = "{ \"device\": \"esp32\", \"pingstatus\": 1 }";
    int code = http.POST(json);

    Serial.print("HTTP code: ");
    Serial.println(code);

    http.end();
  }

  // Delay
  delay(5000);
}
