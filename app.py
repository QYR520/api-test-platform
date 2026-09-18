# -*- coding: utf-8 -*-
"""
Flask 应用：提供页面 + API + 内置 mock 演示接口。
启动:  python app.py   ->  浏览器打开 http://127.0.0.1:5000

内置 mock 接口（供离线演示，不依赖外网）：
  POST /mock/login   返回 {code:0, data:{token:"...", username:"test"}}
  GET  /mock/user?token=xx  校验 token，返回 {code:0, data:{name:...}}
  GET  /mock/health  返回文本平台健康
"""
import json
import os
import threading
import time
from datetime import datetime

import requests
from flask import Flask, request, render_template, redirect, url_for, jsonify

from config import HOST, PORT
from core import database as db
from core import executor as ex

app = Flask(__name__)

# 简单内存 token 存储，演示跨接口变量传递
_TOKENS = set()


# ---------- 内置 mock 演示接口 ----------
@app.post("/mock/login")
def mock_login():
    payload = request.get_json(silent=True) or {}
    token = f"tk-{payload.get('username', 'test')}"
    _TOKENS.add(token)
    return jsonify({"code": 0, "data": {"token": token, "username": payload.get("username", "test")}})


@app.get("/mock/user")
def mock_user():
    token = request.args.get("token", "")
    if token not in _TOKENS:
        return jsonify({"code": 403, "msg": "invalid token"}), 403
    return jsonify({"code": 0, "data": {"name": "张三", "dept": "研发"}})


@app.get("/mock/health")
def mock_health():
    return "platform-health-ok"


# ---------- 用例 CRUD ----------
@app.get("/")
def index():
    return render_template("index.html", cases=db.list_cases(), projects=db.list_projects(),
                           envs=db.list_environments(), current_env=db.get_default_env())


@app.get("/p/<project>")
def index_by_project(project):
    return render_template("index.html", cases=db.list_cases(project), projects=db.list_projects(),
                           current=project, envs=db.list_environments(), current_env=db.get_default_env())


@app.get("/case/<int:cid>")
def case_edit(cid):
    return render_template("case_edit.html", case=db.get_case(cid), projects=db.list_projects() or ["默认项目"])


@app.post("/api/case")
def api_create():
    data = request.get_json()
    cid = db.create_case(data)
    return jsonify({"ok": True, "id": cid})


@app.post("/api/case/<int:cid>")
def api_update(cid):
    db.update_case(cid, request.get_json())
    return jsonify({"ok": True})


@app.post("/api/case/<int:cid>/delete")
def api_delete(cid):
    db.delete_case(cid)
    return redirect(url_for("index"))


# ---------- 执行 ----------
def _env_base_url():
    env = db.get_default_env()
    return env["base_url"] if env else None


@app.post("/api/run/<int:cid>")
def api_run_one(cid):
    case = db.get_case(cid)
    if not case:
        return jsonify({"ok": False, "msg": "case not found"}), 404
    # 统一走 run_many：支持 datalist 参数化展开（多条数据逐条执行）
    outputs = ex.run_many([case], base_url=_env_base_url())
    for o in outputs:
        db.save_result(cid, o["status_code"], o["response"], o["passed"], o["detail"])
    all_passed = all(o["passed"] for o in outputs)
    return jsonify({"ok": True, "passed": all_passed,
                    "detail": "; ".join(o["detail"] for o in outputs),
                    "total": len(outputs), "outputs": outputs,
                    "status_code": outputs[0]["status_code"] if outputs else None,
                    "response": outputs[0]["response"] if outputs else ""})


@app.post("/api/run/all")
def api_run_all():
    project = request.args.get("project")          # 可选：按项目隔离运行
    cases = [c for c in db.list_cases(project) if c.get("enabled")]
    outputs = ex.run_many(cases, base_url=_env_base_url())
    for o in outputs:
        db.save_result(o["case"]["id"], o["status_code"], o["response"],
                       o["passed"], o["detail"])
    passed_count = sum(1 for o in outputs if o["passed"])
    return jsonify({"ok": True, "total": len(outputs),
                    "passed": passed_count, "failed": len(outputs) - passed_count,
                    "outputs": outputs})


@app.get("/api/results")
def api_results():
    return jsonify(db.list_results())


# ---------- 环境切换 ----------
@app.get("/api/env")
def api_env_list():
    return jsonify({"envs": db.list_environments(), "current": db.get_default_env()})


@app.post("/api/env/switch")
def api_env_switch():
    db.switch_env(int(request.json.get("env_id")))
    return jsonify({"ok": True, "current": db.get_default_env()})


@app.post("/api/env")
def api_env_create():
    db.create_env(request.json.get("name"), request.json.get("base_url"))
    return jsonify({"ok": True})


