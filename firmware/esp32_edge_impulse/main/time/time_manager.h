#ifndef TIME_MANAGER_H
#define TIME_MANAGER_H

/* ============================================================
 * time_manager.h - NTP 時間同步管理
 * ESP-MIAO v0.7.0
 * ============================================================ */

#include <stdint.h>

/* Debug 等級控制 */
#define TIME_LOG_LEVEL_NONE   0
#define TIME_LOG_LEVEL_ERROR  1
#define TIME_LOG_LEVEL_INFO   2
#define TIME_LOG_LEVEL_DEBUG  3

#ifndef TIME_LOG
#define TIME_LOG TIME_LOG_LEVEL_INFO
#endif

class TimeManager {
public:
    /**
     * 初始化 SNTP 並等待時間同步。
     * 需在 WiFi 連線完成後呼叫。
     * @param max_retry 最大重試次數，預設 10 次
     */
    void init(int max_retry = 10);

    /**
     * 取得目前 Unix 時間戳（毫秒）。
     * @return uint64_t 毫秒時間戳
     */
    uint64_t get_timestamp_ms() const;

    /**
     * 透過 Server time_sync 訊息直接設定系統時間（RTC 同步）。
     * @param seconds Unix 秒數
     * @param ms      毫秒部分
     */
    void sync_from_server(long seconds, int ms);
};

#endif // TIME_MANAGER_H
