# -*- coding: utf-8 -*-
"""Oracle 数据库监控告警程序 — 主程序入口。

打包为 exe 后，配置文件 config.ini、日志目录 logs/、状态文件 state.json
均放在 exe 同目录，便于整体拷贝分发。
"""

import argparse
import configparser
import json
import os
import shutil
import sys
import time
from datetime import datetime

from checks import run_checks
from logger import setup_logging
from mailer import Mailer

VERSION = "1.2.1"
APP_NAME = "oracle_monitor"


def is_frozen():
    return bool(getattr(sys, "frozen", False))


def base_dir():
    """可写文件（config.ini / logs / state.json）的基准目录。"""
    if is_frozen():
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def resource_path(name):
    """读取随程序打包的只读资源（如 config.sample.ini）。"""
    if is_frozen() and hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, name)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), name)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog=APP_NAME, description="Oracle 数据库监控告警程序"
    )
    parser.add_argument("--once", action="store_true", help="单次执行后退出")
    parser.add_argument("--config", metavar="PATH", help="指定配置文件路径，默认 config.ini")
    parser.add_argument("--check", metavar="M1,M3", help="只运行指定监控项")
    parser.add_argument("--test-mail", action="store_true", help="发送一封测试邮件后退出")
    parser.add_argument("--dry-run", action="store_true", help="检测但不发邮件，仅打印到控制台")
    parser.add_argument("--version", action="version", version="%(prog)s " + VERSION)
    return parser.parse_args(argv)


def ensure_config(config_path):
    """配置文件不存在时，从模板生成一份并返回 True。"""
    if os.path.exists(config_path):
        return False
    sample = resource_path("config.sample.ini")
    if not os.path.exists(sample):
        raise SystemExit("未找到配置文件 {}，且缺少配置模板 config.sample.ini".format(config_path))
    shutil.copyfile(sample, config_path)
    print("=" * 60)
    print("首次运行：已生成配置文件")
    print("  {}".format(config_path))
    print("请编辑该文件，填写 Oracle 数据库与 SMTP 邮箱信息后重新运行。")
    print("=" * 60)
    return True


def load_config(config_path):
    config = configparser.ConfigParser(interpolation=None)
    if not config.read(config_path, encoding="utf-8"):
        raise SystemExit("无法读取配置文件: {}".format(config_path))
    if "oracle" not in config:
        raise SystemExit("配置文件缺少 [oracle] 段: {}".format(config_path))
    return config


class AlertState(object):
    """告警状态持久化，用于静默期与恢复通知。"""

    def __init__(self, path):
        self.path = path
        self.data = {}
        self.load()

    def load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as handle:
                    self.data = json.load(handle)
            except (ValueError, OSError):
                self.data = {}

    def save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(self.data, handle, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)


def connect_database(config):
    import oracledb

    oracle = config["oracle"]
    host = oracle["host"].strip()
    port = int(oracle.get("port", "1521"))
    user = oracle["user"].strip()
    password = oracle["password"]
    timeout = int(oracle.get("connect_timeout", "10"))

    service_name = oracle.get("service_name", "").strip()
    sid = oracle.get("sid", "").strip()
    if service_name:
        dsn = oracledb.makedsn(host, port, service_name=service_name)
    elif sid:
        dsn = oracledb.makedsn(host, port, sid=sid)
    else:
        raise ValueError("config.ini 中必须配置 service_name 或 sid")

    return oracledb.connect(
        user=user, password=password, dsn=dsn, tcp_connect_timeout=timeout
    )


def build_alert_body(instance, messages):
    lines = [
        "【监控时间】{}".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        "【数据库实例】{}".format(instance),
        "【异常数量】{}".format(len(messages)),
        "",
        "-------------------------------",
    ]
    for index, message in enumerate(messages, 1):
        lines.append("{}. {}".format(index, message))
    lines += [
        "",
        "请及时登录数据库排查。",
        "-------------------------------",
        "本邮件由 Oracle 监控程序自动发送，请勿回复。",
    ]
    return "\n".join(lines)


def build_recovery_body(instance, messages):
    lines = [
        "【监控时间】{}".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        "【数据库实例】{}".format(instance),
        "【恢复数量】{}".format(len(messages)),
        "",
        "以下告警已恢复正常：",
        "-------------------------------",
    ]
    for index, message in enumerate(messages, 1):
        lines.append("{}. {}".format(index, message))
    lines += [
        "-------------------------------",
        "本邮件由 Oracle 监控程序自动发送，请勿回复。",
    ]
    return "\n".join(lines)


