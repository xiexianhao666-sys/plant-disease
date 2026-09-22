#!/bin/bash
echo "============================================"
echo "  植物病害识别系统 - 正在启动"
echo "============================================"
echo "[1/2] 安装依赖..."
pip3 install -r requirements.txt -q
echo "[2/2] 启动服务..."
python3 app.py