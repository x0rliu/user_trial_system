/**
 * SETTINGS PANEL LOADER
 * ----------------------
 * Responsibility:
 * - Lazy-loads settings editor panels on first expand
 * - Fetches HTML fragments via GET
 * - Injects fragment into the panel container
 *
 * This pattern is reused for:
 * - Demographics
 * - Interests
 * - Basic Profile
 * - Advanced Profile
 *
 * Saving is handled separately by the submit handler.
 * This code MUST NOT perform any POST or save logic.
 */

document.addEventListener("click", async (e) => {
  const summary = e.target.closest("[data-settings-section]");
  if (!summary) return;

  const section = summary.dataset.settingsSection;
  if (!section) return;

  const item = summary.closest(".settings-item");
  const panel = item.querySelector(".settings-panel");

  // Prevent re-loading if already loaded
  if (panel.dataset.loaded === "1") return;

  const res = await fetch(`/settings/${section}`);
  const html = await res.text();

  panel.innerHTML = html;
  panel.dataset.loaded = "1";

  // 🔑 THIS IS THE MISSING LINE
  if (window.initProfileRules) {
    window.initProfileRules(panel);
  }
});


/**
 * Post for Legal Document DB Updates
 * ---------------------------------
 * Settings forms must submit normally through POST -> redirect.
 * This async handler is intentionally limited to legal document editing.
 */

document.addEventListener(
  "submit",
  async (e) => {
    const form = e.target;
    if (!form) return;

    const isLegalDocumentForm = form.classList.contains("legal-document-form");

    if (!isLegalDocumentForm) {
      return;
    }

    // ✅ prevent double-submit (TinyMCE + async)
    if (form.dataset.saving === "1") {
      return;
    }
    form.dataset.saving = "1";

    e.preventDefault();
    e.stopPropagation();
    e.stopImmediatePropagation();

    const endpoint = form.dataset.endpoint;
    if (!endpoint) {
      form.dataset.saving = "0";
      return;
    }

    const button = form.querySelector("button[type='submit']");
    const originalText = button.textContent;

    button.textContent = "Saving…";
    button.disabled = true;

    // 🔴 CRITICAL: sync TinyMCE → textarea BEFORE reading form data
    if (window.tinymce && tinymce.get("legal-editor")) {
      tinymce.triggerSave();
    }

    const data = Object.fromEntries(new FormData(form));

    try {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });

      const result = await res.json();

      if (result.ok) {
        const docId = result.document_id;

        if (docId) {
          window.location.href = `/legal/documents/${docId}`;
        } else {
          window.location.reload();
        }
      }

      else {
        throw new Error(result.error || "Save failed");
      }

    } catch (err) {
      console.error(err);
      button.textContent = "Error";
      button.disabled = false;
      form.dataset.saving = "0";
    }
  },
  true // 🔑 CAPTURE PHASE — legal editor needs this because TinyMCE can interfere
);

document.addEventListener("click", async (e) => {
  const btn = e.target.closest("#publish-doc");
  if (!btn) return;

  const form = btn.closest(".legal-document-form");
  if (!form) return;

  // prevent double publish
  if (form.dataset.publishing === "1") return;
  form.dataset.publishing = "1";

  // sync TinyMCE → textarea
  if (window.tinymce && tinymce.get("legal-editor")) {
    tinymce.triggerSave();
  }

  const publishEndpoint = "/legal/documents/publish";

  btn.disabled = true;
  const originalText = btn.textContent;
  btn.textContent = "Publishing…";

  const data = Object.fromEntries(new FormData(form));

  try {
    const res = await fetch(publishEndpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });

    const result = await res.json();

    if (!result.ok) {
      throw new Error(result.error || "Publish failed");
    }

    const activeId = result.active_id;
    if (activeId) {
      window.location.href = `/legal/documents/${activeId}`;
    } else {
      window.location.reload();
    }

  } catch (err) {
    console.error(err);
    btn.textContent = "Error";
    btn.disabled = false;
    form.dataset.publishing = "0";
  } finally {
    // If we redirected, this doesn't matter; if we didn't, restore state
    if (btn.textContent !== "Error") {
      btn.textContent = originalText;
    }
  }
});


document.addEventListener("change", function (e) {
    if (!e.target.classList.contains("approval-action")) return;

    const select = e.target;
    const row = select.closest("tr");
    const approvalId = row?.dataset?.approvalId;

    if (!approvalId) return;

    const detailRow = document.querySelector(
        `.approval-detail[data-approval-id="${approvalId}"]`
    );
    if (!detailRow) return;

    // Collapse all other expanded rows
    document
        .querySelectorAll(".approval-detail")
        .forEach(r => r.classList.add("hidden"));

    // Reset all conditional sections
    detailRow.querySelectorAll(".approve-only, .non-approve-only")
        .forEach(el => el.classList.add("hidden"));

    // If no action selected, stay collapsed
    if (!select.value) return;

    // Expand this row
    detailRow.classList.remove("hidden");

    // Sync hidden action input
    const actionInput = detailRow.querySelector('input[name="action"]');
    if (actionInput) {
        actionInput.value = select.value;
    }

    // Toggle correct input block
    if (select.value === "approve") {
        const approveBlock = detailRow.querySelector(".approve-only");
        if (approveBlock) approveBlock.classList.remove("hidden");
    } else {
        const nonApproveBlock = detailRow.querySelector(".non-approve-only");
        if (nonApproveBlock) nonApproveBlock.classList.remove("hidden");
    }
});
