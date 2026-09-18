# -*- coding: utf-8 -*-
"""
执行引擎：读取"用例数据" -> 发请求 -> 变量提取/传递 -> 断言。

关键增值点（测开亮点）：
1. 用例是数据，引擎是通用解释器，上层加用例不改代码。
2. 变量传递：${var} 占位符可在 url/headers/body 里引用上一步提取的值
   （如登录拿到的 token 传给下一个接口的请求头），实现接口链路串联。
"""
import json
import re

import requests

import config
from core import assertions as assert_engine

VAR_RE = re.compile(r"\$\{(\w+)\}")   # 匹配 ${变量名}


def _render(template, context):
    """把模板字符串里的 ${var} 替换为 context 中的值。"""
    if not template or "${" not in template:
        return template
    def _sub(m):
        key = m.group(1)
        return str(context.get(key, ""))
    return VAR_RE.sub(_sub, template)


def _parse_json_or_dict(value, fallback):
    if isinstance(value, dict):
        return value
    try:
        return json.loads(value) if value else fallback
    except Exception:
        return fallback


def run_case(case, context=None, base_url=None, data=None):
    """执行单条用例，context 为共享上下文（用于跨用例变量传递）。
    base_url: 当前环境基础地址；用例 url 以 / 开头时拼在其前面。
    data:     参数化单条数据（datalist 里的一项），并入变量上下文参与渲染。
    """
    context = dict(context or {})
    if data:
        context.update(data)                # 参数化数据优先级最高
    # 1. 渲染 url / headers / body，支持变量替换
    url = _render(case["url"], context)
    if url.startswith("/") and base_url:
        url = base_url.rstrip("/") + url    # 相对路径 -> 拼接当前环境基础地址
    headers = _render(case.get("headers") or "{}", context)
    body = _render(case.get("body") or "{}", context)
    headers = _parse_json_or_dict(headers, {})
    body = _parse_json_or_dict(body, {})

    # 2. 发请求
    try:
        resp = requests.request(
            case["method"], url, headers=headers, json=body or None,
            timeout=config.DEFAULT_TIMEOUT,
        )
    except Exception as e:
        return (False, f"请求失败: {e}", None, "", {})

    status_code = resp.status_code
    try:
        text = resp.text
    except Exception:
        text = ""

    # 3. 变量提取：从响应里取值，供后续用例引用
    extracted = {}
    extract_cfg = _parse_json_or_dict(case.get("extract") or "{}", {})
    try:
        resp_json = json.loads(text) if text else {}
    except Exception:
        resp_json = {}
    for var_name, path in extract_cfg.items():
        val = assert_engine._get_path(resp_json, path)
        if val is not None:
            extracted[var_name] = val

    # 4. 断言
    assertions = _parse_json_or_dict(case.get("assertions") or "[]", [])
    passed, details = assert_engine.run_assertions(assertions, status_code, text)
    return passed, "; ".join(details), status_code, text, extracted


def run_many(cases, shared_ctx=None, base_url=None):
    """顺序执行一组用例，支持跨用例变量传递（上一例提取的值供下一例引用）。
    用例配置了 datalist（参数化数据）时，对每条数据各执行一次并逐条记录结果。
    """
    shared_ctx = shared_ctx or {}
    outputs = []
    for c in cases:
        datalist = _parse_json_or_dict(c.get("datalist") or "[]", [])
        if not isinstance(datalist, list) or not datalist:
            # 普通用例：执行一次
            passed, detail, code, text, extracted = run_case(c, shared_ctx, base_url)
            shared_ctx.update(extracted)   # 本用例提取的变量合并，供后续用例使用
            outputs.append({"case": c, "passed": passed, "detail": detail,
                            "status_code": code, "response": text})
        else:
            # 数据驱动：对每条数据各执行一次
            for i, d in enumerate(datalist, 1):
                passed, detail, code, text, extracted = run_case(c, shared_ctx, base_url, data=d)
                shared_ctx.update(extracted)
                cc = dict(c)
                cc["_data_index"] = i       # 标记是第几条数据，结果展示用
                outputs.append({"case": cc, "passed": passed,
                                "detail": f"[数据{i}] {detail}",
                                "status_code": code, "response": text})
    return outputs