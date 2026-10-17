# 本地同步脉宽编码 v2（独立分支，未烧录）

以功能分支 feat/local-hardware-sync 的 62e015e 为基线；不改 IMU 100 Hz、PPS 捕获和 TIM2 计时语义。

PB10/TIM2_CH3 仍由比较硬件输出 20 Hz 上升沿。每组 81 脉冲：15 ms 标记，后续 80 位用 5/10 ms 编码；大端 boot32、标记序号32、CRC16-CCITT（FFFF 初值，1021 多项式）。默认构建仍是原 v1 的固定 5 ms 脉宽。

```sh
cmake -S firmware -B firmware/build/CodedV2 -G Ninja -DCMAKE_BUILD_TYPE=Release -DLOCAL_SYNC_CODED_V2=ON
cmake --build firmware/build/CodedV2
```

ISR 仅做硬件比较重排、预先计算好的码字位查表和有界事件入队，不做 CRC、格式化、UART、除法或软件 GPIO 翻转。主循环双缓冲预计算后续码字；若赶不上码字切换，报告 LOCAL_SYNC_CODE_NOT_READY 并停止比较通道，不输出虚假身份。码字发生改变时，UART 前缀为 LOCAL_SYNC_V2，其余校验和/时钟字段与 v1 一致。

Pi 必须采双沿，至少两个连续有效码字才能确认身份，并与 MCU 原始报告相符；码字加入点不同，最坏需约 12.15 秒再加模型收敛。CRC 仅检测错误；backup boot_id 在彻底断电后可能重复，不是全球唯一 UUID，应结合 Pi boot/process 与 MCU epoch。

实际执行：ARM 编译链接通过，RAM 18200/20480 B，FLASH 13284/65536 B。Pi 原生 C 两项测试通过：原调度器 200000 上升沿/计时器回绕，以及 v2 8100 个脉宽逐位与独立 Python CRC 比对。它们不是实机电气/实时调度验收。

尚未烧录。烧录前应在稳定供电台架用示波器/逻辑分析仪核验 50 ms 上升沿周期与 5/10/15 ms 脉宽，双沿 GPIO 捕获无丢失，IMU 无缺样；覆盖任意时刻加入、字内漏沿、CRC 错误、MCU/Pi 重启及 GNSS 有无切换。使用另一 Pi 仓库的 tools/test_online_clock.py 和 docs/CONTINUOUS_FUSION_CLOCK.md 完成解码及状态测试。不能因这次构建成功就宣称室内唯一身份已在实机生效。
