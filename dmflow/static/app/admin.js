(function () {
  "use strict";
  function $(s) { return document.querySelector(s); }
  function esc(v) { return String(v == null ? "" : v).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function ago(ts) { var s = Math.max(0, Math.round(Date.now() / 1000 - ts)); return s < 60 ? s + "s ago" : s < 3600 ? Math.floor(s / 60) + "m ago" : s < 86400 ? Math.floor(s / 3600) + "h ago" : Math.floor(s / 86400) + "d ago"; }
  var tt; function toast(m, bad) { var t = $("#toast"); t.textContent = m; t.className = "toast show" + (bad ? " err" : ""); clearTimeout(tt); tt = setTimeout(function () { t.className = "toast"; }, 3200); }
  async function api(p, o) {
    o = o || {}; var r = await fetch(p, { method: o.method || "GET", credentials: "same-origin",
      headers: o.body ? { "Content-Type": "application/json" } : {}, body: o.body ? JSON.stringify(o.body) : undefined });
    if (r.status === 401) { location.href = "/login?next=/admin"; return {}; }
    if (r.status === 403) { location.href = "/app"; return {}; }
    try { return await r.json(); } catch (e) { return { success: false }; }
  }

  async function loadSettings() {
    var out = await api("/api/admin/settings"); if (!out.success) return;
    var f = $("#metaForm");
    Object.keys(out.settings).forEach(function (k) {
      var s = out.settings[k], el = f.elements[k]; if (!el) return;
      el.value = s.value; el.disabled = s.source === "env";
      var tag = document.querySelector('[data-src="' + k + '"]');
      tag.textContent = s.source === "env" ? "from Railway" : s.source === "default" ? "default" : "";
    });
    var u = out.urls, rows = [["OAuth redirect URI", u.redirect_uri], ["Webhook callback", u.webhook],
      ["Verify token", out.settings.verify_token.value], ["Deauthorize callback", u.deauthorize], ["Data deletion URL", u.data_deletion]];
    $("#urls").innerHTML = rows.map(function (r) {
      return '<div class="copy"><span>' + esc(r[0]) + "</span><code>" + esc(r[1]) + '</code><button class="btn btn-sm" data-copy="' + esc(r[1]) + '">Copy</button></div>';
    }).join("");
    var w = out.last_webhook || {}, p = out.last_poll || {};
    $("#health").innerHTML =
      "<dt>Webhook</dt><dd>" + (w.at ? (w.ok ? '<span class="pill green">Received</span> ' : '<span class="pill red">Refused</span> ') + ago(w.at) +
        (w.note ? '<div class="hint">' + esc(w.note) + "</div>" : "") : '<span class="pill">Nothing yet</span><div class="hint">Normal until the app is published - Meta sends only to app testers before that.</div>') + "</dd>" +
      "<dt>Comment check</dt><dd>" + (p.at ? ago(p.at) + " &middot; " + (p.accounts || 0) + " accounts, " + (p.posts || 0) + " posts, " + (p.new || 0) + " new" + (p.errors ? ', <span style="color:var(--red)">' + p.errors + " errors</span>" : "") : "not run yet") + "</dd>";
  }

  async function loadUsers() {
    var out = await api("/api/admin/users"); if (!out.success) return;
    var plans = out.plans;
    $("#users").innerHTML = out.users.map(function (u) {
      return "<tr><td><b>" + esc(u.name || "-") + "</b><div class=\"hint\">" + esc(u.email) + (u.role === "admin" ? ' &middot; <span class="pill ink">admin</span>' : "") + "</div></td>" +
        "<td>" + (u.ig_username ? "@" + esc(u.ig_username) + (u.ig_status !== "connected" ? ' <span class="pill amber">' + esc(u.ig_status) + "</span>" : "") : '<span class="hint">-</span>') + "</td>" +
        "<td>" + (u.live_flows || 0) + "</td>" +
        '<td><select class="input" data-plan="' + esc(u.id) + '">' + plans.map(function (p) { return "<option value=\"" + esc(p.id) + "\"" + (p.id === u.plan ? " selected" : "") + ">" + esc(p.name) + "</option>"; }).join("") + "</select></td>" +
        '<td><select class="input" data-status="' + esc(u.id) + '"><option value="active"' + (u.status === "active" ? " selected" : "") + '>Active</option><option value="suspended"' + (u.status === "suspended" ? " selected" : "") + ">Suspended</option></select></td>" +
        "<td>" + new Date(u.created_at * 1000).toLocaleDateString() + "</td></tr>";
    }).join("");
  }

  async function loadEvents() {
    var out = await api("/api/admin/events"); if (!out.success) return;
    $("#events").innerHTML = out.events.length ? '<ul class="feed">' + out.events.map(function (e) {
      return '<li><span class="when">' + ago(e.at) + '</span><div class="what"><b>' + esc(e.email || "(no workspace)") + "</b> &middot; " + esc(e.kind) +
        (e.username ? " &middot; @" + esc(e.username) : "") + (e.text ? ' &middot; "' + esc(e.text) + '"' : "") +
        (e.note ? "<p>" + esc(e.note) + "</p>" : "") + '</div><span class="pill">' + esc(e.verdict) + "</span></li>";
    }).join("") + "</ul>" : '<div class="empty">No activity yet.</div>';
  }

  $("#metaForm").addEventListener("submit", async function (e) {
    e.preventDefault();
    var data = {}; Array.prototype.forEach.call(this.elements, function (el) { if (el.name && !el.disabled) data[el.name] = el.value; });
    var out = await api("/api/admin/settings", { method: "POST", body: data });
    toast(out.success ? "Saved" : "Could not save", !out.success); loadSettings();
  });
  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-copy]"); if (!b) return;
    navigator.clipboard.writeText(b.dataset.copy).then(function () { toast("Copied"); });
  });
  document.addEventListener("change", async function (e) {
    var t = e.target, id = t.dataset.plan || t.dataset.status; if (!id) return;
    var body = t.dataset.plan ? { plan: t.value } : { status: t.value };
    var out = await api("/api/admin/users/" + id, { method: "POST", body: body });
    toast(out.success ? "Updated" : "Could not update", !out.success);
  });
  loadSettings(); loadUsers(); loadEvents();
})();
