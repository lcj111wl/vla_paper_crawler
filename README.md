# VLA Paper Crawler

一个用于自动抓取 Vision-Language-Action (VLA) 相关论文，并进行多模态大模型评分、写入 Notion 数据库的自动化工具。

[![Code Quality](https://img.shields.io/badge/code%20quality-85%2F100-brightgreen)](https://github.com/lcj111wl/vla_paper_crawler)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

## ✨ 功能特性

### 核心功能
- 🔍 **多源检索**：支持 arXiv 与 Semantic Scholar，自动去重
- 🧠 **多模态评分**：调用支持视觉的 LLM（如 qwen-vl-plus / gpt-4o）对论文进行全文 + 图片综合评分
- 📄 **PDF 智能解析**：提取前 N 页全文（可配置）+ 自适应筛选关键图片（过滤小图、按大小排序）
- 🏷️ **机构信息提取**：自动获取作者所属机构（学校/企业）
- 🧪 **评分维度**：VLA相关性 / 方法创新性 / 实验严谨性 / 技术深度 / 影响潜力
- 📊 **Notion 深度集成**：自动创建并更新 Recommend Score / Rationale / Institutions 等字段

### 智能优化
- ⚡ **提前去重**：在 LLM 评分前过滤重复论文，节省 token 成本
- 🔧 **缺失字段补全**：自动检测并补全已有论文的缺失字段（PDF Link / Institutions / Citations / Recommend Score）
- 📈 **优先级补全**：智能区分免费 API 和付费 LLM，按优先级补全
- 🛠️ **一键部署**：提供 setup.sh、run.sh、test 脚本、配置模板

## 📁 项目结构
```
├── paper_crawler.py          # 主程序：抓取 + 解析 + 评分 + Notion 同步 + 补全
├── vla_filter.py             # VLA 论文过滤模块（公用）NEW!
├── figure_extractor.py       # 框架图提取工具
├── notion_sync_tasks.py      # Notion 任务同步（独立工具）
├── config.template.json      # 配置模板（占位符，无敏感信息）
├── config_lcj.json           # 私有运行配置（勿提交，.gitignore 已忽略）
├── requirements.txt          # Python 依赖列表
├── README.md                 # 项目说明文档
├── README_DEPLOY.md          # 部署与运维文档
├── QUICKSTART.md             # 快速开始指南
├── MULTIMODAL_README.md      # 多模态评分与 PDF 解析说明
├── test_multimodal.sh        # 测试多模态 1 篇论文脚本
├── test_5papers.sh           # 测试 5 篇论文脚本
├── run.sh                    # 运行脚本（生产）
├── setup.sh                  # 一键初始化脚本
└── .gitignore                # Git 忽略规则
```

## 🚀 快速开始
```bash
# 1. 克隆项目并进入目录

cd vla_paper_crawler

# 2. 创建并激活虚拟环境
python -m venv .venv
source .venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 复制配置模板并填写敏感信息
cp config.template.json config.local.json
# 编辑 config.local.json -> 填写 notion_token / database_id / llm_api_key 等

# 5. 运行测试（单篇 PDF 多模态）
./test_multimodal.sh

# 6. 正式运行（使用你的配置）
python paper_crawler.py config.local.json
```

## ⚙️ 核心配置说明（节选）
```json
{
  "keywords": ["Vision-Language-Action", "VLA model"],
  "days_back": 20,
  "max_papers": 50,
  "llm_model": "qwen-vl-plus",          // 多模态模型
  "llm_use_full_pdf": true,              // 启用 PDF 全文解析
  "llm_pdf_max_pages": 30,               // 最多解析页数
  "llm_pdf_max_chars": 50000,            // 最大字符截断
  "llm_pdf_extract_images": true,        // 是否提取图片
  "llm_pdf_max_images": 10,              // 最多图片数
  "llm_max_papers": 999,                 // 对全部论文调用 LLM
  "llm_timeout": 120                     // 超时秒数
}
```

## 🧠 评分输出示例
```json
{
  "score": 85,
  "rationale": "该论文提出新型VLA架构（Figure 2 所示双流编码结构），在7项机器人操作任务上平均提升15%-25%，消融实验（Table 3）验证语言指令模块对性能贡献显著，真实机器人实验展示良好泛化能力，属于优秀创新范畴。"
}
```

## 🛡 安全与隐私
- 请勿提交 `config_lcj.json`、真实 API 密钥、Notion Token 等敏感文件
- 使用环境变量或 `.env` 文件注入敏感配置
- 如果需要开源，可改用占位符：`NOTION_TOKEN=***`

## 🧪 测试建议
| 场景 | 脚本 | 描述 |
|------|------|------|
| 单篇多模态快速验证 | `./test_multimodal.sh` | 抓取 1 篇并评分 |
| 5 篇多模态效果验证 | `./test_5papers.sh` | 抓取 5 篇并评分 |
| 全量运行 | `python paper_crawler.py config.local.json` | 按配置抓取 + 全评分 |

## 📌 后续优化方向
- 表格/公式结构化提取
- 架构图智能判定（而非按大小）
- 本地缓存避免重复下载 PDF
- LLM 失败自动降级为规则评分
- CI 自动运行并推送结果

## 🤝 贡献指南
欢迎通过 Issue / PR 提交：
- 新的数据源（OpenAlex、CrossRef 等）
- 更好的 PDF 图片筛选策略
- 多语言支持（英文报告）

## � 许可证
MIT（可根据实际需求修改）

---
如需更多运行细节请参考 `README_DEPLOY.md` 与 `MULTIMODAL_README.md`。
