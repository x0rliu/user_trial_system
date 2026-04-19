// ================================
// Rail Toggle (single source of truth)
// ================================
document.addEventListener("click", (e) => {
    const toggle = e.target.closest(".rail-toggle");
    if (!toggle) return;

    const group = toggle.closest(".rail-group");
    if (!group) return;

    group.classList.toggle("collapsed");
});

// ================================
// Analysis Loading Overlay
// ================================
function startAnalysisLoading() {
    const overlay = document.getElementById("analysis-loading-overlay");
    const msg = document.getElementById("loading-message");

    if (!overlay || !msg) return;

    overlay.style.display = "flex";

    const timeline = [
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

    timeline.forEach(step => {
        setTimeout(() => {
            msg.innerText = step.text;
        }, step.t);
    });
}

// ================================
// Form Submit Hook (Analysis trigger)
// ================================
document.addEventListener("submit", (e) => {
    const form = e.target;
    if (!form) return;

    if (form.matches('form[action="/surveys/bonus/analyze"]')) {
        startAnalysisLoading();
    }
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