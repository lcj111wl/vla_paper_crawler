# VLA 论文爬虫 - 服务器部署指南

一个自动化爬取 Vision-Language-Action (VLA) 领域最新论文的工具，支持：
- 📚 多数据源（arXiv + Semantic Scholar）
- 🤖 大模型深度评分（支持完整 PDF 解析）
- 📊 自动写入 Notion 数据库
- ⏰ 定时自动运行

---

## 快速开始（服务器一键部署）

### 1. 克隆仓库
```bash
git clone <your-repo-url> vla_paper_crawler
cd vla_paper_crawler
```

### 2. 运行部署脚本
```bash
bash setup.sh
```

脚本会自动完成：
- ✅ 检查 Python 环境
- ✅ 安装依赖包
- ✅ 创建配置文件
- ✅ 设置定时任务

### 3. 配置密钥

编辑 `.env` 文件填入你的密钥：
```bash
nano .env
```

必填项：
```env
NOTION_TOKEN=ntn_xxxxx          # Notion 集成 Token
DATABASE_ID=xxxxxxxx            # Notion 数据库 ID
OPENAI_API_KEY=sk-xxxxx         # 大模型 API Key（支持通义千问等）
```

可选项：
```env
LLM_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1  # 通义千问接口
LLM_MODEL=qwen-plus             # 模型名称
OPENALEX_MAILTO=you@email.com   # 用于影响因子查询
```

### 4. 运行

**手动运行：**
```bash
./run.sh
```

**查看日志：**
```bash
tail -f paper_crawler.log
```

**查看定时任务：**
```bash
crontab -l
```

---

## 配置说明

### 核心配置 (`config.json`)

```json
{
  "days_back": 7,              // 抓取最近N天的论文
  "max_papers": 100,           // 最多添加论文数
  "llm_max_papers": 20,        // 大模型评分数量（前N篇）
  "llm_use_full_pdf": true,    // 是否解析完整PDF（推荐开启）
  "llm_pdf_max_pages": 30,     // PDF最多读取页数
  "extract_figures": false     // 是否提取框架图（可选）
}
```

### 大模型评分配置

**使用通义千问多模态（推荐）：**
```json
{
  "llm_provider": "openai-compatible",
  "llm_model": "qwen-vl-plus",  // 支持视觉输入
  "llm_api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
  "llm_pdf_extract_images": true,  // 提取PDF图片
  "llm_pdf_max_images": 10,        // 最多提取10张图片
  "llm_timeout": 120                // 增加超时时间（多模态需要更长）
}
```

**使用通义千问纯文本（兼容）：**
```json
{
  "llm_provider": "openai-compatible",
  "llm_model": "qwen-plus",  // 不支持视觉，只分析文本
  "llm_api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
  "llm_pdf_extract_images": false
}
```

**使用 OpenAI 多模态：**
```json
{
  "llm_provider": "openai",
  "llm_model": "gpt-4o",  // 或 gpt-4-turbo（支持vision）
  "llm_api_base": "https://api.openai.com/v1",
  "llm_pdf_extract_images": true
}
```

---

## 功能特性

### 1. 智能过滤
- 严格的 VLA 相关性检测
- 避免泛化的多模态论文

### 2. 大模型深度评分（多模态）
- **自动下载并解析完整 PDF**（前 30 页文本 + 最多 10 张关键图片）
- **多模态分析**：
  - 提取 PDF 中的架构图、实验结果图、对比图表
  - 自动过滤小图（logo/icon），优先保留大图
  - 将图片转为 base64 发送给支持视觉的大模型（qwen-vl-plus/gpt-4o）
- **5 维度评分**：VLA相关性(30%) + 方法创新性(25%) + 实验严谨性(20%) + 技术深度(15%) + 影响潜力(10%)
- **打分区间**：90-100(突破性) / 75-89(优秀) / 60-74(中等) / 40-59(边缘) / 0-39(不推荐)
- **评分依据**：引用 PDF 具体章节、实验数据、图片分析

### 3. Notion 集成
自动创建以下属性：
- 📝 基础信息：标题、作者、摘要、发布日期、会议/期刊
- 🔗 链接：论文 URL、PDF 链接、DOI
- 🎯 评分：Recommend Score（0-100）、Recommend Rationale（评分依据）
- 🏢 机构：Institutions（多选标签）
- 📊 指标：引用数、影响力引用、影响因子（可选）

