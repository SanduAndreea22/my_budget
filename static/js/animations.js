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
    toggle.textContent = "👁";
    toggle.setAttribute("aria-label", "Show password");
    wrapper.appendChild(toggle);

    toggle.addEventListener("click", function () {
      const isShown = input.type === "text";
      input.type = isShown ? "password" : "text";
      toggle.textContent = isShown ? "👁" : "🙈";
      toggle.setAttribute("aria-label", isShown ? "Show password" : "Hide password");
    });
  });
});
