# 植物病害智能识别系统

> 基于 Flask + Kindwise Plant.id API

## 功能
- 上传/拍摄植物叶片照片，AI 自动识别病害种类
- 输出病害中文名、置信度、病害说明与防治建议
- 置信度分级：高置信度结论 / 疑似提示 / 拒识
- 保存并展示最近 10 条诊断记录

## 技术栈
| 层次 | 技术 |
|---|---|
| 前端 | 原生 HTML5 + CSS3 + JavaScript (ES6) |
| 后端 | Python 3 + Flask |
| 识别服务 | Kindwise Plant.id API v3 |
| 数据存储 | JSON 文件 |

## 快速开始

### 1. 环境要求
Python 3.9 或更高版本

### 2. 配置 API Key
打开 `config.py`，替换为你的 Key：
```python
API_KEY = "你的Key"
```
申请地址：https://www.kindwise.com/plant-id

### 3. 启动
- **Windows**：双击 `run.bat`
- **Mac / Linux**：`chmod +x run.sh && ./run.sh`
- **手动**：
  ```bash
  pip install -r requirements.txt
  python app.py
  ```

### 4. 访问
http://127.0.0.1:5000

## 离线演示模式
无网络或未配置 Key 时：
```bash
# Windows
set MOCK_MODE=1 && python app.py

# Mac / Linux
MOCK_MODE=1 python app.py
```

## 项目结构
```
plant-disease-app/
├── app.py              后端主程序
├── config.py           配置文件
├── requirements.txt    依赖清单
├── templates/          页面模板
├── static/             静态资源
└── uploads/            上传的图片
```