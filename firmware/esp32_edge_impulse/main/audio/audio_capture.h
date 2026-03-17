#ifndef AUDIO_CAPTURE_H
#define AUDIO_CAPTURE_H

/* ============================================================
 * audio_capture.h - I2S 音訊擷取（INMP441）
 * ESP-MIAO v0.7.0
 * ============================================================ */

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
#include "driver/i2s_std.h"

/* Debug 等級控制 */
#define AUDIO_LOG_NONE   0
#define AUDIO_LOG_ERROR  1
#define AUDIO_LOG_INFO   2
#define AUDIO_LOG_DEBUG  3

#ifndef AUDIO_LOG
#define AUDIO_LOG AUDIO_LOG_INFO
#endif

class AudioCapture {
public:
    AudioCapture();

    /**
     * 初始化 I2S 通道（APLL、Stereo模式）。
     * 必須在使用任何 read 函式前呼叫。
     */
    void init();

    /**
     * 讀取一個推論用 Slice（float，Left channel）。
     * @param out_buffer  輸出 float 陣列（大小 = num_mono_samples）
     * @param num_mono_samples 要讀取的 mono 樣本數
     * @param out_rms     輸出 RMS 值（可為 NULL）
     * @return true = 成功，false = I2S 讀取失敗
     */
    bool read_audio_slice(float *out_buffer, size_t num_mono_samples,
                          float *out_rms = nullptr);

    /**
     * 讀取串流用 int16_t 緩衝區（Left channel）。
     * @param out_buffer  輸出 int16_t 陣列
     * @param num_samples 要讀取的 mono 樣本數
     * @return true = 成功，false = I2S 讀取失敗
     */
    bool read_audio_to_buffer(int16_t *out_buffer, size_t num_samples);

private:
    i2s_chan_handle_t rx_chan_;
};

#endif // AUDIO_CAPTURE_H
