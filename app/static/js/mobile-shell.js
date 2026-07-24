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

  const appendDefinition = (list, label, value) => {
    const group = createElement("div");
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
        desktopSummary.querySelectorAll(".exception-card__field"),
      );
      const desktopMessage = desktopSummary.querySelector(
        ".exception-card__message",
      );
      const desktopDetails = card.querySelector(":scope > .exception-details");
      if (fields.length < 4 || !desktopMessage || !desktopDetails) {
        continue;
      }

      const identity = createElement(
        "div",
        "mobile-exception-card__identity",
      );
      for (const fieldIndex of [0, 3]) {
        const field = fields[fieldIndex];
        const group = createElement("div");
        group.append(
          createElement("span", "", normalizedText(field.querySelector("span"))),
          createElement("strong", "", normalizedText(field.querySelector(":scope > strong"))),
        );
        const small = field.querySelector("small");
        if (small) {
          group.append(createElement("small", "", normalizedText(small)));
        }
        identity.append(group);
      }

      const metadata = createElement(
        "dl",
        "mobile-exception-card__meta",
      );
      for (const fieldIndex of [1, 2]) {
        const field = fields[fieldIndex];
        appendDefinition(
          metadata,
          normalizedText(field.querySelector("span")),
          normalizedText(field.querySelector("strong")),
        );
      }

      const message = createElement(
        "div",
        "mobile-exception-card__message",
      );
      message.append(
        createElement(
          "span",
          "",
          normalizedText(desktopMessage.querySelector("span")),
        ),
        createElement(
          "h3",
          "",
          normalizedText(desktopMessage.querySelector("h3")),
        ),
      );

      const details = createElement(
        "dl",
        "mobile-exception-card__details",
      );
      details.setAttribute("aria-label", "Mobile rule-relevant details");
      for (const sourceDetail of desktopDetails.children) {
        appendDefinition(
          details,
          normalizedText(sourceDetail.querySelector("dt")),
          normalizedText(sourceDetail.querySelector("dd")),
        );
      }
      target.replaceChildren(identity, metadata, message, details);
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
      if (fields.length < 3 || !message) {
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
        "CSV row",
        normalizedText(fields[0].querySelector("small")).replace(
          /^CSV row\s*/i,
          "",
        ),
      );
      appendDefinition(
        definitions,
        normalizedText(fields[1].querySelector("span")),
        normalizedText(fields[1].querySelector("strong")),
      );
      appendDefinition(
        definitions,
        normalizedText(fields[2].querySelector("span")),
        normalizedText(fields[2].querySelector("strong")),
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
      summary.append(
        identity,
        createElement(
          "span",
          "mobile-rule__status",
          normalizedText(card.querySelector(".rule-card__status")),
        ),
      );

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
