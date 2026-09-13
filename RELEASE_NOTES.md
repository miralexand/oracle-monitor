# Oracle 数据库监控 v1.2.0

首个公开发布版本，提供 **CLI / EXE 单机监控** 与 **Docker + Web 集中管理** 两种形态。

## 主要功能

- **多指标监控**：连通性（M1）、实例状态（M2）、表空间使用率（M3）、活跃会话数（M4）、
  长事务（M5）、阻塞锁等待（M6）、归档目录空间（M7）、RMAN 备份状态（M8）、告警日志 ORA- 错误（M9）
- **多数据库**：Web / Docker 版支持添加任意多个 Oracle 实例统一监控
- **Web 管理面板**：整体健康状态、可用率环形图、响应时间曲线、24 小时 / 7 天告警趋势、明亮与暗黑主题
- **登录与用户管理**：默认 `admin / admin123`，管理员 / 只读两种角色，口令 PBKDF2 加盐哈希、前端 SHA-256 预哈希
- **日志细分**：按状态级别、数据库、关键字筛选查看，并导出筛选结果
- **告警忽略**：可忽略单条或全部活动告警，不再发送通知，恢复后自动重置
- **敏感数据加密**：数据库账号密码、SMTP 授权码以 Fernet(AES) 密文存储，非明文落盘
- **配置备份 / 恢复**：加密导出下载，上传备份即可恢复
- **NTP 校时与时间地区**：默认 `Asia/Shanghai`，启动时与每 5 小时自动校时，日志精确到毫秒
- **旧版本兼容**：Docker 镜像内置 Oracle Instant Client，Thick 模式支持 11g 等旧版本数据库

## 运行方式

- **Docker（推荐）**：`docker compose up -d --build`，浏览器访问 `http://<服务器IP>:5432`
- **CLI / EXE**：运行 `monitor.py`，或下载下方 `oracle_monitor.exe`

## 下载文件

- `oracle_monitor.exe`：Windows 单文件可执行程序
- `oracle_monitor.exe.sha256`：SHA256 校验值

## 许可证

木兰公共许可证，第2版（Mulan Public License, Version 2，Mulan PubL v2）。
