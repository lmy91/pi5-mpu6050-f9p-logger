# 软件更新 SOP：PC 开发 → GitHub 发布 → 树莓派更新

适用仓库：`https://github.com/lmy91/pi5-mpu6050-f9p-logger.git`。
PC 路径：`C:\Users\12597\Desktop\lowcost\pi5-mpu6050-f9p-logger`。
树莓派路径：`/home/lmy/pi5-mpu6050-f9p-logger`，SSH 别名：`pi5-ics`。

`main` 只接收已测试、准备部署的版本。树莓派从 GitHub 获取代码，不直接编辑已跟踪源码，
不再使用 `scripts/deploy_to_pi.sh` 的 SCP 覆盖方式。下面每一阶段按顺序执行；
任何命令失败先处理错误，不继续发布或启动失败的新版本。
本 SOP 更新树莓派采集和网页软件；STM32 固件须按 `FIRMWARE_FLASH.md` 单独烧录，
`git pull` 不会自动更新 STM32。

## 1. PC：准备开发环境（首次执行）

在 **Windows PowerShell** 中执行。当前电脑的 `python` 命令是商店占位符，
可用已安装的工作区 Python 创建项目虚拟环境；其他电脑可用已安装的 Python 3.10+ 替代该路径。
前端语法检查还需要 Node.js。

```powershell
Set-Location C:\Users\12597\Desktop\lowcost\pi5-mpu6050-f9p-logger
$Python = 'C:\Users\12597\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $Python -m venv .venv
if ($LASTEXITCODE -ne 0) { throw '创建 Python 环境失败' }
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw '安装依赖失败' }
node --version
```

`.venv/` 已被 Git 忽略，无需激活环境，后续直接使用其中的 Python。

## 2. PC：同步基线并修改代码

开始新一轮开发前执行；若已有未提交工作，先保存并提交这些工作，不直接切分支或覆盖。

```powershell
Set-Location C:\Users\12597\Desktop\lowcost\pi5-mpu6050-f9p-logger
git status --short
git switch main
git pull --ff-only origin main
```

在此基础上修改代码。`git pull` 报分支分叉时停止，先审查和合并历史；不要强制重置。

## 3. PC：测试与检查

以下代码块可整体粘贴到 PowerShell，失败时会停止该块。

```powershell
& {
    $ErrorActionPreference = 'Stop'
    Set-Location C:\Users\12597\Desktop\lowcost\pi5-mpu6050-f9p-logger
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw '依赖安装失败' }
    .\.venv\Scripts\python.exe -m unittest tools.test_capture_serial raspberry_pi5.test_live_dashboard raspberry_pi5.test_gnss_time_sync raspberry_pi5.test_ntrip_client
    if ($LASTEXITCODE -ne 0) { throw '测试失败，禁止发布' }
    .\.venv\Scripts\python.exe -m py_compile tools/capture_serial.py raspberry_pi5/live_dashboard.py raspberry_pi5/ntrip_client.py raspberry_pi5/gnss_time_sync.py
    if ($LASTEXITCODE -ne 0) { throw 'Python 语法检查失败' }
    node --check raspberry_pi5/live_dashboard/app.js
    if ($LASTEXITCODE -ne 0) { throw '前端语法检查失败' }
    git diff --check
    if ($LASTEXITCODE -ne 0) { throw '差异检查失败' }
    git diff --stat
    git diff
}
```

修改串口协议、硬件交互或网页行为时，还需验证对应功能；单元测试通过不等于硬件采集验证完成。

## 4. PC：提交并发布稳定版本

先暂存本次相关文件。下面以时间回溯修复为例，其他任务按实际文件修改列表：

```powershell
git add tools/capture_serial.py raspberry_pi5/live_dashboard.py raspberry_pi5/live_dashboard/app.js raspberry_pi5/test_live_dashboard.py
git diff --cached --stat
git diff --cached
```

若同时更新本 SOP，可额外暂存对应文档：

```powershell
git add docs/SOFTWARE_UPDATE_SOP.md docs/PI_SETUP.md docs/README.md README.md scripts/README.md scripts/deploy_to_pi.sh
```

