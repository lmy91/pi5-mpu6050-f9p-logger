# STM32固件构建与烧录

## 预编译文件

优先使用：

```text
release/mpu6050_f9p_navigation.hex
release/mpu6050_f9p_navigation.elf
```

固件目标为STM32F103C8T6，HSE 8MHz、系统72MHz。USART1为460800 bit/s，
USART2为115200 bit/s；IMU约100Hz，GNSS/RAWX/SAT约1Hz。

## STM32CubeProgrammer图形界面

1. 按[接线说明](WIRING.md)连接ST-Link，BOOT0=0。
2. 打开STM32CubeProgrammer，接口选择ST-LINK/SWD。
3. Connect后选择HEX或ELF。
4. 勾选下载后校验，执行Download。
5. 完成后复位或重新上电。

## Windows命令行烧录

根据实际版本修改程序路径：

```powershell
& "$env:LOCALAPPDATA\stm32cube\bundles\programmer\2.23.0\bin\STM32_Programmer_CLI.exe" `
  -c port=SWD mode=UR reset=HWrst `
  -w ".\release\mpu6050_f9p_navigation.elf" -v -rst
```

若连接失败，检查SWIO/SWCLK是否反接、GND是否连接、目标板是否已供电，并降低
SWD频率。不要用ST-Link 3.3V和外部5V同时给目标板供电。

## 从源码构建

需要CMake、Ninja和GNU Arm Embedded Toolchain：

```powershell
Set-Location .\firmware
cmake --preset Release
cmake --build --preset Release
```

输出位于`firmware/build/Release/mpu6050_f9p_navigation.elf`。生成HEX：

```powershell
arm-none-eabi-objcopy -O ihex `
  .\firmware\build\Release\mpu6050_f9p_navigation.elf `
  .\release\mpu6050_f9p_navigation.hex
```

## 固件启动后的输出

PA9输出纯ASCII协议v3：`IMU`、`GNSS`、`SAT/SAT_END`、
`RAWX/RAWX_MEAS/RAWX_END`及以`#`开头的诊断行。STM32启动时把F9P UART1
配置成115200 bit/s、UBX输出和RTCM3输入，并启用PVT、SAT、RAWX、TIM-TP和
SFRBX相关数据。F9P原始SFRBX不转换为ASCII，由Pi GPIO5旁路保存。

针对实机使用的F9P HPG 1.13，固件会先关闭再开启UART1的SFRBX输出。该版本可能
出现配置回读为1但消息调度器未实际启动的状态；明确的关闭/开启序列可重新启动调度，
且已经用断电后自动配置、UBX帧统计和`convbin`生成RINEX导航文件验证。
