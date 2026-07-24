(() => {
  const form = document.querySelector("[data-export-form]");
  if (!form) {
    return;
  }

  const checkboxes = Array.from(
    form.querySelectorAll("[data-exception-checkbox]"),
  );
  const selectAllControls = Array.from(
    form.querySelectorAll("[data-select-all]"),
  );
  const clearAllControls = Array.from(
    form.querySelectorAll("[data-clear-all]"),
  );
  const exportSelectedControls = Array.from(
    form.querySelectorAll("[data-export-selected]"),
  );
  const statuses = Array.from(
    form.querySelectorAll("[data-selection-status]"),
  );

  const updateSelectionState = () => {
    const selectedCount = checkboxes.filter(
      (checkbox) => checkbox.checked,
    ).length;
    for (const control of exportSelectedControls) {
      control.disabled = selectedCount === 0;
    }
    for (const status of statuses) {
      status.textContent = `${selectedCount} of ${checkboxes.length} selected`;
    }
  };

  for (const selectAll of selectAllControls) {
    selectAll.addEventListener("click", () => {
      for (const checkbox of checkboxes) {
        checkbox.checked = true;
      }
      updateSelectionState();
    });
  }

  for (const clearAll of clearAllControls) {
    clearAll.addEventListener("click", () => {
      for (const checkbox of checkboxes) {
        checkbox.checked = false;
      }
      updateSelectionState();
    });
  }

  form.addEventListener("change", (event) => {
    if (event.target.matches("[data-exception-checkbox]")) {
      updateSelectionState();
    }
  });

  updateSelectionState();
})();
