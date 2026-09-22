# -*- coding: utf-8 -*-
"""
植物病害智能识别系统 —— Flask 后端
调用 Kindwise Plant.id v3 API 完成病害识别
"""
import base64
import json
import os
import socket
import sys
import threading
import time
import uuid
import webbrowser

import requests
from flask import Flask, jsonify, render_template, request, send_from_directory

import config

# ---------------- 路径处理（兼容 PyInstaller） ----------------
def _runtime_dir():
    """可写目录：uploads、history.json 放这里"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _resource_dir():
    """只读资源目录：templates、static 放这里"""
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = _runtime_dir()
RES_DIR = _resource_dir()

UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
HISTORY_FILE = os.path.join(BASE_DIR, "history.json")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__,
            template_folder=os.path.join(RES_DIR, "templates"),
            static_folder=os.path.join(RES_DIR, "static"))
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 单次请求上限 10MB

API_URL = "https://plant.id/api/v3/health_assessment"

# ---------------- 置信度阈值 ----------------
THRESHOLD_SURE = 0.75    # >= 0.75      给出明确结论
THRESHOLD_MAYBE = 0.40   # 0.40 ~ 0.75  判定为"疑似"
                         # < 0.40        拒识，提示重新拍摄

ALLOWED_EXT = {"jpg", "jpeg", "png", "webp", "bmp"}

# ---------------- 离线演示用的假数据 ----------------
_MOCK_RESULT = {
    "result": {
        "is_plant": {"binary": True, "probability": 0.99},
        "is_healthy": {"binary": False, "probability": 0.97},
        "disease": {
            "suggestions": [
                {
                    "name": "Tomato Late Blight",
                    "probability": 0.88,
                    "details": {
                        "local_name": "番茄晚疫病",
                        "description": "由致病疫霉（Phytophthora infestans）引起。叶片出现水渍状暗绿色病斑，"
                                       "扩展迅速，湿度大时叶背产生白色霉层，严重时全田枯死。",
                        "treatment": {
                            "prevention": ["选用抗病品种", "合理密植、加强通风", "避免大水漫灌，降低田间湿度"],
                            "chemical": ["发病初期喷施烯酰吗啉、霜脲氰等药剂",
                                         "每 7~10 天一次，连续 2~3 次，注意轮换用药"],
                            "biological": ["可选用枯草芽孢杆菌等生物制剂进行预防"]
                        },
                        "url": "https://en.wikipedia.org/wiki/Phytophthora_infestans"
                    }
                },
                {"name": "Tomato Early Blight", "probability": 0.07,
                 "details": {"local_name": "番茄早疫病"}},
                {"name": "Tomato Septoria Leaf Spot", "probability": 0.03,
                 "details": {"local_name": "番茄斑枯病"}},
            ]
        },
    }
}


# ================= 工具函数 =================

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_history(record: dict):
    data = load_history()
    data.insert(0, record)
    data = data[:50]                       # 最多保留 50 条
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def call_plant_id(images_b64: list, lat=None, lon=None) -> dict:
    """调用 Plant.id health_assessment 接口，支持多图 / 定位"""
    # ---- 演示模式：直接返回假数据 ----
    if config.MOCK_MODE:
        time.sleep(1.2)
        return _MOCK_RESULT

    if not config.API_KEY or config.API_KEY.startswith("在这里"):
        raise RuntimeError("尚未配置 API Key，请编辑 config.py，"
                           "或设置环境变量 MOCK_MODE=1 使用演示模式")

    headers = {"Api-Key": config.API_KEY, "Content-Type": "application/json"}
    params = {
        "details": "local_name,description,treatment,cause",
        "language": config.LANGUAGE,
    }
    payload = {"images": images_b64, "similar_images": True}

    # 加上经纬度，提升地域相关病害的判断准确率
    if lat and lon:
        try:
            payload["latitude"] = float(lat)
            payload["longitude"] = float(lon)
        except (TypeError, ValueError):
            pass

    resp = requests.post(API_URL, json=payload, headers=headers,
                         params=params, timeout=90)

    if resp.status_code not in (200, 201):
        raise RuntimeError("识别服务返回错误 {}：{}".format(
            resp.status_code, resp.text[:2000]))

    return resp.json()


def pack_suggestion(s: dict) -> dict:
    """把单个候选病害整理成前端友好的结构"""
    d = s.get("details") or {}
    return {
        "name": s.get("name"),
        "local_name": d.get("local_name") or s.get("name"),
        "probability": round(float(s.get("probability", 0)), 3),
        "description": d.get("description"),
        "treatment": d.get("treatment"),
        "url": d.get("url"),
    }


def parse_result(raw: dict, crop_filter: str = None) -> dict:
    """解析 Plant.id 原始响应。策略：只要有候选，一律给出最可能结果"""
    result = raw.get("result") or {}

    is_plant = (result.get("is_plant") or {}).get("binary", True)
    suggestions = (result.get("disease") or {}).get("suggestions") or []

    def pack(s):
        """统一成前端格式，兼容已打包 / 未打包两种输入"""
        if "details" in s:
            d = s.get("details") or {}
        else:
            d = s
        return {
            "name": s.get("name"),
            "local_name": d.get("local_name") or s.get("name"),
            "probability": round(float(s.get("probability", 0)), 4),
            "description": d.get("description"),
            "treatment": d.get("treatment"),
            "url": d.get("url") or s.get("url"),
        }

    # 作物过滤
    if crop_filter and suggestions:
        filtered = [
            s for s in suggestions
            if crop_filter.lower() in json.dumps(s, ensure_ascii=False).lower()
        ]
        if filtered:
            suggestions = filtered

    # ---- A：不是植物 ----
    if not is_plant:
        return {"status": "rejected",
                "message": "未在图片中检测到植物，请重新拍摄叶片照片",
                "candidates": []}

    # ---- B：没有任何候选 ----
    if not suggestions:
        is_healthy = (result.get("is_healthy") or {}).get("binary")
        if is_healthy is True:
            return {"status": "healthy",
                    "message": "未检测到明显病害，植株看起来是健康的",
                    "candidates": []}
        return {"status": "rejected",
                "message": "未能识别出具体病害类型，请拍摄病斑特写后重试",
                "candidates": []}

    # ---- C：有候选 → 一律给出结果，只分三档提示 ----
    top = suggestions[0]
    prob = float(top.get("probability", 0))

    if prob >= THRESHOLD_SURE:              # ≥ 0.75
        status = "confirmed"
        message = "识别完成，置信度较高"
    elif prob >= THRESHOLD_MAYBE:           # 0.40 ~ 0.75
        status = "suspected"
        message = "较可能的结果，建议结合实际症状判断"
    else:                                    # < 0.40 也不再拒识
        status = "low"
        message = "以下是模型给出的最可能结果，置信度偏低，仅供参考"

    return {
        "status": status,
        "message": message,
        "disease": pack(top),
        "candidates": [pack(s) for s in suggestions[1:5]],   # 备选给到 4 个
    }


# ================= 路由 =================

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/diagnose", methods=["POST"])
def diagnose():
    # ---- 1. 接收多张图片 ----
    files = request.files.getlist("images")
    if not files:
        return jsonify({"status": "error", "message": "未接收到图片文件"}), 400

    if len(files) > 5:
        files = files[:5]

    images_b64 = []
    saved_names = []

    for idx, file in enumerate(files):
        if not file.filename or not allowed_file(file.filename):
            return jsonify({"status": "error",
                            "message": "第 {} 张图片格式不支持".format(idx + 1)}), 400

        data = file.read()
        if len(data) < 1024:
            continue                      # 跳过损坏的小文件

        mime = file.mimetype or "image/jpeg"
        images_b64.append("data:{};base64,{}".format(
            mime, base64.b64encode(data).decode("utf-8")))

        # 保存原图
        rid = time.strftime("%Y%m%d%H%M%S") + "_" + uuid.uuid4().hex[:6]
        ext = file.filename.rsplit(".", 1)[1].lower()
        fname = rid + "." + ext
        with open(os.path.join(UPLOAD_DIR, fname), "wb") as f:
            f.write(data)
        saved_names.append(fname)

    if not images_b64:
        return jsonify({"status": "error", "message": "没有有效的图片"}), 400

    print("=" * 60)
    print("收到图片数：", len(images_b64))
    print("=" * 60)

    crop = (request.form.get("crop") or "").strip() or None

    # 定位信息（可选）
    lat = request.form.get("latitude")
    lon = request.form.get("longitude")

    # ---- 2. 调用识别接口 ----
    try:
        raw = call_plant_id(images_b64, lat=lat, lon=lon)
    except Exception as e:
        return jsonify({"status": "error", "message": "识别失败：{}".format(e)}), 502

    # ---- 3. 解析 + 分级 ----
    parsed = parse_result(raw, crop)
    parsed["record_id"] = saved_names[0].rsplit(".", 1)[0]
    parsed["image_url"] = "/uploads/" + saved_names[0]
    parsed["image_count"] = len(saved_names)
    parsed["crop"] = crop
    parsed["time"] = time.strftime("%Y-%m-%d %H:%M:%S")

    # ---- 4. 写入历史 ----
    disease = parsed.get("disease") or {}
    save_history({
        "record_id": parsed["record_id"],
        "time": parsed["time"],
        "crop": crop,
        "status": parsed["status"],
        "image_url": parsed["image_url"],
        "disease": disease.get("local_name"),
        "probability": disease.get("probability"),
        "image_count": len(saved_names),
    })

    return jsonify(parsed)


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)


@app.route("/api/history")
def api_history():
    return jsonify(load_history()[:10])


@app.errorhandler(413)
def too_large(e):
    return jsonify({"status": "error",
                    "message": "图片过大（上限 10MB），请压缩后重试"}), 413


def _find_free_port(start=5000, tries=20):
    """5000 被占用时自动往后找"""
    for p in range(start, start + tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    return start


if __name__ == "__main__":
    _IS_FROZEN = getattr(sys, "frozen", False)

    port = _find_free_port(5000)
    url = "http://127.0.0.1:{}".format(port)
    mode = "【演示模式】" if config.MOCK_MODE else "【真实API模式】"

    print("=" * 56)
    print("  植物病害智能识别系统  " + mode)
    print("  浏览器打开：" + url)
    print("  关闭此窗口即可退出程序")
    print("=" * 56)

    # 只在真正提供服务的进程里开浏览器，避免重复弹窗
    if _IS_FROZEN or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()

    app.run(host="127.0.0.1", port=port,
            debug=not _IS_FROZEN,
            use_reloader=not _IS_FROZEN)