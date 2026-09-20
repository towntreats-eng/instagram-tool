/* ConverFlow — marketing pages behaviour (nav, FAQ, reveal, auth forms) */
(function () {
  "use strict";

  // Sticky nav shadow
  var nav = document.querySelector(".nav");
  if (nav) {
    var onScroll = function () { nav.classList.toggle("scrolled", window.scrollY > 8); };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    var toggle = nav.querySelector(".nav-toggle");
    if (toggle) toggle.addEventListener("click", function () { nav.classList.toggle("open"); });
    nav.querySelectorAll(".nav-links a").forEach(function (a) {
      a.addEventListener("click", function () { nav.classList.remove("open"); });
    });
  }

  // FAQ accordion
  document.querySelectorAll(".faq-item").forEach(function (item) {
    var q = item.querySelector(".faq-q");
    var a = item.querySelector(".faq-a");
    if (!q || !a) return;
    q.addEventListener("click", function () {
      var open = item.classList.contains("open");
      document.querySelectorAll(".faq-item.open").forEach(function (o) {
        o.classList.remove("open");
        o.querySelector(".faq-a").style.maxHeight = null;
      });
      if (!open) { item.classList.add("open"); a.style.maxHeight = a.scrollHeight + "px"; }
    });
  });

  // Scroll reveal
  var reveals = document.querySelectorAll(".reveal");
  if (reveals.length) {
    if ("IntersectionObserver" in window) {
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (e) {
          if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); }
        });
      }, { threshold: 0.12, rootMargin: "0px 0px -40px 0px" });
      reveals.forEach(function (el) { io.observe(el); });
    } else {
      reveals.forEach(function (el) { el.classList.add("in"); });
    }
  }

  // Animated bars in the dashboard mock
  document.querySelectorAll(".mock-bars div").forEach(function (bar, i) {
    bar.style.animationDelay = (i * 0.08) + "s";
  });

  // ------------------------------------------------------------ auth forms
  function showMsg(box, text, kind) {
    if (!box) return;
    box.textContent = text;
    box.className = "auth-msg show " + kind;
  }

  async function post(url, payload) {
    var res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    return res.json();
  }

  var signupForm = document.getElementById("signupForm");
  if (signupForm) {
    signupForm.addEventListener("submit", async function (e) {
      e.preventDefault();
      var box = document.getElementById("authMsg");
      var btn = signupForm.querySelector("button[type=submit]");
      var data = Object.fromEntries(new FormData(signupForm).entries());
      btn.disabled = true; btn.textContent = "Creating your workspace...";
      try {
        var out = await post("/api/auth/signup", data);
        if (out.success) {
          showMsg(box, "Workspace ready! Taking you to the dashboard...", "ok");
          try { localStorage.setItem("cf_user", JSON.stringify(out.user)); } catch (_) {}
          setTimeout(function () { window.location.href = "/app"; }, 900);
        } else {
          showMsg(box, out.error || "Could not create the account.", "err");
          btn.disabled = false; btn.textContent = "Start 15-day free trial";
        }
      } catch (err) {
        showMsg(box, "Server unreachable. Is ConverFlow running?", "err");
        btn.disabled = false; btn.textContent = "Start 15-day free trial";
      }
    });
  }

  var loginForm = document.getElementById("loginForm");
  if (loginForm) {
    loginForm.addEventListener("submit", async function (e) {
      e.preventDefault();
      var box = document.getElementById("authMsg");
      var btn = loginForm.querySelector("button[type=submit]");
      var data = Object.fromEntries(new FormData(loginForm).entries());
      btn.disabled = true; btn.textContent = "Signing in...";
      try {
        var out = await post("/api/auth/login", data);
        if (out.success) {
          showMsg(box, "Welcome back, " + out.user.name.split(" ")[0] + "!", "ok");
          try { localStorage.setItem("cf_user", JSON.stringify(out.user)); } catch (_) {}
          setTimeout(function () { window.location.href = out.user.role === "admin" ? "/admin" : "/app"; }, 700);
        } else {
          showMsg(box, out.error || "Sign in failed.", "err");
          btn.disabled = false; btn.textContent = "Sign in";
        }
      } catch (err) {
        showMsg(box, "Server unreachable. Is ConverFlow running?", "err");
        btn.disabled = false; btn.textContent = "Sign in";
      }
    });
  }
})();

/* ---------------------------------------------------------------------------
   Live pricing — the cards and the comparison table are built from the plans
   the owner configured in Admin > Plans & pricing, so the site is never stale.
   ------------------------------------------------------------------------ */
