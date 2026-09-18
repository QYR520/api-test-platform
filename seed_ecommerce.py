# -*- coding: utf-8 -*-
"""
向平台数据库写入「真实电商项目」冒烟用例集。

被测系统: E:\秋招测试项目\ecommerce  (Node/Express, 端口3000)
调用方式: python seed_ecommerce.py      （重复运行不会重复插入）

链路（冒烟 = 核心业务闭环）:
  注册/登录 -> 商品列表 -> 加购物车 -> 查购物车 -> 下单 -> 查订单
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import database as db

BASE = "http://localhost:3000"
ECOMMERCE_CASES = [
    # 1. 登录（拿 token）——登录接口不会重复创建账号，用户名密码和 users.json 一致
    {
        "name": "电商-冒烟-登录获取token",
        "method": "POST", "url": f"{BASE}/api/login",
        "headers": "{}",
        "body": '{"username": "testuser_run", "password": "Test@123456"}',
        "assertions": '[{"type":"status_code","expect":200},{"type":"json_eq","path":"code","expect":0},{"type":"json_contains","path":"data.token"}]',
        "extract": '{"token": "data.token"}',
    },
    # 2. 商品列表（无需登录）
    {
        "name": "电商-冒烟-商品列表",
        "method": "GET", "url": f"{BASE}/api/products",
        "headers": "{}", "body": "{}",
        "assertions": '[{"type":"status_code","expect":200},{"type":"json_eq","path":"code","expect":0},{"type":"json_contains","path":"data"}]',
        "extract": '{"firstProductId": "data.0.id"}',
    },
    # 3. 加购物车（需要 token）
    {
        "name": "电商-冒烟-加入购物车",
        "method": "POST", "url": f"{BASE}/api/cart",
        "headers": '{"Authorization": "Bearer ${token}"}',
        "body": '{"productId": 1, "quantity": 2}',
        "assertions": '[{"type":"status_code","expect":201},{"type":"json_eq","path":"code","expect":0}]',
        "extract": "{}",
    },
    # 4. 查购物车
    {
        "name": "电商-冒烟-查询购物车",
        "method": "GET", "url": f"{BASE}/api/cart",
        "headers": '{"Authorization": "Bearer ${token}"}',
        "body": "{}",
        "assertions": '[{"type":"status_code","expect":200},{"type":"json_eq","path":"code","expect":0}]',
        "extract": "{}",
    },
    # 5. 下单结算
    {
        "name": "电商-冒烟-提交订单",
        "method": "POST", "url": f"{BASE}/api/orders",
        "headers": '{"Authorization": "Bearer ${token}"}',
        "body": "{}",
        "assertions": '[{"type":"status_code","expect":201},{"type":"json_eq","path":"code","expect":0},{"type":"json_contains","path":"data.id"}]',
        "extract": '{"orderId": "data.id"}',
    },
    # 6. 查订单（确认订单存在）
    {
        "name": "电商-冒烟-查询订单",
        "method": "GET", "url": f"{BASE}/api/orders",
        "headers": '{"Authorization": "Bearer ${token}"}',
        "body": "{}",
        "assertions": '[{"type":"status_code","expect":200},{"type":"json_eq","path":"code","expect":0}]',
        "extract": "{}",
    },
]


def seed_ecommerce():
    existing = {c["name"]: c for c in db.list_cases()}
    added = 0
    for case in ECOMMERCE_CASES:
        if case["name"] not in existing:
            case["project"] = "电商项目"
            db.create_case(case)
            added += 1
        else:
            # 旧数据补 project 标签
            c = existing[case["name"]]
            if c.get("project") in (None, "默认项目"):
                db.update_case(c["id"], {**c, "project": "电商项目"})
    print(f"电商冒烟用例写入完成: 新增 {added} 条, 已有跳过 {len(ECOMMERCE_CASES) - added} 条")


if __name__ == "__main__":
    db.init_db()
    seed_ecommerce()
