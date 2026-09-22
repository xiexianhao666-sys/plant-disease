# -*- coding: utf-8 -*-
"""项目配置"""
import os

# ============================================================
# 【必填】Kindwise Plant.id 的 API Key
#   申请：https://www.kindwise.com/plant-id
#   注册后 Dashboard → API Keys 复制粘贴到这里
# ============================================================
API_KEY = os.environ.get("KINDWISE_API_KEY", "VifxiV8XwtNcf65VRrYDhdk3tcUcvJiScb6SrG2gF9qc9URR81")

# 返回语言：zh 中文 / en 英文
LANGUAGE = os.environ.get("KINDWISE_LANGUAGE", "zh")

# ============================================================
# 【演示开关】MOCK_MODE = 1 时不调用真实 API，返回内置假数据
#   用途：离线演示、额度用完时应急
# ============================================================
MOCK_MODE = os.environ.get("MOCK_MODE", "0") == "1"


# ============================================================
# 打包后从 exe 同目录的 key.txt 读取 API Key（存在则覆盖）
# ============================================================
import sys as _sys

if getattr(_sys, "frozen", False):
    _key_file = os.path.join(os.path.dirname(_sys.executable), "key.txt")
else:
    _key_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "key.txt")

if os.path.exists(_key_file):
    try:
        with open(_key_file, "r", encoding="utf-8") as _f:
            _k = _f.read().strip()
        if _k:
            API_KEY = _k
    except Exception:
        pass

