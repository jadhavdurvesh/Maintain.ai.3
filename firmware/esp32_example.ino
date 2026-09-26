/*
 * MAINTAIN AI — ESP32 telemetry + safety interlock example
 *
 * This example is aligned with the current MAINTAIN AI device contract:
 *
 *   Telemetry
 *     POST /api/devices/ingest
 *       X-Device-Key: <device key>
 *       {"reading_type":"temperature","value":31.2,"unit":"C"}
 *
 *   Safety command polling
 *     GET /api/devices/commands
 *       X-Device-Key: <device key>
 *
 *   Command acknowledgement
 *     POST /api/devices/commands/ack
 *       X-Device-Key: <device key>
 *       {"event_id":123}
 *
 *   Optional live WebSocket
 *     /api/devices/ws
 *
 * IMPORTANT SAFETY NOTE
 * ---------------------
 * This is an integration/example firmware, not a certified safety controller.
 * The relay output must drive an appropriately rated isolated interface,
 * contactor, or safety relay. A real machine must also have an independent
 * emergency-stop/interlock chain. Cloud/app commands are supervisory only.
 *
 * The REST command poll is intentionally retained even when WebSocket is
 * enabled. This makes the shutdown path work when telemetry and commands are
 * handled by different serverless instances.
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <WebSocketsClient.h>
#include <time.h>
#include <DHT.h>

// ============================================================
// CONNECTION CONFIGURATION
// ============================================================

const char* WIFI_SSID     = "YOUR_WIFI_NAME";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// Local development example:
//   http://192.168.1.42:8000
// Production example:
//   https://your-api.example.com
const char* API_BASE_URL  = "http://192.168.1.42:8000";
const bool API_USE_TLS    = false;

const char* DEVICE_KEY = "PASTE_YOUR_DEVICE_KEY_HERE";

// WebSocket is optional. REST telemetry + REST command polling remain the
// reliable baseline and should be kept enabled.
const bool ENABLE_WEBSOCKET = true;
const char* WS_HOST = "192.168.1.42";
const uint16_t WS_PORT = 8000;
const char* WS_PATH = "/api/devices/ws";
const bool WS_USE_TLS = false;

// For a real HTTPS deployment, replace setInsecure() with CA validation.
// It is left as an explicit example setting so the firmware does not silently
// pretend that an unverified TLS connection is production-safe.
const bool ALLOW_INSECURE_TLS_FOR_TESTING = true;

// ============================================================
// SENSOR CONFIGURATION
// ============================================================

// DHT22 example sensor.
#define DHTPIN 4
#define DHTTYPE DHT22
DHT dht(DHTPIN, DHTTYPE);

// Optional generic analog current sensor.
// Leave disabled until the actual sensor's calibration is known.
const bool ENABLE_CURRENT_SENSOR = false;
const int CURRENT_SENSOR_PIN = 34;
const float CURRENT_SENSOR_ZERO_V = 1.65f;
const float CURRENT_SENSOR_VOLTS_PER_AMP = 0.066f;

// Optional generic analog vibration sensor.
// Leave disabled until the actual sensor's calibration is known.
const bool ENABLE_VIBRATION_SENSOR = false;
const int VIBRATION_SENSOR_PIN = 35;
const float VIBRATION_ZERO_V = 1.65f;
const float VIBRATION_VOLTS_PER_G = 0.330f;

// Optional load calculation from current. Disabled by default because the
// correct machine-specific mapping must be configured for the real equipment.
const bool ENABLE_LOAD_FROM_CURRENT = false;
const float LOAD_CURRENT_AT_100_PERCENT = 40.0f;

// ============================================================
// SAFETY OUTPUT
// ============================================================

// Adjust this to the GPIO connected to the certified isolated interface.
const int SAFETY_RELAY_PIN = 26;
const bool SAFETY_RELAY_ACTIVE_HIGH = true;

// Keep the example behavior explicit. A real installation should normally
// default to a de-energized/fail-safe state and require a local reset procedure.
const bool START_MACHINE_ON_BOOT = true;

bool machineShutdownLatched = false;
bool wsConnected = false;

// ============================================================
// TIMING
// ============================================================

const unsigned long TELEMETRY_INTERVAL_MS = 5000;
const unsigned long COMMAND_POLL_INTERVAL_MS = 2000;
const unsigned long WIFI_RETRY_INTERVAL_MS = 5000;

unsigned long lastTelemetryTime = 0;
unsigned long lastCommandPollTime = 0;
unsigned long lastWiFiRetryTime = 0;

WebSocketsClient webSocket;
WiFiClient plainClient;
WiFiClientSecure secureClient;

// ============================================================
// BASIC HELPERS
// ============================================================

String utcTimestamp() {
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo, 1000)) return "";

  char buf[25];
  strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%SZ", &timeinfo);
  return String(buf);
}

void setMachinePower(bool on) {
  bool output = SAFETY_RELAY_ACTIVE_HIGH ? on : !on;
  digitalWrite(SAFETY_RELAY_PIN, output ? HIGH : LOW);
}

void latchMachineShutdown(const String& reason) {
  machineShutdownLatched = true;
  setMachinePower(false);

  Serial.println();
  Serial.println("========================================");
  Serial.println("SAFETY SHUTDOWN — OUTPUT LATCHED OFF");
  Serial.println(reason);
  Serial.println("========================================");
}

bool apiReady() {
  return WiFi.status() == WL_CONNECTED && DEVICE_KEY[0] != '\0';
}

String jsonEscape(const String& input) {
  String output = input;
  output.replace("\\", "\\\\");
  output.replace("\"", "\\\"");
  return output;
}

// ============================================================
// SENSOR READERS
// ============================================================

float readCurrentAmps() {
  int raw = analogRead(CURRENT_SENSOR_PIN);
  float volts = ((float)raw / 4095.0f) * 3.3f;
  float amps = (volts - CURRENT_SENSOR_ZERO_V) / CURRENT_SENSOR_VOLTS_PER_AMP;
  return max(0.0f, amps);
}

float readVibrationG() {
  int raw = analogRead(VIBRATION_SENSOR_PIN);
  float volts = ((float)raw / 4095.0f) * 3.3f;
  float g = (volts - VIBRATION_ZERO_V) / VIBRATION_VOLTS_PER_G;
  return abs(g);
}

float readLoadPercent(float currentAmps) {
  if (LOAD_CURRENT_AT_100_PERCENT <= 0.0f) return 0.0f;
  float load = (currentAmps / LOAD_CURRENT_AT_100_PERCENT) * 100.0f;
  return constrain(load, 0.0f, 100.0f);
}

// ============================================================
// TELEMETRY
// ============================================================

bool sendReading(const char* readingType, float value, const char* unit) {
  if (!apiReady()) return false;

  String timestamp = utcTimestamp();
  String body = String("{\"reading_type\":\"") + jsonEscape(String(readingType)) +
                "\",\"value\":" + String(value, 3) +
                ",\"unit\":\"" + jsonEscape(String(unit)) + "\"";

  if (timestamp.length()) {
    body += ",\"recorded_at\":\"" + timestamp + "\"";
  }
  body += "}";

  // Prefer WebSocket for low-latency telemetry when authenticated.
  if (ENABLE_WEBSOCKET && wsConnected) {
    String wsBody = String("{\"type\":\"reading\",\"reading_type\":\"") +
                    jsonEscape(String(readingType)) +
                    "\",\"value\":" + String(value, 3) +
                    ",\"unit\":\"" + jsonEscape(String(unit)) + "\"";
    if (timestamp.length()) {
      wsBody += ",\"recorded_at\":\"" + timestamp + "\"";
    }
    wsBody += "}";
    return webSocket.sendTXT(wsBody);
  }

  HTTPClient http;
  bool started = false;

  if (API_USE_TLS) {
    if (ALLOW_INSECURE_TLS_FOR_TESTING) {
      secureClient.setInsecure();
    }
    started = http.begin(secureClient, String(API_BASE_URL) + "/api/devices/ingest");
  } else {
    started = http.begin(plainClient, String(API_BASE_URL) + "/api/devices/ingest");
  }

  if (!started) {
    Serial.println("Telemetry HTTP begin() failed.");
    return false;
  }

  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-Key", DEVICE_KEY);

  int statusCode = http.POST(body);
  String response = http.getString();
  http.end();

  Serial.printf("Telemetry %-12s %.3f %-3s -> HTTP %d\n",
                readingType, value, unit, statusCode);

  if (statusCode < 200 || statusCode >= 300) {
    if (response.length()) Serial.println(response);
    return false;
  }

  return true;
}

void sendTelemetryCycle() {
  if (!apiReady()) return;

  float temperature = dht.readTemperature();
  float humidity = dht.readHumidity();

  if (isnan(temperature) || isnan(humidity)) {
    Serial.println("DHT22 read failed.");
  } else {
    sendReading("temperature", temperature, "C");
    sendReading("humidity", humidity, "%");
  }

  if (ENABLE_CURRENT_SENSOR) {
    float current = readCurrentAmps();
    sendReading("current", current, "A");

    if (ENABLE_LOAD_FROM_CURRENT) {
      float load = readLoadPercent(current);
      sendReading("load", load, "%");
    }
  }

  if (ENABLE_VIBRATION_SENSOR) {
    float vibration = readVibrationG();
    sendReading("vibration", vibration, "g");
  }
}

// ============================================================
// DURABLE SAFETY COMMAND POLLING
// ============================================================

void acknowledgeCommand(long eventId) {
  if (!apiReady() || eventId <= 0) return;

  HTTPClient http;
  bool started = false;

  if (API_USE_TLS) {
    if (ALLOW_INSECURE_TLS_FOR_TESTING) {
      secureClient.setInsecure();
    }
    started = http.begin(secureClient, String(API_BASE_URL) + "/api/devices/commands/ack");
  } else {
    started = http.begin(plainClient, String(API_BASE_URL) + "/api/devices/commands/ack");
  }

  if (!started) {
    Serial.println("Command ACK HTTP begin() failed.");
    return;
  }

  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-Key", DEVICE_KEY);

  String body = String("{\"event_id\":") + eventId + "}";
  int statusCode = http.POST(body);

  Serial.printf("Safety command ACK event=%ld -> HTTP %d\n", eventId, statusCode);
  http.end();
}

void pollSafetyCommand() {
  if (!apiReady()) return;

  HTTPClient http;
  bool started = false;

  if (API_USE_TLS) {
    if (ALLOW_INSECURE_TLS_FOR_TESTING) {
      secureClient.setInsecure();
    }
    started = http.begin(secureClient, String(API_BASE_URL) + "/api/devices/commands");
  } else {
    started = http.begin(plainClient, String(API_BASE_URL) + "/api/devices/commands");
  }

  if (!started) {
    Serial.println("Command poll HTTP begin() failed.");
    return;
  }

  http.addHeader("X-Device-Key", DEVICE_KEY);
  int statusCode = http.GET();
  String response = http.getString();
  http.end();

  if (statusCode < 200 || statusCode >= 300) {
    Serial.printf("Safety command poll -> HTTP %d\n", statusCode);
    if (response.length()) Serial.println(response);
    return;
  }

  // Current backend response is intentionally simple, so we avoid requiring
  // ArduinoJson just to read the safety command. The event id is extracted
  // from the JSON response and the command type is matched explicitly.
  if (response.indexOf("\"pending\":true") < 0) return;

  bool isShutdown = response.indexOf("\"command_type\":\"shutdown\"") >= 0;
  bool isTest = response.indexOf("\"command_type\":\"shutdown_test\"") >= 0;
  if (!isShutdown && !isTest) return;

  int eventMarker = response.indexOf("\"event_id\":");
  if (eventMarker < 0) {
    latchMachineShutdown("Shutdown command received without an event id.");
    return;
  }

  eventMarker += 11;
  while (eventMarker < (int)response.length() && response[eventMarker] == ' ') {
    eventMarker++;
  }

  int eventEnd = eventMarker;
  while (eventEnd < (int)response.length() && isDigit(response[eventEnd])) {
    eventEnd++;
  }

  long eventId = response.substring(eventMarker, eventEnd).toInt();
  int reasonMarker = response.indexOf("\"reason\":\"");
  String reason = isTest ? "Manual safety shutdown test" : "Automatic safety shutdown command";

  if (reasonMarker >= 0) {
    reasonMarker += 10;
    int reasonEnd = response.indexOf('"', reasonMarker);
    if (reasonEnd > reasonMarker) {
      reason = response.substring(reasonMarker, reasonEnd);
    }
  }

  latchMachineShutdown(reason);
  acknowledgeCommand(eventId);
}

// ============================================================
// OPTIONAL WEBSOCKET
// ============================================================

void handleWebSocketMessage(const String& message) {
  bool isShutdown = message.indexOf("\"type\":\"shutdown\"") >= 0;
  bool isTest = message.indexOf("\"type\":\"shutdown_test\"") >= 0;
  if (!isShutdown && !isTest) return;

  latchMachineShutdown(isTest ?
    "WebSocket manual safety shutdown test" :
    "WebSocket automatic safety shutdown command");

  // The durable REST command endpoint remains authoritative. This ACK is only
  // for the live channel and is not used as the durable database acknowledgement.
  String ackType = isTest ? "shutdown_test_ack" : "shutdown_ack";
  String ack = String("{\"type\":\"") + ackType +
               "\",\"status\":\"latched_off\"}";
  webSocket.sendTXT(ack);
}

void webSocketEvent(WStype_t type, uint8_t* payload, size_t length) {
  if (type == WStype_CONNECTED) {
    wsConnected = true;

    String auth = String("{\"type\":\"authenticate\",\"device_key\":\"") +
                  DEVICE_KEY + "\"}";
    webSocket.sendTXT(auth);
    Serial.println("Telemetry WebSocket connected — authenticating...");
  }
  else if (type == WStype_DISCONNECTED) {
    wsConnected = false;
    Serial.println("Telemetry WebSocket disconnected — REST fallback remains active.");
  }
  else if (type == WStype_TEXT) {
    String message((char*)payload);
    if (length < message.length()) message = message.substring(0, length);
    Serial.printf("WS <- %s\n", message.c_str());
    handleWebSocketMessage(message);
  }
}

void connectWebSocket() {
  if (!ENABLE_WEBSOCKET) return;

  if (WS_USE_TLS) {
    webSocket.beginSSL(WS_HOST, WS_PORT, WS_PATH);
  } else {
    webSocket.begin(WS_HOST, WS_PORT, WS_PATH);
  }

  webSocket.onEvent(webSocketEvent);
  webSocket.setReconnectInterval(5000);
  webSocket.enableHeartbeat(15000, 3000, 2);
}

// ============================================================
// NETWORK
// ============================================================

void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;

  Serial.print("Connecting to WiFi");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  unsigned long startedAt = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - startedAt < 20000) {
    delay(500);
    Serial.print(".");
  }

  Serial.println();

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi connection failed; will retry.");
    return;
  }

  Serial.print("ESP32 IP: ");
  Serial.println(WiFi.localIP());

  configTime(0, 0, "pool.ntp.org", "time.nist.gov");

  struct tm timeinfo;
  if (getLocalTime(&timeinfo, 10000)) {
    Serial.println("Clock synchronized.");
  } else {
    Serial.println("Clock synchronization timed out; telemetry can continue without recorded_at.");
  }

  connectWebSocket();
}

// ============================================================
// SETUP / LOOP
// ============================================================

void setup() {
  Serial.begin(115200);
  delay(1000);

  pinMode(SAFETY_RELAY_PIN, OUTPUT);
  dht.begin();

  if (ENABLE_CURRENT_SENSOR) pinMode(CURRENT_SENSOR_PIN, INPUT);
  if (ENABLE_VIBRATION_SENSOR) pinMode(VIBRATION_SENSOR_PIN, INPUT);

  // Explicit startup state.
  setMachinePower(START_MACHINE_ON_BOOT);
  machineShutdownLatched = !START_MACHINE_ON_BOOT;

  if (machineShutdownLatched) {
    Serial.println("Machine output starts OFF by configuration.");
  }

  connectWiFi();

  lastTelemetryTime = millis() - TELEMETRY_INTERVAL_MS;
  lastCommandPollTime = millis() - COMMAND_POLL_INTERVAL_MS;
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    unsigned long now = millis();
    if (now - lastWiFiRetryTime >= WIFI_RETRY_INTERVAL_MS) {
      lastWiFiRetryTime = now;
      connectWiFi();
    }
    delay(10);
    return;
  }

  if (ENABLE_WEBSOCKET) {
    webSocket.loop();
  }

  unsigned long now = millis();

  // Safety command polling runs independently of telemetry. This is the
  // important durable path for automatic shutdown on serverless deployments.
  if (now - lastCommandPollTime >= COMMAND_POLL_INTERVAL_MS) {
    lastCommandPollTime = now;
    pollSafetyCommand();
  }

  if (!machineShutdownLatched && now - lastTelemetryTime >= TELEMETRY_INTERVAL_MS) {
    lastTelemetryTime = now;
    sendTelemetryCycle();
  }
}
