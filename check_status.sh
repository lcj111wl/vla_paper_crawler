#!/bin/bash
# 查看爬虫运行状态和历史日志

WORK_DIR="/media/lcj/a/Mcp/vla_paper_crawler"
LOG_DIR="${WORK_DIR}/logs"
STATUS_FILE="${WORK_DIR}/status.json"

echo "=========================================="
echo "VLA 论文爬虫 - 运行状态"
echo "=========================================="
echo ""

# 显示最后运行状态
if [ -f "${STATUS_FILE}" ]; then
    echo "📊 最后运行状态:"
    echo "----------------------------------------"
    
    # 解析 JSON 并格式化输出
    LAST_RUN=$(grep -o '"last_run": "[^"]*"' "${STATUS_FILE}" | cut -d'"' -f4)
    END_TIME=$(grep -o '"end_time": "[^"]*"' "${STATUS_FILE}" | cut -d'"' -f4)
    STATUS=$(grep -o '"status": "[^"]*"' "${STATUS_FILE}" | cut -d'"' -f4)
    EXIT_CODE=$(grep -o '"exit_code": [0-9]*' "${STATUS_FILE}" | grep -o '[0-9]*')
    LOG_FILE=$(grep -o '"log_file": "[^"]*"' "${STATUS_FILE}" | cut -d'"' -f4)
    
    echo "  开始时间: ${LAST_RUN}"
    echo "  结束时间: ${END_TIME}"
    
    if [ "${STATUS}" = "success" ]; then
        echo "  运行状态: ✓ 成功"
    else
        echo "  运行状态: ✗ 失败 (退出码: ${EXIT_CODE})"
    fi
    
    echo "  日志文件: ${LOG_FILE}"
    echo ""
else
    echo "⚠ 未找到运行状态文件"
    echo "请先运行一次爬虫: ./run_daily.sh"
    echo ""
fi

# 显示历史日志列表
if [ -d "${LOG_DIR}" ]; then
    echo "📁 历史日志文件:"
    echo "----------------------------------------"
    ls -lht "${LOG_DIR}"/daily_*.log 2>/dev/null | head -10 | awk '{print "  " $9 " (" $6 " " $7 " " $8 ")"}'
    
    LOG_COUNT=$(ls -1 "${LOG_DIR}"/daily_*.log 2>/dev/null | wc -l)
    if [ ${LOG_COUNT} -gt 10 ]; then
        echo "  ... 还有 $((LOG_COUNT - 10)) 个历史日志"
    fi
    echo ""
fi

# 显示磁盘使用情况
if [ -d "${LOG_DIR}" ]; then
    LOG_SIZE=$(du -sh "${LOG_DIR}" 2>/dev/null | cut -f1)
    echo "💾 日志目录大小: ${LOG_SIZE}"
    echo ""
fi

echo "=========================================="
echo "快速命令:"
echo "----------------------------------------"
echo "  查看最新日志: ./view_log.sh"
echo "  查看完整日志: cat logs/latest.log"
echo "  手动运行:     ./run_daily.sh"
echo "  清理旧日志:   find logs -name 'daily_*.log' -mtime +30 -delete"
echo "=========================================="
