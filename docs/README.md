# 文档索引

这里保存从硬件接线到现场排障的专题说明。建议首次部署按下列顺序阅读：

1. [`WIRING.md`](WIRING.md)：电源、Pi、STM32、MPU6050、C099-F9P和ST-Link接线；
2. [`FIRMWARE_FLASH.md`](FIRMWARE_FLASH.md)：固件构建、烧录及协议v3输出；
3. [`PI_SETUP.md`](PI_SETUP.md)：Raspberry Pi OS、UART、systemd、网络和地图配置；
4. [`OPERATION.md`](OPERATION.md)：采集、RTK、CSV/UBX、质量分析和RINEX转换；
5. [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md)：串口、网页、NTRIP、UBX和欠压排查。

根目录[`README.md`](../README.md)提供系统全貌和最短启动路径，本目录文档负责展开
具体步骤。修改代码造成命令、引脚、文件名或默认参数变化时，应同步更新对应专题和
根README，示例中不得写入真实账号、密码、地图密钥或现场位置数据。

