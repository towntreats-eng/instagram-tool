/* DM Flow — marketing pages behaviour (nav, FAQ, reveal, auth forms) */
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
        showMsg(box, "Server unreachable. Is DM Flow running?", "err");
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
          var params = new URLSearchParams(window.location.search);
          var next = params.get("next");
          var target = (next && next.startsWith("/") && !next.startsWith("//"))
                       ? next
                       : (out.user.role === "admin" ? "/admin" : "/app");
          setTimeout(function () { window.location.href = target; }, 700);
        } else {
          showMsg(box, out.error || "Sign in failed.", "err");
          btn.disabled = false; btn.textContent = "Sign in";
        }
      } catch (err) {
        showMsg(box, "Server unreachable. Is DM Flow running?", "err");
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

  // [one, many] — "1 active automations" reads like a bug, because it is one.
  var LIMIT_LABELS = {
    automations: ["active automation", "active automations"],
    contacts: ["contact", "contacts"],
    dms_per_month: ["DM a month", "DMs a month"],
    ig_accounts: ["Instagram account", "Instagram accounts"]
  };
  function limitLabel(key, value) {
    var pair = LIMIT_LABELS[key] || [key, key];
    return pair[Number(value) === 1 ? 0 : 1];   // -1 (unlimited) takes the plural
  }
  // Only what the product actually does. A feature listed here that the code
  // does not deliver is a promise the merchant pays for and never gets.
  var FEATURE_LABELS = {
    comment_to_dm: "Comment-to-DM automations",
    follow_gate: "Follow-gate before the link",
    any_post: "Watch every post, not just one",
    priority_support: "Priority WhatsApp support"
  };

  // Pricing state: billing cycle and whether the visitor is already signed in.
  var PR = { cycle: "monthly", plans: [], tax: 0, loggedIn: false };

  function buyHref(p) {
    var free = Number(p.price_monthly) === 0;
    if (free) return PR.loggedIn ? "/app" : "/signup";
    var target = "/app/billing?plan=" + encodeURIComponent(p.id) + "&cycle=" + PR.cycle;
    return PR.loggedIn ? target : "/signup?next=" + encodeURIComponent(target);
  }

  function planCard(p) {
    var lines = [];
    ["automations", "contacts", "dms_per_month"].forEach(function (k) {
      if (p.limits[k] != null) lines.push(cap(p.limits[k]) + " " + limitLabel(k, p.limits[k]));
    });
    Object.keys(p.features || {}).forEach(function (k) {
      if (p.features[k] && ["follow_gate", "any_post", "priority_support"].indexOf(k) >= 0) {
        lines.push(FEATURE_LABELS[k]);
      }
    });
    lines = lines.slice(0, 6);
    var free = Number(p.price_monthly) === 0;
    var yearly = PR.cycle === "yearly" && Number(p.price_yearly) > 0;
    var price = free ? 0 : (yearly ? p.price_yearly : p.price_monthly);
    var sub = free ? "No card required"
      : yearly ? "≈ " + inr(Math.round(p.price_yearly / 12)) + " / month, billed yearly"
      : (p.price_yearly ? "or " + inr(p.price_yearly) + " / year" : "Billed monthly");
    var gst = !free && PR.tax ? " + " + PR.tax + "% GST" : "";

    return '<div class="price-card' + (p.highlight ? " featured" : "") + '">' +
      (p.badge ? '<span class="price-tag">' + esc(p.badge) + '</span>' : "") +
      '<div class="price-name">' + esc(p.name) + '</div>' +
      '<div class="price-desc">' + esc(p.tagline || "") + '</div>' +
      '<div class="price-amount"><b>' + inr(price) + '</b><span>' +
      (free ? "forever" : yearly ? "/ year" : "/ month") + esc(gst) + '</span></div>' +
      '<div class="price-sub">' + esc(sub) + '</div>' +
      '<ul class="price-list">' + lines.map(function (l) {
        return "<li>" + CHECK + " " + esc(l) + "</li>";
      }).join("") + '</ul>' +
      '<a href="' + buyHref(p) + '" class="btn ' + (p.highlight ? "btn-green" : "btn-ghost") + ' btn-block">' +
      (free ? (PR.loggedIn ? "Open dashboard" : "Start free") : "Buy " + esc(p.name)) + '</a>' +
      (free ? "" : '<div class="price-pay">UPI · Cards · Net banking</div>') + '</div>';
  }

  function cycleToggle() {
    var save = 0;
    PR.plans.forEach(function (p) {
      if (p.price_monthly > 0 && p.price_yearly > 0) save = Math.max(save, Math.round(100 - p.price_yearly / (p.price_monthly * 12) * 100));
    });
    var wrap = document.createElement("div");
    wrap.className = "cycle-toggle";
    wrap.innerHTML = '<button type="button" data-cyc="monthly" class="on">Monthly</button>' +
      '<button type="button" data-cyc="yearly">Yearly' + (save > 0 ? " <em>save " + save + "%</em>" : "") + "</button>";
    wrap.addEventListener("click", function (e) {
      var b = e.target.closest("[data-cyc]");
      if (!b) return;
      PR.cycle = b.dataset.cyc;
      Array.prototype.forEach.call(wrap.children, function (x) { x.classList.toggle("on", x === b); });
      paintPlans();
    });
    return wrap;
  }

  function paintPlans() {
    if (!grid) return;
    grid.style.gridTemplateColumns = "repeat(auto-fit, minmax(230px, 1fr))";
    grid.style.maxWidth = "1180px";
    grid.innerHTML = PR.plans.map(planCard).join("");
  }

  function comparison(plans) {
    var head = "<thead><tr><th>Feature</th>" + plans.map(function (p) {
      return '<th' + (p.highlight ? ' style="color:var(--green)"' : "") + ">" + esc(p.name) +
        (p.price_monthly ? " · " + inr(p.price_monthly) : "") + "</th>";
    }).join("") + "</tr></thead>";

    var limitRows = Object.keys(LIMIT_LABELS).map(function (k) {
      var head = LIMIT_LABELS[k][1];
      return "<tr><td>" + esc(head.charAt(0).toUpperCase() + head.slice(1)) + "</td>" +
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

  var meReq = fetch("/api/me", { credentials: "same-origin" })
    .then(function (r) { return r.ok; }).catch(function () { return false; });

  fetch("/api/public/plans")
    .then(function (r) { return r.json(); })
    .then(function (out) {
      if (!out.plans || !out.plans.length) return;
      PR.plans = out.plans; PR.tax = out.tax_percent || 0;
      if (grid) {
        grid.parentNode.insertBefore(cycleToggle(), grid);
        paintPlans();
        meReq.then(function (ok) { if (ok) { PR.loggedIn = true; paintPlans(); } });
      }
      if (table) table.innerHTML = comparison(out.plans);
    })
    .catch(function () { /* static fallback stays */ });
})();
