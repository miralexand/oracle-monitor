# -*- coding: utf-8 -*-
"""日志解析与筛选：按级别 / 数据库 / 关键字细分查看与导出。"""

import os
import re

from timesync import time_sync

LINE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d+)?) \[(\w+)\] (.*)$")
LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR"]
ALL_FILES = "__all__"


def available_files(log_dir):
    if not os.path.isdir(log_dir):
        return []
    files = []
    for name in os.listdir(log_dir):
        if not name.endswith(".log"):
            continue
        path = os.path.join(log_dir, name)
        try:
            stat = os.stat(path)
        except OSError:
            continue
        files.append(
            {
                "name": name,
                "size": stat.st_size,
                "modified": time_sync.from_timestamp(stat.st_mtime).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            }
        )
    files.sort(key=lambda item: item["name"], reverse=True)
    return files


def _parse_text(text, source):
    entries = []
    for raw in text.splitlines():
        match = LINE_RE.match(raw)
        if match:
            entries.append(
                {
                    "time": match.group(1),
                    "level": match.group(2).upper(),
                    "message": match.group(3),
                    "extra": [],
                    "source": source,
                }
            )
        elif entries and raw.strip():
            entries[-1]["extra"].append(raw)
    return entries


def _read_file(path, source):
    try:
        with open(path, "rb") as handle:
            text = handle.read().decode("utf-8", errors="replace")
    except OSError:
        return []
    return _parse_text(text, source)


def collect_entries(log_dir, filename):
    """读取指定日志文件；filename 为 ALL_FILES 时合并全部日志。"""
    if filename and filename != ALL_FILES:
        return _read_file(os.path.join(log_dir, filename), filename)
    entries = []
    for item in reversed(available_files(log_dir)):  # 旧 -> 新
        entries.extend(_read_file(os.path.join(log_dir, item["name"]), item["name"]))
    return entries


def filter_entries(entries, levels=None, db=None, keyword=None):
    wanted = {str(level).upper() for level in levels} if levels else None
    keyword = (keyword or "").strip().lower()
    tag = "[{}]".format(db) if db else None
    result = []
    for entry in entries:
        if wanted and entry["level"] not in wanted:
            continue
        message = entry["message"]
        if tag and tag not in message:
            continue
        if keyword:
            blob = (message + "\n" + "\n".join(entry["extra"])).lower()
            if keyword not in blob:
                continue
        result.append(entry)
    return result


def level_counts(entries):
    counts = {level: 0 for level in LEVELS}
    for entry in entries:
        counts[entry["level"]] = counts.get(entry["level"], 0) + 1
    return counts


def to_text(entries):
    lines = []
    for entry in entries:
        lines.append("{} [{}] {}".format(entry["time"], entry["level"], entry["message"]))
        lines.extend(entry["extra"])
    return "\n".join(lines)
