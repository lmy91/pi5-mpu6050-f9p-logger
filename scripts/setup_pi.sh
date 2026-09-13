#!/bin/sh

set -eu

if [ "$(id -u)" -eq 0 ]; then
    echo "请用普通用户执行本脚本，脚本会在需要时调用sudo。" >&2
    exit 1
fi

BOOT_CONFIG=/boot/firmware/config.txt
if [ ! -f "$BOOT_CONFIG" ]; then
    echo "未找到 $BOOT_CONFIG；本脚本仅支持当前Raspberry Pi OS。" >&2
    exit 1
fi

sudo apt-get update
sudo apt-get install -y python3 python3-serial git network-manager
sudo usermod -aG dialout "$(id -un)"

append_once() {
    setting=$1
    grep -qxF "$setting" "$BOOT_CONFIG" || printf '%s\n' "$setting" | sudo tee -a "$BOOT_CONFIG" >/dev/null
}

sudo raspi-config nonint do_serial_cons 1
sudo raspi-config nonint do_serial_hw 0
append_once 'dtparam=uart0=on'
append_once 'dtoverlay=uart0-pi5'
append_once 'dtoverlay=uart2-pi5'

echo
echo "UART覆盖层、串口控制台和dialout权限已配置。"
echo "现在执行：sudo reboot"
echo "重启后回到项目目录运行：./scripts/install_services.sh"

