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

  // Templates ship with {handle}; it becomes whichever account is connected.
  // Nothing in the product should ever name one merchant's Instagram to another.
  function withHandle(text) {
    var h = (STATE.profile && STATE.profile.username) || "";
    return String(text || "").replace(/\{handle\}/g, h || "your account");
  }

  function esc(v) {
    return String(v == null? "": v).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function num(n) {
    return n == null? "—": Number(n).toLocaleString("en-IN");
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
    if (window.showToast) return window.showToast(msg, bad? "error": "success");
    console[bad? "error": "log"](msg);
  }
  function show(el, on) { if (el) el.hidden =!on; }

  /* ---------------------------------------------------------------- connect */
  async function loadAccount() {
    var gate = $("#igConnectGate"), work = $("#igWorkspace");
    if (!gate ||!work) return;

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
    loadChain();
    paintTiles();
  }

  function paintProfile() {
    var gh = document.getElementById("fcGateHandle");
    if (gh) gh.textContent = STATE.profile && STATE.profile.username
      ? "@" + STATE.profile.username: "your account";
    var p = STATE.profile || {};
    var img = $("#igAvatar");
    if (img) {
      if (p.profile_picture_url) { img.src = p.profile_picture_url; img.style.visibility = "visible"; }
      else { img.removeAttribute("src"); img.style.visibility = "hidden"; }
      img.alt = p.username? "@" + p.username: "";
    }
    if ($("#igHandle")) $("#igHandle").textContent = p.username? "@" + p.username: (p.name || "Connected");
    var bits = [];
    if (p.followers_count!= null) bits.push(num(p.followers_count) + " followers");
    if (p.media_count!= null) bits.push(num(p.media_count) + " posts");
    if (p.account_type) bits.push(String(p.account_type).toLowerCase().replace("_", " ") + " account");
    if ($("#igProfileSub")) $("#igProfileSub").textContent = bits.join(" · ") || "Connected";
  }


  /* ----------------------------------------------------------------- chain
     Connected and working are different states, and the gap between them is
     invisible: the account links, the profile loads, the posts appear — and a
     comment still reaches nothing because the webhook was never subscribed.
     This walks the real chain and names the broken link.
     ------------------------------------------------------------------ */
  var MARK = { pass: "\u2713", fail: "!", unknown: "?", info: "i" };

  async function loadChain() {
    var panel = $("#chainPanel");
    if (!panel) return;
    show(panel, true);
    var out = await api("/api/instagram/diagnose");
    if (!out || !out.checks) {
      $("#chainVerdict").textContent = "Could not run the check.";
      return;
    }
    $("#chainVerdict").textContent = out.verdict || "";
    $("#chainList").innerHTML = out.checks.map(function (c) {
      return '<li class="chain-step' + (c.state === "fail" ? " is-fail" : "") + '">' +
        '<span class="chain-mark ' + c.state + '">' + (MARK[c.state] || "") + '</span>' +
        '<div class="chain-body">' +
          '<div class="chain-label">' + esc(c.label) + '</div>' +
          '<div class="chain-detail">' + esc(c.detail) + '</div>' +
          (c.fix && c.state !== "pass" ? '<div class="chain-fix">' + esc(c.fix) + '</div>' : "") +
        '</div></li>';
    }).join("");

    // Repair is only offered when it is the thing that would actually help.
    // Both subscription levels are repairable; the rest (account type, a
    // paused flow) are things only the merchant can change.
    var REPAIRABLE = { app_webhook: 1, webhook_sub: 1 };
    var broken = out.checks.filter(function (c) {
      return REPAIRABLE[c.key] && c.state !== "pass";
    }).length > 0;
    show($("#btnChainRepair"), broken);
  }

  /* ------------------------------------------------------------------ media */
  async function loadMedia(force) {
    var grid = $("#igMediaGrid"), st = $("#igMediaState");
    if (!grid) return;
    grid.innerHTML = '<div class="ig-card is-skeleton"></div>'.repeat(6);
    show(st, false);

    var out = await api("/api/instagram/media?limit=24" + (force? "&refresh=true": ""));
    if (!out.success) {
      grid.innerHTML = "";
      if (st) {
        st.innerHTML = '<b>' + esc(out.error || "Instagram did not answer.") + '</b>' +
          (out.needs_reconnect? '<div><button class="btn btn-primary btn-sm" id="btnReconnect">Reconnect Instagram</button></div>': "");
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
      ? '<span class="ig-card-flag' + (a.active? " is-on": "") + '">' +
'<i class="state-dot ' + (a.active? "is-live": "is-paused") + '"></i>' +
          (a.active? "DM on " + esc((a.keywords[0] || "any comment").toUpperCase()): "Paused") +
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
'<span class="ig-card-cap">' + (cap? esc(cap): "<i>No caption</i>") + '</span>' +
'<span class="ig-card-stats">' +
          (m.comments!= null? num(m.comments) + " comments": "") +
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
    var trigger = r.trigger_scope === "any" ||!words.length
      ? "any comment"
      : words.map(function (w) { return '<code>' + esc(w) + '</code>'; }).join(" ");
    var dm = (r.opening_dm || r.dm_message || "").replace(/\s+/g, " ").slice(0, 110);
    return '<div class="flow-row" data-flow="' + esc(r.id) + '">' +
      (r.post_thumbnail
        ? '<img class="flow-thumb" src="' + esc(r.post_thumbnail) + '" alt="" referrerpolicy="no-referrer">'
        : '<div class="flow-thumb is-empty"></div>') +
'<div class="flow-main">' +
'<div class="flow-state"><i class="state-dot ' + (r.is_active? "is-live": "is-paused") + '"></i>' +
          (r.is_active? "Live": "Paused") + '</div>' +
'<div class="flow-trigger">Comment ' + trigger + ' \u2192 DM</div>' +
'<div class="flow-dm">' + esc(dm) + '</div>' +
'</div>' +
'<div class="flow-actions">' +
'<button class="btn btn-secondary btn-sm" data-toggle="' + esc(r.id) + '">' +
          (r.is_active? "Pause": "Turn on") + '</button>' +
'<button class="btn-link-danger" data-del="' + esc(r.id) + '">Delete</button>' +
'</div></div>';
  }

  /* ------------------------------------------------------------------ tiles */
  async function paintTiles() {
    var b = await api("/api/billing/status");
    var usage = ((b && b.billing) || {}).usage || {};
    var live = STATE.flows.filter(function (f) { return f.is_active; }).length;
    var au = usage.automations || {};
    set("tileFlows", live, au.unlimited? "no limit on your plan"
      : "your plan allows " + (au.limit!= null? au.limit: "—"));
    var dm = usage.dms_per_month || {};
    set("tileDms", dm.used!= null? num(dm.used): "—",
      dm.unlimited? "no monthly cap": "of " + num(dm.limit) + " this month");
    var ct = usage.contacts || {};
    set("tilePeople", ct.used!= null? num(ct.used): "—",
      ct.unlimited? "no cap": "of " + num(ct.limit) + " stored");
  }
  function set(id, value, sub) {
    var v = document.getElementById(id), sb = document.getElementById(id + "Sub");
    if (v) v.textContent = value;
    if (sb) sb.textContent = sub || "";
  }

  /* --------------------------------------------------------------- templates */
  var TEMPLATES = {
    leadmagnet: {
      keywords: "LINK, GUIDE",
      dm: "Hey {name}! Here is the exclusive resource you requested from our reel!\n\nTap the button below to get instant access right now! ",
      button: "Get Instant Access ",
      link: "https://yourstore.com/guide",
      reply: "{Sent you a DM! Check your message requests.|Check your inbox! Just sent over the details.|DM sent! Let me know if you got it!}",
      followPrompt: "Hey {name}! You must follow @{handle} first to unlock this link!\n\nTap the button below to follow us, then comment again or reply 'DONE' to get instant access "
    },
    discount: {
      keywords: "PRICE, DISCOUNT, CODE",
      dm: "Hey {name}! Thanks for commenting! Here is your exclusive 20% OFF discount coupon: WELCOME20\n\nTap below to shop with your discount applied:",
      button: "Claim 20% Off ",
      link: "https://yourstore.com/shop",
      reply: "{Sent you the discount code in DM! |Check your message requests for the coupon code! }",
      followPrompt: "Hey {name}! You must follow @{handle} first to unlock this 20% discount coupon!\n\nTap follow below and comment again to get your code "
    },
    booking: {
      keywords: "CALL, AUDIT, BOOK",
      dm: "Hey {name}! Ready to scale your brand? Let's get on a quick 15-minute 1-on-1 strategy session.\n\nGrab a free slot on my personal calendar below:",
      button: "Book Free Strategy Call ",
      link: "https://calendly.com/your-handle/strategy",
      reply: "{Just sent you the booking link in DM! |Check your messages! Let's talk soon }",
      followPrompt: "Hey {name}! Please follow @{handle} first to unlock the strategy consultation booking link!\n\nTap follow below and comment again to book "
    },
    product: {
      keywords: "INFO, DETAILS, LINK",
      dm: "Hey {name}! Here is the exact link to what you saw in our reel.\n\nTap below to check out all the details before it sells out:",
      button: "View Full Details ",
      link: "https://yourstore.com/product",
      reply: "{Sent the details to your DM! |Check your inbox! }",
      followPrompt: "Hey {name}! Please follow @{handle} first to unlock this product link!\n\nFollow us below, then comment again to receive it "
    }
  };

  function applyTemplate(key) {
    var t = TEMPLATES[key];
    if (!t) return;
    document.querySelectorAll(".fx-tpl-card").forEach(function (el) {
      el.classList.toggle("is-active", el.dataset.tpl === key);
    });
    if ($("#fcKeyword")) $("#fcKeyword").value = t.keywords;
    if ($("#fcDm")) $("#fcDm").value = withHandle(t.dm);
    if ($("#fcBtnText")) $("#fcBtnText").value = t.button;
    if ($("#fcUrl")) $("#fcUrl").value = t.link;
    if ($("#fcReply")) $("#fcReply").value = t.reply;
    if ($("#fcFollowPrompt")) $("#fcFollowPrompt").value = withHandle(t.followPrompt);
    syncMockupPreview();
  }

  function syncMockupPreview() {
    var p = STATE.profile || {};
    var handle = p.username || (STATE.profile && STATE.profile.username) || "";
    var avatar = p.profile_picture_url || "";
    var m = STATE.picked || {};

    // Header sync
    if ($("#prevIgHandle")) $("#prevIgHandle").textContent = handle;
    ["#prevIgAvatar", "#prevIgAvatarBubble", "#prevIgAvatarGate"].forEach(function (sel) {
      var el = $(sel);
      if (el) {
        if (avatar) { el.src = avatar; el.style.visibility = "visible"; }
        else { el.removeAttribute("src"); el.style.visibility = "hidden"; }
      }
    });

    // Reel snippet sync
    var rThumb = $("#prevReelThumb");
    if (rThumb) {
      if (m.thumbnail) { rThumb.src = m.thumbnail; rThumb.style.display = "block"; }
      else { rThumb.style.display = "none"; }
    }
    var kwVal = $("#fcKeyword")? $("#fcKeyword").value.trim(): "";
    var any = $("#fcAny") && $("#fcAny").checked;
    if ($("#prevKwDisplay")) {
      $("#prevKwDisplay").textContent = any? '"Any comment"': ('"' + (kwVal.split(",")[0] || "LINK").trim() + '"');
    }

    // Follower DM preview
    var rawDm = $("#fcDm")? $("#fcDm").value: "";
    var sampleDm = rawDm.replace(/\{name\}|\{first_name\}|\{username\}/g, "Alex")
                        .replace(/\{Hi\|Hey\|Hello\}/g, "Hey");
    if ($("#prevDmBody")) $("#prevDmBody").textContent = sampleDm;

    var btnText = $("#fcBtnText")? $("#fcBtnText").value.trim(): "";
    var btnUrl = $("#fcUrl")? $("#fcUrl").value.trim(): "";
    var ctaEl = $("#prevCtaBtn");
    if (ctaEl) {
      if (btnText) {
        ctaEl.style.display = "inline-flex";
        if ($("#prevBtnText")) $("#prevBtnText").textContent = btnText;
        ctaEl.href = btnUrl || "#";
      } else {
        ctaEl.style.display = "none";
      }
    }

    // Gate prompt preview
    var gatePrompt = $("#fcFollowPrompt")? $("#fcFollowPrompt").value: "";
    var sampleGate = gatePrompt.replace(/\{name\}|\{first_name\}|\{username\}/g, "Alex");
    if ($("#prevGatePrompt")) $("#prevGatePrompt").textContent = sampleGate;
  }

  /* --------------------------------------------------------------- composer */
  function openComposer(mediaId) {
    var m = STATE.media.filter(function (x) { return x.id === mediaId; })[0];
    if (!m) return;
    STATE.picked = m;

    var p = STATE.profile || {};
    var handle = p.username || (STATE.profile && STATE.profile.username) || "";

    $("#fcThumb").src = m.thumbnail || "";
    $("#fcThumb").style.visibility = m.thumbnail? "visible": "hidden";
    $("#fcKind").textContent = (m.kind || "post").toUpperCase();
    $("#fcCaption").textContent = (m.caption || "No caption").slice(0, 160);
    var link = $("#fcLink");
    if (m.permalink) { link.href = m.permalink; link.hidden = false; } else { link.hidden = true; }

    var existing = m.automation;
    var r = existing && STATE.flows.filter(function (f) { return f.id === existing.rule_id; })[0];

    if (r) {
      $("#fcKeyword").value = (r.trigger_keywords || []).join(", ");
      $("#fcAny").checked =!!(r.trigger_scope === "any");
      $("#fcDm").value = r.opening_dm || r.dm_message || "";
      $("#fcBtnText").value = r.button_text || "Get Instant Access ";
      $("#fcUrl").value = r.delivery_link || "";
      $("#fcReply").value = (r.comment_replies || [])[0] || r.public_comment_reply || "";
      if ($("#fcRequireFollow")) $("#fcRequireFollow").checked = r.require_follow!== false;
      if ($("#fcFollowPrompt")) $("#fcFollowPrompt").value = r.follow_prompt_msg ||
        ("Hey {name}! You must follow @" + handle + " first to unlock this link!\n\nTap the button below to follow us, then comment again or reply 'DONE' to get instant access ");
      $("#fcTitle").textContent = "Update comment \u2192 auto DM flow";
      $("#fcSave").textContent = "Save Changes ";
    } else {
      // PRE-FILLED WITH LEAD MAGNET TEMPLATE BY DEFAULT (Instant conversion ready!)
      applyTemplate("leadmagnet");
      if ($("#fcRequireFollow")) $("#fcRequireFollow").checked = true;
      $("#fcTitle").textContent = "Comment \u2192 auto DM flow";
      $("#fcSave").textContent = "Turn On Automation ";
    }

    // Default to follower preview
    setMockupView("follower");
    syncMockupPreview();
    show($("#fcError"), false);

    show($("#flowComposer"), true);
    setTimeout(function () { $("#fcKeyword").focus(); }, 50);
  }

  function setMockupView(view) {
    var isFollower = view === "follower";
    if ($("#btnPrevFollower")) $("#btnPrevFollower").classList.toggle("is-active", isFollower);
    if ($("#btnPrevGate")) $("#btnPrevGate").classList.toggle("is-active",!isFollower);
    show($("#mockupFollowerView"), isFollower);
    show($("#mockupGateView"),!isFollower);
  }

  function closeComposer() { show($("#flowComposer"), false); STATE.picked = null; }

  async function saveFlow() {
    var m = STATE.picked;
    if (!m) return;
    var btn = $("#fcSave"), err = $("#fcError");
    var any = $("#fcAny").checked;
    var words = $("#fcKeyword").value.split(",").map(function (w) { return w.trim(); }).filter(Boolean);
    var dm = $("#fcDm").value.trim();
    var btnText = $("#fcBtnText")? $("#fcBtnText").value.trim(): "Get Instant Access ";
    var linkUrl = $("#fcUrl").value.trim();
    var reply = $("#fcReply").value.trim();
    var requireFollow = $("#fcRequireFollow")? $("#fcRequireFollow").checked: true;
    var followPrompt = $("#fcFollowPrompt")? $("#fcFollowPrompt").value.trim(): "";

    function fail(msg) { err.textContent = msg; show(err, true); btn.disabled = false; btn.textContent = "Turn On Automation "; }
    show(err, false);
    if (!any &&!words.length) return fail("Type the word people should comment (e.g. LINK, PRICE) — or tick “reply to every comment”.");
    if (!dm) return fail("Write the DM message they should get.");

    btn.disabled = true; btn.textContent = "Publishing Flow…";
    // Replacing an existing flow on this post keeps one rule per post.
    if (m.automation && m.automation.rule_id) {
      await api("/api/flows/" + encodeURIComponent(m.automation.rule_id), { method: "DELETE" });
    }
    var out = await api("/api/flows/from-post", {
      method: "POST",
      body: JSON.stringify({
        media_id: m.id,
        keywords: words,
        any_comment: any,
        dm_message: dm,
        button_text: btnText,
        link_url: linkUrl,
        comment_reply: reply,
        require_follow: requireFollow,
        follow_prompt_msg: followPrompt,
        activate: true
      })
    });
    btn.disabled = false; btn.textContent = "Turn On Automation ";
    if (!out.success) {
      if (out.upgrade_required && window.CF && window.CF.openUpgrade) {
        closeComposer(); window.CF.openUpgrade(out.message); return;
      }
      return fail(out.message || out.error || "Could not save that flow.");
    }
    closeComposer();
    toast(any? " Flow live — every comment on that post now gets an instant auto-DM!"
              : " Flow live — comment “" + (words[0] || "").toUpperCase() + "” now triggers instant auto-DM!");
    await loadMedia(true); await loadFlows(); paintTiles();
  }

  /* ----------------------------------------------------------------- events */
  document.addEventListener("click", async function (ev) {
    var pick = ev.target.closest("[data-media]");
    if (pick) { openComposer(pick.dataset.media); return; }

    if (ev.target.closest("#fcClose") || ev.target.closest("#fcCancel")) { closeComposer(); return; }
    if (ev.target.id === "flowComposer") { closeComposer(); return; }
    if (ev.target.closest("#fcSave")) { saveFlow(); return; }

    // Template switcher
    var tplBtn = ev.target.closest(".fx-tpl-card");
    if (tplBtn && tplBtn.dataset.tpl) {
      applyTemplate(tplBtn.dataset.tpl);
      return;
    }

    // Quick keyword chip
    var kwChip = ev.target.closest(".fx-kw-chip-btn");
    if (kwChip && kwChip.dataset.kw) {
      var cur = $("#fcKeyword").value.trim();
      var kw = kwChip.dataset.kw;
      var list = cur.split(",").map(function (x) { return x.trim(); }).filter(Boolean);
      if (!list.includes(kw)) list.push(kw);
      $("#fcKeyword").value = list.join(", ");
      syncMockupPreview();
      return;
    }

    // Dynamic variable pill
    var varBtn = ev.target.closest(".fx-var-btn");
    if (varBtn && varBtn.dataset.var) {
      var tag = varBtn.dataset.var;
      var ta = $("#fcDm");
      if (ta) {
        var start = ta.selectionStart || ta.value.length;
        var end = ta.selectionEnd || ta.value.length;
        ta.value = ta.value.substring(0, start) + " " + tag + " " + ta.value.substring(end);
        ta.focus();
        syncMockupPreview();
      }
      return;
    }

    // Preview mode switcher
    if (ev.target.closest("#btnPrevFollower")) { setMockupView("follower"); return; }
    if (ev.target.closest("#btnPrevGate")) { setMockupView("gate"); return; }

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
    if (ev.target.closest("#btnChainCheck")) {
      var cb = ev.target.closest("#btnChainCheck");
      cb.disabled = true; cb.textContent = "Checking...";
      await loadChain();
      cb.disabled = false; cb.textContent = "Re-check";
      return;
    }
    if (ev.target.closest("#btnChainRepair")) {
      var rb = ev.target.closest("#btnChainRepair");
      rb.disabled = true; rb.textContent = "Repairing...";
      var r = await api("/api/instagram/repair-webhook", { method: "POST" });
      rb.disabled = false; rb.textContent = "Repair";
      // Repair touches two levels. Saying only "failed" hides which one, and
      // which one it is decides what the merchant has to do next.
      var failed = (r.steps || []).filter(function (s) { return !s.ok; });
      if (failed.length && !r.success) {
        toast(failed[0].label + ": " + failed[0].detail, true);
      } else {
        toast(r.message || r.error || "Could not repair", !r.success);
      }
      await loadChain();
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
      if (row &&!row.classList.contains("confirming")) {
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
    if (ev.key === "Escape" &&!$("#flowComposer").hidden) closeComposer();
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
    el.textContent = initials || (name? name[0].toUpperCase(): "?");
  }

  window.CFAccount = { reload: loadAccount };
  function boot() {
    loadAccount();
    paintIdentity();
    ["fcDm", "fcBtnText", "fcUrl", "fcKeyword", "fcFollowPrompt"].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.addEventListener("input", syncMockupPreview);
    });
    var anyBox = document.getElementById("fcAny");
    if (anyBox) anyBox.addEventListener("change", syncMockupPreview);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
