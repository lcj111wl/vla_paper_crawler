#!/bin/bash
# 测试多模态 PDF 解析（5篇论文）

cd "$(dirname "$0")"

echo "=========================================="
echo "🧪 测试多模态 PDF 解析（5篇论文）"
echo "=========================================="
echo "配置："
echo "  - 时间范围: 最近 7 天"
echo "  - 论文数量: 5 篇"
echo "  - 大模型: qwen-vl-plus（支持视觉）"
echo "  - 图片提取: 最多 8 张/篇"
echo "  - 超时时间: 120 秒"
echo ""
echo "开始运行..."
echo "=========================================="
echo ""

# 运行爬虫（显示实时输出）
python -u paper_crawler.py config_test_5papers.json 2>&1 | tee test_multimodal_output.log

EXIT_CODE=${PIPESTATUS[0]}

echo ""
echo "=========================================="
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ 测试完成！"
else
    echo "⚠️  测试中断（退出码: $EXIT_CODE）"
fi
echo "=========================================="
echo ""
echo "📊 测试结果摘要："
echo ""

# 统计关键信息
if [ -f test_multimodal_output.log ]; then
    echo "✓ 找到论文数："
    grep -o "总共找到 [0-9]* 篇论文" test_multimodal_output.log | tail -1
    
    echo ""
    echo "✓ PDF 解析成功："
    grep "PDF 解析成功" test_multimodal_output.log | wc -l
    
    echo ""
    echo "✓ 图片提取情况："
    grep -o "PDF 提取了 [0-9]* 张图片" test_multimodal_output.log
    
    echo ""
    echo "✓ 评分完成："
    grep "LLM 评分" test_multimodal_output.log | wc -l
    
    echo ""
    echo "完整日志已保存到: test_multimodal_output.log"
fi

echo "=========================================="
