#!/bin/bash
# 快速测试脚本 - 仅抓取最近3天、前5篇论文

echo "🧪 快速测试模式"
echo "配置: 最近3天、最多5篇、2篇LLM评分"

# 临时配置
cat > config_test.json << 'EOF'
{
  "notion_token": "${NOTION_TOKEN}",
  "database_id": "${DATABASE_ID}",
  "keywords": [
    "Vision-Language-Action",
    "VLA model"
  ],
  "days_back": 3,
  "max_papers": 5,
  "arxiv_max_results": 20,
  "semantic_scholar_max_results": 10,
  "use_semantic_scholar": false,
  "enrich_citations": false,
  "enrich_impact": false,
  "enrich_institutions": false,
  "extract_figures": false,
  "recommend_score_enabled": true,
  "llm_recommend_score_enabled": true,
  "llm_provider": "openai-compatible",
  "llm_model": "qwen-plus",
  "llm_api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
  "llm_max_papers": 2,
  "llm_call_interval_s": 0.5,
  "llm_temperature": 0.2,
  "llm_timeout": 60,
  "llm_max_tokens": 300,
  "llm_use_full_pdf": true,
  "llm_pdf_max_pages": 20,
  "llm_pdf_max_chars": 30000,
  "log_level": "INFO"
}
EOF

# 从 .env 加载环境变量
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# 替换环境变量
envsubst < config_test.json > config_test_final.json

# 运行
python3 paper_crawler.py config_test_final.json

# 清理
rm config_test.json config_test_final.json

echo ""
echo "✅ 测试完成！"
echo "查看结果: tail -50 paper_crawler.log"
