# Raspberry Pi 5从零安装

## 1. 安装系统和SSH

用Raspberry Pi Imager写入64位Raspberry Pi OS Bookworm。写盘时设置主机名、
普通用户名、密码和SSH。首次启动后从电脑登录：

```powershell
ssh <用户名>@<树莓派IP>
```

建议随后安装SSH公钥，但不要把私钥放进本项目。

## 2. 获取项目

```bash
sudo apt-get update
sudo apt-get install -y git
git clone https://github.com/lmy91/pi5-mpu6050-f9p-logger.git
cd ~/pi5-mpu6050-f9p-logger
chmod +x scripts/*.sh raspberry_pi5/*.sh raspberry_pi5/base_station_ctl.py
```

如果尚未创建远程仓库，也可以用SCP把PC上的整个项目目录复制到Pi家目录。

## 3. 配置两个UART

```bash
./scripts/setup_pi.sh
sudo reboot
```

脚本完成以下工作：

- 安装Python、pyserial、Git和NetworkManager；
- 把当前用户加入`dialout`；
- 关闭GPIO UART上的登录控制台；
- 启用`uart0-pi5`和`uart2-pi5`覆盖层。

重启后确认：

```bash
ls -l /dev/ttyAMA0 /dev/ttyAMA2
pinctrl get 4,5,14,15
```

预期GPIO14/15为TXD0/RXD0，GPIO4/5为TXD2/RXD2。GPIO4无需接线，GPIO5只
作为RXD2输入。`/dev/serial0`在Pi 5上可能指向专用调试UART，本项目明确使用
`/dev/ttyAMA0`和`/dev/ttyAMA2`，不要用`/dev/serial0`替代。

## 4. 安装开机服务

```bash
cd ~/pi5-mpu6050-f9p-logger
./scripts/install_services.sh
```

脚本根据当前用户名和项目绝对路径生成：

```text
/etc/systemd/system/gnss-imu-logger.service
/etc/systemd/system/gnss-imu-dashboard.service
/etc/systemd/system/gnss-imu-time-sync.service
```

并安装以下命令：

```text
gnss-imu-status
gnss-imu-record-start
gnss-imu-record-stop
gnss-imu-clear-data
gnss-imu-base
gnss-imu-diagnose
gnss-imu-time-sync
```

检查：

```bash
systemctl is-enabled gnss-imu-logger.service gnss-imu-dashboard.service gnss-imu-time-sync.service
systemctl is-active gnss-imu-logger.service gnss-imu-dashboard.service
gnss-imu-diagnose
```

采集服务独占两个UART。网页只读取`/run/gnss-imu/live.json`，不会再次打开串口。

## 5. 系统时间

时区保持`Asia/Shanghai`，联网时由`systemd-timesyncd`正常使用NTP。Pi没有RTC后备
电池且断网冷启动时，`gnss-imu-time-sync.service`会等待F9P同时给出有效GPS时间和
有效GPS-UTC闰秒，然后只校正系统时钟一次。它不修改CSV中的GNSS时间戳，也不参与
IMU/GNSS同步。

检查当前状态：

```bash
date --iso-8601=seconds
timedatectl
systemctl status gnss-imu-time-sync.service
journalctl -u gnss-imu-time-sync.service -b --no-pager
sudo gnss-imu-time-sync --dry-run --timeout 10
```

`System time already agrees with GNSS`表示无需调整；`System time set from GNSS`表示
本次开机已经离线校时。没有定位或天线遮挡时服务会等待，不会使用无效时间。

## 6. 网络

### 普通局域网

```bash
hostname -I
```

手机或PC连接同一局域网后访问`http://<Pi地址>:8080`。

### Pi自建热点

```bash
./scripts/setup_hotspot.sh
```

脚本会交互输入密码并创建`gnss-imu-hotspot`，地址固定为`10.42.0.1/24`。手机
连接后访问`http://10.42.0.1:8080`。重新启动后热点自动恢复。

Pi只有一个板载Wi-Fi时，该接口用作热点后不能同时作为普通Wi-Fi客户端。在线
高德地图和NTRIP需要通过以太网、USB网卡或第二块Wi-Fi网卡获得上游互联网。

### PC Wi-Fi共享到网线

Windows可把当前Wi-Fi的“Internet连接共享”目标设为与Pi相连的以太网。典型
地址为PC `192.168.137.1`、Pi `192.168.137.2`，但不同电脑可能变化。Pi检查：

```bash
ip -br address
ip route
ping -c 3 192.168.137.1
curl -I --max-time 8 https://webapi.amap.com/
```

## 7. 高德地图

本地米制轨迹不需要Key。在线地图可在每台浏览器的“地图设置”中填写Web JS API
Key和`securityJsCode`，也可以在Pi统一创建：

```bash
mkdir -p ~/.config/gnss-imu
chmod 700 ~/.config/gnss-imu
nano ~/.config/gnss-imu/amap.json
chmod 600 ~/.config/gnss-imu/amap.json
```

文件内容：

```json
{"key":"你的Web JS API Key","securityJsCode":"你的安全密钥"}
```

不要把该文件加入Git。在线底图由手机浏览器直接访问高德HTTPS资源，因此手机经
Pi热点时，Pi的上游网络转发也必须可用。只有本地网页能打开不代表在线底图可用。

## 8. 更新程序

正式使用Git远程仓库后：

```bash
cd ~/pi5-mpu6050-f9p-logger
git pull --ff-only
python3 -m unittest raspberry_pi5.test_ntrip_client \
  raspberry_pi5.test_live_dashboard tools.test_capture_serial
sudo systemctl restart gnss-imu-logger.service gnss-imu-dashboard.service
```

保存期间先执行`gnss-imu-record-stop`，再更新或重启服务。
