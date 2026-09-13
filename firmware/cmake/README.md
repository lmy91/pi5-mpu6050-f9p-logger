# CMake配置片段

本目录把交叉编译设置拆成若干小文件，由上一级`CMakeLists.txt`依次包含，不应单独
执行。

| 文件 | 功能 |
|---|---|
| `target.cmake` | 目标芯片、CPU、浮点ABI和链接脚本变量 |
| `gcc-arm-none-eabi.cmake` | GNU Arm交叉编译器及二进制工具链 |
| `flags.cmake` | C/ASM编译选项、链接选项和构建类型参数 |
| `files.cmake` | 固件源文件清单 |
| `components.cmake` | 预留组件/库配置入口 |

## 使用方式

在`firmware`目录执行：

```bash
cmake --preset Debug
cmake --build --preset Debug
```

发布构建把`Debug`替换为`Release`。如果新增`.c`或`.S`文件，应先更新
`files.cmake`；更换MCU或存储布局还需同时核对`target.cmake`和上一级链接脚本。
生成的`build/`目录不进入Git。

