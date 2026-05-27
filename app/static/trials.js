document.addEventListener("click", function (event) {
    const toggle = event.target.closest(".apply-toggle");

    if (!toggle) {
        return;
    }

    const roundId = toggle.dataset.roundId;
    const form = document.getElementById("apply-form-" + roundId);

    if (!form) {
        return;
    }

    const isOpening = form.classList.contains("hidden");

    form.classList.toggle("hidden", !isOpening);
    toggle.setAttribute("aria-expanded", isOpening ? "true" : "false");
    toggle.textContent = isOpening
        ? (toggle.dataset.expandedLabel || "Collapse")
        : (toggle.dataset.collapsedLabel || "Apply");
});