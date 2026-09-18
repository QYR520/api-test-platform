# -*- coding: utf-8 -*-
"""
断言引擎：断言规则从数据库读取（配置驱动），而非写死在代码里。
支持 4 类规则（type 字段区分）：
  status_code   : 校验HTTP状态码 == expect
  json_eq       : 校验响应JSON某个path字段 == expect
  json_contains : 校验响应JSON具备某path字段
  text_contains : 校验响应文本包含 expect
path 支持点号路径，如 data.code / data.items.0.id
"""


def _get_path(obj, path):
    """按点路径取值。obj 可以是 dict/list 混合结构。"""
    cur = obj
    for key in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(key)
        elif isinstance(cur, list) and key.isdigit():
            idx = int(key)
            cur = cur[idx] if idx < len(cur) else None
        else:
            return None
    return cur


def run_assertions(assertions, status_code, body_text):
    """逐条执行断言，返回 (passed, details)。body_text 为响应明文字符串。"""
    passed = True
    details = []
    import json

    body_json = None
    try:
        body_json = json.loads(body_text) if body_text else None
    except Exception:
        body_json = None

    for rule in assertions:
        rtype = rule.get("type")
        path = rule.get("path", "")
        expect = rule.get("expect", "")
        try:
            if rtype == "status_code":
                ok = (status_code == int(expect))
            elif rtype == "json_eq":
                actual = _get_path(body_json, path)
                ok = (actual == expect)
            elif rtype == "json_contains":
                ok = (_get_path(body_json, path) is not None)
            elif rtype == "text_contains":
                ok = (expect in (body_text or ""))
            else:
                ok = False
        except Exception as e:
            ok, details = False, f"断言执行异常: {e}"
        details.append(f"[{rtype}] {path or '/status'} 期望={expect} 结果={'通过' if ok else '失败'}")
        passed = passed and ok
    return passed, details