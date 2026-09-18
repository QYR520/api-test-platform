# -*- coding: utf-8 -*-
"""
数据层：把"测试用例"当作一条数据库记录来管理（用例 = 数据，而非代码）。
这是平台区别于 pytest 写死用例的本质：用户增删改用例都在库里完成，不用改代码。
"""
import os
import sqlite3

from config import DB_PATH

_DDL = """
CREATE TABLE IF NOT EXISTS cases (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project     TEXT DEFAULT '默认项目',       -- 所属项目/分组，实现多项目隔离
    name        TEXT NOT NULL,               -- 用例名
    method      TEXT NOT NULL,               -- GET/POST/PUT/DELETE
    url         TEXT NOT NULL,               -- 接口地址
    headers     TEXT DEFAULT '{}',           -- 请求头(JSON字符串)
    body        TEXT DEFAULT '{}',           -- 请求体(JSON字符串)
    assertions  TEXT DEFAULT '[]',           -- 断言规则(JSON数组字符串)
    extract     TEXT DEFAULT '{}',           -- 变量提取配置(JSON字符串)
    enabled     INTEGER DEFAULT 1,           -- 1启用 0停用
    sort        INTEGER DEFAULT 0,           -- 执行顺序，升序执行，支持流程中间插入节点
    datalist    TEXT DEFAULT '[]'            -- 数据驱动参数化：JSON数组，每条数据执行一次
);

CREATE TABLE IF NOT EXISTS results (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id     INTEGER NOT NULL,            -- 关联用例
    status_code INTEGER,                     -- 实际http状态码
    response    TEXT,                        -- 响应体
    passed      INTEGER,                     -- 1通过 0失败
    detail      TEXT,                        -- 断言明细/失败原因
    run_at      TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS environments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,               -- 环境名，如 本地演示 / 测试环境 / 生产
    base_url    TEXT NOT NULL,               -- 环境基础地址，用例相对路径(/开头的url)拼在此前面
    is_default  INTEGER DEFAULT 0            -- 1=当前使用环境
);

CREATE TABLE IF NOT EXISTS schedules (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,               -- 任务名，如 每晚电商回归
    project     TEXT DEFAULT '',             -- 要运行的项目(空=全部)
    hour        INTEGER DEFAULT 0,           -- 每日执行小时
    minute      INTEGER DEFAULT 0,           -- 每日执行分钟
    webhook     TEXT DEFAULT '',             -- 失败通知webhook(企业微信/钉钉/Slack)
    enabled     INTEGER DEFAULT 1            -- 1启用 0停用
);
"""


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.executescript(_DDL)
    # 兼容迁移：旧库缺列时补上
    cols = [r[1] for r in conn.execute("PRAGMA table_info(cases)").fetchall()]
    if "project" not in cols:
        conn.execute("ALTER TABLE cases ADD COLUMN project TEXT DEFAULT '默认项目'")
    if "sort" not in cols:
        conn.execute("ALTER TABLE cases ADD COLUMN sort INTEGER DEFAULT 0")
        # 旧数据按 id 顺序初始化 sort，保证原有顺序不被打乱
        conn.execute(
            "UPDATE cases SET sort=id*10 WHERE sort=0 OR sort IS NULL"
        )
    if "datalist" not in cols:
        conn.execute("ALTER TABLE cases ADD COLUMN datalist TEXT DEFAULT '[]'")
    # 首次建库时 seed 两个演示环境
    if not conn.execute("SELECT COUNT(*) FROM environments").fetchone()[0]:
        conn.execute(
            "INSERT INTO environments(name,base_url,is_default) VALUES('本地演示','http://127.0.0.1:5000',1)"
        )
        conn.execute(
            "INSERT INTO environments(name,base_url,is_default) VALUES('电商后端','http://localhost:3000',0)"
        )
    conn.commit()
    conn.close()


def list_projects():
    conn = get_conn()
    rows = conn.execute("SELECT DISTINCT project FROM cases ORDER BY project").fetchall()
    conn.close()
    return [r["project"] for r in rows]


