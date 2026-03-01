// ====================【引入必要函式庫】====================
#include <WiFi.h>
#include <AsyncTCP.h>
#include <ESPAsyncWebServer.h>
#include <PubSubClient.h>
#include "credential.h"

// ====================【自訂參數設定區】====================
// const char* ssid = "<YOUR WiFi ssid>";
// const char* password = "<YOUR WiFi password>";
// const char* mqtt_server ="<YOUR MQTT Broker ip>";


//const int relayPin = 26; // Relay接腳 (請根據你的接腳改)
const int relayPin=5; // 測試暫時用亮燈的方式來表示

const char* mqttCommandTopic = "lamp/command"; // MQTT指令 Topic
const char* mqttStatusTopic  = "lamp/status";  // 回報狀態用的 Topic

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
    mqttClient.publish(mqttStatusTopic, "ON");  // 回報狀態
  } else if (message == "OFF") {
    digitalWrite(relayPin, LOW);
    mqttClient.publish(mqttStatusTopic, "OFF"); // 回報狀態
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
    Serial.print("IP地址: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\nWiFi連線失敗，將自動重試");
  }
}

// ====================【MQTT 註冊管理 (Discovery)】====================
void sendDiscoveryMessage() {
  const char* discoveryTopic = "home/discovery";
  
  // 建立註冊 JSON 訊息
  // 注意：這裡使用 String 拼接以減少對 ArduinoJson 的依賴，
  // 但建議生產環境使用 ArduinoJson 以確保格式正確。
  String payload = "{";
  payload += "\"device_id\": \"light_01\",";
  payload += "\"device_type\": \"relay\",";
  payload += "\"aliases\": [\"燈\", \"電燈\", \"燈光\", \"lights\", \"light\"],";
  payload += "\"control_topic\": \"" + String(mqttCommandTopic) + "\",";
  payload += "\"commands\": {";
  payload += "  \"on\": \"ON\",";
  payload += "  \"off\": \"OFF\"";
  payload += " }";
  payload += "}";

  Serial.println("發送 Discovery 註冊訊息...");
  if (mqttClient.publish(discoveryTopic, payload.c_str())) {
    Serial.println("Discovery 註冊成功！✅");
  } else {
    Serial.println("Discovery 註冊失敗！❌");
  }
}

// ====================【MQTT連線管理】====================
void connectToMQTT() {
  if (!mqttClient.connected()) {
    Serial.print("正在連接MQTT...");
    String clientId = "ESP32-SmartLight-" + String(random(0xffff), HEX);
    
    if (mqttClient.connect(clientId.c_str(),mqtt_user,mqtt_password)) {
      Serial.println("MQTT連線成功！");
      
      // 連線成功後立即執行註冊與訂閱
      sendDiscoveryMessage();
      mqttClient.subscribe(mqttCommandTopic); // 訂閱指令Topic
    } else {
      Serial.print("MQTT連線失敗, rc=");
      Serial.println(mqttClient.state());
      delay(5000); // 失敗後延遲再重試
    }
  }
}

// ====================【HTTP控制介面】====================
void setupHttpServer() {
  server.on("/on", HTTP_GET, [](AsyncWebServerRequest *request){
    digitalWrite(relayPin, HIGH);
    mqttClient.publish(mqttStatusTopic, "ON");
    request->send(200, "text/plain", "燈已開啟");
  });
  
  server.on("/off", HTTP_GET, [](AsyncWebServerRequest *request){
    digitalWrite(relayPin, LOW);
    mqttClient.publish(mqttStatusTopic, "OFF");
    request->send(200, "text/plain", "燈已關閉");
  });
  
  server.begin();
  Serial.println("HTTP Server啟動完成！");
}

// ====================【主程式入口 setup()】====================
void setup() {
  Serial.begin(115200);
  
  pinMode(relayPin, OUTPUT);
  digitalWrite(relayPin, LOW); // 開機預設關閉燈

  connectToWiFi();

  mqttClient.setServer(mqtt_server, 1883);
  mqttClient.setCallback(mqttCallback);

  setupHttpServer();

  // WiFi低功耗模式
  WiFi.setSleep(true);
}

// ====================【主迴圈 loop()】====================
void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    connectToWiFi();
  }
  delay(10);
  if (!mqttClient.connected()) {
    connectToMQTT();
  }

  mqttClient.loop(); // MQTT一定要呼叫這個來保持連線
}
