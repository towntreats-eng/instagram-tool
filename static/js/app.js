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
    "view-settings": { title: "Settings", sub: "Your Instagram connection and how DM Flow signs in on your behalf." },
    "view-profile": { title: "Profile & Account", sub: "Manage your personal profile, connected Instagram account, security, and session." }
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
    document.querySelectorAll("[data-view]").forEach(item => {
      item.addEventListener("click", (e) => {
        const targetViewId = item.getAttribute("data-view");
        if (targetViewId) {
          e.preventDefault();
          switchView(targetViewId);
          const am = document.getElementById("accountDropdownMenu");
          if (am) am.hidden = true;
        }
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
        switchView("view-profile");
      });
    }

    const navItemProfile = document.getElementById("navItemProfile");
    if (navItemProfile) {
      navItemProfile.addEventListener("click", (e) => {
        e.preventDefault();
        switchView("view-profile");
      });
    }

    const btnSidebarLogout = document.getElementById("btnSidebarLogout");
    if (btnSidebarLogout) {
      btnSidebarLogout.addEventListener("click", (e) => {
        e.preventDefault();
        performLogout();
      });
    }

    // Top Account Selector & Dropdown
    const accountBox = document.getElementById("accountSelectorBox");
    const accountMenu = document.getElementById("accountDropdownMenu");
    if (accountBox && accountMenu) {
      accountBox.addEventListener("click", (e) => {
        e.stopPropagation();
        accountMenu.hidden = !accountMenu.hidden;
      });
      document.addEventListener("click", (e) => {
        if (!e.target.closest(".account-selector-wrapper")) {
          accountMenu.hidden = true;
        }
      });
    }
    const btnDropdownLogout = document.getElementById("btnDropdownLogout");
    if (btnDropdownLogout) {
      btnDropdownLogout.addEventListener("click", (e) => {
        e.preventDefault();
        performLogout();
      });
    }

    // Profile page action buttons
    const btnProfileTopLogout = document.getElementById("btnProfileTopLogout");
    if (btnProfileTopLogout) btnProfileTopLogout.addEventListener("click", performLogout);

    const btnProfileLogoutMain = document.getElementById("btnProfileLogoutMain");
    if (btnProfileLogoutMain) btnProfileLogoutMain.addEventListener("click", performLogout);

    const btnProfileDisconnectIg = document.getElementById("btnProfileDisconnectIg");
    if (btnProfileDisconnectIg) btnProfileDisconnectIg.addEventListener("click", performDisconnectIg);

    const btnProfileRefresh = document.getElementById("btnProfileRefresh");
    if (btnProfileRefresh) btnProfileRefresh.addEventListener("click", loadProfile);

    const formUserProfile = document.getElementById("formUserProfile");
    if (formUserProfile) formUserProfile.addEventListener("submit", handleProfileSave);

    const linkHelp = document.getElementById("linkHelp");
    if (linkHelp) {
      linkHelp.addEventListener("click", (e) => {
        e.preventDefault();
        openHelpModal();
      });
    }

    const linkFooterHelp = document.getElementById("linkFooterHelp");
    if (linkFooterHelp) {
      linkFooterHelp.addEventListener("click", (e) => {
        e.preventDefault();
        openHelpModal();
      });
    }

    if (btnSidebarLogin) btnSidebarLogin.addEventListener("click", triggerOpenLogin);
    if (btnSettingsLogin) btnSettingsLogin.addEventListener("click", triggerOpenLogin);
    if (btnSettingsRefresh) btnSettingsRefresh.addEventListener("click", refreshAccountStatus);

    if (btnToggleWatcher) btnToggleWatcher.addEventListener("click", toggleWatcher);
  }

  function getAllViewElements() {
    return document.querySelectorAll(".content-view, .view-section, [id^='view-']");
  }

  function switchView(viewId) {
    if (!viewId) return;
    if (!viewId.startsWith("view-")) viewId = "view-" + viewId.replace(/^#/, "");

    // Top progress bar pulse
    const prg = document.getElementById("pageTopProgress");
    if (prg) {
      prg.style.opacity = "1";
      prg.style.width = "40%";
      setTimeout(() => { if (prg) prg.style.width = "100%"; }, 60);
      setTimeout(() => { if (prg) { prg.style.opacity = "0"; prg.style.width = "0%"; } }, 320);
    }

    const targetHash = "#" + viewId.replace("view-", "");

    // Toggle active on all navigation items
    document.querySelectorAll(".nav-item, .sidebar-footer-link").forEach(n => {
      const match = n.getAttribute("data-view") === viewId || n.getAttribute("href") === targetHash;
      n.classList.toggle("active", Boolean(match));
    });

    document.querySelectorAll(".mobile-nav-item").forEach(m => {
      const match = m.getAttribute("data-view") === viewId || m.getAttribute("href") === targetHash;
      m.classList.toggle("active", Boolean(match));
    });

    // Toggle visibility on all view containers
    const allViews = getAllViewElements();
    allViews.forEach(v => {
      const isTarget = v.id === viewId;
      v.classList.toggle("active", isTarget);
    });

    // Update document title and header if configured
    if (VIEW_META[viewId]) {
      if (viewTitle) viewTitle.innerText = VIEW_META[viewId].title;
      if (viewSubtitle) viewSubtitle.innerText = VIEW_META[viewId].sub;
    }

    // Keep URL hash updated
    if (window.location.hash !== targetHash) {
      history.replaceState(null, "", targetHash);
    }

    // Reset window scroll
    window.scrollTo({ top: 0, behavior: "instant" });

    // Close account dropdown
    const menu = document.getElementById("accountDropdownMenu");
    if (menu) menu.hidden = true;

    // View-specific data fetching
    if (viewId === "view-home") {
      loadAutomations();
    } else if (viewId === "view-contacts") {
      loadContacts();
    } else if (viewId === "view-profile") {
      loadProfile();
    } else if (viewId === "view-analytics" || viewId === "view-billing" || viewId === "view-settings") {
      if (window.CFRender && window.CFRender[viewId]) {
        try { window.CFRender[viewId](); } catch (e) { console.error(e); }
      }
    }
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
      btnAddLeadQuick.addEventListener("click", async () => {
        const username = prompt("Enter Instagram handle for new contact (e.g. your_customer):");
        if (!username) return;
        const cleanUser = username.replace("@", "").trim();
        if (!cleanUser) return;
        try {
          const res = await fetch("/api/contacts", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              username: cleanUser,
              name: cleanUser.replace(/_/g, " "),
              source: "Manual Capture",
              tags: ["New Lead", "Manual"]
            })
          }).then(r => r.json());
          if (res.success) {
            await loadContacts();
            alert(`Contact @${cleanUser} saved to CRM!`);
          } else {
            alert(res.error || "Could not save contact");
          }
        } catch (_) {
          alert("Network error saving contact");
        }
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

      cachedContactsList = serverContacts;
      const totalCount = cachedContactsList.length;
      if (navContactsCount) navContactsCount.innerText = totalCount;
      const statContactsTotal = document.getElementById("statContactsTotal");
      if (statContactsTotal) statContactsTotal.innerText = totalCount;

      // Real KPI calculations from genuine captured leads
      const activeLeads = cachedContactsList.filter(c => c.status === "active" || c.status === "converted" || (c.tags && c.tags.some(t => t.toLowerCase().includes("lead")))).length;
      const statContactsActive = document.getElementById("statContactsActive");
      if (statContactsActive) statContactsActive.innerText = activeLeads;

      const todayStr = new Date().toISOString().slice(0, 10);
      const newToday = cachedContactsList.filter(c => (c.last_interaction || "").startsWith(todayStr) || (c.first_seen || "").startsWith(todayStr)).length;
      const statContactsToday = document.getElementById("statContactsToday");
      if (statContactsToday) statContactsToday.innerText = newToday;

      const clickedOffers = cachedContactsList.filter(c => (c.tags || []).some(t => /link|click|offer|order|convert/i.test(t))).length;
      const ctrPct = totalCount > 0 ? ((clickedOffers / totalCount) * 100).toFixed(1) + "%" : "0.0%";
      const statContactsCtr = document.getElementById("statContactsCtr");
      if (statContactsCtr) statContactsCtr.innerText = ctrPct;

      // Dynamic tab counters
      const reelCount = cachedContactsList.filter(c => (c.source || "").toLowerCase().includes("reel")).length;
      const storyCount = cachedContactsList.filter(c => (c.source || "").toLowerCase().includes("story")).length;
      const dmCount = cachedContactsList.filter(c => (c.source || "").toLowerCase().includes("dm") || (c.source || "").toLowerCase().includes("direct")).length;

      const tabFilterAll = document.getElementById("tabFilterAll");
      if (tabFilterAll) tabFilterAll.innerText = `All Contacts (${totalCount})`;
      const tabFilterReel = document.getElementById("tabFilterReel");
      if (tabFilterReel) tabFilterReel.innerText = `Reel Leads (${reelCount})`;
      const tabFilterStory = document.getElementById("tabFilterStory");
      if (tabFilterStory) tabFilterStory.innerText = `Story Mentions (${storyCount})`;
      const tabFilterDm = document.getElementById("tabFilterDm");
      if (tabFilterDm) tabFilterDm.innerText = `Direct DMs (${dmCount})`;

      filterAndRenderContacts();
    } catch (e) {
      console.error(e);
      cachedContactsList = [];
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
          <td colspan="7" style="text-align: center; color: var(--text-muted); padding: 48px 24px;">
            <div style="max-width: 440px; margin: 0 auto;">
              <div style="width: 48px; height: 48px; border-radius: 50%; background: var(--ink-050); border: 1px solid var(--ink-200); display: flex; align-items: center; justify-content: center; margin: 0 auto 12px; color: var(--ink-600);">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
              </div>
              <h4 style="margin: 0 0 6px 0; font-size: 15px; font-weight: 700; color: var(--ink-950);">No Contacts Captured Yet</h4>
              <p style="margin: 0; font-size: 13px; color: var(--text-muted); line-height: 1.5;">When users comment on your connected Instagram account posts with matching keywords, DM Flow automatically replies, delivers DMs, and captures them here in real-time.</p>
            </div>
          </td>
        </tr>
      `;
      return;
    }

    const colors = ["#0a0a0b", "#2e2e35", "#47474f", "#62626a", "#8a8a93", "#b0b0b8"];

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
            <span class="source-badge">${escapeHtml(c.source || 'Reel Comments')}</span>
          </td>
          <td>${tagsHtml || '<span style="color:var(--text-faint);">-</span>'}</td>
          <td><small style="color:var(--text-muted);">${escapeHtml(c.last_interaction || 'Recent')}</small></td>
          <td><span class="badge badge-sent">${c.messages_count || 1} msg</span></td>
          <td><span class="lead-status-pill ${statusClass}">${statusLabel}</span></td>
          <td style="text-align: right;">
            <button class="btn-table-action" style="color: #c62828;" onclick="window.deleteContactRecord(${c.id || 0})">
              Delete
            </button>
          </td>
        </tr>
      `;
    }).join("");
  }

  window.deleteContactRecord = async (id) => {
    if (!id) return;
    if (!confirm("Are you sure you want to remove this contact from your CRM?")) return;
    try {
      await fetch(`/api/contacts/${id}`, { method: "DELETE" });
      await loadContacts();
    } catch (_) {
      alert("Error removing contact");
    }
  };

  function setupModalsUI() {
    const helpModal = document.getElementById("helpModal");
    const btnCloseHelpModal = document.getElementById("btnCloseHelpModal");

    if (btnCloseHelpModal) {
      btnCloseHelpModal.addEventListener("click", () => {
        if (helpModal) helpModal.classList.remove("active");
      });
    }
  }

  function openProfileModal() {
    switchView("view-profile");
  }

  function openHelpModal() {
    const helpModal = document.getElementById("helpModal");
    if (helpModal) helpModal.classList.add("active");
  }

  async function performLogout() {
    if (!confirm("Are you sure you want to log out of DM Flow?")) return;
    try {
      await fetch("/api/auth/logout", { method: "POST" });
    } catch (_) {}
    window.location.href = "/login";
  }

  async function performDisconnectIg() {
    if (!confirm("Are you sure you want to disconnect your Instagram account?\n\nAutomated comment replies and DMs will stop firing immediately until reconnected.")) {
      return;
    }
    const btn = document.getElementById("btnProfileDisconnectIg");
    if (btn) { btn.disabled = true; btn.textContent = "Disconnecting…"; }
    try {
      const res = await fetch("/api/instagram/disconnect", { method: "POST" }).then(r => r.json());
      if (res.success) {
        if (window.CF && window.CF.flash) window.CF.flash("Instagram account disconnected");
        else alert("Instagram account disconnected");
        await loadProfile();
        if (window.CFAccount && window.CFAccount.reload) window.CFAccount.reload();
      } else {
        alert(res.error || "Could not disconnect account");
      }
    } catch (e) {
      alert("Error disconnecting account");
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = "Disconnect Instagram Account"; }
    }
  }

  async function handleProfileSave(e) {
    if (e) e.preventDefault();
    const btn = document.getElementById("btnSaveProfile");
    const msg = document.getElementById("profileFormMsg");
    const name = (document.getElementById("inputProfileName") ? document.getElementById("inputProfileName").value : "").trim();
    const business = (document.getElementById("inputProfileBusiness") ? document.getElementById("inputProfileBusiness").value : "").trim();
    const currentPass = document.getElementById("inputCurrentPassword") ? document.getElementById("inputCurrentPassword").value : "";
    const newPass = document.getElementById("inputNewPassword") ? document.getElementById("inputNewPassword").value : "";

    if (!name) {
      if (msg) { msg.textContent = "Name cannot be empty"; msg.style.color = "#b42318"; }
      return;
    }
    if (newPass && newPass.length < 6) {
      if (msg) { msg.textContent = "New password must be at least 6 characters"; msg.style.color = "#b42318"; }
      return;
    }
    if (newPass && !currentPass) {
      if (msg) { msg.textContent = "Please enter your current password to set a new password"; msg.style.color = "#b42318"; }
      return;
    }

    if (btn) { btn.disabled = true; btn.textContent = "Saving…"; }
    if (msg) msg.textContent = "";

    try {
      const res = await fetch("/api/auth/profile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name,
          business: business,
          current_password: currentPass || undefined,
          new_password: newPass || undefined
        })
      }).then(r => r.json());

      if (res.success) {
        if (msg) { msg.textContent = "Profile updated successfully!"; msg.style.color = "#2e7d32"; }
        if (document.getElementById("inputCurrentPassword")) document.getElementById("inputCurrentPassword").value = "";
        if (document.getElementById("inputNewPassword")) document.getElementById("inputNewPassword").value = "";

        const sbName = document.getElementById("sidebarAccountName");
        if (sbName) sbName.textContent = business || name;
        const dispName = document.getElementById("profileDisplayName");
        if (dispName) dispName.textContent = business || name;

        setTimeout(() => { if (msg) msg.textContent = ""; }, 3000);
      } else {
        if (msg) { msg.textContent = res.error || "Update failed"; msg.style.color = "#b42318"; }
      }
    } catch (err) {
      if (msg) { msg.textContent = "Network error. Please try again."; msg.style.color = "#b42318"; }
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = "Save Changes"; }
    }
  }

  async function loadProfile() {
    const formMsg = document.getElementById("profileFormMsg");
    if (formMsg) formMsg.textContent = "";

    try {
      const [authRes, billRes, igRes] = await Promise.all([
        fetch("/api/auth/me").then(r => r.json()).catch(() => ({})),
        fetch("/api/billing/status").then(r => r.json()).catch(() => ({})),
        fetch("/api/instagram/profile").then(r => r.json()).catch(() => ({}))
      ]);

      const user = authRes.user || {};
      const billing = (billRes && billRes.billing) || {};
      const usage = billing.usage || {};

      // Fill Profile Info
      const nameInput = document.getElementById("inputProfileName");
      const busInput = document.getElementById("inputProfileBusiness");
      const emailInput = document.getElementById("inputProfileEmail");
      const dispName = document.getElementById("profileDisplayName");
      const dispEmail = document.getElementById("profileDisplayEmail");
      const bigAvatar = document.getElementById("profileBigAvatar");
      const roleChip = document.getElementById("profileWorkspaceRole");
      const topAvatar = document.getElementById("sidebarAvatarIcon");
      const sideName = document.getElementById("sidebarAccountName");
      const dropEmail = document.getElementById("dropdownUserEmail");
      const dropRole = document.getElementById("dropdownUserRole");

      const effectiveName = user.business || user.name || "Workspace Profile";
      if (nameInput) nameInput.value = user.name || "";
      if (busInput) busInput.value = user.business || "";
      if (emailInput) emailInput.value = user.email || "";
      if (dispName) dispName.textContent = effectiveName;
      if (dispEmail) dispEmail.textContent = user.email || "";
      if (sideName) sideName.textContent = effectiveName;
      if (dropEmail) dropEmail.textContent = user.email || "";
      if (dropRole) dropRole.textContent = authRes.is_admin ? "Administrator" : "Workspace Owner";

      const initials = (user.name || user.business || "W").trim().split(/\s+/).slice(0, 2).map(w => w[0]).join("").toUpperCase();
      if (bigAvatar) bigAvatar.textContent = initials || "W";
      if (topAvatar) topAvatar.textContent = initials || "W";
      const initialsNav = document.getElementById("navAvatarInitials");
      if (initialsNav) initialsNav.textContent = initials || "W";
      if (roleChip) roleChip.textContent = authRes.is_admin ? "ADMIN" : "OWNER";

      // Fill Instagram details
      const igConnected = Boolean(igRes.connected && igRes.success && igRes.profile);
      const igConnBox = document.getElementById("profileIgConnectedBox");
      const igDiscBox = document.getElementById("profileIgDisconnectedBox");
      const igChip = document.getElementById("profileIgStatusChip");

      if (igConnected) {
        if (igConnBox) igConnBox.style.display = "block";
        if (igDiscBox) igDiscBox.style.display = "none";
        if (igChip) {
          igChip.textContent = "CONNECTED";
          igChip.className = "pro-chip is-live";
          igChip.style.background = "#e8f5e9";
          igChip.style.color = "#2e7d32";
        }
        const p = igRes.profile || {};
        const hEl = document.getElementById("profileIgHandle");
        if (hEl) hEl.textContent = p.username ? "@" + p.username : "Connected";
        const metaEl = document.getElementById("profileIgMeta");
        if (metaEl) metaEl.textContent = (p.account_type || "Business").toLowerCase().replace("_", " ") + " account";

        const fEl = document.getElementById("profileIgFollowers");
        if (fEl) fEl.textContent = p.followers_count != null ? Number(p.followers_count).toLocaleString("en-IN") : "—";
        const mEl = document.getElementById("profileIgPosts");
        if (mEl) mEl.textContent = p.media_count != null ? Number(p.media_count).toLocaleString("en-IN") : "—";
        const tEl = document.getElementById("profileIgType");
        if (tEl) tEl.textContent = (p.account_type || "Business").toUpperCase();

        const img = document.getElementById("profileIgAvatar");
        const placeholder = document.getElementById("profileIgPlaceholder");
        if (img && p.profile_picture_url) {
          img.src = p.profile_picture_url;
          img.style.display = "block";
          if (placeholder) placeholder.style.display = "none";
        } else if (img) {
          img.style.display = "none";
          if (placeholder) placeholder.style.display = "flex";
        }
      } else {
        if (igConnBox) igConnBox.style.display = "none";
        if (igDiscBox) igDiscBox.style.display = "block";
        if (igChip) {
          igChip.textContent = "DISCONNECTED";
          igChip.className = "pro-chip";
          igChip.style.background = "#fbe9e7";
          igChip.style.color = "#c62828";
        }
      }

      // Fill Quotas & Plan
      const pName = document.getElementById("profilePlanName");
      const pSub = document.getElementById("profilePlanSub");
      const pBadge = document.getElementById("profilePlanBadge");
      const sideBadge = document.getElementById("sidebarPlanBadge");
      const planTitle = billing.plan_name || "Free Trial";
      if (pName) pName.textContent = planTitle;
      if (pBadge) pBadge.textContent = planTitle.toUpperCase();
      if (sideBadge) sideBadge.textContent = (billing.plan_id || "FREE").toUpperCase();
      if (pSub) pSub.textContent = billing.trial_days_left ? billing.trial_days_left + " days trial remaining" : "Active workspace plan";

      // Quota bars
      const au = usage.automations || {};
      const auText = document.getElementById("profileQuotaFlows");
      const auBar = document.getElementById("profileQuotaFlowsBar");
      if (auText) auText.textContent = (au.used != null ? au.used : "0") + " / " + (au.unlimited ? "∞" : (au.limit || "1"));
      if (auBar) auBar.style.width = au.unlimited ? "20%" : Math.min(100, Math.round(((au.used || 0) / (au.limit || 1)) * 100)) + "%";

      const dm = usage.dms_per_month || {};
      const dmText = document.getElementById("profileQuotaDms");
      const dmBar = document.getElementById("profileQuotaDmsBar");
      if (dmText) dmText.textContent = (dm.used != null ? Number(dm.used).toLocaleString("en-IN") : "0") + " / " + (dm.unlimited ? "∞" : Number(dm.limit || 200).toLocaleString("en-IN"));
      if (dmBar) dmBar.style.width = dm.unlimited ? "20%" : Math.min(100, Math.round(((dm.used || 0) / (dm.limit || 200)) * 100)) + "%";

      const co = usage.contacts || {};
      const coText = document.getElementById("profileQuotaContacts");
      const coBar = document.getElementById("profileQuotaContactsBar");
      if (coText) coText.textContent = (co.used != null ? co.used : "0") + " / " + (co.unlimited ? "∞" : (co.limit || "25"));
      if (coBar) coBar.style.width = co.unlimited ? "20%" : Math.min(100, Math.round(((co.used || 0) / (co.limit || 25)) * 100)) + "%";

    } catch (err) {
      console.warn("[DM Flow] Could not load profile:", err);
    }
  }

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

    window.addEventListener("hashchange", () => {
      const h = window.location.hash;
      if (h) switchView("view-" + h.replace(/^#/, ""));
    });

    try { await loadContacts(); } catch (err) {
      console.warn("[DM Flow] contacts did not load:", err && err.message);
    }

    try {
      await loadProfile();
    } catch (_) {}

    // Check initial hash route
    const initialHash = window.location.hash;
    if (initialHash && initialHash !== "#home") {
      switchView("view-" + initialHash.replace(/^#/, ""));
    }
  }

  window.CFShell = {
    switchView: switchView,
    openUpgrade: openUpgradeModal,
    loadProfile: loadProfile,
    logout: performLogout
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
