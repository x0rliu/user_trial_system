document.addEventListener("change", function (e) {
    if (!e.target.classList.contains("approval-action")) return;

    const select = e.target;
    const row = select.closest("tr");
    const approvalId = row.dataset.approvalId;

    const detailRow = document.querySelector(
        `.approval-detail[data-approval-id="${approvalId}"]`
    );
    if (!detailRow) return;

    document.querySelectorAll(".approval-detail").forEach(r => {
        r.classList.add("hidden");
    });

    if (!select.value) return;

    detailRow.classList.remove("hidden");

    // write action
    const actionInput = detailRow.querySelector('input[name="action"]');
    if (actionInput) {
        actionInput.value = select.value;
    }

    // toggle approve / non-approve blocks
    // Toggle approve-only block
    detailRow.querySelectorAll(".approve-only").forEach(el => {
        const isApprove = select.value === "approve";
        el.classList.toggle("hidden", !isApprove);

        el.querySelectorAll("select, textarea, input").forEach(input => {
            input.required = isApprove;
            input.disabled = !isApprove;
        });
    });

    // Toggle non-approve block
    detailRow.querySelectorAll(".non-approve-only").forEach(el => {
        const isNonApprove = select.value !== "approve";
        el.classList.toggle("hidden", !isNonApprove);

        el.querySelectorAll("select, textarea, input").forEach(input => {
            input.required = isNonApprove;
            input.disabled = !isNonApprove;
        });
    });
});
