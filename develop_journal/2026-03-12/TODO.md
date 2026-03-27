# TODO: Integration of Eye Animation UI - Completed

## Phase 1: Preparation (Components & Build System) [x]
- [x] Create `firmware/esp32_edge_impulse/components` directory.
- [x] Copy necessary UI components from source project.
- [x] Update `idf_component.yml` and `CMakeLists.txt` dependencies.

## Phase 2: Logic Integration [x]
- [x] Resolve `IPADDR_NONE` macro conflict between `arduino-esp32` and `lwip`.
- [x] Initialize Arduino and UI Task in `app_main()`.
- [x] **Bug Fix**: Rewrite record-then-send to **Real-time Streaming** to solve OOM.
- [x] Implement `ui_publish_state()` in `inference_task` and `handle_server_action`.

## Phase 3: Hardware Configuration [x]
- [x] Configure SPI pins and ST7735 driver in `sdkconfig.defaults`.
- [x] Ensure Arduino does not autostart loopTask.

## Phase 4: Build & Test [x]
- [x] `idf.py build` success.
- [x] Flash and monitor verification:
    - [x] OOM issue resolved.
    - [x] State synchronization confirmed via logs and display.
    - [x] Real-time streaming confirmed functional with server.
