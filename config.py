# -*- coding: utf-8 -*-
"""平台基础配置"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# SQLite 数据库文件路径
DB_PATH = os.path.join(BASE_DIR, "platform.db")

# 请求默认超时（秒）
DEFAULT_TIMEOUT = 10

# Flask 启动参数
HOST = "127.0.0.1"
PORT = 5000