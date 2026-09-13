(function () {
  "use strict";

  var SUN = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4.5"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M19.1 4.9l-1.4 1.4M6.3 17.7l-1.4 1.4"/></svg>';
  var MOON = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M21 12.8A9 9 0 1111.2 3a7 7 0 009.8 9.8z"/></svg>';

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    try { localStorage.setItem("om-theme", theme); } catch (e) {}
    var btn = document.getElementById("theme-toggle");
    if (btn) {
      btn.innerHTML = theme === "light" ? MOON : SUN;
      btn.title = theme === "light" ? "切换到暗黑主题" : "切换到明亮主题";
    }
  }

  function initTheme() {
    applyTheme(document.documentElement.getAttribute("data-theme") || "dark");
    var btn = document.getElementById("theme-toggle");
    if (btn && !btn.dataset.bound) {
      btn.dataset.bound = "1";
      btn.addEventListener("click", function () {
        var next = document.documentElement.getAttribute("data-theme") === "light" ? "dark" : "light";
        applyTheme(next);
      });
    }
  }

  function bindPasswordHash() {
    // 提交前用 SHA-256 预哈希密码，避免明文传输；缺省时服务端也会兜底处理
    document.querySelectorAll("form.js-hash").forEach(function (form) {
      if (form.dataset.hashBound) return;
      form.dataset.hashBound = "1";
      form.addEventListener("submit", function () {
        var pw = form.querySelector('input[type="password"][data-hash="1"]');
        if (!pw || !pw.value || !window.sha256Hex) return;
        var hidden = form.querySelector('input[name="password_hash"]');
        if (!hidden) {
          hidden = document.createElement("input");
          hidden.type = "hidden";
          hidden.name = "password_hash";
          form.appendChild(hidden);
        }
        hidden.value = window.sha256Hex(pw.value);
        pw.value = "";
      });
    });
  }

  function postJSON(url, data) {
    var body = new FormData();
    Object.keys(data || {}).forEach(function (k) { body.append(k, data[k]); });
    return fetch(url, { method: "POST", body: body }).then(function (r) { return r.json(); });
  }

  function bindButtons() {
    var runNow = document.getElementById("run-now");
    if (runNow) {
      runNow.addEventListener("click", function () {
        var original = runNow.textContent;
        runNow.disabled = true;
        runNow.textContent = "检测中…";
        postJSON("/settings/run-now", {}).finally(function () {
          setTimeout(function () {
            runNow.disabled = false;
            runNow.textContent = original;
          }, 1200);
        });
      });
    }

    var ntp = document.getElementById("ntp-sync");
    if (ntp) {
      ntp.addEventListener("click", function () {
        var out = document.getElementById("ntp-result");
        out.textContent = "校准中…";
        out.className = "test-result";
        postJSON("/settings/ntp-sync", {}).then(function (res) {
          out.textContent = res.message;
          out.className = "test-result " + (res.ok ? "ok" : "error");
        });
      });
    }

    var testMail = document.getElementById("test-mail");
    if (testMail) {
      testMail.addEventListener("click", function () {
        var out = document.getElementById("mail-result");
        out.textContent = "发送中…";
        out.className = "test-result";
        postJSON("/settings/test-mail", {}).then(function (res) {
          out.textContent = res.ok ? (res.message || "成功") : "失败: " + res.message;
          out.className = "test-result " + (res.ok ? "ok" : "error");
        });
      });
    }

    var inline = document.getElementById("test-inline");
    if (inline) {
      inline.addEventListener("click", function () {
        var form = document.getElementById("db-form");
        var out = document.getElementById("test-result");
        var data = {};
        new FormData(form).forEach(function (v, k) { data[k] = v; });
        out.textContent = "测试中…";
        out.className = "test-result";
        postJSON("/databases/test", data).then(function (res) {
          out.textContent = res.ok ? "连接成功" : "失败: " + res.message;
          out.className = "test-result " + (res.ok ? "ok" : "error");
        });
      });
    }

    document.querySelectorAll(".test-db").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var original = btn.textContent;
        btn.disabled = true;
        btn.textContent = "测试中…";
        postJSON("/databases/" + btn.dataset.id + "/test", {})
          .then(function (res) {
            btn.textContent = res.ok ? "成功" : "失败";
            btn.title = res.message;
            if (!res.ok) alert("测试失败:\n" + res.message);
          })
          .finally(function () {
            setTimeout(function () {
              btn.textContent = original;
              btn.disabled = false;
            }, 1500);
          });
      });
    });

    document.querySelectorAll("[data-confirm]").forEach(function (el) {
      el.addEventListener("click", function (e) {
        if (!window.confirm(el.dataset.confirm)) e.preventDefault();
      });
    });
  }

  function bindLogCards() {
    var wrap = document.getElementById("log-cards");
    if (!wrap) return;
    wrap.addEventListener("click", function (e) {
      var card = e.target.closest(".stat-card");
      if (!card) return;
      var level = card.dataset.level || "";
      var params = new URLSearchParams(window.location.search);
      params.delete("levels");
      if (level && !card.classList.contains("active-filter")) {
        params.append("levels", level);
      }
      var qs = params.toString();
      window.location.href = window.location.pathname + (qs ? "?" + qs : "");
    });
  }

  initTheme();

  document.addEventListener("DOMContentLoaded", function () {
    bindPasswordHash();
    bindButtons();
    bindLogCards();
  });
})();
