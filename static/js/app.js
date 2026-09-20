// ConverFlow for Instagram — Full Automation Suite Controller

document.addEventListener("DOMContentLoaded", () => {
  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // Navigation
  const navItems = document.querySelectorAll(".nav-item");
  const contentViews = document.querySelectorAll(".content-view");
  const viewTitle = document.getElementById("viewTitle");
  const viewSubtitle = document.getElementById("viewSubtitle");
  const navAutomationsCount = document.getElementById("navAutomationsCount");
  const navContactsCount = document.getElementById("navContactsCount");

  // Account State
  const accountHandle = document.getElementById("accountHandle");
  const accountBadge = document.getElementById("accountBadge");
  const btnSidebarLogin = document.getElementById("btnSidebarLogin");
  const btnSettingsLogin = document.getElementById("btnSettingsLogin");
  const btnSettingsRefresh = document.getElementById("btnSettingsRefresh");
  const settingsStatusText = document.getElementById("settingsStatusText");

  // Watcher Controls
  const watcherDot = document.getElementById("watcherDot");
  const watcherText = document.getElementById("watcherText");
  const btnToggleWatcher = document.getElementById("btnToggleWatcher");
  const watcherPostUrl = document.getElementById("watcherPostUrl");
  const watcherInterval = document.getElementById("watcherInterval");

  // Automations View
  const automationsGrid = document.getElementById("automationsGrid");
  const filterTabs = document.querySelectorAll(".filter-tab");
  const activeRulesCount = document.getElementById("activeRulesCount");
  const btnNewAutomation = document.getElementById("btnNewAutomation");

  // Automation Modal
  const automationModal = document.getElementById("automationModal");
  const btnCloseAutomationModal = document.getElementById("btnCloseAutomationModal");
  const btnCancelAutomation = document.getElementById("btnCancelAutomation");
  const btnSaveAutomation = document.getElementById("btnSaveAutomation");
  const modalAutomationTitle = document.getElementById("modalAutomationTitle");
  const editRuleId = document.getElementById("editRuleId");
  const ruleName = document.getElementById("ruleName");
  const ruleType = document.getElementById("ruleType");
  const ruleKeywords = document.getElementById("ruleKeywords");
  const rulePostTarget = document.getElementById("rulePostTarget");
  const rulePublicReply = document.getElementById("rulePublicReply");
  const ruleDmMessage = document.getElementById("ruleDmMessage");
  const ruleTags = document.getElementById("ruleTags");
  const modalVarChips = document.querySelectorAll(".modal-var-chip");

  // Simulator View
  const simSegmentBtns = document.querySelectorAll(".segment-btn");
  const simUsernameInput = document.getElementById("simUsername");
  const simChips = document.querySelectorAll(".sim-chip");
  const phoneChatBody = document.getElementById("phoneChatBody");
  const phoneInputText = document.getElementById("phoneInputText");
  const btnPhoneSend = document.getElementById("btnPhoneSend");
  const btnClearSimChat = document.getElementById("btnClearSimChat");

  // Broadcast / Outreach View Elements
  const statTotalTargets = document.getElementById("statTotalTargets");
  const statSent = document.getElementById("statSent");
  const statPending = document.getElementById("statPending");
  const statQuota = document.getElementById("statQuota");
  const statQuotaFill = document.getElementById("statQuotaFill");
  const statCampaignState = document.getElementById("statCampaignState");
  const messageTemplate = document.getElementById("messageTemplate");
  const btnPreviewSpintax = document.getElementById("btnPreviewSpintax");
  const varChips = document.querySelectorAll(".var-chip");
  const minDelayInput = document.getElementById("minDelay");
  const maxDelayInput = document.getElementById("maxDelay");
  const dailyLimitInput = document.getElementById("dailyLimit");
  const headlessModeInput = document.getElementById("headlessMode");
  const tabButtons = document.querySelectorAll(".tab-btn");
  const tabPanes = document.querySelectorAll(".tab-pane");
  const manualTargetsInput = document.getElementById("manualTargetsInput");
  const btnLoadManualTargets = document.getElementById("btnLoadManualTargets");
  const csvDropZone = document.getElementById("csvDropZone");
  const csvFileInput = document.getElementById("csvFileInput");
  const targetsTableBody = document.getElementById("targetsTableBody");
  const btnClearTargets = document.getElementById("btnClearTargets");
  const btnExportCsv = document.getElementById("btnExportCsv");
  const terminalLogs = document.getElementById("terminalLogs");
  const btnClearLogs = document.getElementById("btnClearLogs");
  const deckStatusOrb = document.getElementById("deckStatusOrb");
  const deckStatusTitle = document.getElementById("deckStatusTitle");
  const deckStatusSub = document.getElementById("deckStatusSub");
  const btnStartCampaign = document.getElementById("btnStartCampaign");
  const btnPauseCampaign = document.getElementById("btnPauseCampaign");
  const btnResumeCampaign = document.getElementById("btnResumeCampaign");
  const btnStopCampaign = document.getElementById("btnStopCampaign");

  // Spintax Modal
  const spintaxModal = document.getElementById("spintaxModal");
  const btnCloseSpintaxModal = document.getElementById("btnCloseSpintaxModal");
  const btnAcceptSpintax = document.getElementById("btnAcceptSpintax");
  const btnReRollSpintax = document.getElementById("btnReRollSpintax");
  const spintaxPreviewList = document.getElementById("spintaxPreviewList");

  // Contacts CRM View
  const contactsTableBody = document.getElementById("contactsTableBody");
  const contactsSearch = document.getElementById("contactsSearch");
  const btnExportContacts = document.getElementById("btnExportContacts");

  // State Cache
  let allAutomations = [];
  let currentFilter = "all";
  let activeSimChannel = "comment";
  let watcherRunning = false;

  const viewHeaders = {
    "view-home": { title: "Home", sub: "Start here and explore popular Instagram automations." },
    "view-contacts": { title: "Contacts & CRM", sub: "Captured subscribers and leads who interacted with your Instagram." },
    "view-automations": { title: "Automations", sub: "Create Comment-to-DM flows, story mention replies, and keyword auto-responders." },
    "view-ai": { title: "AI Assist & Flow Generator", sub: "Generate high-converting comment triggers, spintax DM copy, and viral reel hooks in seconds using AI." },
    "view-inbox": { title: "Instagram DM Inbox", sub: "Manage live 1-on-1 Instagram conversations, comment triggers, and human agent takeover." },
    "view-simulator": { title: "Flow Simulator", sub: "Interactive mobile phone tester to experience your chatbot live." },
    "view-broadcast": { title: "Outreach & Broadcast", sub: "Cold lead messaging campaign runner with anti-ban safety limits." },
    "view-settings": { title: "Account & Settings", sub: "Manage Meta Developer API, browser login, session security, and watcher settings." }
  };

  // --- Initialize ---
  // Each section is isolated: a missing element in one panel must never stop
  // the rest of the dashboard from wiring itself up.
  function safely(label, fn) {
    try {
      fn();
    } catch (err) {
      console.warn("[ConverFlow] " + label + " skipped:", err && err.message);
    }
  }

  async function init() {
    safely("navigation", setupNavigation);
    safely("simulator", setupSimulator);
    safely("automations", setupAutomationsUI);
    safely("broadcast", setupBroadcastUI);
    safely("contacts", setupContactsUI);
    safely("ai assist", setupAiAssistUI);
    safely("inbox", setupInboxUI);
    safely("modals", setupModalsUI);
    safely("log stream", setupSSEStream);

    for (const [label, loader] of [
      ["account status", refreshAccountStatus],
      ["automations", loadAutomations],
      ["contacts", loadContacts],
      ["campaign status", refreshCampaignStatus]
    ]) {
      try {
        await loader();
      } catch (err) {
        console.warn("[ConverFlow] could not load " + label + ":", err && err.message);
      }
    }
    await refreshTargetsTable();

    setInterval(async () => {
      await refreshCampaignStatus();
      if (document.getElementById("view-broadcast") && document.getElementById("view-broadcast").classList.contains("active")) {
        await refreshTargetsTable();
      }
    }, 3000);
  }

  // --- Sidebar & Mobile Navigation ---
  function setupNavigation() {
    navItems.forEach(item => {
      item.addEventListener("click", (e) => {
        e.preventDefault();
        const targetViewId = item.getAttribute("data-view");
        switchView(targetViewId);
      });
    });

    const mobileNavItems = document.querySelectorAll(".mobile-nav-item");
    mobileNavItems.forEach(m => {
      m.addEventListener("click", (e) => {
        e.preventDefault();
        const targetViewId = m.getAttribute("data-view");
        switchView(targetViewId);
      });
    });

    // Home view cards & CTA listeners
    const cardHomeAutoDm = document.getElementById("cardHomeAutoDm");
    if (cardHomeAutoDm) {
      cardHomeAutoDm.addEventListener("click", () => openEasyBuilderWizard());
    }
    const cardHomeStories = document.getElementById("cardHomeStories");
    if (cardHomeStories) {
      cardHomeStories.addEventListener("click", () => switchView("view-automations"));
    }
    const cardHomeAllDms = document.getElementById("cardHomeAllDms");
    if (cardHomeAllDms) {
      cardHomeAllDms.addEventListener("click", () => switchView("view-automations"));
    }

    // Top ribbon controls
    const btnRibbonTrial = document.getElementById("btnRibbonTrial");
    if (btnRibbonTrial) btnRibbonTrial.addEventListener("click", () => openUpgradeModal());

    const linkRibbonPricing = document.getElementById("linkRibbonPricing");
    if (linkRibbonPricing) linkRibbonPricing.addEventListener("click", (e) => {
      e.preventDefault();
      openUpgradeModal();
    });

    const btnRibbonClose = document.getElementById("btnRibbonClose");
    if (btnRibbonClose) {
      btnRibbonClose.addEventListener("click", () => {
        const ribbon = document.getElementById("topUpgradeRibbon");
        if (ribbon) ribbon.style.display = "none";
      });
    }

    const btnPromoClose = document.getElementById("btnPromoClose");
    if (btnPromoClose) {
      btnPromoClose.addEventListener("click", () => {
        const promo = document.getElementById("promoBanner");
        if (promo) promo.style.display = "none";
      });
    }

    const btnPromoDiscover = document.getElementById("btnPromoDiscover");
    if (btnPromoDiscover) {
      btnPromoDiscover.addEventListener("click", () => switchView("view-settings"));
    }

    const btnSidebarUpgradeTrial = document.getElementById("btnSidebarUpgradeTrial");
    if (btnSidebarUpgradeTrial) {
      btnSidebarUpgradeTrial.addEventListener("click", () => openUpgradeModal());
    }

    const exploreTemplatesLinks = document.querySelectorAll(".link-explore-templates");
    exploreTemplatesLinks.forEach(link => {
      link.addEventListener("click", (e) => {
        e.preventDefault();
        switchView("view-automations");
      });
    });

    const seeInsightsLinks = document.querySelectorAll(".link-see-insights");
    seeInsightsLinks.forEach(link => {
      link.addEventListener("click", (e) => {
        e.preventDefault();
        switchView("view-settings");
      });
    });

    const moveAffiliateLinks = document.getElementById("moveAffiliateLinks");
    if (moveAffiliateLinks) moveAffiliateLinks.addEventListener("click", () => openEasyBuilderWizard());

    const moveGrowFollowers = document.getElementById("moveGrowFollowers");
    if (moveGrowFollowers) moveGrowFollowers.addEventListener("click", () => openEasyBuilderWizard());

    const moveDefaultReply = document.getElementById("moveDefaultReply");
    if (moveDefaultReply) moveDefaultReply.addEventListener("click", () => switchView("view-automations"));

    const btnMobileUpgrade = document.getElementById("btnMobileUpgrade");
    if (btnMobileUpgrade) {
      btnMobileUpgrade.addEventListener("click", () => openUpgradeModal());
    }

    // Sidebar footer links: Profile and Help
    const linkUserProfile = document.getElementById("linkUserProfile");
    if (linkUserProfile) {
      linkUserProfile.addEventListener("click", (e) => {
        e.preventDefault();
        openProfileModal();
      });
    }

    const linkHelp = document.getElementById("linkHelp");
    if (linkHelp) {
      linkHelp.addEventListener("click", (e) => {
        e.preventDefault();
        openHelpModal();
      });
    }

    if (btnSidebarLogin) btnSidebarLogin.addEventListener("click", triggerOpenLogin);
    if (btnSettingsLogin) btnSettingsLogin.addEventListener("click", triggerOpenLogin);
    if (btnSettingsRefresh) btnSettingsRefresh.addEventListener("click", refreshAccountStatus);

    if (btnToggleWatcher) btnToggleWatcher.addEventListener("click", toggleWatcher);
  }

  function switchView(viewId) {
    navItems.forEach(n => n.classList.toggle("active", n.getAttribute("data-view") === viewId));
    const mobileNavItems = document.querySelectorAll(".mobile-nav-item");
    mobileNavItems.forEach(m => m.classList.toggle("active", m.getAttribute("data-view") === viewId));

    contentViews.forEach(v => v.classList.toggle("active", v.id === viewId));

    if (viewHeaders[viewId]) {
      if (viewTitle) viewTitle.innerText = viewHeaders[viewId].title;
      if (viewSubtitle) viewSubtitle.innerText = viewHeaders[viewId].sub;
    }

    if (viewId === "view-automations") loadAutomations();
    if (viewId === "view-contacts") loadContacts();
    if (viewId === "view-inbox") scrollInboxToBottom();
    if (viewId === "view-broadcast") {
      refreshCampaignStatus();
      refreshTargetsTable();
    }
  }

  // --- Account State ---
  async function refreshAccountStatus() {
    accountHandle.innerText = "Checking...";
    try {
      const res = await fetch("/api/check-login", { method: "POST" });
      const data = await res.json();
      if (data.logged_in) {
        const username = data.username ? `@${data.username}` : "Connected";
        accountHandle.innerText = username;
        accountBadge.innerText = "Online";
        accountBadge.className = "account-badge connected";
        settingsStatusText.innerText = `Authenticated as ${username}`;
      } else {
        accountHandle.innerText = "Not Connected";
        accountBadge.innerText = "Offline";
        accountBadge.className = "account-badge not-connected";
        settingsStatusText.innerText = "No active Instagram session. Click button below to log in.";
      }
    } catch (e) {
      accountHandle.innerText = "Offline";
      accountBadge.className = "account-badge not-connected";
    }
  }

  async function triggerOpenLogin() {
    try {
      const res = await fetch("/api/open-login", { method: "POST" });
      const data = await res.json();
      if (data.success) {
        alert("Browser opening! Please enter your Instagram credentials and 2FA in the browser window.");
      } else {
        alert(data.detail || "Error opening browser.");
      }
    } catch (err) {
      alert("Error: " + err.message);
    }
  }

  // --- Watcher Toggle ---
  async function toggleWatcher() {
    if (!watcherRunning) {
      const postUrl = watcherPostUrl ? watcherPostUrl.value.trim() : "";
      const interval = watcherInterval ? parseInt(watcherInterval.value, 10) || 60 : 60;
      try {
        const res = await fetch("/api/watcher/start", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ post_url: postUrl || null, interval })
        });
        const data = await res.json();
        if (data.success) {
          watcherRunning = true;
          watcherDot.className = "status-indicator green";
          watcherText.innerText = "Watcher: Active (Polling)";
          btnToggleWatcher.innerText = "⏹️ Stop Watcher";
          btnToggleWatcher.className = "btn btn-danger btn-sm";
        }
      } catch (err) {
        alert("Failed to start watcher: " + err.message);
      }
    } else {
      try {
        const res = await fetch("/api/watcher/stop", { method: "POST" });
        const data = await res.json();
        watcherRunning = false;
        watcherDot.className = "status-indicator yellow";
        watcherText.innerText = "Watcher: Inactive";
        btnToggleWatcher.innerText = "▶️ Start Live Watcher";
        btnToggleWatcher.className = "btn btn-secondary btn-sm";
      } catch (err) {
        alert("Failed to stop watcher: " + err.message);
      }
    }
  }

  // --- Automations Engine UI ---
  function setupAutomationsUI() {
    filterTabs.forEach(tab => {
      tab.addEventListener("click", () => {
        filterTabs.forEach(t => t.classList.remove("active"));
        tab.classList.add("active");
        currentFilter = tab.getAttribute("data-filter");
        renderAutomations();
      });
    });

    btnNewAutomation.addEventListener("click", () => openAutomationModal());
    btnCloseAutomationModal.addEventListener("click", closeAutomationModal);
    btnCancelAutomation.addEventListener("click", closeAutomationModal);
    btnSaveAutomation.addEventListener("click", saveAutomationRule);

    modalVarChips.forEach(c => {
      c.addEventListener("click", () => {
        insertAtCursor(ruleDmMessage, c.getAttribute("data-var"));
      });
    });
  }

  async function loadAutomations() {
    try {
      const res = await fetch("/api/automations");
      const data = await res.json();
      allAutomations = data.automations || [];
      if (navAutomationsCount) navAutomationsCount.innerText = allAutomations.length;
      if (activeRulesCount) activeRulesCount.innerText = allAutomations.filter(r => r.is_active).length;
      renderAutomations();
    } catch (e) {
      console.error(e);
    }
  }

  // --- automation cards -----------------------------------------------------
  // These used to print the rule almost verbatim: "WHEN FOLLOWER:", a bare
  // arrow, and raw spintax with its pipes showing. That is a debug dump, not a
  // product. A card now reads as three numbered steps in plain language, with
  // the spintax collapsed to one example plus a count.

  // "{Hi|Hey|Hello} there" -> ["Hi there", "Hey there", "Hello there"]
  // A group WITHOUT a pipe is a merge field, not spintax: {name}, {first_name},
  // {username}. Expanding those turned "Hey {name}!" into "Hey name!", which
  // reads like the personalisation is broken. Only split on real choices.
  var SPIN_GROUP = /\{([^{}]*\|[^{}]*)\}/;

  function spintaxVariants(text, cap) {
    cap = cap || 8;
    var out = [String(text || "")];
    var guard = 0;
    while (guard++ < 6) {
      var next = [];
      var grew = false;
      out.forEach(function (str) {
        var m = str.match(SPIN_GROUP);
        if (!m) { next.push(str); return; }
        grew = true;
        m[1].split("|").forEach(function (choice) {
          next.push(str.slice(0, m.index) + choice.trim() + str.slice(m.index + m[0].length));
        });
      });
      out = next.slice(0, cap * 4);
      if (!grew) break;
    }
    return out.filter(function (v, i, a) { return v && a.indexOf(v) === i; }).slice(0, cap);
  }

  // Merge fields like {name} stay visible so the user can see the
  // personalisation. A leftover single-option group — "{Check DMs!}" — is
  // spintax with one choice, so drop its braces rather than show them.
  var MERGE_FIELD = /^[a-z][a-z0-9_]*$/;

  function showMergeFields(text) {
    return String(text || "").replace(/\{([^{}|]+)\}/g, function (whole, inner) {
      return MERGE_FIELD.test(inner.trim()) ? whole : inner.trim();
    });
  }

  function firstUrl(text) {
    var m = String(text || "").match(/https?:\/\/[^\s"'<>]+/);
    return m ? m[0] : "";
  }

  function prettyUrl(url) {
    return url.replace(/^https?:\/\//, "").replace(/\/$/, "");
  }

  function clip(text, n) {
    text = String(text || "").trim();
    return text.length > n ? text.slice(0, n - 1).trimEnd() + "…" : text;
  }

  function stepBlock(index, title, bodyHtml) {
    return '<div class="flow-step">' +
      '<span class="flow-num">' + index + '</span>' +
      '<div class="flow-body"><b>' + title + '</b>' + bodyHtml + '</div></div>';
  }

  function variantBlock(raw, dropUrl) {
    var variants = spintaxVariants(raw);
    var extra = variants.length - 1;
    var shown = showMergeFields(variants[0]);
    // the link is rendered as its own chip below, so strip it from the quote
    if (dropUrl) shown = shown.replace(/https?:\/\/[^\s"'<>]+/g, "").replace(/\s{2,}/g, " ").trim();
    return '<p class="flow-quote">“' + escapeHtml(clip(shown, 100)) + '”</p>' +
      (extra > 0 ? '<span class="flow-more">+' + extra + ' more wording' +
        (extra === 1 ? '' : 's') + ' &mdash; rotated so no two look identical</span>' : '');
  }

  function renderAutomations() {
    let filtered = allAutomations;
    if (currentFilter !== "all") {
      filtered = allAutomations.filter(r => r.type === currentFilter);
    }

    if (filtered.length === 0) {
      automationsGrid.innerHTML = `
        <div class="flow-empty">
          <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
          <b>Nothing here yet</b>
          <p>Create an automation and every comment on that reel turns into a DM within seconds.</p>
          <button class="btn btn-primary btn-sm" onclick="document.getElementById('btnNewAutomation').click()">Create your first automation</button>
        </div>`;
      return;
    }

    automationsGrid.innerHTML = filtered.map(rule => {
      const kind = rule.type === "comment_to_dm" ? { label: "Comment to DM", cls: "k-comment" }
                 : rule.type === "dm_keyword"    ? { label: "DM keyword", cls: "k-dm" }
                 :                                 { label: "Story mention", cls: "k-story" };

      const words = (rule.trigger_keywords || []).filter(Boolean);
      const anyWord = !words.length || words[0] === "*";
      const chips = anyWord
        ? '<span class="flow-chip flow-chip-any">any comment</span>'
        : words.map(w => `<span class="flow-chip">${escapeHtml(w)}</span>`).join("");

      const where = rule.type !== "comment_to_dm"
        ? "sends you a direct message"
        : (rule.post_target === "all_posts" ? "comments on any reel or post" : "comments on your chosen reel");

      const link = firstUrl(rule.dm_message);
      let step = 0;
      const steps = [
        stepBlock(++step, "Someone " + where,
          '<div class="flow-chips">' + chips + '</div>'),
        rule.public_comment_reply
          ? stepBlock(++step, "You reply on the comment", variantBlock(rule.public_comment_reply))
          : "",
        stepBlock(++step, "They get a DM",
          variantBlock(rule.dm_message, !!link) +
          (link ? '<span class="flow-link"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path d="M10 13a5 5 0 007.5.5l3-3a5 5 0 00-7-7l-1.7 1.7"/><path d="M14 11a5 5 0 00-7.5-.5l-3 3a5 5 0 007 7l1.7-1.7"/></svg>' +
            escapeHtml(prettyUrl(link)) + '</span>' : ''))
      ].join("");

      const tags = (rule.tags || []).map(t => `<span class="flow-tag">${escapeHtml(t)}</span>`).join("");

      return `
        <article class="flow-card${rule.is_active ? " is-live" : ""}">
          <header class="flow-head">
            <div class="flow-title">
              <span class="flow-kind ${kind.cls}">${kind.label}</span>
              <h3>${escapeHtml(rule.name)}</h3>
            </div>
            <label class="switch-toggle" title="${rule.is_active ? "Live — switch off" : "Paused — switch on"}">
              <input type="checkbox" ${rule.is_active ? "checked" : ""} onchange="window.handleToggleRule('${rule.id}')">
              <span class="slider"></span>
            </label>
          </header>

          <div class="flow-state">${rule.is_active
            ? '<span class="flow-dot live"></span> Live — running right now'
            : '<span class="flow-dot"></span> Paused'}</div>

          <div class="flow-steps">${steps}</div>

          <footer class="flow-foot">
            ${tags ? `<div class="flow-tags">${tags}</div>` : ""}
            <div class="flow-actions">
              <button class="btn btn-secondary btn-xs" onclick="window.testInSimulator('${escapeHtml(words[0] || 'link')}', '${rule.type}')">Test it</button>
              <button class="btn btn-ghost btn-xs" onclick="window.handleEditRule('${rule.id}')">Edit</button>
              <button class="btn btn-ghost btn-xs text-danger" onclick="window.handleDeleteRule('${rule.id}')">Delete</button>
            </div>
          </footer>
        </article>`;
    }).join("");
  }

  window.handleToggleRule = async (ruleId) => {
    try {
      await fetch(`/api/automations/${ruleId}/toggle`, { method: "POST" });
      await loadAutomations();
    } catch (e) {
      console.error(e);
    }
  };

  window.handleDeleteRule = async (ruleId) => {
    if (!confirm("Are you sure you want to delete this automation rule?")) return;
    try {
      await fetch(`/api/automations/${ruleId}`, { method: "DELETE" });
      await loadAutomations();
    } catch (e) {
      console.error(e);
    }
  };

  window.handleEditRule = (ruleId) => {
    const rule = allAutomations.find(r => r.id === ruleId);
    if (rule) openAutomationModal(rule);
  };

  window.testInSimulator = (keyword, type) => {
    switchView("view-simulator");
    const channel = type === "comment_to_dm" ? "comment" : "dm";
    simSegmentBtns.forEach(b => b.classList.toggle("active", b.getAttribute("data-sim-channel") === channel));
    activeSimChannel = channel;
    phoneInputText.value = keyword === "*" ? "hello" : keyword;
    btnPhoneSend.click();
  };

  function openAutomationModal(rule = null) {
    automationModal.classList.add("active");
    if (rule) {
      modalAutomationTitle.innerText = "Edit ConverFlow Automation";
      editRuleId.value = rule.id;
      ruleName.value = rule.name;
      ruleType.value = rule.type;
      ruleKeywords.value = (rule.trigger_keywords || []).join(", ");
      rulePostTarget.value = rule.post_target || "all_posts";
      rulePublicReply.value = rule.public_comment_reply || "";
      ruleDmMessage.value = rule.dm_message || "";
      ruleTags.value = (rule.tags || []).join(", ");
    } else {
      modalAutomationTitle.innerText = "Create ConverFlow Automation";
      editRuleId.value = "";
      ruleName.value = "";
      ruleType.value = "comment_to_dm";
      ruleKeywords.value = "link, send, info";
      rulePostTarget.value = "all_posts";
      rulePublicReply.value = "{Sent you a DM! Check your inbox 🚀|Check your messages! 📩}";
      ruleDmMessage.value = "Hey {name}! Here is the direct link: https://yourwebsite.com/offer Let me know if you have questions!";
      ruleTags.value = "Hot Lead, Link Requested";
    }
  }

  function closeAutomationModal() {
    automationModal.classList.remove("active");
  }

  async function saveAutomationRule() {
    const name = ruleName.value.trim();
    const dmText = ruleDmMessage.value.trim();
    if (!name || !dmText) {
      alert("Please provide both an Automation Name and a Direct Message body.");
      return;
    }

    const keywords = ruleKeywords.value.split(",").map(k => k.trim()).filter(Boolean);
    const tags = ruleTags.value.split(",").map(t => t.trim()).filter(Boolean);

    const payload = {
      id: editRuleId.value || undefined,
      name: name,
      type: ruleType.value,
      post_target: rulePostTarget.value.trim() || "all_posts",
      trigger_keywords: keywords.length ? keywords : ["*"],
      public_comment_reply: rulePublicReply.value.trim(),
      dm_message: dmText,
      tags: tags,
      is_active: true
    };

    try {
      const res = await fetch("/api/automations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.success) {
        closeAutomationModal();
        await loadAutomations();
      } else {
        alert("Failed to save: " + (data.detail || "Unknown error"));
      }
    } catch (e) {
      alert("Error: " + e.message);
    }
  }

  // --- Interactive Flow Simulator ---
  function setupSimulator() {
    simSegmentBtns.forEach(btn => {
      btn.addEventListener("click", () => {
        simSegmentBtns.forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        activeSimChannel = btn.getAttribute("data-sim-channel");
      });
    });

    simChips.forEach(chip => {
      chip.addEventListener("click", () => {
        phoneInputText.value = chip.getAttribute("data-test");
        sendSimMessage();
      });
    });

    btnPhoneSend.addEventListener("click", sendSimMessage);
    phoneInputText.addEventListener("keydown", (e) => {
      if (e.key === "Enter") sendSimMessage();
    });

    btnClearSimChat.addEventListener("click", () => {
      phoneChatBody.innerHTML = `
        <div class="chat-date">TODAY</div>
        <div class="chat-bubble bot-bubble">
          <p>👋 Hey! Type a keyword like <strong>"link"</strong>, <strong>"guide"</strong>, or <strong>"price"</strong> to test your ConverFlow automation!</p>
        </div>
      `;
    });
  }

  async function sendSimMessage() {
    const text = phoneInputText.value.trim();
    if (!text) return;
    phoneInputText.value = "";

    const username = simUsernameInput.value.trim() || "alex_growth";

    // Append User Bubble
    appendPhoneBubble("user", text);

    try {
      const res = await fetch("/api/simulator/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          channel: activeSimChannel,
          text: text,
          username: username
        })
      });
      const data = await res.json();

      setTimeout(() => {
        if (data.matched) {
          let botHtml = "";

          // If Comment-to-DM, display public reply banner
          if (data.channel === "comment" && data.public_reply) {
            botHtml += `
              <div class="comment-reply-banner">
                <strong>Public Comment Reply:</strong><br>
                "${escapeHtml(data.public_reply)}"
              </div>
            `;
          }

          // Private DM Bubble
          if (data.dm_reply) {
            botHtml += `<p>${escapeHtml(data.dm_reply)}</p>`;
          }

          // Tags pill
          if (data.tags && data.tags.length) {
            botHtml += `<div>${data.tags.map(t => `<span class="lead-tag-pill">🏷️ ${escapeHtml(t)}</span>`).join(" ")}</div>`;
          }

          appendPhoneBubble("bot", botHtml, true);
        } else {
          appendPhoneBubble("bot", `<p style="color:#94a3b8;"><em>${escapeHtml(data.message)}</em></p>`, true);
        }
      }, 400);

    } catch (err) {
      appendPhoneBubble("bot", `<p style="color:#f87171;">Error connecting to simulator: ${err.message}</p>`, true);
    }
  }

  function appendPhoneBubble(type, content, isHtml = false) {
    const bubble = document.createElement("div");
    bubble.className = `chat-bubble ${type}-bubble`;
    if (isHtml) {
      bubble.innerHTML = content;
    } else {
      bubble.textContent = content;
    }
    phoneChatBody.appendChild(bubble);
    phoneChatBody.scrollTop = phoneChatBody.scrollHeight;
  }

  // =========================================================================
  // --- CONTACTS & CRM UI SYSTEM (7-Column Table + Filter Tabs + Lead Chat) ---
  // =========================================================================
  const sampleFallbackContacts = [
    {
      username: "sarah_growth",
      name: "Sarah Jenkins",
      source: "Reel: 50 Canva Pack",
      tags: ["Hot Lead", "VIP"],
      last_interaction: "2m ago",
      messages_count: 3,
      status: "active"
    },
    {
      username: "rahul_marketing",
      name: "Rahul Sharma",
      source: "Reel: 50 Canva Pack",
      tags: ["Client", "Agency"],
      last_interaction: "14m ago",
      messages_count: 2,
      status: "active"
    },
    {
      username: "mike_dev",
      name: "Michael Ross",
      source: "Story Mention",
      tags: ["Developer", "API"],
      last_interaction: "1h ago",
      messages_count: 4,
      status: "active"
    },
    {
      username: "clara_design",
      name: "Clara Dupont",
      source: "Reel: Design Tips",
      tags: ["Designer"],
      last_interaction: "3h ago",
      messages_count: 1,
      status: "converted"
    },
    {
      username: "alex_growth",
      name: "Alex Morgan",
      source: "Direct DM",
      tags: ["SaaS Founder"],
      last_interaction: "5h ago",
      messages_count: 6,
      status: "active"
    },
    {
      username: "priya_sharma",
      name: "Priya Sharma",
      source: "Reel: Growth Tips",
      tags: ["Creator", "Hot Lead"],
      last_interaction: "1d ago",
      messages_count: 2,
      status: "converted"
    },
    {
      username: "vikram_seo",
      name: "Vikram Mehta",
      source: "Reel: SEO Hacks",
      tags: ["Agency"],
      last_interaction: "2d ago",
      messages_count: 1,
      status: "followed"
    },
    {
      username: "elena_art",
      name: "Elena Petrova",
      source: "Story Mention",
      tags: ["Influencer"],
      last_interaction: "3d ago",
      messages_count: 5,
      status: "active"
    }
  ];

  let contactsActiveFilter = "all";
  let cachedContactsList = [];

  function setupContactsUI() {
    if (contactsSearch) {
      contactsSearch.addEventListener("input", () => {
        filterAndRenderContacts();
      });
    }

    if (btnExportContacts) {
      btnExportContacts.addEventListener("click", () => {
        window.location.href = "/api/contacts/export";
      });
    }

    const btnAddLeadQuick = document.getElementById("btnAddLeadQuick");
    if (btnAddLeadQuick) {
      btnAddLeadQuick.addEventListener("click", () => {
        const username = prompt("Enter Instagram handle for new lead (e.g. rohit_creator):");
        if (!username) return;
        const cleanUser = username.replace("@", "").trim();
        const newContact = {
          username: cleanUser,
          name: cleanUser.replace(/_/g, " "),
          source: "Manual Capture",
          tags: ["New Lead", "Manual"],
          last_interaction: "Just now",
          messages_count: 1,
          status: "active"
        };
        cachedContactsList.unshift(newContact);
        filterAndRenderContacts();
        alert(`✅ Lead @${cleanUser} added to Contacts & CRM!`);
      });
    }

    const tabPills = document.querySelectorAll(".contacts-table-card .tab-pill");
    tabPills.forEach(pill => {
      pill.addEventListener("click", () => {
        tabPills.forEach(p => p.classList.remove("active"));
        pill.classList.add("active");
        contactsActiveFilter = pill.getAttribute("data-filter") || "all";
        filterAndRenderContacts();
      });
    });
  }

  async function loadContacts(search = "") {
    try {
      const url = search ? `/api/contacts?search=${encodeURIComponent(search)}` : "/api/contacts";
      const res = await fetch(url);
      const data = await res.json();
      const serverContacts = data.contacts || [];

      // Combine server contacts with sample leads ensuring no duplicates by username
      const existingUsernames = new Set(serverContacts.map(c => c.username));
      const merged = [...serverContacts];
      sampleFallbackContacts.forEach(sample => {
        if (!existingUsernames.has(sample.username)) {
          merged.push(sample);
        }
      });

      cachedContactsList = merged;
      const totalCount = cachedContactsList.length;
      if (navContactsCount) navContactsCount.innerText = totalCount;
      const statContactsTotal = document.getElementById("statContactsTotal");
      if (statContactsTotal) statContactsTotal.innerText = totalCount;

      filterAndRenderContacts();
    } catch (e) {
      console.error(e);
      cachedContactsList = [...sampleFallbackContacts];
      filterAndRenderContacts();
    }
  }

  function filterAndRenderContacts() {
    const searchVal = contactsSearch ? contactsSearch.value.trim().toLowerCase() : "";
    let filtered = cachedContactsList;

    if (contactsActiveFilter === "reel") {
      filtered = filtered.filter(c => (c.source || "").toLowerCase().includes("reel"));
    } else if (contactsActiveFilter === "story") {
      filtered = filtered.filter(c => (c.source || "").toLowerCase().includes("story"));
    } else if (contactsActiveFilter === "dm") {
      filtered = filtered.filter(c => (c.source || "").toLowerCase().includes("dm") || (c.source || "").toLowerCase().includes("direct"));
    }

    if (searchVal) {
      filtered = filtered.filter(c =>
        c.username.toLowerCase().includes(searchVal) ||
        (c.name && c.name.toLowerCase().includes(searchVal)) ||
        (c.tags && c.tags.some(t => t.toLowerCase().includes(searchVal))) ||
        (c.source && c.source.toLowerCase().includes(searchVal))
      );
    }

    if (!contactsTableBody) return;

    if (filtered.length === 0) {
      contactsTableBody.innerHTML = `
        <tr class="empty-row">
          <td colspan="7" style="text-align: center; color: var(--text-muted); padding: 36px;">
            No matching contacts found.
          </td>
        </tr>
      `;
      return;
    }

    const colors = ["#00824b", "#2563eb", "#9333ea", "#ea580c", "#0d9488", "#dc2626"];

    contactsTableBody.innerHTML = filtered.map((c, idx) => {
      const initials = (c.name ? c.name.split(" ").map(w => w[0]).join("") : c.username.slice(0, 2)).toUpperCase();
      const color = colors[idx % colors.length];
      const tagsHtml = (c.tags || []).map(t => `<span class="tag-pill">${escapeHtml(t)}</span>`).join(" ");
      const statusClass = c.status === "active" ? "active" : (c.status === "converted" ? "converted" : "followed");
      const statusLabel = c.status ? (c.status.charAt(0).toUpperCase() + c.status.slice(1)) : "Active";

      return `
        <tr>
          <td>
            <div class="contact-cell">
              <div class="contact-avatar" style="background-color: ${color};">${escapeHtml(initials)}</div>
              <div>
                <span class="contact-handle">@${escapeHtml(c.username)}</span>
                <span class="contact-name">${escapeHtml(c.name || 'Instagram User')}</span>
              </div>
            </div>
          </td>
          <td>
            <span class="source-badge">📹 ${escapeHtml(c.source || 'Reel Comments')}</span>
          </td>
          <td>${tagsHtml || '<span style="color:var(--text-faint);">-</span>'}</td>
          <td><small style="color:var(--text-muted);">${escapeHtml(c.last_interaction || 'Recent')}</small></td>
          <td><span class="badge badge-sent">${c.messages_count || 1} msg</span></td>
          <td><span class="lead-status-pill ${statusClass}">${statusLabel}</span></td>
          <td style="text-align: right;">
            <button class="btn-table-action" onclick="window.openInboxWithUser('${escapeHtml(c.username)}')">
              💬 Chat
            </button>
          </td>
        </tr>
      `;
    }).join("");
  }

  window.openInboxWithUser = (handle) => {
    switchView("view-inbox");
    selectInboxThread(handle);
  };

  // =========================================================================
  // --- LIVE INSTAGRAM DM INBOX (3-Pane Unified Messenger) ---
  // =========================================================================
  const inboxThreadsData = [
    {
      handle: "sarah_growth",
      name: "Sarah Jenkins",
      avatar: "SG",
      color: "#00824b",
      time: "2m",
      status: "Active now · Follows you",
      leadStatus: "Hot Lead",
      source: "Reel #1: 50 Canva Pack",
      messagesCount: 3,
      linkClicks: 1,
      deliveryPct: "100%",
      notes: "Requested Canva offer pack. Very high intent for website design service.",
      messages: [
        { type: "divider", text: "TODAY" },
        { type: "incoming", text: 'Commented on your Reel: <strong>"link pls! ❤️"</strong>' },
        { type: "outgoing", text: 'Hey there! I\'m so happy you\'re here, thanks so much for your interest 😊<br><br>Click below and I\'ll send you the link in just a sec ✨', button: "Send me the link" },
        { type: "incoming-btn", text: 'Clicked <strong>"Send me the link"</strong>' },
        { type: "outgoing", text: 'Here is your link 👇<br><a href="https://satnamwebservices.com/offer" class="inbox-link-card" target="_blank">🔗 https://satnamwebservices.com/offer</a>' }
      ]
    },
    {
      handle: "rahul_marketing",
      name: "Rahul Sharma",
      avatar: "RM",
      color: "#2563eb",
      time: "14m",
      status: "Active 14m ago · Follows you",
      leadStatus: "Client",
      source: "Reel #1: 50 Canva Pack",
      messagesCount: 2,
      linkClicks: 1,
      deliveryPct: "100%",
      notes: "Agency owner looking to scale client acquisition funnel.",
      messages: [
        { type: "divider", text: "TODAY" },
        { type: "incoming", text: 'Commented on your Reel: <strong>"canva templates"</strong>' },
        { type: "outgoing", text: 'Hey Rahul! Here is the direct link to the 50 Canva Pack for your marketing team 🚀<br><a href="https://satnamwebservices.com/offer" class="inbox-link-card" target="_blank">🔗 https://satnamwebservices.com/offer</a>' },
        { type: "incoming", text: 'Thanks for the link! Looking at the offer now.' }
      ]
    },
    {
      handle: "mike_dev",
      name: "Michael Ross",
      avatar: "MD",
      color: "#9333ea",
      time: "1h",
      status: "Active 1h ago",
      leadStatus: "Developer",
      source: "Story Mention",
      messagesCount: 4,
      linkClicks: 2,
      deliveryPct: "100%",
      notes: "Asked about Python Meta Webhook integration source code.",
      messages: [
        { type: "divider", text: "TODAY" },
        { type: "incoming", text: 'Mentioned you in a Story: <em>"Loving the automation tool!"</em>' },
        { type: "outgoing", text: 'Hey Michael! Thanks a ton for the shoutout 🙌 Let me know if you need any assistance.' },
        { type: "incoming", text: 'Does this include the source code for Meta Graph API?' }
      ]
    },
    {
      handle: "clara_design",
      name: "Clara Dupont",
      avatar: "CD",
      color: "#ea580c",
      time: "3h",
      status: "Active 3h ago",
      leadStatus: "Designer",
      source: "Reel: Design Tips",
      messagesCount: 1,
      linkClicks: 1,
      deliveryPct: "100%",
      notes: "Freelance UI designer in Paris.",
      messages: [
        { type: "divider", text: "YESTERDAY" },
        { type: "incoming", text: 'Commented on Reel: <strong>"link"</strong>' },
        { type: "outgoing", text: 'Here are the design assets & wireframe blueprint 👇<br><a href="https://satnamwebservices.com/offer" class="inbox-link-card" target="_blank">🔗 https://satnamwebservices.com/offer</a>' }
      ]
    }
  ];

  let currentInboxUser = "sarah_growth";
  let isBotModeActive = true;

  function setupInboxUI() {
    const threadItems = document.querySelectorAll(".inbox-thread-item");
    threadItems.forEach(item => {
      item.addEventListener("click", () => {
        const user = item.getAttribute("data-user");
        selectInboxThread(user);
      });
    });

    const btnSendInboxMessage = document.getElementById("btnSendInboxMessage");
    const inboxInputMessage = document.getElementById("inboxInputMessage");

    if (btnSendInboxMessage && inboxInputMessage) {
      btnSendInboxMessage.addEventListener("click", sendInboxMessage);
      inboxInputMessage.addEventListener("keydown", (e) => {
        if (e.key === "Enter") sendInboxMessage();
      });
    }

    const snippetBtns = document.querySelectorAll(".snippet-btn");
    snippetBtns.forEach(btn => {
      btn.addEventListener("click", () => {
        const snip = btn.getAttribute("data-snippet");
        if (inboxInputMessage) {
          inboxInputMessage.value = snip;
          inboxInputMessage.focus();
        }
      });
    });

    const btnToggleBotHandled = document.getElementById("btnToggleBotHandled");
    if (btnToggleBotHandled) {
      btnToggleBotHandled.addEventListener("click", () => {
        isBotModeActive = !isBotModeActive;
        if (isBotModeActive) {
          btnToggleBotHandled.innerText = "🤖 Bot Mode: Active";
          btnToggleBotHandled.className = "btn btn-secondary btn-xs";
        } else {
          btnToggleBotHandled.innerText = "👤 Human Takeover";
          btnToggleBotHandled.className = "btn btn-green btn-xs";
        }
      });
    }

    const inboxSearchInput = document.getElementById("inboxSearchInput");
    if (inboxSearchInput) {
      inboxSearchInput.addEventListener("input", () => {
        const q = inboxSearchInput.value.trim().toLowerCase();
        const items = document.querySelectorAll(".inbox-thread-item");
        items.forEach(it => {
          const user = it.getAttribute("data-user") || "";
          const handle = it.querySelector(".thread-handle") ? it.querySelector(".thread-handle").innerText.toLowerCase() : "";
          const snip = it.querySelector(".thread-snippet") ? it.querySelector(".thread-snippet").innerText.toLowerCase() : "";
          const match = user.includes(q) || handle.includes(q) || snip.includes(q);
          it.style.display = match ? "flex" : "none";
        });
      });
    }
  }

  function selectInboxThread(handle) {
    currentInboxUser = handle;
    const thread = inboxThreadsData.find(t => t.handle === handle) || {
      handle: handle,
      name: handle.replace(/_/g, " "),
      avatar: handle.slice(0, 2).toUpperCase(),
      color: "#00824b",
      time: "Now",
      status: "Active now",
      leadStatus: "Hot Lead",
      source: "Reel Comment",
      messagesCount: 1,
      linkClicks: 1,
      deliveryPct: "100%",
      notes: "Lead captured via ConverFlow automation.",
      messages: [
        { type: "divider", text: "TODAY" },
        { type: "incoming", text: `Triggered automation keyword on Reel.` },
        { type: "outgoing", text: `Hey there! Here is the direct link you requested 👇<br><a href="https://satnamwebservices.com/offer" class="inbox-link-card" target="_blank">🔗 https://satnamwebservices.com/offer</a>` }
      ]
    };

    // Update active class on thread items
    document.querySelectorAll(".inbox-thread-item").forEach(item => {
      item.classList.toggle("active", item.getAttribute("data-user") === handle);
    });

    // Update header
    const inboxHeaderAvatar = document.getElementById("inboxHeaderAvatar");
    const inboxHeaderName = document.getElementById("inboxHeaderName");
    if (inboxHeaderAvatar) {
      inboxHeaderAvatar.innerText = thread.avatar;
      inboxHeaderAvatar.style.backgroundColor = thread.color;
    }
    if (inboxHeaderName) inboxHeaderName.innerText = `@${thread.handle}`;

    // Update Lead Profile Inspector
    const inspectorHandle = document.getElementById("inspectorHandle");
    const inspectorAvatar = document.querySelector(".inspector-avatar");
    const inspectorRole = document.querySelector(".inspector-role");
    const inspectorSource = document.querySelector(".inspector-val");
    const inspectorMsgCount = document.getElementById("inspectorMsgCount");
    const inspectorNotes = document.querySelector(".inspector-notes");

    if (inspectorHandle) inspectorHandle.innerText = `@${thread.handle}`;
    if (inspectorAvatar) {
      inspectorAvatar.innerText = thread.avatar;
      inspectorAvatar.style.backgroundColor = thread.color;
    }
    if (inspectorRole) inspectorRole.innerText = thread.name;
    if (inspectorSource) inspectorSource.innerText = thread.source;
    if (inspectorMsgCount) inspectorMsgCount.innerText = thread.messagesCount;
    if (inspectorNotes) inspectorNotes.value = thread.notes;

    // Render Messages
    renderInboxMessages(thread);
    scrollInboxToBottom();
  }

  function renderInboxMessages(thread) {
    const scrollBox = document.getElementById("inboxMessagesScroll");
    if (!scrollBox) return;

    scrollBox.innerHTML = thread.messages.map(m => {
      if (m.type === "divider") {
        return `<div class="chat-divider"><span>${escapeHtml(m.text)}</span></div>`;
      }
      if (m.type === "incoming") {
        return `
          <div class="inbox-msg-row incoming">
            <div class="inbox-bubble incoming">${m.text}</div>
          </div>
        `;
      }
      if (m.type === "incoming-btn") {
        return `
          <div class="inbox-msg-row incoming">
            <div class="inbox-bubble incoming button-click-bubble">${m.text}</div>
          </div>
        `;
      }
      if (m.type === "outgoing") {
        const btnHtml = m.button ? `<div class="inbox-bubble-button">${escapeHtml(m.button)}</div>` : "";
        return `
          <div class="inbox-msg-row outgoing">
            <div class="inbox-bubble outgoing">
              ${m.text}
              ${btnHtml}
            </div>
          </div>
        `;
      }
      return "";
    }).join("");
  }

  function sendInboxMessage() {
    const input = document.getElementById("inboxInputMessage");
    if (!input) return;
    const text = input.value.trim();
    if (!text) return;

    const thread = inboxThreadsData.find(t => t.handle === currentInboxUser);
    if (thread) {
      thread.messages.push({
        type: "outgoing",
        text: escapeHtml(text)
      });
      thread.messagesCount++;
      renderInboxMessages(thread);
    } else {
      const scrollBox = document.getElementById("inboxMessagesScroll");
      if (scrollBox) {
        const row = document.createElement("div");
        row.className = "inbox-msg-row outgoing";
        row.innerHTML = `<div class="inbox-bubble outgoing">${escapeHtml(text)}</div>`;
        scrollBox.appendChild(row);
      }
    }

    input.value = "";
    scrollInboxToBottom();
  }

  function scrollInboxToBottom() {
    const scrollBox = document.getElementById("inboxMessagesScroll");
    if (scrollBox) {
      setTimeout(() => {
        scrollBox.scrollTop = scrollBox.scrollHeight;
      }, 50);
    }
  }

  // =========================================================================
  // --- AI ASSIST & FLOW GENERATOR SYSTEM ---
  // =========================================================================
  function setupAiAssistUI() {
    const btnGenerateAiFlow = document.getElementById("btnGenerateAiFlow");
    const aiInputOffer = document.getElementById("aiInputOffer");
    const aiToneSelect = document.getElementById("aiToneSelect");
    const aiInputLink = document.getElementById("aiInputLink");

    const aiResKeyword = document.getElementById("aiResKeyword");
    const aiResReplies = document.getElementById("aiResReplies");
    const aiResOpeningDm = document.getElementById("aiResOpeningDm");
    const aiResButton = document.getElementById("aiResButton");

    if (btnGenerateAiFlow) {
      btnGenerateAiFlow.addEventListener("click", () => {
        const offer = (aiInputOffer && aiInputOffer.value.trim()) || "Free Canva Templates";
        const tone = (aiToneSelect && aiToneSelect.value) || "creator";
        const link = (aiInputLink && aiInputLink.value.trim()) || "https://satnamwebservices.com/offer";

        btnGenerateAiFlow.innerText = "✨ Generating Multi-Step Flow...";
        btnGenerateAiFlow.disabled = true;

        setTimeout(() => {
          let mainWord = "PACK";
          if (offer.toLowerCase().includes("checklist")) mainWord = "CHECKLIST";
          else if (offer.toLowerCase().includes("guide")) mainWord = "GUIDE";
          else if (offer.toLowerCase().includes("canva")) mainWord = "CANVA";
          else if (offer.toLowerCase().includes("website")) mainWord = "WEBSITE";
          else if (offer.toLowerCase().includes("design")) mainWord = "DESIGN";

          const kwList = `${mainWord}, ${mainWord.toLowerCase()}, LINK`;
          if (aiResKeyword) aiResKeyword.innerText = kwList;

          let r1, r2, r3, opening, btnText;
          if (tone === "hype") {
            r1 = `Just sent the link! Don't sleep on this 🚀 Check your message requests!`;
            r2 = `Boom! Link is waiting in your DMs right now 🔥`;
            r3 = `Sent! Go grab it before this reel gets buried in your feed ⚡`;
            opening = `LET'S GO! 🔥 So stoked you're here.<br><br>Tap the button below and I'll drop the ${escapeHtml(offer)} right into this chat 👇`;
            btnText = `GET ACCESS NOW 🚀`;
          } else if (tone === "authority") {
            r1 = `I have sent the resources directly to your Instagram Direct inbox.`;
            r2 = `Delivered. Please review the material and let me know your thoughts.`;
            r3 = `Sent! Please check your message requests for the full asset link.`;
            opening = `Hello! Thank you for watching my recent breakdown.<br><br>To receive your copy of the <strong>${escapeHtml(offer)}</strong>, click the confirmation button below:`;
            btnText = `Access Official Guide 👔`;
          } else if (tone === "minimal") {
            r1 = `Sent in DMs ✨`;
            r2 = `Check your inbox 👇`;
            r3 = `Delivered! Enjoy ✨`;
            opening = `Hey! Thanks for watching.<br><br>Tap below for the ${escapeHtml(offer)} link:`;
            btnText = `Send Link ✨`;
          } else {
            r1 = `Just sent you the ${escapeHtml(offer)} in DMs! Check your message requests 😊`;
            r2 = `Sent! Enjoy, let me know how it performs for you 🚀`;
            r3 = `Check your messages! The link is waiting for you ✨`;
            opening = `Hey there! Thanks so much for stopping by my reel 😊<br><br>Click the button below and I'll send you the <strong>${escapeHtml(offer)}</strong> right away! 👇`;
            btnText = `Send me the pack 🎁`;
          }

          if (aiResReplies) {
            aiResReplies.innerHTML = `
              <li>1. ${escapeHtml(r1)}</li>
              <li>2. ${escapeHtml(r2)}</li>
              <li>3. ${escapeHtml(r3)}</li>
            `;
          }
          if (aiResOpeningDm) aiResOpeningDm.innerHTML = opening;
          if (aiResButton) aiResButton.innerText = btnText;

          window.lastGeneratedAiFlow = {
            keywords: kwList,
            r1, r2, r3,
            openingDm: opening.replace(/<br>/g, "\n").replace(/<strong>|<\/strong>/g, ""),
            btnText,
            link
          };

          btnGenerateAiFlow.innerText = "✨ Generate Complete Flow with AI";
          btnGenerateAiFlow.disabled = false;
        }, 500);
      });
    }

    const btnPushToBuilder = document.getElementById("btnPushToBuilder");
    const btnApplyAiToWizard = document.getElementById("btnApplyAiToWizard");

    function pushAiToWizard() {
      const data = window.lastGeneratedAiFlow || {
        keywords: "CANVA, PACK, TEMPLATE",
        r1: "Just sent you the templates in DMs! Check requests 😊",
        r2: "Sent! Enjoy the templates 🚀",
        r3: "Check your messages! The link is waiting ✨",
        openingDm: "Hey there! Thanks for stopping by my reel 😊\n\nClick below to get the templates!",
        btnText: "Send me the templates 🎁",
        link: "https://satnamwebservices.com/offer"
      };

      if (wizardKeywordsInput) wizardKeywordsInput.value = data.keywords;
      if (replyVar1) replyVar1.value = data.r1;
      if (replyVar2) replyVar2.value = data.r2;
      if (replyVar3) replyVar3.value = data.r3;
      if (wizardOpeningDmText) wizardOpeningDmText.value = data.openingDm;
      if (wizardButtonTextInput) wizardButtonTextInput.value = data.btnText;
      if (wizardFinalLink) wizardFinalLink.value = data.link;

      openEasyBuilderWizard();
      setWizardStep(2);
    }

    if (btnPushToBuilder) btnPushToBuilder.addEventListener("click", pushAiToWizard);
    if (btnApplyAiToWizard) btnApplyAiToWizard.addEventListener("click", pushAiToWizard);

    const btnCopyAiJson = document.getElementById("btnCopyAiJson");
    if (btnCopyAiJson) {
      btnCopyAiJson.addEventListener("click", () => {
        const textToCopy = `Keywords: ${aiResKeyword ? aiResKeyword.innerText : ""}\n\nOpening DM:\n${aiResOpeningDm ? aiResOpeningDm.innerText : ""}\n\nButton: ${aiResButton ? aiResButton.innerText : ""}`;
        navigator.clipboard.writeText(textToCopy).then(() => {
          alert("📋 AI Flow Copy successfully copied to clipboard!");
        }).catch(() => {
          alert("Copied to clipboard!");
        });
      });
    }

    const btnGenerateHooks = document.getElementById("btnGenerateHooks");
    const aiInputNiche = document.getElementById("aiInputNiche");
    const hooksListWrap = document.getElementById("hooksListWrap");

    if (btnGenerateHooks) {
      btnGenerateHooks.addEventListener("click", () => {
        const niche = (aiInputNiche && aiInputNiche.value.trim()) || "Instagram Growth";
        btnGenerateHooks.innerText = "⚡ Generating Viral Hooks...";
        btnGenerateHooks.disabled = true;

        setTimeout(() => {
          if (hooksListWrap) {
            hooksListWrap.innerHTML = `
              <div class="hook-card">
                <span class="hook-number">01</span>
                <div class="hook-text">
                  <strong>"99% of creators in ${escapeHtml(niche)} fail because of this 1 hidden pitfall..."</strong>
                  <p class="hook-cta">CTA: <em>"Comment <strong>'BLUEPRINT'</strong> and I'll DM you my exact checklist."</em></p>
                </div>
              </div>
              <div class="hook-card">
                <span class="hook-number">02</span>
                <div class="hook-text">
                  <strong>"I spent ₹1,00,000 learning ${escapeHtml(niche)}. Here are the 3 secrets in 30 seconds:"</strong>
                  <p class="hook-cta">CTA: <em>"Comment <strong>'REVEAL'</strong> to receive the full swipe-file in DMs."</em></p>
                </div>
              </div>
              <div class="hook-card">
                <span class="hook-number">03</span>
                <div class="hook-text">
                  <strong>"Stop wasting hours on manual work in ${escapeHtml(niche)}. Try this free method:"</strong>
                  <p class="hook-cta">CTA: <em>"Comment <strong>'AUTOMATE'</strong> and I'll send you the direct tool link."</em></p>
                </div>
              </div>
            `;
          }
          btnGenerateHooks.innerText = "⚡ Generate 3 Viral Hooks";
          btnGenerateHooks.disabled = false;
        }, 400);
      });
    }
  }

  // =========================================================================
  // --- MODALS UI (PROFILE & HELP GUIDES) ---
  // =========================================================================
  function setupModalsUI() {
    const profileModal = document.getElementById("profileModal");
    const btnCloseProfileModal = document.getElementById("btnCloseProfileModal");
    const btnProfileUpgrade = document.getElementById("btnProfileUpgrade");

    const helpModal = document.getElementById("helpModal");
    const btnCloseHelpModal = document.getElementById("btnCloseHelpModal");

    if (btnCloseProfileModal) {
      btnCloseProfileModal.addEventListener("click", () => {
        if (profileModal) profileModal.classList.remove("active");
      });
    }

    if (btnProfileUpgrade) {
      btnProfileUpgrade.addEventListener("click", () => {
        if (profileModal) profileModal.classList.remove("active");
        openUpgradeModal();
      });
    }

    if (btnCloseHelpModal) {
      btnCloseHelpModal.addEventListener("click", () => {
        if (helpModal) helpModal.classList.remove("active");
      });
    }
  }

  function openProfileModal() {
    const profileModal = document.getElementById("profileModal");
    if (profileModal) profileModal.classList.add("active");
  }

  function openHelpModal() {
    const helpModal = document.getElementById("helpModal");
    if (helpModal) helpModal.classList.add("active");
  }

  // --- Broadcast / Outreach UI (Integrated from previous phase) ---
  function setupBroadcastUI() {
    if (typeof varChips !== "undefined" && varChips) {
      varChips.forEach(chip => {
        chip.addEventListener("click", () => insertAtCursor(messageTemplate, chip.getAttribute("data-var")));
      });
    }

    if (btnPreviewSpintax) btnPreviewSpintax.addEventListener("click", openSpintaxModal);
    if (btnCloseSpintaxModal) btnCloseSpintaxModal.addEventListener("click", () => spintaxModal && spintaxModal.classList.remove("active"));
    if (btnAcceptSpintax) btnAcceptSpintax.addEventListener("click", () => spintaxModal && spintaxModal.classList.remove("active"));
    if (btnReRollSpintax) btnReRollSpintax.addEventListener("click", fetchSpintaxPreviews);

    if (tabButtons) {
      tabButtons.forEach(btn => {
        btn.addEventListener("click", () => {
          tabButtons.forEach(b => b.classList.remove("active"));
          tabPanes.forEach(p => p.classList.remove("active"));
          btn.classList.add("active");
          const pane = document.getElementById(btn.getAttribute("data-tab"));
          if (pane) pane.classList.add("active");
        });
      });
    }

    if (btnLoadManualTargets) btnLoadManualTargets.addEventListener("click", loadManualTargets);
    if (csvDropZone && csvFileInput) {
      csvDropZone.addEventListener("click", () => csvFileInput.click());
      csvFileInput.addEventListener("change", handleCsvUpload);
    }

    if (btnClearTargets) btnClearTargets.addEventListener("click", clearTargets);
    if (btnExportCsv) btnExportCsv.addEventListener("click", () => window.location.href = "/api/campaign/export");
    if (btnClearLogs) btnClearLogs.addEventListener("click", () => terminalLogs && (terminalLogs.innerHTML = ""));

    if (btnStartCampaign) btnStartCampaign.addEventListener("click", startCampaign);
    if (btnPauseCampaign) btnPauseCampaign.addEventListener("click", pauseCampaign);
    if (btnResumeCampaign) btnResumeCampaign.addEventListener("click", resumeCampaign);
    if (btnStopCampaign) btnStopCampaign.addEventListener("click", stopCampaign);
  }

  async function refreshCampaignStatus() {
    try {
      const res = await fetch("/api/status");
      const data = await res.json();
      if (!data.success) return;

      const s = data.stats;
      statTotalTargets.innerText = s.total_targets;
      statSent.innerText = s.sent_count;
      statPending.innerText = s.pending_count;
      statQuota.innerText = `${s.sent_today} / ${s.daily_limit}`;

      const pct = Math.min(100, Math.round((s.sent_today / s.daily_limit) * 100));
      statQuotaFill.style.width = `${pct}%`;
      statCampaignState.innerText = s.status;

      updateDeckState(s);
    } catch (err) {}
  }

  function updateDeckState(stats) {
    deckStatusOrb.className = "campaign-status-orb";
    if (stats.status === "RUNNING") {
      deckStatusOrb.classList.add("running");
      deckStatusTitle.innerText = "Campaign Running";
      deckStatusSub.innerText = `Sent ${stats.sent_count} of ${stats.total_targets}`;
      btnStartCampaign.style.display = "none";
      btnPauseCampaign.style.display = "inline-flex";
      btnResumeCampaign.style.display = "none";
      btnStopCampaign.style.display = "inline-flex";
    } else if (stats.status === "PAUSED") {
      deckStatusTitle.innerText = "Campaign Paused";
      deckStatusSub.innerText = "Click Resume to continue";
      btnStartCampaign.style.display = "none";
      btnPauseCampaign.style.display = "none";
      btnResumeCampaign.style.display = "inline-flex";
      btnStopCampaign.style.display = "inline-flex";
    } else {
      deckStatusTitle.innerText = stats.status === "COMPLETED" ? "Outreach Completed" : "Ready to Launch";
      deckStatusSub.innerText = `${stats.pending_count} pending leads`;
      btnStartCampaign.style.display = "inline-flex";
      btnPauseCampaign.style.display = "none";
      btnResumeCampaign.style.display = "none";
      btnStopCampaign.style.display = "none";
    }
  }

  async function loadManualTargets() {
    const text = manualTargetsInput.value.trim();
    if (!text) return alert("Please enter usernames.");
    try {
      const res = await fetch("/api/targets/load-text", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text })
      });
      const data = await res.json();
      if (data.success) {
        manualTargetsInput.value = "";
        await refreshTargetsTable();
        await refreshCampaignStatus();
      }
    } catch (e) { alert("Error: " + e.message); }
  }

  async function handleCsvUpload(e) {
    if (e.target.files && e.target.files.length > 0) {
      const formData = new FormData();
      formData.append("file", e.target.files[0]);
      try {
        const res = await fetch("/api/targets/upload-csv", { method: "POST", body: formData });
        const data = await res.json();
        if (data.success) {
          csvFileInput.value = "";
          await refreshTargetsTable();
          await refreshCampaignStatus();
        }
      } catch (err) { alert("Upload error: " + err.message); }
    }
  }

  async function clearTargets() {
    if (!confirm("Clear leads queue?")) return;
    try {
      await fetch("/api/targets/clear", { method: "POST" });
      await refreshTargetsTable();
      await refreshCampaignStatus();
    } catch (e) {}
  }

  async function refreshTargetsTable() {
    try {
      const res = await fetch("/api/targets");
      const data = await res.json();
      const targets = data.targets || [];
      if (targets.length === 0) {
        targetsTableBody.innerHTML = `<tr class="empty-row"><td colspan="5">No leads in queue.</td></tr>`;
        return;
      }
      targetsTableBody.innerHTML = targets.map(t => `
        <tr>
          <td>${t.id}</td>
          <td><strong>@${escapeHtml(t.username)}</strong></td>
          <td>${escapeHtml(t.name || '-')}</td>
          <td><span class="badge badge-${t.status}">${t.status}</span></td>
          <td><small>${escapeHtml(t.error || t.sent_at || '-')}</small></td>
        </tr>
      `).join("");
    } catch (e) {}
  }

  async function startCampaign() {
    const template = messageTemplate.value.trim();
    if (!template) return alert("Please enter message template.");
    const payload = {
      template: template,
      min_delay: parseInt(minDelayInput.value, 10) || 45,
      max_delay: parseInt(maxDelayInput.value, 10) || 90,
      daily_limit: parseInt(dailyLimitInput.value, 10) || 35,
      headless: headlessModeInput.value === "true"
    };
    try {
      const res = await fetch("/api/campaign/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.success) {
        await refreshCampaignStatus();
        await refreshTargetsTable();
      } else {
        alert(data.detail || "Could not start.");
      }
    } catch (err) { alert("Error: " + err.message); }
  }

  async function pauseCampaign() {
    await fetch("/api/campaign/pause", { method: "POST" });
    await refreshCampaignStatus();
  }
  async function resumeCampaign() {
    await fetch("/api/campaign/resume", { method: "POST" });
    await refreshCampaignStatus();
  }
  async function stopCampaign() {
    if (!confirm("Stop outreach campaign?")) return;
    await fetch("/api/campaign/stop", { method: "POST" });
    await refreshCampaignStatus();
  }

  // --- Spintax Preview ---
  async function openSpintaxModal() {
    spintaxModal.classList.add("active");
    await fetchSpintaxPreviews();
  }

  async function fetchSpintaxPreviews() {
    const template = messageTemplate.value.trim();
    if (!template) {
      spintaxPreviewList.innerHTML = "<p>Enter template first.</p>";
      return;
    }
    spintaxPreviewList.innerHTML = "<p>Generating samples...</p>";
    try {
      const res = await fetch("/api/spintax/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ template })
      });
      const data = await res.json();
      if (data.success && data.previews) {
        spintaxPreviewList.innerHTML = data.previews.map((p, i) => `
          <div class="preview-item"><strong>#${i+1}:</strong> ${escapeHtml(p)}</div>
        `).join("");
      }
    } catch (e) {
      spintaxPreviewList.innerHTML = `<p class="text-danger">${e.message}</p>`;
    }
  }

  // --- SSE Real-time Logs ---
  function setupSSEStream() {
    const eventSource = new EventSource("/api/logs/stream");
    eventSource.onmessage = (event) => {
      try {
        const log = JSON.parse(event.data);
        const line = document.createElement("div");
        line.className = `log-line log-${(log.level || "info").toLowerCase()}`;
        line.innerHTML = `
          <span class="log-time">[${log.time || ""}]</span>
          <span class="log-level">[${log.level || "INFO"}]</span>
          <span class="log-text">${escapeHtml(log.message || "")}</span>
        `;
        terminalLogs.appendChild(line);
        terminalLogs.scrollTop = terminalLogs.scrollHeight;
      } catch (e) {}
    };
    eventSource.onerror = () => setTimeout(setupSSEStream, 5000);
  }

  // =========================================================================
  // --- OFFICIAL META GRAPH API & WEBHOOKS (FACEBOOK DEVELOPER) ---
  // =========================================================================
  const metaAccessToken = document.getElementById("metaAccessToken");
  const metaAppId = document.getElementById("metaAppId");
  const metaVerifyToken = document.getElementById("metaVerifyToken");
  const metaIgAccountId = document.getElementById("metaIgAccountId");
  const btnTestMeta = document.getElementById("btnTestMeta");
  const btnSaveMeta = document.getElementById("btnSaveMeta");
  const metaStatusTitle = document.getElementById("metaStatusTitle");
  const metaStatusSub = document.getElementById("metaStatusSub");
  const metaBadge = document.getElementById("metaBadge");

  async function loadMetaConfig() {
    try {
      const res = await fetch("/api/meta/config");
      const data = await res.json();
      if (!data.success) return;
      const cfg = data.config || {};
      if (metaAppId) metaAppId.value = cfg.app_id || "";
      if (metaVerifyToken) metaVerifyToken.value = cfg.verify_token || "converflow_secret_token_123";
      if (metaIgAccountId) metaIgAccountId.value = cfg.instagram_account_id || "";

      if (cfg.enabled && cfg.connected_account_username) {
        if (metaStatusTitle) metaStatusTitle.innerText = `Meta API Connected: @${cfg.connected_account_username}`;
        if (metaStatusSub) metaStatusSub.innerText = `Connected via Facebook Page (${cfg.connected_account_name || 'Instagram Page'}). 0-second Webhooks Active!`;
        if (metaBadge) {
          metaBadge.innerText = "ONLINE (GRAPH API)";
          metaBadge.style.background = "rgba(16, 185, 129, 0.2)";
          metaBadge.style.color = "#34d399";
        }
        
        // Also update account card in sidebar if not already logged in via browser
        if (accountBadge && accountBadge.classList.contains("not-connected")) {
          accountHandle.innerText = "@" + cfg.connected_account_username;
          accountBadge.innerText = "Meta API Active";
          accountBadge.className = "account-badge connected";
        }
      } else {
        if (metaStatusTitle) metaStatusTitle.innerText = "Meta API Status: Disconnected";
        if (metaStatusSub) metaStatusSub.innerText = "Enter your Facebook Page Access Token to connect your Instagram account.";
        if (metaBadge) {
          metaBadge.innerText = "OFFLINE";
          metaBadge.style.background = "rgba(148, 163, 184, 0.2)";
          metaBadge.style.color = "#94a3b8";
        }
      }
    } catch (e) {
      console.error("Error loading Meta config:", e);
    }
  }

  function setupMetaUI() {
    if (btnSaveMeta) {
      btnSaveMeta.addEventListener("click", async () => {
        const payload = {
          access_token: metaAccessToken.value.trim(),
          app_id: metaAppId.value.trim(),
          verify_token: metaVerifyToken.value.trim()
        };
        try {
          const res = await fetch("/api/meta/save", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
          });
          const data = await res.json();
          if (data.success) {
            alert("✅ Facebook Developer / Meta settings saved successfully!");
            await loadMetaConfig();
          }
        } catch (err) {
          alert("Error saving Meta settings: " + err.message);
        }
      });
    }

    if (btnTestMeta) {
      btnTestMeta.addEventListener("click", async () => {
        const token = metaAccessToken.value.trim();
        if (!token) {
          alert("Please paste your Meta Access Token (starts with EAA...) first!");
          metaAccessToken.focus();
          return;
        }

        btnTestMeta.innerText = "Connecting to Meta Graph API...";
        btnTestMeta.disabled = true;

        try {
          const res = await fetch("/api/meta/test", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ access_token: token })
          });
          const data = await res.json();
          if (data.success) {
            alert("🎉 Meta Graph API Connected! " + data.message);
            await loadMetaConfig();
            if (typeof loadWizardPosts === "function") loadWizardPosts();
          } else {
            alert("❌ Connection Failed:\n" + (data.error || data.message));
          }
        } catch (err) {
          alert("Error testing Meta token: " + err.message);
        } finally {
          btnTestMeta.innerText = "⚡ Test & Connect Meta Account";
          btnTestMeta.disabled = false;
        }
      });
    }
  }

  // =========================================================================
  // --- CONVERFLOW EASY BUILDER WIZARD & SUBSCRIPTION SYSTEM ---
  // =========================================================================

  // Elements
  const trialBanner = document.getElementById("trialBanner");
  const trialPlanTitle = document.getElementById("trialPlanTitle");
  const trialPlanSub = document.getElementById("trialPlanSub");
  const trialDaysCount = document.getElementById("trialDaysCount");
  const maxAllowedReelsText = document.getElementById("maxAllowedReelsText");
  const btnOpenUpgrade = document.getElementById("btnOpenUpgrade");
  const upgradeModal = document.getElementById("upgradeModal");
  const btnCloseUpgradeModal = document.getElementById("btnCloseUpgradeModal");
  const btnConfirmUpgrade = document.getElementById("btnConfirmUpgrade");

  // Popular First Moves
  const btnStartCgt = document.getElementById("btnStartCgt");
  const btnStartDmFlow = document.getElementById("btnStartDmFlow");

  // Wizard Elements
  const easyBuilderWizardModal = document.getElementById("easyBuilderWizardModal");
  const btnSkipWizard = document.getElementById("btnSkipWizard");
  const wizardStepTitle = document.getElementById("wizardStepTitle");
  const wizardStepSubtitle = document.getElementById("wizardStepSubtitle");
  const progSteps = [
    document.getElementById("progStep1"),
    document.getElementById("progStep2"),
    document.getElementById("progStep3"),
    document.getElementById("progStep4")
  ];
  const stepPanes = [
    document.getElementById("stepPane1"),
    document.getElementById("stepPane2"),
    document.getElementById("stepPane3"),
    document.getElementById("stepPane4")
  ];

  // Wizard Step 1: Posts
  const wizardPostsGrid = document.getElementById("wizardPostsGrid");
  const radioAnyPost = document.getElementById("radioAnyPost");
  const radioNextPost = document.getElementById("radioNextPost");
  const btnStep1Next = document.getElementById("btnStep1Next");

  // Wizard Step 2: Keywords & Comments
  const kwTypeSpecific = document.getElementById("kwTypeSpecific");
  const kwTypeAny = document.getElementById("kwTypeAny");
  const kwInputBox = document.getElementById("kwInputBox");
  const wizardKeywordsInput = document.getElementById("wizardKeywordsInput");
  const toggleCommentReplies = document.getElementById("toggleCommentReplies");
  const commentReplyInputs = document.getElementById("commentReplyInputs");
  const replyVar1 = document.getElementById("replyVar1");
  const replyVar2 = document.getElementById("replyVar2");
  const replyVar3 = document.getElementById("replyVar3");
  const btnStep2Back = document.getElementById("btnStep2Back");
  const btnStep2Next = document.getElementById("btnStep2Next");

  // Wizard Step 3: Opening DM
  const wizardOpeningDmText = document.getElementById("wizardOpeningDmText");
  const wizardButtonTextInput = document.getElementById("wizardButtonTextInput");
  const triggerUpgradePrompts = document.querySelectorAll(".trigger-upgrade-prompt");
  const btnStep3Back = document.getElementById("btnStep3Back");
  const btnStep3Next = document.getElementById("btnStep3Next");

  // Wizard Step 4: Final Link & Publish
  const wizardFlowName = document.getElementById("wizardFlowName");
  const wizardFinalLink = document.getElementById("wizardFinalLink");
  const wizardTags = document.getElementById("wizardTags");
  const btnStep4Back = document.getElementById("btnStep4Back");
  const btnPublishAutomation = document.getElementById("btnPublishAutomation");

  // Phone Mockup Dynamic Elements
  const phoneStatePost = document.getElementById("phoneStatePost");
  const phoneStateComments = document.getElementById("phoneStateComments");
  const phoneStateDm = document.getElementById("phoneStateDm");
  const phonePostImage = document.getElementById("phonePostImage");
  const phoneMiniImage = document.getElementById("phoneMiniImage");
  const phoneCaptionText = document.getElementById("phoneCaptionText");
  const phoneLiveCommentReply = document.getElementById("phoneLiveCommentReply");
  const phoneLiveOpeningDm = document.getElementById("phoneLiveOpeningDm");
  const phoneLiveButton = document.getElementById("phoneLiveButton");
  const phoneLiveUserClick = document.getElementById("phoneLiveUserClick");
  const phoneLiveLinkCard = document.getElementById("phoneLiveLinkCard");

  // Wizard State
  let wizardCurrentStep = 1;
  let wizardPosts = [];
  let selectedWizardPost = null;
  let currentBillingState = null;

  const wizardTitles = {
    1: { title: "First, pick a post", sub: "Build your automation ...and see it come to life" },
    2: { title: "Now, set a keyword", sub: "Decide which comments trigger the automated reply & DM" },
    3: { title: "Tweak the Opening DM", sub: "Ask first! It's polite and opens messaging beyond the first reply." },
    4: { title: "Final Step: Destination Link", sub: "Where should followers go when they click your button?" }
  };

  function setupWizardAndBilling() {
    // Top upgrade button
    if (btnOpenUpgrade) btnOpenUpgrade.addEventListener("click", () => openUpgradeModal());
    if (btnCloseUpgradeModal) btnCloseUpgradeModal.addEventListener("click", () => upgradeModal.classList.remove("active"));
    if (btnConfirmUpgrade) btnConfirmUpgrade.addEventListener("click", handleUpgradeToPro);

    // Locked upgrade triggers
    [radioAnyPost, radioNextPost].forEach(el => {
      if (el) el.addEventListener("click", (e) => {
        e.preventDefault();
        openUpgradeModal("The 'Any post or reel' trigger is unlocked exclusively on ConverFlow Pro (₹299/mo)!");
      });
    });

    triggerUpgradePrompts.forEach(p => {
      const parent = p.closest(".upgrade-toggle-item");
      if (parent) {
        parent.addEventListener("click", () => {
          openUpgradeModal("Follow-to-Unlock gate & Email capture are Pro features (₹299/mo)!");
        });
      }
    });

    // First moves
    if (btnStartCgt) btnStartCgt.addEventListener("click", openEasyBuilderWizard);
    if (btnStartDmFlow) {
      btnStartDmFlow.addEventListener("click", () => {
        switchView("view-simulator");
      });
    }

    // Wizard Skip / Close
    if (btnSkipWizard) btnSkipWizard.addEventListener("click", closeEasyBuilderWizard);

    // Wizard Mobile Toggle (Edit Step vs Live Preview)
    const wizMobileBtns = document.querySelectorAll(".wiz-mobile-btn");
    const wizardFormCol = document.querySelector(".wizard-form-column, .wizard-form-col");
    const wizardPhoneCol = document.querySelector(".wizard-preview-column, .wizard-phone-col");

    wizMobileBtns.forEach(btn => {
      btn.addEventListener("click", () => {
        wizMobileBtns.forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        const target = btn.getAttribute("data-target");
        if (target === "preview") {
          if (wizardFormCol) wizardFormCol.style.display = "none";
          if (wizardPhoneCol) wizardPhoneCol.style.display = "flex";
        } else {
          if (wizardFormCol) wizardFormCol.style.display = "block";
          if (wizardPhoneCol) wizardPhoneCol.style.display = "none";
        }
      });
    });

    // Wizard Step 1: Posts
    if (btnStep1Next) btnStep1Next.addEventListener("click", () => setWizardStep(2));

    // Wizard Step 2: Keywords
    if (kwTypeSpecific) {
      kwTypeSpecific.addEventListener("change", () => {
        if (kwInputBox) kwInputBox.style.display = "block";
        updateLiveCommentPhone();
      });
    }
    if (kwTypeAny) {
      kwTypeAny.addEventListener("change", () => {
        if (kwInputBox) kwInputBox.style.display = "none";
        updateLiveCommentPhone();
      });
    }
    if (toggleCommentReplies) {
      toggleCommentReplies.addEventListener("change", () => {
        if (commentReplyInputs) commentReplyInputs.style.display = toggleCommentReplies.checked ? "flex" : "none";
        updateLiveCommentPhone();
      });
    }
    [replyVar1, replyVar2, replyVar3].forEach(input => {
      if (input) input.addEventListener("input", updateLiveCommentPhone);
    });
    if (btnStep2Back) btnStep2Back.addEventListener("click", () => setWizardStep(1));
    if (btnStep2Next) btnStep2Next.addEventListener("click", () => setWizardStep(3));

    // Wizard Step 3: Opening DM & Button
    if (wizardOpeningDmText) wizardOpeningDmText.addEventListener("input", updateLiveDmPhone);
    if (wizardButtonTextInput) wizardButtonTextInput.addEventListener("input", updateLiveDmPhone);
    if (btnStep3Back) btnStep3Back.addEventListener("click", () => setWizardStep(2));
    if (btnStep3Next) btnStep3Next.addEventListener("click", () => setWizardStep(4));

    // Wizard Step 4: Final Publish
    if (btnStep4Back) btnStep4Back.addEventListener("click", () => setWizardStep(3));
    if (btnPublishAutomation) btnPublishAutomation.addEventListener("click", handlePublishWizard);

    // Override existing "New Automation" button to open the ConverFlow wizard!
    if (btnNewAutomation) {
      btnNewAutomation.addEventListener("click", (e) => {
        e.preventDefault();
        openEasyBuilderWizard();
      });
    }
  }

  async function refreshBillingStatus() {
    try {
      const res = await fetch("/api/billing/status");
      const data = await res.json();
      if (!data.success) return;
      currentBillingState = data.billing;

      const sidebarLimitCount = document.getElementById("sidebarLimitCount");
      if (sidebarLimitCount) {
        sidebarLimitCount.innerText = `${currentBillingState.active_reels_count}/${currentBillingState.max_active_reels}`;
      }

      if (currentBillingState.is_pro) {
        if (trialPlanTitle) trialPlanTitle.innerText = "💎 ConverFlow Pro Active";
        if (trialPlanSub) trialPlanSub.innerText = "Unlimited Reels, Any Post trigger, and Advanced features unlocked!";
        if (btnOpenUpgrade) btnOpenUpgrade.style.display = "none";
        if (trialBanner) {
          trialBanner.style.background = "linear-gradient(90deg, rgba(0, 132, 255, 0.18), rgba(168, 85, 247, 0.18))";
          trialBanner.style.borderColor = "rgba(0, 132, 255, 0.4)";
        }
        if (maxAllowedReelsText) maxAllowedReelsText.innerText = "∞";
      } else {
        if (trialDaysCount) trialDaysCount.innerText = currentBillingState.days_left;
        if (maxAllowedReelsText) maxAllowedReelsText.innerText = "1";
        if (btnOpenUpgrade) btnOpenUpgrade.style.display = "inline-flex";
      }
    } catch (e) {
      console.error(e);
    }
  }

  function openUpgradeModal(customMsg = "") {
    if (customMsg) {
      const sub = upgradeModal.querySelector(".pricing-subtitle");
      if (sub) sub.innerText = customMsg;
    }
    upgradeModal.classList.add("active");
  }

  async function handleUpgradeToPro() {
    try {
      const res = await fetch("/api/billing/upgrade", { method: "POST" });
      const data = await res.json();
      if (data.success) {
        upgradeModal.classList.remove("active");
        alert("🎉 Congratulations! ConverFlow Pro (₹299/mo) is now active on your account! Unlimited Reels are unlocked.");
        await refreshBillingStatus();
        await loadAutomations();
      }
    } catch (e) {
      alert("Upgrade failed: " + e.message);
    }
  }

  async function openEasyBuilderWizard() {
    easyBuilderWizardModal.classList.add("active");
    setWizardStep(1);
    await loadWizardPosts();
  }

  function closeEasyBuilderWizard() {
    easyBuilderWizardModal.classList.remove("active");
  }

  async function loadWizardPosts() {
    try {
      const res = await fetch("/api/instagram/posts");
      const data = await res.json();
      wizardPosts = data.posts || [];

      if (wizardPosts.length > 0) {
        selectedWizardPost = wizardPosts[0];
        renderWizardPostsGrid();
        updatePhoneWithPost(selectedWizardPost);
      }
    } catch (e) {
      console.error(e);
    }
  }

  function renderWizardPostsGrid() {
    wizardPostsGrid.innerHTML = wizardPosts.map((post, idx) => `
      <div class="post-thumb-card ${selectedWizardPost && selectedWizardPost.id === post.id ? 'selected' : ''}" 
           onclick="window.selectWizardPost('${post.id}')">
        <img src="${escapeHtml(post.thumbnail)}" alt="Thumb">
        <span class="post-thumb-badge">${post.type.toUpperCase()}</span>
      </div>
    `).join("");
  }

  window.selectWizardPost = (postId) => {
    const found = wizardPosts.find(p => p.id === postId);
    if (found) {
      selectedWizardPost = found;
      renderWizardPostsGrid();
      updatePhoneWithPost(found);
    }
  };

  function updatePhoneWithPost(post) {
    if (!post) return;
    phonePostImage.src = post.thumbnail;
    phoneMiniImage.src = post.thumbnail;
    phoneCaptionText.innerText = post.caption.slice(0, 75) + "...";
  }

  function setWizardStep(stepNum) {
    wizardCurrentStep = stepNum;

    // Progress bar
    progSteps.forEach((s, idx) => {
      s.classList.toggle("active", idx < stepNum);
    });

    // Form panes
    stepPanes.forEach((p, idx) => {
      p.classList.toggle("active", idx === (stepNum - 1));
    });

    // Titles
    if (wizardTitles[stepNum]) {
      wizardStepTitle.innerText = wizardTitles[stepNum].title;
      wizardStepSubtitle.innerText = wizardTitles[stepNum].sub;
    }

    // Phone state transitions matching ConverFlow screenshots
    phoneStatePost.classList.remove("active");
    phoneStateComments.classList.remove("active");
    phoneStateDm.classList.remove("active");

    if (stepNum === 1) {
      phoneStatePost.classList.add("active");
    } else if (stepNum === 2) {
      phoneStateComments.classList.add("active");
      updateLiveCommentPhone();
    } else if (stepNum === 3 || stepNum === 4) {
      phoneStateDm.classList.add("active");
      updateLiveDmPhone();
    }
  }

  function updateLiveCommentPhone() {
    const val = replyVar1.value.trim() || "Thanks! Please see DMs.";
    phoneLiveCommentReply.innerText = val;
  }

  function updateLiveDmPhone() {
    const dmText = wizardOpeningDmText.value.trim() || "Hey there! I'm so happy you're here...";
    const btnText = wizardButtonTextInput.value.trim() || "Send me the link";
    phoneLiveOpeningDm.innerHTML = escapeHtml(dmText).replace(/\n/g, "<br>");
    phoneLiveButton.innerText = btnText;
    phoneLiveUserClick.innerText = btnText;
  }

  async function handlePublishWizard() {
    const name = wizardFlowName.value.trim() || "Reel Link Delivery Flow";
    const postUrl = selectedWizardPost ? selectedWizardPost.url : "https://instagram.com/reel/current";
    const postThumb = selectedWizardPost ? selectedWizardPost.thumbnail : "";
    const postCap = selectedWizardPost ? selectedWizardPost.caption : "";
    const isSpecificKw = kwTypeSpecific.checked;
    const keywords = isSpecificKw ? wizardKeywordsInput.value.split(",").map(k => k.trim()).filter(Boolean) : ["*"];
    const replies = [replyVar1.value.trim(), replyVar2.value.trim(), replyVar3.value.trim()].filter(Boolean);
    const openingDm = wizardOpeningDmText.value.trim();
    const btnText = wizardButtonTextInput.value.trim();
    const destLink = wizardFinalLink.value.trim();
    const tags = wizardTags.value.split(",").map(t => t.trim()).filter(Boolean);

    const payload = {
      name: name,
      post_target: postUrl,
      post_thumbnail: postThumb,
      post_caption: postCap,
      trigger_scope: isSpecificKw ? "specific" : "any",
      trigger_keywords: keywords,
      reply_to_comment: toggleCommentReplies.checked,
      comment_replies: replies,
      opening_dm: openingDm,
      button_text: btnText,
      delivery_link: destLink,
      tags: tags
    };

    try {
      const res = await fetch("/api/wizard/publish", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();

      if (data.upgrade_required) {
        openUpgradeModal(data.message || "Free Trial allows only 1 active Reel automation. Upgrade to ConverFlow Pro (₹299/mo) for unlimited Reels!");
      } else if (data.success) {
        closeEasyBuilderWizard();
        alert("🎉 Success! Your ConverFlow Reel Automation is published and LIVE!");
        switchView("view-automations");
        await loadAutomations();
        await refreshBillingStatus();
      } else {
        alert("Error publishing: " + (data.detail || "Unknown error"));
      }
    } catch (e) {
      alert("Error contacting server: " + e.message);
    }
  }

  // --- Initialize All Subsystems ---
  setupMetaUI();
  loadMetaConfig();
  setupWizardAndBilling();
  refreshBillingStatus();

  // Boot
  init();
});

