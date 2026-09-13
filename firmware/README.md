# STM32F103C8T6同步采集固件

本目录是无HAL依赖的STM32F103C8T6裸机工程，负责MPU6050采样、F9P配置与
解析、PPS/IMU中断捕获、GNSS时间标记、RTCM转发以及协议v3串口输出。

## 目录内容

| 路径 | 功能 |
|---|---|
| [`Src/`](Src/README.md) | 主程序、启动文件和最小系统调用实现 |
| [`cmake/`](cmake/README.md) | 芯片、编译器、源文件和编译/链接参数 |
| `CMakeLists.txt` | CMake工程入口 |
| `CMakePresets.json` | `Debug`和`Release`构建预设 |
| `stm32f103x8_flash.ld` | STM32F103x8 Flash/RAM链接布局 |
| `project-description.json` | STM32扩展/IDE工程描述信息 |

## 使用方式

```bash
cmake --preset Release
cmake --build --preset Release
```

生成文件位于`build/Release/`。日常烧录建议直接使用仓库
[`release/`](../release/README.md)中的固定版本；源码修改、重新生成HEX和烧录方法见
[`构建与烧录`](../docs/FIRMWARE_FLASH.md)。

固件连接、输出频率和烧录方法见：

- [完整接线](../docs/WIRING.md)
- [构建与烧录](../docs/FIRMWARE_FLASH.md)

核心配置：72MHz系统时钟；TIM2 1MHz扩展计时；PA0捕获F9P TIMEPULSE，PA1
捕获MPU6050 DATA_RDY；USART1以460800 bit/s连接树莓派，USART2以115200
bit/s连接F9P。STM32启动后自动配置F9P并持续输出协议v3。

固件与硬件接线强耦合。修改GPIO、串口波特率、输出字段或F9P消息频率后，必须同步
修改树莓派采集器、测试和文档，并进行长时间丢帧/串口溢出验证。
