# -*- coding: utf-8 -*-
"""SQLite 数据访问层：多数据库配置、全局设置、检测历史与告警状态。"""

import os
import sqlite3
import threading
import time
from datetime import datetime, timedelta

from cryptoutil import Cipher, is_encrypted
from settings import DEFAULT_SETTINGS
from timesync import time_sync

SCHEMA = """
CREATE TABLE IF NOT EXISTS databases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    host TEXT NOT NULL,
    port INTEGER NOT NULL DEFAULT 1521,
    service_name TEXT,
    sid TEXT,
    username TEXT NOT NULL,
    password TEXT,
    connect_timeout INTEGER NOT NULL DEFAULT 10,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS check_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    db_id INTEGER NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    alert_count INTEGER NOT NULL DEFAULT 0,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    message TEXT
);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    db_id INTEGER NOT NULL,
    alert_key TEXT NOT NULL,
    message TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    last_sent_at REAL DEFAULT 0,
    ignored INTEGER NOT NULL DEFAULT 0,
    resolved_at TEXT,
    UNIQUE (db_id, alert_key)
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    iterations INTEGER NOT NULL DEFAULT 200000,
    role TEXT NOT NULL DEFAULT 'admin',
    created_at TEXT NOT NULL,
    last_login TEXT
);

CREATE INDEX IF NOT EXISTS idx_runs_db_time ON check_runs (db_id, started_at);
CREATE INDEX IF NOT EXISTS idx_alerts_db ON alerts (db_id, status);
"""


def _now_iso():
    return time_sync.now_iso()


