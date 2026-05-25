(function () {
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

    document.addEventListener("mouseover", (event) => {
        if (event.target.closest(".admin-view-mode-flyout")) {
            positionAdminViewModeFlyouts();
        }
    });

    document.addEventListener("focusin", (event) => {
        if (event.target.closest(".admin-view-mode-flyout")) {
            positionAdminViewModeFlyouts();
        }
    });

    window.addEventListener("resize", positionAdminViewModeFlyouts);
})();