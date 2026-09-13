# STM32源代码

## 文件职责

| 文件 | 功能 |
|---|---|
| `main.c` | 时钟/GPIO/I2C/UART/TIM2初始化，MPU6050采样，F9P UBX解析与配置，RTCM桥接，协议v3输出 |
| `startup_stm32f103xx.S` | 向量表、复位入口、数据段初始化及默认中断处理 |
| `syscall.c` | 裸机环境所需的最小newlib系统调用桩 |
| `sysmem.c` | `_sbrk`堆边界实现 |

## 运行数据流

```text
MPU6050 INT/PA1 ─→ TIM2捕获 ─→ I2C读取 ─→ IMU行 ─→ USART1/PA9
F9P TP/PA0      ─→ TIM2捕获 ─→ 本地时钟与GPS周内时对齐
F9P TX/PA3      ─→ USART2 RX ─→ UBX解析 ─→ GNSS/SAT/RAWX行
Pi TX/PA10      ─→ USART1 RX ─→ RTCM环形队列 ─→ USART2/PA2 ─→ F9P
```

`main.c`直接访问STM32寄存器，没有CubeMX生成的HAL层。中断处理必须保持短小；不要
在UART/TIM中断中加入阻塞打印或复杂计算。协议字段、量纲和波特率一旦改变，需同步
更新[`tools/capture_serial.py`](../../tools/capture_serial.py)、对应测试与文档。

构建、生成HEX和烧录见[`固件烧录说明`](../../docs/FIRMWARE_FLASH.md)。

