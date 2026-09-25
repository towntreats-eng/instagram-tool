/**
 * ConverFlow — Systematic Dashboard JS
 * =============================================================
 * Handles: navigation, breadcrumbs, API calls, modals,
 *          automations CRUD, Live Simulator, contacts CRM,
 *          billing with Razorpay INR checkout, toasts.
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
      success: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#16a34a" stroke-width="2.5"><path d="M20 6L9 17l-5-5"/></svg>',
      error: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#dc2626" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><path d="M15 9l-6 6M9 9l6 6"/></svg>',
      warn: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#d97706" stroke-width="2.5"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
      info: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#2563eb" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>',
    };
    const t = document.createElement("div");
    t.className = `toast ${type}`;
    t.innerHTML = `<span class="toast-icon">${icons[type] || icons.info}</span><span>${msg}</span>`;
    c.appendChild(t);
    setTimeout(() => {
      t.style.opacity = "0";
      setTimeout(() => t.remove(), 300);
    }, 4000);
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
  const viewTitles = {
    "view-home": "Dashboard",
    "view-automations": "Automations",
    "view-simulator": "Live Simulator",
    "view-contacts": "Contacts CRM",
    "view-broadcast": "Broadcast",
    "view-analytics": "Analytics",
    "view-settings": "Settings & Meta API",
    "view-billing": "Billing & Razorpay",
  };

  function navigate(viewId) {
    $$(".content-view").forEach((v) => v.classList.remove("active"));
    const target = $(`#${viewId}`);
    if (target) target.classList.add("active");

    $$(".nav-item").forEach((n) => n.classList.remove("active"));
    const navLink = $(`.nav-item[data-view="${viewId}"]`);
    if (navLink) navLink.classList.add("active");

    currentView = viewId;
    window.location.hash = viewId.replace("view-", "");

    // Update topbar breadcrumb
    const bc = $("#breadcrumbActive");
    if (bc) bc.textContent = viewTitles[viewId] || "Console";

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
        $("#sidebar")?.classList.remove("mobile-open");
        $("#mobileOverlay")?.classList.remove("open");
      });
    });

    // Quick action clicks
    $$(".quick-action[data-goto]").forEach((el) => {
      on(el, "click", () => navigate(el.dataset.goto));
    });

    // Header simulator button
    on($("#btnHeaderSimulator"), "click", () => navigate("view-simulator"));

    // Hash routing
    const hash = window.location.hash.replace("#", "");
    if (hash && $(`#view-${hash}`)) navigate("view-" + hash);
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

    // Sidebar Account & Badges
    const acctName = s.meta_account || b.workspace?.name || "satnamwebservices";
    setText("sidebarAccountName", acctName);
    setText("headerAccountName", `@${acctName}`);
    const avatar = $("#accountAvatarLetter");
    if (avatar) avatar.textContent = acctName[0].toUpperCase();

    const badge = $("#sidebarPlanBadge");
    if (badge) {
      badge.textContent = b.label || (b.is_pro ? "PRO" : "FREE");
    }

    // Limits
    const used = b.usage?.contacts || 0;
    const max = b.limits?.contacts || 25;
    setText("limitsCount", `${used} / ${max === -1 ? "∞" : max}`);
    const pct = max === -1 ? 0 : Math.min(100, Math.round((used / max) * 100));
    setText("limitsPercent", `${pct}%`);
    setText("navContactCount", used);

    // Connection checks
    setCheck("checkMeta", s.meta_connected);
    setCheck("checkIG", !!s.meta_account || s.meta_connected);
    if (s.meta_account) setText("igAccountLabel", `Connected as @${s.meta_account}`);
    setCheck("checkWatcher", s.watcher_status === "running" || s.meta_connected);
    setCheck("checkRule", (s.active_reels_count || 0) > 0);
    setText("ruleHealthSubtitle", `${s.active_reels_count || 0} active automation rule${(s.active_reels_count || 0) === 1 ? "" : "s"}`);

    // Checklist cards
    if (s.meta_connected) $("#stepIgCheck")?.classList.add("done");
    if ((s.active_reels_count || 0) > 0) $("#stepRuleCheck")?.classList.add("done");

    // Header Status Dot
    const dot = $("#headerStatusDot");
    if (dot) {
      dot.className = s.meta_connected ? "status-pill-dot" : "status-pill-dot offline";
    }

    // Greeting
    const hour = new Date().getHours();
    const greeting = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
    setText("greetingText", `${greeting} — Instagram channel @${acctName} is active with ${s.active_reels_count || 0} active rules.`);

    // Load logs and rule count
    loadLogs();
    loadRules(false);
  }

  function setCheck(id, ok) {
    const el = $(`#${id}`);
    if (!el) return;
    el.className = `check-icon ${ok ? "ok" : "wait"}`;
    el.textContent = ok ? "✓" : "—";
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
      feed.innerHTML = '<div class="empty-state"><div class="empty-state-title">No activity recorded yet</div><div class="empty-state-text">Events appear here when automations process comments and DMs.</div></div>';
      return;
    }
    feed.innerHTML = logs.map((l) => {
      const type = (l.type || "INFO").toUpperCase();
      const dotStyle = type === "SUCCESS" ? "background:#16a34a" : type === "ERROR" ? "background:#dc2626" : "background:#09090b";
      return `
        <div class="feed-item">
          <div class="feed-msg">
            <span class="feed-dot" style="${dotStyle}"></span>
            <span style="font-weight:600;font-size:11px;font-family:var(--font-mono)">${type}</span>
            <span>${esc(l.message || l.text || "")}</span>
          </div>
          <span class="feed-time">${timeAgo(l.timestamp || l.time)}</span>
        </div>
      `;
    }).join("");
  }

  // ── Automations CRUD ──
  async function loadRules(render = true) {
    const data = await api("/api/rules");
    if (!data.success) return;
    rules = data.rules || [];
    setText("navRuleCount", rules.length);
    if (render) renderRules(rules);
  }

  function renderRules(list) {
    const container = $("#rulesList");
    if (!container) return;
    if (!list.length) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon"><svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg></div>
          <div class="empty-state-title">No automation rules found</div>
          <div class="empty-state-text">Create a rule that listens for keywords on your Reels and sends an instant DM.</div>
          <button class="btn btn-primary" id="btnNewRuleEmptyInner">Create First Rule</button>
        </div>
      `;
      on($("#btnNewRuleEmptyInner"), "click", openRuleModal);
      return;
    }

    container.innerHTML = list.map((r) => {
      const isActive = r.is_active !== false;
      const typeLabel = r.type === "dm_keyword" ? "DM Keyword" : "Comment → DM";
      const kw = Array.isArray(r.keywords) ? r.keywords.join(", ") : (r.keyword || r.keywords || "*");
      const replyPreview = r.dm_message || r.response_text || "Automated response";

      return `
        <div class="rule-card" data-id="${r.id}">
          <div class="rule-info">
            <span class="rule-type-badge">${typeLabel}</span>
            <div>
              <div class="rule-title">${esc(r.name || r.title || "Keyword Trigger")}</div>
              <div class="rule-trigger-summary">
                Keywords: <strong>${esc(kw)}</strong> · DM: "${esc(replyPreview.slice(0, 50))}${replyPreview.length > 50 ? '...' : ''}"
              </div>
            </div>
          </div>
          <div class="rule-actions">
            <span class="badge ${isActive ? 'badge-active' : 'badge-paused'}">${isActive ? 'Active' : 'Paused'}</span>
            <label class="switch">
              <input type="checkbox" class="rule-toggle" data-id="${r.id}" ${isActive ? "checked" : ""}>
              <span class="slider"></span>
            </label>
            <button class="btn btn-secondary btn-sm btn-edit-rule" data-id="${r.id}">Edit</button>
            <button class="btn btn-danger btn-sm btn-del-rule" data-id="${r.id}">Delete</button>
          </div>
        </div>
      `;
    }).join("");

    // Toggle listener
    $$(".rule-toggle", container).forEach((cb) => {
      on(cb, "change", async () => {
        const id = cb.dataset.id;
        const res = await api(`/api/rules/${id}/toggle`, "POST");
        if (res.success) {
          toast(res.is_active ? "Rule enabled" : "Rule paused", "info");
          loadDashboard();
        } else {
          toast(res.error || "Toggle failed", "error");
          cb.checked = !cb.checked;
        }
      });
    });

    // Edit listener
    $$(".btn-edit-rule", container).forEach((btn) => {
      on(btn, "click", () => {
        const r = rules.find((x) => String(x.id) === String(btn.dataset.id));
        if (r) openRuleModal(r);
      });
    });

    // Delete listener
    $$(".btn-del-rule", container).forEach((btn) => {
      on(btn, "click", async () => {
        if (!confirm("Are you sure you want to delete this rule?")) return;
        const res = await api(`/api/rules/${btn.dataset.id}`, "DELETE");
        if (res.success) {
          toast("Rule deleted", "info");
          loadRules();
          loadDashboard();
        } else {
          toast(res.error || "Delete failed", "error");
        }
      });
    });
  }

  function openRuleModal(rule = null) {
    editingRuleId = rule ? rule.id : null;
    setText("ruleModalTitle", rule ? "Edit Automation Rule" : "Create Automation Rule");
    $("#ruleInputName").value = rule ? (rule.name || rule.title || "") : "";
    $("#ruleInputType").value = rule ? (rule.type || "comment_to_dm") : "comment_to_dm";
    $("#ruleInputKeywords").value = rule ? (Array.isArray(rule.keywords) ? rule.keywords.join(", ") : (rule.keyword || rule.keywords || "")) : "LINK, INFO";
    $("#ruleInputCommentReply").value = rule ? (rule.comment_reply || "") : "Sent you the details in your DM! 🚀";
    $("#ruleInputDM").value = rule ? (rule.dm_message || rule.response_text || "") : "Hey {name}! Here is the direct link you requested:";
    $("#ruleInputBtnText").value = rule ? (rule.button_text || "") : "Access Resource";
    $("#ruleInputLink").value = rule ? (rule.link_url || rule.link || "") : "";
    $("#modalRule")?.classList.add("open");
  }

  async function saveRule() {
    const name = $("#ruleInputName")?.value?.trim();
    if (!name) return toast("Please give your rule a name", "error");
    const keywords = $("#ruleInputKeywords")?.value?.split(",").map((k) => k.trim()).filter(Boolean);
    const body = {
      name,
      type: $("#ruleInputType")?.value || "comment_to_dm",
      keywords: keywords.length ? keywords : ["*"],
      comment_reply: $("#ruleInputCommentReply")?.value?.trim() || "",
      dm_message: $("#ruleInputDM")?.value?.trim() || "",
      button_text: $("#ruleInputBtnText")?.value?.trim() || "",
      link_url: $("#ruleInputLink")?.value?.trim() || "",
      is_active: true,
    };

    let res;
    if (editingRuleId) {
      res = await api(`/api/rules/${editingRuleId}`, "PUT", body);
    } else {
      res = await api("/api/rules", "POST", body);
    }

    if (res.success) {
      toast(editingRuleId ? "Rule updated successfully" : "Rule created and activated", "success");
      closeModal("modalRule");
      loadRules();
      loadDashboard();
    } else {
      toast(res.error || "Save failed", "error");
    }
  }

  // ── Live Simulator (Human Touch) ──
  function initSimulator() {
    on($("#btnRunSimulation"), "click", () => {
      const user = $("#simUsername")?.value?.trim() || "rahul_sharma";
      const comment = $("#simComment")?.value?.trim() || "LINK";
      const chat = $("#phoneChat");
      const log = $("#simResultLog");
      if (!chat) return;

      // Find matching rule
      const commentUpper = comment.toUpperCase();
      let matchedRule = null;
      for (const r of rules) {
        if (r.is_active === false) continue;
        const kws = Array.isArray(r.keywords) ? r.keywords : [r.keyword || "*"];
        for (const k of kws) {
          if (k === "*" || commentUpper.includes(k.toUpperCase().trim())) {
            matchedRule = r;
            break;
          }
        }
        if (matchedRule) break;
      }

      // Render in phone mockup
      const dmText = matchedRule ? (matchedRule.dm_message || `Hey @${user}! Here is your link:`) : `Hey @${user}! Thanks for reaching out. Let us know how we can help you today!`;
      const btnText = matchedRule?.button_text || "Get Access";
      const btnLink = matchedRule?.link_url || "#";

      chat.innerHTML = `
        <div class="chat-bubble user">${esc(comment)}</div>
        <div class="chat-bubble bot">
          ${esc(dmText)}
          ${btnText ? `<a href="${btnLink}" class="chat-bubble-btn" target="_blank">${esc(btnText)}</a>` : ""}
        </div>
      `;

      if (log) {
        if (matchedRule) {
          log.innerHTML = `
            <div class="feed-item">
              <div class="feed-msg">
                <span class="feed-dot" style="background:#16a34a"></span>
                <span>Matched rule: <strong>${esc(matchedRule.name)}</strong> for keyword "${esc(comment)}".</span>
              </div>
              <span class="badge badge-active">PASS</span>
            </div>
            <div class="feed-item">
              <div class="feed-msg">
                <span class="feed-dot"></span>
                <span>Public comment reply queued: "${esc(matchedRule.comment_reply || 'Check your DM!')}"</span>
              </div>
            </div>
          `;
        } else {
          log.innerHTML = `
            <div class="feed-item">
              <div class="feed-msg">
                <span class="feed-dot" style="background:#d97706"></span>
                <span>No active rule matched keyword "${esc(comment)}". Using default fallback message.</span>
              </div>
              <span class="badge badge-warning">FALLBACK</span>
            </div>
          `;
        }
      }

      toast("Simulation executed", "success");
    });
  }

  // ── Contacts CRM ──
  async function loadContacts() {
    const data = await api("/api/contacts");
    if (!data.success) return;
    contacts = data.contacts || [];
    const tbody = $("#contactsTableBody");
    if (!tbody) return;
    if (!contacts.length) {
      tbody.innerHTML = '<tr><td colspan="5" class="text-muted" style="text-align:center;padding:40px">No contacts yet. When users comment on your Instagram posts, they will be catalogued here.</td></tr>';
      return;
    }
    tbody.innerHTML = contacts.map((c) => `
      <tr>
        <td style="font-weight:600">@${esc(c.username || c.handle || "user")}</td>
        <td>${esc(c.name || c.full_name || "—")}</td>
        <td><span class="badge badge-neutral">${esc(c.source || "Reel Comment")}</span></td>
        <td><span class="badge badge-active">Captured</span></td>
        <td style="font-family:var(--font-mono);font-size:12px;color:var(--text-muted)">${shortDate(c.created_at || c.date)}</td>
      </tr>
    `).join("");
  }

  // ── Analytics ──
  async function loadAnalytics() {
    const data = await api("/api/analytics");
    if (!data.success) return;
    const a = data.analytics || {};
    setText("analyticsDms", a.total_dms || 0);
    setText("analyticsLeads", a.total_leads || 0);
    setText("analyticsConversion", a.conversion_rate || "0%");
    setText("analyticsResponse", a.avg_latency || "< 1.2s");
  }

  // ── Settings ──
  async function loadSettings() {
    const data = await api("/api/status");
    if (!data.success) return;
    const s = data.stats || {};
    if (s.meta_account) {
      setText("settingsIGTitle", `@${s.meta_account}`);
      setText("settingsIGSubtitle", `Connected Instagram Account · ${s.active_reels_count || 0} active automations`);
    }
  }

  async function connectToken(token) {
    if (!token) return toast("Please enter an access token", "error");
    const res = await api("/api/meta/token", "POST", { access_token: token });
    if (res.success) {
      toast("Instagram token connected!", "success");
      closeModal("modalToken");
      loadDashboard();
      loadSettings();
    } else {
      toast(res.error || "Failed to connect token", "error");
    }
  }

  // ── Billing & Razorpay ──
  async function loadBilling() {
    const [subRes, plansRes] = await Promise.all([
      api("/api/subscription"),
      api("/api/plans"),
    ]);

    if (subRes.success && subRes.subscription) {
      const sub = subRes.subscription;
      setText("currentPlanName", sub.plan_name || "Free Trial");
      setText("currentPlanExpiry", sub.expiry_text || (sub.days_left ? `${sub.days_left} days remaining` : "Active"));
      if (sub.limits) {
        setText("billingAutomations", `${sub.usage?.automations || 0} / ${sub.limits.automations === -1 ? '∞' : sub.limits.automations}`);
        setText("billingContacts", `${sub.usage?.contacts || 0} / ${sub.limits.contacts === -1 ? '∞' : sub.limits.contacts}`);
        setText("billingDms", `${sub.usage?.dms || 0} / ${sub.limits.dms_per_month === -1 ? '∞' : sub.limits.dms_per_month}`);
      }
    }

    if (plansRes.success && plansRes.plans) {
      renderPlans(plansRes.plans);
    }

    // Payment history
    loadPaymentHistory();
  }

  function renderPlans(plans) {
    const container = $("#plansGrid");
    if (!container) return;
    container.innerHTML = plans.map((p) => {
      const isCurrent = p.is_current;
      const isFeatured = p.featured || p.id === "growth" || p.id === "pro";
      const priceStr = p.price_monthly ? `₹${p.price_monthly}` : "Free";

      return `
        <div class="plan-card ${isFeatured ? 'featured' : ''}">
          ${isFeatured ? '<span class="plan-badge-featured">Most Popular</span>' : ''}
          <div class="plan-name">${esc(p.name)}</div>
          <div class="plan-price">${priceStr}</div>
          <div class="plan-period">${p.price_monthly ? 'per month + GST' : 'no credit card needed'}</div>
          <ul class="plan-features">
            <li class="plan-feature-item"><span class="plan-feature-check">✓</span> ${p.automations_limit === -1 ? 'Unlimited' : p.automations_limit} Automations</li>
            <li class="plan-feature-item"><span class="plan-feature-check">✓</span> ${p.contacts_limit === -1 ? 'Unlimited' : p.contacts_limit} Contacts CRM</li>
            <li class="plan-feature-item"><span class="plan-feature-check">✓</span> ${p.dms_limit === -1 ? 'Unlimited' : p.dms_limit} Monthly DMs</li>
            <li class="plan-feature-item"><span class="plan-feature-check">✓</span> Instant Webhook Response</li>
            <li class="plan-feature-item"><span class="plan-feature-check">✓</span> Priority Support</li>
          </ul>
          <button class="btn ${isFeatured ? 'btn-primary' : 'btn-secondary'} btn-lg" onclick="window.upgradeTo('${p.id}')">
            ${isCurrent ? 'Current Plan' : (p.price_monthly ? `Pay ${priceStr} with Razorpay` : 'Select Free')}
          </button>
        </div>
      `;
    }).join("");
  }

  async function loadPaymentHistory() {
    const res = await api("/api/billing/history");
    const tbody = $("#paymentHistoryBody");
    if (!tbody) return;
    if (!res.success || !res.payments || !res.payments.length) {
      tbody.innerHTML = '<tr><td colspan="5" class="text-muted" style="text-align:center;padding:30px">No payment transactions recorded yet.</td></tr>';
      return;
    }
    tbody.innerHTML = res.payments.map((p) => `
      <tr>
        <td style="font-family:var(--font-mono);font-size:12px">${shortDate(p.date)}</td>
        <td style="font-weight:600">${esc(p.plan)}</td>
        <td style="font-family:var(--font-mono)">₹${p.amount}</td>
        <td><span class="badge badge-active">${esc(p.status || 'Paid')}</span></td>
        <td style="font-family:var(--font-mono);font-size:11px;color:var(--text-muted)">${esc(p.id)}</td>
      </tr>
    `).join("");
  }

  // Razorpay Checkout handler
  window.upgradeTo = async function (planId) {
    const coupon = $("#inputCoupon")?.value?.trim() || null;
    toast("Creating checkout order...", "info");

    const order = await api("/api/billing/checkout", "POST", { plan_id: planId, coupon });
    if (!order.success) {
      return toast(order.error || "Could not create checkout order", "error");
    }

    if (order.free) {
      toast("Plan updated successfully!", "success");
      loadBilling();
      loadDashboard();
      return;
    }

    // Launch Razorpay standard modal
    const options = {
      key: order.order.key_id,
      amount: order.order.amount,
      currency: order.order.currency || "INR",
      name: "ConverFlow",
      description: `${order.plan.name} Subscription`,
      order_id: order.order.order_id,
      prefill: order.prefill || {},
      theme: { color: "#09090b" },
      handler: async (response) => {
        toast("Verifying payment signature...", "info");
        const verify = await api("/api/billing/verify", "POST", {
          razorpay_order_id: response.razorpay_order_id,
          razorpay_payment_id: response.razorpay_payment_id,
          razorpay_signature: response.razorpay_signature,
          plan_id: planId,
          coupon,
          amount: order.amount_inr,
        });
        if (verify.success) {
          toast("Payment verified! Plan upgraded.", "success");
          loadBilling();
          loadDashboard();
        } else {
          toast(verify.error || "Payment verification failed", "error");
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

  // Coupon apply
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

  // ── Modals & Actions ──
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
      toast(res.success ? "Instagram token verified successfully!" : (res.error || "Token test failed"), res.success ? "success" : "error");
    });

    // Close on overlay
    $$(".modal-overlay").forEach((overlay) => {
      on(overlay, "click", (e) => { if (e.target === overlay) overlay.classList.remove("open"); });
    });

    // Refresh buttons
    on($("#btnRefreshStatus"), "click", loadDashboard);
    on($("#btnRefreshSettings"), "click", loadSettings);
    on($("#btnClearLogs"), "click", async () => {
      await api("/api/logs/clear", "POST");
      loadLogs();
      toast("Logs cleared", "info");
    });

    // Billing buttons
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
  function esc(s) {
    const d = document.createElement("div");
    d.textContent = s || "";
    return d.innerHTML;
  }

  function timeAgo(ts) {
    if (!ts) return "";
    const d = new Date(ts);
    const diff = (Date.now() - d.getTime()) / 1000;
    if (diff < 60) return "just now";
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
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
    initSimulator();
    loadDashboard();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
