/*
 * MAINTAIN AI — ESP32 telemetry + safety interlock example
 *
 * Telemetry:
 *   ESP32 -> authenticated MAINTAIN AI WebSocket -> live machine monitoring.
 *
 * Safety:
 *   MAINTAIN AI can send shutdown/shutdown_test commands over the same
 *   authenticated device channel. This example latches a relay-control output
 *   OFF. The GPIO must drive an appropriate isolated, safety-rated interface;
 *   never connect it directly to mains or hazardous equipment.
 *
 * For real machinery, use a properly engineered contactor/safety relay and
 * independent emergency-stop/interlock chain. The cloud/app command is a
 * supervisory layer, not the sole protective mechanism.
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <WebSocketsClient.h>
#include <time.h>
#include <DHT.h>

const char* WIFI_SSID     = "YOUR_WIFI_NAME";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
const char* API_BASE_URL  = "http://192.168.1.42:8000";
const char* DEVICE_KEY    = "PASTE_YOUR_DEVICE_KEY_HERE";

const char* WS_HOST = "192.168.1.42";
const uint16_t WS_PORT = 8000;
const char* WS_PATH = "/api/devices/ws";

// DHT22 example sensor.
#define DHTPIN 4
#define DHTTYPE DHT22
DHT dht(DHTPIN, DHTTYPE);

// Safety relay/contactor control interface.
// Adjust pin and polarity to the actual certified interface.
const int SAFETY_RELAY_PIN = 26;
const bool SAFETY_RELAY_ACTIVE_HIGH = true;
bool machineShutdownLatched = false;

const unsigned long SEND_INTERVAL_MS = 30000;
unsigned long lastSendTime = 0;

WebSocketsClient webSocket;
bool wsConnected = false;

void setMachinePower(bool on) {
  bool output = SAFETY_RELAY_ACTIVE_HIGH ? on : !on;
  digitalWrite(SAFETY_RELAY_PIN, output ? HIGH : LOW);
}

String utcTimestamp() {
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo, 1000)) return "";
  char buf[25];
  strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%SZ", &timeinfo);
  return String(buf);
}

void handleSafetyCommand(const String& message) {
  const bool isShutdown = message.indexOf(""type":"shutdown"") >= 0;
  const bool isTest = message.indexOf(""type":"shutdown_test"") >= 0;
  if (!isShutdown && !isTest) return;

  machineShutdownLatched = true;
  setMachinePower(false);
  Serial.println("SAFETY: shutdown output latched OFF");

  String ackType = isTest ? "shutdown_test_ack" : "shutdown_ack";
  String ack = String("{"type":"") + ackType +
               "","status":"latched_off"}";
  webSocket.sendTXT(ack);
}

void webSocketEvent(WStype_t type, uint8_t* payload, size_t length) {
  if (type == WStype_CONNECTED) {
    wsConnected = true;
    String auth = String("{"type":"authenticate","device_key":"") +
                  DEVICE_KEY + ""}";
    webSocket.sendTXT(auth);
    Serial.println("Telemetry WebSocket connected — authenticating...");
  } else if (type == WStype_DISCONNECTED) {
    wsConnected = false;
    Serial.println("Telemetry WebSocket disconnected — reconnecting...");
  } else if (type == WStype_TEXT) {
    String message((char*)payload);
    if (length < message.length()) message = message.substring(0, length);
    Serial.printf("WS <- %s\n", message.c_str());
    handleSafetyCommand(message);
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
  Serial.print("ESP32 IP: ");
  Serial.println(WiFi.localIP());

  configTime(0, 0, "pool.ntp.org", "time.nist.gov");
  struct tm timeinfo;
  getLocalTime(&timeinfo, 10000);
  connectWebSocket();
}

bool sendReading(const char* readingType, float value, const char* unit) {
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
  }

  String timestamp = utcTimestamp();
  String body = String("{"type":"reading","reading_type":"") +
                readingType + "","value":" + String(value, 2) +
                ","unit":"" + unit + """ +
                (timestamp.length() ? String(","recorded_at":"") +
                 timestamp + """ : "") + "}";

  if (wsConnected) {
    webSocket.sendTXT(body);
    return true;
  }

  HTTPClient http;
  String url = String(API_BASE_URL) + "/api/devices/ingest";
  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-Key", DEVICE_KEY);
  String httpBody = String("{"reading_type":"") + readingType +
                    "","value":" + String(value, 2) +
                    ","unit":"" + unit + """ +
                    (timestamp.length() ? String(","recorded_at":"") +
                     timestamp + """ : "") + "}";
  int statusCode = http.POST(httpBody);
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
  if (now - lastSendTime < SEND_INTERVAL_MS) return;
  lastSendTime = now;

  float temperature = dht.readTemperature();
  float humidity = dht.readHumidity();

  if (isnan(temperature) || isnan(humidity)) {
    Serial.println("DHT22 read failed.");
    return;
  }

  sendReading("temperature", temperature, "C");
  sendReading("humidity", humidity, "%");
}
