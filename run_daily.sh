#!/bin/bash
# VLA 论文爬虫 - 每日自动更新脚本
# 使用绝对路径确保 cron 环境下正常运行

# 设置工作目录和日志目录
WORK_DIR="/media/lcj/a/Mcp/vla_paper_crawler"
LOG_DIR="${WORK_DIR}/logs"
DATE_STR=$(date +"%Y-%m-%d")
TIME_STR=$(date +"%Y-%m-%d %H:%M:%S")
DAILY_LOG="${LOG_DIR}/daily_${DATE_STR}.log"
LATEST_LOG="${LOG_DIR}/latest.log"
STATUS_FILE="${WORK_DIR}/status.json"

# 创建日志目录
mkdir -p "${LOG_DIR}"

# 记录开始时间
echo "========================================" | tee -a "${DAILY_LOG}"
echo "开始运行: ${TIME_STR}" | tee -a "${DAILY_LOG}"
echo "========================================" | tee -a "${DAILY_LOG}"

# 切换到工作目录
cd "${WORK_DIR}" || exit 1

# 激活 conda 环境（如果使用 conda）
if [ -f ~/anaconda3/etc/profile.d/conda.sh ]; then
    source ~/anaconda3/etc/profile.d/conda.sh
    conda activate vla_paper_crawler
    echo "✓ 已激活 conda 环境: vla_paper_crawler" | tee -a "${DAILY_LOG}"
elif [ -f ~/miniconda3/etc/profile.d/conda.sh ]; then
    source ~/miniconda3/etc/profile.d/conda.sh
    conda activate vla_paper_crawler
    echo "✓ 已激活 conda 环境: vla_paper_crawler" | tee -a "${DAILY_LOG}"
else
    echo "⚠ 未找到 conda，使用系统 Python" | tee -a "${DAILY_LOG}"
fi

# 运行爬虫，同时输出到日志文件和控制台
echo "" | tee -a "${DAILY_LOG}"
echo "正在运行爬虫..." | tee -a "${DAILY_LOG}"
python paper_crawler.py config_lcj.json 2>&1 | tee -a "${DAILY_LOG}"

# 检查运行结果
EXIT_CODE=${PIPESTATUS[0]}
END_TIME=$(date +"%Y-%m-%d %H:%M:%S")

echo "" | tee -a "${DAILY_LOG}"
echo "========================================" | tee -a "${DAILY_LOG}"
if [ ${EXIT_CODE} -eq 0 ]; then
    echo "✓ 运行成功" | tee -a "${DAILY_LOG}"
    STATUS="success"
else
    echo "✗ 运行失败 (退出码: ${EXIT_CODE})" | tee -a "${DAILY_LOG}"
    STATUS="failed"
fi
echo "结束时间: ${END_TIME}" | tee -a "${DAILY_LOG}"
echo "========================================" | tee -a "${DAILY_LOG}"

# 创建符号链接到最新日志
ln -sf "${DAILY_LOG}" "${LATEST_LOG}"

# 保存运行状态（JSON 格式）
cat > "${STATUS_FILE}" <<EOF
{
  "last_run": "${TIME_STR}",
  "end_time": "${END_TIME}",
  "status": "${STATUS}",
  "exit_code": ${EXIT_CODE},
  "log_file": "${DAILY_LOG}"
}
EOF

# 清理超过 30 天的旧日志
find "${LOG_DIR}" -name "daily_*.log" -mtime +30 -delete

echo ""
echo "日志文件: ${DAILY_LOG}"
echo "实时查看: tail -f ${LATEST_LOG}"
