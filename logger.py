# -*- coding: utf-8 -*-
"""日志模块：按天切分文件、控制台输出、过期清理。"""

import glob
import logging
import os
from datetime import timedelta

from timesync import time_sync

log = logging.getLogger(__name__)


class OffsetFormatter(logging.Formatter):
    """按配置时区与 NTP 偏移输出精确到毫秒的时间。"""

    def formatTime(self, record, datefmt=None):
        moment = time_sync.from_timestamp(record.created)
        if datefmt:
            return moment.strftime(datefmt)
        return moment.strftime("%Y-%m-%d %H:%M:%S") + ".%03d" % (moment.microsecond // 1000)


class DailyFileHandler(logging.Handler):
    """按天写入 logs/monitor_YYYYMMDD.log 的日志处理器，支持跨天自动切换。"""

    def __init__(self, log_dir, prefix="monitor_", encoding="utf-8"):
        super().__init__()
        self.log_dir = log_dir
        self.prefix = prefix
        self.encoding = encoding
        self._date = None
        self._stream = None
        os.makedirs(log_dir, exist_ok=True)
        self._open_for_today()

    def _path_for(self, date_str):
        return os.path.join(self.log_dir, "{}{}.log".format(self.prefix, date_str))

    def _open_for_today(self):
        today = time_sync.now().strftime("%Y%m%d")
        if today != self._date:
            if self._stream is not None:
                try:
                    self._stream.close()
                except Exception:
                    pass
            self._date = today
            self._stream = open(self._path_for(today), "a", encoding=self.encoding)

    def emit(self, record):
        try:
            self._open_for_today()
            self._stream.write(self.format(record) + "\n")
            self._stream.flush()
        except Exception:
            self.handleError(record)

    def close(self):
        if self._stream is not None:
            try:
                self._stream.close()
            finally:
                self._stream = None
        super().close()


def cleanup_old_logs(log_dir, retention_days):
    """删除超过保留天数的日志文件。retention_days <= 0 表示不清理。"""
    try:
        days = int(retention_days)
    except (TypeError, ValueError):
        return
    if days <= 0:
        return
    cutoff = time_sync.now() - timedelta(days=days)
    for path in glob.glob(os.path.join(log_dir, "monitor_*.log")):
        try:
            if time_sync.from_timestamp(os.path.getmtime(path)) < cutoff:
                os.remove(path)
                log.info("已清理过期日志: %s", os.path.basename(path))
        except OSError:
            pass


def setup_logging(log_dir, level="INFO", retention_days=30):
    """初始化根日志器，返回业务用的 logger。"""
    os.makedirs(log_dir, exist_ok=True)

    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass

    numeric_level = getattr(logging, str(level).upper(), logging.INFO)
    root.setLevel(numeric_level)

    formatter = OffsetFormatter("%(asctime)s [%(levelname)s] %(message)s")

    file_handler = DailyFileHandler(log_dir)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    cleanup_old_logs(log_dir, retention_days)
    return logging.getLogger("oracle_monitor")
