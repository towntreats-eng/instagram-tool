/* =============================================================================
   ConverFlow — Admin Console
   ========================================================================== */
(function () {
  "use strict";

  var STATE = { overview: null, users: [], search: "", plan: "all", status: "all", level: "all", current: null };

  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };

  // ------------------------------------------------------------------ utils
  function inr(n) {
    n = Number(n || 0);
    return "₹" + n.toLocaleString("en-IN");
  }
  function num(n) { return Number(n || 0).toLocaleString("en-IN"); }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function initials(name) {
    return String(name || "?").trim().split(/\s+/).slice(0, 2).map(function (w) { return w[0]; }).join("").toUpperCase();
  }
  var AV = ["#00824b", "#0084ff", "#7c5cff", "#e5484d", "#b45309", "#0d9488", "#db2777", "#4f46e5"];
  function avatarColor(seed) {
    var h = 0, s = String(seed || "");
    for (var i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
    return AV[h % AV.length];
  }
  function ago(iso) {
    if (!iso) return "—";
    var d = new Date(iso.replace(" ", "T"));
    if (isNaN(d)) return "—";
    var mins = Math.floor((Date.now() - d.getTime()) / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return mins + "m ago";
    var h = Math.floor(mins / 60);
    if (h < 24) return h + "h ago";
    var days = Math.floor(h / 24);
    if (days < 30) return days + "d ago";
    return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
  }
  function shortDate(iso) {
    if (!iso) return "—";
    var d = new Date(String(iso).replace(" ", "T"));
    return isNaN(d) ? "—" : d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "2-digit" });
  }
  function dateStr(iso) {
    if (!iso) return "—";
    var d = new Date(String(iso).replace(" ", "T"));
    return isNaN(d) ? "—" : d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
  }
  var toastTimer;
  function toast(msg, isErr) {
    var t = $("#toast");
    t.textContent = msg;
    t.className = "toast show" + (isErr ? " err" : "");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { t.className = "toast"; }, 2600); 
  }
  async function api(url, opts) {
    var res = await fetch(url, Object.assign({ headers: { "Content-Type": "application/json" } }, opts || {}));
    if (!res.ok) throw new Error("HTTP " + res.status);
    return res.json();
  }

  // ----------------------------------------------------------------- charts
  var NS = "http://www.w3.org/2000/svg";
  function el(tag, attrs, text) {
    var n = document.createElementNS(NS, tag);
    Object.keys(attrs || {}).forEach(function (k) { n.setAttribute(k, attrs[k]); });
    if (text != null) n.textContent = text;
    return n;
  }

  function barChart(svg, rows, opts) {
    opts = opts || {};
    if (!svg) return;
    svg.innerHTML = "";
    var W = svg.clientWidth || svg.parentNode.clientWidth || 640;
    var H = svg.clientHeight || 232;
    var padL = 46, padR = 10, padT = 22, padB = 30;
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);
    var key = opts.key || "revenue";
    var max = Math.max.apply(null, rows.map(function (r) { return r[key]; }).concat([1]));
    var rawStep = max / 4;
    var mag = Math.pow(10, Math.floor(Math.log(rawStep) / Math.LN10));
    var norm = rawStep / mag;
    var step = (norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 5 ? 5 : 10) * mag;
    var niceMax = step * 4;
    var plotW = W - padL - padR, plotH = H - padT - padB;

    // gridlines + y labels
    for (var g = 0; g <= 4; g++) {
      var y = padT + plotH - (plotH * g / 4);
      svg.appendChild(el("line", { x1: padL, y1: y, x2: W - padR, y2: y, class: "grid-line" }));
      var v = Math.round(niceMax * g / 4);
      svg.appendChild(el("text", { x: padL - 8, y: y + 4, "text-anchor": "end" },
        opts.money ? (v >= 1000 ? (v / 1000) + "k" : String(v)) : String(v)));
    }

    var slot = plotW / rows.length;
    var bw = Math.min(46, slot * 0.54);
    rows.forEach(function (r, i) {
      var val = r[key] || 0;
      var h = Math.max(val > 0 ? 3 : 0, plotH * (val / niceMax));
      var x = padL + slot * i + (slot - bw) / 2;
      var y = padT + plotH - h;
      var rect = el("rect", {
        x: x, y: y, width: bw, height: h, rx: 5, class: "bar",
        fill: opts.color || "url(#gGreen)"
      });
      rect.appendChild(el("title", {}, r.label + ": " + (opts.money ? inr(val) : val)));
      svg.appendChild(rect);
      if (val > 0) {
        svg.appendChild(el("text", { x: x + bw / 2, y: y - 7, "text-anchor": "middle", class: "val" },
          opts.money ? (val >= 1000 ? (val / 1000).toFixed(1) + "k" : String(val)) : String(val)));
      }
      svg.appendChild(el("text", { x: x + bw / 2, y: H - 9, "text-anchor": "middle" }, r.label));
    });

    // gradient def
    var defs = el("defs", {});
    var lg = el("linearGradient", { id: "gGreen", x1: "0", y1: "0", x2: "0", y2: "1" });
    lg.appendChild(el("stop", { offset: "0%", "stop-color": "#12b981" }));
    lg.appendChild(el("stop", { offset: "100%", "stop-color": "#00824b" }));
    var lb = el("linearGradient", { id: "gBlue", x1: "0", y1: "0", x2: "0", y2: "1" });
    lb.appendChild(el("stop", { offset: "0%", "stop-color": "#4dabff" }));
    lb.appendChild(el("stop", { offset: "100%", "stop-color": "#0084ff" }));
    defs.appendChild(lg); defs.appendChild(lb);
    svg.insertBefore(defs, svg.firstChild);
  }

  function donut(svg, legendEl, slices) {
    svg.innerHTML = "";
    var total = slices.reduce(function (a, s) { return a + s.value; }, 0) || 1;
    var cx = 75, cy = 75, r = 58, sw = 21, circ = 2 * Math.PI * r, offset = 0;
    svg.appendChild(el("circle", { cx: cx, cy: cy, r: r, fill: "none", stroke: "#f2f4f7", "stroke-width": sw }));
    slices.forEach(function (s) {
      if (!s.value) return;
      var len = circ * (s.value / total);
      var c = el("circle", {
        cx: cx, cy: cy, r: r, fill: "none", stroke: s.color, "stroke-width": sw,
        "stroke-dasharray": len + " " + (circ - len),
        "stroke-dashoffset": -offset,
        transform: "rotate(-90 " + cx + " " + cy + ")",
        "stroke-linecap": "butt"
      });
      c.appendChild(el("title", {}, s.label + ": " + s.value));
      svg.appendChild(c);
      offset += len;
    });
    svg.appendChild(el("text", { x: cx, y: cy - 2, "text-anchor": "middle",
      style: "font-size:24px;font-weight:800;fill:#0b0f14;letter-spacing:-.03em" }, String(total)));
    svg.appendChild(el("text", { x: cx, y: cy + 16, "text-anchor": "middle",
      style: "font-size:11px;font-weight:700;fill:#8b95a3" }, "workspaces"));

    if (legendEl) {
      legendEl.innerHTML = slices.map(function (s) {
        var pct = total ? Math.round(s.value / total * 100) : 0;
        return '<div class="leg"><i style="background:' + s.color + '"></i><span>' + esc(s.label) +
          '</span><b>' + s.value + ' · ' + pct + '%</b></div>';
      }).join("");
    }
  }

  // ------------------------------------------------------------------- kpis
  function kpi(icon, cls, label, value, meta) {
    return '<div class="kpi"><div class="kpi-top"><div class="kpi-icon ' + cls + '">' + icon +
      '</div><div class="kpi-label">' + label + '</div></div><div class="kpi-value">' + value +
      '</div><div class="kpi-meta">' + (meta || "") + '</div></div>';
  }
  var ICO = {
    users: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/></svg>',
    money: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M12 1v22"/><path d="M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"/></svg>',
    bolt: '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>',
    clock: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
    chart: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M3 20h18M7 20V10M12 20V4M17 20v-7"/></svg>',
    chat: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg>',
    pulse: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>',
    alert: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M12 9v4M12 17h.01"/><path d="M10.3 3.9L1.8 18a2 2 0 001.7 3h17a2 2 0 001.7-3L13.7 3.9a2 2 0 00-3.4 0z"/></svg>'
  };

  // --------------------------------------------------------------- overview
  function renderOverview() {
    var d = STATE.overview;
    if (!d) return;
    var m = d.metrics;

    $("#navUserCount").textContent = m.total_users;

    $("#kpiRow").innerHTML =
      kpi(ICO.money, "i-green", "MRR", inr(m.mrr), "<span class='up'>" + m.pro_users + " Pro</span> × " + inr(m.price_monthly)) +
      kpi(ICO.chart, "i-violet", "Revenue", inr(m.total_revenue), "ARR run-rate " + inr(m.arr)) +
      kpi(ICO.users, "i-blue", "Workspaces", num(m.total_users), m.active_7d + " active in last 7 days") +
      kpi(ICO.bolt, "i-amber", "Trial → Pro", m.conversion_rate + "%", m.trial_users + " on trial, " + m.expired_users + " expired") +
      kpi(ICO.chat, "i-coral", "DMs sent", num(m.total_dms), m.total_dms_failed + " failed across platform") +
      kpi(ICO.pulse, "i-ink", "Automations", num(m.total_automations), num(m.total_contacts) + " contacts captured");

    barChart($("#chartRevenue"), d.revenue_series, { key: "revenue", money: true });
    barChart($("#chartSignups"), d.revenue_series, { key: "signups", color: "url(#gBlue)" });

    var series = d.revenue_series;
    var last = series[series.length - 1] || { revenue: 0 };
    var prev = series[series.length - 2] || { revenue: 0 };
    var delta = prev.revenue ? Math.round((last.revenue - prev.revenue) / prev.revenue * 100) : (last.revenue ? 100 : 0);
    var trend = $("#revTrend");
    trend.textContent = (delta >= 0 ? "▲ " : "▼ ") + Math.abs(delta) + "% vs last month";
    trend.className = "badge " + (delta >= 0 ? "badge-pro" : "badge-suspended");

    donut($("#chartDonut"), $("#donutLegend"), [
      { label: "Pro", value: m.pro_users, color: "#00824b" },
      { label: "Free trial", value: m.trial_users, color: "#0084ff" },
      { label: "Expired", value: m.expired_users, color: "#cbd3db" }
    ]);

    $("#recentPayments").innerHTML = (d.recent_payments || []).slice(0, 6).map(function (p) {
      return '<tr><td><div class="u-cell"><div class="avatar" style="background:' + avatarColor(p.email) +
        '">' + esc(initials(p.user_name)) + '</div><div><b>' + esc(p.user_name) + '</b><span>' +
        dateStr(p.date) + '</span></div></div></td><td style="text-align:right"><b class="num">' + inr(p.amount) +
        '</b><br><span class="badge badge-paid">' + esc(p.status) + '</span></td></tr>';
    }).join("") || '<tr><td class="muted" style="padding:24px">No payments recorded yet.</td></tr>';

    $("#recentUsers").innerHTML = (d.recent_users || []).map(function (u) {
      return '<tr data-id="' + u.id + '" class="u-row"><td>' + userCell(u) + '</td><td>' + planBadge(u) +
        '</td><td class="num">' + num(u.stats.contacts) + '</td><td class="num">' + num(u.stats.dms_sent) +
        '</td><td class="muted">' + dateStr(u.created_at) + '</td></tr>';
    }).join("");

    var h = d.health;
    var pill = $("#healthPill");
    pill.className = "pill " + h.state;
    pill.innerHTML = '<span class="dot"></span> ' + esc(h.label);
  }

  function userCell(u) {
    return '<div class="u-cell"><div class="avatar" style="background:' + avatarColor(u.email) + '">' +
      esc(initials(u.name)) + '</div><div><b>' + esc(u.name) + '</b><span>' +
      esc(u.business || u.email) + (u.ig_handle ? ' · @' + esc(u.ig_handle) : '') + '</span></div></div>';
  }
  function planBadge(u) {
    var p = u.plan_state;
    var cls = p.plan === "pro" ? "badge-pro" : p.plan === "trial" ? "badge-trial" : "badge-expired";
    return '<span class="badge ' + cls + '">' + esc(p.badge) + '</span>';
  }

  // ------------------------------------------------------------------ users
  async function loadUsers() {
    var q = new URLSearchParams({ search: STATE.search, plan: STATE.plan, status: STATE.status });
    var out = await api("/api/admin/users?" + q.toString());
    STATE.users = out.users || [];
    renderUsers();
  }

  function renderUsers() {
    var body = $("#usersBody");
    if (!STATE.users.length) {
      body.innerHTML = '<tr><td colspan="8"><div class="empty">' +
        '<svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>' +
        '<b>No workspaces match</b><p>Try a different search or clear the filters.</p></div></td></tr>';
      return;
    }
    body.innerHTML = STATE.users.map(function (u) {
      var statusBadge = u.status === "suspended"
        ? '<span class="badge badge-suspended">Suspended</span>'
        : '<span class="badge badge-paid">Active</span>';
      var sub = u.plan_state.plan === "trial"
        ? '<span class="muted">' + u.plan_state.days_left + 'd left</span>'
        : u.plan_state.plan === "pro"
          ? '<span class="muted" style="white-space:nowrap">renews ' + shortDate(u.plan_state.renews_on) + '</span>'
          : '<span class="muted">—</span>';
      return '<tr data-id="' + u.id + '" class="u-row">' +
        '<td>' + userCell(u) + '</td>' +
        '<td>' + planBadge(u) + '<br>' + sub + '</td>' +
        '<td>' + statusBadge + '</td>' +
        '<td class="num">' + num(u.stats.contacts) + '</td>' +
        '<td class="num">' + num(u.stats.dms_sent) + '</td>' +
        '<td class="num">' + inr(u.revenue) + '</td>' +
        '<td class="muted">' + ago(u.stats.last_active) + '</td>' +
        '<td style="text-align:right;white-space:nowrap">' +
          (u.plan_state.plan === "pro"
            ? '<button class="btn btn-line btn-xs" data-act="downgrade" data-id="' + u.id + '">Downgrade</button>'
            : '<button class="btn btn-green btn-xs" data-act="pro" data-id="' + u.id + '">Make Pro</button>') +
          ' <button class="btn btn-line btn-xs" data-act="open" data-id="' + u.id + '">Manage</button>' +
        '</td></tr>';
    }).join("");
  }

  // ----------------------------------------------------------------- drawer
  function openDrawer() { $("#drawer").classList.add("show"); $("#scrim").classList.add("show"); }
  function closeDrawer() { $("#drawer").classList.remove("show"); $("#scrim").classList.remove("show"); STATE.current = null; }

  async function showUser(id) {
    var out = await api("/api/admin/users/" + id);
    var u = out.user;
    STATE.current = u;
    $("#drawerTitle").textContent = u.name;
    var p = u.plan_state;
    $("#drawerBody").innerHTML =
      '<div class="u-cell" style="margin-bottom:20px"><div class="avatar" style="width:50px;height:50px;font-size:17px;background:' +
      avatarColor(u.email) + '">' + esc(initials(u.name)) + '</div><div><b style="font-size:16px">' + esc(u.name) +
      '</b><span style="font-size:12.5px">' + esc(u.email) + '</span></div></div>' +
      '<div style="display:flex;gap:8px;margin-bottom:20px">' + planBadge(u) +
      (u.status === "suspended" ? '<span class="badge badge-suspended">Suspended</span>' : '<span class="badge badge-paid">Active</span>') +
      '</div>' +
      '<dl class="dl">' +
        '<dt>Brand</dt><dd>' + esc(u.business || "—") + '</dd>' +
        '<dt>Instagram</dt><dd>' + (u.ig_handle ? "@" + esc(u.ig_handle) : "—") + '</dd>' +
        '<dt>Plan</dt><dd>' + esc(p.label) + '</dd>' +
        (p.plan === "pro" ? '<dt>Renews on</dt><dd>' + dateStr(p.renews_on) + '</dd>'
                          : '<dt>Trial ends</dt><dd>' + dateStr(p.trial_expiry) + '</dd>') +
        '<dt>Joined</dt><dd>' + dateStr(u.created_at) + '</dd>' +
        '<dt>Last active</dt><dd>' + ago(u.stats.last_active) + '</dd>' +
        '<dt>Lifetime value</dt><dd><b>' + inr(u.revenue) + '</b></dd>' +
      '</dl>' +
      '<div style="height:1px;background:var(--line);margin:20px 0"></div>' +
      '<div class="kpis" style="grid-template-columns:1fr 1fr;gap:10px;margin:0">' +
        kpi(ICO.users, "i-blue", "Contacts", num(u.stats.contacts), "") +
        kpi(ICO.chat, "i-green", "DMs sent", num(u.stats.dms_sent), u.stats.dms_failed + " failed") +
        kpi(ICO.bolt, "i-amber", "Automations", num(u.stats.automations), u.stats.active_automations + " active") +
        kpi(ICO.money, "i-violet", "Payments", String((u.payments || []).length), "recorded") +
      '</div>' +
      ((u.payments || []).length
        ? '<div style="margin-top:20px"><div class="kpi-label" style="margin-bottom:10px">Payment history</div>' +
          u.payments.slice().reverse().map(function (pay) {
            return '<div class="evt"><div class="evt-body"><p><b>' + inr(pay.amount) + '</b> · ' + esc(pay.method) +
              '</p><span>' + dateStr(pay.date) + ' · ' + esc(pay.id) + '</span></div><span class="badge badge-paid">' +
              esc(pay.status) + '</span></div>';
          }).join("") + '</div>'
        : '');

    $("#drawerFoot").innerHTML =
      (p.plan === "pro"
        ? '<button class="btn btn-line" data-act="downgrade" data-id="' + u.id + '">Move to trial</button>'
        : '<button class="btn btn-green" data-act="pro" data-id="' + u.id + '">Upgrade to Pro</button>') +
      '<button class="btn btn-line" data-act="extend" data-id="' + u.id + '">+7 trial days</button>' +
      '<button class="btn btn-line" data-act="toggle" data-id="' + u.id + '">' +
        (u.status === "suspended" ? "Reactivate" : "Suspend") + '</button>' +
      '<button class="btn btn-danger" data-act="delete" data-id="' + u.id + '">Delete</button>';
    openDrawer();
  }

  function showAddUser() {
    STATE.current = null;
    $("#drawerTitle").textContent = "Add workspace";
    $("#drawerBody").innerHTML =
      '<form id="newUserForm">' +
      '<div class="field"><label>Owner name</label><input class="input" name="name" required placeholder="Riya Mehta"></div>' +
      '<div class="field"><label>Email</label><input class="input" name="email" type="email" required placeholder="riya@glowcart.in"></div>' +
      '<div class="field-row">' +
        '<div class="field"><label>Brand</label><input class="input" name="business" placeholder="GlowCart"></div>' +
        '<div class="field"><label>Instagram</label><input class="input" name="ig_handle" placeholder="glowcart.in"></div>' +
      '</div>' +
      '<div class="field"><label>Temporary password</label><input class="input" name="password" required minlength="6" value="converflow123"></div>' +
      '<div class="field"><label>Starting plan</label><select class="select" name="plan"><option value="trial">15-day free trial</option><option value="pro">Pro — ₹299/mo</option></select></div>' +
      '</form>';
    $("#drawerFoot").innerHTML = '<button class="btn btn-green" data-act="create">Create workspace</button>' +
      '<button class="btn btn-line" data-act="cancel">Cancel</button>';
    openDrawer();
  }

  async function act(action, id) {
    try {
      if (action === "pro") { await api("/api/admin/users/" + id + "/plan", { method: "POST", body: JSON.stringify({ plan: "pro" }) }); toast("Upgraded to Pro"); }
      else if (action === "downgrade") { await api("/api/admin/users/" + id + "/plan", { method: "POST", body: JSON.stringify({ plan: "trial" }) }); toast("Moved back to trial"); }
      else if (action === "extend") { await api("/api/admin/users/" + id + "/extend", { method: "POST", body: JSON.stringify({ days: 7 }) }); toast("Trial extended by 7 days"); }
      else if (action === "toggle") { var r = await api("/api/admin/users/" + id + "/toggle", { method: "POST" }); toast(r.user.status === "suspended" ? "Workspace suspended" : "Workspace reactivated"); }
      else if (action === "delete") {
        if (!window.confirm("Delete this workspace permanently? This cannot be undone.")) return;
        await api("/api/admin/users/" + id, { method: "DELETE" });
        toast("Workspace deleted");
        closeDrawer();
      } else if (action === "create") {
        var form = $("#newUserForm");
        if (!form.reportValidity()) return;
        var payload = Object.fromEntries(new FormData(form).entries());
        var out = await api("/api/admin/users", { method: "POST", body: JSON.stringify(payload) });
        if (!out.success) { toast(out.error || "Could not create", true); return; }
        toast("Workspace created");
        closeDrawer();
      } else if (action === "cancel") { closeDrawer(); return; }

      await refresh();
      if (STATE.current && action !== "delete") await showUser(STATE.current.id);
    } catch (e) {
      toast("Action failed — is the server running?", true);
    }
  }

  // ---------------------------------------------------------------- revenue
  function renderRevenue() {
    var d = STATE.overview;
    if (!d) return;
    var m = d.metrics;
    $("#revKpis").innerHTML =
      kpi(ICO.money, "i-green", "MRR", inr(m.mrr), "from " + m.pro_users + " Pro workspaces") +
      kpi(ICO.chart, "i-violet", "ARR run-rate", inr(m.arr), "at current MRR") +
      kpi(ICO.bolt, "i-blue", "Lifetime revenue", inr(m.total_revenue), "all payments recorded") +
      kpi(ICO.users, "i-amber", "ARPU", inr(m.arpu), "average per workspace");
    barChart($("#chartRevenueBig"), d.revenue_series, { key: "revenue", money: true });

    $("#ledgerBody").innerHTML = (d.recent_payments || []).map(function (p) {
      return '<tr><td><code style="font-family:var(--mono);font-size:12px">' + esc(p.id) + '</code></td>' +
        '<td><b>' + esc(p.user_name) + '</b><br><span class="muted">' + esc(p.email) + '</span></td>' +
        '<td class="num">' + inr(p.amount) + '</td><td class="muted">' + esc(p.method) + '</td>' +
        '<td><span class="badge badge-paid">' + esc(p.status) + '</span></td>' +
        '<td class="muted">' + dateStr(p.date) + '</td></tr>';
    }).join("") || '<tr><td colspan="6"><div class="empty"><b>No payments yet</b><p>Upgrade a workspace to record the first one.</p></div></td></tr>';
  }

  // ----------------------------------------------------------------- health
  async function loadEvents() {
    var out = await api("/api/admin/events?level=" + encodeURIComponent(STATE.level));
    var h = STATE.overview ? STATE.overview.health : out.health;
    $("#healthKpis").innerHTML =
      kpi(ICO.pulse, h.state === "healthy" ? "i-green" : h.state === "degraded" ? "i-amber" : "i-coral",
          "Status", h.state.charAt(0).toUpperCase() + h.state.slice(1), esc(h.label) + " · error rate " + h.error_rate + "%") +
      kpi(ICO.chat, "i-blue", "Events logged", num(h.events_total), "last " + num(h.events_total) + " platform events") +
      kpi(ICO.alert, "i-amber", "Warnings", num(h.counts.WARN || 0), "needs a look") +
      kpi(ICO.alert, "i-coral", "Errors", num(h.counts.ERROR || 0), "blocking issues");

    $("#eventList").innerHTML = (out.events || []).map(function (e) {
      return '<div class="evt"><span class="lvl lvl-' + esc(e.level) + '">' + esc(e.level) + '</span>' +
        '<div class="evt-body"><p>' + esc(e.message) + '</p><span>' + ago(e.created_at) + '</span></div>' +
        '<span class="evt-src">' + esc(e.source) + '</span></div>';
    }).join("") || '<div class="empty"><b>Nothing logged</b><p>Platform events will appear here as automations run.</p></div>';
  }

  // ---------------------------------------------------------- announcements
  async function loadAnnouncements() {
    var out = await api("/api/admin/announcements");
    $("#annList").innerHTML = (out.announcements || []).map(function (a) {
      return '<div class="ann"><div class="ann-top"><b>' + esc(a.title) + '</b>' +
        '<span class="badge badge-trial">' + esc(a.level) + '</span><div class="spacer"></div>' +
        '<button class="btn btn-danger btn-xs" data-ann="' + a.id + '">Delete</button></div>' +
        '<p>' + esc(a.body) + '</p>' +
        '<div class="ann-meta">' + dateStr(a.created_at) + ' · audience: ' + esc(a.audience) + '</div></div>';
    }).join("") || '<div class="empty"><b>No announcements</b><p>Publish one to notify every workspace.</p></div>';
  }


  // ------------------------------------------------------------------ plans
  var CATALOGUE = { plans: [], schema: null, usage: {} };

  function planLimitLabel(v) {
    if (v === -1) return "Unlimited";
    return num(v);
  }

  async function loadPlans() {
    var out = await api("/api/admin/plans");
    CATALOGUE = { plans: out.plans, schema: out.schema, usage: out.usage || {} };
    renderPlanGrid();
    renderFeatureMatrix();
    var sel = $("#tryPlan");
    if (sel) sel.innerHTML = out.plans.map(function (p) {
      return '<option value="' + p.id + '">' + esc(p.name) + ' — ₹' + p.price_monthly + '</option>';
    }).join("");
  }

  function renderPlanGrid() {
    $("#planGrid").innerHTML = CATALOGUE.plans.map(function (p) {
      var seats = CATALOGUE.usage[p.id] || 0;
      return '<div class="plan-card' + (p.highlight ? " featured" : "") +
        (p.is_public ? "" : " hidden-plan") + '">' +
        (p.badge ? '<span class="plan-flag">' + esc(p.badge) + '</span>' : "") +
        '<h4>' + esc(p.name) + '</h4>' +
        '<div class="tag">' + esc(p.tagline || "") + '</div>' +
        '<div class="plan-price"><b>₹' + num(p.price_monthly) + '</b><span>/ month</span></div>' +
        '<div class="plan-year">' + (p.price_yearly ? "₹" + num(p.price_yearly) + " billed yearly" : "No yearly price") +
        (p.trial_days ? " · " + p.trial_days + "-day trial" : "") + '</div>' +
        '<ul class="plan-limits">' +
          (CATALOGUE.schema ? CATALOGUE.schema.limit_keys.map(function (l) {
            return '<li><span>' + esc(l.label) + '</span><b>' + planLimitLabel(p.limits[l.key]) + '</b></li>';
          }).join("") : "") +
        '</ul>' +
        '<div class="plan-foot">' +
          '<span class="users">' + seats + ' workspace' + (seats === 1 ? "" : "s") + '</span>' +
          '<button class="btn btn-line btn-xs" data-plan-edit="' + p.id + '">Edit</button>' +
          '<button class="btn btn-danger btn-xs" data-plan-del="' + p.id + '">Delete</button>' +
        '</div></div>';
    }).join("");
  }

  function renderFeatureMatrix() {
    if (!CATALOGUE.schema) return;
    var head = '<thead><tr><th>Feature</th>' + CATALOGUE.plans.map(function (p) {
      return "<th>" + esc(p.name) + "</th>";
    }).join("") + "</tr></thead>";
    var rows = CATALOGUE.schema.feature_keys.map(function (f) {
      return "<tr><td>" + esc(f.label) + "</td>" + CATALOGUE.plans.map(function (p) {
        var on = !!(p.features || {})[f.key];
        return '<td><span class="tick' + (on ? " on" : "") + '" role="checkbox" tabindex="0" aria-checked="' + on +
          '" data-feat="' + f.key + '" data-plan="' + p.id + '">' +
          '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>' +
          '</span></td>';
      }).join("") + "</tr>";
    }).join("");
    var limitRows = CATALOGUE.schema.limit_keys.map(function (l) {
      return '<tr><td><b>' + esc(l.label) + '</b></td>' + CATALOGUE.plans.map(function (p) {
        return '<td><input class="cell-num" type="number" value="' + (p.limits[l.key] != null ? p.limits[l.key] : 0) +
          '" data-limit="' + l.key + '" data-plan="' + p.id + '" title="-1 means unlimited"></td>';
      }).join("") + "</tr>";
    }).join("");
    $("#featureMatrix").innerHTML = head + "<tbody>" +
      '<tr class="cmp-group"><td colspan="' + (CATALOGUE.plans.length + 1) + '" style="background:var(--surface-2);font-size:11px;font-weight:800;letter-spacing:.07em;text-transform:uppercase;color:var(--faint)">Limits — use -1 for unlimited</td></tr>' +
      limitRows +
      '<tr class="cmp-group"><td colspan="' + (CATALOGUE.plans.length + 1) + '" style="background:var(--surface-2);font-size:11px;font-weight:800;letter-spacing:.07em;text-transform:uppercase;color:var(--faint)">Features</td></tr>' +
      rows + "</tbody>";
  }

  async function savePlanPatch(planId, patch) {
    var out = await api("/api/admin/plans", { method: "POST", body: JSON.stringify(Object.assign({ id: planId }, patch)) });
    if (!out.success) { toast(out.error || "Could not save", true); return false; }
    var idx = CATALOGUE.plans.findIndex(function (p) { return p.id === planId; });
    if (idx >= 0) CATALOGUE.plans[idx] = out.plan;
    return true;
  }

  function showPlanEditor(planId) {
    var plan = CATALOGUE.plans.find(function (p) { return p.id === planId; }) || {
      id: "", name: "", tagline: "", price_monthly: 0, price_yearly: 0, badge: "",
      trial_days: 0, is_public: true, highlight: false, limits: {}, features: {}
    };
    var isNew = !planId;
    $("#drawerTitle").textContent = isNew ? "New plan" : "Edit " + plan.name;
    $("#drawerBody").innerHTML =
      '<form id="planForm">' +
      '<div class="field"><label>Plan name</label><input class="input" name="name" value="' + esc(plan.name) + '" required></div>' +
      '<div class="field"><label>One-line pitch</label><input class="input" name="tagline" value="' + esc(plan.tagline || "") + '"></div>' +
      '<div class="field-row">' +
        '<div class="field"><label>Monthly price (₹)</label><input class="input" name="price_monthly" type="number" value="' + plan.price_monthly + '"></div>' +
        '<div class="field"><label>Yearly price (₹)</label><input class="input" name="price_yearly" type="number" value="' + plan.price_yearly + '"></div>' +
      '</div>' +
      '<div class="field-row">' +
        '<div class="field"><label>Badge</label><input class="input" name="badge" value="' + esc(plan.badge || "") + '" placeholder="Most popular"></div>' +
        '<div class="field"><label>Trial days</label><input class="input" name="trial_days" type="number" value="' + (plan.trial_days || 0) + '"></div>' +
      '</div>' +
      '<div style="height:1px;background:var(--line);margin:18px 0"></div>' +
      '<div class="kpi-label" style="margin-bottom:8px">Limits — use -1 for unlimited</div>' +
      (CATALOGUE.schema ? CATALOGUE.schema.limit_keys.map(function (l) {
        return '<div class="field"><label>' + esc(l.label) + '</label><input class="input" name="limit_' + l.key +
          '" type="number" value="' + (plan.limits[l.key] != null ? plan.limits[l.key] : 0) + '"></div>';
      }).join("") : "") +
      '<div style="height:1px;background:var(--line);margin:18px 0"></div>' +
      '<div class="kpi-label" style="margin-bottom:4px">Features</div>' +
      (CATALOGUE.schema ? CATALOGUE.schema.feature_keys.map(function (f) {
        return '<label class="switch"><input type="checkbox" name="feat_' + f.key + '"' +
          ((plan.features || {})[f.key] ? " checked" : "") + '><span></span> ' + esc(f.label) + '</label>';
      }).join("") : "") +
      '<div style="height:1px;background:var(--line);margin:18px 0"></div>' +
      '<label class="switch"><input type="checkbox" name="is_public"' + (plan.is_public ? " checked" : "") + '><span></span> Show on the public pricing page</label>' +
      '<label class="switch"><input type="checkbox" name="highlight"' + (plan.highlight ? " checked" : "") + '><span></span> Highlight as the recommended plan</label>' +
      '</form>';
    $("#drawerFoot").innerHTML =
      '<button class="btn btn-green" data-act="plan-save" data-id="' + (plan.id || "") + '">' + (isNew ? "Create plan" : "Save plan") + '</button>' +
      '<button class="btn btn-line" data-act="cancel">Cancel</button>';
    openDrawer();
  }

  async function submitPlan(planId) {
    var form = $("#planForm");
    if (!form || !form.reportValidity()) return;
    var fd = new FormData(form);
    var payload = {
      id: planId || undefined,
      name: fd.get("name"),
      tagline: fd.get("tagline"),
      price_monthly: parseInt(fd.get("price_monthly") || 0, 10),
      price_yearly: parseInt(fd.get("price_yearly") || 0, 10),
      badge: fd.get("badge"),
      trial_days: parseInt(fd.get("trial_days") || 0, 10),
      is_public: fd.get("is_public") === "on",
      highlight: fd.get("highlight") === "on",
      limits: {}, features: {}
    };
    CATALOGUE.schema.limit_keys.forEach(function (l) {
      payload.limits[l.key] = parseInt(fd.get("limit_" + l.key) || 0, 10);
    });
    CATALOGUE.schema.feature_keys.forEach(function (f) {
      payload.features[f.key] = fd.get("feat_" + f.key) === "on";
    });
    var out = await api("/api/admin/plans", { method: "POST", body: JSON.stringify(payload) });
    if (!out.success) { toast(out.error || "Could not save the plan", true); return; }
    toast("Plan saved");
    closeDrawer();
    await loadPlans();
  }

  // ----------------------------------------------------------------- offers
  var OFFER_CTX = { schema: null, plans: [] };

  async function loadOffers() {
    var out = await api("/api/admin/offers");
    OFFER_CTX = { schema: out.schema, plans: out.plans };
    var statusClass = { live: "badge-paid", paused: "badge-expired", expired: "badge-expired",
                        scheduled: "badge-trial", "used up": "badge-suspended" };
    $("#offersBody").innerHTML = out.offers.map(function (o) {
      var value = o.type === "percent" ? o.value + "% off"
                : o.type === "flat" ? "₹" + num(o.value) + " off"
                : o.type === "free_months" ? o.value + " free month" + (o.value === 1 ? "" : "s")
                : "+" + o.value + " trial days";
      var scope = (o.applies_to && o.applies_to.length)
        ? o.applies_to.map(function (id) {
            var p = OFFER_CTX.plans.find(function (x) { return x.id === id; });
            return p ? p.name : id;
          }).join(", ")
        : "All plans";
      var cap = o.max_redemptions ? o.redeemed + " / " + o.max_redemptions : String(o.redeemed);
      return '<tr>' +
        '<td><b style="font-family:var(--mono);font-size:13px">' + esc(o.code) + '</b><br><span class="muted">' + esc(o.title || "") + '</span></td>' +
        '<td class="num">' + esc(value) + '</td>' +
        '<td class="muted">' + esc(scope) + '</td>' +
        '<td class="muted">' + dateStr(o.starts_at) + ' → ' + dateStr(o.expires_at) + '</td>' +
        '<td class="num">' + cap + '</td>' +
        '<td><span class="badge ' + (statusClass[o.status] || "badge-expired") + '">' + esc(o.status) + '</span></td>' +
        '<td style="text-align:right;white-space:nowrap">' +
          '<button class="btn btn-line btn-xs" data-offer-edit="' + o.id + '">Edit</button> ' +
          '<button class="btn btn-line btn-xs" data-offer-toggle="' + o.id + '">' + (o.active ? "Pause" : "Resume") + '</button> ' +
          '<button class="btn btn-danger btn-xs" data-offer-del="' + o.id + '">Delete</button>' +
        '</td></tr>';
    }).join("") || '<tr><td colspan="7"><div class="empty"><b>No coupons yet</b><p>Create one to run a launch or festive offer.</p></div></td></tr>';
  }

  function isoDate(value) {
    if (!value) return "";
    return String(value).slice(0, 10);
  }

  function showOfferEditor(offerId) {
    var row = null;
    if (offerId) {
      var btn = document.querySelector('[data-offer-edit="' + offerId + '"]');
      row = btn ? btn.closest("tr") : null;
    }
    api("/api/admin/offers").then(function (out) {
      var o = out.offers.find(function (x) { return x.id === offerId; }) || {
        code: "", title: "", description: "", type: "percent", value: 20,
        applies_to: [], starts_at: "", expires_at: "", max_redemptions: 0, active: true
      };
      $("#drawerTitle").textContent = offerId ? "Edit " + o.code : "New coupon";
      $("#drawerBody").innerHTML =
        '<form id="offerForm">' +
        '<div class="field"><label>Coupon code</label><input class="input" name="code" value="' + esc(o.code) + '" placeholder="LAUNCH50" required style="text-transform:uppercase;font-family:var(--mono)"></div>' +
        '<div class="field"><label>Internal title</label><input class="input" name="title" value="' + esc(o.title || "") + '" placeholder="Launch offer — 50% off"></div>' +
        '<div class="field"><label>What the customer sees</label><input class="input" name="description" value="' + esc(o.description || "") + '"></div>' +
        '<div class="field-row">' +
          '<div class="field"><label>Type</label><select class="select" name="type">' +
            out.schema.offer_types.map(function (t) {
              return '<option value="' + t.key + '"' + (o.type === t.key ? " selected" : "") + '>' + esc(t.label) + '</option>';
            }).join("") + '</select></div>' +
          '<div class="field"><label>Value</label><input class="input" name="value" type="number" value="' + (o.value || 0) + '"></div>' +
        '</div>' +
        '<div class="field"><label>Applies to</label>' +
          out.plans.map(function (p) {
            var on = !o.applies_to || !o.applies_to.length || o.applies_to.indexOf(p.id) >= 0;
            return '<label class="switch"><input type="checkbox" name="plan_' + p.id + '"' + (on ? " checked" : "") + '><span></span> ' + esc(p.name) + '</label>';
          }).join("") +
        '</div>' +
        '<div class="field-row">' +
          '<div class="field"><label>Starts</label><input class="input" name="starts_at" type="date" value="' + isoDate(o.starts_at) + '"></div>' +
          '<div class="field"><label>Expires</label><input class="input" name="expires_at" type="date" value="' + isoDate(o.expires_at) + '"></div>' +
        '</div>' +
        '<div class="field"><label>Max redemptions</label><input class="input" name="max_redemptions" type="number" value="' + (o.max_redemptions || 0) + '"><div class="hint muted" style="font-size:12px;margin-top:6px">0 means no limit.</div></div>' +
        '<label class="switch"><input type="checkbox" name="active"' + (o.active ? " checked" : "") + '><span></span> Active</label>' +
        '</form>';
      $("#drawerFoot").innerHTML =
        '<button class="btn btn-green" data-act="offer-save" data-id="' + (offerId || "") + '">Save coupon</button>' +
        '<button class="btn btn-line" data-act="cancel">Cancel</button>';
      openDrawer();
    });
  }

  async function submitOffer(offerId) {
    var form = $("#offerForm");
    if (!form || !form.reportValidity()) return;
    var fd = new FormData(form);
    var applies = OFFER_CTX.plans.filter(function (p) { return fd.get("plan_" + p.id) === "on"; })
                                 .map(function (p) { return p.id; });
    var payload = {
      id: offerId || undefined,
      code: (fd.get("code") || "").toUpperCase(),
      title: fd.get("title"),
      description: fd.get("description"),
      type: fd.get("type"),
      value: parseInt(fd.get("value") || 0, 10),
      applies_to: applies.length === OFFER_CTX.plans.length ? [] : applies,
      starts_at: fd.get("starts_at") ? fd.get("starts_at") + "T00:00:00" : null,
      expires_at: fd.get("expires_at") ? fd.get("expires_at") + "T23:59:59" : null,
      max_redemptions: parseInt(fd.get("max_redemptions") || 0, 10),
      active: fd.get("active") === "on"
    };
    var out = await api("/api/admin/offers", { method: "POST", body: JSON.stringify(payload) });
    if (!out.success) { toast(out.error || "Could not save", true); return; }
    toast("Coupon saved");
    closeDrawer();
    loadOffers();
  }

  // -------------------------------------------------------------- instagram
  async function loadInstagram() {
    var out = await api("/api/admin/settings");
    var app = out.settings.meta_app;
    var ready = app.ready;
    var tested = app.last_test_ok;

    var tone = ready && tested ? "green" : ready ? "amber" : "coral";
    var head = ready && tested ? "Instagram connect is live"
             : ready ? "Credentials saved — run a test"
             : "Instagram connect is not set up yet";
    var body = ready && tested
      ? "Customers see a Connect Instagram button in their dashboard and link their own account. You never touch their tokens."
      : ready
      ? "The App ID and Secret are stored. Hit Test connection to confirm Meta accepts them."
      : "Add your Meta app below. Until then, the Connect Instagram button in every customer's dashboard stays disabled.";

    $("#igStatusCard").innerHTML =
      '<div class="banner"><div class="banner-ring i-' + tone + '">' +
      '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="20" rx="5.5"/><circle cx="12" cy="12" r="4"/><circle cx="17.5" cy="6.5" r="1.2" fill="currentColor"/></svg>' +
      '</div><div><b>' + esc(head) + '</b><p>' + esc(body) + '</p></div>' +
      '<div class="spacer"></div>' +
      (app.last_test ? '<span class="muted">Last tested ' + ago(app.last_test) + '</span>' : "") +
      '</div>';

    $("#mApp").value = app.app_id || "";
    $("#mSecret").value = app.app_secret || "";
    $("#mRedirect").value = app.redirect_uri || "";
    $("#mVerify").value = app.verify_token || "";
    $("#mVersion").value = app.api_version || "v21.0";
    $("#mWebhook").value = app.webhook_url || "";

    var users = (await api("/api/admin/users")).users;
    $("#igAccountsBody").innerHTML = users.map(function (u) {
      var ig = u.instagram || {};
      return '<tr><td>' + userCell(u) + '</td>' +
        '<td>' + (ig.connected ? '<b>@' + esc(ig.username || u.ig_handle) + '</b>' : '<span class="muted">Not connected</span>') + '</td>' +
        '<td class="num">' + (ig.followers ? num(ig.followers) : "—") + '</td>' +
        '<td class="muted">' + (ig.connected_at ? dateStr(ig.connected_at) : "—") + '</td>' +
        '<td>' + (ig.connected
          ? '<span class="badge badge-paid">Live</span>'
          : '<span class="badge badge-expired">Waiting</span>') + '</td></tr>';
    }).join("");
  }

  // --------------------------------------------------------------- settings
  async function loadSettings() {
    var out = await api("/api/admin/settings");
    ["brand", "billing", "safety", "flags"].forEach(function (section) {
      var form = document.querySelector('form[data-section="' + section + '"]');
      if (!form) return;
      var values = out.settings[section] || {};
      Array.prototype.forEach.call(form.elements, function (el) {
        if (!el.name) return;
        if (el.type === "checkbox") el.checked = !!values[el.name];
        else if (values[el.name] != null) el.value = values[el.name];
      });
    });
  }

  async function submitSettings(form) {
    var section = form.dataset.section;
    var values = {};
    Array.prototype.forEach.call(form.elements, function (el) {
      if (!el.name) return;
      if (el.type === "checkbox") values[el.name] = el.checked;
      else if (el.type === "number") values[el.name] = parseInt(el.value || 0, 10);
      else values[el.name] = el.value;
    });
    var out = await api("/api/admin/settings", { method: "POST", body: JSON.stringify({ section: section, values: values }) });
    if (!out.success) { toast("Could not save", true); return; }
    toast(section.charAt(0).toUpperCase() + section.slice(1) + " settings saved");
  }

  // -------------------------------------------------------------- templates
  async function loadTemplates() {
    var out = await api("/api/admin/templates");
    $("#templateList").innerHTML = out.templates.map(function (t) {
      return '<div class="tpl" data-tpl="' + t.id + '">' +
        '<div class="tpl-head"><b>' + esc(t.name) + '</b><span>' + esc(t.when || "") + '</span>' +
        '<div class="spacer"></div>' +
        '<span class="badge ' + (t.enabled ? "badge-paid" : "badge-expired") + '">' + (t.enabled ? "On" : "Off") + '</span>' +
        '<svg class="chev" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M6 9l6 6 6-6"/></svg>' +
        '</div>' +
        '<div class="tpl-body">' +
          '<form data-tpl-form="' + t.id + '">' +
            '<div class="field"><label>Subject</label><input class="input" name="subject" value="' + esc(t.subject) + '"></div>' +
            '<div class="field"><label>Body</label><textarea class="input" name="body">' + esc(t.body) + '</textarea></div>' +
            '<label class="switch"><input type="checkbox" name="enabled"' + (t.enabled ? " checked" : "") + '><span></span> Send this notification</label>' +
            '<div style="display:flex;gap:9px;margin-top:14px">' +
              '<button class="btn btn-green btn-xs" type="submit">Save</button>' +
              '<button class="btn btn-line btn-xs" type="button" data-tpl-preview="' + t.id + '">Preview with sample data</button>' +
            '</div>' +
          '</form>' +
          '<div class="tpl-preview" hidden></div>' +
        '</div></div>';
    }).join("");
  }

  // ------------------------------------------------------------------ views
  var TITLES = {
    overview: ["Business overview", "Everything happening across ConverFlow right now"],
    users: ["Users & subscriptions", "Every workspace, plan and lifetime value"],
    revenue: ["Revenue", "MRR, ARR and the full payment ledger"],
    plans: ["Plans & pricing", "Build the ladder — prices, limits and what each tier unlocks"],
    offers: ["Offers & coupons", "Discount codes, festive offers and trial extensions"],
    instagram: ["Instagram API", "One Meta app here, one-click connect for every customer"],
    templates: ["Email templates", "What ConverFlow says to your customers"],
    health: ["System health", "Automation runs, sessions and error logs"],
    announcements: ["Announcements", "Broadcast a notice to your users"],
    settings: ["Plan settings", "Pricing constants and data exports"]
  };

  async function showView(name) {
    $$(".view").forEach(function (v) { v.classList.remove("active"); });
    var v = $("#view-" + name);
    if (v) v.classList.add("active");
    $$(".side-link").forEach(function (l) { l.classList.toggle("active", l.dataset.view === name); });
    var t = TITLES[name] || TITLES.overview;
    $("#pageTitle").textContent = t[0];
    $("#pageSub").textContent = t[1];
    $("#side").classList.remove("show");

    if (name === "users") await loadUsers();
    if (name === "revenue") renderRevenue();
    if (name === "health") await loadEvents();
    if (name === "announcements") await loadAnnouncements();
    if (name === "plans") await loadPlans();
    if (name === "offers") await loadOffers();
    if (name === "instagram") await loadInstagram();
    if (name === "templates") await loadTemplates();
    if (name === "settings") await loadSettings();
    if (name === "overview") renderOverview();
  }

  async function refresh() {
    try {
      STATE.overview = await api("/api/admin/overview");
      renderOverview();
      var active = ($(".view.active") || {}).id || "view-overview";
      var name = active.replace("view-", "");
      if (name === "users") await loadUsers();
      if (name === "revenue") renderRevenue();
      if (name === "health") await loadEvents();
    } catch (e) {
      toast("Could not reach the server", true);
    }
  }

  // ------------------------------------------------------------------ wires
  document.addEventListener("click", function (ev) {
    var link = ev.target.closest(".side-link");
    if (link) { ev.preventDefault(); showView(link.dataset.view); return; }

    var goto = ev.target.closest("[data-goto]");
    if (goto) { showView(goto.dataset.goto); return; }

    var btn = ev.target.closest("[data-act]");
    if (btn) {
      ev.preventDefault();
      var a = btn.dataset.act;
      if (a === "open") { showUser(btn.dataset.id); return; }
      if (a === "plan-save") { submitPlan(btn.dataset.id); return; }
      if (a === "offer-save") { submitOffer(btn.dataset.id); return; }
      act(a, btn.dataset.id);
      return;
    }

    var row = ev.target.closest("tr.u-row");
    if (row && !ev.target.closest("button")) { showUser(row.dataset.id); return; }

    var planEdit = ev.target.closest("[data-plan-edit]");
    if (planEdit) { showPlanEditor(planEdit.dataset.planEdit); return; }

    var planDel = ev.target.closest("[data-plan-del]");
    if (planDel) {
      var pid = planDel.dataset.planDel;
      if (!window.confirm("Delete this plan? Workspaces on it must be moved first.")) return;
      api("/api/admin/plans/" + pid, { method: "DELETE" }).then(function (out) {
        if (!out.success) { toast(out.error || "Could not delete", true); return; }
        toast("Plan deleted");
        loadPlans();
      });
      return;
    }

    var tick = ev.target.closest(".tick");
    if (tick) {
      var on = !tick.classList.contains("on");
      tick.classList.toggle("on", on);
      tick.setAttribute("aria-checked", String(on));
      var patch = { features: {} };
      patch.features[tick.dataset.feat] = on;
      savePlanPatch(tick.dataset.plan, patch).then(function (ok) {
        if (ok) { toast("Plan updated"); renderPlanGrid(); }
        else { tick.classList.toggle("on", !on); }
      });
      return;
    }

    var offerEdit = ev.target.closest("[data-offer-edit]");
    if (offerEdit) { showOfferEditor(offerEdit.dataset.offerEdit); return; }

    var offerToggle = ev.target.closest("[data-offer-toggle]");
    if (offerToggle) {
      api("/api/admin/offers/" + offerToggle.dataset.offerToggle + "/toggle", { method: "POST" })
        .then(function (out) { toast(out.offer.active ? "Coupon resumed" : "Coupon paused"); loadOffers(); });
      return;
    }

    var offerDel = ev.target.closest("[data-offer-del]");
    if (offerDel) {
      if (!window.confirm("Delete this coupon? Anyone typing it will get an error.")) return;
      api("/api/admin/offers/" + offerDel.dataset.offerDel, { method: "DELETE" })
        .then(function () { toast("Coupon deleted"); loadOffers(); });
      return;
    }

    var tplPrev = ev.target.closest("[data-tpl-preview]");
    if (tplPrev) {
      var box = tplPrev.closest(".tpl-body").querySelector(".tpl-preview");
      api("/api/admin/templates/" + tplPrev.dataset.tplPreview + "/preview").then(function (out) {
        box.hidden = false;
        box.innerHTML = "<h5>" + esc(out.preview.subject) + "</h5><pre>" + esc(out.preview.body) + "</pre>";
      });
      return;
    }

    var tplHead = ev.target.closest(".tpl-head");
    if (tplHead) { tplHead.parentNode.classList.toggle("open"); return; }

    var del = ev.target.closest("[data-ann]");
    if (del) {
      api("/api/admin/announcements/" + del.dataset.ann, { method: "DELETE" })
        .then(function () { toast("Announcement removed"); loadAnnouncements(); });
      return;
    }
  });

  $("#scrim").addEventListener("click", closeDrawer);
  $("#drawerClose").addEventListener("click", closeDrawer);
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") closeDrawer(); });
  $("#btnRefresh").addEventListener("click", function () { refresh(); toast("Refreshed"); });
  $("#btnAddUser").addEventListener("click", showAddUser);
  $("#menuBtn").addEventListener("click", function () { $("#side").classList.toggle("show"); });

  var searchTimer;
  $("#userSearch").addEventListener("input", function (e) {
    STATE.search = e.target.value;
    clearTimeout(searchTimer);
    searchTimer = setTimeout(loadUsers, 220);
  });
  $("#planFilter").addEventListener("click", function (e) {
    var b = e.target.closest("button"); if (!b) return;
    $$("#planFilter button").forEach(function (x) { x.classList.toggle("on", x === b); });
    STATE.plan = b.dataset.plan; loadUsers();
  });
  $("#statusFilter").addEventListener("click", function (e) {
    var b = e.target.closest("button"); if (!b) return;
    $$("#statusFilter button").forEach(function (x) { x.classList.toggle("on", x === b); });
    STATE.status = b.dataset.status; loadUsers();
  });
  $("#logFilter").addEventListener("click", function (e) {
    var b = e.target.closest("button"); if (!b) return;
    $$("#logFilter button").forEach(function (x) { x.classList.toggle("on", x === b); });
    STATE.level = b.dataset.level; loadEvents();
  });

  $("#annForm").addEventListener("submit", async function (e) {
    e.preventDefault();
    var payload = Object.fromEntries(new FormData(e.target).entries());
    try {
      await api("/api/admin/announcements", { method: "POST", body: JSON.stringify(payload) });
      e.target.reset();
      toast("Announcement published");
      loadAnnouncements();
    } catch (_) { toast("Could not publish", true); }
  });

  // limits typed straight into the matrix
  document.addEventListener("change", function (ev) {
    var cell = ev.target.closest(".cell-num");
    if (cell) {
      var patch = { limits: {} };
      patch.limits[cell.dataset.limit] = parseInt(cell.value || 0, 10);
      savePlanPatch(cell.dataset.plan, patch).then(function (ok) {
        if (ok) { toast("Limit updated"); renderPlanGrid(); }
      });
    }
  });

  document.addEventListener("submit", function (ev) {
    var form = ev.target;

    if (form.dataset.section) {
      ev.preventDefault();
      submitSettings(form);
      return;
    }

    if (form.id === "metaForm") {
      ev.preventDefault();
      var values = {};
      Array.prototype.forEach.call(form.elements, function (el) {
        if (el.name && el.value && el.value.indexOf("•") === -1) values[el.name] = el.value;
      });
      api("/api/admin/settings", { method: "POST", body: JSON.stringify({ section: "meta_app", values: values }) })
        .then(function (out) {
          if (!out.success) { toast("Could not save", true); return; }
          toast("Meta app saved — now run Test connection");
          loadInstagram();
        });
      return;
    }

    if (form.dataset.tplForm) {
      ev.preventDefault();
      var fd = new FormData(form);
      api("/api/admin/templates/" + form.dataset.tplForm, {
        method: "PATCH",
        body: JSON.stringify({ subject: fd.get("subject"), body: fd.get("body"), enabled: fd.get("enabled") === "on" })
      }).then(function () { toast("Template saved"); loadTemplates(); });
      return;
    }
  });

  var btnNewPlan = $("#btnNewPlan");
  if (btnNewPlan) btnNewPlan.addEventListener("click", function () { showPlanEditor(""); });

  var btnNewOffer = $("#btnNewOffer");
  if (btnNewOffer) btnNewOffer.addEventListener("click", function () { showOfferEditor(""); });

  var btnTestMeta = $("#btnTestMeta");
  if (btnTestMeta) btnTestMeta.addEventListener("click", async function () {
    btnTestMeta.disabled = true;
    btnTestMeta.textContent = "Testing…";
    try {
      var out = await api("/api/admin/meta-app/test", { method: "POST" });
      toast(out.success ? out.message : out.error, !out.success);
      loadInstagram();
    } catch (e) { toast("Test failed", true); }
    btnTestMeta.disabled = false;
    btnTestMeta.textContent = "Test connection";
  });

  var btnTryCode = $("#btnTryCode");
  if (btnTryCode) btnTryCode.addEventListener("click", async function () {
    var code = $("#tryCode").value.trim();
    var plan = $("#tryPlan").value;
    if (!code) { toast("Type a coupon code first", true); return; }
    var out = await api("/api/admin/offers/check", { method: "POST", body: JSON.stringify({ code: code, plan_id: plan }) });
    var r = out.result;
    var box = $("#tryResult");
    if (!r.valid) {
      box.innerHTML = '<span style="color:var(--coral);font-weight:700">' + esc(r.error) + '</span>';
    } else if (r.trial_days) {
      box.innerHTML = '<b style="color:var(--green)">+' + r.trial_days + ' trial days</b> on ' + esc(r.plan);
    } else {
      box.innerHTML = esc(r.plan) + ': <s>₹' + num(r.original_price) + '</s> → <b style="color:var(--green);font-size:15px">₹' +
        num(r.final_price) + '</b> <span class="muted">(₹' + num(r.discount) + ' off)</span>';
    }
  });

  window.addEventListener("resize", function () {
    if (STATE.overview) {
      barChart($("#chartRevenue"), STATE.overview.revenue_series, { key: "revenue", money: true });
      barChart($("#chartSignups"), STATE.overview.revenue_series, { key: "signups", color: "url(#gBlue)" });
      if ($("#view-revenue").classList.contains("active")) {
        barChart($("#chartRevenueBig"), STATE.overview.revenue_series, { key: "revenue", money: true });
      }
    }
  });

  // ------------------------------------------------------------------- boot
  (async function boot() {
    await refresh();
    var hash = (location.hash || "#overview").replace("#", "");
    showView(TITLES[hash] ? hash : "overview");
  })();
})();
