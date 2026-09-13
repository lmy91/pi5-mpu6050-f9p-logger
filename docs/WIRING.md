# 完整接线与上电检查

## 1. 电源

本方案使用外部降压模块星形供电，不让树莓派给其他设备转供电：

| 电源端 | 设备端 | 说明 |
|---|---|---|
| VADJ 5.10～5.20V | Pi Pin 2 / 5V | 第一根正极线 |
| VADJ 5.10～5.20V | Pi Pin 4 / 5V | 第二根正极线 |
| GND | Pi Pin 6 / GND | 第一根地线 |
| GND | Pi Pin 9 / GND | 第二根地线 |
| 固定5V | STM32 5V | 独立支路 |
| 固定5V | C099 DC_IN 5-12V | 独立支路 |
| GND | STM32 GND、C099 GND | 全系统共地 |

调VADJ时必须先断开Pi。模块端不得超过5.25V，不得靠提高源端电压补偿线路
压降。两根正极必须配两根地线，Pi主电源不经过面包板，使用短粗导线和可靠
端子。STM32和C099不要串在Pi的供电引脚后面。

当前现场测量记录：VADJ空载/模块端约5.16～5.20V，Pi带载端曾为4.91V，系统
记录过欠压和降频。这说明线路或电源带载能力仍需整改，不能作为正式采集验收值。

## 2. Pi与STM32

| 树莓派5物理引脚 | 方向 | STM32 | 用途 |
|---|---:|---|---|
| Pin 8 / GPIO14 / TXD0 | → | PA10 / USART1_RX | RTCM和控制数据下发 |
| Pin 10 / GPIO15 / RXD0 | ← | PA9 / USART1_TX | 协议v3数据上传 |
| Pin 6或9 / GND | ↔ | GND | UART公共参考地 |

参数为460800 bit/s、8N1、无流控。UART必须TX接RX。PA9输出和PA10输入均为
3.3V TTL，不是RS-232电平。

## 3. MPU6050与STM32

| MPU6050/GY-521 | STM32 | 用途 |
|---|---|---|
| VCC | 3.3V | 由STM32 3.3V供电 |
| GND | GND | 共地 |
| SCL | PB6 / I2C1_SCL | I2C时钟 |
| SDA | PB7 / I2C1_SDA | I2C数据 |
| INT | PA1 / TIM2_CH2 | 100Hz DATA_RDY硬件时间捕获 |

## 4. C099-F9P与STM32/Pi

| C099-F9P | 方向 | 目标 | 用途 |
|---|---:|---|---|
| TX_ZED | → | STM32 PA3 / USART2_RX | UBX导航、RAWX和SFRBX |
| RX_ZED | ← | STM32 PA2 / USART2_TX | F9P配置和RTCM输入 |
| TP | → | STM32 PA0 / TIM2_CH1 | 1PPS/TIMEPULSE捕获 |
| TX_ZED分支 | → | Pi Pin 29 / GPIO5 | 原始UBX旁路监听 |
| GND | ↔ | 公共GND | 信号参考地 |

`TX_ZED`由一个3.3V发送端驱动PA3和GPIO5两个高阻输入。当前现场GPIO5分支直接
连接、没有串联电阻；GPIO5必须始终配置为输入。重做线束时可在Pi分支串联
330Ω～1kΩ保护电阻。

C099 J4只短接`ARD`位置，即7-8脚。不要同时短接`UART1`或`UART3`，避免多个
发送端共同驱动F9P RX。

## 5. ST-Link

| ST-Link | STM32 | 说明 |
|---|---|---|
| SWDIO | SWIO / PA13 | 调试数据 |
| SWCLK | SWCLK / PA14 | 调试时钟 |
| GND | GND | 必须共地 |
| NRST | NRST | 可选但推荐 |
| 3.3V、5V | 不连接 | STM32已由固定5V支路供电 |

BOOT0保持0。烧录时先给系统正常供电，再插ST-Link USB；不要把ST-Link电源与
外部稳压输出并联。

## 6. 一张表检查全部连接

```text
VADJ 5.10～5.20V → Pi Pin 2、Pin 4
电源GND          → Pi Pin 6、Pin 9
固定5V           → STM32 5V
固定5V           → C099 DC_IN 5-12V
公共GND          ↔ Pi、STM32、MPU6050、C099

Pi Pin 8  TXD0   → STM32 PA10
Pi Pin 10 RXD0   ← STM32 PA9
Pi Pin 29 GPIO5  ← C099 TX_ZED分支

MPU VCC/GND      → STM32 3.3V/GND
MPU SCL/SDA/INT  → PB6/PB7/PA1
C099 TP          → PA0
C099 TX_ZED      → PA3
C099 RX_ZED      ← PA2
C099 J4          = 仅ARD 7-8
```

## 7. 上电顺序

1. 全部断电，检查极性、共地、BOOT0和J4。
2. Pi断开，调VADJ到5.10～5.20V并确认不超过5.25V。
3. 连接Pi，先不插ST-Link和其他USB供电。
4. 上电后在Pi Pin 2/4对Pin 6/9测带载电压。
5. 测STM32 3.3V输出、确认C099启动且所有设备无异常发热。
6. 执行`vcgencmd get_throttled`；正式采集要求`0x0`。
7. 再检查串口服务和数据频率。

