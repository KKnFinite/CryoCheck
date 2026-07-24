(() => {
  const form = document.querySelector("[data-export-form]");
  if (!form) {
    return;
  }

  const checkboxes = Array.from(
    form.querySelectorAll("[data-exception-checkbox]"),
  );
  const selectAll = form.querySelector("[data-select-all]");
  const clearAll = form.querySelector("[data-clear-all]");
  const exportSelected = form.querySelector("[data-export-selected]");
  const status = form.querySelector("[data-selection-status]");

  const updateSelectionState = () => {
    const selectedCount = checkboxes.filter(
      (checkbox) => checkbox.checked,
    ).length;
    exportSelected.disabled = selectedCount === 0;
    status.textContent = `${selectedCount} of ${checkboxes.length} selected`;
  };

  selectAll.addEventListener("click", () => {
    for (const checkbox of checkboxes) {
      checkbox.checked = true;
    }
    updateSelectionState();
  });

  clearAll.addEventListener("click", () => {
    for (const checkbox of checkboxes) {
      checkbox.checked = false;
    }
    updateSelectionState();
  });

  form.addEventListener("change", (event) => {
    if (event.target.matches("[data-exception-checkbox]")) {
      updateSelectionState();
    }
  });

  updateSelectionState();
})();
