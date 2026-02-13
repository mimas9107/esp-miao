#include <ESP_I2S.h>
#include <wav_header.h>

/*
 * ESP-MIAO: ESP32 WebSocket Client for Arduino IDE
 * 
 * 這個程式用於測試 ESP32 Dev Kit v1 與 Server 的 WebSocket 通訊。
 * 實作了 SPEC.md 定義的 JSON Protocol 和 State Machine。
 * 
 * 硬體需求:
 *   - ESP32 Dev Kit v1
 *   - LED on GPIO 2 (內建)
 *   - Relay on GPIO 26 (light)
 *   - Relay on GPIO 27 (fan)
 * 
 * Arduino IDE 設定:
 *   1. 安裝 ESP32 Board: https://github.com/espressif/arduino-esp32
 *   2. 安裝 ArduinoJson: Library Manager -> ArduinoJson
 *   3. 安裝 WebSockets: Library Manager -> WebSockets by Markus Sattler
 *   4. Board: ESP32 Dev Module
 *   5. Upload Speed: 115200
 * 
 * 使用方式:
 *   1. 修改下方的 WiFi 和 Server 設定
 *   2. 上傳到 ESP32
 *   3. 開啟 Serial Monitor (115200 baud)
 *   4. 輸入指令測試 (見下方說明)
 * 
 * Serial 指令:
 *   0-3: 發送本地指令 (0=LIGHT_ON, 1=LIGHT_OFF, 2=FAN_ON, 3=FAN_OFF)
 *   t:文字: 發送 fallback 文字請求 (例如: t:打開電風扇)
 *   s: 顯示目前狀態
 *   r: 重新連線
 */

#include <WiFi.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>

// ==================== 設定區 ====================

// WiFi 設定
const char* WIFI_SSID = "YOUR_WIFI_SSID";      // <-- 修改這裡
const char* WIFI_PASS = "YOUR_WIFI_PASSWORD";  // <-- 修改這裡

// Server 設定
const char* SERVER_HOST = "192.168.1.103";     // <-- 修改為你的 Server IP
const int SERVER_PORT = 8000;
const char* DEVICE_ID = "esp32_01R";

// GPIO 設定
const int PIN_LED = 2;      // 內建 LED
const int PIN_LIGHT = 26;   // Relay: light
const int PIN_FAN = 27;     // Relay: fan

// ==================== 狀態機定義 ====================

enum State {
  STATE_IDLE,
  STATE_WAKE,
  STATE_LISTEN,
  STATE_RECOGNIZE,
  STATE_LOCAL_EXECUTE,
  STATE_FORWARD_SERVER,
  STATE_WAIT_ACTION,
  STATE_PLAY_FEEDBACK,
  STATE_ERROR
};

const char* stateNames[] = {
  "IDLE", "WAKE", "LISTEN", "RECOGNIZE", 
  "LOCAL_EXECUTE", "FORWARD_SERVER", "WAIT_ACTION", 
  "PLAY_FEEDBACK", "ERROR"
};

// 指令對應表
const char* COMMANDS[][3] = {
  {"LIGHT_ON", "light", "on"},   // cmd_id = 0
  {"LIGHT_OFF", "light", "off"}, // cmd_id = 1
  {"FAN_ON", "fan", "on"},       // cmd_id = 2
  {"FAN_OFF", "fan", "off"}      // cmd_id = 3
};
const int NUM_COMMANDS = 4;

// ==================== 全域變數 ====================

WebSocketsClient webSocket;
State currentState = STATE_IDLE;
bool isConnected = false;
unsigned long lastHeartbeat = 0;

// ==================== 工具函數 ====================

void setState(State newState) {
  Serial.printf("[STATE] %s -> %s\n", stateNames[currentState], stateNames[newState]);
  currentState = newState;
}

unsigned long getTimestamp() {
  return millis();
}

// ==================== GPIO 控制 ====================

void setupGPIO() {
  pinMode(PIN_LED, OUTPUT);
  pinMode(PIN_LIGHT, OUTPUT);
  pinMode(PIN_FAN, OUTPUT);
  
  // 初始狀態: 全部關閉
  digitalWrite(PIN_LED, LOW);
  digitalWrite(PIN_LIGHT, LOW);
  digitalWrite(PIN_FAN, LOW);
  
  Serial.println("[GPIO] Initialized: LED=2, LIGHT=26, FAN=27");
}

void setRelay(const char* target, const char* value) {
  int pin = -1;
  
  if (strcmp(target, "light") == 0) {
    pin = PIN_LIGHT;
  } else if (strcmp(target, "fan") == 0) {
    pin = PIN_FAN;
  } else if (strcmp(target, "led") == 0) {
    pin = PIN_LED;
  }
  
  if (pin >= 0) {
    bool state = (strcmp(value, "on") == 0);
    digitalWrite(pin, state ? HIGH : LOW);
    Serial.printf("[RELAY] %s -> %s (GPIO %d = %s)\n", 
                  target, value, pin, state ? "HIGH" : "LOW");
  } else {
    Serial.printf("[ERROR] Unknown target: %s\n", target);
  }
}

