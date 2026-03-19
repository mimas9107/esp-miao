// ====================【引入必要函式庫】====================
#include <WiFi.h>
#include <AsyncTCP.h>
#include <ESPAsyncWebServer.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include "credential.h"

// ====================【自訂參數設定區】====================
const int relayPin = 5; 

const char* mqttCommandTopic = "lamp/command";
const char* mqttStatusTopic  = "home/light_01/status"; // 僅用於 Availability (LWT)
const char* mqttStateTopic   = "home/light_01/state";  // 用於功能狀態回報 (State)

// ====================【系統變數】====================
WiFiClient espClient;
PubSubClient mqttClient(espClient);
AsyncWebServer server(80);

// ====================【MQTT訊息處理】====================
void mqttCallback(char* topic, byte* payload, unsigned int length) {
  String message;
  for (unsigned int i = 0; i < length; i++) {
    message += (char)payload[i];
  }
  Serial.printf("收到MQTT訊息 [%s]: %s\n", topic, message.c_str());

  if (message == "ON") {
    digitalWrite(relayPin, HIGH);
    // 使用新的 state 欄位發送到 /state 主題，這比 status 合理多了
    mqttClient.publish(mqttStateTopic, "{\"state\":\"ON\",\"device_id\":\"light_01\"}");
  } else if (message == "OFF") {
    digitalWrite(relayPin, LOW);
    mqttClient.publish(mqttStateTopic, "{\"state\":\"OFF\",\"device_id\":\"light_01\"}");
  }
}

// ====================【WiFi連線管理】====================
void connectToWiFi() {
  Serial.println("正在連接WiFi...");
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  
  int retry = 0;
  while (WiFi.status() != WL_CONNECTED && retry < 20) {
    delay(500);
    Serial.print(".");
    retry++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi連線成功！");
    // 徹底禁用 WiFi 所有省電功能
    WiFi.setSleep(WIFI_PS_NONE);
  }
}

// ====================【MQTT 註冊管理 (Discovery)】====================
void sendDiscoveryMessage() {
  const char* discoveryTopic = "home/discovery";
  StaticJsonDocument<1024> doc;
  doc["device_id"] = "light_01";
  doc["device_type"] = "relay";
  
  JsonArray aliases = doc.createNestedArray("aliases");
  aliases.add("燈"); aliases.add("電燈"); aliases.add("燈光"); aliases.add("light");
  
  doc["control_topic"] = mqttCommandTopic;
  
  JsonObject commands = doc.createNestedObject("commands");
  commands["on"] = "ON";
  commands["off"] = "OFF";

  JsonObject action_keywords = doc.createNestedObject("action_keywords");
  JsonArray kw_on = action_keywords.createNestedArray("on");
  kw_on.add("開"); kw_on.add("打開"); kw_on.add("開啟");
  
  JsonArray kw_off = action_keywords.createNestedArray("off");
  kw_off.add("關"); kw_off.add("關閉"); kw_off.add("關掉");

  String payload;
  serializeJson(doc, payload);
  mqttClient.publish(discoveryTopic, payload.c_str(), true);
}

// ====================【MQTT連線管理】====================
void connectToMQTT() {
  if (!mqttClient.connected()) {
    Serial.print("正在連接MQTT...");
    // 固定使用 MAC 地址，防止踢線
    String clientId = "ESP32-Light-" + WiFi.macAddress();
    
    // 設定 LWT (最後遺言)，這才是真正的 status 意義：代表離線
    String lwtPayload = "{\"status\":\"offline\",\"device_id\":\"light_01\"}";
    
    if (mqttClient.connect(clientId.c_str(), mqtt_user, mqtt_password, 
                          mqttStatusTopic, 1, true, lwtPayload.c_str())) {
      Serial.println("MQTT連線成功！");
      // 回報在線
      mqttClient.publish(mqttStatusTopic, "{\"status\":\"online\",\"device_id\":\"light_01\"}", true);
      sendDiscoveryMessage();
      mqttClient.subscribe(mqttCommandTopic);
    } else {
      delay(5000);
    }
  }
}

void setupHttpServer() {
  server.on("/on", HTTP_GET, [](AsyncWebServerRequest *request){
    digitalWrite(relayPin, HIGH);
    mqttClient.publish(mqttStateTopic, "{\"state\":\"ON\",\"device_id\":\"light_01\"}");
    request->send(200, "text/plain", "燈已開啟");
  });
  server.on("/off", HTTP_GET, [](AsyncWebServerRequest *request){
    digitalWrite(relayPin, LOW);
    mqttClient.publish(mqttStateTopic, "{\"state\":\"OFF\",\"device_id\":\"light_01\"}");
    request->send(200, "text/plain", "燈已關閉");
  });
  server.begin();
}

void setup() {
  Serial.begin(115200);
  pinMode(relayPin, OUTPUT);
  digitalWrite(relayPin, LOW);
  connectToWiFi();
  mqttClient.setServer(mqtt_server, 1883);
  mqttClient.setBufferSize(1024);
  mqttClient.setCallback(mqttCallback);
  // 放寬 Keep-Alive 到 60 秒，有效避免 30 秒自動斷線
  mqttClient.setKeepAlive(60); 
  setupHttpServer();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    connectToWiFi();
    WiFi.setSleep(WIFI_PS_NONE);
  }
  if (!mqttClient.connected()) {
    connectToMQTT();
  }
  mqttClient.loop();
}
