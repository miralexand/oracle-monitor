# -*- coding: utf-8 -*-
"""邮件发送模块：支持 SSL / STARTTLS / 明文三种方式，兼容中文内容。"""

import logging
import smtplib
import ssl
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate

log = logging.getLogger(__name__)


class Mailer(object):
    def __init__(self, config):
        self.server = config.get("smtp", "server").strip()
        self.port = config.getint("smtp", "port", fallback=465)
        self.encryption = config.get("smtp", "encryption", fallback="ssl").strip().lower()
        self.sender = config.get("smtp", "sender").strip()
        self.password = config.get("smtp", "password", fallback="").strip()
        self.subject_prefix = config.get("smtp", "subject_prefix", fallback="[Oracle监控]").strip()
        receivers_raw = config.get("smtp", "receivers", fallback="").replace(";", ",")
        self.receivers = [item.strip() for item in receivers_raw.split(",") if item.strip()]
        if not self.receivers:
            raise ValueError("smtp.receivers 未配置收件人")

    def send(self, subject, body, receivers=None):
        recipients = receivers or self.receivers
        message = MIMEText(body, "plain", "utf-8")
        message["Subject"] = Header(
            "{} {}".format(self.subject_prefix, subject).strip(), "utf-8"
        )
        message["From"] = formataddr(
            (str(Header("Oracle Monitor", "utf-8")), self.sender)
        )
        message["To"] = ", ".join(recipients)
        message["Date"] = formatdate(localtime=True)

        timeout = 30
        if self.encryption == "ssl":
            conn = smtplib.SMTP_SSL(
                self.server, self.port, timeout=timeout, context=ssl.create_default_context()
            )
        else:
            conn = smtplib.SMTP(self.server, self.port, timeout=timeout)
            conn.ehlo()
            if self.encryption == "tls":
                conn.starttls(context=ssl.create_default_context())
                conn.ehlo()

        try:
            if self.password:
                conn.login(self.sender, self.password)
            conn.sendmail(self.sender, recipients, message.as_string())
        finally:
            try:
                conn.quit()
            except Exception:
                pass

        log.debug("邮件已发送: %s -> %s", self.sender, recipients)
