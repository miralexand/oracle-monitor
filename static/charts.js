(function () {
  "use strict";
  var uid = 0;

  function esc(v) {
    return String(v == null ? "" : v).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  function ring(percent, size, stroke) {
    size = size || 92;
    stroke = stroke || 9;
    var r = (size - stroke) / 2;
    var c = 2 * Math.PI * r;
    var have = percent != null && !isNaN(percent);
    var val = have ? Math.max(0, Math.min(100, percent)) : 0;
    var color = val >= 99 ? "var(--ok)" : val >= 90 ? "var(--accent)" : val >= 70 ? "var(--alert)" : "var(--error)";
    var offset = c * (1 - val / 100);
    return (
      '<svg class="ring" width="' + size + '" height="' + size + '" viewBox="0 0 ' + size + " " + size + '">' +
        '<circle class="ring-bg" cx="' + size / 2 + '" cy="' + size / 2 + '" r="' + r + '" stroke-width="' + stroke + '"/>' +
        '<circle class="ring-fg" cx="' + size / 2 + '" cy="' + size / 2 + '" r="' + r + '" stroke-width="' + stroke + '"' +
          ' stroke="' + color + '" stroke-dasharray="' + c + '" stroke-dashoffset="' + c + '"' +
          ' data-offset="' + offset + '"' +
          ' transform="rotate(-90 ' + size / 2 + " " + size / 2 + ')"/>' +
        '<text class="ring-text" x="50%" y="50%" dominant-baseline="central" text-anchor="middle">' +
          (have ? val + "%" : "--") +
        "</text>" +
      "</svg>"
    );
  }

  function playRings(root) {
    requestAnimationFrame(function () {
      (root || document).querySelectorAll(".ring-fg[data-offset]").forEach(function (el) {
        el.style.strokeDashoffset = el.getAttribute("data-offset");
      });
    });
  }

  function line(points, opts) {
    opts = opts || {};
    var w = opts.width || 560;
    var h = opts.height || 150;
    var pad = { l: 36, r: 10, t: 12, b: 22 };
    var iw = w - pad.l - pad.r;
    var ih = h - pad.t - pad.b;
    var nums = points
      .map(function (p) { return p.value; })
      .filter(function (v) { return v != null && !isNaN(v); });

    if (!nums.length) {
      return (
        '<svg class="line-chart" viewBox="0 0 ' + w + " " + h + '">' +
        '<text class="line-empty" x="' + w / 2 + '" y="' + h / 2 + '" text-anchor="middle">暂无数据</text></svg>'
      );
    }

    var max = Math.max.apply(null, nums);
    var hi = max <= 0 ? 1 : max * 1.25;
    var n = points.length;
    var x = function (i) { return pad.l + (n <= 1 ? iw / 2 : (iw * i / (n - 1))); };
    var y = function (v) { return pad.t + ih - (Math.max(0, v) / hi) * ih; };

    var gid = "lg" + ++uid;
    var svg = '<svg class="line-chart" viewBox="0 0 ' + w + " " + h + '" preserveAspectRatio="none" role="img">';
    svg +=
      '<defs><linearGradient id="' + gid + '" x1="0" y1="0" x2="0" y2="1">' +
      '<stop offset="0%" style="stop-color:var(--accent);stop-opacity:0.35"/>' +
      '<stop offset="100%" style="stop-color:var(--accent);stop-opacity:0"/></linearGradient></defs>';

    [0, 0.5, 1].forEach(function (f) {
      var gy = pad.t + ih * f;
      svg += '<line class="grid-line" x1="' + pad.l + '" y1="' + gy + '" x2="' + (w - pad.r) + '" y2="' + gy + '"/>';
      svg += '<text class="axis-label" x="' + (pad.l - 6) + '" y="' + (gy + 3) + '" text-anchor="end">' +
        Math.round(hi * (1 - f)) + "</text>";
    });

    var segs = [];
    var cur = [];
    points.forEach(function (p, i) {
      if (p.value == null || isNaN(p.value)) {
        if (cur.length) segs.push(cur);
        cur = [];
      } else {
        cur.push([x(i), y(p.value), p.value, p.label, i]);
      }
    });
    if (cur.length) segs.push(cur);

    segs.forEach(function (seg) {
      if (seg.length < 2) return;
      var d = seg
        .map(function (pt, k) { return (k ? "L" : "M") + pt[0].toFixed(1) + " " + pt[1].toFixed(1); })
        .join(" ");
      svg += '<path d="' + d + " L" + seg[seg.length - 1][0].toFixed(1) + " " + (pad.t + ih) +
        " L" + seg[0][0].toFixed(1) + " " + (pad.t + ih) + ' Z" fill="url(#' + gid + ')"/>';
      svg += '<path class="line-path" d="' + d + '"/>';
    });

    points.forEach(function (p, i) {
      if (p.value == null || isNaN(p.value)) return;
      svg += '<circle class="line-dot" cx="' + x(i).toFixed(1) + '" cy="' + y(p.value).toFixed(1) +
        '" r="2.6"><title>' + esc(p.label + ": " + p.value + "ms") + "</title></circle>";
    });

    var step = Math.max(1, Math.ceil(n / 8));
    points.forEach(function (p, i) {
      if (i % step !== 0 && i !== n - 1) return;
      svg += '<text class="axis-label" x="' + x(i).toFixed(1) + '" y="' + (h - 6) +
        '" text-anchor="middle">' + esc(p.label) + "</text>";
    });

    return svg + "</svg>";
  }

  function bars(items) {
    var max = Math.max(1, Math.max.apply(null, items.map(function (i) { return i.value || 0; })));
    return '<div class="bars">' + items.map(function (i) {
      var pct = Math.round(((i.value || 0) / max) * 100);
      return '<div class="bar-item" title="' + esc(i.label + ": " + (i.value || 0)) + '">' +
        '<div class="bar-track"><div class="bar-fill ' + (i.value ? "" : "empty") +
          '" style="height:' + pct + '%"></div></div>' +
        '<div class="bar-label">' + esc(i.label) + "</div></div>";
    }).join("") + "</div>";
  }

  function statusStrip(recent) {
    if (!recent || !recent.length) return '<span class="muted">暂无数据</span>';
    return recent.map(function (r) {
      var ms = r.ms == null ? 0 : r.ms;
      var hgt = Math.max(5, Math.min(26, 5 + ms / 60));
      var title = r.status + " · " + (r.time || "") + " · " + ms + "ms";
      return '<span class="' + esc(r.status) + '" style="height:' + Math.round(hgt) +
        'px" title="' + esc(title) + '"></span>';
    }).join("");
  }

  function countUp(el, target, from) {
    from = from || 0;
    var dur = 650;
    var t0 = performance.now();
    function tick(now) {
      var p = Math.min(1, (now - t0) / dur);
      var e = 1 - Math.pow(1 - p, 3);
      el.textContent = Math.round(from + (target - from) * e);
      if (p < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }

  window.Charts = {
    esc: esc,
    ring: ring,
    playRings: playRings,
    line: line,
    bars: bars,
    statusStrip: statusStrip,
    countUp: countUp,
  };
})();
