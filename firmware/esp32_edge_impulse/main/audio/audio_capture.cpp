/*
 * audio_capture.cpp - I2S 音訊擷取實作
 * ESP-MIAO v0.7.0
 *
 * 硬體：INMP441（BCK=32, WS=25, DIN=33）
 * 模式：Stereo 讀取 + 軟體取左聲道
 */

#include "audio_capture.h"
#include "config.h"
#include "esp_log.h"
#include "esp_err.h"
#include <math.h>
#include <string.h>

static const char *TAG = "AudioCapture";

AudioCapture::AudioCapture() : rx_chan_(nullptr) {}

void AudioCapture::init()
{
    /* 1. 建立 I2S 通道 */
    i2s_chan_config_t chan_cfg = I2S_CHANNEL_DEFAULT_CONFIG(I2S_PORT_NUM, I2S_ROLE_MASTER);
    chan_cfg.dma_desc_num  = DMA_BUF_COUNT;
    chan_cfg.dma_frame_num = DMA_BUF_LEN;
    chan_cfg.auto_clear    = true;
    ESP_ERROR_CHECK(i2s_new_channel(&chan_cfg, NULL, &rx_chan_));

    /* 2. 設定 Standard 模式 */
    i2s_std_config_t std_cfg;
    memset(&std_cfg, 0, sizeof(std_cfg));

    std_cfg.clk_cfg.sample_rate_hz = SAMPLE_RATE;
    std_cfg.clk_cfg.clk_src        = I2S_CLK_SRC_APLL;
    std_cfg.clk_cfg.mclk_multiple  = I2S_MCLK_MULTIPLE_256;
    std_cfg.clk_cfg.bclk_div       = 8;

    std_cfg.slot_cfg.data_bit_width = I2S_DATA_BIT_WIDTH_32BIT;
    std_cfg.slot_cfg.slot_bit_width = I2S_SLOT_BIT_WIDTH_AUTO;
    std_cfg.slot_cfg.slot_mode      = I2S_SLOT_MODE_STEREO;
    std_cfg.slot_cfg.slot_mask      = I2S_STD_SLOT_BOTH;
    std_cfg.slot_cfg.ws_width       = I2S_DATA_BIT_WIDTH_32BIT;
    std_cfg.slot_cfg.ws_pol         = false;
    std_cfg.slot_cfg.bit_shift      = true;
#if SOC_I2S_HW_VERSION_1
    std_cfg.slot_cfg.msb_right      = false;
#else
    std_cfg.slot_cfg.left_align     = true;
    std_cfg.slot_cfg.big_endian     = false;
    std_cfg.slot_cfg.bit_order_lsb  = false;
#endif

    std_cfg.gpio_cfg.mclk = I2S_GPIO_UNUSED;
    std_cfg.gpio_cfg.bclk = I2S_BCK_GPIO;
    std_cfg.gpio_cfg.ws   = I2S_WS_GPIO;
    std_cfg.gpio_cfg.dout = I2S_GPIO_UNUSED;
    std_cfg.gpio_cfg.din  = I2S_DIN_GPIO;

    ESP_ERROR_CHECK(i2s_channel_init_std_mode(rx_chan_, &std_cfg));

    /* 3. 啟用通道 */
    ESP_ERROR_CHECK(i2s_channel_enable(rx_chan_));

    ESP_LOGI(TAG, "I2S initialized: %d Hz, Stereo->Mono(Left), BCK=%d WS=%d DIN=%d",
             SAMPLE_RATE, I2S_BCK_GPIO, I2S_WS_GPIO, I2S_DIN_GPIO);
}

bool AudioCapture::read_audio_slice(float *out_buffer, size_t num_mono_samples,
                                     float *out_rms)
{
    const size_t bytes_per_sample = sizeof(int32_t);
    const size_t chunk_frames     = 256;

    int32_t i2s_buf[chunk_frames * 2];
    size_t  samples_read = 0;
    float   sum_sq       = 0.0f;

    while (samples_read < num_mono_samples) {
        size_t frames_to_read = num_mono_samples - samples_read;
        if (frames_to_read > chunk_frames) frames_to_read = chunk_frames;

        size_t bytes_read = 0;
        esp_err_t ret = i2s_channel_read(rx_chan_, i2s_buf,
                                         frames_to_read * 2 * bytes_per_sample,
                                         &bytes_read, 1000);
        if (ret != ESP_OK) {
            ESP_LOGE(TAG, "I2S read failed: %s", esp_err_to_name(ret));
            return false;
        }

        size_t got_frames = bytes_read / (2 * bytes_per_sample);

        for (size_t i = 0; i < got_frames; i++) {
            int32_t raw_l = i2s_buf[i * 2];
            int32_t s     = raw_l >> 11;
            if (s >  32767) s =  32767;
            if (s < -32768) s = -32768;
            out_buffer[samples_read + i] = (float)s;
            sum_sq += (float)(s * s);
        }
        samples_read += got_frames;
    }

    if (out_rms) {
        *out_rms = sqrtf(sum_sq / num_mono_samples);
    }
    return true;
}

bool AudioCapture::read_audio_to_buffer(int16_t *out_buffer, size_t num_samples)
{
    const size_t bytes_per_sample = sizeof(int32_t);
    const size_t chunk_frames     = 256;

    int32_t i2s_buf[chunk_frames * 2];
    size_t  samples_read = 0;

    while (samples_read < num_samples) {
        size_t frames_to_read = num_samples - samples_read;
        if (frames_to_read > chunk_frames) frames_to_read = chunk_frames;

        size_t bytes_read = 0;
        esp_err_t ret = i2s_channel_read(rx_chan_, i2s_buf,
                                         frames_to_read * 2 * bytes_per_sample,
                                         &bytes_read, 1000);
        if (ret != ESP_OK) {
            ESP_LOGE(TAG, "I2S read failed: %s", esp_err_to_name(ret));
            return false;
        }

        size_t got_frames = bytes_read / (2 * bytes_per_sample);

        for (size_t i = 0; i < got_frames; i++) {
            int32_t raw_l = i2s_buf[i * 2];
            int32_t s     = raw_l >> 11;
            if (s >  32767) s =  32767;
            if (s < -32768) s = -32768;
            out_buffer[samples_read + i] = (int16_t)s;
        }
        samples_read += got_frames;
    }

    return true;
}
