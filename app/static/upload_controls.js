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

    function hasDraggedFiles(event) {
        const types = event.dataTransfer && event.dataTransfer.types;
        if (!types) return false;
        return Array.from(types).includes("Files");
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

    function wirePageDropForm(form) {
        const input = form.querySelector('input[type="file"][data-upload-control="csv-dropzone"]');
        const overlay = form.querySelector('[data-upload-page-overlay="true"]');
        if (!input || !overlay) return;

        let dragDepth = 0;

        function showOverlay() {
            overlay.classList.add("is-visible");
            document.body.classList.add("uts-page-upload-active");
        }

        function hideOverlay() {
            dragDepth = 0;
            overlay.classList.remove("is-visible");
            document.body.classList.remove("uts-page-upload-active");
        }

        document.addEventListener("dragenter", (event) => {
            if (!hasDraggedFiles(event)) return;
            dragDepth += 1;
            showOverlay();
        });

        document.addEventListener("dragover", (event) => {
            if (!hasDraggedFiles(event)) return;
            event.preventDefault();
            showOverlay();
        });

        document.addEventListener("dragleave", (event) => {
            if (!hasDraggedFiles(event)) return;
            dragDepth = Math.max(0, dragDepth - 1);
            if (dragDepth === 0) hideOverlay();
        });

        document.addEventListener("drop", (event) => {
            if (!hasDraggedFiles(event)) return;
            event.preventDefault();
            hideOverlay();

            if (!event.dataTransfer?.files?.length) return;

            input.files = event.dataTransfer.files;
            submitWhenReady(input);
        });
    }

    document.addEventListener("DOMContentLoaded", () => {
        document.querySelectorAll(".uts-upload-dropzone").forEach(wireDropzone);
        document.querySelectorAll('form[data-upload-page-drop="true"]').forEach(wirePageDropForm);
    });
})();