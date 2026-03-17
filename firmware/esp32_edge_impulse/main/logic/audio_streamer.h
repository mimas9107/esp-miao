#ifndef AUDIO_STREAMER_H
#define AUDIO_STREAMER_H

/* ============================================================
 * audio_streamer.h - 實時二進位音訊串流
 * ESP-MIAO v0.7.0
 * ============================================================ */

#include <stddef.h>
#include <stdint.h>
#include "websocket_client.h"
#include "audio_capture.h"
#include "time_manager.h"

class AudioStreamer {
public:
    /**
     * @param ws      已初始化的 WebSocketClient（需已連線）
     * @param audio   已初始化的 AudioCapture
     * @param timemgr 已初始化的 TimeManager（用於 timestamp）
     */
    AudioStreamer(WebSocketClient &ws, AudioCapture &audio, TimeManager &timemgr);

    /**
     * 串流指定樣本數的音訊。
     * @param total_samples  要串流的 PCM 樣本數（int16）
     * @param confidence     ML 信心度（附帶至 audio_start JSON）
     * @return true = 全部送出成功
     */
    bool stream(size_t total_samples, float confidence);

private:
    WebSocketClient &ws_;
    AudioCapture    &audio_;
    TimeManager     &timemgr_;
};

#endif // AUDIO_STREAMER_H
