# VLA Paper Crawler - 快速开始

## 服务器一键部署

### 方式一：自动化部署（推荐）

```bash
# 1. 克隆仓库
git clone <your-repo-url> vla_paper_crawler
cd vla_paper_crawler

# 2. 运行部署脚本
bash setup.sh

# 3. 编辑配置（填入你的 API 密钥）
nano .env

# 4. 测试运行
./test_quick.sh

# 5. 正式运行
./run.sh
```

### 方式二：手动部署

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env
nano .env  # 填入 NOTION_TOKEN, DATABASE_ID, OPENAI_API_KEY

# 3. 生成配置
envsubst < config.template.json > config.json

# 4. 运行
python3 paper_crawler.py config.json
```

---

## 关键配置说明

### 必填项（`.env`）
```env
NOTION_TOKEN=ntn_xxxxx          # Notion 集成 Token
DATABASE_ID=xxxxxxxx            # Notion 数据库 ID
OPENAI_API_KEY=sk-xxxxx         # 大模型 API Key
```

### 性能配置（`config.json`）
```json
{
  "days_back": 7,              // 抓取最近N天
  "llm_max_papers": 20,        // 大模型评分数量（控制费用）
  "llm_use_full_pdf": true,    // 是否解析完整PDF
  "llm_pdf_max_pages": 30      // PDF最多读取页数
}
```

---

## 常用命令

```bash
# 手动运行
./run.sh

# 快速测试（3天、5篇）
./test_quick.sh

# 查看日志
tail -f paper_crawler.log

# 查看定时任务
crontab -l

# 停止运行中的进程
pkill -f paper_crawler.py
```

---

## 定时任务

部署脚本会自动添加每天凌晨2点运行的定时任务：

```bash
# 查看当前定时任务
crontab -l

# 编辑定时任务
crontab -e

# 示例：每天早上8点运行
0 8 * * * cd /path/to/vla_paper_crawler && ./run.sh >> logs/cron.log 2>&1
```

---

## 故障排查

### PDF 解析失败
```bash
pip install PyMuPDF
```

### 大模型 API 限流
调整 `config.json`：
```json
{
  "llm_call_interval_s": 2.0,
  "llm_max_papers": 10
}
```

### Notion 连接失败
- 检查 Token 是否正确
- 确认数据库已授权给集成

---

## 完整文档

详细配置、功能说明、性能优化等请查看：
- 📖 [完整部署文档](README_DEPLOY.md)
- 🔧 [配置文件说明](config.template.json)
- 📝 [环境变量示例](.env.example)

---

## 目录结构

```
vla_paper_crawler/
├── setup.sh              # 一键部署脚本 ⭐
├── run.sh                # 运行脚本 ⭐
├── test_quick.sh         # 快速测试 ⭐
├── paper_crawler.py      # 主程序
├── config.template.json  # 配置模板
├── .env.example         # 环境变量示例
├── requirements.txt      # Python 依赖
└── README_DEPLOY.md     # 完整文档
```

---

## 核心特性

✅ **智能过滤**：严格的 VLA 相关性检测  
✅ **深度评分**：大模型解析完整 PDF 后打分（0-100）  
✅ **自动化**：定时运行，自动写入 Notion  
✅ **多数据源**：arXiv + Semantic Scholar  
✅ **高度可配置**：灵活控制性能与费用
