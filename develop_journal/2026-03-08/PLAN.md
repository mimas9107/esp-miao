# 2026-03-08 Server 模組化重構計畫 (PLAN.md) - [COMPLETED]

## 1. 現狀分析 (Current State) - [DONE]
- `server.py` 行數過多，混合了 API 路由、ASR 運算、LLM 通訊、MQTT 管理與 I/O 邏輯。
- 已完成拆分。

## 2. 目標架構 (Target Architecture) - [DONE]
已成功拆解為：
- `config.py`
- `connection.py`
- `audio.py`
- `intent.py`
- `dispatch.py`
- `utils.py`
- `app.py`
- `version.py`

## 3. 重構原則 - [DONE]
- **漸進式遷移**: 成功。
- **避免循環引用**: 成功（透過調整 `models.py` 與匯入順序）。
- **依賴注入**: 成功。
- **單一事實來源**: 已在 `SPEC.md` 定義以 `CHANGELOG.md` 為準。
