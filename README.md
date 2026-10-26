# 英雄联盟瑞士轮模拟器

基于 Django 的 16 队英雄联盟瑞士轮模拟器。支持自定义胜率矩阵、队伍名称和赛区，可以执行一次完整模拟，也可以批量执行 10,000 次统计模拟。

## 功能

- 16 支队伍、最多 5 轮瑞士轮
- 3 胜晋级、3 败淘汰
- 按当前胜负记录分池配对
- BO3/BO1 自动切换
- 自定义 16×16 胜率矩阵
- 自定义队伍名称和赛区
- 避免重复对战和同赛区对战，并提供回退配对
- 单次详细结果和 10,000 次统计结果
- 统计 9–16 号队伍在晋级队伍中的数量分布

## 赛制规则

- 每支队伍最多进行 5 轮比赛。
- 累计 3 胜晋级，累计 3 败淘汰。
- 相同胜负记录（例如 2-0、1-1）的队伍进入同一轮次池。
- 记录为 `2-0`、`2-1`、`2-2`、`1-2`、`0-2` 时使用 BO3，其他记录使用 BO1。
- 每小局必分胜负。
- 配对时优先避免重复对战，其次避免同赛区对战；无法同时满足时优先避免重复对战。
- 在页面上会标记违反配对规则的对局。

## 环境

- Python 3.10+
- Django 5.2.7
- `tzdata`（在 Windows 上没有系统时区库时需要）

依赖版本见 `requirements.txt`。

## 安装与运行

```bash
python -m venv .venv

# Linux
source .venv/bin/activate
# Windows PowerShell
# .venv\Scripts\Activate.ps1

python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

浏览器访问 `http://127.0.0.1:8000/`。

当前使用 SQLite。`db.sqlite3` 是运行时生成的 Django 数据库，已加入 `.gitignore`，不进入版本库。

## API

### `POST /simulate/`

请求体：

```json
{
  "mode": "single",
  "win_rates": [[0, 0.6, "..."], ["..."]],
  "team_names": ["队伍 1", "队伍 2", "..."],
  "regions": [1, 2, 3, "..."]
}
```

字段说明：

- `mode`：`single` 或 `multi`
- `win_rates`：16×16 数字矩阵，主对角线必须为 0
- `team_names`：16 个字符串
- `regions`：16 个整数，范围 1–16

单次模拟返回 `type=result` 以及每轮分池、对局、小局胜者和晋级队伍；批量模拟返回 10,000 次运行中每支队伍的晋级次数，以及晋级队伍中 9–16 号队伍数量分布。

## 项目结构

```text
manage.py
requirements.txt
swiss_sim/
├─ settings.py       # Django 配置、SQLite、zh-hans、Asia/Shanghai
└─ urls.py           # 根路由
simulator/
├─ views.py          # 赛制、配对和模拟算法
├─ urls.py           # 页面与 API 路由
├─ templates/
│  └─ index.html     # 单页交互界面
├─ models.py         # 当前无业务模型
└─ tests.py          # 当前没有自动化测试
```

## 已知限制

- 模拟使用随机数，结果不可复现；当前没有保存随机种子。
- 模拟结果不写入数据库，数据库只用于 Django Admin、认证和会话。
- 尚未实现自动化测试和前后端分离。
- `settings.py` 使用开发配置；正式部署前需要修改 `SECRET_KEY`、`DEBUG`、`ALLOWED_HOSTS`，并配置静态文件服务。
- 当前依赖解析使用 SQLite，若需要多人共享结果，应单独设计持久化层。