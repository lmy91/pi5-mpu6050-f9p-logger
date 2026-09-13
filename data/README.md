# 数据目录

本目录只保存采集器产生的数据，不放程序配置或长期密钥。实际会话位于
[`decoded/`](decoded/README.md)，每次开始保存都会建立一个独立的时间戳目录。

## 使用方式

```bash
gnss-imu-record-start   # 新建会话并开始写文件
gnss-imu-record-stop    # 刷新、关闭文件，定位服务继续运行
gnss-imu-analyze        # 分析最新会话
```

历史数据可能很大，默认不提交到Git。复制、压缩或删除数据前应先停止保存；清理时
优先使用`gnss-imu-clear-data`，它只处理名称符合规则的会话目录并要求确认。

