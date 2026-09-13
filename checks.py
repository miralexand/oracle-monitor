# -*- coding: utf-8 -*-
"""各监控项检测逻辑。

每个检查函数返回一个列表，元素为 (key, message) 二元组：
    key     告警唯一标识（稳定，用于静默与恢复判断）
    message 人类可读的告警描述
无异常时返回空列表。
"""

import glob
import logging
import os

log = logging.getLogger(__name__)

DEFAULT_ALERT_LOG_PATTERNS = [
    "ORA-00600",
    "ORA-07445",
    "ORA-04031",
    "ORA-01555",
    "ORA-00257",
    "ORA-16038",
]


def check_instance_status(conn):
    """M2 实例状态：非 OPEN 即告警。"""
    alerts = []
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT instance_name, status FROM v$instance")
        row = cursor.fetchone()
        if row:
            name, status = row[0], (row[1] or "").upper()
            if status != "OPEN":
                alerts.append(
                    ("instance_status", "实例 {} 状态为 {}，非 OPEN".format(name, status))
                )
    finally:
        cursor.close()
    return alerts


def check_tablespace(conn, threshold):
    """M3 表空间使用率。"""
    alerts = []
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT tablespace_name, used_percent "
            "FROM dba_tablespace_usage_metrics ORDER BY used_percent DESC"
        )
        for name, used_percent in cursor.fetchall():
            pct = float(used_percent)
            if pct > threshold:
                alerts.append(
                    (
                        "tablespace:{}".format(name),
                        "表空间 {} 使用率 {:.1f}%，超过阈值 {}%".format(name, pct, threshold),
                    )
                )
    finally:
        cursor.close()
    return alerts


def check_session_count(conn, threshold):
    """M4 活跃会话数。"""
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM v$session WHERE type = 'USER'")
        count = int(cursor.fetchone()[0])
    finally:
        cursor.close()
    if count > threshold:
        return [("session_count", "活跃会话数 {}，超过阈值 {}".format(count, threshold))]
    return []


def check_long_query(conn, threshold):
    """M5 长时间运行的 SQL。"""
    alerts = []
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT s.sid, NVL(s.username, '-'), s.last_call_et, s.sql_id
            FROM v$session s
            WHERE s.status = 'ACTIVE' AND s.type = 'USER' AND s.last_call_et > :seconds
            ORDER BY s.last_call_et DESC
            """,
            seconds=threshold,
        )
        for sid, username, elapsed, sql_id in cursor.fetchall():
            alerts.append(
                (
                    "long_query:{}:{}".format(sid, sql_id),
                    "长事务 SID {}({}) 已运行 {} 秒，超过阈值 {} 秒 (SQL_ID={})".format(
                        sid, username, int(elapsed), threshold, sql_id
                    ),
                )
            )
    finally:
        cursor.close()
    return alerts


def check_lock_wait(conn, threshold):
    """M6 阻塞锁等待。"""
    alerts = []
    seen = set()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT w.sid, w.seconds_in_wait, b.sid AS blocking_sid, w.event
            FROM v$lock l1
            JOIN v$session b ON l1.sid = b.sid AND l1.block = 1
            JOIN v$lock l2 ON l1.id1 = l2.id1 AND l1.id2 = l2.id2 AND l2.request > 0
            JOIN v$session w ON w.sid = l2.sid
            WHERE w.seconds_in_wait > :seconds
            """,
            seconds=threshold,
        )
        for sid, seconds_in_wait, blocking_sid, event in cursor.fetchall():
            key = "lock_wait:{}".format(sid)
            if key in seen:
                continue
            seen.add(key)
            alerts.append(
                (
                    key,
                    "会话 SID {} 被 SID {} 阻塞，等待 {} 秒，超过阈值 {} 秒 (event={})".format(
                        sid, blocking_sid, int(seconds_in_wait), threshold, event
                    ),
                )
            )
    finally:
        cursor.close()
    return alerts


def check_archive_space(conn, threshold):
    """M7 归档目录空间使用率。"""
    alerts = []
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT name, space_limit, space_used FROM v$recovery_file_dest")
        for name, space_limit, space_used in cursor.fetchall():
            limit = float(space_limit or 0)
            used = float(space_used or 0)
            if limit <= 0:
                continue
            pct = used / limit * 100.0
            if pct > threshold:
                alerts.append(
                    (
                        "archive_space",
                        "归档目录 {} 使用率 {:.1f}%，超过阈值 {}%".format(name, pct, threshold),
                    )
                )
    finally:
        cursor.close()
    return alerts


