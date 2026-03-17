#ifndef VAD_H
#define VAD_H

/* ============================================================
 * vad.h - FFT 頻域語音活動偵測 (VAD)
 * ESP-MIAO v0.7.0
 * ============================================================ */

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

/* Debug 等級控制 */
#define VAD_LOG_NONE   0
#define VAD_LOG_ERROR  1
#define VAD_LOG_INFO   2
#define VAD_LOG_DEBUG  3

#ifndef VAD_LOG
#define VAD_LOG VAD_LOG_INFO
#endif

/* VAD 統計數據結構 */
struct VadStats {
    uint32_t fft_triggers;  // FFT 觸發次數
    uint32_t ml_triggered;  // ML 辨識成功次數
    float    rms_avg;       // RMS 滑動平均
    float    fft_avg;       // FFT 能量滑動平均
};

class VAD {
public:
    VAD();

    /**
     * 執行 VAD 偵測（FFT 頻域能量分析）。
     * @param buffer      音訊資料（float，16kHz mono）
     * @param length      樣本數
     * @param rms_val     輸出 RMS 值（可為 nullptr）
     * @param fft_energy  輸出 FFT 能量值（可為 nullptr）
     * @return true = 偵測到語音，false = 安靜
     */
    bool detect(const float *buffer, size_t length,
                float *rms_val = nullptr, float *fft_energy = nullptr);

    /** 記錄 ML 觸發成功次數（由 WakeWordDetector 呼叫） */
    void record_ml_trigger();

    /** 取得目前統計數據 */
    const VadStats &stats() const { return stats_; }

private:
    /* FFT 旋轉因子查表（針對 FFT_SIZE 512） */
    float twiddle_r_[256];
    float twiddle_i_[256];
    bool  twiddle_initialized_;

    VadStats stats_;
    uint32_t frame_count_;

    void   init_twiddle_factors_();
    void   fft_compute_(float *real, float *imag, int n);
    bool   fft_detect_(const float *buffer, size_t length, float *fft_energy_out);
};

#endif // VAD_H