def process_alerts(alerts, config, state, mailer, log, args, instance):
    if args.dry_run:
        if alerts:
            log.info("[dry-run] 检测到 %d 项异常，不发送邮件：", len(alerts))
            for _, message in alerts:
                log.info("[dry-run] - %s", message)
        else:
            log.info("[dry-run] 无异常")
        return

    now = time.time()
    silence = config.getint("alert", "silence_minutes", fallback=30) * 60
    notify_recovery = config.getboolean("alert", "notify_on_recovery", fallback=True)

    current = dict(alerts)
    to_send = []
    for key, message in current.items():
        entry = state.data.get(key)
        if entry is None or (now - entry.get("last_sent", 0)) >= silence:
            to_send.append(message)
            state.data[key] = {
                "last_sent": now,
                "message": message,
                "first_seen": entry.get("first_seen", now) if entry else now,
            }

    recovered = []
    for key in [k for k in list(state.data.keys()) if k not in current]:
        entry = state.data.pop(key)
        recovered.append(entry.get("message", key))

    state.save()

    if to_send:
        subject = "{} 检测到 {} 项异常".format(instance, len(current))
        try:
            mailer.send(subject, build_alert_body(instance, to_send))
            log.info("已发送告警邮件，共 %d 条告警", len(to_send))
        except Exception as exc:
            log.error("邮件发送失败: %s", exc)
    elif current:
        log.info("告警处于静默期，未发送邮件")

    if recovered:
        for message in recovered:
            log.info("告警已恢复: %s", message)
        if notify_recovery:
            subject = "{} 告警已恢复".format(instance)
            try:
                mailer.send(subject, build_recovery_body(instance, recovered))
                log.info("已发送恢复通知，共 %d 项恢复", len(recovered))
            except Exception as exc:
                log.error("恢复邮件发送失败: %s", exc)


def run_once(config, state, mailer, log, args, selected=None):
    oracle = config["oracle"]
    host = oracle.get("host", "-")
    port = oracle.get("port", "1521")
    service = oracle.get("service_name") or oracle.get("sid") or "-"
    instance = "{} ({}:{})".format(service, host, port)

    log.info("开始执行数据库检查: %s", instance)

    conn = None
    try:
        conn = connect_database(config)
        log.info("数据库连接成功: %s", service)
    except Exception as exc:
        log.error("数据库连接失败: %s", exc)
        process_alerts(
            [("connectivity", "数据库连接失败: {}".format(exc))],
            config,
            state,
            mailer,
            log,
            args,
            instance,
        )
        return

    try:
        alerts = run_checks(conn, config, selected)
    finally:
        try:
            conn.close()
        except Exception:
            pass

    if alerts:
        for _, message in alerts:
            log.warning("告警: %s", message)
    else:
        log.info("所有检查通过，无告警")

    process_alerts(alerts, config, state, mailer, log, args, instance)


def main(argv=None):
    if sys.platform == "win32":
        for stream in (sys.stdout, sys.stderr):
            try:
                stream.reconfigure(errors="replace")
            except Exception:
                pass

    args = parse_args(argv)
    base = base_dir()
    config_path = os.path.abspath(args.config) if args.config else os.path.join(base, "config.ini")

    if ensure_config(config_path):
        return 0

    config = load_config(config_path)

    log_dir = config.get("logging", "dir", fallback="logs")
    if not os.path.isabs(log_dir):
        log_dir = os.path.join(base, log_dir)
    log = setup_logging(
        log_dir,
        config.get("logging", "level", fallback="INFO"),
        config.getint("logging", "retention_days", fallback=30),
    )
    log.info("加载配置成功: %s", config_path)

    try:
        mailer = Mailer(config)
    except Exception as exc:
        log.error("初始化邮件模块失败: %s", exc)
        return 1

    if args.test_mail:
        try:
            mailer.send(
                "测试邮件",
                "这是一封测试邮件，收到说明 SMTP 配置正确。\n发送时间: {}".format(
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                ),
            )
            log.info("测试邮件已发送至: %s", ", ".join(mailer.receivers))
            return 0
        except Exception as exc:
            log.error("测试邮件发送失败: %s", exc)
            return 1

    state = AlertState(os.path.join(base, "state.json"))
    selected = None
    if args.check:
        selected = [item.strip().upper() for item in args.check.split(",") if item.strip()]

    if args.once:
        run_once(config, state, mailer, log, args, selected)
        return 0

    interval_minutes = config.getint("schedule", "interval_minutes", fallback=5)
    interval_seconds = max(1, interval_minutes) * 60
    log.info("启动持续监控，每 %d 分钟执行一次，按 Ctrl+C 停止", interval_minutes)
    try:
        while True:
            run_once(config, state, mailer, log, args, selected)
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        log.info("收到停止信号，程序退出")
    return 0


if __name__ == "__main__":
    sys.exit(main())
