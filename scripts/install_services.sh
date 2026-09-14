#!/bin/sh

set -eu

if [ "$(id -u)" -eq 0 ]; then
    echo "请用将要运行采集服务的普通用户执行，不要直接用root。" >&2
    exit 1
fi

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
SERVICE_USER=$(id -un)
HOME_DIR=$(getent passwd "$SERVICE_USER" | cut -d: -f6)

for device in /dev/ttyAMA0 /dev/ttyAMA2; do
    if [ ! -c "$device" ]; then
        echo "缺少 $device；请先运行./scripts/setup_pi.sh并重启。" >&2
        exit 1
    fi
done

mkdir -p "$PROJECT_DIR/data/decoded" "$HOME_DIR/.config/gnss-imu"
chmod +x "$PROJECT_DIR"/raspberry_pi5/*.sh "$PROJECT_DIR"/raspberry_pi5/base_station_ctl.py
chmod +x "$PROJECT_DIR"/raspberry_pi5/gnss_time_sync.py
chmod +x "$PROJECT_DIR"/scripts/*.sh
chmod +x "$PROJECT_DIR"/tools/analyze_session.py

render_unit() {
    input=$1
    output=$2
    sed -e "s|@USER@|$SERVICE_USER|g" \
        -e "s|@PROJECT_DIR@|$PROJECT_DIR|g" \
        -e "s|@HOME_DIR@|$HOME_DIR|g" "$input" | sudo tee "$output" >/dev/null
}

render_unit "$PROJECT_DIR/systemd/gnss-imu-logger.service.in" \
    /etc/systemd/system/gnss-imu-logger.service
render_unit "$PROJECT_DIR/systemd/gnss-imu-dashboard.service.in" \
    /etc/systemd/system/gnss-imu-dashboard.service
render_unit "$PROJECT_DIR/systemd/gnss-imu-time-sync.service.in" \
    /etc/systemd/system/gnss-imu-time-sync.service

sudo ln -sf "$PROJECT_DIR/raspberry_pi5/watch_logger_status.sh" /usr/local/bin/gnss-imu-status
sudo ln -sf "$PROJECT_DIR/raspberry_pi5/record_start.sh" /usr/local/bin/gnss-imu-record-start
sudo ln -sf "$PROJECT_DIR/raspberry_pi5/record_stop.sh" /usr/local/bin/gnss-imu-record-stop
sudo ln -sf "$PROJECT_DIR/raspberry_pi5/clear_logger_data.sh" /usr/local/bin/gnss-imu-clear-data
sudo ln -sf "$PROJECT_DIR/raspberry_pi5/base_station_ctl.py" /usr/local/bin/gnss-imu-base
sudo ln -sf "$PROJECT_DIR/scripts/diagnose.sh" /usr/local/bin/gnss-imu-diagnose
sudo ln -sf "$PROJECT_DIR/tools/analyze_session.py" /usr/local/bin/gnss-imu-analyze
sudo ln -sf "$PROJECT_DIR/raspberry_pi5/gnss_time_sync.py" /usr/local/bin/gnss-imu-time-sync

sudo systemctl daemon-reload
sudo systemctl enable --now gnss-imu-logger.service gnss-imu-dashboard.service
sudo systemctl enable gnss-imu-time-sync.service
sudo systemctl restart --no-block gnss-imu-time-sync.service
sleep 2
systemctl --no-pager --full status gnss-imu-logger.service gnss-imu-dashboard.service \
    gnss-imu-time-sync.service || true

echo
echo "安装完成。网页：http://$(hostname -I | awk '{print $1}'):8080"
echo "运行 gnss-imu-diagnose 做完整自检。"