void playSound(const char* filename) {
  // 模擬播放音效 (實際實作需要 I2S DAC)
  Serial.printf("[SOUND] Playing: %s\n", filename);
  
  // LED 閃爍表示播放中
  for (int i = 0; i < 3; i++) {
    digitalWrite(PIN_LED, HIGH);
    delay(100);
    digitalWrite(PIN_LED, LOW);
    delay(100);
  }
}

// ==================== JSON 訊息建構 ====================

String buildCommandRequest(int cmdId, float confidence) {
  StaticJsonDocument<256> doc;
  
  doc["type"] = "command_request";
  doc["device_id"] = DEVICE_ID;
  doc["timestamp"] = getTimestamp();
  
  JsonObject payload = doc.createNestedObject("payload");
  payload["source"] = "esp-sr";
  payload["cmd_id"] = cmdId;
  payload["cmd_name"] = COMMANDS[cmdId][0];
  payload["confidence"] = confidence;
  
  String output;
  serializeJson(doc, output);
  return output;
}

String buildFallbackRequest(const char* text) {
  StaticJsonDocument<256> doc;
  
  doc["type"] = "fallback_request";
  doc["device_id"] = DEVICE_ID;
  doc["timestamp"] = getTimestamp();
  
  JsonObject payload = doc.createNestedObject("payload");
  payload["text"] = text;
  
  String output;
  serializeJson(doc, output);
  return output;
}

String buildActionResult(bool success, const char* error = nullptr) {
  StaticJsonDocument<256> doc;
  
  doc["type"] = "action_result";
  doc["device_id"] = DEVICE_ID;
  doc["timestamp"] = getTimestamp();
  
  JsonObject payload = doc.createNestedObject("payload");
  payload["status"] = success ? "success" : "failure";
  if (error) {
    payload["error"] = error;
  }
  
  String output;
  serializeJson(doc, output);
  return output;
}

// ==================== 訊息處理 ====================

void handleServerMessage(uint8_t* payload, size_t length) {
  StaticJsonDocument<512> doc;
  DeserializationError error = deserializeJson(doc, payload, length);
  
  if (error) {
    Serial.printf("[ERROR] JSON parse failed: %s\n", error.c_str());
    return;
  }
  
  const char* type = doc["type"];
  Serial.printf("[RECV] type=%s\n", type);
  
  if (strcmp(type, "action") == 0) {
    // 處理 action 指令
    setState(STATE_LOCAL_EXECUTE);
    
    const char* action = doc["payload"]["action"];
    const char* target = doc["payload"]["target"];
    const char* value = doc["payload"]["value"];
    const char* sound = doc["payload"]["sound"];
    
    Serial.printf("[ACTION] %s(%s=%s)\n", action, target, value);
    
    bool success = true;
    
    if (strcmp(action, "relay_set") == 0 || strcmp(action, "led_set") == 0) {
      setRelay(target, value);
    } else if (strcmp(action, "noop") == 0) {
      Serial.println("[NOOP] No operation");
    } else {
      Serial.printf("[ERROR] Unknown action: %s\n", action);
      success = false;
    }
    
    // 播放音效
    if (sound && strlen(sound) > 0) {
      setState(STATE_PLAY_FEEDBACK);
      playSound(sound);
    }
    
    // 發送結果
    String result = buildActionResult(success);
    Serial.printf("[SEND] %s\n", result.c_str());
    webSocket.sendTXT(result);
    
    setState(STATE_IDLE);
    
  } else if (strcmp(type, "play") == 0) {
    // 處理 play 指令
    setState(STATE_PLAY_FEEDBACK);
    
    const char* audio = doc["payload"]["audio"];
    playSound(audio);
    
    setState(STATE_IDLE);
    
  } else {
    Serial.printf("[WARN] Unknown message type: %s\n", type);
  }
}

// ==================== WebSocket 事件 ====================

void webSocketEvent(WStype_t type, uint8_t* payload, size_t length) {
  switch (type) {
    case WStype_DISCONNECTED:
      Serial.println("[WS] Disconnected");
      isConnected = false;
      setState(STATE_ERROR);
      break;
      
    case WStype_CONNECTED:
      Serial.printf("[WS] Connected to %s\n", (char*)payload);
      isConnected = true;
      setState(STATE_IDLE);
      break;
      
    case WStype_TEXT:
      Serial.printf("[WS] Received: %s\n", (char*)payload);
      handleServerMessage(payload, length);
      break;
      
    case WStype_ERROR:
      Serial.println("[WS] Error");
      setState(STATE_ERROR);
      break;
      
    default:
      break;
  }
}

// ==================== 指令發送 ====================

