# -*- coding: utf-8 -*-
"""配置备份与恢复：数据库账号密码等敏感信息以加密形式导出/导入。

备份文件为 JSON，其中 `data` 字段是用备份密码经 PBKDF2 派生密钥后
用 Fernet（AES-128-CBC + HMAC-SHA256）加密的负载，包含数据库列表与全部设置。
"""

import base64
import json
import os

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from timesync import time_sync

FORMAT = "oracle-monitor-backup"
VERSION = 1
KDF_NAME = "pbkdf2-hmac-sha256"
ITERATIONS = 200000
SALT_SIZE = 16


class BackupError(Exception):
    """备份/恢复过程中的可预期错误。"""


def _derive_key(password, salt, iterations):
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=iterations,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))


def create_backup(store, password):
    """生成加密备份文件内容（bytes）。"""
    if not password or len(password) < 4:
        raise BackupError("备份密码不能少于 4 个字符")

    payload = store.export_config()
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    salt = os.urandom(SALT_SIZE)
    token = Fernet(_derive_key(password, salt, ITERATIONS)).encrypt(raw)

    document = {
        "format": FORMAT,
        "version": VERSION,
        "created_at": time_sync.now_iso(),
        "kdf": KDF_NAME,
        "iterations": ITERATIONS,
        "salt": base64.b64encode(salt).decode("ascii"),
        "data": token.decode("ascii"),
    }
    return json.dumps(document, ensure_ascii=False, indent=2).encode("utf-8")


def parse_backup(file_bytes, password):
    """校验并解密备份文件，返回负载字典。"""
    if not password:
        raise BackupError("请输入备份密码")
    try:
        document = json.loads(file_bytes.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise BackupError("备份文件格式无效: {}".format(exc))

    if not isinstance(document, dict) or document.get("format") != FORMAT:
        raise BackupError("不是本程序导出的备份文件")
    if document.get("version") != VERSION:
        raise BackupError("备份文件版本不支持: {}".format(document.get("version")))

    try:
        salt = base64.b64decode(document["salt"])
        iterations = int(document.get("iterations") or ITERATIONS)
        token = document["data"].encode("ascii")
    except (KeyError, ValueError, TypeError) as exc:
        raise BackupError("备份文件损坏: {}".format(exc))

    key = _derive_key(password, salt, iterations)
    try:
        raw = Fernet(key).decrypt(token)
    except InvalidToken:
        raise BackupError("密码错误或备份文件已损坏")

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise BackupError("备份内容解析失败: {}".format(exc))
    if not isinstance(payload, dict):
        raise BackupError("备份内容格式错误")
    return payload


def restore_backup(store, file_bytes, password):
    """解密备份并覆盖当前配置，返回统计信息。"""
    payload = parse_backup(file_bytes, password)
    count = store.import_config(payload)
    return {
        "databases": count,
        "settings": len(payload.get("settings") or {}),
        "created_at": None,
    }
