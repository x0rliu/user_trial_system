document.addEventListener("click", (e) => {
    const toggle = e.target.closest(".rail-toggle");
    if (!toggle) return;

    const group = toggle.closest(".rail-group");
    if (!group) return;

    group.classList.toggle("collapsed");
});
