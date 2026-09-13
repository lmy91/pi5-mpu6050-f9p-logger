# 网页前端

这是树莓派实时监控页面的静态资源目录，不使用npm、打包器或前端框架；
`live_dashboard.py`会直接提供这些文件。

| 文件 | 功能 |
|---|---|
| `index.html` | 页面结构：状态、轨迹、IMU曲线、天空图、地图/NTRIP设置和命令窗口 |
| `style.css` | 桌面与手机响应式布局、状态颜色和绘图容器样式 |
| `app.js` | 状态轮询、Canvas绘图、高德地图、采集计时、按钮与命令交互 |

## 使用方式

服务安装后，在同一局域网打开：

```text
http://<树莓派IP>:8080
```

前端定期读取`/api/status`、`/api/track`和`/api/imu`，通过受限POST接口开始/停止
保存以及控制基站。未保存时轨迹只显示当前点；开始保存后累计本次会话轨迹，并显示
采集时长。页面中的“命令行”仅支持后端白名单，不是任意Shell。

## 修改与调试

修改后无需编译：

```bash
sudo systemctl restart gnss-imu-dashboard.service
```

浏览器若仍显示旧代码，执行强制刷新或关闭页面后重新打开。开发时可运行
`python3 raspberry_pi5/live_dashboard.py --host 127.0.0.1 --port 8080`，然后访问
`http://127.0.0.1:8080`。新增API或字段时必须同步修改后端、`app.js`和测试。

高德Key和`securityJsCode`只能通过浏览器设置或用户目录配置加载，不得写入这些
静态文件。网页没有公网身份认证，只允许部署在可信局域网或设备热点。

