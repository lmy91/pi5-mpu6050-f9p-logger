#!/bin/sh

set -u

SCRIPT_PATH=$(readlink -f "$0")
PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$SCRIPT_PATH")/.." && pwd)

echo '=== 型号与系统 ==='
tr -d '\0' </proc/device-tree/model 2>/dev/null; echo
uname -a
uptime

echo '=== 供电 ==='
vcgencmd get_throttled 2>/dev/null || true
vcgencmd measure_temp 2>/dev/null || true

echo '=== UART ==='
ls -l /dev/ttyAMA0 /dev/ttyAMA2 2>&1
pinctrl get 4,5,14,15 2>/dev/null || true
for device in /dev/ttyAMA0 /dev/ttyAMA2; do
    printf '%s占用进程：' "$device "
    fuser "$device" 2>/dev/null || echo '无'
done

echo '=== 服务 ==='
systemctl is-active gnss-imu-logger.service gnss-imu-dashboard.service 2>&1
systemctl --no-pager --full --lines=8 status gnss-imu-logger.service gnss-imu-dashboard.service 2>&1 || true

echo '=== 网络 ==='
ip -br address
ip route

echo '=== 最新采集状态 ==='
journalctl -u gnss-imu-logger.service -n 30 --no-pager -o cat 2>/dev/null | grep '^\[' | tail -n 1 || true

echo '=== 最近错误 ==='
journalctl -u gnss-imu-logger.service -u gnss-imu-dashboard.service -p warning -n 20 --no-pager 2>/dev/null || true

echo '=== 磁盘 ==='
df -h "$PROJECT_ROOT/data"
