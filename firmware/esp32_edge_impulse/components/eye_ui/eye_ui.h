#pragma once

#ifdef __cplusplus
extern "C" {
#endif

// Display power control pin
#define DISPLAY_EN_PIN   GPIO_NUM_4   // GPIO to control display power

// Call initArduino() in app_main() before calling this.
void eye_ui_start(void);

#ifdef __cplusplus
}
#endif
