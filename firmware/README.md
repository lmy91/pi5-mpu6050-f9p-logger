# STM32F103C8T6同步采集固件

固件连接、输出频率和烧录方法见：

- [完整接线](../docs/WIRING.md)
- [构建与烧录](../docs/FIRMWARE_FLASH.md)

核心配置：72MHz系统时钟；TIM2 1MHz扩展计时；PA0捕获F9P TIMEPULSE，PA1
捕获MPU6050 DATA_RDY；USART1以460800 bit/s连接树莓派，USART2以115200
bit/s连接F9P。STM32启动后自动配置F9P并持续输出协议v3。

