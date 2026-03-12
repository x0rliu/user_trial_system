// app/static/js/profile_rules.js
//
// Generic profile rules engine
// Rule: selecting an "x / none / does not use" option
// disables and clears other options in the same category.
//
// Works for radio + checkbox categories.
// No hardcoded category IDs.
// Relies only on value ending in "x" OR label text including "not" / "none".
//

(function () {
  function isNoneOption(input) {
    const value = input.value || "";
    const label = input.closest("label");
    const labelText = label ? label.innerText.toLowerCase() : "";

    return (
      value.endsWith("x") ||
      labelText.includes("none") ||
      labelText.includes("does not") ||
      labelText.includes("no console") 
    );
  }

    function updateCategory(categoryEl) {
    const inputs = Array.from(
        categoryEl.querySelectorAll("input[type='checkbox'], input[type='radio']")
    );

    if (!inputs.length) return;

    // 🔑 NEW: only apply rule to checkbox groups
    const isCheckboxGroup = inputs[0].type === "checkbox";
    if (!isCheckboxGroup) return;

    const noneInput = inputs.find(isNoneOption);
    if (!noneInput) return;

    const noneChecked = noneInput.checked;

    inputs.forEach((input) => {
        if (input === noneInput) return;

        if (noneChecked) {
        input.checked = false;
        input.disabled = true;
        input.closest("label")?.classList.add("disabled");
        } else {
        input.disabled = false;
        input.closest("label")?.classList.remove("disabled");
        }
    });
    }

  function initProfileRules(root = document) {
    const categories = root.querySelectorAll(".profile-category");

    categories.forEach((category) => {
      const inputs = category.querySelectorAll("input");

      inputs.forEach((input) => {
        input.addEventListener("change", () => {
          updateCategory(category);
        });
      });

      // run once on load (important for existing selections)
      updateCategory(category);
    });
  }

  // Initial load
  document.addEventListener("DOMContentLoaded", () => {
    initProfileRules();
  });

  // Expose for dynamically injected fragments (settings)
  window.initProfileRules = initProfileRules;
})();
