document.addEventListener("click", function(e){

    if (e.target.classList.contains("apply-toggle")) {

        const roundId = e.target.dataset.roundId;

        const form = document.getElementById("apply-form-" + roundId);

        if (form.classList.contains("hidden")) {
            form.classList.remove("hidden");
        } else {
            form.classList.add("hidden");
        }

    }

});