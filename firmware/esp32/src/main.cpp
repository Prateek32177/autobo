/**
 * Physical AI ESP32 firmware peer — Milestone 2
 *
 * USB Serial @ 115200, JSON Lines protocol v1.0
 * Aligned with contracts/protocol/messages.py and firmware/virtual_esp32.
 *
 * Does NOT call an LLM. Stops motors on host disconnect / timeout.
 */

#include <Arduino.h>
#include <ArduinoJson.h>
#include <string.h>

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
static bool emergency_stopped = false;
static int left_encoder = 0;
static int right_encoder = 0;
static float battery_voltage = 7.4f;
static float distance_cm = 35.0f;
static const char *left_dir = "idle";
static const char *right_dir = "idle";
String line_buf;

bool isSupportedAction(const char *action) {
  return strcmp(action, "move_forward") == 0 || strcmp(action, "move_backward") == 0 ||
         strcmp(action, "turn_left") == 0 || strcmp(action, "turn_right") == 0 ||
         strcmp(action, "stop") == 0 || strcmp(action, "emergency_stop") == 0 ||
         strcmp(action, "read_distance") == 0 || strcmp(action, "read_battery") == 0 ||
         strcmp(action, "read_encoders") == 0;
}

void stopMotors(const char *reason, bool emergency) {
  motors_active = false;
  motor_deadline_ms = 0;
  left_dir = "idle";
  right_dir = "idle";
  if (emergency) {
    emergency_stopped = true;
  }
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
  JsonArray caps = doc["supported_capabilities"].to<JsonArray>();
  const char *actions[] = {
      "move_forward", "move_backward", "turn_left", "turn_right", "stop",
      "emergency_stop", "read_distance", "read_battery", "read_encoders"};
  for (size_t i = 0; i < 9; i++) {
    JsonObject a = caps.add<JsonObject>();
    a["name"] = actions[i];
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
  doc["emergency_stopped"] = emergency_stopped;
  JsonObject motors = doc["motor_status"].to<JsonObject>();
  motors["left"] = left_dir;
  motors["right"] = right_dir;
  sendJson(doc);
}

void sendAck(const char *command_id, const char *status, const char *reason) {
  JsonDocument ack;
  ack["type"] = "command_ack";
  ack["command_id"] = command_id;
  ack["status"] = status;
  if (reason != nullptr) {
    ack["reason"] = reason;
  }
  sendJson(ack);
}

void handleCommand(JsonDocument &doc) {
  const char *command_id = doc["command_id"] | "unknown";
  const char *action = doc["action"] | "";

  if (!isSupportedAction(action)) {
    sendAck(command_id, "rejected", "unsupported action");
    JsonDocument result;
    result["type"] = "command_result";
    result["command_id"] = command_id;
    result["status"] = "failed";
    result["message"] = "unsupported action";
    sendJson(result);
    return;
  }

  if (emergency_stopped &&
      !(strcmp(action, "stop") == 0 || strcmp(action, "emergency_stop") == 0 ||
        strcmp(action, "read_distance") == 0 || strcmp(action, "read_battery") == 0 ||
        strcmp(action, "read_encoders") == 0)) {
    sendAck(command_id, "rejected", "emergency stop latch active");
    JsonDocument result;
    result["type"] = "command_result";
    result["command_id"] = command_id;
    result["status"] = "failed";
    result["message"] = "emergency stop latch active";
    sendJson(result);
    return;
  }

  sendAck(command_id, "accepted", nullptr);

  JsonDocument result;
  result["type"] = "command_result";
  result["command_id"] = command_id;

  if (strcmp(action, "stop") == 0 || strcmp(action, "emergency_stop") == 0) {
    stopMotors(action, strcmp(action, "emergency_stop") == 0);
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

  if (strcmp(action, "read_encoders") == 0) {
    result["status"] = "completed";
    result["left_encoder_delta"] = 0;
    result["right_encoder_delta"] = 0;
    char msg[64];
    snprintf(msg, sizeof(msg), "left=%d,right=%d", left_encoder, right_encoder);
    result["message"] = msg;
    sendJson(result);
    return;
  }

  float speed = doc["parameters"]["speed"] | 0.15f;
  int duration_ms = doc["parameters"]["duration_ms"] | 500;
  if (speed > 0.4f) speed = 0.4f;
  if (duration_ms > 3000) duration_ms = 3000;
  if (duration_ms < 0) duration_ms = 0;

  int ticks = (int)(speed * duration_ms / 10.0f);
  int left_delta = 0;
  int right_delta = 0;

  if (strcmp(action, "move_forward") == 0) {
    left_delta = right_delta = ticks;
    left_dir = "forward";
    right_dir = "forward";
  } else if (strcmp(action, "move_backward") == 0) {
    left_delta = right_delta = -ticks;
    left_dir = "backward";
    right_dir = "backward";
  } else if (strcmp(action, "turn_left") == 0) {
    left_delta = -ticks;
    right_delta = ticks;
    left_dir = "backward";
    right_dir = "forward";
  } else if (strcmp(action, "turn_right") == 0) {
    left_delta = ticks;
    right_delta = -ticks;
    left_dir = "forward";
    right_dir = "backward";
  }

  motors_active = duration_ms > 0;
  motor_deadline_ms = millis() + (unsigned long)duration_ms;
  if ((motor_deadline_ms - millis()) > MOTOR_TIMEOUT_MS) {
    motor_deadline_ms = millis() + MOTOR_TIMEOUT_MS;
  }
  left_encoder += left_delta;
  right_encoder += right_delta;
  result["status"] = "completed";
  result["left_encoder_delta"] = left_delta;
  result["right_encoder_delta"] = right_delta;
  sendJson(result);
}

void handleEmergencyStopMessage(JsonDocument &doc) {
  const char *command_id = doc["command_id"] | nullptr;
  const char *reason = doc["reason"] | "operator";
  stopMotors(reason, true);
  if (command_id != nullptr && strlen(command_id) > 0) {
    sendAck(command_id, "accepted", nullptr);
    JsonDocument result;
    result["type"] = "command_result";
    result["command_id"] = command_id;
    result["status"] = "completed";
    result["left_encoder_delta"] = 0;
    result["right_encoder_delta"] = 0;
    result["message"] = "emergency_stop";
    sendJson(result);
  }
  sendTelemetry();
}

void handleLine(const String &line) {
  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, line);
  if (err) {
    // Malformed messages must NOT refresh the host watchdog.
    JsonDocument error;
    error["type"] = "error";
    error["code"] = "MALFORMED_MESSAGE";
    error["message"] = "Invalid JSON line";
    sendJson(error);
    return;
  }

  // Only valid protocol frames keep the watchdog satisfied.
  last_host_ms = millis();

  const char *type = doc["type"] | "";
  if (strcmp(type, "command") == 0) {
    handleCommand(doc);
  } else if (strcmp(type, "emergency_stop") == 0) {
    handleEmergencyStopMessage(doc);
  } else if (strcmp(type, "handshake_ack") == 0) {
    // Host accepted/rejected protocol version.
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
    stopMotors("motor_timeout", false);
  }
  if (now - last_host_ms > WATCHDOG_MS) {
    stopMotors("watchdog", true);
  }
  if (now - last_heartbeat_ms >= HEARTBEAT_MS) {
    last_heartbeat_ms = now;
    sendHeartbeat();
    sendTelemetry();
  }
}
