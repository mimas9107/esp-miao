# 技術筆記：ESP32 韌體重構

> 日期：2026-03-17

## 1. ESP-IDF 類別建立注意事項

### 1.1 標頭檔保護
```c
#ifndef CLASS_NAME_H
#define CLASS_NAME_H
// ...
#endif
```

### 1.2 ESP-IDF 日誌使用
```c
#include "esp_log.h"
static const char *TAG = "ClassName";

ESP_LOGI(TAG, "Message");
ESP_LOGE(TAG, "Error: %s", esp_err_to_name(err));
```

### 1.3 條件編譯 Debug 等級
```c
// config.h
#define LOG_LEVEL_NONE   0
#define LOG_LEVEL_ERROR  1
#define LOG_LEVEL_INFO   2
#define LOG_LEVEL_DEBUG  3

#ifndef CLASS_LOG_LEVEL
#define CLASS_LOG_LEVEL LOG_LEVEL_INFO
#endif

// 使用
#if CLASS_LOG_LEVEL >= LOG_LEVEL_DEBUG
    ESP_LOGD(TAG, "Debug info");
#endif
```

## 2. FreeRTOS 整合

### 2.1 Task 建立
```cpp
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

xTaskCreate(task_function, "task_name", stack_size, NULL, priority, NULL);
```

### 2.2 Queue 通訊
- 現有 `ui_state` component 使用 FreeRTOS Queue
- 維持現狀，不重構

## 3. Edge Impulse SDK

### 3.1 需引入的標頭
```c
#include "edge-impulse-sdk/classifier/ei_run_classifier.h"
```

### 3.2 連續推論
```c
run_classifier_init();
run_classifier_continuous(&signal, &result, false);
```

## 4. WebSocket Client

### 4.1 事件處理回調
```c
esp_websocket_register_events(ws_client, WEBSOCKET_EVENT_ANY, 
    websocket_event_handler, (void *)ws_client);
```

### 4.2 發送資料
```c
esp_websocket_client_send_text(ws_client, data, len, portMAX_DELAY);
esp_websocket_client_send_bin(ws_client, data, len, portMAX_DELAY);
```

## 5. I2S 標準驅動（ESP-IDF 5.x）

### 5.1 初始化順序
1. `i2s_new_channel()` - 建立通道
2. `i2s_channel_init_std_mode()` - 初始化標準模式
3. `i2s_channel_enable()` - 啟用通道

### 5.2 Stereo → Mono 軟體提取
- I2S 設定為 Stereo Mode
- 程式碼中只取左聲道（index 0, 2, 4...）

## 6. NVS 使用

### 6.1 開啟 partition
```c
nvs_handle_t nvs_handle;
nvs_open("storage", NVS_READWRITE, &nvs_handle);
```

### 6.2 讀寫字串
```c
nvs_get_str(nvs_handle, "key", buffer, &size);
nvs_set_str(nvs_handle, "key", value);
nvs_commit(nvs_handle);
```

## 7. C++ 與 C 混用

### 7.1 extern "C" 標記
```cpp
extern "C" {
    void c_function();
}
```

### 7.2 類別成員函式指標（Edge Impulse callback）
```c
// 需要 static 或全域函式，無法直接用成員函式
static int ei_audio_signal_get_data(size_t offset, size_t length, float *out_ptr);
```

## 8. 記憶體優化

- 使用 static 緩衝區避免堆疊溢位
- `malloc()` / `free()` 需成對使用
- 小型緩衝區（2KB）解決 OOM 問題

---

## 9. v0.7.0 重構實際心得（2026-03-18 補充）

### 9.1 ESP-IDF CMake include 路徑驗證
`idf_component_register(INCLUDE_DIRS ...)` 在 configure 時會驗證每個路徑是否存在。
**→ 每個 Phase 只能加入已實際建立的子資料夾**（不可預先列入）。

### 9.2 esp_event_base_t 需要明確引入
`wifi_manager.h` 中的 static event handler 使用 `esp_event_base_t`，但僅引入
`esp_err.h` 和 `event_groups.h` 不夠，**需明確加入 `#include "esp_event.h"`**。

### 9.3 Edge Impulse get_data callback 只能用 static 函式
`signal.get_data` 需要 `int (*)(size_t, size_t, float*)` 函式指標（C-style），
無法直接使用成員函式。解法：
- 在類別中宣告 `static WakeWordDetector *instance_`
- `ei_get_data_` 為 `static` 函式，透過 `instance_->slice_buf_` 取得資料

### 9.4 ws_data_callback_t 解耦設計
`WebSocketClient` 透過 `set_data_callback(ws_data_callback_t)` 注入 callback，
`main.cpp` 中使用 `g_ws.set_data_callback(handle_server_action)` 完成注入，
避免 WebSocketClient 直接依賴 main 邏輯。

### 9.5 main.cpp 行數變化
| 版本 | 行數 |
|------|------|
| v0.6.6（原始） | 948 |
| Phase 2 後 | 602 |
| Phase 3 後 | 390 |
| Phase 4-5 後 | ~100 |

### 9.6 AudioStreamer 的 timestamp 依賴
`AudioStreamer::stream()` 的 audio_start JSON 需要 timestamp，
設計為在建構時注入 `TimeManager &`，避免直接呼叫全域 `get_timestamp_ms()`。

