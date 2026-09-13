# Raspberry Pi运行模块

本目录包含树莓派常驻服务使用的Python模块、网页资源、NTRIP控制命令和运维脚本。
串口所有权集中在`tools/capture_serial.py`：网页服务不打开UART，只读取原子状态文件
和已完成/正在写入的会话数据，从而避免多进程争抢串口。

## 文件职责

| 文件 | 功能 | 常用入口 |
|---|---|---|
| `live_dashboard.py` | HTTP服务、实时状态/轨迹API、采集/NTRIP/白名单命令控制 | `gnss-imu-dashboard.service` |
| `ntrip_client.py` | NTRIP v2连接、RTCM3校验/适配、发送队列与链路统计 | 由采集器导入 |
| `base_station_ctl.py` | 终端连接、查询、重连或断开NTRIP | `gnss-imu-base` |
| `record_start.sh` | 创建保存控制标志并等待新会话 | `gnss-imu-record-start` |
| `record_stop.sh` | 清除保存标志并等待文件安全关闭 | `gnss-imu-record-stop` |
| `watch_logger_status.sh` | 从日志读取状态并在同一终端行刷新 | `gnss-imu-status` |
| `clear_logger_data.sh` | 经路径和名称检查后清理时间戳会话 | `gnss-imu-clear-data` |
| `test_ntrip_client.py` | RTCM解析、MSM适配和流控单元测试 | `python3 -m unittest ...` |
| `test_live_dashboard.py` | 状态、API、轨迹和敏感字段处理测试 | `python3 -m unittest ...` |
| [`live_dashboard/`](live_dashboard/README.md) | 无构建步骤的HTML/CSS/JavaScript前端 | 浏览器访问8080端口 |

## 正常使用

首次安装不要逐个运行这些文件，按[`docs/PI_SETUP.md`](../docs/PI_SETUP.md)执行：

```bash
./scripts/setup_pi.sh
sudo reboot
./scripts/install_services.sh
```

安装后使用：

```bash
gnss-imu-status
gnss-imu-record-start
gnss-imu-record-stop
gnss-imu-base connect
```

## 开发与测试

```bash
python3 -m unittest raspberry_pi5.test_ntrip_client \
  raspberry_pi5.test_live_dashboard
python3 raspberry_pi5/live_dashboard.py --host 127.0.0.1 --port 8080
```

直接启动网页服务适合无硬件界面开发；完整运行仍需要采集器维护
`/run/gnss-imu/live.json`。NTRIP账号写入内存盘`/run/gnss-imu/ntrip.json`，断开或
重启后清除，不得改成仓库内的明文配置文件。

