# 每日自动更新设置指南

## 方法 1: 使用 Cron（推荐，适用于 Linux/macOS）

### 快速设置（3 步）

1. **打开 crontab 编辑器**
```bash
crontab -e
```

2. **添加定时任务**（在编辑器中添加以下行）
```bash
# 每天早上 9:00 自动运行
0 9 * * * /media/lcj/a/Mcp/vla_paper_crawler/run_daily.sh >> /media/lcj/a/Mcp/vla_paper_crawler/cron.log 2>&1
```

3. **保存并退出**（按 `Esc`，输入 `:wq` 回车）

### 验证设置

查看当前的 cron 任务：
```bash
crontab -l
```

查看运行日志：
```bash
tail -f /media/lcj/a/Mcp/vla_paper_crawler/cron.log
```

### 常用时间设置

```bash
# 每天早上 8:00
0 8 * * * /media/lcj/a/Mcp/vla_paper_crawler/run_daily.sh >> /media/lcj/a/Mcp/vla_paper_crawler/cron.log 2>&1

# 每天中午 12:00
0 12 * * * /media/lcj/a/Mcp/vla_paper_crawler/run_daily.sh >> /media/lcj/a/Mcp/vla_paper_crawler/cron.log 2>&1

# 每天晚上 20:00
0 20 * * * /media/lcj/a/Mcp/vla_paper_crawler/run_daily.sh >> /media/lcj/a/Mcp/vla_paper_crawler/cron.log 2>&1

# 每 12 小时一次（早上 9:00 和晚上 21:00）
0 9,21 * * * /media/lcj/a/Mcp/vla_paper_crawler/run_daily.sh >> /media/lcj/a/Mcp/vla_paper_crawler/cron.log 2>&1

# 每 6 小时一次
0 */6 * * * /media/lcj/a/Mcp/vla_paper_crawler/run_daily.sh >> /media/lcj/a/Mcp/vla_paper_crawler/cron.log 2>&1
```

## 方法 2: 使用 systemd timer（更现代的方式）

### 创建 service 文件

创建 `/etc/systemd/system/vla-crawler.service`：

```ini
[Unit]
Description=VLA Paper Crawler
After=network.target

[Service]
Type=oneshot
User=lcj
WorkingDirectory=/media/lcj/a/Mcp/vla_paper_crawler
ExecStart=/media/lcj/a/Mcp/vla_paper_crawler/run_daily.sh
StandardOutput=append:/media/lcj/a/Mcp/vla_paper_crawler/systemd.log
StandardError=append:/media/lcj/a/Mcp/vla_paper_crawler/systemd.log
```

### 创建 timer 文件

创建 `/etc/systemd/system/vla-crawler.timer`：

```ini
[Unit]
Description=Run VLA Paper Crawler daily
Requires=vla-crawler.service

[Timer]
OnCalendar=daily
OnCalendar=09:00
Persistent=true

[Install]
WantedBy=timers.target
```

### 启用并启动 timer

```bash
sudo systemctl daemon-reload
sudo systemctl enable vla-crawler.timer
sudo systemctl start vla-crawler.timer
```

### 查看状态

```bash
# 查看 timer 状态
sudo systemctl status vla-crawler.timer

# 查看所有 timer
systemctl list-timers

# 查看服务日志
journalctl -u vla-crawler.service -f
```

## 方法 3: 手动定期运行

如果不想设置自动化，可以每天手动运行：

```bash
cd /media/lcj/a/Mcp/vla_paper_crawler
./run_daily.sh
```

或直接运行：
```bash
python paper_crawler.py config_lcj.json
```

## 配置调整

### 修改爬取天数

编辑 `config_lcj.json`，调整 `days_back`：

```json
{
  "days_back": 1,  // 只爬取最近 1 天的论文（推荐每日运行）
  "max_papers": 999
}
```

建议：
- 每日运行：`days_back: 1`
- 每周运行：`days_back: 7`
- 首次运行：`days_back: 30`

## 日志查看

```bash
# 查看爬虫日志
tail -f /media/lcj/a/Mcp/vla_paper_crawler/paper_crawler.log

# 查看 cron 运行日志
tail -f /media/lcj/a/Mcp/vla_paper_crawler/cron.log

# 查看最后运行时间
cat /media/lcj/a/Mcp/vla_paper_crawler/last_run.log
```

## 故障排查

### Cron 任务没有运行

1. **检查 cron 服务是否运行**
```bash
systemctl status cron  # 或 crond
```

2. **检查脚本权限**
```bash
ls -l run_daily.sh  # 应该有 x 权限
```

3. **手动运行脚本测试**
```bash
./run_daily.sh
```

4. **查看系统日志**
```bash
grep CRON /var/log/syslog  # Ubuntu/Debian
grep CRON /var/log/cron    # CentOS/RHEL
```

### Python 环境问题

如果 cron 环境下找不到 Python，修改 `run_daily.sh`：

```bash
# 使用绝对路径
/usr/bin/python3 paper_crawler.py config_lcj.json

# 或指定虚拟环境
source /path/to/venv/bin/activate
python paper_crawler.py config_lcj.json
```

## 推荐配置

**每天早上 9:00 自动更新，只爬取最近 1 天的论文**

1. `config_lcj.json`:
```json
{
  "days_back": 1
}
```

2. Crontab:
```bash
0 9 * * * /media/lcj/a/Mcp/vla_paper_crawler/run_daily.sh >> /media/lcj/a/Mcp/vla_paper_crawler/cron.log 2>&1
```

这样可以确保：
- ✅ 每天自动运行
- ✅ 不会重复爬取旧论文
- ✅ 及时获取最新论文
- ✅ 日志可查
