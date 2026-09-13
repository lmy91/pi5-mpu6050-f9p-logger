#!/bin/sh

set -eu

PROFILE=gnss-imu-hotspot
SSID=${1:-GNSS-IMU-Pi}
PASSWORD=${2:-}

if [ -z "$PASSWORD" ]; then
    printf '热点密码（至少8位，不回显）：'
    stty -echo
    IFS= read -r PASSWORD
    stty echo
    printf '\n'
fi
if [ "${#PASSWORD}" -lt 8 ]; then
    echo "密码至少需要8位。" >&2
    exit 1
fi

sudo nmcli radio wifi on
if nmcli -t -f NAME connection show | grep -qxF "$PROFILE"; then
    sudo nmcli connection modify "$PROFILE" connection.interface-name wlan0
else
    sudo nmcli connection add type wifi ifname wlan0 con-name "$PROFILE" ssid "$SSID"
fi
sudo nmcli connection modify "$PROFILE" \
    802-11-wireless.mode ap \
    802-11-wireless.band bg \
    802-11-wireless.ssid "$SSID" \
    wifi-sec.key-mgmt wpa-psk \
    wifi-sec.psk "$PASSWORD" \
    ipv4.method shared \
    ipv4.addresses 10.42.0.1/24 \
    ipv6.method disabled \
    connection.autoconnect yes
sudo nmcli connection up "$PROFILE"

echo "热点已启动：$SSID"
echo "手机连接后访问：http://10.42.0.1:8080"
echo "在线地图和NTRIP仍需树莓派从以太网获得互联网。"

