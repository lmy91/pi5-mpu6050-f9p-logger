# 采集会话

本目录是默认的数据输出根目录。`.gitkeep`和本说明用于保留目录结构，真实采集文件
由`.gitignore`排除。

## 目录结构

```text
YYYYMMDDHHMMSS/
├── imu.csv            约100 Hz，带GNSS时间戳的IMU原始值和SI换算值
├── gnss.csv           约1 Hz，位置、NED速度、精度、卫星数和RTK状态
├── rawx.csv           约1 Hz，逐信号伪距、载波、多普勒和质量标志
├── f9p.ubx            F9P UART原始UBX旁路字节流
└── quality_report.md  运行质量分析后生成，不是采集器必定创建
```

开始、停止、检查和RINEX转换命令见
[`docs/OPERATION.md`](../../docs/OPERATION.md)。采集过程中不要用表格软件打开
正在写入的CSV，也不要直接拔电；应先停止保存或正常关闭系统。
