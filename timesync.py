# -*- coding: utf-8 -*-
"""NTP 软件校时：向 NTP 服务器查询时间偏移，并应用到日志与界面显示。

为什么不直接设置系统时钟？容器默认没有修改主机时钟的权限，且修改容器时钟会
影响宿主机。这里采用"软件偏移"方案：记录本地时钟与 NTP 的偏差，在生成时间戳
时补偿该偏差，从而让日志与界面时间精准，且无需特权、不触碰宿主机。
"""

import logging
import socket
import struct
import threading
import time
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

log = logging.getLogger(__name__)

NTP_EPOCH_DELTA = 2208988800  # 1900-01-01 到 1970-01-01 的秒数
DEFAULT_SERVER = "pool.ntp.org"
DEFAULT_INTERVAL_HOURS = 5
DEFAULT_TIMEZONE = "Asia/Shanghai"


class TimeSync(object):
    def __init__(self):
        self._lock = threading.Lock()
        self.enabled = False
        self.server = DEFAULT_SERVER
        self.interval_seconds = DEFAULT_INTERVAL_HOURS * 3600
        self.timezone_name = DEFAULT_TIMEZONE
        self._tz = self._resolve_tz(DEFAULT_TIMEZONE)
        self._offset = 0.0
        self.last_sync = None
        self.last_error = None
        self._started = False

    # ------------------------------------------------------------ timezone
    @staticmethod
    def _resolve_tz(name):
        name = (name or DEFAULT_TIMEZONE).strip() or DEFAULT_TIMEZONE
        if ZoneInfo is not None:
            try:
                return ZoneInfo(name)
            except Exception:
                log.warning("时区 %s 无效，回退默认", name)
        if name in ("Asia/Shanghai", "Asia/Chongqing", "Asia/Harbin", "PRC"):
            return timezone(timedelta(hours=8))
        return timezone.utc

    # ------------------------------------------------------------- configure
    def configure(self, enabled, server, interval_hours, timezone_name=None):
        with self._lock:
            self.enabled = bool(enabled)
            self.server = (server or DEFAULT_SERVER).strip() or DEFAULT_SERVER
            try:
                hours = float(interval_hours)
            except (TypeError, ValueError):
                hours = DEFAULT_INTERVAL_HOURS
            self.interval_seconds = max(1, hours) * 3600
            if timezone_name is not None:
                self.timezone_name = (
                    (timezone_name or DEFAULT_TIMEZONE).strip() or DEFAULT_TIMEZONE
                )
                self._tz = self._resolve_tz(self.timezone_name)

    # -------------------------------------------------------------- ntp query
    @staticmethod
    def _parse_target(server):
        host, _, port = server.partition(":")
        return host.strip(), int(port) if port.strip() else 123

    @staticmethod
    def _query(server, timeout=3.0):
        host, port = TimeSync._parse_target(server)
        packet = bytearray(48)
        packet[0] = 0x1B  # LI=0, VN=3, Mode=3 (client)
        t1 = time.time()
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(timeout)
            sock.sendto(bytes(packet), (host, port))
            data, _ = sock.recvfrom(48)
        t4 = time.time()
        if len(data) < 48:
            raise ValueError("NTP 响应长度异常")

        def timestamp(offset):
            seconds, fraction = struct.unpack("!II", data[offset:offset + 8])
            return seconds + fraction / 2 ** 32 - NTP_EPOCH_DELTA

        t2 = timestamp(32)  # 服务器接收时间
        t3 = timestamp(40)  # 服务器发送时间
        offset = ((t2 - t1) + (t3 - t4)) / 2.0
        return offset

    # ------------------------------------------------------------------ sync
    def sync_once(self):
        with self._lock:
            enabled = self.enabled
            server = self.server
        if not enabled:
            return False, "NTP 未启用"
        try:
            offset = self._query(server)
        except Exception as exc:  # 网络不可达 / DNS 失败 / 超时
            with self._lock:
                self.last_error = str(exc)
            log.warning("NTP 校准失败 (%s): %s", server, exc)
            return False, str(exc)
        with self._lock:
            self._offset = offset
            self.last_error = None
            self.last_sync = (
                datetime.now(timezone.utc) + timedelta(seconds=offset)
            ).astimezone(self._tz)
        log.info("NTP 校准成功: 服务器 %s，时钟偏移 %.3f 秒", server, offset)
        return True, None

    def start(self):
        """启动后台线程，每隔 interval_seconds 自动校准一次。"""
        if self._started:
            return
        self._started = True
        threading.Thread(target=self._loop, name="ntp-sync", daemon=True).start()

    def _loop(self):
        while True:
            with self._lock:
                interval = self.interval_seconds
            time.sleep(interval)
            self.sync_once()

    # ------------------------------------------------------------------ apply
    def offset(self):
        with self._lock:
            return self._offset

    def now(self):
        with self._lock:
            tz = self._tz
            offset = self._offset
        instant = datetime.now(timezone.utc) + timedelta(seconds=offset)
        return instant.astimezone(tz)

    def from_timestamp(self, timestamp):
        with self._lock:
            tz = self._tz
            offset = self._offset
        instant = datetime.fromtimestamp(timestamp, tz=timezone.utc) + timedelta(
            seconds=offset
        )
        return instant.astimezone(tz)

    def now_iso(self, timespec="seconds"):
        return self.now().isoformat(timespec=timespec)

    def status(self):
        with self._lock:
            timezone_name = self.timezone_name
            last_sync = (
                self.last_sync.isoformat(timespec="seconds") if self.last_sync else None
            )
            status = {
                "enabled": self.enabled,
                "server": self.server,
                "offset_seconds": round(self._offset, 3),
                "last_sync": last_sync,
                "last_error": self.last_error,
                "interval_hours": self.interval_seconds / 3600.0,
                "timezone": timezone_name,
            }
        status["now"] = self.now().strftime("%Y-%m-%d %H:%M:%S")
        return status


time_sync = TimeSync()
