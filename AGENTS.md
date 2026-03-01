# environment
本專案以 uv為主要套件與環境管理,
本專案的 firmware/esp32_edge_impulse/ 是主要喚醒詞接收核心, 利用 esp idf 環境 結合 edge impulse mfcc模型開發.

* 已經 uv init過:
pyproject.toml

* 相關相依套件以下指令加入:
uv add <package> 

* 已經 uv venv過:
.venv

* 執行請以:
uv run <scripts>

* esp idf環境啟用:
get_idf

執行過後即可使用指令:
idf.py

* esp idf環境啟用後 idf.py指令:
  - `idf.py fullclean` 完全清除前次的創建編譯任務
  - `idf.py build` 建立當前的編譯任務
  - `idf.py flash` 將build完的韌體燒錄上 esp32開發板
  - `idf.py monitor` 連接esp32開發板並監測訊息

# 專案角色分工 (Architectural Roles)
* **ESP32 (邊緣端)**:
  - 任務: 負責本地端 VAD 喚醒 (辨識 "heymiaomiao")。
  - 行為: 觸發後錄製 3 秒音訊，透過 WebSocket 傳送二進位流至伺服器。
  - **注意**: ESP32 不負責任何 MQTT 指令發送或邏輯判斷。

* **Server (伺服器端 - RPi4: 192.168.1.16, 開發PC: 192.168.1.103)**:
  - 任務: 接收音訊、ASR 辨識、LLM 意圖解析。
  - 觸發: 根據解析結果，由伺服器發送 MQTT 指令 (例如 "ON"/"OFF") 到 `lamp/command`。
  - 職責: 所有的控制決策與 MQTT Trigger 均在伺服器端執行。

