# Oracle 数据库监控告警程序

> 一个轻量级、跨平台的 Oracle 数据库健康监测工具。定时轮询数据库状态，异常时写入日志并通过 SMTP 邮件通知管理员。

[![License: Mulan PubL v2](https://img.shields.io/badge/License-Mulan%20PubL%20v2-3f51b5.svg)](https://license.coscl.org.cn/MulanPubL-2.0)
[![GitHub stars](https://img.shields.io/github/stars/miralexand/oracle-monitor?style=social)](https://github.com/miralexand/oracle-monitor/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/miralexand/oracle-monitor?style=social)](https://github.com/miralexand/oracle-monitor/network/members)
[![GitHub issues](https://img.shields.io/github/issues/miralexand/oracle-monitor)](https://github.com/miralexand/oracle-monitor/issues)
[![Last commit](https://img.shields.io/github/last-commit/miralexand/oracle-monitor)](https://github.com/miralexand/oracle-monitor/commits/main)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](https://github.com/miralexand/oracle-monitor)
[![Build Windows EXE](https://github.com/miralexand/oracle-monitor/actions/workflows/build-release.yml/badge.svg)](https://github.com/miralexand/oracle-monitor/actions/workflows/build-release.yml)

## 界面预览

![Oracle 数据库监控面板](docs/%E7%9B%91%E6%8E%A7%E9%9D%A2%E6%9D%BF.png)

> Web 管理面板：整体健康状态、各库可用率环形图、响应时间曲线、24h/7d 告警趋势等，详见 [13.3 Docker 部署](#133-docker-部署web-管理面板推荐)。

---

## 目录

- [1. 项目简介](#1-项目简介)
- [2. 功能特性](#2-功能特性)
- [3. 监控项说明](#3-监控项说明)
- [4. 环境要求](#4-环境要求)
- [5. 项目结构](#5-项目结构)
- [6. 快速开始](#6-快速开始)
- [7. 配置文件详解](#7-配置文件详解)
- [8. 定时执行](#8-定时执行)
- [9. 日志说明](#9-日志说明)
- [10. 常见邮箱 SMTP 配置](#10-常见邮箱-smtp-配置)
- [11. 如何新增监控项](#11-如何新增监控项)
- [12. 常见问题 FAQ](#12-常见问题-faq)
- [13. 打包与部署](#13-打包与部署)
- [14. 敏感数据与安全](#14-敏感数据与安全)
- [15. 许可证](#15-许可证)
- [Star History](#star-history)

---

## 1. 项目简介

本程序用于在本地电脑或服务器上**定时检测 Oracle 数据库的健康状态**，覆盖数据库连通性、表空间使用率、活跃会话数、长事务、锁等待、RMAN 备份结果、告警日志 ORA- 错误等关键指标。支持**同时监控多个数据库**，并提供 **Web 管理面板**（Docker 部署）用于查看实时状态、稳定性趋势与日志，以及在线配置 SMTP、检测间隔和多数据库。

一旦检测到异常：

1. 按天写入日志文件 `logs/monitor_YYYYMMDD.log`
2. 通过 SMTP 邮件将告警发送给指定收件人
3. 恢复正常后也发送"恢复通知"（可选）

程序基于 **Python 3.9+** 编写（推荐 3.11），依赖较少，可运行于 Windows / Linux / macOS。

---

## 2. 功能特性

| 特性 | 说明 |
|------|------|
| 定时轮询 | 间隔可配置（默认 15 分钟），Web 在线修改 |
| 多数据库 | 支持添加任意多个 Oracle 实例，统一监控 |
| 多指标检测 | 连通性、表空间、会话、锁、长事务、备份、告警日志 |
| Web 管理面板 | Docker 一键部署，看板 / 日志 / 配置全部在线管理 |
| 稳定性趋势 | 每个库的 24h 可用率、最近 30 次检测状态可视化 |
| 图表面板 | 可用率环形图、响应时间曲线、24h/7d 告警柱状图，通俗易懂 |
| 明暗主题 | 一键切换明亮 / 暗黑主题，跟随系统偏好并记忆 |
| 阈值可配 | 所有阈值集中在 Web 设置或 `config.ini` 中管理 |
| 按天日志 | 日志自动按日期分文件，支持在线查看与下载 |
| SMTP 邮件告警 | 支持 TLS / SSL，兼容 QQ、163、Gmail、企业邮箱 |
| 恢复通知 | 告警解除后发送恢复邮件，避免"狼来了"效应 |
| 配置备份 | 数据库账号密码等加密导出为文件，Web 一键下载 |
| 配置恢复 | 上传加密备份文件即可恢复全部数据库与设置 |
| 登录鉴权 | 默认账号 admin/admin123，密码哈希存储、前端 SHA-256 预哈希 |
| 用户管理 | 管理员 / 只读两种角色，可增删用户、重置密码 |
| 日志细分 | 按级别、数据库、关键字筛选查看，可导出筛选结果 |
| 告警忽略 | 可忽略单条或全部活动告警，不再发送通知，全部忽略后状态显示为「正常」，恢复后自动重置 |
| 敏感数据加密 | 数据库账号/密码、SMTP 授权码以 Fernet(AES) 密文存储，非明文 |
| NTP 校时 | 自定义 NTP 服务器与时间地区（默认上海），启动与每 5 小时自动校时，日志毫秒级精准 |
| 服务运行时间 | 面板展示监控服务已运行时长与启动时间 |
| 无侵入 | 只读查询，不对数据库做任何写操作 |
| 旧版本兼容 | 内置 Oracle Instant Client，Thick 模式支持 11g 等旧库 |
| 单文件运行 | 核心逻辑集中，便于二次开发 |

---

## 3. 监控项说明

| 编号 | 监控项 | 数据来源 | 默认阈值 | 说明 |
|------|--------|----------|----------|------|
| M1 | 数据库连通性 | `SELECT 1 FROM DUAL` | 连接失败即告警 | 最基本的存活检测 |
| M2 | 实例状态 | `v$instance.status` | 非 `OPEN` 即告警 | 检测实例是否挂起 |
| M3 | 表空间使用率 | `dba_tablespace_usage_metrics` | > 85% | 防止磁盘写满 |
| M4 | 活跃会话数 | `v$session` | > 500 | 检测会话泄漏/攻击 |
| M5 | 长时间运行 SQL | `v$session` + `v$sql` | > 3600 秒 | 发现慢查询 |
| M6 | 阻塞锁等待 | `v$lock` + `v$session` | > 300 秒 | 发现锁竞争 |
| M7 | 归档目录空间 | `v$recovery_file_dest` | > 85% | 防止归档满导致数据库挂起 |
| M8 | RMAN 备份状态 | `v$rman_backup_job_details` | 24 小时内失败即告警 | 备份巡检 |
| M9 | 告警日志 ORA- 错误 | `alert_<SID>.log` 文件 | 出现 `ORA-00600/ORA-07445` 等即告警 | 捕获严重错误 |

> 默认启用 M2–M6，M7–M9 为可选模块（在 `config.ini` 或 Web「设置 → 监控模块」中开启）。M1 连通性由连接过程自动判定。

---

## 4. 环境要求

| 项目 | 要求 |
|------|------|
| 操作系统 | Windows 10+ / Linux (CentOS 7+ / Ubuntu 18.04+) / macOS 10.15+ |
| Python | 3.9 及以上（推荐 3.11） |
| Oracle | 11g R2 / 12c / 18c / 19c / 21c / 23c |
| 网络 | 可访问 Oracle 监听端口（默认 1521）与 SMTP 服务器端口 |
| 权限 | 数据库账号至少具备 `SELECT` on `V_$SESSION`、`V_$INSTANCE`、`DBA_TABLESPACE_USAGE_METRICS` 等视图 |
| 内存 | ≥ 100 MB |
| 磁盘 | ≥ 50 MB（用于日志） |

---

## 5. 项目结构

```
oracle-monitor/
├── config.ini              # 主配置文件（CLI / EXE 方式必填）
├── config.sample.ini       # 配置模板（参考用）
├── requirements.txt        # Python 依赖
├── monitor.py              # CLI / EXE 主程序入口
├── checks.py               # 各监控项检测逻辑（M1–M9）
├── mailer.py               # 邮件发送模块
├── logger.py               # 日志模块
├── settings.py             # 配置模型（Web 端使用）
├── oracle_conn.py          # Thin / Thick 连接管理
├── messages.py             # 告警邮件正文模板
├── auth.py                 # 登录认证与口令哈希
├── cryptoutil.py           # 敏感字段 Fernet 加密
├── timesync.py             # NTP 软件校时
├── logview.py              # 日志解析与筛选
├── backup.py               # 配置加密备份/恢复
├── store.py                # SQLite 数据访问（多库/设置/历史/告警/用户）
├── scheduler.py            # 后台检测调度
├── webapp.py               # Flask 路由与 API
├── run_web.py              # Web 入口（waitress）
├── templates/ static/      # Web 页面与静态资源
├── Dockerfile
├── docker-compose.yml
├── data/                   # Web 版持久化数据（自动生成）
├── state.json              # 告警状态持久化（CLI 模式自动生成）
├── logs/                   # 日志目录（自动生成）
│   └── monitor_20250101.log
└── readme.md               # 本文档
```

| 运行方式 | 入口 | 配置来源 | 适用场景 |
|----------|------|----------|----------|
| Web（Docker，推荐） | `run_web.py` | Web 页面 + SQLite | 多数据库、集中看板、在线配置 |
| CLI / EXE | `monitor.py` | `config.ini` | 单机、任务计划程序、cron |

---

## 6. 快速开始

### 6.1 克隆项目

```bash
git clone https://github.com/miralexand/oracle-monitor.git
cd oracle-monitor
```

### 6.2 创建虚拟环境（推荐）

**Windows：**
```bat
python -m venv venv
venv\Scripts\activate
```

**Linux / macOS：**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 6.3 安装依赖

```bash
pip install -r requirements.txt
```

`requirements.txt` 内容：

```txt
oracledb>=2.0.0
Flask>=3.0.0
waitress>=3.0.0
cryptography>=41.0.0
tzdata>=2024.1
```

> - `oracledb` 是 `cx_Oracle` 的官方下一代驱动，默认 Thin 模式，连接 **Oracle 12.1+** 无需安装 Instant Client；
>   连接 11g 等旧库需 Thick 模式（Docker 镜像已内置客户端）。
> - `Flask` + `waitress` 用于 Web 管理面板；`cryptography` 用于敏感字段加密与 Thin 模式；
>   `tzdata` 提供时区数据（NTP/时区功能）。
> - 仅使用 CLI / EXE（`monitor.py`）时，也可只安装 `oracledb` 与 `tzdata`。

### 6.4 准备配置

```bash
cp config.sample.ini config.ini
```

编辑 `config.ini`，填入数据库、SMTP 信息（详见 [第 7 节](#7-配置文件详解)）。

### 6.5 运行一次自检

```bash
python monitor.py --once
```

若配置正确，控制台会输出：

```
2025-01-01 10:00:00.123 [INFO] 加载配置成功: config.ini
2025-01-01 10:00:00.456 [INFO] 开始执行数据库检查: ORCL (192.168.1.100:1521)
2025-01-01 10:00:00.789 [INFO] 数据库连接成功: ORCL
2025-01-01 10:00:01.012 [INFO] 所有检查通过，无告警
```

### 6.6 启动持续监控

```bash
python monitor.py
```

按 `Ctrl+C` 停止。

---

## 7. 配置文件详解

`config.ini` 完整示例：

```ini
[oracle]
# 数据库主机（IP 或域名）
host = 192.168.1.100
# 监听端口
port = 1521
# 服务名（SERVICE_NAME）或 SID
service_name = ORCL
# 或使用 SID 方式（与 service_name 二选一）
# sid = ORCL
# 监控账号
user = monitor_user
password = your_password
# 连接超时（秒）
connect_timeout = 10

[smtp]
# SMTP 服务器地址
server = smtp.qq.com
# 端口：465 (SSL) / 587 (TLS) / 25 (明文，不推荐)
port = 465
# 加密方式：ssl / tls / none
encryption = ssl
# 发件人邮箱
sender = monitor@example.com
# 发件人授权码（不是登录密码！）
password = xxxxxxxxxxxxxxxx
# 收件人（多个用英文逗号分隔）
receivers = dba@example.com,ops@example.com
# 邮件主题前缀
subject_prefix = [Oracle监控]

[thresholds]
# 表空间使用率告警阈值（百分比）
tablespace_usage_pct = 85
# 活跃会话数阈值
session_count = 500
# 长事务运行秒数阈值
long_query_seconds = 3600
# 锁等待秒数阈值
lock_wait_seconds = 300
# 归档目录使用率阈值（百分比）
archive_usage_pct = 85
# RMAN 备份允许的最大间隔（小时）
rman_backup_interval_hours = 24

[modules]
# 是否启用各监控项，true / false（M1 连通性由连接过程自动判定，无独立开关）
enable_m2_instance_status = true
enable_m3_tablespace = true
enable_m4_session_count = true
enable_m5_long_query = true
enable_m6_lock_wait = true
enable_m7_archive_space = false
enable_m8_rman_backup = false
enable_m9_alert_log = false

[schedule]
# 检测间隔（分钟），默认 15 分钟以降低数据库轮询压力
interval_minutes = 15

[logging]
# 日志级别：DEBUG / INFO / WARNING / ERROR
level = INFO
# 日志目录
dir = logs
# 日志保留天数（0 表示不清理）
retention_days = 30

[alert]
# 恢复后是否发送恢复通知
notify_on_recovery = true
# 同一告警静默期（分钟），避免刷屏
silence_minutes = 30
```

### 7.1 关键字段说明

| 字段 | 是否必填 | 说明 |
|------|----------|------|
| `oracle.host` | ✅ | 数据库 IP 或域名 |
| `oracle.port` | ✅ | 默认 1521 |
| `oracle.service_name` | ✅（或 sid） | 服务名 |
| `oracle.user` / `password` | ✅ | 监控账号 |
| `smtp.server` / `port` | ✅ | SMTP 服务器 |
| `smtp.sender` / `password` | ✅ | 发件邮箱和**授权码** |
| `smtp.receivers` | ✅ | 收件人列表 |
| `thresholds.*` | ✅ | 各类阈值 |

> ⚠️ **注意**：QQ、163、Gmail 等邮箱的 `password` 字段填的是 **授权码**，不是邮箱登录密码。开启方式见 [第 10 节](#10-常见邮箱-smtp-配置)。

### 7.2 数据库账号权限

推荐新建只读账号：

```sql
CREATE USER monitor_user IDENTIFIED BY "YourPassword";
GRANT CREATE SESSION TO monitor_user;
GRANT SELECT ON V_$INSTANCE TO monitor_user;
GRANT SELECT ON V_$SESSION TO monitor_user;
GRANT SELECT ON V_$SQL TO monitor_user;
GRANT SELECT ON V_$LOCK TO monitor_user;
GRANT SELECT ON DBA_TABLESPACE_USAGE_METRICS TO monitor_user;
GRANT SELECT ON V_$RECOVERY_FILE_DEST TO monitor_user;
GRANT SELECT ON V_$RMAN_BACKUP_JOB_DETAILS TO monitor_user;
```

---

## 8. 定时执行

### 8.1 Windows — 任务计划程序

1. 按 `Win + R`，输入 `taskschd.msc`，回车
2. 右侧点击 **创建基本任务**
3. 名称：`Oracle监控`；触发器：**每天** → 重复间隔 **15 分钟**，持续时间 **无限期**
4. 操作：**启动程序**
   - 程序：`C:\path\to\venv\Scripts\python.exe`
   - 参数：`C:\path\to\monitor.py --once`
   - 起始于：`C:\path\to\`
5. 完成 → 右键任务 → 属性 → 勾选 **不管用户是否登录都要运行** 和 **使用最高权限运行**

> 使用 `--once` 参数表示单次执行，由任务计划程序负责循环。

### 8.2 Linux — crontab

```bash
crontab -e
```

添加：

```cron
# 每 15 分钟运行一次
*/15 * * * * cd /opt/oracle_monitor && /opt/oracle_monitor/venv/bin/python monitor.py --once >> /opt/oracle_monitor/logs/cron.log 2>&1
```

或使用 `systemd` 常驻：

```ini
# /etc/systemd/system/oracle-monitor.service
[Unit]
Description=Oracle Monitor Service
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/oracle_monitor
ExecStart=/opt/oracle_monitor/venv/bin/python monitor.py
Restart=always
RestartSec=10
User=oracle

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now oracle-monitor
sudo systemctl status oracle-monitor
```

### 8.3 macOS — launchd

参考 `launchd` plist 或直接用 `cron`（macOS 仍支持）。

---

## 9. 日志说明

### 9.1 日志位置

```
# CLI / EXE
logs/monitor_20250101.log
logs/monitor_20250102.log

# Docker / Web
/data/logs/monitor_20250101.log
```

按天自动切分，超过 `retention_days` 天的日志自动删除。Web 版可在「日志」页面在线筛选、查看与导出。

### 9.2 日志格式

时间精确到**毫秒**，并按所选时区显示（见 [13.5 时间同步](#135-时间同步ntp-校时)）：

```
2025-01-01 10:00:00.123 [INFO] 加载配置成功
2025-01-01 10:00:00.456 [INFO] 数据库连接成功: ORCL
2025-01-01 10:00:00.789 [WARNING] 表空间 USERS 使用率 88.3%，超过阈值 85%
2025-01-01 10:00:01.012 [INFO] 已发送告警邮件，共 1 条告警
2025-01-01 10:05:00.345 [INFO] 所有检查通过，无告警
2025-01-01 10:05:00.678 [INFO] 告警已恢复: 表空间 USERS
```

### 9.3 日志级别

| 级别 | 用途 |
|------|------|
| DEBUG | 调试信息（SQL 执行详情） |
| INFO | 正常流程 |
| WARNING | 告警触发 |
| ERROR | 连接失败、邮件发送失败等 |

---

## 10. 常见邮箱 SMTP 配置

| 邮箱 | SMTP 服务器 | 端口 | 加密 | 备注 |
|------|------------|------|------|------|
| QQ 邮箱 | `smtp.qq.com` | 465 | SSL | 需开启"IMAP/SMTP 服务"并生成授权码 |
| 163 邮箱 | `smtp.163.com` | 465 或 587 | SSL/TLS | 需开启 SMTP 并获取授权码 |
| Gmail | `smtp.gmail.com` | 587 | TLS | 需开启"应用专用密码" |
| Outlook | `smtp.office365.com` | 587 | TLS | 部分账号需 OAuth2 |
| 阿里云企业邮 | `smtp.qiye.aliyun.com` | 465 | SSL | 使用邮箱密码 |
| 腾讯企业邮 | `smtp.exmail.qq.com` | 465 | SSL | 使用邮箱密码 |

### 获取 QQ 邮箱授权码

1. 登录 QQ 邮箱 → 设置 → 账户
2. 找到 **IMAP/SMTP 服务** → 开启
3. 按提示发送短信 → 获取 16 位授权码
4. 将授权码填入 `config.ini` 的 `smtp.password`

---

## 11. 如何新增监控项

以"新增 **表锁数量** 监控（M10）"为例：

**Step 1** 在 `checks.py` 中新增检测函数。约定：返回 `(key, message)` 列表；
`key` 为稳定标识（用于静默/恢复/忽略判断），`message` 为人类可读描述，无异常时返回空列表：

```python
def check_table_locks(conn, threshold):
    """检查表级锁数量，返回 [(key, message), ...]"""
    alerts = []
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM v$lock WHERE type = 'TM'")
        count = int(cursor.fetchone()[0])
    finally:
        cursor.close()
    if count > threshold:
        alerts.append(("table_locks", f"表级锁数量 {count}，超过阈值 {threshold}"))
    return alerts
```

**Step 2** 在 `checks.py` 的 `run_checks()` 中注册（沿用 `_selected` / `_enabled` / `_threshold` 辅助函数）：

```python
if _selected(selected, "M10") and _enabled(config, "enable_table_locks", False):
    alerts += _run("M10", check_table_locks, conn, _threshold(config, "table_lock_count", 100))
```

**Step 3** 增加配置项：

- **Web / Docker**：在 `settings.py` 的 `DEFAULT_SETTINGS` 增加
  `"table_lock_count": "100"`、`"enable_table_locks": "false"`，并加入
  `webapp.py` 的 `EDITABLE_SETTING_KEYS` / `BOOLEAN_FORM_KEYS`，即可在设置页配置。
- **CLI / EXE**：在 `config.sample.ini` 的 `[thresholds]` / `[modules]` 增加对应项。

**Step 4** 在本文档第 3 节「监控项说明」表格中登记。

---

## 12. 常见问题 FAQ

### Q1: 连接报错 `DPI-1047` 或 `DPY-3010`

**`DPY-3010: connections to this database server version are not supported by python-oracledb in thin mode`**

**原因**：目标数据库版本过旧（低于 12.1），Thin 模式不支持。

**解决**：改用 Thick 模式。Docker 镜像已内置 Instant Client：进入
「设置 → 调度与连接」勾选「使用 Oracle Thick 模式」，Instant Client 目录填
`/opt/oracle/instantclient`，保存后重启容器（`docker compose restart`）。
本地 / EXE 运行请安装
[Oracle Instant Client](https://www.oracle.com/database/technologies/instant-client.html)
并配置 `PATH` / `LD_LIBRARY_PATH`。

**`DPI-1047: Cannot locate a 64-bit Oracle Client library`**

**原因**：启用了 Thick 模式但找不到 Instant Client 或缺少 `libaio`。

**解决**：确认「Instant Client 目录」正确、系统已安装 `libaio`，或改用 Thin 模式连接 12.1+ 数据库。

### Q2: 报错 `ORA-12541: TNS:no listener`

**原因**：监听未启动或网络不通。

**排查**：
```bash
telnet <host> 1521
```
若不通，请检查防火墙、监听状态（`lsnrctl status`）。

### Q3: 报错 `ORA-28000: the account is locked`

**解决**：
```sql
ALTER USER monitor_user ACCOUNT UNLOCK;
```

### Q4: 邮件发送失败 `SMTPAuthenticationError: 535`

**原因**：密码填的是登录密码，不是授权码；或未开启 SMTP 服务。

**解决**：见 [第 10 节](#10-常见邮箱-smtp-配置)。

### Q5: 中文邮件内容乱码

**解决**：代码已使用 `MIMEText(body, 'plain', 'utf-8')` 并设置 `Subject` 编码。若仍乱码，请检查 SMTP 服务器是否支持 UTF-8，或在 `mailer.py` 中使用 `email.header.Header` 编码主题。

### Q6: 定时任务不执行

- Windows：检查任务计划程序"上次运行结果"，确认 Python 路径正确、勾选"不管用户是否登录都要运行"
- Linux：`grep CRON /var/log/syslog` 查看 cron 日志；确保脚本路径为绝对路径

### Q7: 如何避免告警邮件轰炸？

**解决**：`config.ini` 中 `alert.silence_minutes = 30`，同一告警在 30 分钟内只发一次。

### Q8: 支持多个数据库同时监控吗？

**解决**：**Web / Docker 版原生支持**，在「数据库管理」中添加任意多个实例即可统一监控。
CLI / EXE 版为单实例（`config.ini`）；如需多实例，可复制多份目录并分别运行，或改用 Web 版。

### Q9: 数据库密码会不会明文存放？

**解决**：
- **Web / Docker 版**：数据库账号/密码与 SMTP 授权码在 SQLite 中以
  `Fernet`（AES-128-CBC + HMAC）**密文存储，不再明文落盘**；密钥见 `data.key` / `OM_DATA_KEY`。
  详见 [14. 敏感数据与安全](#14-敏感数据与安全)。
- **CLI / EXE 版**：`config.ini` 为明文，请用 `chmod 600` 保护并勿提交 Git；如需加密，建议改用 Web 版。
- 通用建议：使用只读账号；更强隔离可接入 HashiCorp Vault / KMS。

### Q10: 程序占用内存过高？

**解决**：`monitor.py --once` 模式由外部调度器控制，进程执行完即退出，内存占用最低。常驻模式内存稳定在 50 MB 以内。

---

## 13. 打包与部署

### 13.1 打包为单文件 EXE（Windows）

项目已内置打包脚本与 PyInstaller 配置，直接双击或命令行执行：

```bat
build_exe.bat
```

脚本会自动创建虚拟环境、安装依赖，并调用 `oracle_monitor.spec` 生成 `dist\oracle_monitor.exe`。

也可以手动执行：

```bash
pip install -r requirements.txt pyinstaller
pyinstaller --clean --noconfirm oracle_monitor.spec
```

> `oracle_monitor.spec` 已通过 `collect_all` 打入 `oracledb`、`cryptography`、`cffi`、`tzdata`
> （`python-oracledb` 的 Thin 模式依赖 `cryptography`，时区功能依赖 `tzdata`，缺省不会自动收集）。

**自动构建与发布**：仓库内置 GitHub Actions 工作流
`.github/workflows/build-release.yml`，推送 `v*` 标签会**自动构建 EXE 并发布到 GitHub Release**
（附带 `oracle_monitor.exe` 与 `.sha256`）；也可在 Actions 页面手动触发。
发布说明正文取自仓库根目录的 `RELEASE_NOTES.md`（中文），发布前请先更新该文件。

**分发与首次运行**：只需把单个 `dist\oracle_monitor.exe` 拷贝给用户。
首次运行会在 exe 同目录生成 `config.ini`，编辑后再次运行即可；日志 `logs\`
与状态 `state.json` 同样生成在 exe 所在目录，实现绿色便携。

### 13.2 打包为 Linux 可执行文件

在 Linux 上同样使用项目内置的 spec（会自动收集依赖与时区数据）：

```bash
pip install -r requirements.txt pyinstaller
pyinstaller --clean --noconfirm oracle_monitor.spec
# 产物：dist/oracle_monitor
```

> `/opt/oracle/instantclient` 等 Thick 模式客户端需在目标机器自行安装（见 [第 12 节](#12-常见问题-faq)）。

### 13.3 Docker 部署（Web 管理面板，推荐）

> **为什么需要 Thick 模式？** `python-oracledb` 的 Thin 模式仅支持 Oracle 12.1 及以上。
> 连接更旧版本时会报
> `DPY-3010: connections to this database server version are not supported by python-oracledb in thin mode`。
> 本镜像已内置 **Oracle Instant Client 21c**，在 Web 设置中勾选「使用 Oracle Thick 模式」
> 即可连接 11g 等旧版本数据库。

镜像包含：

- 后台定时检测线程（检测间隔可在 Web 中配置）
- Web 管理面板：监控看板、日志筛选、SMTP/阈值/间隔设置、多数据库管理
- 登录与用户管理：默认管理员 admin/admin123，支持管理员 / 只读角色
- 配置备份/恢复：数据库账号密码加密导出下载，上传备份即可恢复
- SQLite 持久化（`/data/monitor.db`）与按天日志（`/data/logs/`）
- Oracle Instant Client（Thick 模式，兼容旧版本数据库）

构建与启动（宿主机端口默认 **5432**，可在 `.env` 中改 `OM_WEB_PORT`）：

```bash
docker compose up -d --build

# 或手动（注意使用命名卷，不要用 Windows 绑定挂载）
docker build -t oracle-monitor .
docker run -d --name oracle-monitor -p 5432:8080 \
  -v oracle-monitor-data:/data oracle-monitor
```

访问 `http://<服务器IP>:5432`，使用默认账号 **admin / admin123** 登录：

1. **监控面板**：整体健康状态、服务运行时间、各库可用率环形图、响应时间曲线、24h/7d 告警趋势，可忽略指定告警
2. **数据库管理**：添加任意多个 Oracle 数据库（名称 / 主机 / 端口 / Service Name 或 SID / 账号）
3. **设置**：配置 SMTP、检测间隔、阈值、监控模块开关、Thick 模式
4. **日志**：按状态级别 / 数据库 / 关键字筛选，导出筛选结果
5. **备份**：导出加密备份文件，或上传备份恢复配置
6. **用户**（管理员）：新增用户、切换管理员 / 只读角色、重置密码、删除用户

> 登录状态由签名会话 Cookie 维持；口令以 `PBKDF2-HMAC-SHA256` 加盐存储，
> 登录时前端先用 `SHA-256` 预哈希，HTTP 下也不会明文传输原始密码。
> 首次启动可用环境变量 `OM_ADMIN_USER` / `OM_ADMIN_PASSWORD` 指定管理员账号，
> 登录后请在「修改密码」中尽快更改默认口令。

启用 Thick 模式：进入「设置 → 调度与连接」，勾选「使用 Oracle Thick 模式」，
「Instant Client 目录」填 `/opt/oracle/instantclient`，保存后**重启容器**生效：

```bash
docker compose restart
```

> 数据持久化在 Docker 命名卷 `oracle-monitor-data`（SQLite 数据库与日志），升级镜像不丢失。
> **不要使用 Windows 绑定挂载**（如 `-v ./data:/data`）：Windows→WSL2 的挂载会导致
> SQLite 报 `disk I/O error`，容器会启动即崩溃重启。查看日志请用 Web 的「日志」页面。
> 首次启动自动创建管理员 `admin / admin123`，可用 `OM_ADMIN_USER` / `OM_ADMIN_PASSWORD` 自定义。

Web 版目录结构：

```text
oracle-monitor/
├── webapp.py            # Flask 路由与 API
├── run_web.py           # Web 入口（waitress）
├── auth.py              # 登录认证与口令哈希
├── store.py             # SQLite 数据访问（多库/设置/历史/告警/用户）
├── cryptoutil.py        # 敏感字段 Fernet 加密
├── timesync.py          # NTP 软件校时
├── logview.py           # 日志解析与筛选
├── backup.py            # 配置加密备份/恢复
├── scheduler.py         # 后台检测调度
├── oracle_conn.py       # Thin / Thick 连接管理
├── settings.py          # 配置模型
├── checks.py            # 监控项 M1–M9
├── mailer.py            # 邮件发送
├── logger.py            # 日志（毫秒级、NTP 补偿）
├── templates/ static/   # Web 页面与静态资源
├── Dockerfile
├── docker-compose.yml
└── data/                # 持久化数据（自动生成）
```

### 13.4 配置备份与恢复

进入「备份」页面：

- **导出**：设置一个备份密码后点击「下载加密备份」，得到
  `oracle-monitor-backup-YYYYmmdd-HHMMSS.json.enc`。该文件包含全部数据库
  （含账号密码）、SMTP、阈值、检测间隔等设置，整个负载使用备份密码派生密钥加密。
- **恢复**：选择备份文件、输入相同密码并勾选确认，即可覆盖恢复全部配置。

加密说明：使用 `PBKDF2-HMAC-SHA256`（20 万次迭代，随机盐）派生密钥，
再用 `Fernet`（AES-128-CBC + HMAC-SHA256）加密负载，密码本身不落盘。
**忘记备份密码将无法恢复**，请妥善保管。

### 13.5 时间同步（NTP 校时）

进入「设置 → 时间同步（NTP）」：

- **启用 NTP 校时**：勾选后保存。
- **NTP 服务器**：可自定义，如 `pool.ntp.org`、`ntp.aliyun.com`、`time.windows.com`，
  也支持 `host:port` 形式。
- **校准间隔（小时）**：默认 **5 小时**，可修改。
- **时间地区（时区）**：默认 **`Asia/Shanghai`**，可选内置常用时区（香港、东京、新加坡、
  UTC、伦敦、纽约等）。日志、面板、邮件与导出文件的时间**统一按该时区显示**。

行为：

1. **启动时自动校准**一次（等待 NTP 响应，最长约 3 秒，失败则回退系统时间）。
2. 之后**每隔设定小时数自动校准**。
3. 可在设置页点击「立即校准」手动触发。
4. 校准结果（时间偏移、上次校准时间、错误信息）与当前时区显示在设置页与监控面板 Hero 区。

> 实现说明：容器默认没有修改主机时钟的权限。本功能采用**软件偏移**方案——
> 仅记录本地时钟与 NTP 的偏差，在生成日志和界面时间戳时补偿该偏差并按所选时区换算，
> 因此**不会修改宿主机系统时钟**，无需特权。日志时间精确到**毫秒**。
> 依赖 `tzdata`（已随镜像安装）提供时区数据。

### 13.6 监控系统迁移

把整套监控（含数据库、用户、密钥、历史与日志）迁移到新主机：

**方式一：迁移数据卷（推荐，完整保留全部数据）**

```bash
# 1) 旧主机：停止服务
docker compose down

# 2) 旧主机：打包命名卷
docker run --rm -v oracle_monitor_oracle-monitor-data:/data \
  -v "$(pwd)":/backup alpine \
  tar czf /backup/oracle-monitor-data.tar.gz -C /data .

# 3) 将以下文件拷贝到新主机同一目录
#    oracle-monitor-data.tar.gz、docker-compose.yml、.env（若有）、项目源码或已构建镜像

# 4) 新主机：创建卷并解包
docker volume create oracle_monitor_oracle-monitor-data
docker run --rm -v oracle_monitor_oracle-monitor-data:/data \
  -v "$(pwd)":/backup alpine \
  sh -c "cd /data && tar xzf /backup/oracle-monitor-data.tar.gz"

# 5) 新主机：启动（无需 --build 可复用已有镜像）
docker compose up -d --build
```

迁移后检查：

- 访问 `http://<新主机IP>:5432`，用原账号登录。
- 进入「数据库管理」逐个「测试」连接。
- 确认 `data.key` 已随卷迁移（否则加密的口令无法解密）；若丢失，需重新录入账号密码。

**方式二：仅迁移配置（数据库与设置）**

1. 旧主机「备份」页导出 `oracle-monitor-backup-*.json.enc`。
2. 新主机全新启动后，在同一页面用**相同密码**上传恢复。
3. 用户账号、历史记录与日志不在此备份内，需另行迁移数据卷或重新创建用户。

> 换了宿主机端口或域名后，`.env` 中的 `OM_WEB_PORT` 与反向代理需同步调整；
> 数据卷名固定为 `oracle_monitor_oracle-monitor-data`（由 compose 项目名 + 卷名组成）。

---

## 14. 敏感数据与安全

### 14.1 敏感数据存储位置

所有运行数据集中在**数据目录**下。Docker 版默认使用命名卷 `oracle-monitor-data`，
挂载到容器内 `/data`；本地 / EXE 版为项目下的 `data/`、`logs/` 与 `config.ini`。

| 敏感数据 | Docker 版位置 | 本地 / EXE 版位置 | 保护方式 |
|----------|---------------|-------------------|----------|
| 数据库监控账号 / 密码 | SQLite `databases` 表 `username` / `password` 字段 | `data/monitor.db` | ✅ **Fernet(AES) 加密**，非明文 |
| SMTP 发件授权码 | SQLite `settings` 表 `smtp_password` | `data/monitor.db` | ✅ **Fernet(AES) 加密**，非明文 |
| Web 登录口令 | SQLite `users` 表 `password_hash` / `salt` | `data/monitor.db` | ✅ PBKDF2-HMAC-SHA256 加盐哈希 |
| 数据加密密钥 | `/data/data.key` | `data/data.key` | Fernet 密钥，权限 600；丢弃将无法解密口令 |
| 会话签名密钥 | `/data/secret.key` | `data/secret.key` | 32 字节随机数，文件权限保护 |
| 备份文件 | 用户下载的 `*.json.enc` | 用户本地 | ✅ PBKDF2 + Fernet(AES) 加密 |
| 运行日志 | `/data/logs/monitor_YYYYMMDD.log` | `logs/` | ⚠️ 明文（不含口令，含主机/实例名/报错） |
| CLI / EXE 配置 | —（不使用） | `config.ini` | ⚠️ **明文**（CLI 模式，见下方说明） |
| 告警状态 | SQLite `alerts` 表 / `state.json` | 同左 | 不含口令 |

> 结论：**数据库账号/密码与 SMTP 授权码在 SQLite 中以 Fernet（AES-128-CBC + HMAC）
> 密文形式存储，不再明文落盘**；Web 登录口令为 PBKDF2 加盐哈希。
> 密文对应的密钥保存在同目录的 `data.key`（或环境变量 `OM_DATA_KEY`），
> 因此**保护 `monitor.db` 的同时也要保护 `data.key`**。

**加密实现**：`cryptoutil.py` 对敏感字段做透明加解密，`store.py` 在写入前加密、
读取后解密，业务代码（连接、备份、界面）拿到的始终是明文，无需改动。
启动时会自动把历史遗留的明文记录就地加密。

**密钥管理**（`data.key` 或 `OM_DATA_KEY`）：

- 默认首次启动生成 `data/data.key`（权限 600）。**丢失该文件将无法解密已有口令**，
  数据库连接会失败，需要重新录入账号密码。
- 生产环境推荐用环境变量提供密钥，使密钥不随数据库落盘：

  ```bash
  # 生成一个 Fernet 密钥
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  # 在 docker-compose.yml 中设置 OM_DATA_KEY，或使用 Docker secret
  ```

> 说明：这是"静态加密"，密钥与数据在同一主机，可防止直接查看数据库文件时泄露明文，
> 但无法抵御主机被完全攻破。更强隔离请使用 KMS / Vault 等外部密钥管理。
> CLI / EXE 模式仍读取 `config.ini`，该文件为明文，请用 `chmod 600` 保护并勿提交 Git；
> 如需同样加密，建议改用 Web / Docker 版。

Docker 命名卷的实际宿主机路径（Windows Docker Desktop 下由虚拟机管理）：

```bash
docker volume inspect oracle_monitor_oracle-monitor-data
docker exec oracle-monitor ls -l /data
# /data/monitor.db   /data/data.key   /data/secret.key   /data/logs/
```

备份整个数据卷（含数据库、密钥、日志）：

```bash
docker run --rm -v oracle_monitor_oracle-monitor-data:/data \
  -v "$(pwd)":/backup alpine \
  tar czf /backup/oracle-monitor-data.tar.gz -C /data .
```

> 也可用 Web 的「备份」页面导出加密配置（内含解密后的账号密码，再用备份密码加密），
> 恢复时会用新实例的密钥重新加密，因此备份文件可跨实例迁移。

### 14.2 安全加固建议

1. **修改默认口令**：首次登录后立即修改 `admin/admin123`，并删除多余测试账号。
2. **使用只读账号**：监控账号只授予 `SELECT` 权限，杜绝误操作。
3. **保护数据与密钥**：`chmod 600 data/monitor.db data/data.key data/secret.key config.ini`，禁止提交到 Git。
4. **收紧数据卷访问**：仅授权管理员访问宿主机 Docker，避免他人 `docker exec` 读取数据库。
5. **网络隔离**：监控服务放在管理网段，避免直接暴露公网；如需公网访问，前置 HTTPS 反向代理。
6. **使用授权码**：邮件密码使用授权码而非登录密码，泄露风险更低。
7. **日志脱敏**：不要将口令写入日志；程序默认不记录口令。
8. **定期轮换**：每 90 天更换数据库口令、邮箱授权码与 Web 登录密码。
9. **备份加密**：导出的备份已用口令加密，妥善保管备份密码。
10. **最小化开启**：只启用需要的监控模块，减少数据库压力。

`.gitignore` 示例：

```
venv/
.venv/
__pycache__/
*.pyc
config.ini
.env
opencode.json
logs/
data/
*.log
state.json
dist/
build/
.idea/
```

---

## 15. 许可证

本项目采用 **木兰公共许可证，第2版（Mulan Public License, Version 2，Mulan PubL v2）** 开源。

- 许可证全文：[LICENSE](LICENSE)
- 官方地址：<https://license.coscl.org.cn/MulanPubL-2.0>

> Mulan PubL v2 是一种**弱 copyleft（传染性）**许可证：您可以自由使用、修改、分发，
> 但分发本软件或其"衍生作品"时，须以相同许可证提供**对应源代码**，并保留版权与免责声明。
> 详见 `LICENSE` 全文（中英文双语，具同等法律效力，以中文版为准）。

在源文件头部建议添加如下声明：

```text
Copyright (c) 2025 miralexand
Oracle Monitor is licensed under Mulan PubL v2.
You can use this software according to the terms and conditions of the Mulan PubL v2.
You may obtain a copy of Mulan PubL v2 at:
    http://license.coscl.org.cn/MulanPubL-2.0
THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
See the Mulan PubL v2 for more details.
```

---

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=miralexand/oracle-monitor&type=Date)](https://star-history.com/#miralexand/oracle-monitor&Date)

---

## 附录 A：命令行参数

| 参数 | 说明 |
|------|------|
| （无） | 常驻模式，按 `interval_minutes` 循环 |
| `--once` | 单次执行后退出（推荐配合 cron / 任务计划程序） |
| `--config <path>` | 指定配置文件路径，默认 `config.ini` |
| `--check <M1,M3>` | 只运行指定监控项 |
| `--test-mail` | 发送一封测试邮件后退出 |
| `--dry-run` | 检测但不发邮件，仅打印到控制台 |
| `--version` | 显示版本 |
| `--help` | 显示帮助 |

## 附录 B：示例邮件

```
主题: [Oracle监控] ORCL 检测到 2 项异常

收件人: dba@example.com, ops@example.com

正文:
【监控时间】2025-01-01 10:00:00
【数据库实例】ORCL (192.168.1.100:1521)
【异常数量】2

-------------------------------
1. 表空间 USERS 使用率 88.3%，超过阈值 85%
2. 活跃会话数 612，超过阈值 500

请及时登录数据库排查。
-------------------------------
本邮件由 Oracle 监控程序自动发送，请勿回复。
```

## 附录 C：版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0.0 | 2025-01-01 | 首个版本：CLI 监控 M1–M6、SMTP 告警、按天日志 |
| v1.1.0 | 2025-02-01 | 新增 M7–M9 监控项、恢复通知、静默期 |
| v1.2.0 | 2025-03-01 | Web 管理面板 / Docker、多数据库、登录与用户管理、图表看板、日志筛选、加密备份/恢复、告警忽略、NTP 校时与时间地区、敏感数据加密 |

---

**项目地址**：https://github.com/miralexand/oracle-monitor
**问题反馈**：https://github.com/miralexand/oracle-monitor/issues