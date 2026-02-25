/*
 * Edge Impulse Wake Word Detection with INMP441 I2S Microphone
 * 
 * Hardware: ESP32 DevKit V1 + INMP441
 * Model:    esp-miao-mfcc (MFCC-based, 3 classes: heymiaomiao / noise / unknown)
 * 
 * I2S Configuration:
 *   - Pins: BCK=32, WS=25, DIN=33 (Matching inmp441_recorder configuration)
 *   - Mode: Stereo Read + Software Left Channel Extraction
 *     (Required for ESP32 HW V1 compatibility with I2S std driver)
 *   - Clock: APLL enabled for accurate 16kHz sample rate
 * 
 * Inference:
 *   - Continuous sliding window (16000 samples, 4 slices)
 *   - Wake word: "heymiaomiao" (Threshold > 0.6)
 */

#include <stdio.h>
#include <string.h>
#include <math.h>

#include "edge-impulse-sdk/classifier/ei_run_classifier.h"

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/gpio.h"
#include "driver/i2s_std.h"
#include "esp_log.h"
#include "esp_err.h"
#include "sdkconfig.h"
#include "esp_idf_version.h"

/* ---------- Hardware Configuration ---------- */

#define LED_PIN         GPIO_NUM_2

#define I2S_BCK_GPIO    GPIO_NUM_32
#define I2S_WS_GPIO     GPIO_NUM_25
#define I2S_DIN_GPIO    GPIO_NUM_33

/* ---------- Audio Configuration ---------- */

#define SAMPLE_RATE     16000
#define I2S_PORT_NUM    I2S_NUM_0
#define DMA_BUF_COUNT   8
#define DMA_BUF_LEN     256

#define VAD_THRESHOLD   1000.0f

/* ---------- Globals ---------- */

static i2s_chan_handle_t rx_chan = NULL;
static float ei_slice_buffer[EI_CLASSIFIER_SLICE_SIZE];

/* ---------- I2S Initialization ---------- */

static void init_i2s(void)
{
    i2s_chan_config_t chan_cfg = I2S_CHANNEL_DEFAULT_CONFIG(I2S_PORT_NUM, I2S_ROLE_MASTER);
    chan_cfg.dma_desc_num  = DMA_BUF_COUNT;
    chan_cfg.dma_frame_num = DMA_BUF_LEN;
    chan_cfg.auto_clear    = true;
    ESP_ERROR_CHECK(i2s_new_channel(&chan_cfg, NULL, &rx_chan));

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

    ESP_ERROR_CHECK(i2s_channel_init_std_mode(rx_chan, &std_cfg));
    ESP_ERROR_CHECK(i2s_channel_enable(rx_chan));

    printf("I2S initialized: %d Hz, Stereo Mode (Left Extracted), Pins: 32/25/33\r\n", SAMPLE_RATE);
}

/* ---------- Read Audio Slice (Stereo -> Mono Left) ---------- */

