# 固定固件发布文件

本目录保存无需本地编译即可烧录的STM32F103C8T6固件，对应仓库稳定版源码。

| 文件 | 用途 | SHA-256 |
|---|---|---|
| `mpu6050_f9p_navigation.hex` | STM32CubeProgrammer或其他烧录器使用的Intel HEX | `7904f69d733e5f18a93080db8c175abfc64a8a860eef29a23214c03ba705498c` |
| `mpu6050_f9p_navigation.elf` | 烧录、符号调试和反汇编 | `00318bc5386d320f7c43f5f0fb7c74ba3b0ca0991ba7f4072e95677e17d805ba` |

完整ST-Link接线和图形/命令行烧录步骤见
[`docs/FIRMWARE_FLASH.md`](../docs/FIRMWARE_FLASH.md)。发布文件必须来自干净的
`Release`构建；重新编译后应同时替换ELF和HEX、更新上表校验值、运行主机端协议
测试，并在实机验证100 Hz IMU、1 Hz GNSS/RAWX与RTCM转发后再提交。

发布文件对应的固件基线与上游提交记录在根目录
[`UPSTREAM_VERSION`](../UPSTREAM_VERSION)。同步固件源码后必须重新编译并更新本目录
的 HEX/ELF，保证产物与源码来自同一提交，避免烧录到过期二进制。

