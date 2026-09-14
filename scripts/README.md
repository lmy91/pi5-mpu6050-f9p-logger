# 安装与诊断脚本

这些脚本用于把一个全新的Raspberry Pi OS配置成可开机自启的采集设备。均应在
项目根目录以普通用户执行；需要系统权限的步骤会自行调用`sudo`。

| 脚本 | 功能 | 是否需要重启 |
|---|---|---|
| `setup_pi.sh` | 安装依赖、加入`dialout`、关闭串口控制台、启用UART0/UART2 | 是 |
| `install_services.sh` | 安装定位、网页和离线GNSS校时服务及快捷命令 | 否 |
| `setup_hotspot.sh` | 通过NetworkManager建立`GNSS-IMU-Pi`热点 | 通常否 |
| `diagnose.sh` | 输出供电、UART、GPIO、服务、网络、错误和磁盘信息 | 否 |

## 推荐顺序

```bash
chmod +x scripts/*.sh raspberry_pi5/*.sh raspberry_pi5/base_station_ctl.py
./scripts/setup_pi.sh
sudo reboot
cd ~/pi5-mpu6050-f9p-logger
./scripts/install_services.sh
gnss-imu-diagnose
```

建立手机直连热点时运行`./scripts/setup_hotspot.sh`并按提示输入至少8位密码。密码
只交给NetworkManager，禁止把真实密码写进脚本或README。

这些脚本针对当前Raspberry Pi OS Bookworm和Pi 5 UART覆盖层。运行前可用
`sh -n scripts/*.sh`做语法检查。修改服务命令或项目结构时，应同步更新
[`systemd/`](../systemd/README.md)和安装文档。
