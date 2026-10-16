# PB10 本地硬件同步：阶段 1

基线 `f810b49`，分支 `feat/local-hardware-sync`。只升级固件；实际 Pi 接收端在
`pi5-stm32-f9p-fisheye-logger` 的同名分支，需先升级 Pi 解析器再烧录。

## 实现与接线

PB10 → Pi GPIO23 / 物理 Pin16，公共 GND。保持 PA0/PPS、PA1/DRDY、两路 UART、
I2C、相机和原 F9P PPS 接线不变。TIM2 Partial Remap 2（MAPR[9:8]=10）保留
PA0/PA1，CH3 复用推挽输出 PB10。SWJ_CFG 显式写 000 保持 SWD。

TIM2 仍为 1 MHz、ARR=65535。OC3 硬件 toggle，首次上升沿 timer=50000 us，
每 50000 us 一次上升沿、高电平 5000 us。ISR 先处理现有 CH1/CH2 和溢出，
再把 CCR3 设为下一边沿的低 16 位；边沿时间取已安排的扩展比较时间，
不是 ISR 或串口发送时刻。比较 ISR 超过下一比较前 500 us 安全界时，
锁存故障、强制输出低并停用 CH3 中断；不自动把漏调度解释成正常边沿。
故障时软件强制低的瞬间不是有效同步锚点，F/R 故障报文必须拒绝用于拟合。

ISR 只向 16 槽环存放事件，上升沿由主循环报告；队列满时累计 dropped 并在
后续报文标记。即使最终故障事件遇到队列满，主循环仍补报锁存故障。
USART1 新增 512 字节 TXE 中断发送环，所有旧报文的字节和顺序保留；
旧输出保留满环背压，新同步消息必须整帧有空间才入队，不等串口。
TIM2 IRQ 优先于 UART IRQ。原 IMU/GNSS/RAWX/SAT/RTCM/#sync 字段不改变。

## 协议 v1（v4 采集协议的可检测扩展）

```text
LOCAL_SYNC,<boot_id>,<seq>,<R|F>,<timer_us>,<flags>,<dropped>,<reset_flags>*HH\r\n
```

HH 是 `LOCAL_SYNC` 开始到 `*` 之前所有 ASCII 字节的 XOR8，两位十六进制。
普通消息仅上升沿 R；F 仅可能是故障比较事件。seq 为上升沿计数。
timer_us 为 48 位扩展比较时间；flags bit0=漏调度/迟到，bit1=曾队列丢失，
bit2=序号耗尽，bit8=备份域冷启动。dropped 为本次 MCU 启动累计丢失。
reset_flags 为原始 RCC_CSR。XOR8 用于基本传输校验，不是强完整性证明。

boot_id 是 BKP 备份域 32 位递增启动计数，可区分有备份供电时的 MCU 复位。
完全断电后可能重复，不能当全局 UUID：Pi 必须保留自身 boot_id、collector_id、
原始 timer 和冷启动标志，重启/回退分段，不可仅凭 MCU boot_id 跨会话拼接。
阶段 1 不进行脉冲配对，固定 20 Hz 的相位歧义仍待阶段 2 解决。

启动能力行是 `# local_sync=v1_pb10_tim2_ch3_20hz_5ms_xor8_observation_only`。
旧固件仍可供新 Pi 采集（无此能力、同步日志为空）。旧 Pi 解析器会把新增消息
计作 unknown_record，因此回滚时先停记录、恢复旧固件，再恢复旧 Pi 软件。

## 构建与测试

```powershell
cd firmware
cmake --preset Release
cmake --build --preset Release
arm-none-eabi-objcopy -O ihex build/Release/mpu6050_f9p_navigation.elf build/Release/mpu6050_f9p_navigation.hex
arm-none-eabi-objcopy -O binary build/Release/mpu6050_f9p_navigation.elf build/Release/mpu6050_f9p_navigation.bin
```

在有原生 cc/gcc 的 Linux 主机（包括 Pi）从仓库根目录运行：

```sh
python3 -m unittest discover -s firmware/tests -p test_local_sync.py
```

测试执行生产调度头文件的 C 实现及从 main.c 提取的捕获时间算术，检查
200000 个上升沿、16 位回绕、跨 32 位时间、迟到/漏比较拒绝、序号耗尽和
捕获溢出两侧算术。它不替代实机 CH1/CH2/CH3 并行、IMU 无丢样或电气精度测试。

## 烧录与恢复

先在 Pi 执行现用项目 `python3 scripts/assert_idle.py`，不得中断正在记录的任务。
用 STM32CubeProgrammer HOTPLUG 读取 0x08000000 起完整 65536 字节，保存 SHA-256。
备份不上传仓库。核对芯片 0x410 / 64 KiB 和 SWD 连接后，使用新构建 ELF，
不要覆盖 release/ 的旧固定版本。主机 ST-LINK 已独立供电时不接其电源输出。

```powershell
& "$env:LOCALAPPDATA\stm32cube\bundles\programmer\2.23.0\bin\STM32_Programmer_CLI.exe" -c port=SWD mode=UR reset=HWrst -w firmware/build/Release/mpu6050_f9p_navigation.elf -v -rst
```

若无 NRST 导线，可使用 `mode=NORMAL reset=SWrst`，仍需确认设备未记录。
恢复时将完整备份 bin 写回 0x08000000 并校验、复位，再恢复 Pi 软件备份。
不得在未保存失败证据前重烧或擦除数据。
