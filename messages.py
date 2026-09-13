# -*- coding: utf-8 -*-
"""告警邮件正文模板。"""

from timesync import time_sync


def _now():
    return time_sync.now().strftime("%Y-%m-%d %H:%M:%S")


def build_alert_body(instance, messages):
    lines = [
        "【监控时间】{}".format(_now()),
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
        "【监控时间】{}".format(_now()),
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
