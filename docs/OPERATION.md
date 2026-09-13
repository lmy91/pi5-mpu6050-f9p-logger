# 采集、RTK和数据文件

## 服务与保存是两个状态

Pi开机后定位服务持续运行，实时解码、网页和NTRIP可用，但默认不写文件。只有
点击网页“开始采集”或执行`gnss-imu-record-start`后才创建一次采集会话。

```bash
gnss-imu-status
gnss-imu-record-start
gnss-imu-record-stop
```

`gnss-imu-status`只刷新终端同一行。`REC=OFF`表示只实时处理，`REC=ON`表示
正在保存。

## 每次采集内容

```text
data/decoded/YYYYMMDDHHMMSS/
├── imu.csv    100Hz带GPS时间戳的IMU原始量和SI换算量
├── gnss.csv   1Hz位置、NED速度、精度、卫星数和RTK状态
├── rawx.csv   1Hz逐信号伪距、载波相位、多普勒和质量标志
└── f9p.ubx    GPIO5旁路得到的F9P原始UBX字节流
```

开始保存前，程序只维护很小的实时状态，不缓存一份待补写的历史采集数据。停止时
四个文件立即刷新关闭，定位服务继续运行。正常关机由systemd发送SIGINT并安全
关闭文件；保存时直接切断电源可能损坏当前文件和SD卡文件系统。

查看最新会话：

```bash
ls -ltd data/decoded/20* | head
du -sh data/decoded
```

清理所有时间戳会话：

```bash
gnss-imu-clear-data
```

该命令只允许删除当前项目`data/decoded`内符合时间戳名称的目录，并要求输入
`yes`确认。

## 网页

网页显示：

- 当前GNSS/RTK状态、卫星数、PDOP和精度；
- WGS-84本地等比例轨迹或高德地图；
- NED速度、天空图；
- 1Hz抽取的三轴加速度、角速度和温度曲线；
- 定位服务、保存状态和NTRIP状态；
- 白名单维护命令及结果。

未保存时地图只保留一个当前点，开始保存后才累计本次会话的离散轨迹点。

## NTRIP/RTK

终端连接：

```bash
gnss-imu-base connect
```

按提示输入服务器、端口、挂载点、用户名和密码。密码不回显。状态与控制：

```bash
gnss-imu-base status
gnss-imu-base reconnect
gnss-imu-base disconnect
```

RTCM链路为：

```text
NTRIP → Pi网络线程 → /dev/ttyAMA0 TX → PA10
      → STM32环形队列 → PA2 → F9P RX_ZED
```

STM32的`#RTCM`状态返回接收/转发、丢字节和F9P使用计数。收到RTCM不等于立刻
固定；RTK还取决于基线、共同卫星、信号质量、电离层、周跳和基站数据完整性。

## RAWX质量检查

停止保存后执行：

```bash
python3 tools/decode_rawx.py data/decoded/<会话>/rawx.csv
```

可输出JSON：

```bash
python3 tools/decode_rawx.py data/decoded/<会话>/rawx.csv \
  --json data/decoded/<会话>/rawx_report.json
```

## UBX转换RINEX

`f9p.ubx`同时包含RXM-RAWX观测数据和RXM-SFRBX广播导航字。结束保存后，在安装
RTKLIB `convbin`的电脑或Pi上运行：

```bash
convbin -r ubx -v 3.04 -f 5 -od -os -oi -ot -ol \
  -o rover.obs -n rover.nav f9p.ubx
```

Windows示例：

```powershell
& "C:\path\to\convbin.exe" -r ubx -v 3.04 -f 5 -od -os -oi -ot -ol `
  -o ".\rover.obs" -n ".\rover.nav" ".\f9p.ubx"
```

为了收齐各星座广播导航电文，开阔环境建议连续记录至少30分钟。`convbin`只能
转换实际记录到的数据，不能补出本次未收到的星座或频点。

