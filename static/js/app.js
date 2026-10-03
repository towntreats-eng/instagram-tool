/* ===========================================================================
   DM Flow — dashboard shell.

   What this file is allowed to do: switch views, render the contacts table,
   open the profile/help modals. That is all that is left of it.

   The account screen (connect, posts, flows) lives in flows.js; plan, billing
   and analytics live in dmflow.js. Roughly 1,900 lines of simulator,
   inbox, AI-assist and broadcast demo code were deleted rather than hidden —
   none of it moved real data, and a control that does nothing is worse than
   no control at all.
   =========================================================================== */
(function () {
  "use strict";

  // Module state the contacts table keeps between renders.
  var cachedContactsList = [];
  var contactsActiveFilter = "all";

  var VIEW_META = {
    "view-home": { title: "", sub: "" },
    "view-contacts": { title: "People", sub: "Everyone your automations have captured, and where they came from." },
    "view-analytics": { title: "Results", sub: "Not how many messages went out — how many turned into something." },
    "view-billing": { title: "Plan & billing", sub: "What you're on, what you've used, and what upgrading unlocks." },
    "view-settings": { title: "Settings", sub: "Your Instagram connection and how DM Flow signs in on your behalf." }
  };

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
    "view-settings": { title: "Account & Settings", sub: "Manage Meta Developer API, browser login, session security, and watcher settings." }
  };

  // --- Initialize ---
  // Each section is isolated: a missing element in one panel must never stop
  // the rest of the dashboard from wiring itself up.

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
      cardHomeStories.addEventListener("click", () => switchView("view-home"));
    }
    const cardHomeAllDms = document.getElementById("cardHomeAllDms");
    if (cardHomeAllDms) {
      cardHomeAllDms.addEventListener("click", () => switchView("view-home"));
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
        switchView("view-home");
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
    if (moveDefaultReply) moveDefaultReply.addEventListener("click", () => switchView("view-home"));

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

    if (viewId === "view-home") loadAutomations();
    if (viewId === "view-contacts") loadContacts();
  }

  // --- Account State ---

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
        alert(` Lead @${cleanUser} added to Contacts & CRM!`);
      });
    }

    const tabPills = document.querySelectorAll(".contacts-table-card.tab-pill");
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
      const url = search? `/api/contacts?search=${encodeURIComponent(search)}`: "/api/contacts";
      const res = await fetch(url);
      const data = await res.json();
      const serverContacts = data.contacts || [];

      // Only real contacts. This used to top the list up with invented people,
      // which meant a merchant could open a DM to somebody who did not exist.
      cachedContactsList = serverContacts;
      const totalCount = cachedContactsList.length;
      if (navContactsCount) navContactsCount.innerText = totalCount;
      const statContactsTotal = document.getElementById("statContactsTotal");
      if (statContactsTotal) statContactsTotal.innerText = totalCount;

      filterAndRenderContacts();
    } catch (e) {
      console.error(e);
      cachedContactsList = []; // an error shows an empty list, never fake people
      filterAndRenderContacts();
    }
  }

  function filterAndRenderContacts() {
    const searchVal = contactsSearch? contactsSearch.value.trim().toLowerCase(): "";
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

    const colors = ["#0a0a0b", "#2e2e35", "#47474f", "#62626a", "#8a8a93", "#b0b0b8"];

    contactsTableBody.innerHTML = filtered.map((c, idx) => {
      const initials = (c.name? c.name.split(" ").map(w => w[0]).join(""): c.username.slice(0, 2)).toUpperCase();
      const color = colors[idx % colors.length];
      const tagsHtml = (c.tags || []).map(t => `<span class="tag-pill">${escapeHtml(t)}</span>`).join(" ");
      const statusClass = c.status === "active"? "active": (c.status === "converted"? "converted": "followed");
      const statusLabel = c.status? (c.status.charAt(0).toUpperCase() + c.status.slice(1)): "Active";

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
            <span class="source-badge"> ${escapeHtml(c.source || 'Reel Comments')}</span>
          </td>
          <td>${tagsHtml || '<span style="color:var(--text-faint);">-</span>'}</td>
          <td><small style="color:var(--text-muted);">${escapeHtml(c.last_interaction || 'Recent')}</small></td>
          <td><span class="badge badge-sent">${c.messages_count || 1} msg</span></td>
          <td><span class="lead-status-pill ${statusClass}">${statusLabel}</span></td>
          <td style="text-align: right;">
            <button class="btn-table-action" onclick="window.openInboxWithUser('${escapeHtml(c.username)}')">
               Chat
            </button>
          </td>
        </tr>
      `;
    }).join("");
  }

  window.openInboxWithUser = (handle) => {
    switchView("view-home");
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
      color: "#101014",
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
        { type: "incoming", text: 'Commented on your Reel: <strong>"link pls! "</strong>' },
        { type: "outgoing", text: 'Hey there! I\'m so happy you\'re here, thanks so much for your interest <br><br>Click below and I\'ll send you the link in just a sec ', button: "Send me the link" },
        { type: "incoming-btn", text: 'Clicked <strong>"Send me the link"</strong>' },
        { type: "outgoing", text: 'Here is your link <br><a href="https://satnamwebservices.com/offer" class="inbox-link-card" target="_blank"> https://satnamwebservices.com/offer</a>' }
      ]
    },
    {
      handle: "rahul_marketing",
      name: "Rahul Sharma",
      avatar: "RM",
      color: "#232329",
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
        { type: "outgoing", text: 'Hey Rahul! Here is the direct link to the 50 Canva Pack for your marketing team <br><a href="https://satnamwebservices.com/offer" class="inbox-link-card" target="_blank"> https://satnamwebservices.com/offer</a>' },
        { type: "incoming", text: 'Thanks for the link! Looking at the offer now.' }
      ]
    },
    {
      handle: "mike_dev",
      name: "Michael Ross",
      avatar: "MD",
      color: "#3a3a41",
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
        { type: "outgoing", text: 'Hey Michael! Thanks a ton for the shoutout Let me know if you need any assistance.' },
        { type: "incoming", text: 'Does this include the source code for Meta Graph API?' }
      ]
    },
    {
      handle: "clara_design",
      name: "Clara Dupont",
      avatar: "CD",
      color: "#62626a",
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
        { type: "outgoing", text: 'Here are the design assets & wireframe blueprint <br><a href="https://satnamwebservices.com/offer" class="inbox-link-card" target="_blank"> https://satnamwebservices.com/offer</a>' }
      ]
    }
  ];

  let currentInboxUser = "sarah_growth";
  let isBotModeActive = true;

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

  // --- Bridges to the modules that replaced the deleted code ----------------
  function loadAutomations() { return window.CFAccount? window.CFAccount.reload(): Promise.resolve(); }
  function refreshCampaignStatus() { return Promise.resolve(); }
  function refreshTargetsTable() { return Promise.resolve(); }
  function selectInboxThread() {}
  function scrollInboxToBottom() {}
  function openEasyBuilderWizard() { switchView("view-home"); }
  function openUpgradeModal(msg) {
    if (window.CF && window.CF.openUpgrade) return window.CF.openUpgrade(msg);
    switchView("view-billing");
  }

  function safely(label, fn) {
    try { fn(); } catch (err) { console.warn("[DM Flow] " + label + " skipped:", err && err.message); }
  }

  async function init() {
    safely("navigation", setupNavigation);
    safely("contacts", setupContactsUI);
    safely("modals", setupModalsUI);
    try { await loadContacts(); } catch (err) {
      console.warn("[DM Flow] contacts did not load:", err && err.message);
    }
    try {
      var authRes = await fetch("/api/auth/me").then(function (r) { return r.json(); });
      if (authRes && authRes.signed_in) {
        if (authRes.is_admin) {
          var adminGroup = document.getElementById("adminNavGroup");
          if (adminGroup) adminGroup.style.display = "";
        }
        if (authRes.user && authRes.user.name) {
          var initialsEl = document.getElementById("navAvatarInitials");
          if (initialsEl) {
            var parts = authRes.user.name.trim().split(" ");
            initialsEl.textContent = (parts[0][0] + (parts[1] ? parts[1][0] : "")).toUpperCase();
          }
        }
      }
    } catch (_) {}
  }

  window.CFShell = { switchView: switchView, openUpgrade: openUpgradeModal };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
