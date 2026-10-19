# 完整接线与上电检查

## 1. 电源

2026-10-19 更新：树莓派已改用 USB Type-C 接口供电，原接到物理 Pin 2、Pin 4 的两根 5V 杜邦线均已移除。STM32 和 C099 继续由外部降压模块独立分路供电，所有设备共地，不让树莓派给其他设备转供电。本文 Pin 编号均为 40 针排针的物理编号。

| 电源端 | 设备端 | 说明 |
|---|---|---|
| Type-C 电源 | Pi USB-C 电源口 | Pi 当前主电源 |
| VADJ → Pi Pin 2 / 5V | 已断开 | 第一根 5V 杜邦线已移除 |
| VADJ → Pi Pin 4 / 5V | 已断开 | 第二根 5V 杜邦线已移除 |
| GND | Pi Pin 6 / GND | 原共地线保留 |
| GND | Pi Pin 9 / GND | 原共地线保留 |
| 固定5V | STM32 5V | 独立支路 |
| 固定5V | C099 DC_IN 5-12V | 独立支路 |
| GND | STM32 GND、C099 GND | 全系统共地 |

Type-C 供电时，VADJ 和固定 5V 均不得再接 Pi Pin 2/4，避免两个电源输出并联；拆下的线头须绝缘固定。Pi 上电后 Pin 2/4 仍带 5V，不能把它们当作未通电引脚。保留 Pi 与 STM32、C099 的公共地及原信号线。STM32 和 C099 不串在 Pi 的供电引脚后面。

电源及 Type-C 线缆须满足 Pi 5 与外设负载，优先选用 Pi 5 官方 27W（5.1V/5A）电源；现场所用电源型号尚未核实。此前 VADJ/GPIO 供电曾出现欠压。更换 Type-C 后连续约 20 秒、10 次采样为 4.919～4.941V，`get_throttled=0x0`；这是当时负载下的结果，正式记录时仍需复核。

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
Type-C 电源      → Pi USB-C 电源口
VADJ → Pin 2/4   = 两根5V杜邦线已移除，不连接
电源GND          ↔ Pi Pin 6、Pin 9（保留共地）
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

1. 停止记录并等待保存完成，正常关机；断开 Type-C 和 DC 板两路电源后检查接线、共地、BOOT0 和 J4。
2. 确认 Pi Pin 2/4 的两根原 5V 杜邦线均已移除，线头绝缘；保留 Pin 6/9 等公共地。
3. 确认 STM32 和 C099 的固定 5V 独立支路后，接通 DC 板及 Pi Type-C 电源，ST-Link 电源脚不连接。
4. 上电后用 `vcgencmd pmic_read_adc` 检查 `EXT5V_V`；有万用表时可在 Pi Pin 2/4 对 Pin 6/9 测带载电压，这些引脚仅用于测量，不接外部正极。
5. 测STM32 3.3V输出、确认C099启动且所有设备无异常发热。
6. 执行`vcgencmd get_throttled`；正式采集要求`0x0`。
7. 再检查串口服务和数据频率。

需要整机彻底断电时，正常关机后同时断开 Type-C 和 DC 板电源；仅关闭 DC 板不会切断 Pi 的供电。

