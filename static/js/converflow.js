/* =============================================================================
   ConverFlow v3 — Instagram connect, Plan & billing, Broadcast, Analytics
   Loaded after app.js; owns only the views app.js does not touch.
   ========================================================================== */
(function () {
  "use strict";

  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };

  var STATE = { billing: null, plans: [], targets: 0, stream: null, insights: null, upgradeTarget: null };

  function inr(n) { return "₹" + Number(n || 0).toLocaleString("en-IN"); }
  function num(n) { return Number(n || 0).toLocaleString("en-IN"); }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function limitLabel(v) { return v === -1 ? "Unlimited" : num(v); }

  async function api(url, opts) {
    var res = await fetch(url, Object.assign({ headers: { "Content-Type": "application/json" } }, opts || {}));
    return res.json();
  }

  function flash(msg, bad) {
    var t = $("#cfToast");
    if (!t) {
      t = document.createElement("div");
      t.id = "cfToast";
      t.style.cssText = "position:fixed;bottom:22px;left:50%;transform:translate(-50%,140%);z-index:999;" +
        "background:#0b0f14;color:#fff;padding:12px 20px;border-radius:999px;font-size:13.5px;font-weight:700;" +
        "box-shadow:0 18px 44px rgba(11,15,20,.22);transition:transform .3s cubic-bezier(.2,.8,.2,1);font-family:inherit";
      document.body.appendChild(t);
    }
    t.textContent = msg;
    t.style.background = bad ? "#e5484d" : "#0b0f14";
    t.style.transform = "translate(-50%,0)";
    clearTimeout(t._timer);
    t._timer = setTimeout(function () { t.style.transform = "translate(-50%,140%)"; }, 2800);
  }

  // ===================================================== Instagram connect
  async function renderConnect() {
    var card = $("#connectCard");
    if (!card) return;
    var out = await api("/api/instagram/status");
    var ig = out.instagram || {};

    // Instagram SVG icon used across all states
    var igIcon = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="20" rx="5.5"/><circle cx="12" cy="12" r="4"/><circle cx="17.5" cy="6.5" r="1.2" fill="currentColor"/></svg>';

    if (ig.connected) {
      card.className = "connect-card is-live";
      card.innerHTML =
        '<div class="connect-badge ig-gradient">' + igIcon + '</div>' +
        '<div class="connect-copy"><h3>@' + esc(ig.username || "") + ' is connected</h3>' +
        '<p>' + (ig.followers ? num(ig.followers) + " followers · " : "") +
        'Comment and DM triggers are being delivered through the official Instagram API.</p></div>' +
        '<div class="connect-actions">' +
        '<button class="btn btn-secondary btn-sm" id="igDisconnect">Disconnect</button></div>';
    } else if (!out.platform_ready) {
      card.className = "connect-card";
      card.innerHTML =
        '<div class="connect-badge" style="background:#eef1f4;color:#8b95a3"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg></div>' +
        '<div class="connect-copy"><h3>Connect your Instagram account</h3>' +
        '<p>Connect with your Meta Page Access Token, or use browser sign-in below.</p></div>' +
        '<div class="connect-actions">' +
        '<button class="btn btn-primary" id="btnConnectToken">Connect with Access Token</button>' +
        '</div>';
    } else {
      card.className = "connect-card";
      card.innerHTML =
        '<div class="connect-badge ig-gradient">' + igIcon + '</div>' +
        '<div class="connect-copy"><h3>Connect your Instagram account</h3>' +
        '<p>One click — log in with your Instagram credentials. You need a Business or Creator account.</p></div>' +
        '<div class="connect-actions" style="display:flex;gap:8px;flex-wrap:wrap;">' +
        '<button class="btn btn-ig" id="igConnect"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" style="margin-right:6px;vertical-align:-2px"><rect x="2" y="2" width="20" height="20" rx="5.5"/><circle cx="12" cy="12" r="4"/><circle cx="17.5" cy="6.5" r="1.2" fill="currentColor"/></svg>Connect with Instagram</button>' +
        '<button class="btn btn-secondary btn-sm" id="btnConnectToken">Paste Access Token</button>' +
        '</div>';
    }
  }


  document.addEventListener("click", async function (ev) {
    if (ev.target.closest("#btnConnectToken")) {
      var token = window.prompt("Paste your Meta / Facebook Page Access Token:");
      if (!token || !token.trim()) return;
      var btn = ev.target.closest("#btnConnectToken");
      btn.disabled = true; btn.textContent = "Connecting…";
      var out = await api("/api/instagram/connect-token", {
        method: "POST",
        body: JSON.stringify({ access_token: token.trim() })
      });
      if (out.success) {
        flash(out.message || "Connected to @" + (out.account ? out.account.ig_username : "Instagram") + "!");
        renderConnect();
      } else {
        flash(out.error || out.message || "Could not connect with this token", true);
        btn.disabled = false; btn.textContent = "Paste Access Token";
      }
      return;
    }
    if (ev.target.closest("#igConnect")) {
      var btn = ev.target.closest("#igConnect");
      btn.disabled = true; btn.textContent = "Opening Instagram…";
      var out = await api("/api/instagram/connect");
      if (out.success) { window.location.href = out.url; }
      else { flash(out.error, true); btn.disabled = false; btn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" style="margin-right:6px;vertical-align:-2px"><rect x="2" y="2" width="20" height="20" rx="5.5"/><circle cx="12" cy="12" r="4"/><circle cx="17.5" cy="6.5" r="1.2" fill="currentColor"/></svg>Connect with Instagram'; }
      return;
    }
    if (ev.target.closest("#igDisconnect")) {
      if (!window.confirm("Disconnect Instagram? Your automations will stop firing.")) return;
      await api("/api/instagram/disconnect", { method: "POST" });
      flash("Instagram disconnected");
      renderConnect();
      return;
    }
  });

  // ========================================================= Plan & billing
  async function renderBilling() {
    var out = await api("/api/billing/status");
    STATE.billing = out.billing;
    STATE.plans = out.plans || [];
    var b = out.billing;

    var hero = $("#planHero");
    if (hero) {
      var sub = b.state === "trialing"
        ? b.days_left + " days left on your trial"
        : b.state === "expired"
        ? "Your trial has ended — automations are paused"
        : b.renews_on
        ? "Renews on " + new Date(String(b.renews_on).replace(" ", "T")).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })
        : "No renewal — this plan is free";
      hero.innerHTML =
        '<div><span class="plan-chip">' + esc(b.badge || "") + '</span>' +
        '<h3 style="margin-top:10px">' + esc(b.plan_name) + '</h3>' +
        '<p>' + esc(sub) + '</p></div>' +
        '<div class="spacer"></div>' +
        '<div style="text-align:right"><div style="font-size:26px;font-weight:800;letter-spacing:-.04em">' +
        inr(b.price_monthly) + '<span style="font-size:13px;opacity:.6">/mo</span></div></div>';
    }

    var grid = $("#usageGrid");
    if (grid) {
      var names = {
        automations: "Active automations", contacts: "Contacts stored",
        dms_per_month: "DMs this month", ig_accounts: "Instagram accounts", team_seats: "Team seats"
      };
      grid.innerHTML = Object.keys(b.usage || {}).map(function (key) {
        var u = b.usage[key];
        var cls = u.over ? "over" : u.percent >= 80 ? "warn" : "";
        return '<div class="usage-tile"><div class="label">' + esc(names[key] || key) + '</div>' +
          '<div class="value">' + num(u.used) + ' <small>/ ' + limitLabel(u.limit) + '</small></div>' +
          '<div class="meter ' + cls + '"><i style="width:' + (u.unlimited ? 6 : u.percent) + '%"></i></div></div>';
      }).join("");
    }

    syncSidebar(b);

    var picker = $("#planPicker");
    if (picker) {
      picker.innerHTML = STATE.plans.map(function (p) {
        var current = p.id === b.plan_id;
        var perks = Object.keys(p.features || {}).filter(function (k) { return p.features[k]; }).slice(0, 5);
        return '<div class="pick-card' + (current ? " current" : "") + '">' +
          (p.badge ? '<span class="pick-flag">' + esc(p.badge) + '</span>' : "") +
          '<h4>' + esc(p.name) + '</h4>' +
          '<div class="price"><b>' + inr(p.price_monthly) + '</b><span>/mo</span></div>' +
          '<ul>' +
            '<li><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>' +
              limitLabel(p.limits.automations) + ' automations</li>' +
            '<li><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>' +
              limitLabel(p.limits.contacts) + ' contacts</li>' +
            '<li><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>' +
              limitLabel(p.limits.dms_per_month) + ' DMs / month</li>' +
            (p.features.broadcast ? '<li><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>Broadcast engine</li>' : "") +
            (p.features.ai_assist ? '<li><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>AI flow generator</li>' : "") +
          '</ul>' +
          (current
            ? '<button class="btn btn-secondary btn-sm btn-block" disabled>Current plan</button>'
            : '<button class="btn btn-primary btn-sm btn-block" data-pick="' + p.id + '">' +
              (p.price_monthly === 0 ? "Switch to Free" : "Choose " + esc(p.name)) + '</button>') +
          '</div>';
      }).join("");
    }
  }

  document.addEventListener("click", async function (ev) {
    var pick = ev.target.closest("[data-pick]");
    if (pick) {
      var planId = pick.dataset.pick;
      var coupon = ($("#couponCode") && $("#couponCode").value.trim()) || null;
      pick.disabled = true; pick.textContent = "Switching…";
      var out = await api("/api/billing/upgrade", { method: "POST", body: JSON.stringify({ plan_id: planId, coupon: coupon }) });
      if (!out.success) { flash(out.error || "Could not switch plan", true); pick.disabled = false; return; }
      flash("You're on the " + out.billing.plan_name + " plan");
      renderBilling();
      return;
    }
    if (ev.target.closest("#couponApply")) {
      var code = $("#couponCode").value.trim();
      if (!code) { flash("Type a code first", true); return; }
      var planId = STATE.billing ? STATE.billing.plan_id : "growth";
      var r = await api("/api/billing/coupon", { method: "POST", body: JSON.stringify({ code: code, plan_id: planId }) });
      var box = $("#couponResult");
      if (!r.valid) box.innerHTML = '<span style="color:var(--mc-coral);font-weight:700">' + esc(r.error) + '</span>';
      else if (r.trial_days) box.innerHTML = '<b style="color:var(--mc-green)">+' + r.trial_days + ' trial days</b> — pick a plan to apply it';
      else box.innerHTML = '<s>' + inr(r.original_price) + '</s> → <b style="color:var(--mc-green);font-size:15px">' +
        inr(r.final_price) + '</b> <span style="color:var(--text-faint)">(' + inr(r.discount) + ' off)</span>';
      return;
    }
  });

  // Keep the sidebar plan chip and the contacts meter honest.
  function syncSidebar(b) {
    var badge = $("#sidebarPlanBadge");
    if (badge) {
      badge.textContent = b.badge || b.plan_name;
      badge.style.cssText = b.state === "expired"
        ? "background:#fef1f1;color:#e5484d"
        : b.is_paid ? "background:#e8f5ee;color:#00824b" : "";
    }
    var count = $("#sidebarLimitCount");
    if (count && b.usage && b.usage.contacts) {
      var u = b.usage.contacts;
      count.textContent = num(u.used) + " / " + limitLabel(u.limit);
    }
    var label = document.querySelector(".limit-label");
    if (label) label.textContent = b.plan_name + " contacts";

    // the mobile header carries its own badge
    var mob = document.querySelector(".mobile-badge-free");
    if (mob) {
      mob.textContent = b.badge || b.plan_name;
      if (b.is_paid) mob.style.cssText = "background:#e8f5ee;color:#00824b";
    }
  }

  // ============================================================= broadcast
  function bcLog(level, text) {
    var box = $("#bcLog");
    if (!box) return;
    var colour = { SUCCESS: "#00824b", ERROR: "#e5484d", WARN: "#b45309" }[level] || "#5b6673";
    var row = document.createElement("div");
    row.style.cssText = "color:" + colour + ";line-height:1.5;flex-shrink:0";
    row.textContent = "› " + text;
    box.appendChild(row);
    box.scrollTop = box.scrollHeight;
  }

  async function renderBroadcast() {
    var out = await api("/api/billing/status");
    var allowed = (out.billing.features || {}).broadcast;
    var lock = $("#bcLock");
    if (lock) {
      lock.style.display = allowed ? "none" : "flex";
      if (!allowed) {
        var upsell = (out.plans || []).find(function (p) { return p.features && p.features.broadcast; });
        $("#bcLockText").innerHTML = "Broadcast is not on the <strong>" + esc(out.billing.plan_name) +
          "</strong> plan." + (upsell ? " It's included from <strong>" + esc(upsell.name) + " — " + inr(upsell.price_monthly) + "/month</strong>." : "");
      }
    }
    ["bcStart", "bcPause", "bcStop"].forEach(function (id) {
      var el = $("#" + id);
      if (el) el.disabled = !allowed;
    });

    var data = await insights(true);
    var cockpit = $("#bcSafety");
    if (cockpit) cockpit.innerHTML = safetyHTML(data.safety);

    var t = await api("/api/targets");
    STATE.targets = (t.targets || []).length;
    var c = $("#bcCount");
    if (c) c.textContent = STATE.targets ? STATE.targets + " leads loaded" : "No leads loaded yet";
  }

  function openStream() {
    if (STATE.stream || !window.EventSource) return;
    try {
      STATE.stream = new EventSource("/api/logs/stream");
      STATE.stream.onmessage = function (e) {
        try {
          var d = JSON.parse(e.data);
          if (d.message) bcLog(d.level, d.message);
          if (d.stats) {
            if ($("#bcSent")) $("#bcSent").textContent = num(d.stats.sent || 0);
            if ($("#bcFailed")) $("#bcFailed").textContent = num(d.stats.failed || 0);
          }
        } catch (_) {}
      };
      STATE.stream.onerror = function () { STATE.stream.close(); STATE.stream = null; };
    } catch (_) {}
  }

  document.addEventListener("click", async function (ev) {
    if (ev.target.closest("#bcLoadText")) {
      var text = $("#bcTargets").value;
      var out = await api("/api/targets/load-text", { method: "POST", body: JSON.stringify({ text: text }) });
      flash((out.count || 0) + " leads loaded");
      renderBroadcast();
      return;
    }
    if (ev.target.closest("#bcClear")) {
      await api("/api/targets/clear", { method: "POST" });
      $("#bcTargets").value = "";
      flash("Lead list cleared");
      renderBroadcast();
      return;
    }
    if (ev.target.closest("#bcPreview")) {
      var tpl = $("#bcTemplate").value;
      var box = $("#bcPreviewBox");
      box.innerHTML = "";
      for (var i = 0; i < 3; i++) {
        var r = await api("/api/spintax/preview", { method: "POST", body: JSON.stringify({ template: tpl }) });
        var line = document.createElement("div");
        line.className = "bot-bubble";
        line.style.cssText = "max-width:100%;align-self:stretch";
        line.textContent = r.preview || r.result || "";
        box.appendChild(line);
      }
      return;
    }
    if (ev.target.closest("#bcStart")) {
      if (!STATE.targets) { flash("Load a lead list first", true); return; }
      openStream();
      var body = {
        template: $("#bcTemplate").value,
        min_delay: parseInt($("#bcMin").value || 45, 10),
        max_delay: parseInt($("#bcMax").value || 90, 10),
        daily_limit: parseInt($("#bcCap").value || 35, 10),
        headless: false
      };
      var out = await api("/api/campaign/start", { method: "POST", body: JSON.stringify(body) });
      flash(out.success ? "Campaign started" : (out.error || "Could not start"), !out.success);
      bcLog("INFO", "Campaign starting — " + STATE.targets + " leads queued.");
      return;
    }
    if (ev.target.closest("#bcPause")) { await api("/api/campaign/pause", { method: "POST" }); flash("Campaign paused"); return; }
    if (ev.target.closest("#bcStop")) { await api("/api/campaign/stop", { method: "POST" }); flash("Campaign stopped"); return; }
  });

  document.addEventListener("change", async function (ev) {
    if (ev.target.id === "bcCsv" && ev.target.files && ev.target.files[0]) {
      var fd = new FormData();
      fd.append("file", ev.target.files[0]);
      var res = await fetch("/api/targets/upload-csv", { method: "POST", body: fd });
      var out = await res.json();
      flash((out.count || 0) + " leads imported from CSV");
      renderBroadcast();
    }
  });

  // ============================================================= insights
  // Everything below renders /api/insights — the funnel, the safety margin and
  // the 60-second speed line. See COMPETITIVE_STRATEGY.md for why each exists.

  async function insights(force) {
    if (STATE.insights && !force) return STATE.insights;
    STATE.insights = await api("/api/insights");
    return STATE.insights;
  }

  var CHECK_ICON = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>';
  var DOT_ICON = '<svg width="8" height="8" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="12"/></svg>';

  // --- safety cockpit -------------------------------------------------------
  function safetyHTML(sf) {
    function gauge(cap, d) {
      return '<div class="cf-gauge"><div class="cap">' + cap + '</div>' +
        '<div class="fig">' + num(d.used) + ' <small>/ ' + num(d.limit) + '</small></div>' +
        '<div class="track"><i style="width:' + Math.max(2, d.percent) + '%"></i></div></div>';
    }
    return '<div class="cf-safety ' + sf.state + '">' +
      '<div><h4>' + esc(sf.headline) + '</h4><p>' + esc(sf.detail) +
      (sf.your_cap ? ' Your own daily cap is set to ' + num(sf.your_cap) + '.' : '') + '</p></div>' +
      '<div class="cf-gauges">' + gauge("This hour", sf.hour) + gauge("Today", sf.day) + '</div></div>';
  }

  // --- home -----------------------------------------------------------------
  async function renderHome() {
    var data = await insights();
    var f = data.funnel, h = data.health, sp = data.speed;

    var head = $("#cfHeadline"), sub = $("#cfHeadlineSub");
    if (head) {
      var comments = f.stages[0].value, dms = f.stages[1].value;
      if (!comments && !dms) {
        head.textContent = "Nothing has come through yet";
        sub.textContent = "Switch on an automation and your first comment will show up here within seconds.";
      } else {
        head.innerHTML = num(comments) + " comment" + (comments === 1 ? "" : "s") +
          " turned into <b>" + num(dms) + "</b> DM" + (dms === 1 ? "" : "s") + ".";
        sub.textContent = sp.known
          ? "Median reply time " + sp.label + ". " + (sp.fast
              ? "That's inside the 60-second window where intent is still hot."
              : "Automating this trigger would cut it to seconds.")
          : "Reply speed fills in once your first automation fires.";
      }
    }

    var list = $("#cfHealthList");
    if (list) {
      list.innerHTML = h.checks.map(function (c) {
        return '<div class="cf-check' + (c.ok ? " ok" : "") + '">' +
          '<span class="dot">' + (c.ok ? CHECK_ICON : DOT_ICON) + '</span>' +
          '<span><span class="what">' + esc(c.label) + '</span>' +
          (c.ok ? '' : '<span class="fix">' + esc(c.fix) + '</span>') + '</span>' +
          '<span>' + (c.ok
            ? '<span style="font-size:12px;font-weight:700;color:var(--mc-green)">OK</span>'
            : '<span style="font-size:12px;font-weight:700;color:var(--mc-coral)">Fix</span>') + '</span></div>';
      }).join("") +
      '<p style="font-size:12.5px;color:var(--text-faint);margin-top:12px;line-height:1.6">' +
      esc(h.summary) + ' · delivery ' + h.success_rate + '%</p>';
    }

    var safe = $("#cfHomeSafety");
    if (safe) safe.innerHTML = safetyHTML(data.safety);
  }

  // --- analytics ------------------------------------------------------------
  async function renderAnalytics() {
    var data = await insights(true);
    var f = data.funnel;

    var box = $("#anFunnel");
    if (box) {
      box.innerHTML = f.stages.map(function (st) {
        var width = Math.max(24, st.of_top);
        return '<div class="cf-stage">' +
          '<div class="cf-stage-bar' + (st.known ? "" : " unknown") + '" style="width:' + width + '%">' +
          '<b>' + (st.known ? num(st.value) : "—") + '</b><span>' + esc(st.label) + '</span></div>' +
          '<div class="cf-stage-meta">' +
          (st.drop != null && st.drop > 0
            ? '<span class="cf-drop">' + st.drop + '% drop off here</span>' : '') +
          '<span class="cf-stage-hint">' + esc(st.hint) + '</span></div></div>';
      }).join("");
    }

    var conv = $("#anConversion");
    if (conv) {
      conv.innerHTML = f.attribution_ready
        ? '<b>' + f.conversion + '%</b> of comments became orders'
        : 'Tag a contact <b>Converted</b> to start measuring orders';
    }

    var speedBox = $("#anSpeed");
    if (speedBox) {
      var sp = data.speed;
      if (!sp.known) {
        speedBox.innerHTML = '<div class="cf-speed"><div class="cf-speed-dial" style="--dial:0%"><span>—</span></div>' +
          '<div><h4>' + esc(sp.label) + '</h4><p>' + esc(sp.detail) + '</p></div></div>';
      } else {
        var dial = Math.max(6, Math.min(100, 100 - (sp.seconds / sp.benchmark) * 100));
        if (!sp.fast) dial = 88;
        speedBox.innerHTML = '<div class="cf-speed' + (sp.fast ? "" : " slow") + '">' +
          '<div class="cf-speed-dial" style="--dial:' + dial + '%"><span>' + esc(sp.label) + '</span></div>' +
          '<div><h4>' + (sp.fast ? "Inside the 60-second window" : "Slower than the 60-second window") + '</h4>' +
          '<p>' + esc(sp.detail) + '</p></div></div>';
      }
    }

    var kw = $("#anKeywords");
    if (kw) {
      kw.innerHTML = (data.keywords || []).map(function (r, i) {
        return '<tr><td><span class="cf-rank' + (i === 0 && r.converted ? " top" : "") + '">' + (i + 1) + '</span></td>' +
          '<td><b>' + esc(r.name) + '</b></td>' +
          '<td>' + (r.keywords.length
            ? r.keywords.map(function (w) { return '<span class="cf-word">' + esc(w) + '</span>'; }).join("")
            : '<span class="cf-word">any comment</span>') + '</td>' +
          '<td class="num">' + num(r.contacts) + '</td>' +
          '<td class="num">' + num(r.converted) + '</td>' +
          '<td class="num">' + r.conversion + '%</td>' +
          '<td>' + (r.active
            ? '<span style="font-size:12px;font-weight:700;color:var(--mc-green)">Live</span>'
            : '<span style="font-size:12px;font-weight:700;color:var(--text-faint)">Paused</span>') + '</td></tr>';
      }).join("") ||
      '<tr><td colspan="7" style="padding:36px;text-align:center;color:var(--text-faint)">' +
      'No automations yet — build one and this table tells you which word earns.</td></tr>';
    }

    // sources, from the contacts CRM
    var contacts = await api("/api/contacts");
    var rows = contacts.contacts || [];
    var sources = {};
    rows.forEach(function (c) {
      var src = (c.source || "Unknown").replace(/\s*\(.*\)$/, "");
      sources[src] = (sources[src] || 0) + 1;
    });
    var total = rows.length || 1;
    var sbox = $("#anSources");
    if (sbox) {
      sbox.innerHTML = Object.keys(sources)
        .sort(function (a, b) { return sources[b] - sources[a]; })
        .map(function (src) {
          var pct = Math.round(sources[src] / total * 100);
          return '<div style="display:flex;align-items:center;gap:14px;padding:10px 0">' +
            '<span style="font-size:13.5px;font-weight:600;width:240px;flex-shrink:0">' + esc(src) + '</span>' +
            '<div class="meter" style="flex:1"><i style="width:' + pct + '%"></i></div>' +
            '<span style="font-size:12.5px;font-weight:700;width:90px;text-align:right;color:var(--text-muted)">' +
            sources[src] + ' · ' + pct + '%</span></div>';
        }).join("") ||
        '<p class="helper-text">No contacts captured yet — run an automation or the Flow Tester.</p>';
    }
  }

  // --- the upgrade modal ----------------------------------------------------
  // The old modal hardcoded "Pro — ₹299/month" and a fixed benefit list. With a
  // four-tier catalogue that was guaranteed to go stale, so it now reads the
  // plans the admin actually sells and offers the next one up.
  var FEATURE_COPY = {
    broadcast: ["Broadcast engine", "Send a personalised DM to a whole lead list, with anti-ban delays."],
    ai_assist: ["AI flow generator", "Describe your offer and get the whole comment-to-DM flow written."],
    story_mention: ["Story mention trigger", "Reply automatically when someone mentions you in a story."],
    wildcard_trigger: ["Any-comment trigger", "Catch every comment on a post, not just chosen keywords."],
    analytics: ["Campaign analytics", "See which keyword earns and where people drop off."],
    priority_support: ["Priority WhatsApp support", "A real person on WhatsApp, not a ticket queue."],
    white_label: ["White-label", "Run client brands without ConverFlow's name on it."],
    remove_branding: ["No ConverFlow branding", "Your DMs look like yours."]
  };

  async function fillUpgradeModal() {
    if (!$("#upModalPrice")) return;
    var out = await api("/api/billing/status");
    var b = out.billing, plans = out.plans || [];

    var current = plans.find(function (p) { return p.id === b.plan_id; });
    var order = current ? current.order : 0;
    // Only ever offer a plan ABOVE the current one. Falling back to the
    // "recommended" plan would have pitched Growth to an Agency customer — a
    // downgrade dressed up as an upgrade.
    var target = plans.filter(function (p) { return p.order > order; })[0];

    if (!target) {
      STATE.upgradeTarget = null;
      $("#upModalTitle").textContent = "You're on our top plan";
      $("#upModalPrice").textContent = num(b.price_monthly);
      $("#upModalSub").textContent = (current && current.tagline) || "Everything is unlocked.";
      $("#upModalCta").textContent = "Manage plan & usage";
      $("#upModalBenefits").innerHTML =
        '<div class="benefit-item"><span class="benefit-check">✓</span>' +
        '<div><strong>Nothing left to unlock</strong> — ' + esc(b.plan_name) +
        ' includes every feature we ship. Need more than it allows? Talk to us about a custom limit.</div></div>';
      return;
    }

    STATE.upgradeTarget = target.id;
    $("#upModalTitle").textContent = "Upgrade to " + target.name;
    $("#upModalPrice").textContent = num(target.price_monthly);
    $("#upModalSub").textContent = target.tagline || "";
    $("#upModalCta").textContent = "Switch to " + target.name + " — " + inr(target.price_monthly) + " / month";

    // what this plan adds that the current one does not
    var have = (current && current.features) || {};
    var gains = Object.keys(target.features || {}).filter(function (k) {
      return target.features[k] && !have[k] && FEATURE_COPY[k];
    });
    // -1 means unlimited, so treat it as the largest possible value when
    // deciding whether a limit actually improves.
    var rank = function (v) { return v === -1 ? Infinity : (v || 0); };
    var limitLine = function (key, label) {
      var to = target.limits[key];
      if (to == null) return null;
      var from = current ? current.limits[key] : null;
      if (from != null && rank(to) <= rank(from)) return null;   // not an upgrade
      return [limitLabel(to) + " " + label,
              from != null ? "Up from " + limitLabel(from) + "." : ""];
    };
    var rows = [limitLine("automations", "automations"),
                limitLine("contacts", "contacts"),
                limitLine("dms_per_month", "DMs a month")]
      .filter(Boolean)
      .concat(gains.map(function (k) { return FEATURE_COPY[k]; }));

    $("#upModalBenefits").innerHTML = rows.slice(0, 6).map(function (r) {
      return '<div class="benefit-item"><span class="benefit-check">✓</span>' +
        '<div><strong>' + esc(r[0]) + '</strong>' + (r[1] ? ' — ' + esc(r[1]) : '') + '</div></div>';
    }).join("") || '<div class="benefit-item"><span class="benefit-check">✓</span>' +
      '<div>You are already on our top plan.</div></div>';
  }

  document.addEventListener("click", async function (ev) {
    var confirm = ev.target.closest("#btnConfirmUpgrade");
    if (confirm && !STATE.upgradeTarget) {
      var modalTop = document.getElementById("upgradeModal");
      if (modalTop) modalTop.classList.remove("active", "show");
      window.location.hash = "#billing";
      renderFor("view-billing");
      return;
    }
    if (confirm && STATE.upgradeTarget) {
      confirm.disabled = true;
      var out = await api("/api/billing/upgrade", {
        method: "POST", body: JSON.stringify({ plan_id: STATE.upgradeTarget })
      });
      confirm.disabled = false;
      if (!out.success) { flash(out.error || "Could not switch plan", true); return; }
      flash("You're on the " + out.billing.plan_name + " plan");
      var modal = document.getElementById("upgradeModal");
      if (modal) modal.classList.remove("active", "show");
      renderBilling(); fillUpgradeModal(); renderSettingsPlan();
    }
  });

  // --- the small plan card on Settings --------------------------------------
  async function renderSettingsPlan() {
    if (!$("#setPlanLine")) return;
    var out = await api("/api/billing/status");
    var b = out.billing;
    var badge = $("#setPlanBadge");
    if (badge) {
      badge.textContent = b.badge || b.plan_name;
      if (b.is_paid) badge.style.cssText = "background:#e8f5ee;color:#00824b";
    }
    var limits = b.limits || {};
    var autos = limits.automations === -1 ? "unlimited automations"
      : limits.automations + " automation" + (limits.automations === 1 ? "" : "s");
    $("#setPlanLine").textContent = b.state === "trialing"
      ? "Trial of " + b.plan_name + " — " + b.days_left + " days left, " + autos + "."
      : b.state === "expired"
      ? "Your trial has ended, so automations are paused."
      : "You're on " + b.plan_name + " with " + autos + ".";
    $("#setPlanPrice").textContent = inr(b.price_monthly);
    $("#setPlanCycle").textContent = b.price_monthly ? " / month" : " — free forever";
  }

  // --- connection doctor ----------------------------------------------------
  // Every step reports its own state. A failure always carries its cause and its
  // fix, because the single loudest complaint about ManyChat is a connect button
  // that does nothing and says nothing.
  async function renderDoctor() {
    var steps = $("#doctorSteps");
    if (!steps) return;
    var out = await api("/api/instagram/status");
    var ig = out.instagram || {};
    var data = await insights(true);
    var health = data.health.checks.reduce(function (m, c) { m[c.key] = c.ok; return m; }, {});

    var plan = [
      {
        label: "ConverFlow can talk to Meta",
        pass: out.platform_ready,
        desc: out.platform_ready
          ? "The platform's Meta app is configured and accepted."
          : "One-click connect is off. An existing session can still work, but new users cannot self-connect.",
        why: "The Meta app is not set up yet, so the Connect button has nowhere to send you.",
        fix: "We're finishing this setup at our end. Until it's live you can use "
             + "\"Sign in with a browser window\" below."
      },
      {
        label: "Your Instagram account is linked",
        pass: !!ig.connected,
        desc: ig.connected ? "@" + (ig.username || "") + " is connected." : "Not connected yet.",
        why: "No Instagram account is attached to this workspace.",
        fix: "Press Connect Instagram above. You need a Business or Creator account linked to a Facebook page."
      },
      {
        label: "Account type is Business or Creator",
        pass: !!ig.connected,
        desc: "Personal accounts cannot receive automated DMs — Meta blocks it at the API.",
        why: "Meta only exposes messaging for professional accounts.",
        fix: "Instagram app → Settings → Account type → switch to Business, then link a Facebook page."
      },
      {
        label: "Comment watcher is running",
        pass: !!health.watcher,
        desc: "Something is listening for new comments.",
        why: "The watcher is idle, so comments are not being picked up.",
        fix: "Open Automations and press Start Live Watcher."
      },
      {
        label: "At least one automation is live",
        pass: !!health.rules,
        desc: "A rule is switched on and ready to fire.",
        why: "Every rule is paused, so nothing will trigger even with a healthy connection.",
        fix: "Switch a rule on in Automations."
      }
    ];

    // Every failing step is marked failed — hiding the later ones would repeat
    // exactly the vagueness we're trying to beat. Only the first one carries the
    // fix panel, so the user always knows which single thing to do next.
    var failing = plan.filter(function (p) { return !p.pass; });
    var firstFail = plan.findIndex(function (p) { return !p.pass; });

    steps.innerHTML = plan.map(function (p, i) {
      return '<div class="cf-step ' + (p.pass ? "done" : "failed") + '">' +
        '<span class="cf-step-mark">' + (p.pass ? CHECK_ICON : (i + 1)) + '</span>' +
        '<div><b>' + esc(p.label) + '</b><p>' + esc(p.desc) + '</p>' +
        (i === firstFail
          ? '<div class="reason"><em>Why it is stuck:</em> ' + esc(p.why) +
            '<br><em>Fix:</em> ' + esc(p.fix) + '</div>'
          : '') +
        '</div><span>' + (p.pass
          ? ''
          : '<span style="font-size:11.5px;font-weight:700;color:var(--mc-coral)">' +
            (i === firstFail ? "Do this" : "Blocked") + '</span>') + '</span></div>';
    }).join("");

    var chip = $("#doctorChip");
    if (chip) {
      var n = failing.length;
      chip.textContent = n === 0 ? "ALL CLEAR" : n + (n === 1 ? " STEP LEFT" : " STEPS LEFT");
      chip.style.cssText = n === 0
        ? "background:var(--mc-green-light);color:var(--mc-green)"
        : "background:#fef2f2;color:#c2262b";
    }
  }

  // ================================================================ routing
  var RENDER = {
    "view-home": renderHome,
    "view-billing": renderBilling,
    "view-broadcast": renderBroadcast,
    "view-analytics": renderAnalytics,
    "view-settings": function () { renderConnect(); renderDoctor(); renderSettingsPlan(); }
  };

  function renderFor(viewId) {
    var fn = RENDER[viewId];
    if (fn) { try { fn(); } catch (e) { console.error(e); } }
  }

  document.addEventListener("click", function (ev) {
    var link = ev.target.closest("[data-view]");
    if (link) setTimeout(function () { renderFor(link.getAttribute("data-view")); }, 60);
  });
  window.addEventListener("hashchange", function () {
    var map = { "#billing": "view-billing", "#broadcast": "view-broadcast",
                "#analytics": "view-analytics", "#settings": "view-settings" };
    renderFor(map[window.location.hash]);
  });
  $("#anRefresh") && $("#anRefresh").addEventListener("click", renderAnalytics);

  document.addEventListener("DOMContentLoaded", boot);
  if (document.readyState !== "loading") boot();
  function boot() {
    renderConnect();
    renderHome();
    fillUpgradeModal();
    api("/api/billing/status").then(function (out) {
      if (out && out.billing) { STATE.billing = out.billing; STATE.plans = out.plans || []; syncSidebar(out.billing); }
    }).catch(function () {});
    var map = { "#billing": "view-billing", "#broadcast": "view-broadcast", "#analytics": "view-analytics" };
    var v = map[window.location.hash];
    if (v) renderFor(v);
  }
})();
