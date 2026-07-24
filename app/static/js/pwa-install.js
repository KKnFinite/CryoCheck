(() => {
  const installActions = Array.from(
    document.querySelectorAll("[data-install-action]"),
  );
  const iosInstructions = document.querySelector(
    "[data-ios-install-instructions]",
  );
  const iosCloseControls = Array.from(
    document.querySelectorAll("[data-ios-install-close]"),
  );
  let deferredInstallPrompt = null;
  let previousFocus = null;

  const isStandalone = (
    window.matchMedia("(display-mode: standalone)").matches
    || window.navigator.standalone === true
  );
  const isIos = (
    /iPhone|iPad|iPod/i.test(window.navigator.userAgent)
    || (
      window.navigator.platform === "MacIntel"
      && window.navigator.maxTouchPoints > 1
    )
  );

  document.documentElement.classList.toggle(
    "pwa-standalone",
    isStandalone,
  );

  const setInstallVisibility = (isVisible) => {
    for (const action of installActions) {
      action.hidden = !isVisible || isStandalone;
    }
  };

  const closeIosInstructions = () => {
    if (!iosInstructions) {
      return;
    }
    iosInstructions.hidden = true;
    document.body.classList.remove("install-sheet-open");
    if (previousFocus instanceof HTMLElement) {
      previousFocus.focus();
    }
  };

  const showIosInstructions = () => {
    if (!iosInstructions) {
      return;
    }
    previousFocus = document.activeElement;
    iosInstructions.hidden = false;
    document.body.classList.add("install-sheet-open");
    const primaryClose = iosInstructions.querySelector(
      ".ios-install-sheet__panel [data-ios-install-close]",
    );
    if (primaryClose) {
      primaryClose.focus();
    }
  };

  for (const closeControl of iosCloseControls) {
    closeControl.addEventListener("click", closeIosInstructions);
  }

  for (const action of installActions) {
    action.addEventListener("click", async () => {
      const menuClose = document.querySelector("[data-mobile-menu-close]");
      if (menuClose) {
        menuClose.click();
      }
      if (isIos) {
        showIosInstructions();
        return;
      }
      if (!deferredInstallPrompt) {
        return;
      }
      deferredInstallPrompt.prompt();
      await deferredInstallPrompt.userChoice;
      deferredInstallPrompt = null;
      setInstallVisibility(false);
    });
  }

  document.addEventListener("keydown", (event) => {
    if (
      event.key === "Escape"
      && iosInstructions
      && !iosInstructions.hidden
    ) {
      closeIosInstructions();
    }
  });

  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferredInstallPrompt = event;
    setInstallVisibility(true);
  });

  window.addEventListener("appinstalled", () => {
    deferredInstallPrompt = null;
    setInstallVisibility(false);
  });

  if (isIos && !isStandalone) {
    setInstallVisibility(true);
  } else {
    setInstallVisibility(false);
  }

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("/service-worker.js", {
        scope: "/",
      });
    });
  }
})();
