# Navicat Trial Reset for macOS

用于尝试重置 Navicat Premium 本地试用状态的个人脚本，提供 macOS 定时检查、进程检测和文件备份。运行代码采用 Python 标准库，无第三方 Python 依赖。

本项目处理本地文件，**不生成许可证、不提供官方授权，也不等同于永久激活**。是否重新获得试用期，以应用实际显示为准；单机验证结果不保证其他版本或今后更新仍然有效。

## 已验证的范围

| 项目 | 已取得的证据 | 证据边界 |
| --- | --- | --- |
| 实机环境 | 2026-11-23，macOS 26.3.1、arm64、Navicat Premium 18.0.5 | 仅此环境，不代表全部 macOS 或 Navicat 版本 |
| 首次处理 | 应用从“试用已到期”变为显示“剩余 14 天”，点击 Trial 后进入主界面 | 这是试用状态变化，不是正式许可证激活 |
| 本仓库实现 | 安装仓库代码后手动调用同一文件处理函数，再次启动显示“剩余 14 天”，进入主界面 | 单次实机执行，不是等待 13 天触发的长期运行验证 |
| 数据库连接 | 处理后原有连接名称仍显示在列表 | 未逐个验证连接、保存的密码及全部偏好；不能据此保证所有设置无损 |
| 定时安装 | LaunchAgent 已加载，检查进程退出码为 0 | 不代表未来每次处理有效，也不代表已经走完一个 13 天周期 |
| 自动化测试 | 临时合成文件验证周期判断、进程等待、目标范围、备份、失败时的时间戳及安装/卸载 | 安装测试模拟 launchctl；测试通过不等于应用授权或外部环境验收 |

上述均为维护者本机观察，不是 Navicat 官方兼容性声明。未修改系统时间，也未验证无限期重复执行。人工触发后的新一轮 13 天周期尚未经过实际时间验证。

## 安装定时任务

需要 macOS、可用的 `/usr/bin/python3`、Git，以及当前登录的桌面用户会话。请使用当前用户执行，不要使用 `sudo`。本仓库使用 macOS 用户级 LaunchAgent，不支持 Windows 或 Linux。

```bash
git clone https://github.com/yangshuxin199393/navicat-trial-reset.git
cd navicat-trial-reset
/usr/bin/python3 install.py
```

安装行为：

- 首次安装从安装时刻开始计时，安装本身不立即处理 Navicat 文件。
- 重复安装保留现有周期起点；覆盖同名旧脚本和任务文件前，将它们备份在本机。
- LaunchAgent 设置 `StartInterval=3600` 和 `RunAtLoad=true`。每次检查距周期起点是否已满 `13 × 24` 小时，达到阈值才尝试处理。
- 检测到匹配的 Navicat Premium 进程时跳过本次处理，后续检查再尝试，不强制退出应用。
- 实际执行时间受登录、睡眠、关机及系统调度影响，不承诺精确到某一时刻。登录后会检查；持续运行的 Navicat 会使处理继续顺延。
- 文件处理完成后更新周期起点。程序不读取应用界面验证试用效果，因此这个时间戳不是“授权成功”记录。

状态文件沿用名称 `last-success`：首次安装时保存安装时间，此后保存上次目标文件处理完成的时间。安装或文件处理失败可能留下已完成的部分操作，应检查错误日志和备份后再处理，不能把报错理解为完全没有改动。

## 查看状态和日志

```bash
"$HOME/Library/Application Support/NavicatReferenceTimer/Run.sh" --status
tail -n 30 "$HOME/Library/Application Support/NavicatReferenceTimer/run.log"
tail -n 30 "$HOME/Library/Application Support/NavicatReferenceTimer/error.log"
launchctl print "gui/$(id -u)/com.shuxin.navicat-reference-reset"
```

`--status` 和 `--dry-run` 只报告到期判断、下次阈值时间及进程检测结果，不修改 Navicat 文件；它们可能创建本任务的锁文件。`due=false` 只表示未达到阈值，`mode=read_only` 不表示应用已激活。

## 修改范围与恢复

每次处理仅尝试把下面的目标文件移动到独立备份目录：

- `~/Library/Preferences/com.navicat.NavicatPremium.plist`，存在时处理整个文件，因此偏好设置会受到影响。
- `~/Library/Application Support/PremiumSoft CyberTech/Navicat CC/Navicat Premium/` 目录中，文件名精确匹配 `.[0-9A-Z]{32}` 的普通文件。

程序不遍历删除连接目录、不修改 Navicat 程序包，也不修改 macOS 时钟或安全设置。文件处理逻辑存在执行前的进程检查，但没有与 Navicat 共用互斥锁；执行过程中启动应用仍可能发生并发访问。请在处理期间保持应用关闭。

备份路径：

```text
~/Library/Application Support/NavicatReferenceTimer/reset-backups/
```

每次独立建目录，`manifest.json` 记录计划处理的原路径，实际存在的备份文件表示已移动的对象。移动是逐文件操作，不是事务；中途失败可能只移走部分文件，失败时不推进周期起点。

恢复前退出 Navicat，并先停用定时任务（见下方卸载命令），避免恢复后再次到期处理。随后核对备份中的实际文件，按清单复制回原路径；这会覆盖当前对应文件。恢复可能同时还原偏好及原试用状态，效果需重新打开应用检查。程序不提供一键恢复，也不自动清理备份。

备份可能含数据库连接相关配置或其他敏感信息，不应上传到 GitHub 或提交到 issue。仓库的忽略规则只是辅助，提交前仍需核对实际文件。

## 卸载定时任务

```bash
/usr/bin/python3 install.py --uninstall
```

卸载移除同名 LaunchAgent，保留本地脚本、日志、周期起点及备份；不恢复或修改 Navicat 文件。

## 开发验证

```bash
/usr/bin/python3 -m unittest discover -s tests -v
```

测试使用临时合成文件，不操作真实 Navicat 配置。修改定时或文件逻辑后，应同时核对说明中的行为范围；实机观察和测试结果请分别记录。提交 issue 时提供版本、固定错误信息和复现步骤，不要附连接配置、密码或原始备份。

## 来源和许可

实现参考了 [pretend-m/navicat_for_mac_reset](https://github.com/pretend-m/navicat_for_mac_reset) 公开描述的目标文件及处理思路。本仓库不分发上游脚本副本，来源与许可核对见 [NOTICE.md](NOTICE.md)。

本仓库维护者编写的代码和文档采用 [MIT License](LICENSE)，允许依许可证使用、修改和分发，须保留版权与许可声明。此许可不授予 Navicat 软件的使用权，不改变其许可条款，也不表示获得上游项目或 Navicat 官方认可。使用者须自行确认对目标软件和环境的操作权限；项目按 MIT 条款以现状提供。
