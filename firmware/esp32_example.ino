/*
 * MAINTAIN AI — ESP32 live sensor example
 * ----------------------------------------
 * Reads a sensor periodically and pushes it straight into MAINTAIN AI's
 * live-machine-data endpoint. This is one working example, not the only
 * way to do it — swap the sensor-reading section for whatever hardware
 * you actually have (vibration sensor, current clamp, etc.) and keep the
 * WiFi + HTTP POST section as-is.
 *
 * HARDWARE (as written): ESP32 dev board + DHT22 temperature/humidity
 * sensor. DHT22 data pin -> GPIO 4 (change DHTPIN below if wired
 * differently). Don't forget the DHT22's pull-up resistor (4.7k-10k
 * between VCC and DATA) if your breakout board doesn't already have one.
 *
 * LIBRARIES NEEDED (Arduino IDE -> Library Manager):
 *   - "DHT sensor library" by Adafruit
 *   - "Adafruit Unified Sensor" (DHT library depends on this)
 *   (WiFi.h and HTTPClient.h ship with the ESP32 board package already)
 *
 * SETUP:
 *   1. In the app: open the machine's page -> enable IoT device -> copy
 *      the device key it gives you (shown once — if you lose it,
 *      re-enabling issues a new one).
 *   2. Fill in WIFI_SSID, WIFI_PASSWORD, API_BASE_URL, and DEVICE_KEY below.
 *   3. Flash this to the ESP32 (Arduino IDE: Tools -> Board -> your ESP32
 *      board, then Sketch -> Upload).
 *   4. Open the Serial Monitor at 115200 baud to watch it connect and post.
 *
 * API_BASE_URL must be reachable from the ESP32's network. If MAINTAIN AI
 * is running on your laptop (not a public server), that means the ESP32
 * needs to be on the SAME WiFi network, and you use your laptop's local
 * IP (e.g., http://192.168.1.42:8000), not "localhost" — the ESP32 has no
 * idea what "localhost" means on your laptop.
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <WebSocketsClient.h>
#include <time.h>
#include <DHT.h>

// ---- Fill these in ----
const char* WIFI_SSID     = "YOUR_WIFI_NAME";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
const char* API_BASE_URL  = "http://192.168.1.42:8000";   // your machine's local IP + port
const char* DEVICE_KEY    = "PASTE_YOUR_DEVICE_KEY_HERE"; // from the app's IoT Device panel

// WebSocket settings. Use the backend host/IP directly; do not use localhost.
const char* WS_HOST = "192.168.1.42";
const uint16_t WS_PORT = 8000;
const char* WS_PATH = "/api/devices/ws";

// OPTIONAL SAFETY OUTPUT. Connect this to a properly rated safety relay/contactor
// interface, never directly to mains. Choose the polarity for your relay module.
const int SAFETY_RELAY_PIN = 26;
const bool SAFETY_RELAY_ACTIVE_HIGH = true;
bool machineShutdownLatched = false;

void setMachinePower(bool on) {
  bool output = SAFETY_RELAY_ACTIVE_HIGH ? on : !on;
  digitalWrite(SAFETY_RELAY_PIN, output ? HIGH : LOW);
}

// ---- Sensor wiring ----
#define DHTPIN 4
#define DHTTYPE DHT22
DHT dht(DHTPIN, DHTTYPE);

// How often to send a reading. Don't go faster than every few seconds —
// there's no need, and it just spams the audit-adjacent alert checks.
const unsigned long SEND_INTERVAL_MS = 30000; // 30 seconds
unsigned long lastSendTime = 0;
WebSocketsClient webSocket;
bool wsConnected = false;

String utcTimestamp() {
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo, 1000)) return "";
  char buf[25];
  strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%SZ", &timeinfo);
  return String(buf);
}

void webSocketEvent(WStype_t type, uint8_t* payload, size_t length) {
  if (type == WStype_CONNECTED) {
    wsConnected = true;
    String auth = String("{\"type\":\"authenticate\",\"device_key\":\"") + DEVICE_KEY + "\"}";
    webSocket.sendTXT(auth);
    Serial.println("Telemetry WebSocket connected — authenticating...");
  } else if (type == WStype_DISCONNECTED) {
    wsConnected = false;
    Serial.println("Telemetry WebSocket disconnected — reconnecting automatically...");
  } else if (type == WStype_TEXT) {
    Serial.printf("WS <- %.*s\n", (int)length, payload);
  }
}

void connectWebSocket() {
  webSocket.begin(WS_HOST, WS_PORT, WS_PATH);
  webSocket.onEvent(webSocketEvent);
  webSocket.setReconnectInterval(5000);
  webSocket.enableHeartbeat(15000, 3000, 2);
}

void connectWiFi() {
  Serial.print("Connecting to WiFi");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  Serial.print("Connected. IP address: ");
  Serial.println(WiFi.localIP());
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");
  Serial.println("Synchronizing UTC clock...");
  struct tm timeinfo;
  getLocalTime(&timeinfo, 10000);
  connectWebSocket();
}

// Sends one reading. Returns true on success (HTTP 2xx).
bool sendReading(const char* readingType, float value, const char* unit) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi dropped — reconnecting before sending...");
    connectWiFi();
  }

  String timestamp = utcTimestamp();
  String body = String("{\"type\":\"reading\",\"reading_type\":\"") + readingType +
                "\",\"value\":" + String(value, 2) +
                ",\"unit\":\"" + unit + "\"" +
                (timestamp.length() ? String(",\"recorded_at\":\"") + timestamp + "\"" : "") + "}";

  if (wsConnected) {
    webSocket.sendTXT(body);
    Serial.printf("[%s] WS -> %s\\n", readingType, body.c_str());
    return true;
  }

  // Backwards-compatible HTTP fallback while the WebSocket is reconnecting.
  HTTPClient http;
  String url = String(API_BASE_URL) + "/api/devices/ingest";
  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-Key", DEVICE_KEY);
  String httpBody = String("{\"reading_type\":\"") + readingType +
                    "\",\"value\":" + String(value, 2) +
                    ",\"unit\":\"" + unit + "\"" +
                    (timestamp.length() ? String(",\"recorded_at\":\"") + timestamp + "\"" : "") + "}";
  int statusCode = http.POST(httpBody);
  Serial.printf("[%s] HTTP fallback -> %d\\n", readingType, statusCode);
  http.end();
  return statusCode >= 200 && statusCode < 300;
}*
 * MAINTAIN AI — ESP32 live sensor example
 * ----------------------------------------
 * Reads a sensor periodically and pushes it straight into MAINTAIN AI's
 * live-machine-data endpoint. This is one working example, not the only
 * way to do it — swap the sensor-reading section for whatever hardware
 * you actually have (vibration sensor, current clamp, etc.) and keep the
 * WiFi + HTTP POST section as-is.
 *
 * HARDWARE (as written): ESP32 dev board + DHT22 temperature/humidity
 * sensor. DHT22 data pin -> GPIO 4 (change DHTPIN below if wired
 * differently). Don't forget the DHT22's pull-up resistor (4.7k-10k
 * between VCC and DATA) if your breakout board doesn't already have one.
 *
 * LIBRARIES NEEDED (Arduino IDE -> Library Manager):
 *   - "DHT sensor library" by Adafruit
 *   - "Adafruit Unified Sensor" (DHT library depends on this)
 *   (WiFi.h and HTTPClient.h ship with the ESP32 board package already)
 *
 * SETUP:
 *   1. In the app: open the machine's page -> enable IoT device -> copy
 *      the device key it gives you (shown once — if you lose it,
 *      re-enabling issues a new one).
 *   2. Fill in WIFI_SSID, WIFI_PASSWORD, API_BASE_URL, and DEVICE_KEY below.
 *   3. Flash this to the ESP32 (Arduino IDE: Tools -> Board -> your ESP32
 *      board, then Sketch -> Upload).
 *   4. Open the Serial Monitor at 115200 baud to watch it connect and post.
 *
 * API_BASE_URL must be reachable from the ESP32's network. If MAINTAIN AI
 * is running on your laptop (not a public server), that means the ESP32
 * needs to be on the SAME WiFi network, and you use your laptop's local
 * IP (e.g., http://192.168.1.42:8000), not "localhost" — the ESP32 has no
 * idea what "localhost" means on your laptop.
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <WebSocketsClient.h>
#include <time.h>
#include <DHT.h>

// ---- Fill these in ----
const char* WIFI_SSID     = "YOUR_WIFI_NAME";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
const char* API_BASE_URL  = "http://192.168.1.42:8000";   // your machine's local IP + port
const char* DEVICE_KEY    = "PASTE_YOUR_DEVICE_KEY_HERE"; // from the app's IoT Device panel

// WebSocket settings. Use the backend host/IP directly; do not use localhost.
const char* WS_HOST = "192.168.1.42";
const uint16_t WS_PORT = 8000;
const char* WS_PATH = "/api/devices/ws";

// ---- Sensor wiring ----
#define DHTPIN 4
#define DHTTYPE DHT22
DHT dht(DHTPIN, DHTTYPE);

// How often to send a reading. Don't go faster than every few seconds —
// there's no need, and it just spams the audit-adjacent alert checks.
const unsigned long SEND_INTERVAL_MS = 30000; // 30 seconds
unsigned long lastSendTime = 0;
WebSocketsClient webSocket;
bool wsConnected = false;

String utcTimestamp() {
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo, 1000)) return "";
  char buf[25];
  strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%SZ", &timeinfo);
  return String(buf);
}

void webSocketEvent(WStype_t type, uint8_t* payload, size_t length) {
  if (type == WStype_CONNECTED) {
    wsConnected = true;
    String auth = String("{\"type\":\"authenticate\",\"device_key\":\"") + DEVICE_KEY + "\"}";
    webSocket.sendTXT(auth);
    Serial.println("Telemetry WebSocket connected — authenticating...");
  } else if (type == WStype_DISCONNECTED) {
    wsConnected = false;
    Serial.println("Telemetry WebSocket disconnected — reconnecting automatically...");
  } else if (type == WStype_TEXT) {
    Serial.printf("WS <- %.*s\n", (int)length, payload);
  }
}

void connectWebSocket() {
  webSocket.begin(WS_HOST, WS_PORT, WS_PATH);
  webSocket.onEvent(webSocketEvent);
  webSocket.setReconnectInterval(5000);
  webSocket.enableHeartbeat(15000, 3000, 2);
}

void connectWiFi() {
  Serial.print("Connecting to WiFi");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  Serial.print("Connected. IP address: ");
  Serial.println(WiFi.localIP());
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");
  Serial.println("Synchronizing UTC clock...");
  struct tm timeinfo;
  getLocalTime(&timeinfo, 10000);
  connectWebSocket();
}

// Sends one reading. Returns true on success (HTTP 2xx).
bool sendReading(const char* readingType, float value, const char* unit) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi dropped — reconnecting before sending...");
    connectWiFi();
  }

  HTTPClient http;
  String url = String(API_BASE_URL) + "/api/devices/ingest";
  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-Key", DEVICE_KEY);

  // Minimal hand-built JSON — fine for three fields; reach for a JSON
  // library instead if you extend this to send more.
  String body = String("{\"reading_type\":\"") + readingType +
                "\",\"value\":" + String(value, 2) +
                ",\"unit\":\"" + unit + "\"}";

  int statusCode = http.POST(body);

  if (statusCode > 0) {
    String response = http.getString();
    Serial.printf("[%s] POST -> HTTP %d: %s\n", readingType, statusCode, response.c_str());
  } else {
    Serial.printf("[%s] POST failed: %s\n", readingType, http.errorToString(statusCode).c_str());
  }

  http.end();
  return statusCode >= 200 && statusCode < 300;
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  dht.begin();
  pinMode(SAFETY_RELAY_PIN, OUTPUT);
  setMachinePower(true);
  connectWiFi();
  lastSendTime = millis() - SEND_INTERVAL_MS;
}

void loop() {
  webSocket.loop();

  unsigned long now = millis();
  if (now - lastSendTime < SEND_INTERVAL_MS) {
    return; // not time yet — keep loop() fast and non-blocking
  }
  lastSendTime = now;

  float temperature = dht.readTemperature(); // Celsius
  float humidity = dht.readHumidity();

  if (isnan(temperature) || isnan(humidity)) {
    Serial.println("Failed to read from DHT22 sensor — check wiring.");
    return;
  }

  Serial.printf("Read: %.1f C, %.1f%% humidity\n", temperature, humidity);

  sendReading("temperature", temperature, "\u00b0C");
  // Humidity isn't one of the app's built-in reading types, but the field
  // is a free-text string server-side, so this works fine — it'll show up
  // in the machine's reading history same as temperature/vibration/current/load.
  sendReading("humidity", humidity, "%");
}

/*
 * SAFETY OUTPUT
 * ------------
 * The backend can send shutdown/shutdown_test commands over the authenticated
 * device WebSocket. This example latches the safety output OFF. Wire the pin
 * to a certified relay/contactor or safety-rated controller appropriate for
 * the machine. The ESP32/GPIO must not be the sole protection for hazardous
 * equipment. The application setting controls whether the backend sends the
 * automatic command; the physical interlock should fail safe independently.
 *
 * ADAPTING THIS FOR OTHER SENSORS
 * --------------------------------
 * Vibration (e.g., ADXL345 accelerometer over I2C):
 *   - Replace the DHT setup/read with the accelerometer library's read
 *     calls, compute a magnitude (sqrt(x*x + y*y + z*z) minus gravity),
 *     and call sendReading("vibration", magnitude, "g").
 *
 * Current (e.g., ACS712 current sensor, analog):
 *   - int raw = analogRead(34); convert raw ADC value to amps per your
 *     sensor's datasheet formula, then
 *     sendReading("current", amps, "A").
 *
 * Whatever the sensor, the only thing that matters to the app is that
 * reading_type is a short string, value is a number, and unit is whatever
 * you want displayed next to it.
 */