检查暂存内容无采集数据、账号密码或密钥后执行，提交说明按实际改动填写：

```powershell
git commit -m "fix: prevent dashboard time rollback"
git fetch origin
git log --oneline origin/main..HEAD
git status -sb
```

日志列出此次将推送的**全部**提交，不只是最后一个。若显示 `behind` 或分叉，先整合远端修改并重新测试。
确认提交列表正确后执行：

```powershell
git push origin main
git rev-parse HEAD
git ls-remote origin refs/heads/main
```

最后两条命令显示的完整提交哈希应一致。记下该哈希，作为本次发布版本。
推送失败时不要继续在树莓派部署，不使用强制推送。

## 5. 接网线并检查共享上网

PC 保持 Wi-Fi 联网，网线连接 PC 和树莓派。当前约定地址为 PC `192.168.137.1`、
Pi `192.168.137.2`。在 **PC PowerShell** 执行：

```powershell
Get-NetIPAddress -InterfaceAlias '以太网' -AddressFamily IPv4
ssh pi5-ics
```

未配置别名时使用 `ssh lmy@192.168.137.2`。以下命令在 **SSH 登录后的树莓派终端** 执行：

```bash
ip -br address
ip route
cat /etc/resolv.conf
getent ahostsv4 github.com
curl -I --connect-timeout 5 --max-time 10 https://github.com
cd /home/lmy/pi5-mpu6050-f9p-logger
timeout 15 git ls-remote origin refs/heads/main
```

预期默认网关和 DNS 都是 `192.168.137.1`，Git 能返回远端提交哈希。
只连得上 SSH 不代表可以上网。若失败，在 Windows 运行 `ncpa.cpl`，打开
**WLAN → 属性 → 共享**，取消共享并保存，再重新勾选；如有目标选项，选“以太网”。
没有目标选项时，以以上连通性结果为准。无需关闭防火墙。

## 6. 首次整理之前 SCP 覆盖的修复（只做一次）

2026-09-29 检查时，Pi 的 Git 记录停留在 `f05e56e`，四个修复文件是本地修改，
而 GitHub 已包含这份修复。先执行第 7 节的停止采集步骤，再在 Pi 执行：

```bash
cd /home/lmy/pi5-mpu6050-f9p-logger
git status --short
git diff --stat
git diff --ignore-space-at-eol
```

确认仍只有已发布的那四个修复文件后，先停止服务，再备份修改到 stash，避免运行中更换源码：

```bash
sudo systemctl stop gnss-imu-dashboard.service gnss-imu-logger.service
git stash push -m "backup-before-first-git-update" -- tools/capture_serial.py raspberry_pi5/live_dashboard.py raspberry_pi5/live_dashboard/app.js raspberry_pi5/test_live_dashboard.py
git stash list
git status --short
```

`git status --short` 应无输出，否则先处理剩余修改。备份保存在此 Pi 仓库的 stash 中，
可用 `git stash show -p 'stash@{0}'` 查看最近备份。更新后不要执行 `stash pop`，
否则会把旧修改重新加回工作区。此步骤不清理采集数据或忽略文件。
首次整理后直接执行第 7 节的更新代码块；服务已停止，无需再次调用网页状态接口。

## 7. Pi：停止采集，拉取、测试并启动新版

先停止文件保存，确认网页显示“未保存”：

```bash
gnss-imu-record-stop
curl -fsS http://127.0.0.1:8080/api/status | python3 -c 'import json,sys; s=json.load(sys.stdin); print("recording =", s.get("recording"))'
```

若仍为 `True`，稍等再执行查询；应为 `False` 后继续。首次部署先完成第 6 节。
下面整个代码块在 Pi 的 Bash 终端运行，任一步失败都会停止后续步骤：