# ---------- 测试报告 ----------
@app.get("/api/report")
def api_report():
    conn = db.get_conn()
    total_cases = conn.execute(
        "SELECT COUNT(*) FROM cases WHERE enabled=1").fetchone()[0]
    total_runs = conn.execute("SELECT COUNT(*) FROM results").fetchone()[0]
    passed_runs = conn.execute(
        "SELECT COUNT(*) FROM results WHERE passed=1").fetchone()[0]

    # 按项目统计
    proj_rows = conn.execute(
        "SELECT project, COUNT(*) AS cnt FROM cases WHERE enabled=1 GROUP BY project"
    ).fetchall()
    projects = []
    for r in proj_rows:
        pid = r["project"]
        run = conn.execute(
            "SELECT COUNT(*) AS n, SUM(passed) AS ok FROM results r "
            "LEFT JOIN cases c ON c.id=r.case_id WHERE c.project=? AND c.project IS NOT NULL",
            (pid,),
        ).fetchone()
        projects.append({
            "name": pid, "case_count": r["cnt"],
            "run_count": run["n"], "pass_count": run["ok"] or 0,
            "pass_rate": round((run["ok"] or 0) / run["n"] * 100) if run["n"] else None,
        })

    # 最近7天趋势（按日期）
    trend_rows = conn.execute(
        "SELECT date(run_at) AS d, COUNT(*) AS n, SUM(passed) AS ok "
        "FROM results WHERE run_at >= datetime('now','-7 days') "
        "GROUP BY date(run_at) ORDER BY d"
    ).fetchall()
    trend = [{"date": r["d"], "count": r["n"],
              "pass_rate": round((r["ok"] or 0) / r["n"] * 100)} for r in trend_rows]

    conn.close()
    return jsonify({
        "total_cases": total_cases, "total_runs": total_runs,
        "pass_rate": round(passed_runs / total_runs * 100) if total_runs else None,
        "projects": projects, "trend": trend,
        "recent": db.list_results(10),
    })


@app.get("/report")
def report_page():
    return render_template("report.html")


# ---------- 定时任务 ----------
@app.get("/api/schedules")
def api_schedules():
    return jsonify(db.list_schedules())


@app.post("/api/schedule")
def api_schedule_save():
    data = request.json
    if data.get("id"):
        db.update_schedule(int(data["id"]), data)
    else:
        db.create_schedule(data)
    return jsonify({"ok": True})


@app.post("/api/schedule/<int:sid>/delete")
def api_schedule_delete(sid):
    db.delete_schedule(sid)
    return jsonify({"ok": True})


def run_scheduled(s):
    """执行一次定时任务：跑项目全部用例 -> 存结果 -> 失败时 webhook 通知。"""
    project = s["project"]
    cases = [c for c in db.list_cases(project) if c.get("enabled")]
    if not cases:
        return
    outputs = ex.run_many(cases, base_url=_env_base_url())
    for o in outputs:
        db.save_result(o["case"]["id"], o["status_code"], o["response"],
                       o["passed"], o["detail"])
    failed = [o for o in outputs if not o["passed"]]
    if failed and s.get("webhook"):
        try:
            requests.post(s["webhook"], timeout=5, json={
                "msgtype": "text",
                "text": {"content": f"[测试平台]定时任务「{s['name']}」失败 {len(failed)} 条\n"
                                    + "\n".join(f"- {o['case']['name']}: {o['detail'][:100]}"
                                                for o in failed[:5])},
            })
        except Exception:
            pass


def scheduler_loop():
    """后台守护线程：每30秒检查一次，到点(时:分)触发每日定时任务。"""
    fired = set()
    while True:
        now = datetime.now()
        for s in db.list_schedules():
            if not s.get("enabled"):
                continue
            key = f"{s['id']}_{now.strftime('%Y-%m-%d')}"
            if (now.hour, now.minute) == (s["hour"], s["minute"]) and key not in fired:
                fired.add(key)
                try:
                    run_scheduled(s)
                except Exception:
                    pass
        time.sleep(30)


# ---------- 初始化 + 启动 ----------
def seed():
    """首次运行写入两条演示用例（含跨接口 token 传递），便于直接点击运行。"""
    if db.list_cases():
        return
    demo = {"project": "演示项目"}
    db.create_case({
        **demo,
        "name": "示例1-登录获取token",
        "method": "POST", "url": "http://127.0.0.1:5000/mock/login",
        "headers": "{}",
        "body": '{"username": "tester"}',
        "assertions": '[{"type":"status_code","expect":200},{"type":"json_eq","path":"code","expect":0},{"type":"json_contains","path":"data.token"}]',
        "extract": '{"token": "data.token"}',
    })
    db.create_case({
        **demo,
        "name": "示例2-带token查用户(跨用例变量传递)",
        "method": "GET", "url": "http://127.0.0.1:5000/mock/user?token=${token}",
        "headers": "{}", "body": "{}",
        "assertions": '[{"type":"status_code","expect":200},{"type":"json_eq","path":"code","expect":0}]',
        "extract": '{}',
    })
    db.create_case({
        **demo,
        "name": "示例3-健康检查文本包含",
        "method": "GET", "url": "http://127.0.0.1:5000/mock/health",
        "headers": "{}", "body": "{}",
        "assertions": '[{"type":"status_code","expect":200},{"type":"text_contains","expect":"ok"}]',
        "extract": '{}',
    })


def main():
    db.init_db()
    seed()
    # 仅主进程启动调度线程（debug reloader 会跑两个进程，避免重复）
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or app.debug is False:
        threading.Thread(target=scheduler_loop, daemon=True).start()
    app.run(host=HOST, port=PORT, debug=True)


if __name__ == "__main__":
    main()