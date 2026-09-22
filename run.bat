@echo off
chcp 65001 >nul
echo ============================================
echo   植物病害识别系统 - 正在启动
echo ============================================
echo.
echo [1/2] 检查并安装依赖...
pip install -r requirements.txt -q

echo [2/2] 启动服务...
start "" http://127.0.0.1:5000
python app.py

pause