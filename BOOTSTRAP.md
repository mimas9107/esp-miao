
# Project Bootstrap Point

本專案工程切入點定義為：

> **ESP32 能穩定從 I2S 麥克風取得 PCM → 丟進 esp-sr → 正確觸發 WakeNet 與 MultiNet。**

在此之前，不要實作 Server、LLM、WebSocket、Relay、TTS。

先讓語音神經反射成功，後面模組才有意義。

---

## Future Extensions

* Multi device ESP32
* Home Assistant bridge
* MQTT integration
* Interrupt speech
* Context memory

---

# Code Skeleton

## ESP-IDF + esp-sr Skeleton

```c
// main.c
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "nvs_flash.h"
#include "driver/i2s.h"
#include "esp_sr_iface.h"
#include "esp_sr_models.h"
#include "esp_wn_iface.h"
#include "esp_mn_iface.h"

static const char *TAG = "voice_agent";

void app_main(void)
{
    nvs_flash_init();
    ESP_LOGI(TAG, "Init voice agent");

    // Init I2S mic here
    // init_i2s();

    // Load models
    srmodel_list_t *models = esp_srmodel_init("model");

    const esp_wn_iface_t *wakenet = esp_wn_handle_from_name(models, "wn9_hiesp");
    const esp_mn_iface_t *multinet = esp_mn_handle_from_name(models, "mn6_cn");

    void *wn_handle = wakenet->create(models, 16000);
    void *mn_handle = multinet->create(models, 16000);

    int16_t audio_buff[512];

    while (1) {
        // read mic pcm to audio_buff
        // i2s_read(...)

        if (wakenet->detect(wn_handle, audio_buff)) {
            ESP_LOGI(TAG, "Wake detected");
        }

        int cmd = multinet->detect(mn_handle, audio_buff);
        if (cmd >= 0) {
            ESP_LOGI(TAG, "Command id: %d", cmd);
            // map and execute or forward
        }
    }
}
```

---

## Server FastAPI Skeleton

```python
# server.py
from fastapi import FastAPI, WebSocket
import json
import ollama

app = FastAPI()

device_table = {
    "light": {"type": "relay", "gpio": 26}
}

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    while True:
        msg = await ws.receive_text()
        data = json.loads(msg)

        if data["type"] == "text_command":
            text = data["text"]
            intent = parse_intent(text)
            await ws.send_text(json.dumps(intent))


def parse_intent(text: str):
    prompt = f"""
    Device table: {device_table}
    Convert command to json: {text}
    """
    res = ollama.generate(model="qwen2.5", prompt=prompt)
    return json.loads(res["response"])
```
