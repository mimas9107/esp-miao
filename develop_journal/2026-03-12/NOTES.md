# Integration Notes: Eye UI & Streaming Optimization

## 1. Architectural Change: Record-then-Send vs. Streaming
- **Initial Issue**: `malloc(96KB)` for a 3-second buffer failed due to heap fragmentation (OOM).
- **Solution**: Implemented `stream_audio_realtime`. It reads 2KB from I2S and sends it via WebSocket immediately.
- **Result**: Reduced peak memory usage significantly. Heap remained stable at ~118KB during operation.

## 2. Macro Conflicts
- `IPADDR_NONE` is defined by both `lwip` and `arduino-esp32`.
- **Fix**: `#undef IPADDR_NONE` before including `Arduino.h` in `main.cpp`.

## 3. UI State Latency
- The `UI_THINKING` state is now published at the start of the streaming process. 
- The server processing starts concurrently with the stream, reducing total wait time for the `UI_ACTION` feedback.

## 4. Hardware Safety
- Confirmed I2S (32, 25, 33) and SPI (23, 18, 16, 5, 17) pins are physically and logically isolated.
- TFT Backlight control is disabled (`CONFIG_ENABLE_BL=n`) to save pins/power as per current hardware setup.

## 5. Performance
- Core 1 is dedicated to UI rendering.
- Core 0 handles Edge Impulse inference, WiFi, and Audio Streaming.
- FPS remains stable without stuttering during voice processing.
