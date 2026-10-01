// Client-side hints for the profile and register forms. The server still validates.
(function () {
  // Profile: a language picked in one slot is disabled in the other slots.
  const selects = Array.from(document.querySelectorAll('.config select[name^="lang"]'));

  function syncLangs() {
    const taken = selects.map((s) => s.value);
    selects.forEach((s, i) => {
      Array.from(s.options).forEach((opt) => {
        if (!opt.value) return;
        opt.disabled = taken.some((v, j) => j !== i && v === opt.value);
      });
    });
  }

  selects.forEach((s) => s.addEventListener("change", syncLangs));
  if (selects.length) syncLangs();

  // Register: flag a mismatched confirm password before submitting.
  const pw = document.querySelector('input[name="password"]');
  const confirm = document.querySelector('input[name="confirm"]');
  if (pw && confirm) {
    const check = () =>
      confirm.setCustomValidity(confirm.value && confirm.value !== pw.value ? "passwords do not match" : "");
    pw.addEventListener("input", check);
    confirm.addEventListener("input", check);
  }
})();
