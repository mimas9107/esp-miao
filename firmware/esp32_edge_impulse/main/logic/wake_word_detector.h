#ifndef WAKE_WORD_DETECTOR_H
#define WAKE_WORD_DETECTOR_H

/* ============================================================
 * wake_word_detector.h - 喚醒詞偵測主控器
 * ESP-MIAO v0.7.0
 *
 * 職責：
 *   - 持續讀取音訊切片並執行 Edge Impulse 推論
 *   - 整合 FFT VAD 前置過濾
 *   - 偵測到喚醒詞後協調 HardwareController / AudioStreamer
 * ============================================================ */

#include <stddef.h>
#include "audio_capture.h"
#include "vad.h"
#include "websocket_client.h"
#include "hardware_controller.h"
#include "audio_streamer.h"

/**
 * 伺服器動作回調（由 main.cpp 注入）。
 * @param json_str  NULL-terminated JSON 字串
 */
typedef void (*server_action_cb_t)(const char *json_str);

class WakeWordDetector {
public:
    /**
     * @param audio   已初始化的 AudioCapture
     * @param vad     已初始化的 VAD
     * @param ws      已初始化的 WebSocketClient
     * @param hw      已初始化的 HardwareController
     * @param streamer 已初始化的 AudioStreamer
     */
    WakeWordDetector(AudioCapture       &audio,
                     VAD                &vad,
                     WebSocketClient    &ws,
                     HardwareController &hw,
                     AudioStreamer      &streamer);

    /**
     * 設定伺服器動作回調（在 run() 前呼叫）。
     */
    void set_server_action_cb(server_action_cb_t cb) { on_server_action_ = cb; }

    /**
     * 啟動推論迴圈（此函式不會返回）。
     * 設計為在獨立 FreeRTOS task 中執行。
     */
    void run();

private:
    AudioCapture       &audio_;
    VAD                &vad_;
    WebSocketClient    &ws_;
    HardwareController &hw_;
    AudioStreamer       &streamer_;
    server_action_cb_t  on_server_action_;

    /* Edge Impulse 音訊切片緩衝（靜態分配於物件內） */
    float slice_buf_[/* EI_CLASSIFIER_SLICE_SIZE */ 4000];

    static int ei_get_data_(size_t offset, size_t length, float *out_ptr);

    /* 用於 ei_get_data_ static callback 的單例指標 */
    static WakeWordDetector *instance_;

    void on_wake_word_detected_(float confidence);
};

#endif // WAKE_WORD_DETECTOR_H
