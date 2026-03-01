#!/bin/bash
echo "測試訂閱 mqtt頻道 lamp/status訊息"
mosquitto_sub -h <your mqtt broker> -p 1883 -u <your mqtt user> -P <your mqtt password> -t lamp/status
