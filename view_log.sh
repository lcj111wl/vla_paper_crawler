#!/bin/bash
# 实时查看爬虫运行日志

LOG_DIR="/media/lcj/a/Mcp/vla_paper_crawler/logs"
LATEST_LOG="${LOG_DIR}/latest.log"

# 检查日志文件是否存在
if [ ! -f "${LATEST_LOG}" ]; then
    echo "❌ 找不到日志文件: ${LATEST_LOG}"
    echo "请先运行一次爬虫: ./run_daily.sh"
    exit 1
fi

echo "=========================================="
echo "实时查看 VLA 论文爬虫日志"
echo "=========================================="
echo "日志文件: ${LATEST_LOG}"
echo "按 Ctrl+C 退出"
echo "=========================================="
echo ""

# 实时跟踪日志
tail -f "${LATEST_LOG}"
