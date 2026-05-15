// ================================
// Product Team Rail Toggle
// Mirrors the Bonus Survey rail behavior.
// ================================
document.addEventListener("click", (event) => {
    const toggle = event.target.closest(".product-rail .rail-toggle");
    if (!toggle) return;

    // Ignore real links inside rail headers.
    // Do NOT ignore the toggle button itself.
    if (event.target.closest("a")) {
        return;
    }

    const group = toggle.closest(".rail-group");
    if (!group) return;

    group.classList.toggle("collapsed");
});