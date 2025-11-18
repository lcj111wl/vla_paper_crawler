# VLA 论文爬虫 - 自动化运行完整指南

## 🚀 快速开始

### 1. 一键设置自动运行

```bash
# 编辑 crontab
crontab -e

# 添加以下行（每天早上 9:00 自动运行）
0 9 * * * /media/lcj/a/Mcp/vla_paper_crawler/run_daily.sh

# 保存退出（Vim: Esc + :wq, Nano: Ctrl+X + Y）
```

### 2. 测试运行

```bash
# 手动运行一次测试
./run_daily.sh

# 查看运行状态
./check_status.sh

# 实时查看日志
./view_log.sh
```

## 📁 文件说明

### 脚本文件

- **`run_daily.sh`** - 主运行脚本
  - 自动激活 conda 环境
  - 运行爬虫并记录日志
  - 保存运行状态
  - 自动清理 30 天前的旧日志

- **`view_log.sh`** - 实时查看日志
  - 实时跟踪最新日志
  - 按 Ctrl+C 退出

- **`check_status.sh`** - 查看运行状态
  - 显示最后运行状态
  - 列出历史日志文件
  - 显示日志目录大小

### 日志文件

- **`logs/latest.log`** - 最新运行日志（符号链接）
- **`logs/daily_YYYY-MM-DD.log`** - 每日日志（按日期命名）
- **`status.json`** - 运行状态文件（JSON 格式）

## 🎯 使用方法

### 查看日志

```bash
# 实时查看最新日志（推荐）
./view_log.sh

# 或使用 tail 命令
tail -f logs/latest.log

# 查看完整日志
cat logs/latest.log

# 查看特定日期的日志
cat logs/daily_2025-11-17.log
```

### 查看状态

```bash
# 查看运行状态和历史
./check_status.sh

# 查看 JSON 状态文件
cat status.json
```

### 手动运行

```bash
# 手动运行爬虫
./run_daily.sh

# 运行后查看日志
./view_log.sh
```

## ⏰ Cron 定时任务配置

### 推荐配置

```bash
# 每天早上 9:00（推荐）
0 9 * * * /media/lcj/a/Mcp/vla_paper_crawler/run_daily.sh

# 每天早上 8:00
0 8 * * * /media/lcj/a/Mcp/vla_paper_crawler/run_daily.sh

# 每天中午 12:00
0 12 * * * /media/lcj/a/Mcp/vla_paper_crawler/run_daily.sh

# 每天晚上 20:00
0 20 * * * /media/lcj/a/Mcp/vla_paper_crawler/run_daily.sh

# 每 12 小时一次（早 9 和晚 21）
0 9,21 * * * /media/lcj/a/Mcp/vla_paper_crawler/run_daily.sh

# 每 6 小时一次
0 */6 * * * /media/lcj/a/Mcp/vla_paper_crawler/run_daily.sh
```

### Cron 管理命令

```bash
# 查看当前的 cron 任务
crontab -l

# 编辑 cron 任务
crontab -e

# 删除所有 cron 任务
crontab -r

# 查看 cron 服务状态
systemctl status cron    # Ubuntu/Debian
systemctl status crond   # CentOS/RHEL
```

## 📊 日志格式

### 日志内容示例

```
==========================================
开始运行: 2025-11-17 09:00:00
==========================================
✓ 已激活 conda 环境: vla_paper_crawler

正在运行爬虫...
2025-11-17 09:00:01 - INFO - 开始执行论文爬取任务
2025-11-17 09:00:02 - INFO - 正在搜索 arXiv: ...
2025-11-17 09:00:10 - INFO - 从 arXiv 找到 5 篇论文
2025-11-17 09:00:15 - INFO - 成功添加 2 篇新论文到 Notion

==========================================
✓ 运行成功
结束时间: 2025-11-17 09:00:20
==========================================
```

### 状态文件格式（status.json）

```json
{
  "last_run": "2025-11-17 09:00:00",
  "end_time": "2025-11-17 09:00:20",
  "status": "success",
  "exit_code": 0,
  "log_file": "/media/lcj/a/Mcp/vla_paper_crawler/logs/daily_2025-11-17.log"
}
```

## 🛠️ 维护管理

### 日志清理

```bash
# 自动清理（脚本会自动删除 30 天前的日志）
# 无需手动操作

# 手动清理 30 天前的日志
find logs -name "daily_*.log" -mtime +30 -delete

# 清理 7 天前的日志
find logs -name "daily_*.log" -mtime +7 -delete

# 查看日志目录大小
du -sh logs/

# 列出所有日志文件
ls -lh logs/
```

### 故障排查

#### 1. Cron 没有运行

```bash
# 检查 cron 服务
systemctl status cron

# 启动 cron 服务
sudo systemctl start cron

# 查看系统日志
grep CRON /var/log/syslog | tail -20
```

#### 2. 脚本权限问题

```bash
# 确保脚本有执行权限
chmod +x run_daily.sh view_log.sh check_status.sh

# 检查权限
ls -l *.sh
```

#### 3. Python 环境问题

编辑 `run_daily.sh`，取消注释并修改 conda 路径：

```bash
# 修改为你的实际路径
source ~/anaconda3/etc/profile.d/conda.sh
conda activate vla_paper_crawler
```

#### 4. 查看错误日志

```bash
# 查看最新日志
cat logs/latest.log

# 搜索错误信息
grep -i error logs/latest.log
grep -i failed logs/latest.log

# 查看 Python 错误
grep -A 5 "Traceback" logs/latest.log
```

## 📈 监控建议

### 设置邮件通知（可选）

在 crontab 顶部添加：

```bash
MAILTO=your_email@example.com

0 9 * * * /media/lcj/a/Mcp/vla_paper_crawler/run_daily.sh
```

### 使用 systemd timer（高级）

如果想要更现代的定时任务管理，参考 `DAILY_UPDATE.md` 中的 systemd timer 配置。

## 🎨 自定义配置

### 修改运行时间

编辑 `config_lcj.json`：

```json
{
  "days_back": 2,      // 爬取最近 2 天的论文
  "max_papers": 999    // 最多爬取论文数
}
```

建议：
- 每日运行：`days_back: 2`（有 1 天重叠，防止遗漏）
- 每周运行：`days_back: 7`
- 首次运行：`days_back: 30`

### 修改日志保留时间

编辑 `run_daily.sh`，修改清理命令：

```bash
# 保留 60 天
find "${LOG_DIR}" -name "daily_*.log" -mtime +60 -delete

# 保留 7 天
find "${LOG_DIR}" -name "daily_*.log" -mtime +7 -delete
```

## 📱 实时监控

### 方法 1: watch 命令

```bash
# 每 2 秒刷新状态
watch -n 2 './check_status.sh'
```

### 方法 2: 终端分屏

```bash
# 使用 tmux 或 screen 分屏查看
tmux new-session './view_log.sh' \; split-window -h './check_status.sh'
```

### 方法 3: Web 日志查看（可选）

```bash
# 使用 Python 简单 HTTP 服务器
cd logs
python -m http.server 8000

# 然后在浏览器访问: http://localhost:8000
```

## ✅ 完整工作流程

```bash
# 1. 首次设置
crontab -e
# 添加: 0 9 * * * /media/lcj/a/Mcp/vla_paper_crawler/run_daily.sh

# 2. 测试运行
./run_daily.sh

# 3. 查看状态
./check_status.sh

# 4. 实时监控（可选）
./view_log.sh

# 5. 日常检查（每周一次）
./check_status.sh
```

现在你的 VLA 论文爬虫会每天自动运行，所有日志都会保存，可以随时实时查看！🎉
