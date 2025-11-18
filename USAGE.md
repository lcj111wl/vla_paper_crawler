# 使用说明

## 快速开始

### 1. 配置
编辑 `config_lcj.json`：
- `notion_token`: 你的 Notion API Token
- `database_id`: 你的 Notion 数据库 ID
- `days_back`: 爬取最近 N 天的论文（默认 7）
- `max_papers`: 最多爬取论文数（默认 999）

### 2. 运行
```bash
python paper_crawler.py config_lcj.json
```

### 3. 自动每日更新
```bash
# 1. 编辑 crontab
crontab -e

# 2. 添加定时任务（每天早上 9:00）
0 9 * * * /media/lcj/a/Mcp/vla_paper_crawler/run_daily.sh >> /media/lcj/a/Mcp/vla_paper_crawler/cron.log 2>&1

# 3. 保存退出
```

详细说明见 `DAILY_UPDATE.md`

### 3. 上传图片
```bash
python open_for_upload.py
```
自动打开 Notion 数据库和 images/ 文件夹，拖拽图片到 "Framework Image"。

## 时间范围配置

常用设置：
- `days_back: 7` - 最近1周
- `days_back: 14` - 最近2周  
- `days_back: 30` - 最近1个月
- `days_back: 90` - 最近3个月

## 严格 VLA 过滤

爬虫会自动进行二次过滤，论文必须满足以下条件之一：

1. **明确包含** "Vision-Language-Action"（任意连字符形式）
2. **包含 VLA** 且明确是以下上下文之一：
   - "VLA model"
   - "VLA policy"
   - "VLA agent"
   - "VLA robot"
   - "VLA framework"
   - "VLA architecture"
3. **完整短语** "vision language action"

配置关键词仅用于初步搜索，实际过滤由代码内置逻辑严格控制。

## 框架图提取策略

- **置信度阈值**：0.6（只保留高置信度架构图）
- **数量限制**：每篇论文默认 1 张（最可能的框架图）
- **搜索范围**：论文前 10 页
- **过滤尺寸**：宽/高 > 200px

## 文件命名

图片文件名格式：`论文标题_fig1_p页码_时间戳.png`

例如：`Audio-VLA__Adding_Contact_Audio_Perception_to_Visi_fig1_p3_1731846789012.png`
