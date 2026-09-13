# -*- coding: utf-8 -*-
"""Flask Web 应用：登录、监控面板、日志筛选导出、数据库与设置、用户管理。"""

import logging
import os
import re
import time
from datetime import timedelta

from flask import (
    Flask,
    Response,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

import auth
import logview
import oracle_conn
from backup import BackupError, create_backup, restore_backup
from logger import setup_logging
from scheduler import MonitorScheduler, test_connection
from settings import DEFAULT_SETTINGS, as_bool
from timesync import time_sync

log = logging.getLogger(__name__)

APP_VERSION = "1.2.0"
SERVICE_STARTED = time.time()

EDITABLE_SETTING_KEYS = [
    "interval_minutes",
    "silence_minutes",
    "notify_on_recovery",
    "oracle_use_thick",
    "oracle_client_lib_dir",
    "log_level",
    "log_retention_days",
    "ntp_enabled",
    "ntp_server",
    "ntp_interval_hours",
    "timezone",
    "smtp_server",
    "smtp_port",
    "smtp_encryption",
    "smtp_sender",
    "smtp_password",
    "smtp_receivers",
    "smtp_subject_prefix",
    "tablespace_usage_pct",
    "session_count",
    "long_query_seconds",
    "lock_wait_seconds",
    "archive_usage_pct",
    "rman_backup_interval_hours",
    "alert_log_patterns",
    "enable_m2_instance_status",
    "enable_m3_tablespace",
    "enable_m4_session_count",
    "enable_m5_long_query",
    "enable_m6_lock_wait",
    "enable_m7_archive_space",
    "enable_m8_rman_backup",
    "enable_m9_alert_log",
]

BOOLEAN_FORM_KEYS = {
    "notify_on_recovery",
    "oracle_use_thick",
    "ntp_enabled",
    "enable_m2_instance_status",
    "enable_m3_tablespace",
    "enable_m4_session_count",
    "enable_m5_long_query",
    "enable_m6_lock_wait",
    "enable_m7_archive_space",
    "enable_m8_rman_backup",
    "enable_m9_alert_log",
}


def _base_dir():
    return os.path.dirname(os.path.abspath(__file__))


def _safe_int(value, default):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _format_dt(value):
    """把 ISO 时间显示为 YYYY-MM-DD HH:MM:SS（去掉时区后缀）。"""
    if not value:
        return "-"
    text = str(value).replace("T", " ")
    return re.sub(r"([+-]\d{2}:\d{2}|Z)$", "", text)


def _db_payload(form):
    return {
        "name": (form.get("name") or "").strip(),
        "host": (form.get("host") or "").strip(),
        "port": form.get("port") or 1521,
        "service_name": (form.get("service_name") or "").strip(),
        "sid": (form.get("sid") or "").strip(),
        "username": (form.get("username") or "").strip(),
        "password": form.get("password") or "",
        "connect_timeout": form.get("connect_timeout") or 10,
        "enabled": form.get("enabled") == "on",
    }


def _load_secret_key(data_dir):
    env = os.environ.get("OM_SECRET_KEY")
    if env:
        return env
    path = os.path.join(data_dir, "secret.key")
    if os.path.exists(path):
        try:
            with open(path, "rb") as handle:
                return handle.read()
        except OSError:
            pass
    key = os.urandom(32)
    try:
        with open(path, "wb") as handle:
            handle.write(key)
    except OSError:
        pass
    return key


def _safe_log_name(log_dir, name):
    if not name or name == logview.ALL_FILES:
        return logview.ALL_FILES
    name = os.path.basename(name)
    if os.path.exists(os.path.join(log_dir, name)):
        return name
    return logview.ALL_FILES


def create_app():
    base = _base_dir()
    data_dir = os.environ.get("OM_DATA_DIR", os.path.join(base, "data"))
    os.makedirs(data_dir, exist_ok=True)
    log_dir = os.environ.get("OM_LOG_DIR", os.path.join(base, "logs"))

    from store import Store

    store = Store(os.path.join(data_dir, "monitor.db"))

    settings = store.get_settings()

    time_sync.configure(
        as_bool(settings.get("ntp_enabled"), False),
        settings.get("ntp_server", "pool.ntp.org"),
        settings.get("ntp_interval_hours", "5"),
        settings.get("timezone", "Asia/Shanghai"),
    )
    if time_sync.enabled:
        time_sync.sync_once()  # 启动时自动校准
    service_started_wall = time_sync.now()

    setup_logging(
        log_dir,
        settings.get("log_level", "INFO"),
        _safe_int(settings.get("log_retention_days", "30"), 30),
    )

    app = Flask(
        __name__,
        template_folder=os.path.join(base, "templates"),
        static_folder=os.path.join(base, "static"),
    )
    app.secret_key = _load_secret_key(data_dir)
    app.permanent_session_lifetime = timedelta(days=7)
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.jinja_env.filters["dt"] = _format_dt

    scheduler = MonitorScheduler(store)
    if as_bool(settings.get("oracle_use_thick"), False) and oracle_conn.is_available():
        lib_dir = (settings.get("oracle_client_lib_dir") or "").strip() or None
        try:
            oracle_conn.ensure_thick(lib_dir)
        except Exception as exc:
            log.error("启动时启用 Oracle Thick 模式失败: %s", exc)
    scheduler.start()
    time_sync.start()  # 每 ntp_interval_hours 小时自动校准

    # ---------------------------------------------------------------- guards
    @app.before_request
    def _require_login():
        endpoint = request.endpoint or ""
        if endpoint in auth.LOGIN_ENDPOINTS or request.path.startswith("/static/"):
            return None
        if not session.get("uid"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "unauthorized"}), 401
            return redirect(url_for("login", next=request.path))
        return None

    @app.context_processor
    def _inject_user():
        return {
            "current_user": auth.current_user(),
            "is_admin": auth.is_admin(),
            "app_version": APP_VERSION,
        }

    # ----------------------------------------------------------------- login
    @app.route("/login", methods=["GET", "POST"])
    def login():
        if session.get("uid"):
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            username = (request.form.get("username") or "").strip()
            secret = auth.login_secret(request.form)
            user = store.get_user_by_name(username)
            if user and auth.verify_password(
                secret, user["salt"], user["iterations"], user["password_hash"]
            ):
                session.clear()
                session["uid"] = user["id"]
                session["username"] = user["username"]
                session["role"] = user["role"]
                session.permanent = True
                store.touch_login(user["id"])
                nxt = request.form.get("next") or request.args.get("next")
                if nxt and nxt.startswith("/"):
                    return redirect(nxt)
                return redirect(url_for("dashboard"))
            flash("用户名或密码错误", "error")
        return render_template("login.html", next=request.args.get("next", ""))

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.route("/health")
    def health():
        return jsonify({"status": "ok"})

    # --------------------------------------------------------------- profile
    @app.route("/profile", methods=["GET", "POST"])
    @auth.login_required
    def profile_page():
        if request.method == "POST":
            raw = request.form.get("password") or ""
            pre = request.form.get("password_hash") or ""
            if len(raw) < 4 and len(pre) != 64:
                flash("新密码至少 4 位", "error")
            else:
                store.update_user_password(session["uid"], auth.new_secret(request.form))
                flash("密码已修改", "success")
                return redirect(url_for("profile_page"))
        return render_template("profile.html")

    # ----------------------------------------------------------------- users
    @app.route("/users")
    @auth.admin_required
    def users_page():
        return render_template("users.html", users=store.list_users())

    @app.route("/users/add", methods=["POST"])
    @auth.admin_required
    def users_add():
        username = (request.form.get("username") or "").strip()
        role = request.form.get("role") if request.form.get("role") in ("admin", "viewer") else "viewer"
        raw = request.form.get("password") or ""
        pre = request.form.get("password_hash") or ""
        if not username:
            flash("用户名不能为空", "error")
        elif len(raw) < 4 and len(pre) != 64:
            flash("密码至少 4 位", "error")
        elif store.get_user_by_name(username):
            flash("用户名已存在", "error")
        else:
            store.create_user(username, auth.new_secret(request.form), role)
            flash("用户已创建", "success")
        return redirect(url_for("users_page"))

    @app.route("/users/<int:user_id>/role", methods=["POST"])
    @auth.admin_required
    def users_role(user_id):
        user = store.get_user(user_id)
        if not user:
            abort(404)
        role = request.form.get("role")
        if role not in ("admin", "viewer"):
            abort(400)
        if user["role"] == "admin" and role != "admin" and store.count_admins() <= 1:
            flash("至少保留一个管理员", "error")
        else:
            store.update_user_role(user_id, role)
            flash("角色已更新", "success")
        return redirect(url_for("users_page"))

    @app.route("/users/<int:user_id>/password", methods=["POST"])
    @auth.admin_required
    def users_password(user_id):
        user = store.get_user(user_id)
        if not user:
            abort(404)
        raw = request.form.get("password") or ""
        pre = request.form.get("password_hash") or ""
        if len(raw) < 4 and len(pre) != 64:
            flash("密码至少 4 位", "error")
        else:
            store.update_user_password(user_id, auth.new_secret(request.form))
            flash("密码已重置", "success")
        return redirect(url_for("users_page"))

    @app.route("/users/<int:user_id>/delete", methods=["POST"])
    @auth.admin_required
    def users_delete(user_id):
        user = store.get_user(user_id)
        if not user:
            abort(404)
        if user["id"] == session.get("uid"):
            flash("不能删除当前登录用户", "error")
        elif user["role"] == "admin" and store.count_admins() <= 1:
            flash("至少保留一个管理员", "error")
        else:
            store.delete_user(user_id)
            flash("用户已删除", "success")
        return redirect(url_for("users_page"))

    # ------------------------------------------------------------------ pages
    @app.route("/")
    def dashboard():
        return render_template("dashboard.html")

    @app.route("/databases")
    def databases_page():
        edit_id = request.args.get("edit", type=int)
        editing = store.get_database(edit_id) if edit_id else None
        return render_template(
            "databases.html", databases=store.list_databases(), editing=editing
        )

    @app.route("/settings", methods=["GET", "POST"])
    @auth.admin_required
    def settings_page():
        if request.method == "POST":
            values = {}
            for key in EDITABLE_SETTING_KEYS:
                if key in BOOLEAN_FORM_KEYS:
                    values[key] = "true" if request.form.get(key) == "on" else "false"
                else:
                    value = request.form.get(key)
                    if value is None:
                        continue
                    if key == "smtp_password" and value == "":
                        continue
                    values[key] = value
            store.update_settings(values)
            current = store.get_settings()
            time_sync.configure(
                as_bool(current.get("ntp_enabled"), False),
                current.get("ntp_server", "pool.ntp.org"),
                current.get("ntp_interval_hours", "5"),
                current.get("timezone", "Asia/Shanghai"),
            )
            if time_sync.enabled:
                time_sync.sync_once()
            scheduler.trigger()
            flash("设置已保存", "success")
            return redirect(url_for("settings_page"))
        current = store.get_settings()
        return render_template(
            "settings.html", settings=current, time_sync=time_sync.status()
        )

    # ------------------------------------------------------------------- logs
    def _log_filters():
        levels = request.args.getlist("levels") or list(logview.LEVELS)
        return {
            "levels": [level.upper() for level in levels],
            "db": (request.args.get("db") or "").strip(),
            "keyword": (request.args.get("q") or "").strip(),
        }

    @app.route("/logs")
    def logs_page():
        files = logview.available_files(log_dir)
        selected = _safe_log_name(log_dir, request.args.get("file") or "")
        filters = _log_filters()
        entries = logview.collect_entries(log_dir, selected) if (files or selected == logview.ALL_FILES) else []
        counts = logview.level_counts(entries)
        filtered = logview.filter_entries(entries, **filters)
        databases = [db["name"] for db in store.list_databases()]
        return render_template(
            "logs.html",
            files=files,
            selected=selected,
            filters=filters,
            counts=counts,
            total=len(filtered),
            entries=filtered[-1000:],
            databases=databases,
            all_files=logview.ALL_FILES,
            all_levels=logview.LEVELS,
        )

    @app.route("/logs/export")
    def logs_export():
        selected = _safe_log_name(log_dir, request.args.get("file") or "")
        filters = _log_filters()
        entries = logview.filter_entries(
            logview.collect_entries(log_dir, selected), **filters
        )
        text = logview.to_text(entries) or "没有符合筛选条件的日志"
        filename = "oracle-monitor-logs-{}.txt".format(
            time_sync.now().strftime("%Y%m%d-%H%M%S")
        )
        return Response(
            text.encode("utf-8"),
            mimetype="text/plain; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename={}".format(filename)},
        )

    # ------------------------------------------------------------- db actions
    @app.route("/databases/add", methods=["POST"])
    @auth.admin_required
    def database_add():
        payload = _db_payload(request.form)
        if not payload["name"] or not payload["host"] or not payload["username"]:
            flash("名称、主机、用户名不能为空", "error")
        elif not payload["service_name"] and not payload["sid"]:
            flash("必须填写 service_name 或 sid", "error")
        else:
            store.add_database(payload)
            scheduler.trigger()
            flash("数据库已添加", "success")
        return redirect(url_for("databases_page"))

    @app.route("/databases/<int:db_id>/edit", methods=["POST"])
    @auth.admin_required
    def database_edit(db_id):
        existing = store.get_database(db_id)
        if not existing:
            abort(404)
        payload = _db_payload(request.form)
        if not payload["password"]:
            payload["password"] = existing["password"]
        if not payload["name"] or not payload["host"] or not payload["username"]:
            flash("名称、主机、用户名不能为空", "error")
        else:
            store.update_database(db_id, payload)
            scheduler.trigger()
            flash("数据库已更新", "success")
        return redirect(url_for("databases_page"))

    @app.route("/databases/<int:db_id>/delete", methods=["POST"])
    @auth.admin_required
    def database_delete(db_id):
        store.delete_database(db_id)
        flash("数据库已删除", "success")
        return redirect(url_for("databases_page"))

    @app.route("/databases/<int:db_id>/toggle", methods=["POST"])
    @auth.admin_required
    def database_toggle(db_id):
        db = store.get_database(db_id)
        if not db:
            abort(404)
        store.set_enabled(db_id, not bool(db["enabled"]))
        scheduler.trigger()
        return redirect(url_for("databases_page"))

    @app.route("/databases/<int:db_id>/test", methods=["POST"])
    @auth.login_required
    def database_test(db_id):
        db = store.get_database(db_id)
        if not db:
            abort(404)
        ok, message = _run_test(db)
        return jsonify({"ok": ok, "message": message})

    @app.route("/databases/test", methods=["POST"])
    @auth.admin_required
    def database_test_inline():
        payload = _db_payload(request.form)
        if not payload["service_name"] and not payload["sid"]:
            return jsonify({"ok": False, "message": "必须填写 service_name 或 sid"})
        ok, message = _run_test(payload)
        return jsonify({"ok": ok, "message": message})

    @app.route("/settings/test-mail", methods=["POST"])
    @auth.admin_required
    def settings_test_mail():
        from mailer import Mailer
        from settings import build_config

        config = build_config(store.get_settings())
        try:
            mailer = Mailer(config)
            mailer.send(
                "测试邮件",
                "这是一封测试邮件，收到说明 SMTP 配置正确。\n发送时间: {}".format(
                    time_sync.now().strftime("%Y-%m-%d %H:%M:%S")
                ),
            )
            return jsonify({"ok": True, "message": "测试邮件已发送至 " + ", ".join(mailer.receivers)})
        except Exception as exc:
            return jsonify({"ok": False, "message": str(exc)})

    @app.route("/settings/run-now", methods=["POST"])
    @auth.login_required
    def settings_run_now():
        scheduler.trigger()
        return jsonify({"ok": True, "message": "已触发，请稍后刷新面板"})

    @app.route("/settings/ntp-sync", methods=["POST"])
    @auth.admin_required
    def settings_ntp_sync():
        if not time_sync.enabled:
            return jsonify({"ok": False, "message": "请先勾选启用 NTP 并保存设置"})
        ok, error = time_sync.sync_once()
        status = time_sync.status()
        if ok:
            return jsonify(
                {
                    "ok": True,
                    "message": "校准成功，时钟偏移 {:.3f} 秒".format(status["offset_seconds"]),
                    "status": status,
                }
            )
        return jsonify({"ok": False, "message": "校准失败: " + (error or ""), "status": status})

    # ----------------------------------------------------------------- backup
    @app.route("/backup")
    @auth.admin_required
    def backup_page():
        databases = store.list_databases()
        return render_template("backup.html", databases=databases)

    @app.route("/backup/download", methods=["POST"])
    @auth.admin_required
    def backup_download():
        password = request.form.get("password") or ""
        try:
            data = create_backup(store, password)
        except BackupError as exc:
            flash("备份失败: {}".format(exc), "error")
            return redirect(url_for("backup_page"))
        filename = "oracle-monitor-backup-{}.json.enc".format(
            time_sync.now().strftime("%Y%m%d-%H%M%S")
        )
        return Response(
            data,
            mimetype="application/octet-stream",
            headers={"Content-Disposition": "attachment; filename={}".format(filename)},
        )

    @app.route("/backup/restore", methods=["POST"])
    @auth.admin_required
    def backup_restore():
        upload = request.files.get("file")
        password = request.form.get("password") or ""
        if not upload or not upload.filename:
            flash("请选择备份文件", "error")
            return redirect(url_for("backup_page"))
        if request.form.get("confirm") != "on":
            flash("请勾选确认以覆盖当前配置", "error")
            return redirect(url_for("backup_page"))
        try:
            stats = restore_backup(store, upload.read(), password)
        except BackupError as exc:
            flash("恢复失败: {}".format(exc), "error")
            return redirect(url_for("backup_page"))
        scheduler.trigger()
        flash(
            "恢复成功：{} 个数据库，{} 项设置已导入".format(
                stats["databases"], stats["settings"]
            ),
            "success",
        )
        return redirect(url_for("dashboard"))

    # ----------------------------------------------------------------- alerts
    @app.route("/alerts/ignore", methods=["POST"])
    @auth.admin_required
    def alerts_ignore():
        db_id = request.form.get("db_id", type=int)
        alert_key = request.form.get("alert_key") or ""
        action = request.form.get("action") or "ignore"
        if not db_id or not store.get_database(db_id):
            return jsonify({"ok": False, "message": "数据库不存在"}), 404
        ignored = action != "unignore"
        count = store.set_alert_ignored(db_id, alert_key, ignored)
        message = "已{} {} 条告警".format("忽略" if ignored else "取消忽略", count)
        return jsonify({"ok": True, "message": message, "count": count})

    # -------------------------------------------------------------------- api
    @app.route("/api/dashboard")
    @auth.login_required
    def api_dashboard():
        databases = store.dashboard()
        uptime = int(time.time() - SERVICE_STARTED)
        return jsonify(
            {
                "summary": store.summary(databases),
                "databases": databases,
                "scheduler_running": scheduler.is_running(),
                "server_time": time_sync.now().strftime("%Y-%m-%d %H:%M:%S"),
                "service_uptime_seconds": uptime,
                "service_started_at": service_started_wall.strftime("%Y-%m-%d %H:%M:%S"),
                "version": APP_VERSION,
                "time_sync": time_sync.status(),
            }
        )

    @app.route("/api/logs")
    @auth.login_required
    def api_logs():
        return jsonify(logview.available_files(log_dir))

    def _run_test(db):
        current = store.get_settings()
        use_thick = as_bool(current.get("oracle_use_thick"), False)
        lib_dir = (current.get("oracle_client_lib_dir") or "").strip() or None
        return test_connection(db, use_thick, lib_dir)

    return app
