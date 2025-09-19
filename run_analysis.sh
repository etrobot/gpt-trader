#!/bin/bash
# Docker Freqtrade 策略分析脚本

set -e

echo "🚀 Docker Freqtrade 策略分析"
echo "==============================="

# 检查 Docker 和 docker-compose
if ! command -v docker &> /dev/null; then
    echo "❌ 需要安装 Docker"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ 需要安装 docker-compose"
    exit 1
fi

# 检查容器状态
CONTAINER_ID=$(docker-compose ps -q freqtrade 2>/dev/null)
if [ ! -z "$CONTAINER_ID" ]; then
    STATUS=$(docker inspect --format='{{.State.Status}}' $CONTAINER_ID 2>/dev/null)
    if [ "$STATUS" = "running" ]; then
        echo "🟢 检测到 Freqtrade 容器正在运行"
        echo "容器 ID: ${CONTAINER_ID:0:12}"
        echo ""
    fi
fi

echo "请选择操作:"
echo "1) 下载数据"
echo "2) 策略回测"
echo "3) 参数优化"
echo "4) 查看结果"
echo "5) 策略管理"
echo "6) 容器管理"
echo ""

read -p "选择 (1-6): " choice

case $choice in
    1)
        echo "📥 下载交易数据..."
        python backtest.py --action download
        ;;
    2)
        echo "📊 执行策略回测..."
        python backtest.py --action backtest
        ;;
    3)
        echo "⚙️ 执行参数优化..."
        python backtest.py --action hyperopt --epochs 50
        ;;
    4)
        echo "📈 显示回测结果..."
        python backtest.py --action results
        ;;
    5)
        echo "🎯 策略管理..."
        python strategy_manager.py
        ;;
    6)
        echo "🐳 容器管理..."
        echo "选择容器操作:"
        echo "a) 启动容器"
        echo "b) 停止容器"
        echo "c) 查看状态"
        echo "d) 查看日志"
        read -p "选择 (a-d): " container_choice
        
        case $container_choice in
            a)
                echo "🚀 启动 Freqtrade 容器..."
                docker-compose up -d freqtrade
                ;;
            b)
                echo "🛑 停止 Freqtrade 容器..."
                docker-compose stop freqtrade
                ;;
            c)
                echo "📊 容器状态:"
                docker-compose ps freqtrade
                ;;
            d)
                echo "📋 容器日志:"
                docker-compose logs --tail=50 freqtrade
                ;;
            *)
                echo "❌ 无效选择"
                ;;
        esac
        ;;
    *)
        echo "❌ 无效选择"
        exit 1
        ;;
esac