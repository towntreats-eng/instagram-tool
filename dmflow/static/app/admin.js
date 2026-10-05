(function () {
  "use strict";

  function $(s) { return document.querySelector(s); }
  function $$(s) { return Array.from(document.querySelectorAll(s)); }
  function esc(v) {
    return String(v == null ? "" : v).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function ago(ts) {
    if (!ts) return "-";
    var s = Math.max(0, Math.round(Date.now() / 1000 - ts));
    return s < 60 ? s + "s ago" : s < 3600 ? Math.floor(s / 60) + "m ago" : s < 86400 ? Math.floor(s / 3600) + "h ago" : Math.floor(s / 86400) + "d ago";
  }

  var tt;
  function toast(m, bad) {
    var t = $("#toast");
    t.textContent = m;
    t.className = "toast show" + (bad ? " err" : "");
    clearTimeout(tt);
    tt = setTimeout(function () { t.className = "toast"; }, 3200);
  }

  async function api(path, options) {
    options = options || {};
    try {
      var res = await fetch(path, {
        method: options.method || "GET",
        credentials: "same-origin",
        headers: options.body ? { "Content-Type": "application/json" } : {},
        body: options.body ? JSON.stringify(options.body) : undefined
      });
      if (res.status === 401) {
        location.href = "/login?next=/admin";
        return { success: false };
      }
      if (res.status === 403) {
        // If forbidden, reload login
        location.href = "/login";
        return { success: false };
      }
      return await res.json();
    } catch (e) {
      return { success: false, error: e.message };
    }
  }

  window.closeModal = function (id) {
    var m = document.getElementById(id);
    if (m) m.style.display = "none";
  };
  function openModal(id) {
    var m = document.getElementById(id);
    if (m) m.style.display = "grid";
  }

  // State
  var currentUsers = [];
  var currentPlans = [];
  var currentTickets = [];
  var activeUserFilter = "all";
  var activeTicketFilter = "all";

  // Navigation
  $$("#adminNav button").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var tab = btn.dataset.tab;
      $$("#adminNav button").forEach(function (b) { b.classList.remove("active"); });
      btn.classList.add("active");
      $$(".adm-tab-section").forEach(function (sec) { sec.style.display = "none"; });
      var target = document.getElementById("tab-" + tab);
      if (target) target.style.display = "block";

      var titles = {
        overview: ["Overview & Stats", "Real-time pulse of your DM Flow SaaS platform"],
        users: ["Customer Management & Lifetime VIP", "Control user accounts, grant free lifetime access, and manage subscriptions"],
        plans: ["Subscription Plans & Limits", "Customize pricing packages, monthly DM caps, and feature flags"],
        tickets: ["Customer Support Tickets", "Respond to customer inquiries and resolve support tickets directly"],
        offers: ["Offers & Promotional Coupons", "Create discount vouchers and free promotional lifetime passes"],
        billing: ["Payment Gateway Settings", "Configure Razorpay, Stripe, and checkout currencies"],
        email: ["Email & SMTP Configuration", "Setup transactional email delivery and test live SMTP connection"],
        meta: ["Meta & Instagram App Setup", "Manage Facebook/Instagram App secrets and webhook subscriptions"],
        platform: ["Platform & Brand Settings", "Brand name, maintenance mode, signups toggle, and broadcast banners"]
      };
      if (titles[tab]) {
        $("#viewTitle").textContent = titles[tab][0];
        $("#viewSubtitle").textContent = titles[tab][1];
      }

      // Load specific tab data
      if (tab === "overview") loadOverview();
      else if (tab === "users") loadUsers();
      else if (tab === "plans") loadPlans();
      else if (tab === "tickets") loadTickets();
      else if (tab === "offers") loadOffers();
      else if (tab === "billing") loadBilling();
      else if (tab === "email") loadEmail();
      else if (tab === "meta") loadMeta();
      else if (tab === "platform") loadPlatform();
    });
  });

  $("#btnRefresh").addEventListener("click", function () {
    var activeBtn = $("#adminNav button.active");
    if (activeBtn) activeBtn.click();
    toast("Refreshed");
  });

  // Logout
  $("#adminLogoutBtn").addEventListener("click", async function () {
    if (!confirm("Sign out of the Owner Command Center?")) return;
    await api("/api/auth/logout", { method: "POST" });
    location.href = "/login";
  });

  // ========================================================== OVERVIEW
  async function loadOverview() {
    var out = await api("/api/admin/overview");
    if (!out.success) return;
    var s = out.stats || {};
    $("#kpiUsers").textContent = s.total_users || 0;
    $("#kpiActiveUsers").textContent = s.active_users || 0;
    $("#kpiLifetime").textContent = s.lifetime_users || 0;
    $("#kpiDMs").textContent = (s.dms_this_month || 0).toLocaleString();
    $("#kpiLiveFlows").textContent = s.live_flows || 0;
    $("#kpiTickets").textContent = s.open_tickets || 0;
    $("#kpiIg").textContent = s.connected_ig || 0;

    // Badge
    var b = $("#navTicketsBadge");
    if (s.open_tickets > 0) {
      b.textContent = s.open_tickets;
      b.style.display = "inline-block";
    } else {
      b.style.display = "none";
    }

    var sys = out.system || {};
    var w = sys.last_webhook || {}, p = sys.last_poll || {};
    $("#overviewHealth").innerHTML =
      '<div class="copy-box"><span class="title">Meta Webhook</span>' +
      (w.at ? (w.ok ? '<span class="adm-pill emerald">● Receiving (' + ago(w.at) + ')</span>' : '<span class="adm-pill rose">● Refused (' + ago(w.at) + ')</span>') : '<span class="adm-pill dim">Waiting for Meta event</span>') +
      '</div>' +
      '<div class="copy-box"><span class="title">Comment Poller</span>' +
      (p.at ? '<span class="adm-pill emerald">● Active (' + ago(p.at) + ' &middot; ' + (p.accounts || 0) + ' accounts)</span>' : '<span class="adm-pill dim">Initialized</span>') +
      '</div>' +
      '<div class="copy-box"><span class="title">Database Engine</span><span class="adm-pill indigo">● ' + esc(sys.storage).toUpperCase() + '</span></div>' +
      '<div class="copy-box"><span class="title">Mail SMTP</span>' +
      (sys.smtp_configured ? '<span class="adm-pill emerald">● Configured</span>' : '<span class="adm-pill dim">Not configured</span>') +
      '</div>';

    // Recent Users
    var ru = out.recent_users || [];
    $("#overviewRecentUsers").innerHTML = ru.length ? ru.map(function (u) {
      return '<tr><td><b>' + esc(u.name || "Customer") + '</b><div style="font-size:11.5px;color:var(--adm-dim);">' + esc(u.email) + '</div></td>' +
        '<td><span class="adm-pill dim">' + esc(u.plan) + '</span></td>' +
        '<td>' + (u.is_lifetime ? '<span class="adm-pill gold">🌟 VIP</span>' : '<button class="adm-btn adm-btn-gold adm-btn-sm" onclick="grantLifetimeDirect(\'' + esc(u.id) + '\', true)">Grant VIP</button>') + '</td>' +
        '<td style="font-size:12px;color:var(--adm-muted);">' + ago(u.created_at) + '</td></tr>';
    }).join("") : '<tr><td colspan="4" style="text-align:center;color:var(--adm-dim);padding:20px;">No customers yet</td></tr>';

    // Recent Tickets
    var rt = out.recent_tickets || [];
    $("#overviewRecentTickets").innerHTML = rt.length ? rt.map(function (t) {
      return '<tr><td><b>' + esc(t.subject) + '</b></td>' +
        '<td style="font-size:12px;">' + esc(t.user_name || t.user_email) + '</td>' +
        '<td>' + ticketStatusBadge(t.status) + '</td>' +
        '<td><button class="adm-btn adm-btn-dark adm-btn-sm" onclick="viewTicket(\'' + esc(t.id) + '\')">Reply</button></td></tr>';
    }).join("") : '<tr><td colspan="4" style="text-align:center;color:var(--adm-dim);padding:20px;">No support tickets open 🎉</td></tr>';
  }

  // Quick Action Buttons
  $("#btnQuickLifetime").addEventListener("click", function () {
    populateQuickLifetimeDropdown();
    openModal("modalQuickLifetime");
  });
  $("#btnQuickPlan").addEventListener("click", function () {
    $("#formPlanEdit").reset();
    $("#modalPlanTitle").textContent = "Create New Subscription Plan";
    $("#planId").readOnly = false;
    openModal("modalPlan");
  });
  $("#btnQuickOffer").addEventListener("click", function () {
    $("#formOfferEdit").reset();
    openModal("modalOffer");
  });
  $("#btnQuickEmail").addEventListener("click", function () {
    $$("#adminNav button").find(function (b) { return b.dataset.tab === "email"; }).click();
  });

  // ========================================================== CUSTOMERS
  async function loadUsers() {
    var q = ($("#userSearchInput").value || "").trim();
    var out = await api("/api/admin/users?status=" + encodeURIComponent(activeUserFilter) + "&q=" + encodeURIComponent(q));
    if (!out.success) return;
    currentUsers = out.users || [];
    currentPlans = out.plans || [];
    renderUsersTable();
  }

  function renderUsersTable() {
    var tbody = $("#userTableBody");
    if (!currentUsers.length) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:36px;color:var(--adm-dim);">No customer workspaces match your filter.</td></tr>';
      return;
    }
    tbody.innerHTML = currentUsers.map(function (u) {
      var planBadge = '<span class="adm-pill dim">' + esc(u.plan) + '</span>';
      var lifetimeBtn = u.is_lifetime
        ? '<button class="adm-btn adm-btn-danger adm-btn-sm" title="Revoke Lifetime VIP" onclick="grantLifetimeDirect(\'' + esc(u.id) + '\', false)">Revoke VIP</button>'
        : '<button class="adm-btn adm-btn-gold adm-btn-sm" title="Grant Free Lifetime Access" onclick="grantLifetimeDirect(\'' + esc(u.id) + '\', true)">⭐ Grant Lifetime</button>';

      return '<tr>' +
        '<td><b>' + esc(u.name || "Customer") + '</b>' + (u.role === "admin" ? ' <span class="adm-pill gold">ADMIN</span>' : "") +
        '<div style="font-size:12px;color:var(--adm-dim);">' + esc(u.email) + '</div>' +
        (u.notes ? '<div style="font-size:11px;color:#0284c7;margin-top:2px;">📝 ' + esc(u.notes) + '</div>' : '') + '</td>' +
        '<td>' + (u.ig_username ? '<span style="color:#0284c7;">@' + esc(u.ig_username) + '</span> ' + (u.ig_status === "connected" ? '<span class="adm-pill emerald">Live</span>' : '<span class="adm-pill rose">' + esc(u.ig_status) + '</span>') : '<span style="color:var(--adm-dim);">-</span>') + '</td>' +
        '<td>' + planBadge + '</td>' +
        '<td>' + (u.is_lifetime ? '<span class="adm-pill emerald" style="font-weight:800;">🌟 FREE LIFETIME VIP</span>' : '<span class="adm-pill dim">Standard</span>') + '</td>' +
        '<td style="font-size:12.5px;"><b>' + (u.dms_this_month || 0) + '</b> DMs / <b>' + (u.live_flows || 0) + '</b> flows</td>' +
        '<td>' + (u.status === "active" ? '<span class="adm-pill emerald">Active</span>' : '<span class="adm-pill rose">Suspended</span>') + '</td>' +
        '<td><div style="display:flex;gap:6px;align-items:center;">' +
        lifetimeBtn +
        '<button class="adm-btn adm-btn-dark adm-btn-sm" onclick="openEditCustomerModal(\'' + esc(u.id) + '\')">Edit</button>' +
        '<button class="adm-btn adm-btn-ghost adm-btn-sm" title="Reset DM Limit" onclick="resetUserUsage(\'' + esc(u.id) + '\')">🔄</button>' +
        (u.role !== "admin" ? '<button class="adm-btn adm-btn-ghost adm-btn-sm" style="color:#e11d48;" title="Delete Customer" onclick="deleteUserAccount(\'' + esc(u.id) + '\')">🗑️</button>' : '') +
        '</div></td>' +
        '</tr>';
    }).join("");
  }

  // Filter Buttons
  $$(".filter-user-btn").forEach(function (btn) {
    btn.addEventListener("click", function () {
      $$(".filter-user-btn").forEach(function (b) { b.classList.remove("active"); });
      btn.classList.add("active");
      activeUserFilter = btn.dataset.filter;
      loadUsers();
    });
  });

  // Search input debounce
  var userSearchTimeout;
  $("#userSearchInput").addEventListener("input", function () {
    clearTimeout(userSearchTimeout);
    userSearchTimeout = setTimeout(loadUsers, 280);
  });

  // Direct Lifetime Grant
  window.grantLifetimeDirect = async function (userId, enable) {
    var action = enable ? "grant FREE LIFETIME VIP ACCESS to" : "revoke Lifetime VIP status for";
    var user = currentUsers.find(function (x) { return x.id === userId; });
    var email = user ? user.email : "this customer";
    if (!confirm("Are you sure you want to " + action + " " + email + "?")) return;

    var out = await api("/api/admin/users/" + userId + "/lifetime", {
      method: "POST",
      body: { enable: enable, notify_email: true }
    });
    if (out.success) {
      toast(out.message || "Updated lifetime status");
      loadUsers();
      loadOverview();
    } else {
      toast(out.error || "Failed to update", true);
    }
  };

  // Quick Lifetime Modal
  function populateQuickLifetimeDropdown() {
    var sel = $("#quickLifetimeUserSelect");
    sel.innerHTML = currentUsers.map(function (u) {
      return '<option value="' + esc(u.id) + '">' + esc(u.name || u.email) + ' (' + esc(u.email) + ')' + (u.is_lifetime ? ' [Already Lifetime VIP]' : '') + '</option>';
    }).join("");
  }

  $("#formQuickLifetime").addEventListener("submit", async function (e) {
    e.preventDefault();
    var uid = $("#quickLifetimeUserSelect").value;
    var notify = $("#quickLifetimeNotify").checked;
    if (!uid) return;
    var out = await api("/api/admin/users/" + uid + "/lifetime", {
      method: "POST",
      body: { enable: true, notify_email: notify }
    });
    if (out.success) {
      toast(out.message || "Lifetime VIP granted!");
      closeModal("modalQuickLifetime");
      loadUsers();
      loadOverview();
    } else {
      toast(out.error || "Error granting lifetime", true);
    }
  });

  // Edit Customer Modal
  window.openEditCustomerModal = function (userId) {
    var u = currentUsers.find(function (x) { return x.id === userId; });
    if (!u) return;
    $("#editUserId").value = u.id;
    $("#modalCustomerEmail").textContent = u.email;
    $("#editUserName").value = u.name || "";
    $("#editUserStatus").value = u.status || "active";
    $("#editUserRole").value = u.role || "customer";
    $("#editUserLifetime").checked = !!u.is_lifetime;
    $("#editUserNotes").value = u.notes || "";

    var planSel = $("#editUserPlan");
    planSel.innerHTML = currentPlans.map(function (p) {
      return '<option value="' + esc(p.id) + '"' + (p.id === u.plan ? ' selected' : '') + '>' + esc(p.name) + '</option>';
    }).join("");

    openModal("modalCustomer");
  };

  $("#formEditCustomer").addEventListener("submit", async function (e) {
    e.preventDefault();
    var uid = $("#editUserId").value;
    var payload = {
      name: $("#editUserName").value,
      plan: $("#editUserPlan").value,
      status: $("#editUserStatus").value,
      role: $("#editUserRole").value,
      is_lifetime: $("#editUserLifetime").checked,
      notes: $("#editUserNotes").value
    };
    var out = await api("/api/admin/users/" + uid, { method: "POST", body: payload });
    if (out.success) {
      toast("Customer updated");
      closeModal("modalCustomer");
      loadUsers();
    } else {
      toast(out.error || "Could not update", true);
    }
  });

  window.resetUserUsage = async function (userId) {
    if (!confirm("Reset this customer's DM usage for the current cycle?")) return;
    var out = await api("/api/admin/users/" + userId + "/reset-usage", { method: "POST" });
    if (out.success) {
      toast("DM usage reset");
      loadUsers();
    } else {
      toast("Failed to reset usage", true);
    }
  };

  window.deleteUserAccount = async function (userId) {
    var user = currentUsers.find(function (x) { return x.id === userId; });
    var email = user ? user.email : "this account";
    if (!confirm("⚠️ PERMANENT DELETE: Are you sure you want to completely remove " + email + " and delete all their flows, contacts, and tickets?")) return;
    var out = await api("/api/admin/users/" + userId, { method: "DELETE" });
    if (out.success) {
      toast(out.message || "Account deleted");
      loadUsers();
      loadOverview();
    } else {
      toast(out.error || "Could not delete account", true);
    }
  };

  // ========================================================== PLANS
  async function loadPlans() {
    var out = await api("/api/admin/plans");
    if (!out.success) return;
    currentPlans = out.plans || [];
    renderPlansGrid();
  }

  function renderPlansGrid() {
    var container = $("#plansContainer");
    container.innerHTML = currentPlans.map(function (p, idx) {
      var isLt = p.id === "lifetime" || p.price_monthly === 0 && p.badge.toLowerCase().includes("lifetime");
      var popular = p.highlight ? " is-popular" : "";
      var lifetimeClass = isLt ? " is-lifetime" : "";

      return '<div class="plan-box' + popular + lifetimeClass + '">' +
        '<div>' +
        '<div style="display:flex;justify-content:space-between;align-items:flex-start;">' +
        '<h3 style="margin:0;color:var(--adm-text);">' + esc(p.name) + '</h3>' +
        (p.badge ? '<span class="adm-pill ' + (isLt ? 'gold' : 'emerald') + '">' + esc(p.badge) + '</span>' : '') +
        '</div>' +
        '<p style="color:var(--adm-muted);font-size:12.5px;margin:4px 0 0;">' + esc(p.tagline || "") + '</p>' +
        '<div class="plan-price">' + (p.price_monthly === 0 ? "Free" : "₹" + p.price_monthly) + '<span style="font-size:14px;color:var(--adm-dim);font-weight:400;"> /mo</span></div>' +
        '<div style="font-size:12px;color:var(--adm-dim);">Yearly: ' + (p.price_yearly === 0 ? "Free" : "₹" + p.price_yearly + "/yr") + ' &middot; ' + (p.trial_days ? p.trial_days + " days trial" : "No trial") + '</div>' +
        '<ul class="plan-limits">' +
        '<li>⚡ <b>' + (p.limits.automations === -1 ? "Unlimited" : p.limits.automations) + '</b> active automations</li>' +
        '<li>💬 <b>' + (p.limits.dms_per_month === -1 ? "Unlimited" : p.limits.dms_per_month.toLocaleString()) + '</b> DMs / month</li>' +
        '<li>👥 <b>' + (p.limits.contacts === -1 ? "Unlimited" : p.limits.contacts.toLocaleString()) + '</b> contacts limit</li>' +
        '<li>📱 <b>' + (p.limits.ig_accounts === -1 ? "Unlimited" : p.limits.ig_accounts) + '</b> Instagram connection</li>' +
        '</ul>' +
        '</div>' +
        '<div style="display:flex;gap:8px;margin-top:16px;">' +
        '<button class="adm-btn adm-btn-dark adm-btn-sm" style="flex:1;" onclick="editPlanIndex(' + idx + ')">Edit Plan</button>' +
        (currentPlans.length > 1 ? '<button class="adm-btn adm-btn-danger adm-btn-sm" onclick="deletePlanId(\'' + esc(p.id) + '\')">Delete</button>' : '') +
        '</div>' +
        '</div>';
    }).join("");
  }

  window.editPlanIndex = function (idx) {
    var p = currentPlans[idx];
    if (!p) return;
    $("#modalPlanTitle").textContent = "Edit Plan: " + p.name;
    $("#planEditIndex").value = idx;
    $("#planId").value = p.id;
    $("#planId").readOnly = true;
    $("#planName").value = p.name;
    $("#planTagline").value = p.tagline || "";
    $("#planPriceM").value = p.price_monthly || 0;
    $("#planPriceY").value = p.price_yearly || 0;
    $("#planTrial").value = p.trial_days || 0;
    $("#planBadge").value = p.badge || "";

    $("#planLimitAuto").value = p.limits ? p.limits.automations : 1;
    $("#planLimitContacts").value = p.limits ? p.limits.contacts : 500;
    $("#planLimitDMs").value = p.limits ? p.limits.dms_per_month : 1000;

    var feat = p.features || {};
    $("#planFeatComment").checked = !!feat.comment_to_dm;
    $("#planFeatFollow").checked = !!feat.follow_gate;
    $("#planFeatAnyPost").checked = !!feat.any_post;
    $("#planFeatPriority").checked = !!feat.priority_support;
    $("#planFeatAI").checked = !!feat.ai_assist;
    $("#planFeatCSV").checked = !!feat.csv_export;

    openModal("modalPlan");
  };

  $("#formPlanEdit").addEventListener("submit", async function (e) {
    e.preventDefault();
    var idx = $("#planEditIndex").value;
    var planObj = {
      id: $("#planId").value.trim().toLowerCase().replace(/[^a-z0-9_-]/g, ""),
      name: $("#planName").value.trim(),
      tagline: $("#planTagline").value.trim(),
      price_monthly: parseFloat($("#planPriceM").value) || 0,
      price_yearly: parseFloat($("#planPriceY").value) || 0,
      trial_days: parseInt($("#planTrial").value) || 0,
      badge: $("#planBadge").value.trim(),
      highlight: $("#planBadge").value.toLowerCase().includes("popular"),
      is_active: true,
      limits: {
        automations: parseInt($("#planLimitAuto").value) || 1,
        contacts: parseInt($("#planLimitContacts").value) || 500,
        dms_per_month: parseInt($("#planLimitDMs").value) || 1000,
        ig_accounts: 1
      },
      features: {
        comment_to_dm: $("#planFeatComment").checked,
        follow_gate: $("#planFeatFollow").checked,
        any_post: $("#planFeatAnyPost").checked,
        priority_support: $("#planFeatPriority").checked,
        ai_assist: $("#planFeatAI").checked,
        csv_export: $("#planFeatCSV").checked
      }
    };

    var updatedPlans = currentPlans.slice();
    if (idx !== "" && !isNaN(parseInt(idx))) {
      updatedPlans[parseInt(idx)] = planObj;
    } else {
      updatedPlans.push(planObj);
    }

    var out = await api("/api/admin/plans", { method: "POST", body: { plans: updatedPlans } });
    if (out.success) {
      toast("Plan catalogue updated");
      closeModal("modalPlan");
      currentPlans = out.plans;
      renderPlansGrid();
    } else {
      toast(out.error || "Failed to save plan", true);
    }
  });

  window.deletePlanId = async function (planId) {
    if (!confirm("Delete plan '" + planId + "'?")) return;
    var out = await api("/api/admin/plans/" + planId, { method: "DELETE" });
    if (out.success) {
      toast("Plan deleted");
      loadPlans();
    } else {
      toast(out.error || "Cannot delete plan", true);
    }
  };

  $("#btnResetPlans").addEventListener("click", async function () {
    if (!confirm("Reset plans to system defaults (Free, Starter, Growth, Lifetime VIP)?")) return;
    var out = await api("/api/admin/plans/reset", { method: "POST" });
    if (out.success) {
      toast("Plans reset to defaults");
      loadPlans();
    }
  });

  // ========================================================== TICKETS
  function ticketStatusBadge(status) {
    if (status === "open") return '<span class="adm-pill rose">Open</span>';
    if (status === "in_progress") return '<span class="adm-pill gold">In Progress</span>';
    if (status === "resolved") return '<span class="adm-pill emerald">Resolved</span>';
    return '<span class="adm-pill dim">' + esc(status) + '</span>';
  }

  async function loadTickets() {
    var out = await api("/api/admin/tickets?status=" + encodeURIComponent(activeTicketFilter));
    if (!out.success) return;
    currentTickets = out.tickets || [];
    renderTicketsTable();
  }

  function renderTicketsTable() {
    var tbody = $("#ticketsTableBody");
    if (!currentTickets.length) {
      tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;padding:36px;color:var(--adm-dim);">No customer support tickets found.</td></tr>';
      return;
    }
    tbody.innerHTML = currentTickets.map(function (t) {
      return '<tr>' +
        '<td><code style="color:#0284c7;">#' + esc(t.id) + '</code></td>' +
        '<td><b>' + esc(t.user_name || "Customer") + '</b><div style="font-size:11.5px;color:var(--adm-dim);">' + esc(t.user_email) + '</div></td>' +
        '<td><b>' + esc(t.subject) + '</b></td>' +
        '<td><span class="adm-pill dim">' + esc(t.category) + '</span></td>' +
        '<td><span class="adm-pill ' + (t.priority === 'urgent' ? 'rose' : t.priority === 'high' ? 'gold' : 'dim') + '">' + esc(t.priority) + '</span></td>' +
        '<td>' + ticketStatusBadge(t.status) + '</td>' +
        '<td style="font-size:12px;color:var(--adm-muted);">' + ago(t.updated_at) + '</td>' +
        '<td><div style="display:flex;gap:6px;">' +
        '<button class="adm-btn adm-btn-emerald adm-btn-sm" onclick="viewTicket(\'' + esc(t.id) + '\')">Open Thread</button>' +
        '<button class="adm-btn adm-btn-ghost adm-btn-sm" style="color:#e11d48;" onclick="deleteTicket(\'' + esc(t.id) + '\')">🗑️</button>' +
        '</div></td>' +
        '</tr>';
    }).join("");
  }

  $$(".filter-ticket-btn").forEach(function (btn) {
    btn.addEventListener("click", function () {
      $$(".filter-ticket-btn").forEach(function (b) { b.classList.remove("active"); });
      btn.classList.add("active");
      activeTicketFilter = btn.dataset.filter;
      loadTickets();
    });
  });

  window.viewTicket = async function (ticketId) {
    var out = await api("/api/admin/tickets/" + ticketId);
    if (!out.success) {
      toast("Could not load ticket", true);
      return;
    }
    var t = out.ticket, msgs = out.messages || [], u = out.user || {};
    $("#replyTicketId").value = t.id;
    $("#ticketModalSubject").textContent = "#" + t.id + ": " + t.subject;
    $("#ticketModalMeta").textContent = "Submitted by " + (t.user_name || t.user_email) + " (" + t.user_email + ") &middot; Plan: " + (u.plan || "free") + (u.is_lifetime ? " [VIP]" : "");
    $("#ticketModalStatusPill").className = "adm-pill " + (t.status === "resolved" ? "emerald" : t.status === "open" ? "rose" : "gold");
    $("#ticketModalStatusPill").textContent = t.status.toUpperCase();
    $("#ticketReplyStatus").value = t.status === "open" ? "in_progress" : t.status;
    $("#ticketReplyText").value = "";

    var chat = $("#ticketChatContainer");
    chat.innerHTML = msgs.map(function (m) {
      var isAdm = m.sender_role === "admin";
      return '<div class="chat-msg ' + (isAdm ? 'admin' : 'customer') + '">' +
        '<div class="meta"><b>' + esc(m.sender_name || (isAdm ? "DM Flow Support" : "Customer")) + '</b><span>' + ago(m.created_at) + '</span></div>' +
        esc(m.message).replace(/\n/g, "<br>") +
        '</div>';
    }).join("");
    chat.scrollTop = chat.scrollHeight;

    openModal("modalTicket");
  };

  $("#formTicketReply").addEventListener("submit", async function (e) {
    e.preventDefault();
    var tid = $("#replyTicketId").value;
    var msg = $("#ticketReplyText").value.trim();
    var status = $("#ticketReplyStatus").value;
    var sendMail = $("#ticketReplyEmailCheck").checked;
    if (!msg) return;

    var out = await api("/api/admin/tickets/" + tid + "/reply", {
      method: "POST",
      body: { message: msg, status: status, send_email: sendMail }
    });
    if (out.success) {
      toast("Response posted!");
      closeModal("modalTicket");
      loadTickets();
      loadOverview();
    } else {
      toast(out.error || "Could not post reply", true);
    }
  });

  window.deleteTicket = async function (ticketId) {
    if (!confirm("Delete ticket #" + ticketId + "?")) return;
    var out = await api("/api/admin/tickets/" + ticketId, { method: "DELETE" });
    if (out.success) {
      toast("Ticket deleted");
      loadTickets();
      loadOverview();
    }
  };

  // ========================================================== OFFERS
  async function loadOffers() {
    var out = await api("/api/admin/offers");
    if (!out.success) return;
    var tbody = $("#offersTableBody");
    var list = out.offers || [];
    if (!list.length) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:36px;color:var(--adm-dim);">No active promo offers or coupons created yet.</td></tr>';
      return;
    }
    tbody.innerHTML = list.map(function (o) {
      var discountStr = o.discount_type === "percentage" ? o.discount_val + "% OFF" : o.discount_type === "flat" ? "₹" + o.discount_val + " OFF" : "🌟 100% Free Lifetime Deal";
      return '<tr>' +
        '<td><b style="color:#d97706;font-family:monospace;font-size:14px;">' + esc(o.code) + '</b></td>' +
        '<td>' + esc(o.title || "-") + '</td>' +
        '<td><span class="adm-pill ' + (o.discount_type === 'lifetime' ? 'gold' : 'emerald') + '">' + discountStr + '</span></td>' +
        '<td><span class="adm-pill dim">' + esc(o.applicable_plans) + '</span></td>' +
        '<td>' + (o.max_uses === -1 ? o.used_count + ' uses' : o.used_count + ' / ' + o.max_uses) + '</td>' +
        '<td><button class="adm-btn adm-btn-sm ' + (o.is_active ? 'adm-btn-emerald' : 'adm-btn-dark') + '" onclick="toggleOffer(\'' + esc(o.id) + '\')">' + (o.is_active ? 'Active' : 'Paused') + '</button></td>' +
        '<td><button class="adm-btn adm-btn-ghost adm-btn-sm" style="color:#e11d48;" onclick="deleteOffer(\'' + esc(o.id) + '\')">🗑️</button></td>' +
        '</tr>';
    }).join("");
  }

  $("#btnCreateOffer").addEventListener("click", function () {
    $("#formOfferEdit").reset();
    openModal("modalOffer");
  });

  $("#formOfferEdit").addEventListener("submit", async function (e) {
    e.preventDefault();
    var payload = {
      code: $("#offerCode").value.trim().toUpperCase(),
      title: $("#offerTitle").value.trim(),
      discount_type: $("#offerType").value,
      discount_val: parseFloat($("#offerVal").value) || 0,
      applicable_plans: $("#offerPlans").value.trim() || "all",
      max_uses: parseInt($("#offerMaxUses").value) || -1,
      is_active: true
    };
    var out = await api("/api/admin/offers", { method: "POST", body: payload });
    if (out.success) {
      toast("Coupon code created");
      closeModal("modalOffer");
      loadOffers();
    } else {
      toast(out.error || "Failed to save coupon", true);
    }
  });

  window.toggleOffer = async function (offerId) {
    var out = await api("/api/admin/offers/" + offerId + "/toggle", { method: "POST" });
    if (out.success) {
      toast(out.is_active ? "Offer activated" : "Offer paused");
      loadOffers();
    }
  };

  window.deleteOffer = async function (offerId) {
    if (!confirm("Delete this coupon code?")) return;
    var out = await api("/api/admin/offers/" + offerId, { method: "DELETE" });
    if (out.success) {
      toast("Coupon deleted");
      loadOffers();
    }
  };

  // ========================================================== BILLING
  async function loadBilling() {
    var out = await api("/api/admin/billing/settings");
    if (!out.success) return;
    var b = out.billing || {};
    var f = $("#billingForm");
    Object.keys(b).forEach(function (k) {
      if (f.elements[k]) f.elements[k].value = b[k];
    });
    $("#razorpay_enabled_check").checked = b.razorpay_enabled === "1";
    $("#stripe_enabled_check").checked = b.stripe_enabled === "1";
  }

  $("#billingForm").addEventListener("submit", async function (e) {
    e.preventDefault();
    var data = {};
    Array.from(this.elements).forEach(function (el) {
      if (el.name) data[el.name] = el.value;
    });
    data.razorpay_enabled = $("#razorpay_enabled_check").checked ? "1" : "0";
    data.stripe_enabled = $("#stripe_enabled_check").checked ? "1" : "0";

    var out = await api("/api/admin/billing/settings", { method: "POST", body: data });
    toast(out.message || (out.success ? "Billing settings saved" : "Error saving billing"), !out.success);
    loadBilling();
  });

  // ========================================================== EMAIL & SMTP
  async function loadEmail() {
    var out = await api("/api/admin/email/settings");
    if (!out.success) return;
    var em = out.email_settings || {};
    var f = $("#emailForm");
    Object.keys(em).forEach(function (k) {
      if (f.elements[k]) f.elements[k].value = em[k];
    });
    $("#smtp_enabled_check").checked = em.smtp_enabled === "1";
    $("#email_welcome_check").checked = em.email_welcome_enabled === "1";
    $("#email_ticket_check").checked = em.email_ticket_enabled === "1";
    $("#email_lifetime_check").checked = em.email_lifetime_enabled === "1";
  }

  $("#emailForm").addEventListener("submit", async function (e) {
    e.preventDefault();
    var data = {};
    Array.from(this.elements).forEach(function (el) {
      if (el.name) data[el.name] = el.value;
    });
    data.smtp_enabled = $("#smtp_enabled_check").checked ? "1" : "0";
    data.email_welcome_enabled = $("#email_welcome_check").checked ? "1" : "0";
    data.email_ticket_enabled = $("#email_ticket_check").checked ? "1" : "0";
    data.email_lifetime_enabled = $("#email_lifetime_check").checked ? "1" : "0";

    var out = await api("/api/admin/email/settings", { method: "POST", body: data });
    toast(out.message || (out.success ? "Email settings saved" : "Error saving email settings"), !out.success);
    loadEmail();
  });

  $("#btnSendTestEmail").addEventListener("click", async function () {
    var to = ($("#testEmailTarget").value || "").trim();
    if (!to || !to.includes("@")) {
      toast("Enter a valid recipient email", true);
      return;
    }
    var resDiv = $("#testEmailResult");
    resDiv.style.display = "block";
    resDiv.innerHTML = '<span style="color:#d97706;">Connecting to SMTP server and sending test email...</span>';
    var out = await api("/api/admin/email/test", { method: "POST", body: { to: to } });
    if (out.success) {
      resDiv.innerHTML = '<span style="color:#059669;">✅ ' + esc(out.message) + '</span>';
      toast("Test email sent!");
    } else {
      resDiv.innerHTML = '<span style="color:#e11d48;">❌ ' + esc(out.error || "Failed to send") + '</span>';
      toast("Failed to send test email", true);
    }
  });

  // ========================================================== META & INSTAGRAM
  async function loadMeta() {
    var out = await api("/api/admin/settings");
    if (!out.success) return;
    var f = $("#metaForm");
    Object.keys(out.settings).forEach(function (k) {
      var s = out.settings[k], el = f.elements[k];
      if (!el) return;
      el.value = s.value;
      el.disabled = s.source === "env";
    });

    var u = out.urls, rows = [
      ["OAuth Redirect URI", u.redirect_uri],
      ["Webhook Callback URL", u.webhook],
      ["Verify Token", out.settings.verify_token.value],
      ["Deauthorize Callback", u.deauthorize],
      ["Data Deletion URL", u.data_deletion]
    ];
    $("#metaUrls").innerHTML = rows.map(function (r) {
      return '<div class="copy-box"><span class="title">' + esc(r[0]) + '</span><code>' + esc(r[1]) + '</code><button class="adm-btn adm-btn-dark adm-btn-sm" data-copy="' + esc(r[1]) + '">Copy</button></div>';
    }).join("");

    var eventsOut = await api("/api/admin/events");
    var events = eventsOut.events || [];
    $("#metaEventsList").innerHTML = events.length ? events.map(function (e) {
      return '<div style="padding:8px 0;border-bottom:1px solid var(--adm-line);font-size:12.5px;">' +
        '<div style="display:flex;justify-content:space-between;color:var(--adm-dim);font-size:11px;">' +
        '<span>' + esc(e.kind) + (e.username ? ' &middot; @' + esc(e.username) : '') + '</span>' +
        '<span>' + ago(e.at) + '</span>' +
        '</div>' +
        '<div style="color:var(--adm-text);margin:2px 0;">' + esc(e.text || e.note || e.verdict) + '</div>' +
        '</div>';
    }).join("") : '<div style="color:var(--adm-dim);padding:14px;text-align:center;">No platform activity logged yet.</div>';
    // Simulate Comment Button
    var btnSim = $("#btnSimulateComment");
    if (btnSim && !btnSim._bound) {
      btnSim._bound = true;
      btnSim.addEventListener("click", async function () {
        var text = ($("#simCommentText").value || "").trim();
        var user = ($("#simCommentUser").value || "").trim();
        var resDiv = $("#simCommentResult");
        resDiv.style.display = "block";
        resDiv.innerHTML = '<span style="color:#d97706;">Running simulation through keyword matcher and Meta Graph API...</span>';

        var out = await api("/api/system/simulate-comment", {
          method: "POST",
          body: { text: text, username: user }
        });

        if (out.success) {
          var ev = out.event || {};
          var vColor = out.verdict === "sent" ? "#059669" : out.verdict === "ignored" ? "#d97706" : "#e11d48";
          resDiv.innerHTML = '<div><b>Verdict:</b> <span style="color:' + vColor + ';font-weight:700;">' + esc(out.verdict.toUpperCase()) + '</span></div>' +
                             '<div style="margin-top:4px;color:var(--adm-text);"><b>Details:</b> ' + esc(ev.note || "Processed") + '</div>' +
                             '<div style="margin-top:4px;color:var(--adm-dim);font-size:11px;">Comment ID: ' + esc(out.comment_id) + '</div>';
          toast(out.verdict === "sent" ? "Simulation DM Sent!" : "Simulation completed: " + out.verdict, out.verdict !== "sent");
          loadMeta();
        } else {
          resDiv.innerHTML = '<span style="color:#e11d48;">❌ ' + esc(out.error || "Simulation failed") + '</span>';
          toast(out.error || "Simulation failed", true);
        }
      });
    }

    var btnRef = $("#btnRefreshMetaEvents");
    if (btnRef && !btnRef._bound) {
      btnRef._bound = true;
      btnRef.addEventListener("click", function () {
        loadMeta();
        toast("Refreshed activity logs");
      });
    }
  }

  $("#metaForm").addEventListener("submit", async function (e) {
    e.preventDefault();
    var data = {};
    Array.from(this.elements).forEach(function (el) {
      if (el.name && !el.disabled) data[el.name] = el.value;
    });
    var out = await api("/api/admin/settings", { method: "POST", body: data });
    toast(out.success ? "Meta credentials updated" : "Could not save credentials", !out.success);
    loadMeta();
  });

  // Copy click
  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-copy]");
    if (!b) return;
    navigator.clipboard.writeText(b.dataset.copy).then(function () {
      toast("Copied to clipboard!");
    });
  });

  // ========================================================== PLATFORM
  async function loadPlatform() {
    var out = await api("/api/admin/platform/settings");
    if (!out.success) return;
    var p = out.platform || {};
    var f = $("#platformForm");
    Object.keys(p).forEach(function (k) {
      if (f.elements[k]) f.elements[k].value = p[k];
    });
    $("#signups_open_check").checked = p.signups_open !== "0";
    $("#maintenance_mode_check").checked = p.maintenance_mode === "1";
  }

  $("#platformForm").addEventListener("submit", async function (e) {
    e.preventDefault();
    var data = {};
    Array.from(this.elements).forEach(function (el) {
      if (el.name) data[el.name] = el.value;
    });
    data.signups_open = $("#signups_open_check").checked ? "1" : "0";
    data.maintenance_mode = $("#maintenance_mode_check").checked ? "1" : "0";

    var out = await api("/api/admin/platform/settings", { method: "POST", body: data });
    toast(out.message || (out.success ? "Platform settings saved" : "Error saving settings"), !out.success);
    loadPlatform();
  });

  // Initialize
  async function init() {
    var meOut = await api("/api/me");
    if (meOut.success && meOut.user) {
      $("#ownerEmail").textContent = meOut.user.email;
    }
    loadOverview();
  }

  init();
})();
