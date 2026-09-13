# 调试与故障排查

## 一键现场信息

```bash
gnss-imu-diagnose
```

报告不读取NTRIP密码，包含型号、供电、UART、GPIO复用、服务、网络、最新状态、
最近错误和磁盘空间。反馈问题时优先保存这段输出。

## 服务没有启动

```bash
systemctl status gnss-imu-logger.service
journalctl -u gnss-imu-logger.service -b --no-pager -n 100
ls -l /dev/ttyAMA0 /dev/ttyAMA2
id
```

缺少UART节点：重新运行`./scripts/setup_pi.sh`并重启。用户不在`dialout`组：重启
或重新登录。端口被占用：

```bash
sudo fuser -v /dev/ttyAMA0 /dev/ttyAMA2
```

不要让minicom、Qt、另一个Python采集器与systemd服务同时打开UART。

## 临时查看STM32输出

先停止服务：

```bash
sudo systemctl stop gnss-imu-logger.service
sudo stty -F /dev/ttyAMA0 460800 raw -echo -ixon -ixoff
timeout 3 head -n 30 /dev/ttyAMA0
sudo systemctl start gnss-imu-logger.service
```

应看到`IMU`、`GNSS`、`SAT`、`RAWX`和以`#`开头的状态行。

## 临时检查原始UBX旁路

```bash
sudo systemctl stop gnss-imu-logger.service
sudo stty -F /dev/ttyAMA2 115200 raw -echo -ixon -ixoff
sudo timeout 3 dd if=/dev/ttyAMA2 bs=4096 status=none | od -An -tx1 -N64
sudo systemctl start gnss-imu-logger.service
```

正常数据应反复出现UBX同步字`b5 62`。GPIO5必须是RXD2输入，不能被其他程序
配置为输出。

## IMU没有100Hz或丢帧

检查MPU6050 `INT→PA1`、I2C PB6/PB7、3.3V和共地。运行：

```bash
gnss-imu-status
journalctl -u gnss-imu-logger.service -f
```

`lost`应保持0，IMU频率应接近100Hz。系统欠压、CPU/SD卡异常或UART线路过长
也可能导致不稳定。

## GNSS/RAWX没有数据

检查C099 `TX_ZED→PA3`、`RX_ZED←PA2`、`TP→PA0`，J4只能放在ARD 7-8。
固件重启会重新配置F9P UART1。确认F9P天线供电和开阔视野。

## f9p.ubx为空

检查`TX_ZED`到GPIO5的分支、`uart2-pi5`覆盖层和`/dev/ttyAMA2`。只有点击开始
保存后才写`f9p.ubx`；未保存时服务仍持续清空UART以保持实时性。

## 网页打不开

```bash
systemctl status gnss-imu-dashboard.service
ss -lntp | grep ':8080'
curl http://127.0.0.1:8080/api/status
ip -br address
```

手机直连Pi热点时用`http://10.42.0.1:8080`，不要写成中文冒号。

## 本地网页能开但高德地图加载失败

本地页面只需要手机到Pi连通，高德底图还需要手机流量经Pi转发到互联网。检查：

```bash
ip route
curl -I --max-time 8 https://webapi.amap.com/
nmcli -t -f NAME,DEVICE,STATE connection show --active
```

同时核对Web JS API Key、`securityJsCode`以及高德控制台域名限制。Pi板载Wi-Fi
作为热点时，上游互联网应来自以太网或第二网卡。

## NTRIP连接失败或频繁断流

```bash
gnss-imu-base status
journalctl -u gnss-imu-logger.service -f
ping -c 3 <NTRIP服务器>
```

HTTP 401通常是账号密码问题；404通常是挂载点或服务器状态；Bad Gateway、超时
和间歇恢复多为服务器、VPN或网络路径问题。串口计数正常而网络RTCM停止，不能
归因于STM32。

## Pi欠压

```bash
vcgencmd get_throttled
dmesg | grep -i voltage
```

`0x0`才表示本次开机没有检测到欠压/降频。现场曾出现`0x50005`，并测得模块端
5.16V、Pi端4.91V，属于带载线路压降。不能通过把VADJ提高到5.25V以上补偿。
应同时测模块输出端和Pi引脚端，使用两根5V、两根GND、短粗线和可靠端子，绕过
面包板。修复后重启，历史标志才会清零。

