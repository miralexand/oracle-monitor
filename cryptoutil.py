# -*- coding: utf-8 -*-
"""敏感字段的透明加密存储。

使用 Fernet（AES-128-CBC + HMAC）对数据库账号/密码、SMTP 授权码等字段加密后
再写入 SQLite。密钥来源优先级：

1. 环境变量 ``OM_DATA_KEY``（推荐用于生产，密钥不落盘）
2. 数据目录下的 ``data.key`` 文件（首次自动生成，权限 600）

注意：这是"静态加密"，密钥与数据在同一主机；可防止直接查看数据库文件时
泄露明文，但无法抵御主机被完全攻破。更强隔离请使用 KMS / Vault。
"""

import os

from cryptography.fernet import Fernet, InvalidToken

PREFIX = "enc:v1:"


def is_encrypted(value):
    return isinstance(value, str) and value.startswith(PREFIX)


class Cipher(object):
    def __init__(self, data_dir):
        key = os.environ.get("OM_DATA_KEY")
        if key:
            key = key.strip().encode("ascii")
        else:
            key = self._load_or_create(os.path.join(data_dir, "data.key"))
        self._fernet = Fernet(key)

    @staticmethod
    def _load_or_create(path):
        if os.path.exists(path):
            with open(path, "rb") as handle:
                return handle.read().strip()
        key = Fernet.generate_key()
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(key)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        return key

    def encrypt(self, value):
        if value is None or value == "":
            return value
        token = self._fernet.encrypt(str(value).encode("utf-8")).decode("ascii")
        return PREFIX + token

    def decrypt(self, value):
        if not is_encrypted(value):
            return value
        try:
            return self._fernet.decrypt(value[len(PREFIX):].encode("ascii")).decode("utf-8")
        except (InvalidToken, ValueError):
            return ""
