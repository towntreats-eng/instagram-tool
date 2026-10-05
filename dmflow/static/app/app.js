/* DM Flow - customer panel. Vanilla JS, no build step.
   Every number and name on screen comes from the server; nothing is invented. */
(function () {
  "use strict";

  var S = { me: null, plan: null, usage: {}, ig: { connected: false }, igReady: true,
            flows: [], template: null, media: null, events: [], health: {} };

  // ------------------------------------------------------------ helpers
  function $(sel, root) { return (root || document).querySelector(sel); }
  function $$(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function esc(v) {
    return String(v == null ? "" : v).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function clone(o) { return JSON.parse(JSON.stringify(o)); }
  function num(n) { n = Number(n || 0); return n >= 1000 ? (n / 1000).toFixed(n >= 10000 ? 0 : 1) + "k" : String(n); }
  function cap(n) { return Number(n) === -1 ? "Unlimited" : num(n); }
  function ago(ts) {
    var s = Math.max(0, Math.round(Date.now() / 1000 - Number(ts || 0)));
    if (s < 60) return s + "s ago"; if (s < 3600) return Math.floor(s / 60) + "m ago";
    if (s < 86400) return Math.floor(s / 3600) + "h ago"; return Math.floor(s / 86400) + "d ago";
  }
  function day(ts) { return ts ? new Date(ts * 1000).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }) : "-"; }

  var toastTimer;
  function toast(msg, isErr) {
    var t = $("#toast"); t.textContent = msg; t.className = "toast show" + (isErr ? " err" : "");
    clearTimeout(toastTimer); toastTimer = setTimeout(function () { t.className = "toast"; }, 3600);
  }

  async function api(path, opts) {
    opts = opts || {};
    var init = { method: opts.method || "GET", credentials: "same-origin", headers: {} };
    if (opts.body !== undefined) { init.headers["Content-Type"] = "application/json"; init.body = JSON.stringify(opts.body); }
    var res;
    try { res = await fetch(path, init); } catch (e) { return { success: false, error: "Network error - check your connection." }; }
    if (res.status === 401) { location.href = "/login?next=" + encodeURIComponent(location.pathname); return { success: false }; }
    var out = {};
    try { out = await res.json(); } catch (e) { out = { success: res.ok }; }
    if (!res.ok && out.success === undefined) out.success = false;
    if (!res.ok && !out.error) out.error = out.detail || ("Request failed (" + res.status + ")");
    return out;
  }

  function modal(html) {
    var bg = document.createElement("div"); bg.className = "modal-bg";
    bg.innerHTML = '<div class="modal">' + html + "</div>";
    bg.addEventListener("click", function (e) { if (e.target === bg) bg.remove(); });
    document.body.appendChild(bg);
    return bg;
  }

  var I = {
    check: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>',
    bolt: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2 3 14h8l-1 8 11-13h-8z"/></svg>',
    ig: '<svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.5" cy="6.5" r="1" fill="currentColor"/></svg>',
    more: '<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="5" r="1.8"/><circle cx="12" cy="12" r="1.8"/><circle cx="12" cy="19" r="1.8"/></svg>',
    img: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="9" cy="9" r="2"/><path d="m21 15-5-5L5 21"/></svg>',
    x: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M18 6 6 18M6 6l12 12"/></svg>'
  };

  // ------------------------------------------------------------ data
  async function loadMe() {
    var out = await api("/api/me");
    if (!out.success) return false;
    S.me = out.user; S.plan = out.plan; S.usage = out.usage; S.ig = out.instagram || { connected: false };
    S.igReady = out.instagram_ready;
    paintSide();
    return true;
  }
  async function loadFlows() {
    var out = await api("/api/flows");
    if (out.success) { S.flows = out.flows; S.template = out.template; }
  }
  async function loadMedia(force) {
    if (S.media && !force) return S.media;
    var out = await api("/api/instagram/media");
    S.media = out.success ? out.media : [];
    return S.media;
  }

  function paintSide() {
    var a = $("#acct");
    if (S.ig.connected) {
      a.className = "acct";
      a.innerHTML = (S.ig.picture ? '<img src="' + esc(S.ig.picture) + '" alt="" referrerpolicy="no-referrer">' : '<span class="ph">@</span>') +
        "<div><b>@" + esc(S.ig.username) + "</b><span><i class=\"dot\"></i>Connected</span></div>";
    } else {
      a.className = "acct off";
      a.innerHTML = '<span class="ph">' + I.img + "</span><div><b>No account</b><span><i class=\"dot\"></i>" +
        (S.ig.status === "expired" ? "Connection expired" : "Not connected") + "</span></div>";
    }
    var lim = S.plan ? S.plan.limits.dms_per_month : 0, used = S.usage.dms || 0;
    $("#mUse").textContent = num(used) + " / " + cap(lim);
    $("#mBar").style.width = (lim === -1 ? 4 : Math.min(100, (used / Math.max(1, lim)) * 100)) + "%";
    $("#mPlan").textContent = (S.plan ? S.plan.name : "") + " plan";
    var nm = (S.me.name || S.me.email || "?");
    $("#meAv").textContent = nm.charAt(0).toUpperCase();
    $("#meName").textContent = S.me.name || "You"; $("#meEmail").textContent = S.me.email;
  }

  // ------------------------------------------------------------ router
  var VIEWS = { home: viewHome, automations: viewAutomations, contacts: viewContacts, settings: viewSettings };
  var TITLES = { home: "Home", automations: "Automations", contacts: "Contacts", settings: "Settings" };

  function current() {
    var p = location.pathname.replace(/^\/app\/?/, "").split("/")[0];
    return VIEWS[p] ? p : "home";
  }
  function go(path) { history.pushState({}, "", path); route(); }
  async function route() {
    var v = current();
    $$("#nav a").forEach(function (a) { a.classList.toggle("on", a.dataset.v === v); });
    $("#title").textContent = TITLES[v]; $("#topAct").innerHTML = "";
    $("#side").classList.remove("open");
    $("#view").innerHTML = '<div class="empty">Loading...</div>';
    await VIEWS[v]();
    window.scrollTo(0, 0);
  }

  document.addEventListener("click", function (e) {
    var a = e.target.closest("a[href^='/app']");
    if (a && !e.metaKey && !e.ctrlKey && a.target !== "_blank") { e.preventDefault(); go(a.getAttribute("href")); }
    if (!e.target.closest(".kebab")) $$(".pop").forEach(function (p) { p.remove(); });
  });
  window.addEventListener("popstate", route);
  $("#menu").addEventListener("click", function () { $("#side").classList.toggle("open"); });
  $("#logout").addEventListener("click", async function () {
    await api("/api/auth/logout", { method: "POST" }); location.href = "/login";
  });

  // ------------------------------------------------------------ HOME
  var PRESETS = {
    link: { title: "Auto-DM links from comments", text: "Someone comments a keyword, they get your link in DMs.", pill: "Popular",
            body: {} },
    follow: { title: "Grow followers from comments", text: "Ask them to follow before the link arrives.", pill: "",
              body: { follow_gate: { on: true } } },
    every: { title: "Reply to every comment", text: "Any comment on a post gets a reply and a DM.", pill: "",
             body: { trigger: { mode: "any" } } }
  };

  function connectCard() {
    var expired = S.ig.status === "expired";
    return '<div class="card connect"><div class="connect-body">' +
      '<span class="pill ' + (expired ? "amber" : "green") + '">' + (expired ? "Reconnect needed" : "Step 1") + "</span>" +
      "<h2 style=\"margin-top:12px\">" + (expired ? "Your Instagram connection stopped working" : "Connect your Instagram account") + "</h2>" +
      "<p>" + (expired ? esc(S.ig.note || "Instagram no longer accepts the saved login.") + " Connect again to resume your automations."
        : "DM Flow uses Instagram's official login. You approve it on Instagram itself - we never see your password.") + "</p>" +
      (S.igReady ? '<a class="btn btn-green btn-lg" href="/connect/instagram">Connect Instagram</a>'
        : '<div class="errbox">Instagram is not set up on this platform yet - the administrator needs to add the app credentials.</div>') +
      "<ul><li>" + I.check + "Business or Creator account (switch free in the Instagram app)</li>" +
      "<li>" + I.check + "No Facebook Page needed</li>" +
      "<li>" + I.check + "Disconnect any time - everything stops immediately</li></ul>" +
      '</div><div class="connect-art"><div class="ig-badge">' + I.ig + "</div></div></div>";
  }

  function accountStrip() {
    return '<div class="card acct-strip">' +
      (S.ig.picture ? '<img src="' + esc(S.ig.picture) + '" alt="" referrerpolicy="no-referrer">' : "") +
      "<div><b>@" + esc(S.ig.username) + '</b> <span class="pill green">' + I.check + " Connected</span>" +
      '<div class="meta">' + esc(S.ig.name || "") + (S.ig.name ? " · " : "") + num(S.ig.followers) + " followers · " +
      num(S.ig.media_count) + " posts · " + esc((S.ig.account_type || "").toLowerCase().replace("media_creator", "creator")) + " account</div></div>" +
      '<div class="sp"></div><button class="btn btn-sm" data-act="refresh">Refresh</button></div>';
  }

  function healthLine() {
    var h = S.health || {}, bits = [];
    if (h.webhook_last_at) bits.push((h.webhook_last_ok ? "Instagram last delivered " : "Last delivery refused ") + ago(h.webhook_last_at));
    else bits.push("No webhook delivery yet");
    if (h.poll && h.poll.at) bits.push("comments checked " + ago(h.poll.at));
    return bits.join(" · ");
  }

  var VERDICT = {
    sent: ["DM sent", "green"], link_sent: ["Link sent", "green"], held: ["Asked to follow", "amber"],
    no_flow: ["No automation", ""], ignored: ["Skipped", ""], failed: ["Failed", "red"], limit: ["Limit reached", "red"],
    reply_failed: ["Reply failed", "red"], connected: ["Connected", "green"], disconnected: ["Disconnected", ""],
    deauthorized: ["Removed on Instagram", ""], error: ["Error", "red"], rejected: ["Refused", "red"]
  };
  function feed(rows) {
    if (!rows.length) return '<div class="empty"><b>Nothing yet</b>Comments that reach DM Flow appear here, with what happened to each.</div>';
    return '<ul class="feed">' + rows.map(function (r) {
      var v = VERDICT[r.verdict] || [r.verdict, ""];
      var who = r.username ? "@" + r.username : (r.kind === "account" ? "Account" : "Someone");
      var what = r.kind === "comment" ? " commented" + (r.text ? ' "' + esc(r.text) + '"' : "") :
        r.kind === "postback" ? " tapped the button" : "";
      return '<li><span class="when">' + ago(r.at) + '</span><div class="what"><b>' + esc(who) + "</b>" + what +
        (r.note ? "<p>" + esc(r.note) + "</p>" : "") + '</div><span class="pill ' + v[1] + '">' + esc(v[0]) + "</span></li>";
    }).join("") + "</ul>";
  }

  async function viewHome() {
    var act = await api("/api/activity");
    S.events = act.events || []; S.health = act.health || {};
    var first = (S.me.name || "").split(" ")[0] || "there";
    var lim = S.plan.limits;
    var html = '<h1 class="hello">Hello, ' + esc(first) + "!</h1>" +
      '<p class="sub">' + (S.ig.connected ? "1 connected channel · @" + esc(S.ig.username) : "No Instagram account connected yet") +
      (S.ig.connected ? '<a class="link" href="/app/automations">See automations</a>' : "") + "</p>" +
      (S.ig.connected ? accountStrip() : connectCard()) +
      '<h2 class="h2">Start here<span class="sp"></span></h2><div class="grid3">' +
      Object.keys(PRESETS).map(function (k) {
        var p = PRESETS[k];
        return '<button class="tpl" data-preset="' + k + '"><div><b>' + esc(p.title) + "</b><p>" + esc(p.text) + "</p></div>" +
          '<div class="tpl-foot"><span>' + I.bolt + " Quick automation</span>" + (p.pill ? '<span class="pill ink">' + esc(p.pill) + "</span>" : "") + "</div></button>";
      }).join("") + "</div>" +
      '<h2 class="h2">This month</h2><div class="tiles">' +
      '<div class="card tile"><span>Live automations</span><b>' + num(S.usage.live) + "</b><small>" + (lim.automations === -1 ? "no limit on your plan" : "of " + lim.automations + " on your plan") + "</small></div>" +
      '<div class="card tile"><span>DMs sent</span><b>' + num(S.usage.dms) + "</b><small>of " + cap(lim.dms_per_month) + " this month</small></div>" +
      '<div class="card tile"><span>People captured</span><b>' + num(S.usage.contacts) + "</b><small>of " + cap(lim.contacts) + " stored</small></div></div>" +
      '<h2 class="h2">Recent activity<span class="sp"></span>' +
      (S.ig.connected ? '<span class="hint">' + esc(healthLine()) + '</span><button class="btn btn-sm" data-act="poll">Check comments now</button>' : "") +
      '</h2><div class="card">' + feed(S.events.slice(0, 12)) + "</div>";
    $("#view").innerHTML = html;
  }

  // ------------------------------------------------------------ AUTOMATIONS
  function flowSummary(b) {
    var t = b.trigger.mode === "any" ? "Any comment" : "Keyword: " + b.trigger.keywords.join(", ");
    var p = b.post.mode === "any" ? "any post" : "one post";
    return t + " · " + p + (b.follow_gate.on ? " · follow-gate" : "");
  }
  async function viewAutomations() {
    await loadFlows();
    $("#topAct").innerHTML = '<button class="btn btn-primary" data-act="new">New automation</button>';
    if (!S.flows.length) {
      $("#view").innerHTML = '<div class="card"><div class="empty"><b>No automations yet</b>' +
        "Pick a post, choose a keyword, write the DM. Takes about a minute.<br><br>" +
        '<button class="btn btn-primary" data-act="new">Create your first automation</button></div></div>';
      return;
    }
    $("#view").innerHTML = '<div class="card"><ul class="flows">' + S.flows.map(function (f) {
      var b = f.body, thumb = b.post.thumb;
      return '<li class="flow" data-id="' + esc(f.id) + '">' +
        '<div class="th" style="' + (thumb ? "background-image:url('" + esc(thumb) + "')" : "") + '">' + (thumb ? "" : (b.post.mode === "any" ? I.bolt : I.img)) + "</div>" +
        "<div><b>" + esc(f.name) + '</b><div class="meta">' + esc(flowSummary(b)) + "</div></div>" +
        '<div class="num"><b>' + num(f.stats.triggered) + "</b><br>triggered</div>" +
        '<label class="switch" title="' + (f.status === "live" ? "Live" : "Off") + '"><input type="checkbox" data-toggle="' + esc(f.id) + '"' + (f.status === "live" ? " checked" : "") + "><span></span></label>" +
        '<div class="kebab"><button class="btn btn-ghost btn-sm" data-menu="' + esc(f.id) + '">' + I.more + "</button></div></li>";
    }).join("") + "</ul></div>";
  }

  // ------------------------------------------------------------ CONTACTS
  async function viewContacts() {
    var out = await api("/api/contacts"), rows = out.contacts || [];
    $("#topAct").innerHTML = rows.length ? '<a class="btn" href="/api/contacts.csv">Export CSV</a>' : "";
    if (!rows.length) {
      $("#view").innerHTML = '<div class="card"><div class="empty"><b>No contacts yet</b>Everyone who comments on a live automation is saved here.</div></div>';
      return;
    }
    $("#view").innerHTML = '<div class="toolbar"><input class="input" id="cSearch" placeholder="Search by username"></div>' +
      '<div class="card"><table class="t"><thead><tr><th>Username</th><th>Automation</th><th>Follows</th><th>Link</th><th>Last seen</th></tr></thead><tbody id="cBody"></tbody></table></div>';
    function paint(q) {
      $("#cBody").innerHTML = rows.filter(function (r) { return !q || (r.username || "").toLowerCase().indexOf(q) >= 0; }).map(function (r) {
        return "<tr><td><b>" + (r.username ? "@" + esc(r.username) : "-") + "</b></td><td>" + esc(r.flow_name || "-") + "</td>" +
          "<td>" + (r.follows ? '<span class="pill green">Yes</span>' : '<span class="pill">-</span>') + "</td>" +
          "<td>" + (r.link_sent ? '<span class="pill green">Sent</span>' : '<span class="pill">-</span>') + "</td>" +
          "<td>" + ago(r.last_seen) + "</td></tr>";
      }).join("");
    }
    paint("");
    $("#cSearch").addEventListener("input", function (e) { paint(e.target.value.trim().toLowerCase()); });
  }

  // ------------------------------------------------------------ SETTINGS
  async function viewSettings() {
    var ig = S.ig, p = S.plan, lim = p.limits;
    var igCard = '<div class="card pad set-card"><h3>Instagram</h3><p>The account your automations reply from.</p>' +
      (ig.connected
        ? '<div class="acct-strip" style="padding:0">' + (ig.picture ? '<img src="' + esc(ig.picture) + '" alt="" referrerpolicy="no-referrer">' : "") +
          "<div><b>@" + esc(ig.username) + '</b><div class="meta">' + esc(ig.name || "") + "</div></div></div>" +
          '<dl class="kv"><dt>Status</dt><dd><span class="pill green">' + I.check + " Connected</span></dd>" +
          "<dt>Account type</dt><dd>" + esc((ig.account_type || "").toLowerCase().replace("media_creator", "creator")) + "</dd>" +
          "<dt>Followers</dt><dd>" + num(ig.followers) + "</dd><dt>Connected</dt><dd>" + day(ig.connected_at) + "</dd>" +
          "<dt>Last checked</dt><dd>" + ago(ig.checked_at) + "</dd></dl>" +
          '<div class="row"><button class="btn" data-act="refresh">Check connection</button><button class="btn btn-danger" data-act="disconnect">Disconnect</button></div>'
        : '<p class="hint" style="margin-bottom:16px">' + (ig.status === "expired" ? esc(ig.note || "The saved login stopped working.") : "Nothing is connected.") + "</p>" +
          (S.igReady ? '<a class="btn btn-green" href="/connect/instagram">Connect Instagram</a>' : '<div class="errbox">Instagram is not set up on this platform yet.</div>')) +
      "</div>";
    $("#view").innerHTML = '<div class="set-grid">' + igCard +
      '<div class="card pad set-card"><h3>Plan</h3><p>What your workspace can do.</p>' +
      '<dl class="kv"><dt>Plan</dt><dd>' + esc(p.name) + "</dd><dt>Automations</dt><dd>" + cap(lim.automations) + " live</dd>" +
      "<dt>DMs a month</dt><dd>" + num(S.usage.dms) + " of " + cap(lim.dms_per_month) + "</dd>" +
      "<dt>Contacts</dt><dd>" + num(S.usage.contacts) + " of " + cap(lim.contacts) + "</dd></dl>" +
      '<a class="btn" href="/pricing" target="_blank" rel="noopener">See plans</a></div>' +
      '<div class="card pad set-card"><h3>Profile</h3><p>Your login.</p>' +
      '<div class="field"><label>Name</label><input class="input" id="pName" value="' + esc(S.me.name || "") + '"></div>' +
      '<div class="field"><label>Email</label><input class="input" value="' + esc(S.me.email) + '" disabled></div>' +
      '<button class="btn btn-primary" data-act="saveName">Save</button></div>' +
      '<div class="card pad set-card"><h3>Password</h3><p>Changing it signs you out everywhere.</p>' +
      '<div class="field"><label>Current password</label><input class="input" type="password" id="pCur" autocomplete="current-password"></div>' +
      '<div class="field"><label>New password</label><input class="input" type="password" id="pNew" autocomplete="new-password"><small>At least 8 characters</small></div>' +
      '<button class="btn btn-primary" data-act="savePw">Change password</button></div></div>';
  }

  function disconnectFlow() {
    var m = modal("<h3>Disconnect @" + esc(S.ig.username) + "?</h3><p>This is a real disconnect, done through Instagram's API:</p>" +
      "<ul><li>Instagram stops sending this account's comments and messages to DM Flow</li>" +
      "<li>Instagram is asked to remove DM Flow's permissions</li>" +
      "<li>The saved access token and profile are deleted</li><li>Your live automations are paused (not deleted)</li></ul>" +
      '<div class="row"><button class="btn" data-x>Cancel</button><button class="btn btn-danger" data-go>Disconnect</button></div>');
    $("[data-x]", m).onclick = function () { m.remove(); };
    $("[data-go]", m).onclick = async function () {
      this.disabled = true; this.textContent = "Disconnecting...";
      var out = await api("/api/instagram/disconnect", { method: "POST" });
      var r = out.report || {};
      m.querySelector(".modal").innerHTML = "<h3>Disconnected</h3><p>Here is exactly what happened:</p><ul>" +
        "<li>Webhooks: " + (r.unsubscribed === true ? "stopped" : esc(r.unsubscribed == null ? "no token was saved" : "Instagram said: " + r.unsubscribed)) + "</li>" +
        "<li>Permissions: " + (r.revoked === true ? "removed by Instagram" : esc(r.revoked == null ? "-" : "Instagram said: " + r.revoked)) + "</li>" +
        "<li>Token and profile: deleted from DM Flow</li></ul>" +
        '<p class="hint">To also remove DM Flow from Instagram\'s side, open Instagram > Settings > Apps and websites and remove it there.</p>' +
        '<div class="row"><button class="btn btn-primary" data-x>Done</button></div>';
      $("[data-x]", m).onclick = function () { m.remove(); };
      await loadMe(); route();
    };
  }

  // ------------------------------------------------------------ actions
  document.addEventListener("click", async function (e) {
    var t = e.target.closest("[data-act],[data-preset],[data-menu]");
    if (!t) return;
    if (t.dataset.preset) return openWizard(null, PRESETS[t.dataset.preset].body);
    if (t.dataset.menu) {
      var id = t.dataset.menu, f = S.flows.find(function (x) { return x.id === id; });
      $$(".pop").forEach(function (p) { p.remove(); });
      var pop = document.createElement("div"); pop.className = "pop";
      pop.innerHTML = '<button data-edit>Edit</button><button class="danger" data-del>Delete</button>';
      t.parentNode.appendChild(pop);
      $("[data-edit]", pop).onclick = function () { pop.remove(); openWizard(f); };
      $("[data-del]", pop).onclick = function () {
        pop.remove();
        var m = modal("<h3>Delete this automation?</h3><p>" + esc(f.name) + " will stop and cannot be restored. Contacts it captured are kept.</p>" +
          '<div class="row"><button class="btn" data-x>Cancel</button><button class="btn btn-danger" data-go>Delete</button></div>');
        $("[data-x]", m).onclick = function () { m.remove(); };
        $("[data-go]", m).onclick = async function () { await api("/api/flows/" + id, { method: "DELETE" }); m.remove(); toast("Deleted"); await loadMe(); route(); };
      };
      return;
    }
    var act = t.dataset.act;
    if (act === "new") return openWizard(null, {});
    if (act === "refresh") {
      t.disabled = true;
      var o = await api("/api/instagram?refresh=1");
      if (o.success) S.ig = o.instagram;
      paintSide(); toast(S.ig.connected ? "Instagram answered - connection is working" : "Instagram did not accept the connection", !S.ig.connected);
      return route();
    }
    if (act === "disconnect") return disconnectFlow();
    if (act === "poll") {
      t.disabled = true; t.textContent = "Checking...";
      var p = await api("/api/poll-now", { method: "POST" });
      if (!p.success) toast(p.error, true);
      else toast(p.stats.primed ? "First look at your posts - existing comments are marked as already seen." :
        p.stats.new ? p.stats.new + " new comment(s) handled" : "No new comments on watched posts");
      await loadMe(); return route();
    }
    if (act === "saveName") {
      var r = await api("/api/me", { method: "POST", body: { name: $("#pName").value } });
      if (r.success) { await loadMe(); toast("Saved"); } else toast(r.error, true);
      return;
    }
    if (act === "savePw") {
      var r2 = await api("/api/me", { method: "POST", body: { current_password: $("#pCur").value, new_password: $("#pNew").value } });
      if (r2.success) { toast(r2.message || "Password changed"); setTimeout(function () { location.href = "/login"; }, 1200); }
      else toast(r2.error, true);
    }
  });

  document.addEventListener("change", async function (e) {
    var t = e.target;
    if (!t.dataset.toggle) return;
    t.disabled = true;
    var out = await api("/api/flows/" + t.dataset.toggle + "/status", { method: "POST", body: { live: t.checked } });
    t.disabled = false;
    if (!out.success) { t.checked = !t.checked; return toast(out.error, true); }
    toast(t.checked ? "Live - comments on that post now get a DM" : "Paused");
    await loadMe();
  });

  // ============================================================ WIZARD
  var W = null;
  var STEPS = [
    { t: "First, pick a post", s: "Build your automation ...and see it come to life" },
    { t: "Now, set a keyword", s: "What should a comment say to start the conversation?" },
    { t: "Tweak the opening DM", s: "Ask first! It's polite, and it's what lets the link and the follow check through." },
    { t: "Finally, send the link", s: "What they get after tapping the button." }
  ];

  function deepMerge(base, patch) {
    var out = clone(base);
    Object.keys(patch || {}).forEach(function (k) {
      if (patch[k] && typeof patch[k] === "object" && !Array.isArray(patch[k]) && out[k] && typeof out[k] === "object") out[k] = deepMerge(out[k], patch[k]);
      else out[k] = patch[k];
    });
    return out;
  }

  async function openWizard(flow, preset) {
    if (!S.template) await loadFlows();
    W = { id: flow ? flow.id : null, name: flow ? flow.name : "", step: 1, err: "", showAll: false, saving: false,
          b: flow ? clone(flow.body) : deepMerge(S.template, preset || {}) };
    $("#wiz").hidden = false; document.body.style.overflow = "hidden";
    renderWizard();
    if (S.ig.connected) { await loadMedia(); if (W && W.step === 1) renderWizard(); }
  }
  function closeWizard() { W = null; $("#wiz").hidden = true; $("#wiz").innerHTML = ""; document.body.style.overflow = ""; }

  function opt(name, val, label, body, extra) {
    var on = name === val;
    return '<div class="opt' + (on ? " on" : "") + '"><label data-pick="' + esc(label[0]) + '"><span class="radio"></span>' + esc(label[1]) +
      (extra || "") + "</label>" + (on && body ? '<div class="opt-body">' + body + "</div>" : "") + "</div>";
  }
  function counter(v, max) { return '<div class="count">' + (v || "").length + " / " + max + "</div>"; }

  function stepForm() {
    var b = W.b;
    if (W.step === 1) {
      var media = S.media || [], shown = W.showAll ? media : media.slice(0, 8);
      var grid = !S.ig.connected ? '<div class="errbox">Connect Instagram first to pick one of your posts.</div>'
        : !S.media ? '<div class="hint">Loading your posts...</div>'
        : !media.length ? '<div class="hint">No posts found on this account.</div>'
        : '<div class="media-grid">' + shown.map(function (m) {
            var th = m.thumbnail_url || m.media_url || "";
            return '<button class="media' + (b.post.media_id === m.id ? " on" : "") + '" data-media="' + esc(m.id) + '" style="background-image:url(\'' + esc(th) + '\')" title="' + esc((m.caption || "").slice(0, 80)) + '">' +
              (m.media_product_type === "REELS" ? '<span class="tag">REEL</span>' : "") + "</button>";
          }).join("") + "</div>" + (media.length > 8 ? '<a class="link" href="#" data-showall>' + (W.showAll ? "Show less" : "Show all " + media.length) + "</a>" : "");
      var anyOk = S.plan.features && S.plan.features.any_post;
      return "<h3>When someone comments on</h3>" +
        opt(b.post.mode, "specific", ["post:specific", "a specific post or reel"], grid) +
        opt(b.post.mode, "any", ["post:any", "any post or reel"], '<div class="hint">Every post you have published, and every new one.</div>',
          anyOk ? "" : '<span class="pill amber">Upgrade</span>');
    }
    if (W.step === 2) {
      var chips = '<div class="chips" id="chips">' + b.trigger.keywords.map(function (k, i) {
        return '<span class="chip">' + esc(k) + '<button data-rmkw="' + i + '" aria-label="Remove">&times;</button></span>';
      }).join("") + '<input id="kwIn" placeholder="' + (b.trigger.keywords.length ? "Add another" : "Type a word, press Enter") + '"></div>' +
        '<div class="hint">Matches the whole word, any case - "LINK please" matches link.</div>';
      var replies = '<label class="tog">Reply to their comment under the post<span class="switch"><input type="checkbox" data-bind="public_reply.on"' + (b.public_reply.on ? " checked" : "") + "><span></span></span></label>" +
        (b.public_reply.on ? [0, 1, 2].map(function (i) {
          return '<input class="input" data-variant="' + i + '" maxlength="200" placeholder="Reply ' + (i + 1) + (i ? " (optional)" : "") + '" value="' + esc(b.public_reply.variants[i] || "") + '">';
        }).join("") + '<div class="hint">One is picked at random each time, so the replies do not all look identical.</div>' : "");
      return "<h3>And this comment has</h3>" +
        opt(b.trigger.mode, "keyword", ["trig:keyword", "a specific word"], chips) +
        opt(b.trigger.mode, "any", ["trig:any", "any word or emoji"], '<div class="hint">Every comment starts the conversation.</div>') +
        '<div class="opt on">' + replies + "</div>";
    }
    if (W.step === 3) {
      var opening = b.opening.on
        ? '<textarea class="area" data-bind="opening.text" maxlength="640">' + esc(b.opening.text) + "</textarea>" + counter(b.opening.text, 640) +
          '<input class="input" data-bind="opening.button" maxlength="20" value="' + esc(b.opening.button) + '">' + counter(b.opening.button, 20) +
          '<div class="why">Why an opening DM? Instagram lets a comment get one private message. A tap on this button starts a real conversation, which is what allows the link and the follow check.</div>'
        : '<div class="hint">The link is sent straight away in the one private reply Instagram allows. No follow check is possible this way.</div>';
      if (b.follow_gate.on) opening += '<div class="hint">Required while the follow check is on - following can only be checked after they tap.</div>';
      var follow = '<label class="tog">Ask them to follow you before they get the link<span class="switch"><input type="checkbox" data-bind="follow_gate.on"' + (b.follow_gate.on ? " checked" : "") + "><span></span></span></label>" +
        (b.follow_gate.on ? '<textarea class="area" data-bind="follow_gate.text" maxlength="640">' + esc(b.follow_gate.text) + "</textarea>" + counter(b.follow_gate.text, 640) +
          '<input class="input" data-bind="follow_gate.button" maxlength="20" value="' + esc(b.follow_gate.button) + '">' + counter(b.follow_gate.button, 20) +
          '<div class="hint">They also get an "Open profile" button. Tapping yours checks again.</div>' : "");
      return "<h3>They will get</h3>" +
        '<div class="opt on"><label class="tog">An opening DM with a button<span class="switch"><input type="checkbox" data-bind="opening.on"' + (b.opening.on ? " checked" : "") + (b.follow_gate.on ? " disabled" : "") + '><span></span></span></label><div class="opt-body">' + opening + "</div></div>" +
        '<div class="opt on">' + follow + "</div>";
    }
    return "<h3>After they tap, they get</h3>" +
      '<div class="field"><label>Message</label><textarea class="area" data-bind="link.text" maxlength="640">' + esc(b.link.text) + "</textarea>" + counter(b.link.text, 640) + "</div>" +
      '<div class="field"><label>Button label</label><input class="input" data-bind="link.button" maxlength="20" value="' + esc(b.link.button) + '">' + counter(b.link.button, 20) + "</div>" +
      '<div class="field"><label>Link</label><input class="input" data-bind="link.url" placeholder="https://yourstore.com/product" value="' + esc(b.link.url) + '"></div>' +
      '<div class="field"><label>Name this automation</label><input class="input" id="wName" maxlength="60" placeholder="e.g. Diwali sale reel" value="' + esc(W.name) + '"><small>Only you see this.</small></div>';
  }

  function preview() {
    var b = W.b, ig = S.ig, user = ig.username || "yourbrand";
    var av = ig.picture ? "background-image:url('" + esc(ig.picture) + "')" : "";
    var head = '<div class="sbar"><span>9:41</span><i></i><span>5G</span></div>';
    if (W.step <= 2) {
      var m = (S.media || []).find(function (x) { return x.id === b.post.media_id; });
      var th = b.post.mode === "specific" ? (m ? (m.thumbnail_url || m.media_url) : b.post.thumb) : "";
      var comment = b.trigger.mode === "any" ? "Leaves any comment" : (b.trigger.keywords[0] || "your keyword");
      var reply = b.public_reply.on ? (b.public_reply.variants[0] || "...") : "";
      return head + '<div class="p-head"><span class="p-av" style="' + av + '"></span><b>' + esc(user) + "</b></div>" +
        '<div class="p-post" style="' + (th ? "background-image:url('" + esc(th) + "')" : "") + '">' + (th ? "" : (b.post.mode === "any" ? "Any post or reel" : "Pick a post")) + "</div>" +
        '<div class="p-comments"><h5>Comments</h5>' +
        '<div class="p-c"><span class="p-av"></span><div><b>username</b> <small>now</small><p>' + esc(comment) + "</p></div></div>" +
        (reply ? '<div class="p-c reply"><span class="p-av" style="' + av + '"></span><div><b>' + esc(user) + "</b> <small>now</small><p>" + esc(reply) + "</p></div></div>" : "") +
        "</div>";
    }
    var msgs = "";
    if (b.opening.on) {
      msgs += '<div class="b-in">' + esc(b.opening.text) + '<div class="b-btn">' + esc(b.opening.button) + "</div></div>" +
        '<div class="b-out">' + esc(b.opening.button) + "</div>";
      if (b.follow_gate.on) {
        msgs += '<div class="b-in">' + esc(b.follow_gate.text) + '<div class="b-btn">Open profile</div><div class="b-btn">' + esc(b.follow_gate.button) + "</div></div>" +
          '<div class="b-note">they follow you</div><div class="b-out">' + esc(b.follow_gate.button) + "</div>";
      }
    }
    if (W.step === 4 || !b.opening.on) {
      msgs += '<div class="b-in">' + esc(b.link.text) + '<div class="b-btn">' + esc(b.link.button || "Open link") + "</div></div>";
    }
    return head + '<div class="p-head"><span class="p-av" style="' + av + '"></span><b>' + esc(user) + "</b></div>" +
      '<div class="p-dm">' + msgs + '</div><div class="p-input">Message...</div>';
  }

  function stepError() {
    var b = W.b;
    if (W.step === 1 && b.post.mode === "specific" && !b.post.media_id) return "Pick the post this automation should watch.";
    if (W.step === 1 && b.post.mode === "any" && !(S.plan.features || {}).any_post) return "'Any post' needs a higher plan. Pick a specific post.";
    if (W.step === 2 && b.trigger.mode === "keyword" && !b.trigger.keywords.length) return "Add at least one keyword, or choose any word.";
    if (W.step === 2 && b.public_reply.on && !b.public_reply.variants.filter(Boolean).length) return "Write a public reply, or switch it off.";
    if (W.step === 3 && b.opening.on && (!b.opening.text.trim() || !b.opening.button.trim())) return "The opening DM needs a message and a button label.";
    if (W.step === 3 && b.follow_gate.on && (!b.follow_gate.text.trim() || !b.follow_gate.button.trim())) return "The follow request needs a message and a button label.";
    return "";
  }

  function renderWizard() {
    if (!W) return;
    var st = STEPS[W.step - 1];
    $("#wiz").innerHTML = '<div class="wiz-top"><span></span><div class="steps">' + [1, 2, 3, 4].map(function (i) {
        return '<i class="' + (i <= W.step ? "on" : "") + '"></i>'; }).join("") +
      '</div><button class="btn btn-ghost x" data-wclose>' + I.x + "</button></div>" +
      '<div class="wiz-head"><h2>' + esc(st.t) + "</h2><p>" + esc(st.s) + "</p></div>" +
      '<div class="wiz-body"><div class="wiz-form">' + stepForm() +
      (W.err ? '<div class="errbox">' + esc(W.err) + "</div>" : "") +
      '<div class="wiz-nav"><button class="btn" data-wback>' + (W.step === 1 ? "Cancel" : "Back") + "</button>" +
      (W.step < 4 ? '<button class="btn btn-primary" data-wnext>Next</button>'
        : '<span class="row"><button class="btn" data-wsave="draft">Save draft</button><button class="btn btn-green" data-wsave="live"' + (S.ig.connected ? "" : " disabled title=\"Connect Instagram first\"") + ">Go live</button></span>") +
      "</div></div>" +
      '<div class="wiz-prev"><span>Preview</span><div class="phone"><div class="screen">' + preview() + "</div></div></div></div>";
    var kw = $("#kwIn");
    if (kw) kw.addEventListener("keydown", function (e) {
      if ((e.key === "Enter" || e.key === ",") && kw.value.trim()) {
        e.preventDefault();
        var v = kw.value.replace(/,/g, "").trim();
        if (v && W.b.trigger.keywords.indexOf(v) < 0) W.b.trigger.keywords.push(v);
        W.err = ""; renderWizard(); $("#kwIn") && $("#kwIn").focus();
      } else if (e.key === "Backspace" && !kw.value && W.b.trigger.keywords.length) {
        W.b.trigger.keywords.pop(); renderWizard(); $("#kwIn") && $("#kwIn").focus();
      }
    });
  }

  function setPath(obj, path, val) {
    var parts = path.split("."), o = obj;
    for (var i = 0; i < parts.length - 1; i++) o = o[parts[i]];
    o[parts[parts.length - 1]] = val;
  }
  function refreshPreview() { var s = $(".screen"); if (s) s.innerHTML = preview(); }

  $("#wiz").addEventListener("input", function (e) {
    if (!W) return;
    var t = e.target;
    if (t.dataset.bind && t.type !== "checkbox") {
      setPath(W.b, t.dataset.bind, t.value);
      var c = t.nextElementSibling; if (c && c.classList.contains("count")) c.textContent = t.value.length + " / " + (t.maxLength > 0 ? t.maxLength : "");
      refreshPreview();
    }
    if (t.dataset.variant !== undefined) {
      var v = W.b.public_reply.variants; v[Number(t.dataset.variant)] = t.value;
      W.b.public_reply.variants = [v[0] || "", v[1] || "", v[2] || ""];
      refreshPreview();
    }
    if (t.id === "wName") W.name = t.value;
  });
  $("#wiz").addEventListener("change", function (e) {
    if (!W) return;
    var t = e.target;
    if (t.dataset.bind && t.type === "checkbox") {
      setPath(W.b, t.dataset.bind, t.checked);
      if (t.dataset.bind === "follow_gate.on" && t.checked) W.b.opening.on = true;
      W.err = ""; renderWizard();
    }
  });
  $("#wiz").addEventListener("click", async function (e) {
    if (!W) return;
    var t = e.target.closest("[data-pick],[data-media],[data-showall],[data-rmkw],[data-wnext],[data-wback],[data-wclose],[data-wsave]");
    if (!t) return;
    if (t.dataset.pick) {
      var p = t.dataset.pick.split(":");
      if (p[0] === "post") W.b.post.mode = p[1]; else W.b.trigger.mode = p[1];
      W.err = ""; return renderWizard();
    }
    if (t.dataset.media) {
      var m = (S.media || []).find(function (x) { return x.id === t.dataset.media; }) || {};
      W.b.post.media_id = m.id; W.b.post.thumb = m.thumbnail_url || m.media_url || "";
      W.b.post.caption = (m.caption || "").slice(0, 200); W.b.post.permalink = m.permalink || "";
      W.err = ""; return renderWizard();
    }
    if (t.dataset.showall !== undefined) { e.preventDefault(); W.showAll = !W.showAll; return renderWizard(); }
    if (t.dataset.rmkw !== undefined) { W.b.trigger.keywords.splice(Number(t.dataset.rmkw), 1); return renderWizard(); }
    if (t.dataset.wclose !== undefined) return closeWizard();
    if (t.dataset.wback !== undefined) { if (W.step === 1) return closeWizard(); W.step--; W.err = ""; return renderWizard(); }
    if (t.dataset.wnext !== undefined) {
      var kwIn = $("#kwIn");
      if (kwIn && kwIn.value.trim()) { var v = kwIn.value.trim(); if (W.b.trigger.keywords.indexOf(v) < 0) W.b.trigger.keywords.push(v); }
      W.err = stepError(); if (W.err) return renderWizard();
      W.step++; return renderWizard();
    }
    if (t.dataset.wsave) {
      if (W.saving) return;
      W.saving = true; t.disabled = true;
      var body = clone(W.b); body.public_reply.variants = body.public_reply.variants.filter(function (x) { return x && x.trim(); });
      var out = await api(W.id ? "/api/flows/" + W.id : "/api/flows", { method: W.id ? "PUT" : "POST",
        body: { name: W.name, body: body, live: t.dataset.wsave === "live" } });
      W.saving = false;
      if (!out.success) { W.err = (out.errors || [out.error]).join(" "); t.disabled = false; return renderWizard(); }
      var live = t.dataset.wsave === "live";
      closeWizard(); await loadMe();
      toast(live ? "Live! Comments matching it now get a DM." : "Saved as a draft");
      go("/app/automations");
    }
  });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape" && W) closeWizard(); });

  // ------------------------------------------------------------ boot
  (async function boot() {
    if (!(await loadMe())) return;
    var q = new URLSearchParams(location.search);
    if (q.get("connected")) {
      toast("Instagram connected as @" + (S.ig.username || ""));
      history.replaceState({}, "", location.pathname);
    }
    route();
  })();
})();
