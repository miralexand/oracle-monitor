# -*- coding: utf-8 -*-
"""Oracle 连接管理：支持 Thin（无需客户端）与 Thick（需 Instant Client）模式。

python-oracledb 的 Thin 模式仅支持 Oracle 12.1 及以上；连接更旧的数据库
（报 DPY-3010）必须使用 Thick 模式并加载 Oracle Instant Client。
init_oracle_client() 是进程级全局操作，因此本模块保证只初始化一次。
"""

import logging
import threading

try:
    import oracledb
except ImportError:  # pragma: no cover
    oracledb = None

log = logging.getLogger(__name__)

_lock = threading.RLock()
_thick_initialized = False


def is_available():
    return oracledb is not None


def is_thick_initialized():
    return _thick_initialized


def ensure_thick(lib_dir=None):
    """启用 Thick 模式（幂等）。必须在建立任何连接之前调用。"""
    global _thick_initialized
    if oracledb is None:
        raise RuntimeError("未安装 python-oracledb")
    if _thick_initialized:
        return
    with _lock:
        if _thick_initialized:
            return
        if lib_dir:
            oracledb.init_oracle_client(lib_dir=lib_dir)
        else:
            oracledb.init_oracle_client()
        _thick_initialized = True
        log.info("已启用 Oracle Thick 模式 (lib_dir=%s)", lib_dir or "auto")


def _build_dsn(host, port, service_name, sid):
    if service_name:
        return oracledb.makedsn(host, port, service_name=service_name)
    if sid:
        return oracledb.makedsn(host, port, sid=sid)
    raise ValueError("必须配置 service_name 或 sid")


def connect(db, use_thick=False, lib_dir=None):
    """根据数据库记录建立连接。db 为字典或 sqlite3.Row。"""
    if oracledb is None:
        raise RuntimeError("未安装 python-oracledb，无法连接数据库")
    if use_thick:
        ensure_thick(lib_dir)

    host = str(db["host"]).strip()
    port = int(db["port"] or 1521)
    user = str(db["username"]).strip()
    password = db["password"] or ""
    timeout = int(db["connect_timeout"] or 10)
    service_name = (db["service_name"] or "").strip()
    sid = (db["sid"] or "").strip()

    dsn = _build_dsn(host, port, service_name, sid)
    connection = oracledb.connect(
        user=user, password=password, dsn=dsn, tcp_connect_timeout=timeout
    )
    # 单条语句最长执行时间，避免慢查询长期占用数据库资源
    try:
        connection.call_timeout = 30000
    except Exception:
        pass
    return connection
