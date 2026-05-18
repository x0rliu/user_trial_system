(function () {
    function updateFileName(input) {
        const dropzone = input.closest(".uts-upload-dropzone");
        if (!dropzone) return;

        const fileLabel = dropzone.querySelector(".uts-upload-dropzone-file");
        const file = input.files && input.files.length ? input.files[0] : null;

        dropzone.classList.toggle("has-file", Boolean(file));
        if (fileLabel) fileLabel.textContent = file ? `Selected: ${file.name}` : "";
    }

    function submitWhenReady(input) {
        const form = input.closest("form");
        if (!form) return;

        updateFileName(input);

        if (typeof form.reportValidity === "function" && !form.reportValidity()) {
            return;
        }

        if (typeof form.requestSubmit === "function") {
            form.requestSubmit();
        } else {
            form.submit();
        }
    }

    function wireDropzone(dropzone) {
        const input = dropzone.querySelector('input[type="file"][data-upload-control="csv-dropzone"]');
        if (!input) return;

        input.addEventListener("change", () => {
            if (input.files && input.files.length) submitWhenReady(input);
        });

        dropzone.addEventListener("dragover", (event) => {
            event.preventDefault();
            dropzone.classList.add("is-dragging");
        });

        dropzone.addEventListener("dragleave", () => {
            dropzone.classList.remove("is-dragging");
        });

        dropzone.addEventListener("drop", (event) => {
            event.preventDefault();
            dropzone.classList.remove("is-dragging");

            if (!event.dataTransfer?.files?.length) return;

            input.files = event.dataTransfer.files;
            submitWhenReady(input);
        });
    }

    document.addEventListener("DOMContentLoaded", () => {
        document.querySelectorAll(".uts-upload-dropzone").forEach(wireDropzone);
    });
})();