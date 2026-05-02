// ================================
// Rail Toggle (single source of truth)
// ================================
document.addEventListener("click", (event) => {
    const toggle = event.target.closest(".rail-toggle");
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

// ================================
// Rail Default State
// ================================
// Presentational only.
// If a group has real survey links, open it.
// If it only has an empty-state message, keep it collapsed.
document.addEventListener("DOMContentLoaded", () => {
    const groups = document.querySelectorAll(
        ".bonus-rail .rail-group[data-collapsible]"
    );

    groups.forEach((group) => {
        const section = group.querySelector(".rail-section");
        if (!section) return;

        const hasRealItems = Boolean(
            section.querySelector("a.rail-item")
        );

        if (hasRealItems) {
            group.classList.remove("collapsed");
        } else {
            group.classList.add("collapsed");
        }
    });
});

// ================================
// Analysis Loading Overlay
// ================================

let analysisTimers = [];

function startAnalysisLoading() {
    const overlay = document.getElementById("analysis-loading-overlay");
    const msg = document.getElementById("loading-message");

    if (!overlay || !msg) {
        console.log("Spinner failed: overlay or message not found");
        return;
    }

    // -------------------------
    // Reset any previous state
    // -------------------------
    stopAnalysisLoading();

    overlay.style.display = "flex";
    msg.innerText = "Initializing...";

    // -------------------------
    // BASE TIMELINE (your original)
    // -------------------------
    const baseTimeline = [
        { t: 0, text: "Contacting MotherBox..." },
        { t: 2000, text: "Securing connection..." },
        { t: 4000, text: "Sending payload..." },
        { t: 6000, text: "Processing segments..." },
        { t: 9000, text: "Extracting signals..." },
        { t: 12000, text: "Analyzing patterns..." },
        { t: 15000, text: "Thinking..." },
        { t: 18000, text: "Thinking some more..." },
        { t: 22000, text: "Fascinating insights coming..." },
        { t: 26000, text: "Almost there..." }
    ];

    // -------------------------
    // LOOPING MESSAGES (prevents stall)
    // -------------------------
    const loopMessages = [
        "Still thinking...",
        "Cross-referencing signals...",
        "Checking edge cases...",
        "Refining insights...",
        "Running deeper analysis...",
        "Looking for patterns...",
        "Verifying consistency...",
        "Almost there..."
    ];

    const timeline = [...baseTimeline];

    // -------------------------
    // EXTEND TIMELINE (~3+ minutes)
    // -------------------------
    let lastTime = baseTimeline[baseTimeline.length - 1].t;

    for (let i = 1; i <= 50; i++) {
        timeline.push({
            t: lastTime + (i * 4000),
            text: loopMessages[i % loopMessages.length]
        });
    }

    // -------------------------
    // APPLY TIMELINE
    // -------------------------
    timeline.forEach(step => {
        const timer = setTimeout(() => {
            msg.innerText = step.text;
        }, step.t);

        analysisTimers.push(timer);
    });
}

function stopAnalysisLoading() {
    analysisTimers.forEach(t => clearTimeout(t));
    analysisTimers = [];

    const overlay = document.getElementById("analysis-loading-overlay");
    if (overlay) {
        overlay.style.display = "none";
    }
}

// ================================
// Form Submit Hook (Analysis trigger)
// ================================
document.addEventListener("submit", (event) => {
    const form = event.target;
    if (!form || form.tagName !== "FORM") return;

    const action = form.getAttribute("action") || "";

    const shouldTrigger =
        action.includes("/historical/upload") ||
        action.includes("/historical/generate-insights") ||
        action.includes("/historical/generate-section-summaries") ||
        action.includes("/historical/generate-section-names") ||
        action.includes("/surveys/bonus/analyze");

    if (!shouldTrigger) return;

    // Prevent double submit
    if (form.dataset.loading === "true") return;

    event.preventDefault();

    form.dataset.loading = "true";

    console.log("Spinner triggered for:", action);

    startAnalysisLoading();

    // Allow spinner to render before submitting.
    setTimeout(() => {
        form.submit();
    }, 100);
});

// ================================
// Toast System (server-driven)
// ================================
document.addEventListener("DOMContentLoaded", () => {
    const toastType = document.body.getAttribute("data-toast");
    if (!toastType) return;

    const container = document.getElementById("toast-container");
    if (!container) return;

    let message = "";

    if (toastType === "closed") {
        message = "Survey closed successfully";
    }

    if (!message) return;

    const toast = document.createElement("div");
    toast.className = "toast success";
    toast.innerText = message;

    container.appendChild(toast);

    setTimeout(() => toast.remove(), 3000);
});

// ================================
// Expand / Collapse All Sections
// ================================

function expandAllSections() {
    const groups = document.querySelectorAll(".bonus-rail .rail-group[data-collapsible]");

    groups.forEach(group => {
        group.classList.remove("collapsed");
    });
}

function collapseAllSections() {
    const groups = document.querySelectorAll(".bonus-rail .rail-group[data-collapsible]");

    groups.forEach(group => {
        group.classList.add("collapsed");
    });
}