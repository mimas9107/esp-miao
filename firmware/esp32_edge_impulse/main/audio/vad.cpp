/*
 * vad.cpp - FFT 頻域語音活動偵測實作
 * ESP-MIAO v0.7.0
 *
 * 採用基 2 DIT FFT + 旋轉因子查表（優化版）
 * 計算 300Hz~3400Hz 人聲頻段能量，與閾值比較
 */

#include "vad.h"
#include "config.h"
#include "esp_log.h"
#include <math.h>
#include <string.h>

static const char *TAG = "VAD";

VAD::VAD()
    : twiddle_initialized_(false),
      frame_count_(0)
{
    memset(&stats_, 0, sizeof(stats_));
    memset(twiddle_r_, 0, sizeof(twiddle_r_));
    memset(twiddle_i_, 0, sizeof(twiddle_i_));
}

void VAD::init_twiddle_factors_()
{
    if (twiddle_initialized_) return;
    for (int i = 0; i < FFT_SIZE / 2; i++) {
        float angle   = -2.0f * (float)M_PI * i / FFT_SIZE;
        twiddle_r_[i] = cosf(angle);
        twiddle_i_[i] = sinf(angle);
    }
    twiddle_initialized_ = true;
}

void VAD::fft_compute_(float *real, float *imag, int n)
{
    init_twiddle_factors_();

    // Bit-reversal permutation
    int j = 0;
    for (int i = 0; i < n - 1; i++) {
        if (i < j) {
            float tr = real[i]; float ti = imag[i];
            real[i] = real[j]; imag[i] = imag[j];
            real[j] = tr;      imag[j] = ti;
        }
        int k = n / 2;
        while (k <= j) { j -= k; k /= 2; }
        j += k;
    }

    // Butterfly computation
    for (int len = 2; len <= n; len <<= 1) {
        int half = len >> 1;
        int step = n / len;
        for (int i = 0; i < n; i += len) {
            for (int k = 0; k < half; k++) {
                int   idx = k * step;
                float wr  = twiddle_r_[idx];
                float wi  = twiddle_i_[idx];
                float tr  = wr * real[i + k + half] - wi * imag[i + k + half];
                float ti  = wr * imag[i + k + half] + wi * real[i + k + half];
                real[i + k + half] = real[i + k] - tr;
                imag[i + k + half] = imag[i + k] - ti;
                real[i + k] += tr;
                imag[i + k] += ti;
            }
        }
    }
}

bool VAD::fft_detect_(const float *buffer, size_t length, float *fft_energy_out)
{
    if (length < FFT_SIZE) {
        if (fft_energy_out) *fft_energy_out = 0.0f;
        return false;
    }

    static float real[FFT_SIZE];
    static float imag[FFT_SIZE];

    // Hamming windowing + copy
    for (int i = 0; i < FFT_SIZE; i++) {
        float window = 0.54f - 0.46f * cosf(2.0f * (float)M_PI * i / (FFT_SIZE - 1));
        real[i] = buffer[i] * window;
        imag[i] = 0.0f;
    }

    fft_compute_(real, imag, FFT_SIZE);

    int   start_bin  = (FFT_FREQ_MIN * FFT_SIZE) / SAMPLE_RATE;
    int   end_bin    = (FFT_FREQ_MAX * FFT_SIZE) / SAMPLE_RATE;
    float sum_power  = 0.0f;
    int   bin_count  = 0;

    for (int i = start_bin; i < end_bin && i < FFT_SIZE / 2; i++) {
        sum_power += (real[i] * real[i] + imag[i] * imag[i]);
        bin_count++;
    }

    float band_rms = (bin_count > 0) ? sqrtf(sum_power / bin_count) : 0.0f;

    if (fft_energy_out) *fft_energy_out = band_rms;
    return (band_rms > FFT_ENERGY_THRESHOLD);
}

bool VAD::detect(const float *buffer, size_t length,
                 float *rms_val, float *fft_energy)
{
    // RMS（調試用）
    if (rms_val) {
        float sum_sq = 0.0f;
        for (size_t i = 0; i < length; i++) sum_sq += buffer[i] * buffer[i];
        *rms_val = sqrtf(sum_sq / length);
    }

    // FFT 偵測
    float local_fft = 0.0f;
    bool  result    = fft_detect_(buffer, length, &local_fft);
    if (fft_energy) *fft_energy = local_fft;

    // 統計更新
    frame_count_++;
    if (result) stats_.fft_triggers++;
    stats_.fft_avg = stats_.fft_avg * 0.99f + local_fft * 0.01f;
    if (rms_val) stats_.rms_avg = stats_.rms_avg * 0.99f + (*rms_val) * 0.01f;

#if VAD_FFT_DEBUG
    if (frame_count_ % PRINT_STATS_INTERVAL == 0) {
        ESP_LOGI(TAG, "[VAD Stats frame=%lu] fft_trig=%lu ml_trig=%lu rms_avg=%.2f fft_avg=%.2f(>%.0f?)",
                 (unsigned long)frame_count_,
                 (unsigned long)stats_.fft_triggers,
                 (unsigned long)stats_.ml_triggered,
                 stats_.rms_avg, stats_.fft_avg, (float)FFT_ENERGY_THRESHOLD);
    }
#endif

    return result;
}

void VAD::record_ml_trigger()
{
    stats_.ml_triggered++;
}