static bool read_audio_slice(float *out_buffer, size_t num_mono_samples, float *out_rms)
{
    const size_t bytes_per_sample = sizeof(int32_t);
    const size_t chunk_frames = 256;
    
    int32_t i2s_buf[chunk_frames * 2];

    size_t samples_read = 0;
    float sum_sq = 0.0f;

    while (samples_read < num_mono_samples) {
        size_t frames_to_read = num_mono_samples - samples_read;
        if (frames_to_read > chunk_frames) frames_to_read = chunk_frames;

        size_t bytes_read = 0;
        esp_err_t ret = i2s_channel_read(rx_chan, i2s_buf,
                                         frames_to_read * 2 * bytes_per_sample,
                                         &bytes_read, 1000);
        if (ret != ESP_OK) {
            printf("ERR: I2S read failed: %d\r\n", ret);
            return false;
        }

        size_t got_frames = bytes_read / (2 * bytes_per_sample);

        for (size_t i = 0; i < got_frames; i++) {
            int32_t raw_l = i2s_buf[i * 2];
            int32_t s = raw_l >> 11;
            
            if (s > 32767)  s = 32767;
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

/* ---------- Edge Impulse Signal Callback ---------- */

static int ei_audio_signal_get_data(size_t offset, size_t length, float *out_ptr)
{
    memcpy(out_ptr, ei_slice_buffer + offset, length * sizeof(float));
    return 0;
}

/* ---------- LED Control ---------- */

static void setup_led(void)
{
#if ESP_IDF_VERSION >= ESP_IDF_VERSION_VAL(5, 0, 0)
    esp_rom_gpio_pad_select_gpio(LED_PIN);
#elif ESP_IDF_VERSION >= ESP_IDF_VERSION_VAL(4, 0, 0)
    gpio_pad_select_gpio(LED_PIN);
#endif
    gpio_set_direction(LED_PIN, GPIO_MODE_OUTPUT);
    gpio_set_level(LED_PIN, 0);
}

/* ---------- Inference Task ---------- */

static void inference_task(void *arg)
{
    printf("\r\n=== Edge Impulse Wake Word Detection ===\r\n");
    printf("Project : %s  (ID %d)\r\n", EI_CLASSIFIER_PROJECT_NAME, EI_CLASSIFIER_PROJECT_ID);
    printf("Window  : %d ms, Slices: %d\r\n", 
           (int)(EI_CLASSIFIER_RAW_SAMPLE_COUNT * 1000 / EI_CLASSIFIER_FREQUENCY),
           EI_CLASSIFIER_SLICES_PER_MODEL_WINDOW);
    printf("Threshold: %.2f\r\n", (float)EI_CLASSIFIER_THRESHOLD);
    printf("VAD Threshold: %.2f (RMS)\r\n\r\n", VAD_THRESHOLD);

    run_classifier_init();

    printf("Warming up microphone...\r\n");
    for (int i = 0; i < 8; i++) {
        read_audio_slice(ei_slice_buffer, EI_CLASSIFIER_SLICE_SIZE, NULL);
    }
    printf("Started.\r\n");

    ei_impulse_result_t result = {};

    while (1) {
        float current_rms = 0.0f;

        if (!read_audio_slice(ei_slice_buffer, EI_CLASSIFIER_SLICE_SIZE, &current_rms)) {
            vTaskDelay(pdMS_TO_TICKS(100));
            continue;
        }

        signal_t signal;
        signal.total_length = EI_CLASSIFIER_SLICE_SIZE;
        signal.get_data     = &ei_audio_signal_get_data;

        EI_IMPULSE_ERROR res = run_classifier_continuous(&signal, &result, false);
        if (res != EI_IMPULSE_OK) {
            printf("ERR: Inference failed (%d)\r\n", res);
            continue;
        }

        bool wake_word_detected = false;
        
        for (uint16_t i = 0; i < EI_CLASSIFIER_LABEL_COUNT; i++) {
            if (strcmp(ei_classifier_inferencing_categories[i], "heymiaomiao") == 0) {
                if (result.classification[i].value >= EI_CLASSIFIER_THRESHOLD && current_rms > VAD_THRESHOLD) {
                    wake_word_detected = true;
                }
            }
        }

        if (wake_word_detected) {
            printf("\r\n>>> 🐱 WAKE WORD DETECTED! 🐱 <<<\r\n\r\n");
            for (int k = 0; k < 3; k++) {
                gpio_set_level(LED_PIN, 1);
                vTaskDelay(pdMS_TO_TICKS(100));
                gpio_set_level(LED_PIN, 0);
                vTaskDelay(pdMS_TO_TICKS(100));
            }
        }
    }
}

extern "C" int app_main()
{
    setup_led();
    init_i2s();
    xTaskCreate(inference_task, "ei_infer", 16384, NULL, 5, NULL);
    return 0;
}
