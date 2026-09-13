(function () {
  "use strict";

  var C = window.Charts;
  var state = { data: null, range: "24h", prevSummary: {}, first: true, signature: null };
  var ICONS = {
    total: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/></svg>',
    ok: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M8 12.5l2.5 2.5L16 9.5"/></svg>',
    alert: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3l9 16H3z"/><path d="M12 9v5"/><path d="M12 17h.01"/></svg>',
    error: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M15 9l-6 6M9 9l6 6"/></svg>',
    active: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 8a6 6 0 10-12 0c0 7-3 8-3 8h18s-3-1-3-8"/><path d="M10.5 20a2 2 0 003 0"/></svg>'
  };

  function statusShort(s) {
    return s === "ok" ? "正常" : s === "alert" ? "告警" : s === "error" ? "失败" : "未知";
  }
  function fmtTime(iso) {
    return (iso || "-").replace("T", " ").replace(/([+-]\d{2}:\d{2}|Z)$/, "");
  }

  function timeAgo(iso) {
    if (!iso) return "-";
    var t = new Date(iso.replace(" ", "T"));
    if (isNaN(t.getTime())) return iso;
    var diff = Math.max(0, (Date.now() - t.getTime()) / 1000);
    if (diff < 60) return "刚刚";
    if (diff < 3600) return Math.floor(diff / 60) + " 分钟前";
    if (diff < 86400) return Math.floor(diff / 3600) + " 小时前";
    return Math.floor(diff / 86400) + " 天前";
  }

  function formatUptime(seconds) {
    if (seconds == null) return "-";
    var d = Math.floor(seconds / 86400);
    var h = Math.floor((seconds % 86400) / 3600);
    var m = Math.floor((seconds % 3600) / 60);
    if (d > 0) return d + " 天 " + h + " 小时";
    if (h > 0) return h + " 小时 " + m + " 分钟";
    return m + " 分钟";
  }
  function setAnim(el, animate) {
    if (!el) return;
    if (animate) el.classList.remove("no-anim");
    else el.classList.add("no-anim");
  }

  function plainSummary(db) {
    var s = db.latest_status;
    var ms = db.latest_duration_ms;
    if (s === "ok") {
      var text = "运行状态良好" + (ms != null ? "，最近一次检测用时 <strong>" + ms + " 毫秒</strong>" : "") + "。";
      if (db.ignored_alerts > 0) {
        text += "（<strong>" + db.ignored_alerts + "</strong> 项告警已忽略）";
      }
      return text;
    }
    if (s === "alert") {
      if (db.active_alerts === 0 && db.ignored_alerts > 0) {
        return "检测到的问题已<strong>全部忽略</strong>，如已处理可恢复监控。";
      }
      return "数据库可以连接，但检测到 <strong>" + db.active_alerts + " 项指标超过阈值</strong>，请查看下方告警。";
    }
    if (s === "error") {
      return "无法连接数据库，请检查网络、监听或账号配置。";
    }
    return "尚无检测数据，等待首次检测…";
  }

  function overallStatus(s) {
    if (!s.total) {
      return { cls: "unknown", title: "尚未配置数据库", desc: "前往「数据库管理」添加需要监控的 Oracle 实例。" };
    }
    if (s.error > 0) {
      return { cls: "error", title: "存在无法连接的数据库", desc: s.error + " 个数据库连接失败，请及时排查网络或账号配置。" };
    }
    if (s.active_alerts > 0) {
      return { cls: "alert", title: "有指标需要关注", desc: "当前有 " + s.active_alerts + " 项活动告警，" + s.alert + " 个数据库处于告警状态。" };
    }
    return {
      cls: "ok",
      title: "系统运行正常",
      desc: "全部 " + s.total + " 个数据库连接正常，24 小时整体可用率 " +
        (s.overall_uptime == null ? "-" : s.overall_uptime + "%") + "。"
    };
  }

  function timeSyncLabel(ts) {
    if (!ts || !ts.enabled) return "时间未校准";
    if (ts.last_error) return "NTP 异常";
    return "NTP 偏移 " + (ts.offset_seconds >= 0 ? "+" : "") + ts.offset_seconds + "s";
  }

  function renderHero(summary, animate, uptimeSeconds, timeSync) {
    var el = document.getElementById("hero");
    if (!el) return;
    setAnim(el, animate);
    var info = overallStatus(summary);
    var ignored = summary.ignored_alerts || 0;
    var tsCls = timeSync && timeSync.enabled && !timeSync.last_error ? "ok" : "muted";
    el.innerHTML =
      '<div class="hero ' + info.cls + ' fade-up">' +
        '<div class="hero-ring">' + C.ring(summary.overall_uptime, 104, 10) + "</div>" +
        '<div class="hero-text"><div class="hero-title">' + info.title + "</div>" +
        '<div class="hero-desc">' + info.desc + "</div>" +
        '<div class="hero-meta">' +
          '<span>服务已运行 <b>' + C.esc(formatUptime(uptimeSeconds)) + "</b></span>" +
          "<span>24h 检测 <b>" + (summary.checks_24h || 0) + "</b> 次</span>" +
          "<span>24h 异常 <b>" + (summary.incidents_24h || 0) + "</b> 次</span>" +
          (ignored ? "<span>已忽略 <b>" + ignored + "</b> 项</span>" : "") +
          '<span class="ts ' + tsCls + '" title="' +
            C.esc((timeSync && timeSync.server) || "") +
            '">' + C.esc(timeSyncLabel(timeSync)) + "</span>" +
          "<span>时区 <b>" + C.esc((timeSync && timeSync.timezone) || "UTC") + "</b></span>" +
        "</div></div>" +
      "</div>";
    C.playRings(el);
  }

  function renderSummary(summary, animate) {
    var el = document.getElementById("summary");
    if (!el) return;
    setAnim(el, animate);
    var cards = [
      { key: "total", label: "数据库总数", value: summary.total, cls: "" },
      { key: "ok", label: "正常运行", value: summary.ok, cls: "ok" },
      { key: "alert", label: "存在告警", value: summary.alert, cls: "alert" },
      { key: "error", label: "连接失败", value: summary.error, cls: "error" },
      { key: "active", label: "活动告警", value: summary.active_alerts, cls: summary.active_alerts ? "alert" : "" }
    ];
    var prev = state.prevSummary;
    el.innerHTML = cards.map(function (c, i) {
      return '<div class="stat-card ' + c.cls + ' fade-up" style="animation-delay:' + i * 60 + 'ms">' +
        '<span class="stat-icon">' + ICONS[c.key] + "</span>" +
        '<div class="num" data-key="' + c.key + '">' + (prev[c.key] == null ? 0 : prev[c.key]) + "</div>" +
        '<div class="label">' + c.label + "</div></div>";
    }).join("");
    cards.forEach(function (c) {
      var num = el.querySelector('[data-key="' + c.key + '"]');
      if (animate) {
        C.countUp(num, c.value, prev[c.key] == null ? 0 : prev[c.key]);
      } else {
        num.textContent = c.value;
      }
      prev[c.key] = c.value;
    });
  }

  function overallItems(data, range) {
    if (range === "7d") {
      var map = {};
      data.forEach(function (db) {
        (db.alert_7d || []).forEach(function (p) { map[p.date] = (map[p.date] || 0) + p.count; });
      });
      return Object.keys(map).map(function (k) { return { label: k, value: map[k] }; });
    }
    var len = data.length && data[0].hourly ? data[0].hourly.length : 24;
    var items = [];
    for (var i = 0; i < len; i++) {
      var value = 0;
      var hour = "";
      data.forEach(function (db) {
        var h = db.hourly[i];
        if (h) { value += h.alert + h.error; }
        if (!hour && h) hour = h.hour;
      });
      items.push({ label: i % 3 === 0 ? hour : "", value: value });
    }
    return items;
  }

  function renderOverall(data, animate) {
    var el = document.getElementById("overall-chart");
    if (!el) return;
    setAnim(el, animate);
    var items = overallItems(data, state.range);
    var any = items.some(function (i) { return i.value > 0; });
    el.innerHTML = C.bars(items) +
      '<p class="muted" style="font-size:12px;margin:10px 0 0">' +
      (state.range === "7d" ? "最近 7 天每天新增告警数量。" : "最近 24 小时每小时的告警与连接失败次数。") +
      (any ? "" : " 当前一切正常，没有异常记录。") + "</p>";
  }

  function renderDatabase(db, index) {
    var status = db.latest_status || "unknown";
    var conn = C.esc(db.host) + ":" + C.esc(db.port) + "/" + C.esc(db.service_name || db.sid || "-");
    var avg = db.avg_duration_ms == null ? "-" : db.avg_duration_ms + "ms";

    var canManage = !!window.IS_ADMIN;
    var alertItems = db.active_alerts_list || [];
    var alerts = alertItems.slice(0, 8).map(function (a) {
      var extra = a.ignored ? " ignored" : (status === "error" ? " error" : "");
      var text = '<span class="alert-text">' + C.esc(a.message) + "</span>";
      if (!canManage) return '<li class="' + extra.trim() + '">' + text + "</li>";
      var action = a.ignored ? "unignore" : "ignore";
      var label = a.ignored ? "取消忽略" : "忽略";
      return '<li class="' + extra.trim() + '">' + text +
        '<button class="alert-ignore btn small" data-db="' + db.id + '" data-key="' +
          C.esc(a.key) + '" data-action="' + action + '">' + label + "</button></li>";
    }).join("");

    var ignoreAll = "";
    if (canManage && alertItems.length > 1) {
      ignoreAll =
        '<div class="alert-actions">' +
        '<button class="alert-ignore btn small" data-db="' + db.id + '" data-key="" data-action="ignore">忽略全部</button>' +
        '<button class="alert-ignore btn small" data-db="' + db.id + '" data-key="" data-action="unignore">全部取消忽略</button>' +
        "</div>";
    }

    return '<article class="db-card ' + C.esc(status) + ' fade-up" style="animation-delay:' + (index * 80) + 'ms">' +
      '<div class="db-head">' +
        "<div><div class=\"db-name\">" + C.esc(db.name) + "</div>" +
        '<div class="db-conn">' + conn + (db.enabled ? "" : " · 已停用") + "</div></div>" +
        '<span class="badge ' + C.esc(status) + '"><i class="dot"></i>' + statusShort(status) + "</span>" +
      "</div>" +
      '<p class="db-summary">' + plainSummary(db) + "</p>" +
      '<div class="db-main">' +
        '<div class="gauge">' + C.ring(db.uptime_24h) + '<div class="gauge-label">24h 可用率</div></div>' +
        '<div class="db-metrics">' +
          "<div>24h 检测次数<b>" + db.checks_24h + "</b></div>" +
          "<div>24h 告警次数<b>" + db.alert_24h + "</b></div>" +
          "<div>活动告警<b>" + db.active_alerts + "</b></div>" +
          "<div>平均检测耗时<b>" + avg + "</b></div>" +
          '<div>最近检测时间<b title="' + C.esc(fmtTime(db.latest_time)) + '">' + C.esc(timeAgo(db.latest_time)) + "</b></div>" +
          "<div>连接地址<b>" + C.esc(db.host) + "</b></div>" +
        "</div>" +
      "</div>" +
      '<div class="chart-block"><div class="block-title"><span>响应时间（24 小时）</span><span>毫秒</span></div>' +
        C.line((db.hourly || []).map(function (h) { return { label: h.hour, value: h.avg_ms }; })) +
      "</div>" +
      '<div class="chart-block"><div class="block-title"><span>最近检测记录</span>' +
        '<span class="legend"><span><i class="ok"></i>正常</span><span><i class="alert"></i>告警</span><span><i class="error"></i>失败</span></span>' +
      "</div>" + C.statusStrip(db.recent) + "</div>" +
      (alerts ? ignoreAll + '<ul class="alert-list">' + alerts + "</ul>" : "") +
    "</article>";
  }

  function renderDatabases(data, animate) {
    var list = document.getElementById("db-list");
    var hint = document.getElementById("empty-hint");
    if (!list) return;
    setAnim(list, animate);
    if (!data.length) {
      list.innerHTML = "";
      if (hint) hint.style.display = "block";
      return;
    }
    if (hint) hint.style.display = "none";
    list.innerHTML = data.map(renderDatabase).join("");
    C.playRings(list);
  }

  function updateMeta(payload) {
    var time = document.getElementById("server-time");
    if (time) {
      time.textContent = "更新于 " + payload.server_time + (payload.scheduler_running ? " · 检测中…" : "");
    }
    var sub = document.getElementById("page-subtitle");
    if (sub) {
      sub.textContent = "共 " + payload.summary.total + " 个数据库，24 小时整体可用率 " +
        (payload.summary.overall_uptime == null ? "-" : payload.summary.overall_uptime + "%") +
        "，累计告警 " + payload.summary.incidents_24h + " 次";
    }
  }

  function loadDashboard() {
    fetch("/api/dashboard")
      .then(function (r) {
        if (r.status === 401) {
          window.location.href = "/login";
          throw new Error("unauthorized");
        }
        return r.json();
      })
      .then(function (payload) {
        updateMeta(payload);
        // 数据未变化时跳过重绘，进一步避免闪烁
        var signature = JSON.stringify(payload.databases) + JSON.stringify(payload.summary);
        if (signature === state.signature) return;
        state.signature = signature;

        var animate = state.first;
        state.first = false;
        state.data = payload.databases || [];
        renderHero(payload.summary, animate, payload.service_uptime_seconds, payload.time_sync);
        renderSummary(payload.summary, animate);
        renderOverall(state.data, animate);
        renderDatabases(state.data, animate);
      })
      .catch(function () {});
  }

  function bind() {
    var refresh = document.getElementById("refresh-btn");
    if (refresh) {
      refresh.addEventListener("click", function () {
        state.first = false; // 手动刷新也不重放入场动画
        state.signature = null;
        loadDashboard();
      });
    }

    var list = document.getElementById("db-list");
    if (list) {
      list.addEventListener("click", function (e) {
        var btn = e.target.closest(".alert-ignore");
        if (!btn) return;
        var body = new FormData();
        body.append("db_id", btn.dataset.db);
        body.append("alert_key", btn.dataset.key);
        body.append("action", btn.dataset.action);
        btn.disabled = true;
        fetch("/alerts/ignore", { method: "POST", body: body })
          .then(function (r) { return r.json(); })
          .then(function () {
            state.signature = null;
            state.first = false;
            loadDashboard();
          })
          .catch(function () { btn.disabled = false; });
      });
    }

    var tabs = document.getElementById("trend-tabs");
    if (tabs) {
      tabs.addEventListener("click", function (e) {
        var btn = e.target.closest(".tab");
        if (!btn) return;
        state.range = btn.dataset.range;
        tabs.querySelectorAll(".tab").forEach(function (t) { t.classList.toggle("active", t === btn); });
        if (state.data) renderOverall(state.data, false);
      });
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (window.PAGE !== "dashboard") return;
    bind();
    loadDashboard();
    setInterval(loadDashboard, 15000);
  });
})();
