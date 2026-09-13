# -*- coding: utf-8 -*-
"""登录认证与用户口令处理。

口令存储：PBKDF2-HMAC-SHA256（随机盐 + 20 万次迭代）。
登录传输：前端先用纯 JS SHA-256 预哈希密码，服务端再对哈希值做 PBKDF2，
          即使通过 HTTP 也不会明文传输原始密码。
"""

import functools
import hashlib
import hmac
import os

from flask import jsonify, redirect, request, session, url_for

PBKDF2_ITERATIONS = 200000
SALT_SIZE = 16

LOGIN_ENDPOINTS = {"login", "static", "health", "favicon"}


def sha256_hex(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def hash_password(secret, salt=None, iterations=PBKDF2_ITERATIONS):
    if salt is None:
        salt = os.urandom(SALT_SIZE)
    elif isinstance(salt, str):
        salt = bytes.fromhex(salt)
    derived = hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), salt, iterations)
    return derived.hex(), salt.hex(), iterations


def verify_password(secret, salt_hex, iterations, expected_hash):
    try:
        salt = bytes.fromhex(salt_hex or "")
        rounds = int(iterations or PBKDF2_ITERATIONS)
    except (ValueError, TypeError):
        return False
    derived = hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), salt, rounds)
    return hmac.compare_digest(derived.hex(), expected_hash or "")


def login_secret(form):
    """优先使用前端 SHA-256 预哈希，否则服务端对明文做 SHA-256。"""
    prehashed = (form.get("password_hash") or "").strip().lower()
    if len(prehashed) == 64:
        return prehashed
    return sha256_hex(form.get("password") or "")


def new_secret(form):
    """新增用户 / 重置密码时使用（同样支持预哈希）。"""
    prehashed = (form.get("password_hash") or "").strip().lower()
    if len(prehashed) == 64:
        return prehashed
    return sha256_hex(form.get("password") or "")


def current_user():
    if not session.get("uid"):
        return None
    return {
        "id": session.get("uid"),
        "username": session.get("username"),
        "role": session.get("role", "viewer"),
    }


def is_admin():
    return session.get("role") == "admin"


def _deny():
    if request.path.startswith("/api/"):
        return jsonify({"error": "unauthorized"}), 401
    return redirect(url_for("login", next=request.path))


def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("uid"):
            return _deny()
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("uid"):
            return _deny()
        if session.get("role") != "admin":
            if request.path.startswith("/api/"):
                return jsonify({"error": "forbidden"}), 403
            return "需要管理员权限", 403
        return view(*args, **kwargs)

    return wrapped