```bash
(
set -eu
cd /home/lmy/pi5-mpu6050-f9p-logger
test "$(git branch --show-current)" = main
test -z "$(git status --porcelain)"
git fetch origin
git log --oneline HEAD..origin/main
git merge-base --is-ancestor HEAD origin/main

# 保存更新前版本，供回退使用；打印并记下这个分支名。
backup_branch="backup/pi-before-update-$(date +%Y%m%d-%H%M%S)"
git branch "$backup_branch" HEAD
printf '回退分支：%s\n' "$backup_branch"

sudo systemctl stop gnss-imu-dashboard.service gnss-imu-logger.service
git pull --ff-only origin main
python3 -m unittest tools.test_capture_serial raspberry_pi5.test_live_dashboard raspberry_pi5.test_gnss_time_sync raspberry_pi5.test_ntrip_client
python3 -m py_compile tools/capture_serial.py raspberry_pi5/live_dashboard.py raspberry_pi5/ntrip_client.py raspberry_pi5/gnss_time_sync.py
sudo systemctl start gnss-imu-logger.service gnss-imu-dashboard.service
sleep 3
systemctl is-active gnss-imu-logger.service gnss-imu-dashboard.service
git log -1 --oneline
git status --short
)
```

这会短暂停止实时定位和网页。测试失败时服务保持停止，按第 9 节回退。
两个服务都停止时，`/run/gnss-imu` 内的易失 NTRIP 配置可能被清除；更新前请准备好
基站账号和挂载点，更新后在网页重新连接。不要把这些凭据保存到 Git。
若缺少 `serial`，执行 `sudo apt-get install python3-serial`，随后重新执行测试和启动步骤。
以后若新增依赖，应在发布说明中附上 Pi 的安装命令，不能用系统 `pip` 强行覆盖系统包。

若本次修改了 `systemd/` 模板或服务安装脚本，需要在测试通过后、启动服务前额外运行
`sh scripts/install_services.sh`；普通 Python/前端更新无需重新安装服务。
安装脚本会启动服务并重新触发 GNSS 校时，按该版本说明安排执行。

## 8. Pi：确认版本和功能

```bash
cd /home/lmy/pi5-mpu6050-f9p-logger
git rev-parse HEAD
git ls-remote origin refs/heads/main
systemctl show gnss-imu-logger.service gnss-imu-dashboard.service -p WorkingDirectory -p ExecStart -p ActiveEnterTimestamp
journalctl -u gnss-imu-logger.service -u gnss-imu-dashboard.service -n 60 --no-pager
curl -fsS http://127.0.0.1:8080/api/status | python3 -c 'import json,sys; s=json.load(sys.stdin); print({k:s.get(k) for k in ("service_running","recording","imu_online","online","imu_updated_monotonic_s")})'
```

Pi 的 `HEAD` 应与第 4 节记录的发布哈希一致；若期间又有发布，应核对实际拉取版本。
`service_running` 和有硬件输入时的 `imu_online` 应为 `True`；GNSS 在线状态受实际数据输入影响。
打开 `http://192.168.137.2:8080` 并按 `Ctrl+F5`，确认样本、曲线和采集计时正常。
需要差分定位时，在网页重新连接基站并确认 RTCM 数据持续增长。
确认后按需开始采集：

```bash
gnss-imu-record-start
```

## 9. 新版异常时回退

先停止保存并确认 `recording=False`（见第 7 节），列出保存的回退分支：

```bash
cd /home/lmy/pi5-mpu6050-f9p-logger
git branch --list 'backup/pi-before-update-*'
git status --short
```

选择本次更新前的分支，把下方示例名称替换为实际值。工作区必须干净：

```bash
(
set -eu
cd /home/lmy/pi5-mpu6050-f9p-logger
test -z "$(git status --porcelain)"
sudo systemctl stop gnss-imu-dashboard.service gnss-imu-logger.service
git switch backup/pi-before-update-20260929-120000
sudo systemctl start gnss-imu-logger.service gnss-imu-dashboard.service
systemctl is-active gnss-imu-logger.service gnss-imu-dashboard.service
git log -1 --oneline
)
```

这里切换到旧版本分支，不删除新版提交或采集数据。若升级过服务模板，回退代码后也需重新安装旧模板。
PC 修复并发布之后，Pi 先停止采集和两个服务，执行 `git switch main`，再按第 7 节更新。
不要用 `git reset --hard`、`git clean` 或直接覆盖源码来处理更新冲突。
