# Raspberry Pi 5 + STM32 + MPU6050 + ZED-F9P采集系统

当前稳定版：`v1.0.0`。该版本对应2026-09-14在树莓派5上连续运行验证的
STM32协议v3采集、原始UBX旁路、NTRIP/RTCM转发和网页监控版本。

这是从`stm32-mpu6050-f9p-navigation`独立出来的树莓派实时采集项目。系统以
STM32F103C8T6完成MPU6050/F9P硬件时间同步和协议v3输出，树莓派5负责开机
定位服务、按需保存、原始UBX旁路、NTRIP/RTCM转发以及手机/PC网页显示。

本项目不包含PC Qt和组合导航算法，适合作为后续树莓派实时GNSS/INS解算的
稳定数据入口。

## 上游版本对应关系

固件和串口协议的唯一上游是
[`stm32-mpu6050-f9p-navigation`](https://github.com/lmy91/stm32-mpu6050-f9p-navigation)。
本仓库的 `firmware/` 与 `release/` 是**部署快照**，只在主项目修改并验证后同步过来，
**不在本仓库直接修改固件源码**。同步流程固定为：主项目开发 → 测试 → 冻结提交 →
同步到本仓库 → 重新编译 `release/` → Pi 实机验证。

当前快照对应的上游提交、固件基线和协议版本记录在 [`UPSTREAM_VERSION`](UPSTREAM_VERSION)。
每次同步固件或协议后必须更新该文件并重新编译 `release/`，保证 `release/` 产物与源码
来自同一提交。

本仓库专属逻辑（网页、systemd、NTRIP、UBX 旁路、Wi-Fi 热点、GNSS 校时）只在这里
修改，不反向复制回主项目。

## 功能

- 100 Hz带GNSS时间戳的MPU6050原始IMU；
- 1 Hz F9P位置、NED速度、精度、卫星数和天空图；
- 1 Hz RXM-RAWX原始观测；
- F9P原始UBX旁路保存，包含RAWX和SFRBX，可转换RINEX观测/导航文件；
- 网页本地轨迹、高德在线地图、IMU曲线、天空图和RTK状态；
- 网页或终端开始/停止保存，未开始保存时仍持续实时定位；
- 网页开始保存后显示本次采集时长，停止保存后计时归零；
- 树莓派直接连接NTRIP，RTCM经STM32转发到F9P；
- 联网优先使用NTP，离线冷启动时从有效F9P时间一次性校正系统时钟；
- systemd开机自启、异常自动恢复和统一诊断命令。

## 系统连接

```text
互联网/NTRIP ─→ 树莓派5 ─UART0/460800─→ STM32 PA10 ─USART2─→ F9P
                         ←UART0/460800─ STM32 PA9  ← IMU/GNSS/RAWX
                         ←UART2/115200──────────── C099 TX_ZED原始UBX

外部降压模块
  ├─ VADJ 5.10～5.20V ─→ Pi Pin 2 + Pin 4
  ├─ GND ─────────────→ Pi Pin 6 + Pin 9
  ├─ 固定5V ──────────→ STM32 5V
  └─ 固定5V ──────────→ C099 DC_IN 5-12V
```

所有设备必须共地。当前现场曾测得模块端5.16V、Pi带载端4.91V并出现欠压；
这不是合格的正式采集供电。不得继续升高VADJ补偿，必须使用短粗线、可靠端子
并绕过面包板，使Pi端带载电压尽量达到5.0～5.15V且
`vcgencmd get_throttled`为`0x0`。

完整引脚、J4跳帽、ST-Link和上电检查见[接线说明](docs/WIRING.md)。

## 从零开始

### 1. 烧录STM32

仓库提供已经构建的固件：

```text
release/mpu6050_f9p_navigation.hex
release/mpu6050_f9p_navigation.elf
```

ST-Link只连接`SWDIO、SWCLK、GND、可选NRST`。STM32由降压模块固定5V供电时，
不要连接ST-Link的3.3V或5V。使用STM32CubeProgrammer选择HEX或ELF烧录，地址
由文件自带；BOOT0保持0。完整构建和命令行烧录见[固件烧录](docs/FIRMWARE_FLASH.md)。

### 2. 安装Raspberry Pi OS

建议使用64位Raspberry Pi OS Bookworm，创建普通用户并开启SSH。把本仓库放到
树莓派，例如：

```bash
git clone https://github.com/lmy91/pi5-mpu6050-f9p-logger.git
cd ~/pi5-mpu6050-f9p-logger
chmod +x scripts/*.sh raspberry_pi5/*.sh raspberry_pi5/base_station_ctl.py
./scripts/setup_pi.sh
sudo reboot
```

重启后：

```bash
cd ~/pi5-mpu6050-f9p-logger
./scripts/install_services.sh
gnss-imu-diagnose
```

安装脚本会自动按当前用户名和项目绝对路径生成systemd服务，不要求用户名必须
是`lmy`，也没有旧项目的硬编码路径。详细过程见[树莓派安装](docs/PI_SETUP.md)。

### 3. 打开网页

电脑与树莓派位于同一网络时：

```text
http://<树莓派IP>:8080
```

创建树莓派热点供手机直连：

```bash
./scripts/setup_hotspot.sh
```

手机连接`GNSS-IMU-Pi`后访问：

```text
http://10.42.0.1:8080
```

热点只提供本地网页。高德在线地图和NTRIP还要求树莓派通过以太网获得互联网。
高德Key不写入Git，配置方法见[树莓派安装](docs/PI_SETUP.md)。

### 4. 开始和停止保存

开机后两个服务自动运行，但默认不写数据文件。可在网页点击“开始采集”，或执行：

```bash
gnss-imu-record-start
gnss-imu-status
```

停止并安全关闭当前文件：

```bash
gnss-imu-record-stop
```

每次开始都会新建独立目录：

```text
data/decoded/YYYYMMDDHHMMSS/
├── imu.csv
├── gnss.csv
├── rawx.csv
├── sync.csv
└── f9p.ubx
```

正常系统关机会刷新文件；禁止在保存期间直接拔电。完整命令见
[采集与数据](docs/OPERATION.md)。

### 5. 连接RTK基站

网页点击“连接基站”，或在终端交互输入账号：

```bash
gnss-imu-base connect
gnss-imu-base status
gnss-imu-base reconnect
gnss-imu-base disconnect
```

密码只保存在`/run/gnss-imu/ntrip.json`，不会进入Git或采集目录，重启后清除。

## 快速调试

```bash
# 一次性完整自检
gnss-imu-diagnose

# 两个服务
systemctl status gnss-imu-logger.service
systemctl status gnss-imu-dashboard.service

# 实时日志
journalctl -u gnss-imu-logger.service -f
journalctl -u gnss-imu-dashboard.service -f

# UART与引脚
ls -l /dev/ttyAMA0 /dev/ttyAMA2
pinctrl get 4,5,14,15

# 欠压检查，正式采集必须为0x0
vcgencmd get_throttled

# 串口占用
sudo fuser -v /dev/ttyAMA0 /dev/ttyAMA2

# 网页接口
curl http://127.0.0.1:8080/api/status
```

不要在服务运行时再用`cat`、minicom、Qt或另一个采集器打开两个UART。需要查看
原始串口时先停止服务。分层排障流程见[调试手册](docs/TROUBLESHOOTING.md)。

## 测试

在树莓派项目根目录运行：

```bash
python3 -m unittest \
  raspberry_pi5.test_ntrip_client \
  raspberry_pi5.test_live_dashboard \
  tools.test_capture_serial
```

## 目录

| 目录 | 内容 |
|---|---|
| [`firmware/`](firmware/README.md) | STM32F103源码和CMake工程 |
| [`release/`](release/README.md) | 可直接烧录的ELF/HEX |
| [`raspberry_pi5/`](raspberry_pi5/README.md) | NTRIP、网页、服务控制和测试 |
| [`tools/`](tools/README.md) | 协议v3采集与sync诊断 |
| [`systemd/`](systemd/README.md) | 可移植的服务模板 |
| [`scripts/`](scripts/README.md) | 从零安装、热点和诊断脚本 |
| [`docs/`](docs/README.md) | 接线、烧录、安装、操作和排障文档 |
| [`data/`](data/README.md) | 本机采集目录；真实会话不提交到Git |

每个受版本控制的子目录均有自己的`README.md`，源码和网页二级目录可从上表继续
进入查看。

## 安全边界

- GPIO14、GPIO15和GPIO5只能承受3.3V逻辑，禁止输入5V；
- Pi的5V引脚直接进入5V电源轨，VADJ不得超过5.25V；
- VADJ、固定5V和USB-C电源不能并联给Pi供电；
- ST-Link与外部电源同时连接时不接ST-Link电源脚；
- 网页没有公网账号认证，只允许在可信局域网或设备热点使用；
- NTRIP账号、高德密钥和采集数据都不得提交到公开仓库。

## License

[MIT](LICENSE)
