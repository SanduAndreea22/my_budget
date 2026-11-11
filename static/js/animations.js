const EYE_ON = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>';
const EYE_OFF = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M17.9 17.9A10.9 10.9 0 0 1 12 19c-6.5 0-10-7-10-7a18.7 18.7 0 0 1 4.1-4.9M9.9 5.2A9.7 9.7 0 0 1 12 5c6.5 0 10 7 10 7a18.5 18.5 0 0 1-2.2 3.2M1 1l22 22"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/></svg>';
document.addEventListener("DOMContentLoaded", function () {
  // Progress bars: render at 0% then transition to their real value,
  // instead of just appearing already full.
  requestAnimationFrame(function () {
    document.querySelectorAll(".progress-fill[data-fill]").forEach(function (el) {
      el.style.width = el.dataset.fill + "%";
    });
  });

  // Big summary numbers: count up from 0 instead of appearing instantly.
  const countupDuration = 900;

  function formatCountupNumber(value) {
    return value.toLocaleString("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  }

  document.querySelectorAll("[data-countup]").forEach(function (el) {
    const target = parseFloat(el.dataset.countup);
    if (Number.isNaN(target)) return;

    const suffix = el.dataset.countupSuffix || "";
    const start = performance.now();
    el._countupValue = 0;

    function tick(now) {
      const progress = Math.min(1, (now - start) / countupDuration);
      const eased = 1 - Math.pow(1 - progress, 3);
      const value = target * eased;
      el._countupValue = value;
      el.textContent = formatCountupNumber(value) + suffix;
      if (progress < 1) requestAnimationFrame(tick);
    }

    requestAnimationFrame(tick);
  });

  // Numbers that must always equal the difference of two other count-up
  // elements' CURRENTLY DISPLAYED value (e.g. Balance = Income - Expense)
  // — read live from those elements every frame instead of animating on
  // an independent timer. Three separately-eased animations can drift out
  // of sync for a moment (each has its own start time and easing curve),
  // which briefly makes Income - Expense != Balance on screen even though
  // the underlying totals are correct. Driving this one from the other
  // two's live values instead makes that impossible at any frame.
  document.querySelectorAll("[data-countup-diff]").forEach(function (el) {
    const ids = el.dataset.countupDiff.split(",").map(function (id) { return id.trim(); });
    const minuendEl = document.getElementById(ids[0]);
    const subtrahendEl = document.getElementById(ids[1]);
    if (!minuendEl || !subtrahendEl) return;

    const suffix = el.dataset.countupSuffix || "";
    const start = performance.now();

    function tick(now) {
      const progress = Math.min(1, (now - start) / countupDuration);
      const value = (minuendEl._countupValue || 0) - (subtrahendEl._countupValue || 0);
      el.textContent = formatCountupNumber(value) + suffix;
      if (progress < 1) requestAnimationFrame(tick);
    }

    requestAnimationFrame(tick);
  });

  // Subnav (11 links) scrolls sideways on phones: bring the active section
  // into view, and fade the edge(s) that still hide more links.
  const subnav = document.querySelector(".subnav");
  if (subnav) {
    const active = subnav.querySelector(".subnav__link--active");
    if (active) {
      subnav.scrollLeft = active.offsetLeft - (subnav.clientWidth - active.offsetWidth) / 2;
    }
    const updateFade = function () {
      const max = subnav.scrollWidth - subnav.clientWidth;
      subnav.classList.toggle("fade-l", subnav.scrollLeft > 4);
      subnav.classList.toggle("fade-r", max > 4 && subnav.scrollLeft < max - 4);
    };
    subnav.addEventListener("scroll", updateFade, { passive: true });
    window.addEventListener("resize", updateFade);
    updateFade();
  }

  // Toasts: auto-dismiss (errors stay longer), click to dismiss early.
  document.querySelectorAll(".toast").forEach(function (toast) {
    const isError = toast.classList.contains("toast--error");
    const ms = isError ? 8000 : 5000;
    toast.style.setProperty("--dur", ms + "ms");
    let timer = setTimeout(dismiss, ms);

    function dismiss() {
      toast.classList.add("is-leaving");
      setTimeout(function () { toast.remove(); }, 300);
    }
    toast.addEventListener("click", function () { clearTimeout(timer); dismiss(); });
  });

  // Password fields: add a show/hide toggle to every password input,
  // wherever it appears (login, register, reset password) — no per-form
  // markup needed.
  document.querySelectorAll('input[type="password"]').forEach(function (input) {
    const wrapper = document.createElement("div");
    wrapper.className = "password-field";
    input.parentNode.insertBefore(wrapper, input);
    wrapper.appendChild(input);

    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "password-toggle";
    toggle.innerHTML = EYE_ON;
    toggle.setAttribute("aria-label", "Show password");
    wrapper.appendChild(toggle);

    toggle.addEventListener("click", function () {
      const isShown = input.type === "text";
      input.type = isShown ? "password" : "text";
      toggle.innerHTML = isShown ? EYE_ON : EYE_OFF;
      toggle.setAttribute("aria-label", isShown ? "Show password" : "Hide password");
    });
  });
});

// Called by chart pages once a Chart.js chart has rendered, to fade out
// the shimmering placeholder behind the canvas.
window.markChartReady = function (canvas) {
  if (canvas && canvas.parentElement) canvas.parentElement.classList.add("is-ready");
};

// Quick pickers: buttons with data-pick/data-target fill an input (emoji, color)
// and show which one is currently selected.
document.addEventListener("DOMContentLoaded", function () {
  const buttons = document.querySelectorAll("[data-pick][data-target]");
  function sync(input) {
    document.querySelectorAll('[data-target="' + input.id + '"]').forEach(function (b) {
      b.classList.toggle("is-selected", b.dataset.pick.toLowerCase() === input.value.toLowerCase());
    });
  }
  buttons.forEach(function (btn) {
    const input = document.getElementById(btn.dataset.target);
    if (!input) return;
    btn.addEventListener("click", function () {
      input.value = btn.dataset.pick;
      input.dispatchEvent(new Event("input", { bubbles: true }));
      sync(input);
    });
    if (!input._pickerBound) {
      input._pickerBound = true;
      input.addEventListener("input", function () { sync(input); });
      sync(input);
    }
  });

  // Dropdown menus (<details class="menu">): close on outside click / Escape.
  document.addEventListener("click", function (e) {
    document.querySelectorAll("details.menu[open]").forEach(function (m) {
      if (!m.contains(e.target)) m.removeAttribute("open");
    });
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") document.querySelectorAll("details.menu[open]").forEach(function (m) { m.removeAttribute("open"); });
  });
});

// Live preview on the add income/expense forms: mirrors the amount being typed.
document.addEventListener("DOMContentLoaded", function () {
  const card = document.querySelector("[data-preview]");
  const input = document.querySelector('input[name="amount"]');
  const out = card && card.querySelector("[data-preview-amount]");
  if (!card || !input || !out) return;
  const placeholder = out.textContent;
  function update() {
    const v = parseFloat(input.value);
    out.textContent = Number.isNaN(v) || v <= 0
      ? placeholder
      : card.dataset.sign + v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " " + card.dataset.currency;
  }
  input.addEventListener("input", update);
  update();
});

// Money formatting shared by charts: "1,234.50 RON". Charts get the user's
// currency from the page so tooltips/axes never show a bare number.
window.fmtMoney = function (value, currency) {
  return Number(value).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " " + currency;
};

// Lightbox for landing screenshots: the links open the image on their own without JS;
// with JS they open a full-screen dialog you can scroll and pinch (Esc, Close button or
// a click outside the image closes it).
document.addEventListener("DOMContentLoaded", function () {
  const links = document.querySelectorAll("a[data-lightbox]");
  if (!links.length || typeof HTMLDialogElement === "undefined") return;

  const dialog = document.createElement("dialog");
  dialog.className = "lightbox";
  dialog.setAttribute("aria-label", "Enlarged screenshot");
  dialog.innerHTML =
    '<span class="lightbox__hint">Scroll or pinch to look around</span>' +
    '<button type="button" class="lightbox__close">Close ✕</button>' +
    '<div class="lightbox__scroll"><img class="lightbox__img" alt=""></div>';
  document.body.appendChild(dialog);
  const img = dialog.querySelector(".lightbox__img");

  links.forEach(function (link) {
    link.addEventListener("click", function (e) {
      e.preventDefault();
      const thumb = link.querySelector("img");
      img.src = link.getAttribute("href");
      img.alt = thumb ? thumb.alt : "";
      dialog.showModal();
      dialog.querySelector(".lightbox__scroll").scrollTo(0, 0);
    });
  });
  dialog.querySelector(".lightbox__close").addEventListener("click", function () { dialog.close(); });
  dialog.addEventListener("click", function (e) {
    if (e.target === dialog || e.target.classList.contains("lightbox__scroll")) dialog.close();
  });
});

// Demo guide: open by default on wide screens; on a phone it stays closed so the totals
// remain in the first screen (the summary line is still visible and tappable).
document.addEventListener("DOMContentLoaded", function () {
  const tour = document.getElementById("demo-tour");
  if (tour && window.matchMedia("(min-width: 861px)").matches) tour.open = true;
});
