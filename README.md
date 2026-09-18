# 接口自动化测试平台（演示 Demo）

面向「测试转测开」的**代表作项目**。核心价值：把**测试用例变成数据库里的数据**，
由通用**执行引擎 + 断言引擎**解释执行——这与「用 pytest 把用例写成代码」有本质区别，
正是测开岗位要求的「造框架、做工具」能力。

## 它能证明的测开能力（面试自检清单）

| 能力 | 在本项目的体现 |
|------|---------------|
| 平台开发 | Flask + SQLite 前后端，用例 CRUD |
| 用例数据化 | 用例存库，加改用例不用改代码 |
| 执行引擎 | requests 通用请求器，读取配置发请求 |
| 断言引擎 | 4 类断言规则配置驱动，非写死代码 |
| 变量传递(链路) | ${token} 占位符串联登录→查用户 |
| 工程化/CI | GitHub Actions 自动跑冒烟回归 |

## 快速开始

```bash
cd api_test_platform
pip install -r requirements.txt
python app.py            # 启动，开 http://127.0.0.1:5000
```
打开页面直接点「运行全部用例」——会自动写入 3 条演示用例（含跨接口 token 传递）。

## 无服务器跑通核心（CI 也是这条）

```bash
python run_smoke.py      # 不经 UI，直接验证引擎+变量传递，输出 PASS/FAIL
python -m pytest -q      # 若有 pytest，运行 fixtures 版冒烟
```

## 接 CI（GitHub Actions）

`.github/workflows/test.yml` 已配好，把项目推到 GitHub 即自动运行
`run_smoke.py` + `pytest`，失败会报警告。这就是简历里「自动化接入 CI」的真实来源。

## 目录结构

```
api_test_platform/
├── app.py                # Flask 入口 + 内置 mock 演示接口
├── config.py             # 配置
├── requirements.txt
├── run_smoke.py          # CI/离线冒烟入口
├── core/
│   ├── database.py       # 数据层：用例/结果存 SQLite（用例=数据）
│   ├── assertions.py     # 断言引擎：配置驱动的 4 类断言
│   └── executor.py       # 执行引擎：发请求+变量提取/传递+断言
├── templates/            # 页面：用例列表 / 用例编辑
├── static/               # 样式
└── .github/workflows/    # CI 配置
```

## 面试话术要点

> 「我用 Flask 搭了个接口自动化平台，核心不是包装 pytest，而是把每一条用例结构化存进
> 数据库，自研的执行引擎和断言引擎去解释执行。加接口用例在页面表单里填即可，不碰代码；
> 还做了变量传递，上一个接口提取的 token 用 \${token} 占位符传给下一个接口，实现跨接口
> 链路串联；并用 GitHub Actions 把冒烟回归接到 CI，提交即自动跑、失败即告警。」

## 后续可升级方向（加分）

- 用例分组/套件、定时执行、结果趋势图表
- 请求参数变量来源扩展（全局变量/环境切换）
- 用该平台的脚本进行性能冒烟（并发）