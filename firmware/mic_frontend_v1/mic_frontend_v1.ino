#include <Arduino.h>
#include <driver/i2s.h>
#include <math.h>

#define I2S_WS   25
#define I2S_SD   33
#define I2S_SCK  32
#define INDICATOR_LED 2

#define I2S_PORT I2S_NUM_0

#define SAMPLE_RATE 16000
#define BUFFER_LEN  512

//=== wav file structure
struct WAVHeader {
  char riff[4] = {'R','I','F','F'};
  uint32_t size;
  char wave[4] = {'W','A','V','E'};
  char fmt[4]  = {'f','m','t',' '};
  uint32_t fmtSize = 16;
  uint16_t format = 1;
  uint16_t channels = 1;
  uint32_t sampleRate = SAMPLE_RATE;
  uint32_t byteRate;
  uint16_t blockAlign;
  uint16_t bits = 16;
  char data[4] = {'d','a','t','a'};
  uint32_t dataSize;
};

// ===== VAD / Wake Parameters =====
#define VAD_ON_THRESHOLD   350
#define VAD_OFF_THRESHOLD  200
#define VAD_HOLD_MS        600

// ===== Recorder =====
#define RECORD_SECONDS   3
#define RECORD_RATE      SAMPLE_RATE
#define RECORD_SAMPLES   (RECORD_SECONDS * RECORD_RATE)

int16_t *recordBuffer = nullptr;
uint32_t recordIndex = 0;
bool isRecording = false;

uint32_t silenceFrames = 0;
#define SILENCE_LIMIT  25   // about 250ms

//===

int32_t sBuffer[BUFFER_LEN];
uint32_t loopcount; 

// ===== VAD State =====
bool vad_active = false;
uint32_t vad_last_active = 0;


void i2s_install() {
  const i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 8,
    .dma_buf_len = BUFFER_LEN,
    .use_apll = false,
    .tx_desc_auto_clear = false,
    .fixed_mclk = 0
  };

  i2s_driver_install(I2S_PORT, &i2s_config, 0, NULL);
}

void i2s_setpin() {
  const i2s_pin_config_t pin_config = {
    .bck_io_num = I2S_SCK,
    .ws_io_num = I2S_WS,
    .data_out_num = -1,
    .data_in_num = I2S_SD
  };

  i2s_set_pin(I2S_PORT, &pin_config);
}

void setup() {
  
  pinMode(INDICATOR_LED, OUTPUT);

  Serial.begin(115200);
  delay(1000);

  Serial.println("ESP32 INMP441 Audio Monitor Start");

  i2s_install();
  i2s_setpin();
  i2s_start(I2S_PORT);

  // initialize the Recorder
  // ===== Recorder Init =====
  recordBuffer = (int16_t*) heap_caps_malloc(RECORD_SAMPLES * sizeof(int16_t), MALLOC_CAP_8BIT);
  if (!recordBuffer) {
    Serial.println("Recorder malloc failed!");
    while (1);
  }
  Serial.printf("Recorder buffer ready: %u samples\n", RECORD_SAMPLES);
  
  // Before go into loop(), I will eliminate the initial spike while micphone being starting to recieve signal.
  loopcount=0;
  size_t bytesIn=0;
  for(int c=0; c<30; c++){
      i2s_read(I2S_PORT, sBuffer, sizeof(sBuffer), &bytesIn, portMAX_DELAY);
  }

}

// reocorder functions:
void recorderStart() {
  recordIndex = 0;
  silenceFrames = 0;
  isRecording = true;
  Serial.println("=== REC START ===");
}

void recorderStop() {
  isRecording = false;
  Serial.printf("=== REC STOP, samples=%u ===\n", recordIndex);
  
  for (int i = 0; i < 32 && i < recordIndex; i++) {
    Serial.printf("%d,", recordBuffer[i]);
  }
  Serial.println();

  WAVHeader hdr;
  hdr.dataSize = recordIndex * 2;
  hdr.blockAlign = hdr.channels * 2;
  hdr.byteRate = hdr.sampleRate * hdr.blockAlign;
  hdr.size = hdr.dataSize + sizeof(WAVHeader) - 8;

Serial.printf("WAV size=%u bytes\n", hdr.dataSize + sizeof(WAVHeader));


}

void recorderPush(int16_t v) {
  if (!isRecording) return;
  if (recordIndex >= RECORD_SAMPLES) {
    recorderStop();
    return;
  }
  recordBuffer[recordIndex++] = v;
}


// main loop
void loop() {
  int rangelimit = 1500;
  
  size_t bytesIn = 0;
  i2s_read(I2S_PORT, sBuffer, sizeof(sBuffer), &bytesIn, portMAX_DELAY);

  int samples = bytesIn / 4;

  float rms = 0;
  float peak = 0;

  float mean = 0;

  for (int i = 0; i < samples; i++) {
      mean += (float)(sBuffer[i] >> 14);
  }
  mean /= samples;

  for (int i = 0; i < samples; i++) {
    // // INMP441: keep scale reasonable
    // float v = (float)(sBuffer[i] >> 14) - mean;   // <<<<<< 關鍵修正
    // rms += v * v;
    // float av = fabs(v);
    // if (av > peak) peak = av;

    int16_t pcm=(int16_t)(sBuffer[i]>>14);
    float v=(float)pcm;
    rms+=v*v;
    float av=fabs(v);
    if(av>peak)peak=av;

    recorderPush(pcm);

  }

  rms = sqrtf(rms / samples);
  
  if (isRecording) {
    // peak可能對突刺太敏感。
    //if (peak < 120) silenceFrames++;
    if(rms < 120) silenceFrames++;
    else silenceFrames = 0;

    if (silenceFrames > SILENCE_LIMIT) {
      //Serial.println("[VAD] END");
      recorderStop();
      silenceFrames = 0;
    }
  }


  // // ===== Simple Trigger =====
  // static bool armed = true;
  // if (armed && peak > 600) {
  //   recorderStart();
  //   armed = false;
  // }
  // if (!isRecording && !armed) {
  //   armed = true;
  // }

  // === smooth signal ===
  static float smooth = 0;
  //smooth = 0.8f * smooth + 0.2f * rms;
  if (smooth < 1) smooth = rms;
  else smooth = 0.8f * smooth + 0.2f * rms;

  // ===== VAD FSM =====
  uint32_t now = millis();

  if (!vad_active && smooth > VAD_ON_THRESHOLD) {
      vad_active = true;
      vad_last_active = now;
      Serial.println("[VAD] WAKE");
      digitalWrite(INDICATOR_LED, HIGH);

      if (!isRecording) recorderStart();
  }

  if (vad_active) {
      if (smooth > VAD_OFF_THRESHOLD) {
          vad_last_active = now;
      }

      if (now - vad_last_active > VAD_HOLD_MS) {
          vad_active = false;
          Serial.println("[VAD] END");
          digitalWrite(INDICATOR_LED, LOW);

          if (isRecording) recorderStop();
      }
  }


  static uint32_t last = 0;
  if (millis() - last > 100) {
    // Serial.print(-1);
    // Serial.print(" ");
    // Serial.print(rangelimit);
    // Serial.print(" ");

    last = millis();
    // === original message ===
    // Serial.printf("rms=%8.2f smooth=%8.2f peak=%8.2f heap=%u\n",
    //               rms, smooth, peak, ESP.getFreeHeap());

    // === VAD message ===
    Serial.printf("rms=%8.2f smooth=%8.2f peak=%8.2f vad=%d heap=%u\n",
                  rms, smooth, peak, vad_active, ESP.getFreeHeap());

  }
}