(function () {
  "use strict";
  var grid = document.getElementById("planGrid");
  var table = document.getElementById("cmpTable");
  if (!grid && !table) return;

  function inr(n) { return "₹" + Number(n || 0).toLocaleString("en-IN"); }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function cap(v) { return v === -1 ? "Unlimited" : Number(v || 0).toLocaleString("en-IN"); }

  var CHECK = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>';
  var CROSS = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6L6 18M6 6l12 12"/></svg>';

  var LIMIT_LABELS = {
    automations: "active automations", contacts: "contacts", dms_per_month: "DMs a month",
    ig_accounts: "Instagram account", team_seats: "team seat"
  };
  var FEATURE_LABELS = {
    comment_to_dm: "Comment-to-DM automations", dm_keyword: "DM keyword auto-replies",
    wildcard_trigger: "Wildcard (any comment) trigger", story_mention: "Story mention trigger",
    broadcast: "Broadcast / cold DM engine", ai_assist: "AI flow & hook generator",
    analytics: "Campaign analytics", csv_export: "CSV export",
    remove_branding: "No ConverFlow branding", priority_support: "Priority WhatsApp support",
    white_label: "White-label for clients"
  };

  function planCard(p) {
    var lines = [];
    ["automations", "contacts", "dms_per_month"].forEach(function (k) {
      if (p.limits[k] != null) lines.push(cap(p.limits[k]) + " " + LIMIT_LABELS[k]);
    });
    Object.keys(p.features || {}).forEach(function (k) {
      if (p.features[k] && ["broadcast", "ai_assist", "story_mention", "priority_support", "white_label"].indexOf(k) >= 0) {
        lines.push(FEATURE_LABELS[k]);
      }
    });
    lines = lines.slice(0, 6);

    return '<div class="price-card' + (p.highlight ? " featured" : "") + '">' +
      (p.badge ? '<span class="price-tag">' + esc(p.badge) + '</span>' : "") +
      '<div class="price-name">' + esc(p.name) + '</div>' +
      '<div class="price-desc">' + esc(p.tagline || "") + '</div>' +
      '<div class="price-amount"><b>' + inr(p.price_monthly) + '</b><span>' +
      (p.price_monthly === 0 ? "forever" : "/ month") + '</span></div>' +
      '<div class="price-sub">' +
      (p.price_yearly ? inr(p.price_yearly) + " billed yearly" : "No card required") +
      (p.trial_days ? " · " + p.trial_days + "-day free trial" : "") + '</div>' +
      '<ul class="price-list">' + lines.map(function (l) {
        return "<li>" + CHECK + " " + esc(l) + "</li>";
      }).join("") + '</ul>' +
      '<a href="/signup" class="btn ' + (p.highlight ? "btn-green" : "btn-ghost") + ' btn-block">' +
      (p.price_monthly === 0 ? "Start free" : "Choose " + esc(p.name)) + '</a></div>';
  }

  function comparison(plans) {
    var head = "<thead><tr><th>Feature</th>" + plans.map(function (p) {
      return '<th' + (p.highlight ? ' style="color:var(--green)"' : "") + ">" + esc(p.name) +
        (p.price_monthly ? " · " + inr(p.price_monthly) : "") + "</th>";
    }).join("") + "</tr></thead>";

    var limitRows = Object.keys(LIMIT_LABELS).map(function (k) {
      return "<tr><td>" + esc(LIMIT_LABELS[k].charAt(0).toUpperCase() + LIMIT_LABELS[k].slice(1)) + "</td>" +
        plans.map(function (p) {
          return '<td class="yes">' + cap(p.limits[k]) + "</td>";
        }).join("") + "</tr>";
    }).join("");

    var featRows = Object.keys(FEATURE_LABELS).map(function (k) {
      return "<tr><td>" + esc(FEATURE_LABELS[k]) + "</td>" + plans.map(function (p) {
        return (p.features || {})[k]
          ? '<td class="yes">✓</td>'
          : '<td class="no">—</td>';
      }).join("") + "</tr>";
    }).join("");

    return head + "<tbody>" +
      '<tr class="cmp-group"><td colspan="' + (plans.length + 1) + '">What you get</td></tr>' + limitRows +
      '<tr class="cmp-group"><td colspan="' + (plans.length + 1) + '">Features</td></tr>' + featRows +
      "</tbody>";
  }

  fetch("/api/public/plans")
    .then(function (r) { return r.json(); })
    .then(function (out) {
      if (!out.plans || !out.plans.length) return;
      if (grid) {
        grid.style.gridTemplateColumns = "repeat(auto-fit, minmax(230px, 1fr))";
        grid.style.maxWidth = "1180px";
        grid.innerHTML = out.plans.map(planCard).join("");
      }
      if (table) table.innerHTML = comparison(out.plans);

      if (out.offers && out.offers.length && grid) {
        var o = out.offers[0];
        var banner = document.createElement("p");
        banner.style.cssText = "text-align:center;margin-top:22px;font-size:14px;color:var(--muted)";
        banner.innerHTML = 'Use code <b style="font-family:var(--mono);color:var(--green)">' + esc(o.code) +
          "</b> at checkout — " + esc(o.description || o.title || "");
        grid.parentNode.insertBefore(banner, grid.nextSibling);
      }
    })
    .catch(function () { /* static fallback stays */ });
})();