class Store(object):
    def __init__(self, path):
        self.path = path
        directory = os.path.dirname(os.path.abspath(path))
        if directory:
            os.makedirs(directory, exist_ok=True)
        self._lock = threading.RLock()
        self._cipher = Cipher(directory or ".")
        self._conn = sqlite3.connect(path, check_same_thread=False, timeout=30)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA busy_timeout=5000")
        try:
            self._conn.execute("PRAGMA journal_mode=WAL")
        except sqlite3.DatabaseError:
            self._conn.execute("PRAGMA journal_mode=DELETE")
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._migrate()
            self._seed_settings()
            self._seed_admin()
            self._encrypt_existing_sensitive()
            self._conn.commit()

    def _seed_admin(self):
        """首次运行时创建默认管理员 admin/admin123。"""
        row = self._conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()
        if row["c"]:
            return
        from auth import hash_password, sha256_hex

        username = os.environ.get("OM_ADMIN_USER", "admin") or "admin"
        password = os.environ.get("OM_ADMIN_PASSWORD", "admin123") or "admin123"
        password_hash, salt, iterations = hash_password(sha256_hex(password))
        self._conn.execute(
            "INSERT INTO users (username, password_hash, salt, iterations, role, created_at) "
            "VALUES (?, ?, ?, ?, 'admin', ?)",
            (username, password_hash, salt, iterations, _now_iso()),
        )

    def _migrate(self):
        """兼容旧版本数据库文件，补齐新增列。"""
        columns = {row["name"] for row in self._conn.execute("PRAGMA table_info(alerts)")}
        if "last_sent_at" not in columns:
            self._conn.execute("ALTER TABLE alerts ADD COLUMN last_sent_at REAL DEFAULT 0")
        if "ignored" not in columns:
            self._conn.execute("ALTER TABLE alerts ADD COLUMN ignored INTEGER NOT NULL DEFAULT 0")

    def _encrypt_existing_sensitive(self):
        """将历史遗留的明文敏感字段就地加密。"""
        rows = self._conn.execute("SELECT id, username, password FROM databases").fetchall()
        for row in rows:
            updates = {}
            if row["username"] and not is_encrypted(row["username"]):
                updates["username"] = self._cipher.encrypt(row["username"])
            if row["password"] and not is_encrypted(row["password"]):
                updates["password"] = self._cipher.encrypt(row["password"])
            if updates:
                clauses = ", ".join("{} = ?".format(col) for col in updates)
                self._conn.execute(
                    "UPDATE databases SET {} WHERE id = ?".format(clauses),
                    tuple(updates.values()) + (row["id"],),
                )
        row = self._conn.execute(
            "SELECT value FROM settings WHERE key = 'smtp_password'"
        ).fetchone()
        if row and row["value"] and not is_encrypted(row["value"]):
            self._conn.execute(
                "UPDATE settings SET value = ? WHERE key = 'smtp_password'",
                (self._cipher.encrypt(row["value"]),),
            )

    # ---------------------------------------------------------------- settings
    def _seed_settings(self):
        for key, value in DEFAULT_SETTINGS.items():
            env_value = os.environ.get(key.upper())
            if env_value not in (None, ""):
                value = env_value
            if key == "smtp_password" and value:
                value = self._cipher.encrypt(value)
            self._conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value)
            )

    def get_settings(self):
        with self._lock:
            rows = self._conn.execute("SELECT key, value FROM settings").fetchall()
        data = dict(DEFAULT_SETTINGS)
        data.update({row["key"]: row["value"] for row in rows})
        if data.get("smtp_password"):
            data["smtp_password"] = self._cipher.decrypt(data["smtp_password"])
        return data

    def get_setting(self, key, default=None):
        with self._lock:
            row = self._conn.execute(
                "SELECT value FROM settings WHERE key = ?", (key,)
            ).fetchone()
        if row is None:
            value = DEFAULT_SETTINGS.get(key, default)
        else:
            value = row["value"]
        if key == "smtp_password":
            value = self._cipher.decrypt(value)
        return value

    def update_settings(self, values):
        with self._lock:
            for key, value in values.items():
                if value is None:
                    continue
                if key == "smtp_password" and value:
                    value = self._cipher.encrypt(value)
                self._conn.execute(
                    "INSERT INTO settings (key, value) VALUES (?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    (key, str(value)),
                )
            self._conn.commit()

    # -------------------------------------------------------------- databases
    def _decode_database(self, row):
        data = dict(row)
        data["username"] = self._cipher.decrypt(data.get("username"))
        data["password"] = self._cipher.decrypt(data.get("password"))
        return data

    def list_databases(self, enabled_only=False):
        query = "SELECT * FROM databases"
        if enabled_only:
            query += " WHERE enabled = 1"
        query += " ORDER BY id"
        with self._lock:
            rows = self._conn.execute(query).fetchall()
        return [self._decode_database(row) for row in rows]

    def get_database(self, db_id):
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM databases WHERE id = ?", (db_id,)
            ).fetchone()
        return self._decode_database(row) if row else None

    def add_database(self, data):
        with self._lock:
            cursor = self._conn.execute(
                "INSERT INTO databases "
                "(name, host, port, service_name, sid, username, password, "
                " connect_timeout, enabled, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    data["name"],
                    data["host"],
                    data.get("port") or 1521,
                    data.get("service_name") or "",
                    data.get("sid") or "",
                    self._cipher.encrypt(data["username"]),
                    self._cipher.encrypt(data.get("password") or ""),
                    data.get("connect_timeout") or 10,
                    1 if data.get("enabled", True) else 0,
                    _now_iso(),
                ),
            )
            self._conn.commit()
            return cursor.lastrowid

    def update_database(self, db_id, data):
        with self._lock:
            self._conn.execute(
                "UPDATE databases SET name = ?, host = ?, port = ?, service_name = ?, "
                "sid = ?, username = ?, password = ?, connect_timeout = ?, enabled = ? "
                "WHERE id = ?",
                (
                    data["name"],
                    data["host"],
                    data.get("port") or 1521,
                    data.get("service_name") or "",
                    data.get("sid") or "",
                    self._cipher.encrypt(data["username"]),
                    self._cipher.encrypt(data.get("password") or ""),
                    data.get("connect_timeout") or 10,
                    1 if data.get("enabled", True) else 0,
                    db_id,
                ),
            )
            self._conn.commit()

    def set_enabled(self, db_id, enabled):
        with self._lock:
            self._conn.execute(
                "UPDATE databases SET enabled = ? WHERE id = ?", (1 if enabled else 0, db_id)
            )
            self._conn.commit()

    def delete_database(self, db_id):
        with self._lock:
            self._conn.execute("DELETE FROM check_runs WHERE db_id = ?", (db_id,))
            self._conn.execute("DELETE FROM alerts WHERE db_id = ?", (db_id,))
            self._conn.execute("DELETE FROM databases WHERE id = ?", (db_id,))
            self._conn.commit()

    # --------------------------------------------------------------- backup
    def export_config(self):
        """导出数据库列表与全部设置（含密码，由上层负责加密）。"""
        return {
            "databases": self.list_databases(),
            "settings": self.get_settings(),
        }

    def import_config(self, data):
        """用备份数据整体覆盖当前数据库与设置，返回恢复的数据库数量。"""
        databases = data.get("databases") or []
        settings = data.get("settings") or {}
        if not isinstance(databases, list):
            raise ValueError("databases 字段格式错误")

        with self._lock:
            self._conn.execute("DELETE FROM databases")
            self._conn.execute("DELETE FROM check_runs")
            self._conn.execute("DELETE FROM alerts")
            for db in databases:
                self._conn.execute(
                    "INSERT INTO databases "
                    "(name, host, port, service_name, sid, username, password, "
                    " connect_timeout, enabled, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        (db.get("name") or "unnamed").strip(),
                        (db.get("host") or "").strip(),
                        db.get("port") or 1521,
                        db.get("service_name") or "",
                        db.get("sid") or "",
                        self._cipher.encrypt((db.get("username") or "").strip()),
                        self._cipher.encrypt(db.get("password") or ""),
                        db.get("connect_timeout") or 10,
                        1 if db.get("enabled", True) else 0,
                        _now_iso(),
                    ),
                )
            for key, value in settings.items():
                if key in DEFAULT_SETTINGS and value is not None:
                    if key == "smtp_password" and value:
                        value = self._cipher.encrypt(value)
                    self._conn.execute(
                        "INSERT INTO settings (key, value) VALUES (?, ?) "
                        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                        (key, str(value)),
                    )
            self._conn.commit()
        return len(databases)

    # ------------------------------------------------------------------ runs
    def record_run(self, db_id, started_at, finished_at, status, alert_count, duration_ms, message):
        with self._lock:
            self._conn.execute(
                "INSERT INTO check_runs "
                "(db_id, started_at, finished_at, status, alert_count, duration_ms, message) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (db_id, started_at, finished_at, status, alert_count, duration_ms, message),
            )
            self._conn.commit()

    def recent_runs(self, db_id, limit=30):
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM check_runs WHERE db_id = ? ORDER BY id DESC LIMIT ?",
                (db_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    # ---------------------------------------------------------------- alerts
    def apply_alert_cycle(self, db_id, alerts, silence_seconds):
        """同步本轮告警，返回 (需要发送的告警消息, 已恢复的消息)。"""
        now = time.time()
        now_iso = _now_iso()
        current = dict(alerts)
        to_send = []
        recovered = []
        with self._lock:
            active_rows = {
                row["alert_key"]: row
                for row in self._conn.execute(
                    "SELECT * FROM alerts WHERE db_id = ? AND status = 'active'", (db_id,)
                ).fetchall()
            }
            for key, message in current.items():
                row = active_rows.get(key)
                if row is None:
                    existing = self._conn.execute(
                        "SELECT * FROM alerts WHERE db_id = ? AND alert_key = ?", (db_id, key)
                    ).fetchone()
                    if existing:
                        self._conn.execute(
                            "UPDATE alerts SET status='active', message=?, first_seen=?, "
                            "last_seen=?, last_sent_at=?, ignored=0, resolved_at=NULL WHERE id=?",
                            (message, now_iso, now_iso, now, existing["id"]),
                        )
                    else:
                        self._conn.execute(
                            "INSERT INTO alerts (db_id, alert_key, message, status, "
                            "first_seen, last_seen, last_sent_at) VALUES (?, ?, ?, 'active', ?, ?, ?)",
                            (db_id, key, message, now_iso, now_iso, now),
                        )
                    to_send.append(message)
                else:
                    self._conn.execute(
                        "UPDATE alerts SET message = ?, last_seen = ? WHERE id = ?",
                        (message, now_iso, row["id"]),
                    )
                    last_sent = row["last_sent_at"] or 0
                    if not row["ignored"] and now - float(last_sent) >= silence_seconds:
                        to_send.append(message)
                        self._conn.execute(
                            "UPDATE alerts SET last_sent_at = ? WHERE id = ?", (now, row["id"])
                        )
            for key, row in active_rows.items():
                if key not in current:
                    self._conn.execute(
                        "UPDATE alerts SET status='resolved', resolved_at=? WHERE id=?",
                        (now_iso, row["id"]),
                    )
                    recovered.append(row["message"])
            self._conn.commit()
        return to_send, recovered

    def active_alerts(self, db_id):
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM alerts WHERE db_id = ? AND status = 'active' ORDER BY first_seen DESC",
                (db_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def set_alert_ignored(self, db_id, alert_key, ignored):
        with self._lock:
            if alert_key:
                cursor = self._conn.execute(
                    "UPDATE alerts SET ignored = ? WHERE db_id = ? AND alert_key = ? AND status='active'",
                    (1 if ignored else 0, db_id, alert_key),
                )
            else:
                cursor = self._conn.execute(
                    "UPDATE alerts SET ignored = ? WHERE db_id = ? AND status='active'",
                    (1 if ignored else 0, db_id),
                )
            self._conn.commit()
            return cursor.rowcount

    def alert_count_since(self, db_id, since_iso):
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS c FROM alerts WHERE db_id = ? AND first_seen >= ?",
                (db_id, since_iso),
            ).fetchone()
        return int(row["c"])

    # ------------------------------------------------------------- dashboard
    def _hourly_history(self, db_id, hours=24):
        now = time_sync.now().replace(minute=0, second=0, microsecond=0)
        start = now - timedelta(hours=hours - 1)
        with self._lock:
            rows = self._conn.execute(
                "SELECT started_at, status, duration_ms FROM check_runs "
                "WHERE db_id = ? AND started_at >= ?",
                (db_id, start.isoformat(timespec="seconds")),
            ).fetchall()
        buckets = {}
        for i in range(hours):
            slot = start + timedelta(hours=i)
            buckets[slot.strftime("%Y-%m-%d %H")] = {
                "total": 0, "ok": 0, "alert": 0, "error": 0, "ms_sum": 0, "ms_n": 0,
            }
        for row in rows:
            try:
                dt = datetime.fromisoformat(row["started_at"])
            except (ValueError, TypeError):
                continue
            bucket = buckets.get(dt.strftime("%Y-%m-%d %H"))
            if bucket is None:
                continue
            bucket["total"] += 1
            if row["status"] in ("ok", "alert", "error"):
                bucket[row["status"]] += 1
            if row["duration_ms"]:
                bucket["ms_sum"] += row["duration_ms"]
                bucket["ms_n"] += 1
        result = []
        for i in range(hours):
            slot = start + timedelta(hours=i)
            bucket = buckets[slot.strftime("%Y-%m-%d %H")]
            result.append(
                {
                    "hour": slot.strftime("%H:00"),
                    "avg_ms": round(bucket["ms_sum"] / bucket["ms_n"]) if bucket["ms_n"] else None,
                    "ok": bucket["ok"],
                    "alert": bucket["alert"],
                    "error": bucket["error"],
                    "total": bucket["total"],
                }
            )
        return result

    def _alert_trend(self, db_id, days=7):
        today = time_sync.now().date()
        start = today - timedelta(days=days - 1)
        with self._lock:
            rows = self._conn.execute(
                "SELECT substr(first_seen, 1, 10) AS day, COUNT(*) AS c "
                "FROM alerts WHERE db_id = ? AND first_seen >= ? GROUP BY day",
                (db_id, start.isoformat()),
            ).fetchall()
        counts = {row["day"]: row["c"] for row in rows}
        result = []
        for i in range(days):
            day = start + timedelta(days=i)
            result.append(
                {"date": day.strftime("%m-%d"), "count": counts.get(day.isoformat(), 0)}
            )
        return result

    def dashboard(self):
        since = (time_sync.now() - timedelta(hours=24)).isoformat(timespec="seconds")
        result = []
        for db in self.list_databases():
            with self._lock:
                latest = self._conn.execute(
                    "SELECT * FROM check_runs WHERE db_id = ? ORDER BY id DESC LIMIT 1",
                    (db["id"],),
                ).fetchone()
                stats = self._conn.execute(
                    "SELECT "
                    "COUNT(*) AS total, "
                    "SUM(CASE WHEN status='ok' THEN 1 ELSE 0 END) AS ok_count, "
                    "SUM(CASE WHEN status='alert' THEN 1 ELSE 0 END) AS alert_count, "
                    "SUM(CASE WHEN status='error' THEN 1 ELSE 0 END) AS error_count, "
                    "AVG(duration_ms) AS avg_ms "
                    "FROM check_runs WHERE db_id = ? AND started_at >= ?",
                    (db["id"], since),
                ).fetchone()
                active_rows = self._conn.execute(
                    "SELECT alert_key, message, first_seen, ignored FROM alerts "
                    "WHERE db_id = ? AND status='active' ORDER BY ignored, first_seen DESC",
                    (db["id"],),
                ).fetchall()
                recent = self._conn.execute(
                    "SELECT status, started_at, duration_ms FROM check_runs "
                    "WHERE db_id = ? ORDER BY id DESC LIMIT 30",
                    (db["id"],),
                ).fetchall()

            total = stats["total"] or 0
            healthy = (stats["ok_count"] or 0) + (stats["alert_count"] or 0)
            uptime = round(healthy / total * 100, 1) if total else None
            active_count = sum(1 for row in active_rows if not row["ignored"])
            ignored_count = sum(1 for row in active_rows if row["ignored"])
            run_status = latest["status"] if latest else None
            # 当所有告警均被忽略时，展示状态由“告警”回归“正常”
            if run_status in ("alert", "error") and active_count == 0 and ignored_count > 0:
                effective_status = "ok"
            else:
                effective_status = run_status
            result.append(
                {
                    "id": db["id"],
                    "name": db["name"],
                    "host": db["host"],
                    "port": db["port"],
                    "service_name": db["service_name"],
                    "sid": db["sid"],
                    "enabled": bool(db["enabled"]),
                    "latest_status": effective_status,
                    "run_status": run_status,
                    "latest_time": latest["started_at"] if latest else None,
                    "latest_message": latest["message"] if latest else None,
                    "latest_duration_ms": latest["duration_ms"] if latest else None,
                    "checks_24h": total,
                    "ok_24h": stats["ok_count"] or 0,
                    "alert_24h": stats["alert_count"] or 0,
                    "error_24h": stats["error_count"] or 0,
                    "avg_duration_ms": int(stats["avg_ms"]) if stats["avg_ms"] else None,
                    "uptime_24h": uptime,
                    "active_alerts": active_count,
                    "ignored_alerts": ignored_count,
                    "active_alerts_list": [
                        {
                            "key": row["alert_key"],
                            "message": row["message"],
                            "ignored": bool(row["ignored"]),
                            "first_seen": row["first_seen"],
                        }
                        for row in active_rows
                    ],
                    "recent": [
                        {"status": r["status"], "time": r["started_at"], "ms": r["duration_ms"]}
                        for r in reversed(recent)
                    ],
                    "hourly": self._hourly_history(db["id"]),
                    "alert_7d": self._alert_trend(db["id"]),
                }
            )
        return result

    def summary(self, data=None):
        if data is None:
            data = self.dashboard()
        total_checks = sum(d["checks_24h"] for d in data)
        healthy = sum(d["ok_24h"] + d["alert_24h"] for d in data)
        return {
            "total": len(data),
            "ok": sum(1 for d in data if d["latest_status"] == "ok"),
            "alert": sum(1 for d in data if d["latest_status"] == "alert"),
            "error": sum(1 for d in data if d["latest_status"] == "error"),
            "unknown": sum(1 for d in data if d["latest_status"] is None),
            "active_alerts": sum(d["active_alerts"] for d in data),
            "ignored_alerts": sum(d.get("ignored_alerts", 0) for d in data),
            "checks_24h": total_checks,
            "alerts_24h": sum(d["alert_24h"] for d in data),
            "connect_failures_24h": sum(d["error_24h"] for d in data),
            "incidents_24h": sum(d["alert_24h"] + d["error_24h"] for d in data),
            "overall_uptime": round(healthy / total_checks * 100, 1) if total_checks else None,
        }

    # ----------------------------------------------------------------- users
    def list_users(self):
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, username, role, created_at, last_login FROM users ORDER BY id"
            ).fetchall()
        return [dict(row) for row in rows]

    def get_user(self, user_id):
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        return dict(row) if row else None

    def get_user_by_name(self, username):
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
        return dict(row) if row else None

    def create_user(self, username, secret, role="viewer"):
        from auth import hash_password

        password_hash, salt, iterations = hash_password(secret)
        with self._lock:
            self._conn.execute(
                "INSERT INTO users (username, password_hash, salt, iterations, role, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (username, password_hash, salt, iterations, role, _now_iso()),
            )
            self._conn.commit()

    def update_user_role(self, user_id, role):
        with self._lock:
            self._conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
            self._conn.commit()

    def update_user_password(self, user_id, secret):
        from auth import hash_password

        password_hash, salt, iterations = hash_password(secret)
        with self._lock:
            self._conn.execute(
                "UPDATE users SET password_hash = ?, salt = ?, iterations = ? WHERE id = ?",
                (password_hash, salt, iterations, user_id),
            )
            self._conn.commit()

    def delete_user(self, user_id):
        with self._lock:
            self._conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            self._conn.commit()

    def count_admins(self):
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS c FROM users WHERE role = 'admin'"
            ).fetchone()
        return int(row["c"])

    def touch_login(self, user_id):
        with self._lock:
            self._conn.execute(
                "UPDATE users SET last_login = ? WHERE id = ?", (_now_iso(), user_id)
            )
            self._conn.commit()
