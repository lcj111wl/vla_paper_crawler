#!/bin/bash
# VLA Paper Crawler - 一键部署脚本
# 用法: bash setup.sh

set -e

echo "=========================================="
echo "VLA Paper Crawler - 自动部署"
echo "=========================================="

# 检查 Python 版本
echo "📦 检查 Python 版本..."
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到 Python3，请先安装 Python 3.8+"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "✅ Python 版本: $(python3 --version)"

# 创建虚拟环境（可选）
read -p "是否创建虚拟环境？(y/n，推荐y): " CREATE_VENV
if [[ "$CREATE_VENV" == "y" || "$CREATE_VENV" == "Y" ]]; then
    echo "📦 创建虚拟环境..."
    python3 -m venv venv
    source venv/bin/activate
    echo "✅ 虚拟环境已激活"
else
    echo "⚠️  跳过虚拟环境，将安装到系统 Python"
fi

# 升级 pip
echo "📦 升级 pip..."
pip install --upgrade pip

# 安装依赖
echo "📦 安装 Python 依赖..."
pip install -r requirements.txt
echo "✅ 依赖安装完成"

# 创建必要目录
echo "📁 创建目录结构..."
mkdir -p logs images
echo "✅ 目录创建完成"

# 配置环境变量
if [ ! -f .env ]; then
    echo "📝 创建环境配置文件..."
    cp .env.example .env
    echo "⚠️  请编辑 .env 文件填入你的 API 密钥："
    echo "   - NOTION_TOKEN"
    echo "   - DATABASE_ID"
    echo "   - OPENAI_API_KEY (用于大模型评分)"
    echo ""
    read -p "按回车键打开编辑器 (vim/nano)，或输入 'skip' 跳过: " EDIT_ENV
    if [[ "$EDIT_ENV" != "skip" ]]; then
        ${EDITOR:-nano} .env
    fi
else
    echo "✅ .env 文件已存在"
fi

# 生成配置文件
if [ ! -f config.json ]; then
    echo "📝 生成配置文件..."
    # 从 .env 读取并替换模板
    source .env 2>/dev/null || true
    envsubst < config.template.json > config.json
    echo "✅ config.json 已生成"
else
    echo "✅ config.json 已存在"
fi

# 测试运行
echo ""
echo "=========================================="
echo "🧪 测试运行"
echo "=========================================="
read -p "是否进行测试运行？(y/n): " TEST_RUN
if [[ "$TEST_RUN" == "y" || "$TEST_RUN" == "Y" ]]; then
    echo "运行测试（抓取最近3天的论文）..."
    python3 paper_crawler.py config.json 2>&1 | head -30
    echo ""
    echo "✅ 测试完成！查看完整日志: tail -f paper_crawler.log"
fi

# 设置定时任务
echo ""
echo "=========================================="
echo "⏰ 配置定时任务"
echo "=========================================="
read -p "是否设置定时任务（每天自动运行）？(y/n): " SETUP_CRON
if [[ "$SETUP_CRON" == "y" || "$SETUP_CRON" == "Y" ]]; then
    SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
    CRON_CMD="0 2 * * * cd $SCRIPT_DIR && $SCRIPT_DIR/run.sh >> $SCRIPT_DIR/logs/cron.log 2>&1"
    
    echo "将添加以下 cron 任务（每天凌晨2点运行）："
    echo "$CRON_CMD"
    echo ""
    read -p "确认添加？(y/n): " CONFIRM_CRON
    if [[ "$CONFIRM_CRON" == "y" || "$CONFIRM_CRON" == "Y" ]]; then
        (crontab -l 2>/dev/null | grep -v "paper_crawler.py"; echo "$CRON_CMD") | crontab -
        echo "✅ 定时任务已添加"
        echo "查看定时任务: crontab -l"
    fi
fi

echo ""
echo "=========================================="
echo "✅ 部署完成！"
echo "=========================================="
echo ""
echo "快速开始："
echo "  1. 编辑配置: nano .env 或 nano config.json"
echo "  2. 手动运行: ./run.sh"
echo "  3. 查看日志: tail -f paper_crawler.log"
echo "  4. 查看定时任务: crontab -l"
echo ""
echo "重要提示："
echo "  - 确保已在 Notion 中创建集成并授权数据库访问权限"
echo "  - 大模型评分需要配置 OPENAI_API_KEY（支持通义千问等兼容接口）"
echo "  - 建议首次运行时设置 days_back=3 进行小规模测试"
echo ""
