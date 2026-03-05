# specification
本專案為一個基於 ESP32 的智慧語音控制系統，主要功能為透過語音喚醒詞 "heymiaomiao" 觸發後，將音訊傳送至伺服器進行語音辨識與意圖解析,並透過 MQTT 指令控制燈光.本專案採用 C/C++/python 開發，並使用 ESP-IDF 作為開發框架.

# constraints
* 請參考 SPEC.md 規格精神進行開發.

# environment
本專案的 firmware/esp32_edge_impulse/ 是主要喚醒詞接收核心, 利用 esp idf 環境 結合 edge impulse mfcc模型開發.
本專案的 src/esp-miao/ 為主要伺服器中樞, 負責接收喚醒後的 ASR指令解析過濾、LLM指令fallback補全、MQTT裝置管理註冊與控制、支援HTTPX Restful API溝通子控制器
本專案以 uv為主要套件與環境管理,

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

# 開發日誌依據 (路徑： ./develop_journal/<YYYY-MM-DD/>/子計畫[選項])
  - PLAN.md 一定要先讀的計畫.
  - TODO.md 計畫要執行的詳細項目排程.
  - NOTES.md 計畫執行時的大大小小技術要點可以記錄下來幫助你記憶.
  - (TEST_)REVIEW_TODO.md 最後項目做完(或測試做完)要審查的要點.

