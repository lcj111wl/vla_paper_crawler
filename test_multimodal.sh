#!/bin/bash
# 测试多模态 PDF 解析（文本+图片）

cd "$(dirname "$0")"

# 创建测试配置（只抓取1天、1篇论文、启用LLM+图片）
cat > config_test_multimodal.json <<EOF
{
  "notion_token": "$(grep -o '"notion_token": *"[^"]*"' config_lcj.json | cut -d'"' -f4)",
  "database_id": "$(grep -o '"database_id": *"[^"]*"' config_lcj.json | cut -d'"' -f4)",
  "keywords": [
    "Vision-Language-Action"
  ],
  "days_back": 1,
  "max_papers": 1,
  "arxiv_max_results": 5,
  "semantic_scholar_max_results": 0,
  "use_semantic_scholar": false,
  "enrich_citations": false,
  "enrich_impact": false,
  "enrich_institutions": false,
  "extract_figures": false,
  "recommend_score_enabled": true,
  "llm_recommend_score_enabled": true,
  "llm_provider": "openai-compatible",
  "llm_model": "qwen-vl-plus",
  "llm_api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
  "llm_api_key": "$(grep -o '"llm_api_key": *"[^"]*"' config_lcj.json | cut -d'"' -f4)",
  "llm_max_papers": 1,
  "llm_call_interval_s": 1.0,
  "llm_temperature": 0.2,
  "llm_timeout": 120,
  "llm_max_tokens": 500,
  "llm_use_full_pdf": true,
  "llm_pdf_max_pages": 30,
  "llm_pdf_max_chars": 50000,
  "llm_pdf_extract_images": true,
  "llm_pdf_max_images": 5,
  "openalex_mailto": "$(grep -o '"openalex_mailto": *"[^"]*"' config_lcj.json | cut -d'"' -f4)",
  "log_level": "INFO"
}
EOF

echo "=========================================="
echo "🧪 测试多模态 PDF 解析"
echo "=========================================="
echo "配置: 1天、1篇论文、qwen-vl-plus、提取5张图片"
echo ""

python paper_crawler.py config_test_multimodal.json

echo ""
echo "=========================================="
echo "✅ 测试完成！"
echo "=========================================="
echo "请检查日志中是否显示："
echo "  ✓ PDF 提取了 X 张图片"
echo "  ✓ PDF 解析成功 (X 页, X 字符, X 张图片)"
echo ""
echo "如果图片提取成功，评分理由应该引用图片内容"
echo "=========================================="
