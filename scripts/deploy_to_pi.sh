#!/usr/bin/env bash
# 一键把 PC 上的修改同步到树莓派并重启服务
#
# 用法（在 PC 的 Git Bash 中，从项目根目录运行）：
#   ./scripts/deploy_to_pi.sh
#
# 说明：
#   - 依赖 ~/.ssh/config 中的主机别名 pi5-ics（已配置为 192.168.137.2 / 用户 lmy）。
#   - 不依赖树莓派联网 GitHub，直接 SCP 覆盖文件（适合 ICS 网线直连、Pi 无法上外网的场景）。
#   - 只同步本次时间回溯修复涉及的 4 个文件；改动其它文件时请在 FILES 里追加对应路径。
set -euo pipefail

PI="pi5-ics"                                   # SSH 主机别名
REMOTE_DIR="~/pi5-mpu6050-f9p-logger"          # 树莓派上的项目根目录

# 需要同步的文件（本地相对路径 = 树莓派相对路径，逐一指定以保留目录结构）
FILES=(
  tools/capture_serial.py
  raspberry_pi5/live_dashboard.py
  raspberry_pi5/live_dashboard/app.js
  raspberry_pi5/test_live_dashboard.py
)

echo "==> 同步文件到 ${PI} ..."
for f in "${FILES[@]}"; do
  echo "    ${f}"
  scp -o ConnectTimeout=8 "${f}" "${PI}:${REMOTE_DIR}/${f}"
done

echo "==> 树莓派上运行测试 ..."
ssh -o ConnectTimeout=15 "${PI}" \
  "cd ${REMOTE_DIR} && python3 -m unittest raspberry_pi5.test_live_dashboard tools.test_capture_serial"

echo "==> 重启服务 ..."
ssh -o ConnectTimeout=10 "${PI}" \
  "sudo systemctl restart gnss-imu-logger.service gnss-imu-dashboard.service && sleep 2 && systemctl is-active gnss-imu-logger.service gnss-imu-dashboard.service"

echo "==> 完成。浏览器刷新 http://$(ssh -o ConnectTimeout=8 "${PI}" 'hostname -I' | awk '{print $1}'):8080"
