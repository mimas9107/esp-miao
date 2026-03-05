import os
import sys
import time
import subprocess
from pathlib import Path

def print_header(text):
    print("\n" + "="*60)
    print(f" {text}")
    print("="*60)

def wait_for_user(prompt="準備好了嗎？按下 Enter 開始這一關的測試..."):
    input(f"\n[?] {prompt}")

def run_command(cmd):
    try:
        subprocess.run(cmd, shell=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"執行出錯: {e}")

class ExperimentRunner:
    def __init__(self):
        self.metrics_file = Path("metrics.jsonl")
        self.analyzer = "scripts/analyze_metrics.py"

    def clear_metrics(self):
        if self.metrics_file.exists():
            print(f"\n[!] 偵測到舊的數據檔，正在備份並清空以確保數據純淨...")
            backup = f"metrics_backup_{int(time.time())}.jsonl"
            self.metrics_file.rename(backup)
            print(f"[*] 已備份至 {backup}")

    def run(self):
        print_header("ESP-MIAO 效能與魯棒性受控實驗導引")
        print("本腳本將引導您完成 4 個階段的真實場景測試。")
        
        self.clear_metrics()

        # --- Stage 1: Baseline ---
        print_header("第 1 關：物理基準測試 (Physical Baseline)")
        print("條件：安靜環境，距離 ESP32 約 1 公尺。")
        print("任務：請對著設備說 5 次「開燈」或「關燈」，每次間隔 5 秒。")
        wait_for_user()
        print("[*] 正在監聽物理輸入... 請開始說話。完成後請按下 Enter。")
        wait_for_user("完成 5 次發話了嗎？按下 Enter 進入下一關...")

        # --- Stage 2: Robustness ---
        print_header("第 2 關：環境雜音魯棒性 (Robustness)")
        print("條件：開啟電視、音樂或環境噪音。")
        print("任務：請重複剛才的動作，說 5 次「開燈」或「關燈」。")
        wait_for_user()
        print("[*] 正在監聽雜音環境下的輸入... 完成後請按下 Enter。")
        wait_for_user("完成 5 次雜音測試了嗎？按下 Enter 進入下一關...")

        # --- Stage 3: Gating & Logic ---
        print_header("第 3 關：意圖解析與 LLM 節流 (Logic Gating)")
        print("條件：安靜環境。")
        print("任務：請交替說出以下指令各 3 次：")
        print("  1. 命中關鍵字: 「啟動掃地機器人」 (預期跳過 LLM)")
        print("  2. 模糊意圖: 「幫我把地掃乾淨」 (預期觸發 LLM)")
        wait_for_user()
        print("[*] 正在錄製邏輯分支數據... 完成後請按下 Enter。")
        wait_for_user("完成邏輯分支測試了嗎？按下 Enter 進入最後一關...")

        # --- Stage 4: Concurrency ---
        print_header("第 4 關：併發壓力測試 (Concurrency - Simulated)")
        print("條件：此關卡會自動呼叫模擬器，測試 RPi4 在併發請求下的排隊能力。")
        wait_for_user("按下 Enter 將啟動模擬器發送 5 個併發請求...")
        
        print("[*] 正在發送併發請求...")
        # 這裡假設您有測試用的 wav 檔，若無則改用文字 fallback 模擬
        sim_cmd = "printf 't:開燈\nt:關燈\nt:掃地\nt:回充\nt:開燈\n' | uv run esp32-sim"
        run_command(sim_cmd)
        
        print("\n[*] 所有實驗關卡已完成！")
        print_header("產出實驗報告")
        run_command(f"uv run python {self.analyzer}")

if __name__ == "__main__":
    if not Path("scripts/analyze_metrics.py").exists():
        print("錯誤: 找不到分析腳本 scripts/analyze_metrics.py")
        sys.exit(1)
        
    runner = ExperimentRunner()
    try:
        runner.run()
    except KeyboardInterrupt:
        print("\n\n[!] 實驗被使用者中斷。")
