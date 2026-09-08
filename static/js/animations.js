document.addEventListener("DOMContentLoaded", function () {
  // Progress bars: render at 0% then transition to their real value,
  // instead of just appearing already full.
  requestAnimationFrame(function () {
    document.querySelectorAll(".progress-fill[data-fill]").forEach(function (el) {
      el.style.width = el.dataset.fill + "%";
    });
  });

  // Big summary numbers: count up from 0 instead of appearing instantly.
  document.querySelectorAll("[data-countup]").forEach(function (el) {
    const target = parseFloat(el.dataset.countup);
    if (Number.isNaN(target)) return;

    const suffix = el.dataset.countupSuffix || "";
    const duration = 900;
    const start = performance.now();

    function formatNumber(value) {
      return value.toLocaleString("en-US", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      });
    }

    function tick(now) {
      const progress = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - progress, 3);
      el.textContent = formatNumber(target * eased) + suffix;
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
