# -*- coding: utf-8 -*-
"""后台监控调度：按间隔遍历所有启用的数据库并执行检查、落库、发信。"""

import logging
import threading
import time

import oracle_conn
from checks import run_checks
from mailer import Mailer
from messages import build_alert_body, build_recovery_body
from settings import as_bool, build_config
from timesync import time_sync

log = logging.getLogger(__name__)


class MonitorScheduler(object):
    def __init__(self, store):
        self.store = store
        self._thread = None
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._running = threading.Event()

    # --------------------------------------------------------------- lifecycle
    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, name="monitor-scheduler", daemon=True
        )
        self._thread.start()
        log.info("监控调度线程已启动")

    def stop(self):
        self._stop.set()
        self._wake.set()

    def trigger(self):
        """立即唤醒一次检测（设置变更后可调用）。"""
        self._wake.set()

    def is_running(self):
        return self._running.is_set()

    # ------------------------------------------------------------------- loop
    def _loop(self):
        while not self._stop.is_set():
            self._running.set()
            try:
                self.run_cycle()
            except Exception:
                log.exception("监控周期执行异常")
            finally:
                self._running.clear()
            interval = self._interval_seconds()
            self._wake.wait(timeout=interval)
            self._wake.clear()

    def _interval_seconds(self):
        try:
            minutes = int(float(self.store.get_setting("interval_minutes", "5")))
        except (TypeError, ValueError):
            minutes = 5
        return max(1, minutes) * 60

    # ------------------------------------------------------------------ cycle
    def run_cycle(self):
        settings = self.store.get_settings()
        config = build_config(settings)
        self._prepare_thick(settings)

        databases = self.store.list_databases(enabled_only=True)
        log.info("开始监控周期，共 %d 个数据库", len(databases))
        mailer = self._build_mailer(config)
        for db in databases:
            self.check_database(db, config, mailer)

    def _prepare_thick(self, settings):
        if not as_bool(settings.get("oracle_use_thick"), False):
            return
        lib_dir = (settings.get("oracle_client_lib_dir") or "").strip() or None
        try:
            oracle_conn.ensure_thick(lib_dir)
        except Exception as exc:
            log.error(
                "启用 Oracle Thick 模式失败: %s（若刚在页面切换连接模式，请重启服务生效）", exc
            )

    def _build_mailer(self, config):
        try:
            return Mailer(config)
        except Exception as exc:
            log.warning("邮件模块不可用，跳过邮件通知: %s", exc)
            return None

    def check_database(self, db, config, mailer):
        settings = self.store.get_settings()
        use_thick = as_bool(settings.get("oracle_use_thick"), False)
        lib_dir = (settings.get("oracle_client_lib_dir") or "").strip() or None

        started = time.time()
        started_at = time_sync.now_iso()
        conn = None
        alerts = []
        status = "ok"
        message = None

        try:
            conn = oracle_conn.connect(db, use_thick, lib_dir)
            log.info("[%s] 数据库连接成功", db["name"])
            alerts = run_checks(conn, config, None)
            status = "alert" if alerts else "ok"
            if alerts:
                for _, text in alerts:
                    log.warning("[%s] 告警: %s", db["name"], text)
            else:
                log.info("[%s] 所有检查通过", db["name"])
        except Exception as exc:
            status = "error"
            message = str(exc)
            alerts = [("connectivity", "数据库连接失败: {}".format(exc))]
            log.error("[%s] 检查失败: %s", db["name"], exc)
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

        duration_ms = int((time.time() - started) * 1000)
        finished_at = time_sync.now_iso()
        self.store.record_run(
            db["id"], started_at, finished_at, status, len(alerts), duration_ms, message
        )
        self._notify(db, config, mailer, alerts)

    def _notify(self, db, config, mailer, alerts):
        silence_seconds = config.getint("alert", "silence_minutes", fallback=30) * 60
        to_send, recovered = self.store.apply_alert_cycle(db["id"], alerts, silence_seconds)
        notify_recovery = config.getboolean("alert", "notify_on_recovery", fallback=True)
        instance = "{} ({}:{})".format(db["name"], db["host"], db["port"])

        if mailer is not None and to_send:
            try:
                mailer.send(
                    "{} 检测到 {} 项异常".format(db["name"], len(dict(alerts))),
                    build_alert_body(instance, to_send),
                )
                log.info("[%s] 已发送告警邮件，共 %d 条", db["name"], len(to_send))
            except Exception as exc:
                log.error("[%s] 邮件发送失败: %s", db["name"], exc)

        if recovered:
            for text in recovered:
                log.info("[%s] 告警已恢复: %s", db["name"], text)
            if mailer is not None and notify_recovery:
                try:
                    mailer.send(
                        "{} 告警已恢复".format(db["name"]),
                        build_recovery_body(instance, recovered),
                    )
                    log.info("[%s] 已发送恢复通知，共 %d 项", db["name"], len(recovered))
                except Exception as exc:
                    log.error("[%s] 恢复邮件发送失败: %s", db["name"], exc)


def test_connection(db, use_thick=False, lib_dir=None):
    """测试单个数据库连接，返回 (是否成功, 信息)。"""
    try:
        conn = oracle_conn.connect(db, use_thick, lib_dir)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM DUAL")
            cursor.fetchone()
            cursor.close()
        finally:
            conn.close()
        return True, "连接成功"
    except Exception as exc:
        return False, str(exc)
