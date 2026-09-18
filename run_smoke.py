# -*- coding: utf-8 -*-
"""
冒烟测试：用 Flask test_client 跑，无需启动真实服务器，便于在 CI 中运行。
验证：核心引擎正确性 + 用例数据化 + 变量传递闭环。
运行: python -m pytest -q   或   python run_smoke.py
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["WERKZEUG_RUN_MAIN"] = "1"

from app import app, seed
from core import database as db


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # 用临时库 + 真实服务器线程，端到端验证变量传递
    import config
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "smoke.db"))
    import core.database as d
    monkeypatch.setattr(d, "DB_PATH", str(tmp_path / "smoke.db"))
    d.init_db()
    PORT = 5002
    BASE = f"http://127.0.0.1:{PORT}"
    d.create_case({
        "name": "登录", "method": "POST", "url": f"{BASE}/mock/login",
        "headers": "{}", "body": '{"username":"t"}',
        "assertions": '[{"type":"status_code","expect":200},{"type":"json_eq","path":"code","expect":0}]',
        "extract": '{"token":"data.token"}',
    })
    d.create_case({
        "name": "查用户(引用token)", "method": "GET", "url": f"{BASE}/mock/user?token=${{token}}",
        "headers": "{}", "body": "{}",
        "assertions": '[{"type":"status_code","expect":200},{"type":"json_eq","path":"code","expect":0}]',
        "extract": "{}",
    })
    import threading, time
    from app import app as _app
    _app.config["TESTING"] = True
    t = threading.Thread(target=lambda: _app.run(
        host="127.0.0.1", port=PORT, debug=False, use_reloader=False), daemon=True)
    t.start()
    time.sleep(1.0)
    yield ()
    time.sleep(0.2)


def test_mock_login_and_variable_transfer(client):
    from core import executor as ex
    cases = db.list_cases()
    outputs = ex.run_many(cases)
    assert all(o["passed"] for o in outputs), [o["detail"] for o in outputs]
    # 验证 token 确实被传递：查用户接口若 token 空会返回 403 导致失败，此处已通过即证明传递生效


def test_case_is_data_not_code(client):
    from app import app as _app
    c = _app.test_client()
    r = c.get("/")
    assert r.status_code == 200
    r = c.post("/api/case", json={
        "name": "动态新增", "method": "POST", "url": "/mock/login",
        "headers": "{}", "body": "{}", "assertions": "[]", "extract": "{}"})
    assert r.json["ok"] is True


def test_assertion_engine_basic():
    from core.assertions import run_assertions
    passed, _ = run_assertions(
        [{"type": "status_code", "expect": 200},
         {"type": "json_eq", "path": "code", "expect": 0},
         {"type": "json_contains", "path": "data.token"}],
        200, '{"code":0,"data":{"token":"tk"}}')
    assert passed


def test_assertion_engine_fail_detect():
    from core.assertions import run_assertions
    passed, _ = run_assertions(
        [{"type": "json_eq", "path": "code", "expect": 1}],
        200, '{"code":0}')
    assert not passed


if __name__ == "__main__":
    # 独立入口脚本：起一个真实 Server 线程，端到端跑通「用例数据+引擎+变量传递」。
    # CI 里的 `python run_smoke.py` 走的就是这条，无需 pytest。
    import tempfile
    import threading
    import time
    import config

    config.DB_PATH = os.path.join(tempfile.gettempdir(), "smoke_db_tmp.db")
    if os.path.exists(config.DB_PATH):
        os.remove(config.DB_PATH)   # 清掉可能的旧数据，保证每轮干净
    import core.database as d
    d.DB_PATH = config.DB_PATH
    d.init_db()
    # 用例用例使用绝对地址，直达内置 mock
    d.create_case({
        "name": "登录", "method": "POST",
        "url": "http://127.0.0.1:5001/mock/login",
        "headers": "{}", "body": '{"username":"t"}',
        "assertions": '[{"type":"status_code","expect":200},{"type":"json_eq","path":"code","expect":0}]',
        "extract": '{"token":"data.token"}',
    })
    d.create_case({
        "name": "查用户(引用token)", "method": "GET",
        "url": "http://127.0.0.1:5001/mock/user?token=${token}",
        "headers": "{}", "body": "{}",
        "assertions": '[{"type":"status_code","expect":200},{"type":"json_eq","path":"code","expect":0}]',
        "extract": "{}",
    })
    d.create_case({
        "name": "健康检查", "method": "GET",
        "url": "http://127.0.0.1:5001/mock/health",
        "headers": "{}", "body": "{}",
        "assertions": '[{"type":"status_code","expect":200},{"type":"text_contains","expect":"ok"}]',
        "extract": "{}",
    })
    from app import app as _flask_app

    port = 5001
    t = threading.Thread(target=lambda: _flask_app.run(
        host="127.0.0.1", port=port, debug=False, use_reloader=False), daemon=True)
    t.start()
    time.sleep(1.0)

    from core import executor as ex
    outs = ex.run_many(d.list_cases())  # 正序执行，保证 登录→查用户 依赖成立
    ok_all = True
    for o in outs:
        print("PASS" if o["passed"] else "FAIL", "->", o["case"]["name"], "|", o["detail"])
        ok_all = ok_all and o["passed"]
    print("总体:", "全部通过" if ok_all else "存在失败")
    raise SystemExit(0 if ok_all else 1)