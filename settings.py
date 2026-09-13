# -*- coding: utf-8 -*-
"""配置模型：在 configparser 与纯字典之间提供统一访问接口。

checks.py / mailer.py 通过 get()/getint()/getboolean() 读取配置，
DictConfig 让 Web 端可以用扁平的 SQLite 设置直接驱动这些模块，无需改动它们。
"""

DEFAULT_ALERT_LOG_PATTERNS = "ORA-00600,ORA-07445,ORA-04031,ORA-01555,ORA-00257,ORA-16038"

DEFAULT_SETTINGS = {
    # 调度（默认 15 分钟，降低对数据库的轮询压力）
    "interval_minutes": "15",
    # 告警
    "silence_minutes": "30",
    "notify_on_recovery": "true",
    # Oracle 连接
    "oracle_use_thick": "false",
    "oracle_client_lib_dir": "",
    # 日志
    "log_level": "INFO",
    "log_retention_days": "30",
    # 时间同步（NTP）
    "ntp_enabled": "false",
    "ntp_server": "pool.ntp.org",
    "ntp_interval_hours": "5",
    "timezone": "Asia/Shanghai",
    # SMTP
    "smtp_server": "smtp.qq.com",
    "smtp_port": "465",
    "smtp_encryption": "ssl",
    "smtp_sender": "",
    "smtp_password": "",
    "smtp_receivers": "",
    "smtp_subject_prefix": "[Oracle监控]",
    # 阈值
    "tablespace_usage_pct": "85",
    "session_count": "500",
    "long_query_seconds": "3600",
    "lock_wait_seconds": "300",
    "archive_usage_pct": "85",
    "rman_backup_interval_hours": "24",
    "alert_log_patterns": DEFAULT_ALERT_LOG_PATTERNS,
    # 监控模块开关
    "enable_m2_instance_status": "true",
    "enable_m3_tablespace": "true",
    "enable_m4_session_count": "true",
    "enable_m5_long_query": "true",
    "enable_m6_lock_wait": "true",
    "enable_m7_archive_space": "false",
    "enable_m8_rman_backup": "false",
    "enable_m9_alert_log": "false",
}

BOOL_KEYS = {
    "notify_on_recovery",
    "oracle_use_thick",
    "ntp_enabled",
    "enable_m2_instance_status",
    "enable_m3_tablespace",
    "enable_m4_session_count",
    "enable_m5_long_query",
    "enable_m6_lock_wait",
    "enable_m7_archive_space",
    "enable_m8_rman_backup",
    "enable_m9_alert_log",
}


def as_bool(value, fallback=False):
    if value is None or value == "":
        return fallback
    return str(value).strip().lower() in ("1", "true", "yes", "on")


class DictConfig(object):
    """模仿 configparser 的只读访问接口。"""

    def __init__(self, data):
        self.data = data

    def __contains__(self, section):
        return section in self.data

    def __getitem__(self, section):
        return self.data[section]

    def get(self, section, key, fallback=None):
        return self.data.get(section, {}).get(key, fallback)

    def getint(self, section, key, fallback=0):
        value = self.get(section, key, None)
        if value is None or value == "":
            return fallback
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return fallback

    def getboolean(self, section, key, fallback=False):
        return as_bool(self.get(section, key, None), fallback)


def build_config(settings):
    """把扁平设置字典转换为 checks/mailer 需要的分段结构。"""
    s = settings
    return DictConfig(
        {
            "oracle": {
                "use_thick": s.get("oracle_use_thick", "false"),
                "client_lib_dir": s.get("oracle_client_lib_dir", ""),
            },
            "thresholds": {
                "tablespace_usage_pct": s.get("tablespace_usage_pct", "85"),
                "session_count": s.get("session_count", "500"),
                "long_query_seconds": s.get("long_query_seconds", "3600"),
                "lock_wait_seconds": s.get("lock_wait_seconds", "300"),
                "archive_usage_pct": s.get("archive_usage_pct", "85"),
                "rman_backup_interval_hours": s.get("rman_backup_interval_hours", "24"),
                "alert_log_patterns": s.get("alert_log_patterns", DEFAULT_ALERT_LOG_PATTERNS),
            },
            "modules": {
                "enable_m2_instance_status": s.get("enable_m2_instance_status", "true"),
                "enable_m3_tablespace": s.get("enable_m3_tablespace", "true"),
                "enable_m4_session_count": s.get("enable_m4_session_count", "true"),
                "enable_m5_long_query": s.get("enable_m5_long_query", "true"),
                "enable_m6_lock_wait": s.get("enable_m6_lock_wait", "true"),
                "enable_m7_archive_space": s.get("enable_m7_archive_space", "false"),
                "enable_m8_rman_backup": s.get("enable_m8_rman_backup", "false"),
                "enable_m9_alert_log": s.get("enable_m9_alert_log", "false"),
            },
            "smtp": {
                "server": s.get("smtp_server", ""),
                "port": s.get("smtp_port", "465"),
                "encryption": s.get("smtp_encryption", "ssl"),
                "sender": s.get("smtp_sender", ""),
                "password": s.get("smtp_password", ""),
                "receivers": s.get("smtp_receivers", ""),
                "subject_prefix": s.get("smtp_subject_prefix", "[Oracle监控]"),
            },
            "alert": {
                "notify_on_recovery": s.get("notify_on_recovery", "true"),
                "silence_minutes": s.get("silence_minutes", "30"),
            },
            "schedule": {"interval_minutes": s.get("interval_minutes", "5")},
            "logging": {
                "level": s.get("log_level", "INFO"),
                "retention_days": s.get("log_retention_days", "30"),
            },
        }
    )
