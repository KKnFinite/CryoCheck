(() => {
  const createElement = (tagName, className, text) => {
    const element = document.createElement(tagName);
    if (className) {
      element.className = className;
    }
    if (text !== undefined) {
      element.textContent = text;
    }
    return element;
  };

  const normalizedText = (element) => (
    element ? element.textContent.trim().replace(/\s+/g, " ") : ""
  );

  const appendDefinition = (list, label, value, valueKind = "") => {
    const group = createElement("div");
    if (valueKind) {
      group.dataset.displayKind = valueKind;
    }
    if (valueKind === "invalid") {
      group.classList.add("result-detail--invalid");
    }
    group.append(
      createElement("dt", "", label),
      createElement("dd", "", value),
    );
    list.append(group);
  };

  const hydrateMobileExceptions = () => {
    for (const card of document.querySelectorAll("[data-exception-card]")) {
      const target = card.querySelector("[data-mobile-exception-content]");
      const desktopSummary = card.querySelector(
        ".exception-card__desktop-summary",
      );
      if (!target || !desktopSummary) {
        continue;
      }
      const fields = Array.from(
        desktopSummary.querySelectorAll(
          ".exception-card__identity .exception-card__field",
        ),
      );
      const desktopMessage = desktopSummary.querySelector(
        ".exception-card__message",
      );
      const desktopDetails = card.querySelector(":scope > .exception-details");
      if (fields.length < 2 || !desktopMessage || !desktopDetails) {
        continue;
      }

      const identity = createElement(
        "dl",
        "mobile-exception-card__identity",
      );
      for (const field of fields) {
        appendDefinition(
          identity,
          normalizedText(field.querySelector("dt")),
          normalizedText(field.querySelector("dd")),
          field.dataset.displayKind || "",
        );
      }

      const message = createElement(
        "h3",
        "mobile-exception-card__message",
        normalizedText(desktopMessage.querySelector("h3")),
      );
      const ruleDetails = createElement(
        "dl",
        "mobile-exception-card__details",
      );
      for (const detail of desktopDetails.children) {
        appendDefinition(
          ruleDetails,
          normalizedText(detail.querySelector("dt")),
          normalizedText(detail.querySelector("dd")),
          detail.dataset.displayKind || "",
        );
      }
      target.replaceChildren(message, identity, ruleDetails);
    }
  };

  const hydrateMobileWarnings = () => {
    const target = document.querySelector("[data-mobile-warning-list]");
    if (!target) {
      return;
    }
    for (const warning of document.querySelectorAll(".audit-warning-card")) {
      const fields = Array.from(
        warning.querySelectorAll(".audit-warning-card__field"),
      );
      const message = warning.querySelector(".audit-warning-card__message");
      if (fields.length < 2 || !message) {
        continue;
      }
      const item = createElement("li");
      const definitions = createElement("dl");
      appendDefinition(
        definitions,
        normalizedText(fields[0].querySelector("span")),
        normalizedText(fields[0].querySelector("strong")),
      );
      appendDefinition(
        definitions,
        normalizedText(fields[1].querySelector("span")),
        normalizedText(fields[1].querySelector("strong")),
      );
      item.append(
        definitions,
        createElement("p", "", normalizedText(message)),
      );
      target.append(item);
    }
  };

  const hydrateMobilePreview = () => {
    const target = document.querySelector("[data-mobile-preview-list]");
    const table = document.querySelector(".preview-table");
    if (!target || !table) {
      return;
    }
    const headings = Array.from(table.querySelectorAll("thead th"))
      .map(normalizedText);
    for (const row of table.querySelectorAll("tbody tr")) {
      const item = createElement("li");
      const definitions = createElement("dl");
      Array.from(row.querySelectorAll("td")).forEach((cell, index) => {
        appendDefinition(
          definitions,
          headings[index] || "Value",
          normalizedText(cell),
        );
      });
      item.append(definitions);
      target.append(item);
    }
  };

  const hydrateMobileRules = () => {
    const target = document.querySelector("[data-mobile-rules-list]");
    if (!target) {
      return;
    }
    for (const card of document.querySelectorAll(
      ".rules-list--desktop .rule-card",
    )) {
      const item = createElement("li");
      const rule = createElement("details", "mobile-rule");
      const summary = createElement("summary");
      const identity = createElement("span", "mobile-rule__identity");
      identity.append(
        createElement(
          "span",
          "",
          normalizedText(card.querySelector(".rule-card__id")),
        ),
        createElement(
          "strong",
          "",
          normalizedText(card.querySelector(".rule-card__identity h2")),
        ),
      );
      summary.append(identity);

      const body = createElement("div", "mobile-rule__body");
      body.append(
        createElement(
          "p",
          "",
          normalizedText(card.querySelector(".rule-card__description")),
        ),
      );
      for (const sourceDetail of card.querySelectorAll(".rule-detail")) {
        const section = createElement("section");
        section.append(
          createElement(
            "h2",
            "",
            normalizedText(sourceDetail.querySelector("h3")),
          ),
        );
        const sourceList = sourceDetail.querySelector("ul");
        if (sourceList) {
          section.append(sourceList.cloneNode(true));
        } else {
          section.append(
            createElement(
              "p",
              "mobile-rule__exception",
              normalizedText(sourceDetail.querySelector("p")),
            ),
          );
        }
        body.append(section);
      }
      rule.append(summary, body);
      item.append(rule);
      target.append(item);
    }
  };

  hydrateMobileExceptions();
  hydrateMobileWarnings();
  hydrateMobilePreview();
  hydrateMobileRules();
  document.documentElement.classList.add("mobile-layout-ready");

  const toggle = document.querySelector("[data-mobile-menu-toggle]");
  const menu = document.querySelector("[data-mobile-menu]");
  const backdrop = document.querySelector("[data-mobile-menu-backdrop]");
  const closeButton = document.querySelector("[data-mobile-menu-close]");
  if (!toggle || !menu || !backdrop || !closeButton) {
    return;
  }

  const closeMenu = () => {
    menu.classList.remove("mobile-menu--open");
    menu.setAttribute("aria-hidden", "true");
    backdrop.hidden = true;
    toggle.setAttribute("aria-expanded", "false");
    toggle.setAttribute("aria-label", "Open menu");
    document.body.classList.remove("mobile-menu-open");
  };

  const openMenu = () => {
    menu.classList.add("mobile-menu--open");
    menu.setAttribute("aria-hidden", "false");
    backdrop.hidden = false;
    toggle.setAttribute("aria-expanded", "true");
    toggle.setAttribute("aria-label", "Close menu");
    document.body.classList.add("mobile-menu-open");
    closeButton.focus();
  };

  toggle.addEventListener("click", () => {
    if (toggle.getAttribute("aria-expanded") === "true") {
      closeMenu();
    } else {
      openMenu();
    }
  });
  closeButton.addEventListener("click", closeMenu);
  backdrop.addEventListener("click", closeMenu);
  menu.addEventListener("click", (event) => {
    if (event.target.closest("a")) {
      closeMenu();
    }
  });
  document.addEventListener("keydown", (event) => {
    if (
      event.key === "Escape"
      && toggle.getAttribute("aria-expanded") === "true"
    ) {
      closeMenu();
      toggle.focus();
    }
  });
})();
