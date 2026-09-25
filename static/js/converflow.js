/**
 * ConverFlow — Noir Dashboard JS
 * =============================================================
 * Clean, minimal JavaScript for the redesigned SaaS dashboard.
 * Handles: navigation, API calls, modals, automations CRUD,
 *          contacts table, billing/Razorpay, toasts.
 * =============================================================
 */

(function () {
  "use strict";

  // ── DOM Helpers ──
  const $ = (s, p) => (p || document).querySelector(s);
  const $$ = (s, p) => [...(p || document).querySelectorAll(s)];
  const on = (el, ev, fn) => el && el.addEventListener(ev, fn);

  // ── State ──
  let currentView = "view-home";
  let rules = [];
  let contacts = [];
  let editingRuleId = null;

  // ── Toast Notifications ──
  function toast(msg, type = "info") {
    const c = $("#toastContainer");
    if (!c) return;
    const icons = {
      success: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M20 6L9 17l-5-5"/></svg>',
      error: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><path d="M15 9l-6 6M9 9l6 6"/></svg>',
      warn: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
      info: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>',
    };
    const t = document.createElement("div");
    t.className = `toast ${type}`;
    t.innerHTML = `<span class="toast-icon">${icons[type] || icons.info}</span><span>${msg}</span>`;
    c.appendChild(t);
    setTimeout(() => { t.style.opacity = "0"; setTimeout(() => t.remove(), 300); }, 4000);
  }

  // ── API Helper ──
  async function api(url, method = "GET", body = null) {
    try {
      const opts = { method, headers: { "Content-Type": "application/json" } };
      if (body) opts.body = JSON.stringify(body);
      const res = await fetch(url, opts);
      return await res.json();
    } catch (e) {
      console.error("API error:", url, e);
      return { success: false, error: e.message };
    }
  }

  // ── Navigation ──
  function navigate(viewId) {
    $$(".content-view").forEach((v) => v.classList.remove("active"));
    const target = $(`#${viewId}`);
    if (target) target.classList.add("active");
    $$(".nav-item").forEach((n) => n.classList.remove("active"));
    const navLink = $(`.nav-item[data-view="${viewId}"]`);
    if (navLink) navLink.classList.add("active");
    currentView = viewId;
    window.location.hash = viewId.replace("view-", "");

    // Load data for the view
    if (viewId === "view-home") loadDashboard();
    if (viewId === "view-automations") loadRules();
    if (viewId === "view-contacts") loadContacts();
    if (viewId === "view-analytics") loadAnalytics();
    if (viewId === "view-settings") loadSettings();
    if (viewId === "view-billing") loadBilling();
  }

  function initNav() {
    $$(".nav-item[data-view]").forEach((link) => {
      on(link, "click", (e) => {
        e.preventDefault();
        navigate(link.dataset.view);
        // Close mobile sidebar
        $("#sidebar")?.classList.remove("mobile-open");
        $("#mobileOverlay")?.classList.remove("open");
      });
    });
    // Quick actions
    $$(".quick-action[data-goto]").forEach((el) => {
      on(el, "click", () => navigate(el.dataset.goto));
    });
    // Hash routing
    const hash = window.location.hash.replace("#", "");
    if (hash) navigate("view-" + hash);
  }

  // ── Sidebar ──
  function initSidebar() {
    on($("#btnCollapse"), "click", () => {
      $("#sidebar")?.classList.toggle("collapsed");
    });
    on($("#btnMobileMenu"), "click", () => {
      $("#sidebar")?.classList.add("mobile-open");
      $("#mobileOverlay")?.classList.add("open");
    });
    on($("#mobileOverlay"), "click", () => {
      $("#sidebar")?.classList.remove("mobile-open");
      $("#mobileOverlay")?.classList.remove("open");
    });
  }

  // ── Dashboard / Home ──
  async function loadDashboard() {
    const data = await api("/api/status");
    if (!data.success) return;
    const s = data.stats || {};
    const b = s.billing || {};

    // Stats
    setText("statDms", s.dms_sent || s.dm_count || 0);
    setText("statContacts", b.usage?.contacts || 0);
    setText("statRules", s.active_reels_count || 0);
    setText("statComments", s.comments_replied || 0);

    // Sidebar
    setText("sidebarAccountName", b.workspace?.name || b.workspace?.business || "Workspace");
    const avatar = $("#accountAvatarLetter");
    if (avatar) avatar.textContent = (b.workspace?.name || "W")[0].toUpperCase();
    const badge = $("#sidebarPlanBadge");
    if (badge) {
      badge.textContent = b.label || (b.is_pro ? "PRO" : "FREE");
      badge.classList.toggle("pro", !!b.is_pro);
    }

    // Limits
    const used = b.usage?.contacts || 0;
    const max = b.limits?.contacts || 25;
    setText("limitsCount", `${used} / ${max === -1 ? "∞" : max}`);
    const pct = max === -1 ? 0 : Math.round((used / max) * 100);
    setText("limitsPercent", `${pct}%`);
    const gauge = $("#limitsGauge");
    if (gauge) {
      gauge.classList.toggle("low", pct > 60 && pct < 90);
      gauge.classList.toggle("full", pct >= 90);
    }
    setText("navContactCount", used);

    // Connection checks
    setCheck("checkMeta", s.meta_connected);
    setCheck("checkIG", !!s.meta_account);
    if (s.meta_account) setText("igAccountLabel", `@${s.meta_account}`);
    setCheck("checkWatcher", s.watcher_status === "running" || s.meta_connected);
    setCheck("checkRule", (s.active_reels_count || 0) > 0);

    // Greeting
    const hour = new Date().getHours();
    const greeting = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
    setText("greetingText", `${greeting}. ${s.active_reels_count || 0} automation${(s.active_reels_count || 0) !== 1 ? "s" : ""} running.`);

    // Activity feed
    loadLogs();
  }

  function setCheck(id, ok) {
    const el = $(`#${id}`);
    if (!el) return;
    el.className = `check-icon ${ok ? "pass" : "fail"}`;
    el.textContent = ok ? "✓" : "✕";
  }

  function setText(id, text) {
    const el = $(`#${id}`);
    if (el) el.textContent = text;
  }

  async function loadLogs() {
    const data = await api("/api/logs");
    if (!data.success) return;
    const feed = $("#activityFeed");
    if (!feed) return;
    const logs = (data.logs || []).slice(0, 30);
    if (!logs.length) {
      feed.innerHTML = '<div class="empty-state"><div class="empty-state-title">No activity yet</div><div class="empty-state-text">Events appear here when automations run.</div></div>';
      return;
    }
    feed.innerHTML = logs.map((l) => {
      const cls = (l.level || "").toLowerCase().includes("error") ? "error" : (l.level || "").toLowerCase().includes("warn") ? "warn" : "success";
      return `<div class="feed-item"><div class="feed-dot ${cls}"></div><div class="feed-text">${esc(l.message || l.text || "")}</div><div class="feed-time">${timeAgo(l.timestamp || l.time)}</div></div>`;
    }).join("");
  }

  // ── Automations ──
  async function loadRules() {
    const data = await api("/api/automations");
    if (!data.success) return;
    rules = data.rules || [];
    renderRules(rules);
  }

  function renderRules(list) {
    const container = $("#rulesList");
    if (!container) return;
    if (!list.length) {
      container.innerHTML = `<div class="empty-state"><div class="empty-state-icon"><svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg></div><div class="empty-state-title">No automations yet</div><div class="empty-state-text">Create your first rule to automate Instagram DMs.</div><button class="btn btn-primary" onclick="document.getElementById('btnNewRule').click()">Create first automation</button></div>`;
      return;
    }
    container.innerHTML = list.map((r) => {
      const active = r.is_active !== false;
      const kws = (r.trigger_keywords || []).map((k) => `<span class="tag">${esc(k)}</span>`).join("");
      return `
        <div class="rule-card">
          <div class="status-dot ${active ? "active" : "off"}"></div>
          <div class="rule-info">
            <div class="rule-name">${esc(r.name || "Untitled Rule")}</div>
            <div class="rule-meta">${esc(r.type || "comment_to_dm")} · ${r.trigger_keywords?.length || 0} keywords</div>
            <div class="rule-keywords">${kws}</div>
          </div>
          <div class="rule-actions">
            <label class="toggle"><input type="checkbox" ${active ? "checked" : ""} onchange="window.CF.toggleRule('${r.id}', this.checked)"><span class="toggle-track"></span><span class="toggle-knob"></span></label>
            <button class="btn btn-ghost btn-sm" onclick="window.CF.editRule('${r.id}')">Edit</button>
            <button class="btn btn-ghost btn-sm text-red" onclick="window.CF.deleteRule('${r.id}')">Delete</button>
          </div>
        </div>`;
    }).join("");
  }

  // Rule CRUD
  function openRuleModal(rule = null) {
    editingRuleId = rule?.id || null;
    setText("ruleModalTitle", rule ? "Edit Rule" : "New Automation Rule");
    $("#ruleInputName").value = rule?.name || "";
    $("#ruleInputType").value = rule?.type || "comment_to_dm";
    $("#ruleInputKeywords").value = (rule?.trigger_keywords || []).join(", ");
    $("#ruleInputCommentReply").value = rule?.public_comment_reply || "";
    $("#ruleInputDM").value = rule?.dm_message || rule?.opening_dm || "";
    $("#ruleInputBtnText").value = rule?.button_text || "";
    $("#ruleInputLink").value = rule?.delivery_link || "";
    $("#modalRule")?.classList.add("open");
  }

  async function saveRule() {
    const payload = {
      name: $("#ruleInputName")?.value?.trim(),
      type: $("#ruleInputType")?.value,
      trigger_keywords: ($("#ruleInputKeywords")?.value || "").split(",").map((k) => k.trim()).filter(Boolean),
      public_comment_reply: $("#ruleInputCommentReply")?.value?.trim(),
      dm_message: $("#ruleInputDM")?.value?.trim(),
      button_text: $("#ruleInputBtnText")?.value?.trim(),
      delivery_link: $("#ruleInputLink")?.value?.trim(),
      is_active: true,
    };
    if (!payload.name) return toast("Rule name is required", "error");
    if (!payload.dm_message) return toast("DM message is required", "error");

    if (editingRuleId) payload.id = editingRuleId;
    const data = await api("/api/automations/save", "POST", payload);
    if (data.success) {
      toast(editingRuleId ? "Rule updated" : "Rule created", "success");
      closeModal("modalRule");
      loadRules();
    } else {
      toast(data.error || "Failed to save rule", "error");
    }
  }

  window.CF = {
    toggleRule: async (id, active) => {
      await api("/api/automations/toggle", "POST", { id, is_active: active });
      toast(active ? "Rule activated" : "Rule paused", active ? "success" : "warn");
      loadRules();
    },
    editRule: (id) => {
      const rule = rules.find((r) => r.id === id);
      if (rule) openRuleModal(rule);
    },
    deleteRule: async (id) => {
      if (!confirm("Delete this automation rule?")) return;
      const data = await api("/api/automations/delete", "POST", { id });
      if (data.success) { toast("Rule deleted", "success"); loadRules(); }
      else toast(data.error || "Failed to delete", "error");
    },
  };

  // ── Contacts ──
  async function loadContacts() {
    const data = await api("/api/contacts");
    if (!data.success) return;
    contacts = data.contacts || [];
    const tbody = $("#contactsTableBody");
    if (!tbody) return;
    if (!contacts.length) {
      tbody.innerHTML = '<tr><td colspan="6" class="text-muted" style="text-align:center;padding:40px">No contacts yet.</td></tr>';
      return;
    }
    tbody.innerHTML = contacts.map((c) => {
      const tags = (c.tags || []).map((t) => `<span class="tag">${esc(t)}</span>`).join(" ");
      return `<tr>
        <td><strong>@${esc(c.username || "")}</strong></td>
        <td>${esc(c.name || "")}</td>
        <td class="text-muted">${esc(c.source || "")}</td>
        <td>${tags}</td>
        <td class="text-muted">${shortDate(c.created_at || c.first_seen)}</td>
        <td><button class="btn btn-ghost btn-xs" onclick="window.CF.deleteContact('${c.username}')">×</button></td>
      </tr>`;
    }).join("");
  }

  window.CF.deleteContact = async (username) => {
    if (!confirm(`Remove contact @${username}?`)) return;
    await api("/api/contacts/delete", "POST", { username });
    toast("Contact removed", "success");
    loadContacts();
  };

  // ── Analytics ──
  async function loadAnalytics() {
    const data = await api("/api/insights/summary");
    if (!data.success) return;
    const s = data.summary || {};
    setText("analyticsDms", s.total_dms || 0);
    setText("analyticsLeads", s.total_contacts || 0);
    const rate = s.total_dms > 0 ? Math.round((s.total_contacts / s.total_dms) * 100) : 0;
    setText("analyticsConversion", `${rate}%`);
  }

  // ── Settings ──
  async function loadSettings() {
    const data = await api("/api/meta/config");
    if (!data.success) return;
    const cfg = data.config || {};

    const connected = cfg.enabled && cfg.connected_account_username;
    setText("settingsIGTitle", connected ? `@${cfg.connected_account_username}` : "Not connected");
    setText("settingsIGSubtitle", connected ? "Connected via Meta Graph API" : "Add your access token to connect");

    // Connection checks
    setSettingsCheck("sCheckMeta", cfg.enabled, cfg.enabled ? "Connected" : "Not configured");
    setSettingsCheck("sCheckIG", !!cfg.connected_account_username, cfg.connected_account_username ? `@${cfg.connected_account_username}` : "Pending");
    setSettingsCheck("sCheckBusiness", connected, connected ? "Verified" : "Pending");

    const statusData = await api("/api/status");
    const watcher = statusData?.stats?.watcher_status === "running" || cfg.enabled;
    setSettingsCheck("sCheckWatcher", watcher, watcher ? "Active" : "Inactive");

    const steps = [cfg.enabled, !!cfg.connected_account_username, connected, watcher].filter(Boolean).length;
    setText("connectionStepCount", `${4 - steps} steps left`);

    if (cfg.access_token_masked) {
      const tokenInput = $("#inputAccessToken");
      if (tokenInput) tokenInput.placeholder = cfg.access_token_masked;
    }
  }

  function setSettingsCheck(id, ok, label) {
    const icon = $(`#${id}`);
    if (icon) { icon.className = `check-icon ${ok ? "pass" : "fail"}`; icon.textContent = ok ? "✓" : "✕"; }
    const status = $(`#${id}Status`);
    if (status) {
      status.textContent = label;
      status.className = `badge ${ok ? "badge-green" : "badge-red"}`;
    }
  }

  async function connectToken(token) {
    if (!token) return toast("Please paste an access token", "error");
    const result = await api("/api/meta/test", "POST", { access_token: token });
    if (result.success) {
      await api("/api/meta/save", "POST", { access_token: token, enabled: true });
      toast("Instagram connected successfully!", "success");
      closeModal("modalToken");
      loadSettings();
      loadDashboard();
    } else {
      toast(result.error || result.message || "Connection failed", "error");
    }
  }

  // ── Billing ──
  async function loadBilling() {
    const data = await api("/api/billing/status");
    if (!data.success) return;
    const b = data.billing || {};
    const plans = data.plans || [];

    setText("currentPlanName", b.label || b.plan_name || "Free");
    setText("currentPlanExpiry", b.expired ? "Plan expired" : b.days_left !== undefined ? `${b.days_left} days remaining` : "Active");

    const limits = b.limits || {};
    const usage = b.usage || {};
    setText("billingAutomations", `${usage.automations || 0} / ${limits.automations === -1 ? "∞" : limits.automations || 1}`);
    setText("billingContacts", `${usage.contacts || 0} / ${limits.contacts === -1 ? "∞" : limits.contacts || 25}`);
    setText("billingDms", `${usage.dms_this_month || 0} / ${limits.dms_per_month === -1 ? "∞" : limits.dms_per_month || 50}`);

    // Plans grid
    const grid = $("#plansGrid");
    if (grid && plans.length) {
      grid.innerHTML = plans.map((p) => {
        const isCurrent = p.id === b.plan_id;
        const featured = p.featured || p.recommended;
        return `
          <div class="plan-card${featured ? " featured" : ""}">
            <div class="plan-name">${esc(p.name)}</div>
            <div class="plan-price"><span class="currency">₹</span>${p.price_monthly || 0}<span class="period">/mo</span></div>
            <ul class="plan-features">
              <li>${(p.limits?.automations ?? 1) === -1 ? "Unlimited" : p.limits?.automations || 1} automations</li>
              <li>${(p.limits?.contacts ?? 25) === -1 ? "Unlimited" : p.limits?.contacts || 25} contacts</li>
              <li>${(p.limits?.dms_per_month ?? 50) === -1 ? "Unlimited" : p.limits?.dms_per_month || 50} DMs/month</li>
            </ul>
            <button class="btn ${isCurrent ? "btn-secondary" : "btn-primary"} btn-block" ${isCurrent ? "disabled" : ""} onclick="window.CF.checkout('${p.id}')">${isCurrent ? "Current Plan" : "Choose Plan"}</button>
          </div>`;
      }).join("");
    }

    // Payment history
    const user = b.workspace?.id;
    if (user) {
      const userData = await api(`/api/users/${user}`);
      const payments = userData?.user?.payments || [];
      const tbody = $("#paymentHistoryBody");
      if (tbody && payments.length) {
        tbody.innerHTML = payments.map((p) => `
          <tr>
            <td>${shortDate(p.date)}</td>
            <td>${esc(p.plan || "—")}</td>
            <td>₹${p.amount || 0}</td>
            <td><span class="badge badge-green">${p.status || "paid"}</span></td>
            <td>${esc(p.method || "—")}</td>
          </tr>`).join("");
      }
    }
  }

  // Razorpay checkout
  window.CF.checkout = async (planId) => {
    const gw = await api("/api/billing/gateway");
    if (!gw.ready) {
      toast("Payment gateway not configured. Contact admin.", "warn");
      // Fallback: direct upgrade
      const res = await api("/api/billing/upgrade", "POST", { plan_id: planId });
      if (res.success) { toast("Plan upgraded!", "success"); loadBilling(); loadDashboard(); }
      return;
    }

    const coupon = $("#inputCoupon")?.value?.trim() || undefined;
    const order = await api("/api/billing/checkout", "POST", { plan_id: planId, coupon });
    if (!order.success) return toast(order.error || "Checkout failed", "error");
    if (order.free) { toast("Plan activated!", "success"); loadBilling(); loadDashboard(); return; }

    const options = {
      key: order.order.key_id,
      amount: order.order.amount,
      currency: order.order.currency || "INR",
      name: order.brand || "ConverFlow",
      description: `${order.plan.name} Plan`,
      order_id: order.order.order_id,
      prefill: order.prefill || {},
      theme: { color: "#000000" },
      handler: async (response) => {
        const verify = await api("/api/billing/verify", "POST", {
          razorpay_order_id: response.razorpay_order_id,
          razorpay_payment_id: response.razorpay_payment_id,
          razorpay_signature: response.razorpay_signature,
          plan_id: planId,
          coupon,
          amount: order.amount_inr,
        });
        if (verify.success) {
          toast("Payment successful! Plan upgraded.", "success");
          loadBilling();
          loadDashboard();
        } else {
          toast(verify.error || "Verification failed", "error");
        }
      },
    };

    if (typeof Razorpay !== "undefined") {
      new Razorpay(options).open();
    } else {
      const script = document.createElement("script");
      script.src = "https://checkout.razorpay.com/v1/checkout.js";
      script.onload = () => new Razorpay(options).open();
      document.head.appendChild(script);
    }
  };

  // Coupon preview
  on($("#btnApplyCoupon"), "click", async () => {
    const code = $("#inputCoupon")?.value?.trim();
    if (!code) return;
    const res = await api("/api/billing/coupon", "POST", { code });
    const el = $("#couponResult");
    if (el) {
      el.textContent = res.success ? `✓ ${res.discount_label || "Coupon applied"} → ₹${res.final_price}` : res.error || "Invalid coupon";
      el.style.color = res.success ? "var(--green)" : "var(--red)";
    }
  });

  // ── Modals ──
  function closeModal(id) {
    $(`#${id}`)?.classList.remove("open");
  }

  function initModals() {
    // Rule modal
    on($("#btnNewRule"), "click", () => openRuleModal());
    on($("#btnNewRuleEmpty"), "click", () => openRuleModal());
    on($("#btnCloseRuleModal"), "click", () => closeModal("modalRule"));
    on($("#btnCancelRule"), "click", () => closeModal("modalRule"));
    on($("#btnSaveRule"), "click", saveRule);

    // Token modal
    on($("#btnConnectToken"), "click", () => $("#modalToken")?.classList.add("open"));
    on($("#btnCloseTokenModal"), "click", () => closeModal("modalToken"));
    on($("#btnCancelToken"), "click", () => closeModal("modalToken"));
    on($("#btnSubmitToken"), "click", () => connectToken($("#modalTokenInput")?.value?.trim()));

    // Settings token save
    on($("#btnSaveToken"), "click", () => connectToken($("#inputAccessToken")?.value?.trim()));
    on($("#btnTestToken"), "click", async () => {
      const token = $("#inputAccessToken")?.value?.trim();
      if (!token) return toast("Enter an access token", "error");
      const res = await api("/api/meta/test", "POST", { access_token: token });
      toast(res.success ? "Connection successful!" : (res.error || "Failed"), res.success ? "success" : "error");
    });

    // Close modals on overlay click
    $$(".modal-overlay").forEach((overlay) => {
      on(overlay, "click", (e) => { if (e.target === overlay) overlay.classList.remove("open"); });
    });

    // Refresh buttons
    on($("#btnRefreshStatus"), "click", loadDashboard);
    on($("#btnRefreshSettings"), "click", loadSettings);
    on($("#btnClearLogs"), "click", async () => {
      await api("/api/logs/clear", "POST");
      loadLogs();
    });

    // Billing
    on($("#btnChangePlan"), "click", () => navigate("view-billing"));
    on($("#btnUpgrade"), "click", () => navigate("view-billing"));

    // CSV Export
    on($("#btnExportCSV"), "click", () => {
      window.open("/api/contacts/export", "_blank");
    });

    // Automation tabs
    $$("#automationTabs .tab-btn").forEach((btn) => {
      on(btn, "click", () => {
        $$("#automationTabs .tab-btn").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        const tab = btn.dataset.tab;
        if (tab === "all") renderRules(rules);
        else if (tab === "active") renderRules(rules.filter((r) => r.is_active !== false));
        else if (tab === "paused") renderRules(rules.filter((r) => r.is_active === false));
      });
    });
  }

  // ── Utilities ──
  function esc(s) { const d = document.createElement("div"); d.textContent = s || ""; return d.innerHTML; }

  function timeAgo(ts) {
    if (!ts) return "";
    const d = new Date(ts);
    const diff = (Date.now() - d.getTime()) / 1000;
    if (diff < 60) return "now";
    if (diff < 3600) return `${Math.floor(diff / 60)}m`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h`;
    return `${Math.floor(diff / 86400)}d`;
  }

  function shortDate(ts) {
    if (!ts) return "—";
    try { return new Date(ts).toLocaleDateString("en-IN", { day: "numeric", month: "short" }); }
    catch { return ts; }
  }

  // ── Init ──
  function init() {
    initNav();
    initSidebar();
    initModals();
    loadDashboard();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
