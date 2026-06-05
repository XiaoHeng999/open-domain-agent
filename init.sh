#!/bin/bash
# init.sh — open-agent 一键环境初始化
set -e

INSTALL_CMD="uv pip install -e \".[dev,openai,anthropic]\""
VERIFY_CMD="pytest tests/ -x -q"

echo "=== open-agent 初始化 ==="

echo ""
echo "[1/2] 安装依赖..."
eval "$INSTALL_CMD"

echo ""
echo "[2/2] 运行验证..."
eval "$VERIFY_CMD"

echo ""
echo "=== 初始化完成 ==="
echo "快速启动命令："
echo "  agent run '你的任务'    # 单次任务"
echo "  agent chat              # 交互模式"
echo "  make check              # 全部验证"
