/**
 * Physical AI ESP32 firmware peer — Milestone 2
 *
 * USB Serial @ 115200, JSON Lines protocol v1.0
 * - handshake, heartbeat, telemetry
 * - command / command_ack / command_result
 * - emergency_stop + motor command timeout + watchdog
 *
 * Does NOT call an LLM. Stops motors on host disconnect / timeout.
 */

#include <Arduino.h>
#include <ArduinoJson.h>

static const char *DEVICE_ID = "rover-001";
static const char *FIRMWARE_VERSION = "0.2.0";
static const char *PROTOCOL_VERSION = "1.0";
static const unsigned long HEARTBEAT_MS = 1000;
static const unsigned long MOTOR_TIMEOUT_MS = 1500;
static const unsigned long WATCHDOG_MS = 3000;

static unsigned long last_heartbeat_ms = 0;
static unsigned long last_host_ms = 0;
static unsigned long motor_deadline_ms = 0;
static bool motors_active = false;
static int left_encoder = 0;
static int right_encoder = 0;
static float battery_voltage = 7.4f;
static float distance_cm = 35.0f;
String line_buf;

void stopMotors(const char *reason) {
  motors_active = false;
  motor_deadline_ms = 0;
  // Hook motor driver pins here in hardware bring-up.
  (void)reason;
}

void sendJson(const JsonDocument &doc) {
  serializeJson(doc, Serial);
  Serial.println();
}

void sendHandshake() {
  JsonDocument doc;
  doc["type"] = "handshake";
  doc["device_id"] = DEVICE_ID;
  doc["manufacturer"] = "physical-ai";
  doc["board"] = "esp32";
  doc["model"] = "autonomous_rover";
  doc["firmware_version"] = FIRMWARE_VERSION;
  doc["protocol_version"] = PROTOCOL_VERSION;
  JsonArray comps = doc["supported_components"].to<JsonArray>();
  const char *keys[] = {
      "controller", "distance_sensor", "left_motor", "right_motor",
      "left_encoder", "right_encoder", "battery"};
  const char *types[] = {
      "controller", "distance_sensor", "motor", "motor",
      "encoder", "encoder", "battery"};
  for (size_t i = 0; i < 7; i++) {
    JsonObject c = comps.add<JsonObject>();
    c["key"] = keys[i];
    c["component_type"] = types[i];
  }
  sendJson(doc);
}

void sendHeartbeat() {
  JsonDocument doc;
  doc["type"] = "heartbeat";
  doc["device_id"] = DEVICE_ID;
  doc["firmware_version"] = FIRMWARE_VERSION;
  doc["uptime_ms"] = millis();
  doc["protocol_version"] = PROTOCOL_VERSION;
  sendJson(doc);
}

void sendTelemetry() {
  JsonDocument doc;
  doc["type"] = "telemetry";
  doc["device_id"] = DEVICE_ID;
  doc["timestamp_ms"] = millis();
  doc["battery_voltage"] = battery_voltage;
  doc["distance_cm"] = distance_cm;
  doc["left_encoder"] = left_encoder;
  doc["right_encoder"] = right_encoder;
  doc["uptime_ms"] = millis();
  doc["firmware_version"] = FIRMWARE_VERSION;
  JsonObject motors = doc["motor_status"].to<JsonObject>();
  motors["left"] = motors_active ? "forward" : "idle";
  motors["right"] = motors_active ? "forward" : "idle";
  sendJson(doc);
}

void handleCommand(JsonDocument &doc) {
  const char *command_id = doc["command_id"] | "unknown";
  const char *action = doc["action"] | "";

  JsonDocument ack;
  ack["type"] = "command_ack";
  ack["command_id"] = command_id;
  ack["status"] = "accepted";
  sendJson(ack);

  JsonDocument result;
  result["type"] = "command_result";
  result["command_id"] = command_id;

  if (strcmp(action, "stop") == 0 || strcmp(action, "emergency_stop") == 0) {
    stopMotors(action);
    result["status"] = "completed";
    result["left_encoder_delta"] = 0;
    result["right_encoder_delta"] = 0;
    sendJson(result);
    return;
  }

  if (strcmp(action, "read_distance") == 0) {
    result["status"] = "completed";
    result["distance_cm"] = distance_cm;
    sendJson(result);
    return;
  }

  if (strcmp(action, "read_battery") == 0) {
    result["status"] = "completed";
    result["battery_voltage"] = battery_voltage;
    sendJson(result);
    return;
  }

  float speed = doc["parameters"]["speed"] | 0.15f;
  int duration_ms = doc["parameters"]["duration_ms"] | 500;
  if (speed > 0.4f) speed = 0.4f;
  if (duration_ms > 3000) duration_ms = 3000;
  if (duration_ms < 0) duration_ms = 0;

  if (strcmp(action, "move_forward") == 0 || strcmp(action, "move_backward") == 0 ||
      strcmp(action, "turn_left") == 0 || strcmp(action, "turn_right") == 0) {
    motors_active = true;
    motor_deadline_ms = millis() + (unsigned long)duration_ms;
    if (motor_deadline_ms - millis() > MOTOR_TIMEOUT_MS) {
      motor_deadline_ms = millis() + MOTOR_TIMEOUT_MS;
    }
    int delta = (int)(speed * duration_ms / 10.0f);
    if (strcmp(action, "move_backward") == 0) delta = -delta;
    left_encoder += delta;
    right_encoder += delta;
    result["status"] = "completed";
    result["left_encoder_delta"] = delta;
    result["right_encoder_delta"] = delta;
    sendJson(result);
    return;
  }

  result["status"] = "failed";
  result["message"] = "unsupported action";
  sendJson(result);
}

void handleLine(const String &line) {
  last_host_ms = millis();
  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, line);
  if (err) {
    JsonDocument error;
    error["type"] = "error";
    error["code"] = "MALFORMED_MESSAGE";
    error["message"] = "Invalid JSON line";
    sendJson(error);
    return;
  }

  const char *type = doc["type"] | "";
  if (strcmp(type, "command") == 0) {
    handleCommand(doc);
  } else if (strcmp(type, "emergency_stop") == 0) {
    stopMotors("emergency_stop");
  } else if (strcmp(type, "handshake_ack") == 0) {
    // Host accepted/rejected protocol version — nothing else required.
  }
}

void setup() {
  Serial.begin(115200);
  delay(500);
  last_host_ms = millis();
  sendHandshake();
  sendHeartbeat();
  sendTelemetry();
}

void loop() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n') {
      if (line_buf.length() > 0) {
        handleLine(line_buf);
        line_buf = "";
      }
    } else if (c != '\r') {
      line_buf += c;
      if (line_buf.length() > 512) {
        line_buf = "";
      }
    }
  }

  unsigned long now = millis();
  if (motors_active && motor_deadline_ms != 0 && now >= motor_deadline_ms) {
    stopMotors("motor_timeout");
  }
  if (now - last_host_ms > WATCHDOG_MS) {
    stopMotors("watchdog");
  }
  if (now - last_heartbeat_ms >= HEARTBEAT_MS) {
    last_heartbeat_ms = now;
    sendHeartbeat();
    sendTelemetry();
  }
}
