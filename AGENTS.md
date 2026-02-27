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