---

## 定时任务

### Cron 配置（已自动添加）
```bash
# 每天凌晨 2 点运行
0 2 * * * cd /path/to/vla_paper_crawler && ./run.sh >> logs/cron.log 2>&1
```

### 修改定时任务
```bash
crontab -e
```

### 常用定时示例
```bash
# 每天早上 8 点
0 8 * * * cd /path/to/vla_paper_crawler && ./run.sh

# 每周一凌晨 3 点
0 3 * * 1 cd /path/to/vla_paper_crawler && ./run.sh

# 每 6 小时
0 */6 * * * cd /path/to/vla_paper_crawler && ./run.sh
```

---

## 目录结构

```
vla_paper_crawler/
├── paper_crawler.py        # 主程序
├── figure_extractor.py     # 图片提取器（可选）
├── config.json             # 运行时配置
├── config.template.json    # 配置模板
├── .env                    # 环境变量（不要提交到 Git）
├── .env.example           # 环境变量示例
├── requirements.txt        # Python 依赖
├── setup.sh               # 一键部署脚本
├── run.sh                 # 运行脚本
├── logs/                  # 日志目录
├── images/                # 图片缓存
└── README_DEPLOY.md       # 本文档
```

---

## 故障排查

### 问题 1: 找不到 Python 包
```bash
pip install -r requirements.txt
```

### 问题 2: PDF 解析失败
确保安装了 PyMuPDF：
```bash
pip install PyMuPDF
```

### 问题 3: 大模型 API 限流
调整配置降低频率：
```json
{
  "llm_call_interval_s": 2.0,    // 增加调用间隔
  "llm_max_papers": 10           // 减少评分数量
}
```

### 问题 4: Notion API 报错
检查：
- Notion Token 是否正确
- 数据库是否已授权给集成
- 网络是否能访问 notion.com

### 问题 5: 内存不足
减少 PDF 解析范围：
```json
{
  "llm_pdf_max_pages": 15,
  "llm_pdf_max_chars": 30000
}
```

---

## 性能优化

### 减少运行时间
```json
{
  "days_back": 3,              // 缩短时间窗口
  "enrich_citations": false,   // 关闭引用数查询
  "enrich_institutions": false,// 关闭机构查询
  "llm_use_full_pdf": false    // 仅用摘要评分（快但不精准）
}
```

### 控制费用
```json
{
  "llm_max_papers": 10,        // 只对前 10 篇用大模型
  "llm_model": "qwen-turbo"    // 使用更便宜的模型
}
```

### 提升准确性
```json
{
  "llm_use_full_pdf": true,    // 完整 PDF 解析
  "llm_model": "qwen-max",     // 使用最强模型
  "llm_temperature": 0.1       // 降低随机性
}
```

---

## 高级用法

### 自定义评分标准
编辑 `paper_crawler.py` 中的 `LLMScoringEngine._build_messages()` 方法，修改评分提示词。

### 添加新数据源
在 `paper_crawler.py` 中实现新的 Crawler 类。

### 导出数据
Notion 支持导出为 CSV/Markdown/PDF。

---

## 安全建议

1. **不要提交 `.env` 到 Git**
   ```bash
   echo ".env" >> .gitignore
   echo "config.json" >> .gitignore
   ```

2. **使用环境变量存储密钥**
   ```bash
   export NOTION_TOKEN="ntn_xxxxx"
   export OPENAI_API_KEY="sk_xxxxx"
   ```

3. **定期轮换 API Key**

4. **限制服务器访问权限**
   ```bash
   chmod 600 .env
   chmod 700 run.sh
   ```

---

## 更新日志

### v2.0 (2025-11-18)
- ✨ 新增完整 PDF 解析功能
- ✨ 优化大模型评分提示词（更高区分度）
- 🔧 简化部署流程（一键脚本）
- 📝 完善部署文档

### v1.0
- 基础爬取与 Notion 同步
- 规则评分系统

---

## 贡献指南

欢迎提交 Issue 和 Pull Request！

---

## 许可证

MIT License

---

## 联系方式

如有问题，请通过 Issue 或邮件联系。