def list_cases(project=None):
    conn = get_conn()
    if project:
        rows = conn.execute(
            "SELECT * FROM cases WHERE project=? ORDER BY sort ASC, id ASC", (project,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM cases ORDER BY sort ASC, id ASC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_case(case_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_case(data):
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO cases(project,name,method,url,headers,body,assertions,extract,enabled,sort,datalist)"
        " VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (data.get("project", "默认项目"), data["name"], data["method"], data["url"],
         data.get("headers", "{}"), data.get("body", "{}"),
         data.get("assertions", "[]"), data.get("extract", "{}"), 1,
         int(data.get("sort", 0) or 0),
         data.get("datalist", "[]")),
    )
    conn.commit()
    cid = cur.lastrowid
    conn.close()
    return cid


def update_case(case_id, data):
    conn = get_conn()
    conn.execute(
        "UPDATE cases SET project=?,name=?,method=?,url=?,headers=?,body=?,assertions=?,extract=?,sort=?,datalist=? WHERE id=?",
        (data.get("project", "默认项目"), data["name"], data["method"], data["url"],
         data.get("headers", "{}"), data.get("body", "{}"),
         data.get("assertions", "[]"), data.get("extract", "{}"),
         int(data.get("sort", 0) or 0), data.get("datalist", "[]"), case_id),
    )
    conn.commit()
    conn.close()


def delete_case(case_id):
    conn = get_conn()
    conn.execute("DELETE FROM cases WHERE id=?", (case_id,))
    conn.execute("DELETE FROM results WHERE case_id=?", (case_id,))
    conn.commit()
    conn.close()


def save_result(case_id, status_code, response, passed, detail):
    conn = get_conn()
    conn.execute(
        "INSERT INTO results(case_id,status_code,response,passed,detail) VALUES(?,?,?,?,?)",
        (case_id, status_code, response, 1 if passed else 0, detail),
    )
    conn.commit()
    conn.close()


def list_results(limit=100):
    conn = get_conn()
    rows = conn.execute(
        "SELECT r.*, c.name AS case_name FROM results r "
        "LEFT JOIN cases c ON c.id=r.case_id ORDER BY r.id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------- 环境 ----------
def list_environments():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM environments ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_default_env():
    conn = get_conn()
    row = conn.execute("SELECT * FROM environments WHERE is_default=1").fetchone()
    conn.close()
    return dict(row) if row else None


def switch_env(env_id):
    """切换当前使用环境（is_default 唯一）。"""
    conn = get_conn()
    conn.execute("UPDATE environments SET is_default=0")
    conn.execute("UPDATE environments SET is_default=1 WHERE id=?", (env_id,))
    conn.commit()
    conn.close()


def create_env(name, base_url):
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO environments(name,base_url,is_default) VALUES(?,?,0)",
        (name, base_url),
    )
    conn.commit()
    eid = cur.lastrowid
    conn.close()
    return eid


# ---------- 定时任务 ----------
def list_schedules():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM schedules ORDER BY hour, minute, id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_schedule(data):
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO schedules(name,project,hour,minute,webhook,enabled) VALUES(?,?,?,?,?,?)",
        (data.get("name"), data.get("project", ""),
         int(data.get("hour", 0) or 0), int(data.get("minute", 0) or 0),
         data.get("webhook", ""), 1 if data.get("enabled", True) else 0),
    )
    conn.commit()
    sid = cur.lastrowid
    conn.close()
    return sid


def update_schedule(sid, data):
    conn = get_conn()
    conn.execute(
        "UPDATE schedules SET name=?,project=?,hour=?,minute=?,webhook=?,enabled=? WHERE id=?",
        (data.get("name"), data.get("project", ""),
         int(data.get("hour", 0) or 0), int(data.get("minute", 0) or 0),
         data.get("webhook", ""), 1 if data.get("enabled", True) else 0, sid),
    )
    conn.commit()
    conn.close()


def delete_schedule(sid):
    conn = get_conn()
    conn.execute("DELETE FROM schedules WHERE id=?", (sid,))
    conn.commit()
    conn.close()