void sendCommandRequest(int cmdId) {
  if (!isConnected) {
    Serial.println("[ERROR] Not connected to server");
    return;
  }
  
  if (cmdId < 0 || cmdId >= NUM_COMMANDS) {
    Serial.printf("[ERROR] Invalid command ID: %d\n", cmdId);
    return;
  }
  
  setState(STATE_WAKE);
  Serial.println("[WAKE] Simulated wake word detected");
  delay(200);
  
  setState(STATE_RECOGNIZE);
  Serial.printf("[RECOGNIZE] Local command: %s\n", COMMANDS[cmdId][0]);
  delay(200);
  
  setState(STATE_FORWARD_SERVER);
  String msg = buildCommandRequest(cmdId, 0.95);
  Serial.printf("[SEND] %s\n", msg.c_str());
  webSocket.sendTXT(msg);
  
  setState(STATE_WAIT_ACTION);
}

void sendFallbackRequest(const char* text) {
  if (!isConnected) {
    Serial.println("[ERROR] Not connected to server");
    return;
  }
  
  setState(STATE_WAKE);
  Serial.println("[WAKE] Simulated wake word detected");
  delay(200);
  
  setState(STATE_RECOGNIZE);
  Serial.printf("[RECOGNIZE] Fallback text: %s\n", text);
  delay(200);
  
  setState(STATE_FORWARD_SERVER);
  String msg = buildFallbackRequest(text);
  Serial.printf("[SEND] %s\n", msg.c_str());
  webSocket.sendTXT(msg);
  
  setState(STATE_WAIT_ACTION);
}

// ==================== Serial 指令處理 ====================

void processSerialCommand() {
  if (!Serial.available()) return;
  
  String input = Serial.readStringUntil('\n');
  input.trim();
  
  if (input.length() == 0) return;
  
  Serial.printf("\n> %s\n", input.c_str());
  
  // 單一數字: 本地指令
  if (input.length() == 1 && input[0] >= '0' && input[0] <= '3') {
    int cmdId = input[0] - '0';
    sendCommandRequest(cmdId);
    return;
  }
  
  // t:文字: fallback 請求
  if (input.startsWith("t:")) {
    String text = input.substring(2);
    text.trim();
    if (text.length() > 0) {
      sendFallbackRequest(text.c_str());
    } else {
      Serial.println("[ERROR] Please provide text after 't:'");
    }
    return;
  }
  
  // s: 顯示狀態
  if (input == "s") {
    Serial.println("\n=== Status ===");
    Serial.printf("State: %s\n", stateNames[currentState]);
    Serial.printf("Connected: %s\n", isConnected ? "Yes" : "No");
    Serial.printf("Server: %s:%d\n", SERVER_HOST, SERVER_PORT);
    Serial.printf("Device ID: %s\n", DEVICE_ID);
    Serial.printf("Uptime: %lu ms\n", millis());
    Serial.println("==============\n");
    return;
  }
  
  // r: 重新連線
  if (input == "r") {
    Serial.println("[WS] Reconnecting...");
    webSocket.disconnect();
    delay(500);
    webSocket.begin(SERVER_HOST, SERVER_PORT, String("/ws/") + DEVICE_ID);
    return;
  }
  
  // h: 說明
  if (input == "h") {
    Serial.println("\n=== Commands ===");
    Serial.println("0: LIGHT_ON");
    Serial.println("1: LIGHT_OFF");
    Serial.println("2: FAN_ON");
    Serial.println("3: FAN_OFF");
    Serial.println("t:文字: Fallback request (e.g., t:打開電風扇)");
    Serial.println("s: Show status");
    Serial.println("r: Reconnect");
    Serial.println("h: Help");
    Serial.println("================\n");
    return;
  }
  
  Serial.println("[ERROR] Unknown command. Type 'h' for help.");
}

// ==================== WiFi 連線 ====================

void setupWiFi() {
  Serial.printf("[WiFi] Connecting to %s", WIFI_SSID);
  
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println(" Connected!");
    Serial.printf("[WiFi] IP: %s\n", WiFi.localIP().toString().c_str());
  } else {
    Serial.println(" Failed!");
    Serial.println("[ERROR] WiFi connection failed. Check credentials.");
  }
}

// ==================== Setup & Loop ====================

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n");
  Serial.println("========================================");
  Serial.println("  ESP-MIAO: ESP32 WebSocket Client");
  Serial.println("  Version: 0.1.0");
  Serial.println("========================================");
  Serial.println();
  
  // 初始化 GPIO
  setupGPIO();
  
  // 連接 WiFi
  setupWiFi();
  
  if (WiFi.status() == WL_CONNECTED) {
    // 連接 WebSocket
    Serial.printf("[WS] Connecting to ws://%s:%d/ws/%s\n", 
                  SERVER_HOST, SERVER_PORT, DEVICE_ID);
    
    webSocket.begin(SERVER_HOST, SERVER_PORT, String("/ws/") + DEVICE_ID);
    webSocket.onEvent(webSocketEvent);
    webSocket.setReconnectInterval(5000);
  }
  
  Serial.println("\nType 'h' for help.\n");
}

void loop() {
  webSocket.loop();
  processSerialCommand();
  
  // 心跳 (可選)
  if (isConnected && millis() - lastHeartbeat > 30000) {
    lastHeartbeat = millis();
    // Serial.println("[HEARTBEAT]");
  }
}
