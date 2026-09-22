# 采集工具

本目录是数据入口，可在树莓派或安装了Python/pyserial的PC上使用。

| 文件 | 功能 |
|---|---|
| `capture_serial.py` | 解码STM32协议v3，保存IMU/GNSS/RAWX/sync.csv，旁路保存UBX，发布实时状态并协同NTRIP |
| `test_capture_serial.py` | 协议、控制文件、状态和保存逻辑测试 |

## 直接采集

树莓派正式运行由systemd调用，不需要手工启动。调试时必须先停止服务，避免串口被
两个进程同时打开：

```bash
sudo systemctl stop gnss-imu-logger.service
python3 tools/capture_serial.py /dev/ttyAMA0 --baud 460800 --hours 0 \
  --output-dir data/decoded --save imu gnss rawx \
  --ubx-port /dev/ttyAMA2 --ubx-baud 115200
```

PC连接USB-TTL时可使用例如`COM7`，且不指定`--ubx-port`。按`Ctrl+C`会刷新并
关闭当前文件。正式树莓派用法、控制文件和服务参数以
[`systemd/gnss-imu-logger.service.in`](../systemd/gnss-imu-logger.service.in)为准。

## 测试

```bash
python3 -m unittest discover -s tools -p 'test_*.py'
```

新增协议字段时应先修改采集器的列定义与解析，再补测试和文档。工具不得记录NTRIP
密码或地图密钥；真实会话数据也不提交到Git。