def check_rman_backup(conn, hours):
    """M8 RMAN 备份状态：区间内存在失败任务或没有备份时告警。"""
    alerts = []
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT session_key, input_type, status,
                   TO_CHAR(start_time, 'YYYY-MM-DD HH24:MI:SS'),
                   TO_CHAR(end_time, 'YYYY-MM-DD HH24:MI:SS')
            FROM v$rman_backup_job_details
            WHERE start_time > SYSDATE - :hours
            ORDER BY start_time DESC
            """,
            hours=hours,
        )
        rows = cursor.fetchall()
    finally:
        cursor.close()

    if not rows:
        return [
            ("rman_missing", "最近 {} 小时内未发现 RMAN 备份记录".format(hours))
        ]

    for session_key, input_type, status, start_time, end_time in rows:
        status_upper = (status or "").upper()
        if status_upper not in ("COMPLETED", "RUNNING"):
            alerts.append(
                (
                    "rman_failed:{}".format(session_key),
                    "RMAN 备份任务 {} ({}) 状态为 {}，开始时间 {}，结束时间 {}".format(
                        session_key, input_type, status, start_time, end_time
                    ),
                )
            )
    return alerts


def _tail(path, lines=1000, block_size=8192):
    """高效读取文件末尾若干行。"""
    with open(path, "rb") as handle:
        handle.seek(0, os.SEEK_END)
        size = handle.tell()
        data = b""
        while size > 0 and data.count(b"\n") <= lines:
            read_size = min(block_size, size)
            size -= read_size
            handle.seek(size)
            data = handle.read(read_size) + data
    text = data.decode("utf-8", errors="replace")
    return text.splitlines()[-lines:]


def check_alert_log(conn, patterns=None, max_lines=1000):
    """M9 告警日志中的严重 ORA- 错误。仅当监控主机能访问数据库诊断目录时有效。"""
    patterns = patterns or DEFAULT_ALERT_LOG_PATTERNS
    alerts = []
    try:
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT value FROM v$diag_info WHERE name = 'Diag Trace'")
            row = cursor.fetchone()
        finally:
            cursor.close()
        if not row or not row[0]:
            return []
        trace_dir = row[0]
        candidates = glob.glob(os.path.join(trace_dir, "alert_*.log"))
        if not candidates:
            return []
        path = max(candidates, key=os.path.getmtime)
        for line in _tail(path, max_lines):
            for pattern in patterns:
                if pattern in line:
                    alerts.append(
                        (
                            "alert_log:{}".format(pattern),
                            "告警日志发现 {}: {}".format(pattern, line.strip()[:200]),
                        )
                    )
                    break
    except Exception as exc:  # 文件不可读、视图不存在等
        log.warning("读取告警日志失败，跳过 M9: %s", exc)
    return alerts


def _run(name, func, *args, **kwargs):
    try:
        return func(*args, **kwargs) or []
    except Exception as exc:
        log.error("%s 检查执行失败: %s", name, exc)
        return []


def _enabled(config, flag, default=True):
    try:
        return config.getboolean("modules", flag)
    except Exception:
        return default


def _threshold(config, key, default):
    try:
        return config.getint("thresholds", key)
    except Exception:
        return default


def _selected(selected, code):
    return not selected or code.upper() in selected


def run_checks(conn, config, selected=None):
    """按配置执行所有已启用的监控项，返回告警列表 [(key, message), ...]。"""
    if selected:
        selected = {item.strip().upper() for item in selected}

    alerts = []

    if _selected(selected, "M2") and _enabled(config, "enable_m2_instance_status"):
        alerts += _run("M2", check_instance_status, conn)

    if _selected(selected, "M3") and _enabled(config, "enable_m3_tablespace"):
        alerts += _run(
            "M3", check_tablespace, conn, _threshold(config, "tablespace_usage_pct", 85)
        )

    if _selected(selected, "M4") and _enabled(config, "enable_m4_session_count"):
        alerts += _run(
            "M4", check_session_count, conn, _threshold(config, "session_count", 500)
        )

    if _selected(selected, "M5") and _enabled(config, "enable_m5_long_query"):
        alerts += _run(
            "M5",
            check_long_query,
            conn,
            _threshold(config, "long_query_seconds", 3600),
        )

    if _selected(selected, "M6") and _enabled(config, "enable_m6_lock_wait"):
        alerts += _run(
            "M6", check_lock_wait, conn, _threshold(config, "lock_wait_seconds", 300)
        )

    if _selected(selected, "M7") and _enabled(config, "enable_m7_archive_space", False):
        alerts += _run(
            "M7", check_archive_space, conn, _threshold(config, "archive_usage_pct", 85)
        )

    if _selected(selected, "M8") and _enabled(config, "enable_m8_rman_backup", False):
        alerts += _run(
            "M8",
            check_rman_backup,
            conn,
            _threshold(config, "rman_backup_interval_hours", 24),
        )

    if _selected(selected, "M9") and _enabled(config, "enable_m9_alert_log", False):
        raw = config.get(
            "thresholds",
            "alert_log_patterns",
            fallback=",".join(DEFAULT_ALERT_LOG_PATTERNS),
        )
        patterns = [item.strip() for item in raw.split(",") if item.strip()]
        alerts += _run("M9", check_alert_log, conn, patterns)

    return alerts
