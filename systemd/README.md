# systemd服务模板

本目录保存可移植的系统服务模板。`scripts/install_services.sh`会把占位符替换为当前
用户和项目绝对路径，再安装到`/etc/systemd/system/`。

| 模板 | 职责 |
|---|---|
| `gnss-imu-logger.service.in` | 独占`/dev/ttyAMA0`与`/dev/ttyAMA2`，持续采集、解码、发布状态并按需保存 |
| `gnss-imu-dashboard.service.in` | 提供8080网页，只读取状态/数据文件并写易失控制文件 |
| `gnss-imu-time-sync.service.in` | 断网启动时等待有效F9P时间并一次性校正系统时钟 |

占位符：

- `@USER@`：运行服务的普通用户名；
- `@PROJECT_DIR@`：仓库绝对路径；
- `@HOME_DIR@`：用户主目录，用于可选地图配置。

## 安装与更新

```bash
./scripts/install_services.sh
systemctl status gnss-imu-logger.service gnss-imu-dashboard.service gnss-imu-time-sync.service
```

模板修改后要重新运行安装脚本并执行`sudo systemctl daemon-reload`，仅编辑本目录不会
改变已经安装的服务。保存期间更新前先运行`gnss-imu-record-stop`。定位和网页服务
配置异常自动重启，日志写入journal；GNSS校时服务每次开机成功校时一次后退出：

```bash
journalctl -u gnss-imu-logger.service -f
journalctl -u gnss-imu-dashboard.service -f
journalctl -u gnss-imu-time-sync.service -b --no-pager
```

采集器是UART唯一拥有者。不要在网页服务模板中添加串口访问，也不要删除
`RuntimeDirectory=gnss-imu`相关配置，否则易失状态/控制文件可能在单独重启服务时
消失或失去写权限。
