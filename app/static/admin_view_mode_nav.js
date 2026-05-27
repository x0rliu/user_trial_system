(function () {
    function closeAdminViewModeFlyouts(exceptFlyout) {
        const flyouts = document.querySelectorAll(".admin-view-mode-flyout");

        flyouts.forEach((flyout) => {
            if (exceptFlyout && flyout === exceptFlyout) {
                return;
            }

            flyout.classList.remove("is-open");

            const trigger = flyout.querySelector(".admin-view-mode-flyout-trigger");
            if (trigger) {
                trigger.setAttribute("aria-expanded", "false");
            }
        });
    }

    function positionAdminViewModeFlyouts() {
        const flyouts = document.querySelectorAll(".admin-view-mode-flyout");

        flyouts.forEach((flyout) => {
            flyout.classList.remove("open-left");

            const submenu = flyout.querySelector(".admin-view-mode-submenu");
            if (!submenu) return;

            const flyoutRect = flyout.getBoundingClientRect();
            const submenuWidth = submenu.offsetWidth || 240;
            const viewportWidth = window.innerWidth || document.documentElement.clientWidth;

            const wouldOverflowRight = flyoutRect.right + submenuWidth > viewportWidth - 12;

            if (wouldOverflowRight) {
                flyout.classList.add("open-left");
            }
        });
    }

    function openAdminViewModeFlyout(flyout) {
        closeAdminViewModeFlyouts(flyout);

        flyout.classList.add("is-open");

        const trigger = flyout.querySelector(".admin-view-mode-flyout-trigger");
        if (trigger) {
            trigger.setAttribute("aria-expanded", "true");
        }

        positionAdminViewModeFlyouts();
    }

    function toggleAdminViewModeFlyout(flyout) {
        if (flyout.classList.contains("is-open")) {
            closeAdminViewModeFlyouts();
            return;
        }

        openAdminViewModeFlyout(flyout);
    }

    function setupAdminViewModeFlyouts() {
        const flyouts = document.querySelectorAll(".admin-view-mode-flyout");

        flyouts.forEach((flyout) => {
            const trigger = flyout.querySelector(".admin-view-mode-flyout-trigger");
            const submenu = flyout.querySelector(".admin-view-mode-submenu");

            if (!trigger || !submenu) {
                return;
            }

            trigger.addEventListener("click", (event) => {
                event.preventDefault();
                event.stopPropagation();

                toggleAdminViewModeFlyout(flyout);
            });

            submenu.addEventListener("click", (event) => {
                event.stopPropagation();
            });
        });
    }

    document.addEventListener("click", (event) => {
        if (event.target.closest(".admin-view-mode-flyout")) {
            return;
        }

        closeAdminViewModeFlyouts();
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            closeAdminViewModeFlyouts();
        }
    });

    window.addEventListener("resize", positionAdminViewModeFlyouts);

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", setupAdminViewModeFlyouts);
    } else {
        setupAdminViewModeFlyouts();
    }
})();