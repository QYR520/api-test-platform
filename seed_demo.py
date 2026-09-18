# -*- coding: utf-8 -*-
"""补入演示项目用例（演示项目隔离对比用）"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import database as db

db.init_db()
demo = {"project": "演示项目"}
CASES = [
    {"name": "演示-登录取token", "method": "POST",
     "url": "http://127.0.0.1:5000/mock/login", "headers": "{}",
     "body": '{"username": "tester"}',
     "assertions": '[{"type":"status_code","expect":200},{"type":"json_eq","path":"code","expect":0}]',
     "extract": '{"token": "data.token"}'},
    {"name": "演示-带token查用户", "method": "GET",
     "url": "http://127.0.0.1:5000/mock/user?token=${token}", "headers": "{}",
     "body": "{}",
     "assertions": '[{"type":"status_code","expect":200}]',
     "extract": "{}"},
    {"name": "演示-健康检查", "method": "GET",
     "url": "http://127.0.0.1:5000/mock/health", "headers": "{}",
     "body": "{}",
     "assertions": '[{"type":"text_contains","expect":"ok"}]',
     "extract": "{}"},
]
existing = {c["name"] for c in db.list_cases()}
n = 0
for c in CASES:
    if c["name"] not in existing:
        db.create_case({**demo, **c})
        n += 1
print(f"演示项目用例补入 {n} 条")
