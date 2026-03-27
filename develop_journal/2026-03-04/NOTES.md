# 2026-03-04 技術重點紀錄 (NOTES.md) - Final Insights

## 1. HTTP Timeout 的硬體背景
掃地機器人的 API (如 `home()`) 往往涉及多次 UDP 握手。在本機測試時 5s 足夠，但在 RPi4 的真實網路環境下，10s 是更安全的門檻。這是「Web 開發」與「硬體控制」思維的關鍵差異。

## 2. ASR 誤差的語義補償
對於常用指令，與其強求 Whisper 100% 準確，不如在 `aliases` 中加入常見的錯誤同音字（如「少地」）。這能大幅提升用戶體驗，讓系統顯得「聽得懂人話」。

## 3. 混合路徑的優勢
目前的 `dispatch_command` 實現了 MQTT (Low-level) 與 HTTP (High-level) 的完美共存。這種「依據設備能力決定通訊協議」的架構，是構建複雜智慧家居系統的基石。

## 4. RPi4 性能基準
- **Idle**: 10% CPU / 346MB RAM.
- **Processing**: 20% Peak (Avg).
- **Zombie Free**: asyncio subprocess management is verified.
