/* ===========================================================================
   ConverFlow — the account screen.
   Connect -> see your real posts -> pick one -> set the DM -> on.

   Rule this file keeps: nothing is ever invented. If the API cannot answer,
   the screen says what went wrong and what to do, and shows nothing else.
   =========================================================================== */
(function () {
  "use strict";

  var $ = function (sel) { return document.querySelector(sel); };
  var STATE = { profile: null, media: [], flows: [], picked: null };

  function esc(v) {
    return String(v == null ? "" : v).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function num(n) {
    return n == null ? "—" : Number(n).toLocaleString("en-IN");
  }
  async function api(url, opts) {
    try {
      var r = await fetch(url, Object.assign({ headers: { "Content-Type": "application/json" } }, opts || {}));
      return await r.json();
    } catch (e) {
      return { success: false, error: "Could not reach the server. Check your connection." };
    }
  }
  function toast(msg, bad) {
    if (window.CF && window.CF.flash) return window.CF.flash(msg, bad);
    if (window.showToast) return window.showToast(msg, bad ? "error" : "success");
    console[bad ? "error" : "log"](msg);
  }
  function show(el, on) { if (el) el.hidden = !on; }

  /* ---------------------------------------------------------------- connect */
  async function loadAccount() {
    var gate = $("#igConnectGate"), work = $("#igWorkspace");
    if (!gate || !work) return;

    var out = await api("/api/instagram/profile");

    if (out.connected === false) {
      show(gate, true); show(work, false);
      var note = $("#igGateNote"), btn = $("#btnIgConnect");
      if (out.platform_ready === false) {
        if (note) note.textContent = "One-click connect is being switched on at our end. " +
          "Until it is live, ask us and we'll connect your account for you.";
        if (btn) btn.disabled = true;
      }
      return;
    }

    if (!out.success) {
      show(gate, true); show(work, false);
      var n2 = $("#igGateNote");
      if (n2) n2.textContent = out.error || "Instagram did not answer.";
      var b2 = $("#btnIgConnect");
      if (b2 && out.needs_reconnect) b2.textContent = "Reconnect Instagram";
      return;
    }

    show(gate, false); show(work, true);
    STATE.profile = out.profile || {};
    paintProfile();
    await Promise.all([loadMedia(), loadFlows()]);
    paintTiles();
  }

  function paintProfile() {
    var p = STATE.profile || {};
    var img = $("#igAvatar");
    if (img) {
      if (p.profile_picture_url) { img.src = p.profile_picture_url; img.style.visibility = "visible"; }
      else { img.removeAttribute("src"); img.style.visibility = "hidden"; }
      img.alt = p.username ? "@" + p.username : "";
    }
    if ($("#igHandle")) $("#igHandle").textContent = p.username ? "@" + p.username : (p.name || "Connected");
    var bits = [];
    if (p.followers_count != null) bits.push(num(p.followers_count) + " followers");
    if (p.media_count != null) bits.push(num(p.media_count) + " posts");
    if (p.account_type) bits.push(String(p.account_type).toLowerCase().replace("_", " ") + " account");
    if ($("#igProfileSub")) $("#igProfileSub").textContent = bits.join("  ·  ") || "Connected";
  }

  /* ------------------------------------------------------------------ media */
  async function loadMedia(force) {
    var grid = $("#igMediaGrid"), st = $("#igMediaState");
    if (!grid) return;
    grid.innerHTML = '<div class="ig-card is-skeleton"></div>'.repeat(6);
    show(st, false);

    var out = await api("/api/instagram/media?limit=24" + (force ? "&refresh=true" : ""));
    if (!out.success) {
      grid.innerHTML = "";
      if (st) {
        st.innerHTML = '<b>' + esc(out.error || "Instagram did not answer.") + '</b>' +
          (out.needs_reconnect ? '<div><button class="btn btn-primary btn-sm" id="btnReconnect">Reconnect Instagram</button></div>' : "");
        show(st, true);
      }
      return;
    }
    STATE.media = out.media || [];
    if (!STATE.media.length) {
      grid.innerHTML = "";
      if (st) {
        st.innerHTML = "<b>No posts on this account yet.</b>" +
          "<div>Post a reel, then reload — it will show up here and you can set its DM.</div>";
        show(st, true);
      }
      return;
    }
    grid.innerHTML = STATE.media.map(card).join("");
  }

  function card(m) {
    var a = m.automation;
    var cap = (m.caption || "").replace(/\s+/g, " ").slice(0, 70);
    var badge = a
      ? '<span class="ig-card-flag' + (a.active ? " is-on" : "") + '">' +
          '<i class="state-dot ' + (a.active ? "is-live" : "is-paused") + '"></i>' +
          (a.active ? "DM on " + esc((a.keywords[0] || "any comment").toUpperCase()) : "Paused") +
        '</span>'
      : "";
    var thumb = m.thumbnail
      ? '<img src="' + esc(m.thumbnail) + '" alt="" loading="lazy" referrerpolicy="no-referrer">'
      : '<div class="ig-card-nothumb">No preview</div>';
    return '<button class="ig-card" data-media="' + esc(m.id) + '">' +
      '<div class="ig-card-img">' + thumb +
        '<span class="ig-card-kind">' + esc(m.kind) + '</span>' + badge +
      '</div>' +
      '<div class="ig-card-body">' +
        '<span class="ig-card-cap">' + (cap ? esc(cap) : "<i>No caption</i>") + '</span>' +
        '<span class="ig-card-stats">' +
          (m.comments != null ? num(m.comments) + " comments" : "") +
        '</span>' +
      '</div></button>';
  }

  /* ------------------------------------------------------------------ flows */
  async function loadFlows() {
    var list = $("#igFlowList");
    if (!list) return;
    var out = await api("/api/automations");
    STATE.flows = (out.rules || out.automations || []).filter(function (r) {
      return r.type === "comment_to_dm";
    });
    if (!STATE.flows.length) {
      list.innerHTML = '<div class="ig-state"><b>No flows yet.</b>' +
        '<div>Tap any post above and you will have one running in under a minute.</div></div>';
      return;
    }
    list.innerHTML = STATE.flows.map(flowRow).join("");
  }

  function flowRow(r) {
    var words = (r.trigger_keywords || []);
    var trigger = r.trigger_scope === "any" || !words.length
      ? "any comment"
      : words.map(function (w) { return '<code>' + esc(w) + '</code>'; }).join(" ");
    var dm = (r.opening_dm || r.dm_message || "").replace(/\s+/g, " ").slice(0, 110);
    return '<div class="flow-row" data-flow="' + esc(r.id) + '">' +
      (r.post_thumbnail
        ? '<img class="flow-thumb" src="' + esc(r.post_thumbnail) + '" alt="" referrerpolicy="no-referrer">'
        : '<div class="flow-thumb is-empty"></div>') +
      '<div class="flow-main">' +
        '<div class="flow-state"><i class="state-dot ' + (r.is_active ? "is-live" : "is-paused") + '"></i>' +
          (r.is_active ? "Live" : "Paused") + '</div>' +
        '<div class="flow-trigger">Comment ' + trigger + ' &rarr; DM</div>' +
        '<div class="flow-dm">' + esc(dm) + '</div>' +
      '</div>' +
      '<div class="flow-actions">' +
        '<button class="btn btn-secondary btn-sm" data-toggle="' + esc(r.id) + '">' +
          (r.is_active ? "Pause" : "Turn on") + '</button>' +
        '<button class="btn-link-danger" data-del="' + esc(r.id) + '">Delete</button>' +
      '</div></div>';
  }

  /* ------------------------------------------------------------------ tiles */
  async function paintTiles() {
    var b = await api("/api/billing/status");
    var usage = ((b && b.billing) || {}).usage || {};
    var live = STATE.flows.filter(function (f) { return f.is_active; }).length;
    var au = usage.automations || {};
    set("tileFlows", live, au.unlimited ? "no limit on your plan"
      : "your plan allows " + (au.limit != null ? au.limit : "—"));
    var dm = usage.dms_per_month || {};
    set("tileDms", dm.used != null ? num(dm.used) : "—",
      dm.unlimited ? "no monthly cap" : "of " + num(dm.limit) + " this month");
    var ct = usage.contacts || {};
    set("tilePeople", ct.used != null ? num(ct.used) : "—",
      ct.unlimited ? "no cap" : "of " + num(ct.limit) + " stored");
  }
  function set(id, value, sub) {
    var v = document.getElementById(id), sb = document.getElementById(id + "Sub");
    if (v) v.textContent = value;
    if (sb) sb.textContent = sub || "";
  }

  /* --------------------------------------------------------------- composer */
  function openComposer(mediaId) {
    var m = STATE.media.filter(function (x) { return x.id === mediaId; })[0];
    if (!m) return;
    STATE.picked = m;

    $("#fcThumb").src = m.thumbnail || "";
    $("#fcThumb").style.visibility = m.thumbnail ? "visible" : "hidden";
    $("#fcKind").textContent = m.kind;
    $("#fcCaption").textContent = (m.caption || "No caption").slice(0, 160);
    var link = $("#fcLink");
    if (m.permalink) { link.href = m.permalink; link.hidden = false; } else { link.hidden = true; }

    var existing = m.automation;
    var r = existing && STATE.flows.filter(function (f) { return f.id === existing.rule_id; })[0];
    $("#fcKeyword").value = r ? (r.trigger_keywords || []).join(", ") : "";
    $("#fcAny").checked = !!(r && r.trigger_scope === "any");
    $("#fcDm").value = r ? (r.opening_dm || r.dm_message || "") : "";
    $("#fcUrl").value = r ? (r.delivery_link || "") : "";
    $("#fcReply").value = r ? ((r.comment_replies || [])[0] || "") : "";
    $("#fcTitle").textContent = r ? "Update this post's DM" : "On this post";
    $("#fcSave").textContent = r ? "Save changes" : "Turn it on";
    show($("#fcError"), false);

    show($("#flowComposer"), true);
    setTimeout(function () { $("#fcKeyword").focus(); }, 40);
  }
  function closeComposer() { show($("#flowComposer"), false); STATE.picked = null; }

  async function saveFlow() {
    var m = STATE.picked;
    if (!m) return;
    var btn = $("#fcSave"), err = $("#fcError");
    var any = $("#fcAny").checked;
    var words = $("#fcKeyword").value.split(",").map(function (w) { return w.trim(); }).filter(Boolean);
    var dm = $("#fcDm").value.trim();

    function fail(msg) { err.textContent = msg; show(err, true); btn.disabled = false; btn.textContent = "Turn it on"; }
    show(err, false);
    if (!any && !words.length) return fail("Type the word people should comment — or tick “reply to every comment”.");
    if (!dm) return fail("Write the DM they should get.");

    btn.disabled = true; btn.textContent = "Turning on…";
    // Replacing an existing flow on this post keeps one rule per post.
    if (m.automation && m.automation.rule_id) {
      await api("/api/flows/" + encodeURIComponent(m.automation.rule_id), { method: "DELETE" });
    }
    var out = await api("/api/flows/from-post", {
      method: "POST",
      body: JSON.stringify({
        media_id: m.id, keywords: words, any_comment: any, dm_message: dm,
        link_url: $("#fcUrl").value.trim(), comment_reply: $("#fcReply").value.trim(), activate: true
      })
    });
    btn.disabled = false; btn.textContent = "Turn it on";
    if (!out.success) {
      if (out.upgrade_required && window.CF && window.CF.openUpgrade) {
        closeComposer(); window.CF.openUpgrade(out.message); return;
      }
      return fail(out.message || out.error || "Could not save that.");
    }
    closeComposer();
    toast(any ? "Live — every comment on that post now gets a DM."
              : "Live — a comment saying “" + words[0] + "” now gets a DM.");
    await loadMedia(true); await loadFlows(); paintTiles();
  }

  /* ----------------------------------------------------------------- events */
  document.addEventListener("click", async function (ev) {
    var pick = ev.target.closest("[data-media]");
    if (pick) { openComposer(pick.dataset.media); return; }

    if (ev.target.closest("#fcClose") || ev.target.closest("#fcCancel")) { closeComposer(); return; }
    if (ev.target.id === "flowComposer") { closeComposer(); return; }
    if (ev.target.closest("#fcSave")) { saveFlow(); return; }

    var conn = ev.target.closest("#btnIgConnect") || ev.target.closest("#btnReconnect");
    if (conn) {
      conn.disabled = true; conn.textContent = "Opening Instagram…";
      var out = await api("/api/instagram/connect");
      if (out.success && out.url) { window.location.href = out.url; return; }
      conn.disabled = false; conn.textContent = "Connect Instagram";
      var note = $("#igGateNote");
      if (note) note.textContent = out.error || "Could not start the connection.";
      return;
    }

    if (ev.target.closest("#btnIgRefresh")) {
      var rb = ev.target.closest("#btnIgRefresh");
      rb.disabled = true;
      var pr = await api("/api/instagram/profile?refresh=true");
      if (pr.success) { STATE.profile = pr.profile; paintProfile(); }
      await loadMedia(true); await loadFlows(); paintTiles();
      rb.disabled = false;
      return;
    }
    if (ev.target.closest("#btnMediaRefresh")) {
      await loadMedia(true); await loadFlows();
      return;
    }

    var tg = ev.target.closest("[data-toggle]");
    if (tg) {
      tg.disabled = true;
      var res = await api("/api/automations/" + encodeURIComponent(tg.dataset.toggle) + "/toggle", { method: "POST" });
      tg.disabled = false;
      if (!res.success) {
        if (res.upgrade_required && window.CF && window.CF.openUpgrade) return window.CF.openUpgrade(res.message);
        return toast(res.message || "Could not change that flow.", true);
      }
      await loadFlows(); await loadMedia(true); paintTiles();
      return;
    }

    var del = ev.target.closest("[data-del]");
    if (del) {
      var row = del.closest(".flow-row");
      if (row && !row.classList.contains("confirming")) {
        row.classList.add("confirming"); del.textContent = "Really delete?";
        setTimeout(function () {
          if (row.classList.contains("confirming")) { row.classList.remove("confirming"); del.textContent = "Delete"; }
        }, 4000);
        return;
      }
      await api("/api/flows/" + encodeURIComponent(del.dataset.del), { method: "DELETE" });
      toast("Flow deleted.");
      await loadFlows(); await loadMedia(true); paintTiles();
      return;
    }
  });

  document.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape" && !$("#flowComposer").hidden) closeComposer();
  });

  // The sidebar avatar is the workspace's own initials, never a stock photo.
  async function paintIdentity() {
    var el = document.getElementById("navAvatarInitials");
    if (!el) return;
    var out = await api("/api/billing/status");
    var ws = ((out && out.billing) || {}).workspace || {};
    var name = ws.name || ws.email || "";
    var initials = name.trim().split(/\s+/).slice(0, 2)
      .map(function (w) { return w[0]; }).join("").toUpperCase();
    el.textContent = initials || (name ? name[0].toUpperCase() : "?");
  }

  window.CFAccount = { reload: loadAccount };
  function boot() { loadAccount(); paintIdentity(); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
