# -*- coding: utf-8 -*-
"""
CI 回归入口（供 GitHub Actions 使用）：
  假设电商后端已由 workflow 启动 (node server.js, 端口3000)。
  本脚本：临时库 + 注入电商用例集 + 跑全部 + 断言全通过。
  运行: python run_ci.py   (退出码 0=通过 1=失败)
"""
import os
import sys
import tempfile

import config

# 隔离：用临时库，不污染本地演示数据
config.DB_PATH = os.path.join(tempfile.gettempdir(), "ci_platform.db")
if os.path.exists(config.DB_PATH):
    os.remove(config.DB_PATH)

from core import database as db
from seed_ecommerce import ECOMMERCE_CASES

db.DB_PATH = config.DB_PATH
db.init_db()
for case in ECOMMERCE_CASES:
    case["project"] = "电商项目"
    db.create_case(case)

from core import executor as ex

cases = db.list_cases("电商项目")   # 只跑电商项目，隔离演示项目；按 sort 顺序执行
outs = ex.run_many(cases)

failed = []
for o in outs:
    flag = "PASS" if o["passed"] else "FAIL"
    print(f"{flag} | {o['case']['name']} | status={o['status_code']}")
    if not o["passed"]:
        failed.append(f"{o['case']['name']}: {o['detail']}")

if failed:
    print("回归失败:")
    for f in failed:
        print(" -", f)
    raise SystemExit(1)
print(f"电商冒烟回归全部通过 ({len(outs)} 条)")
raise SystemExit(0)
