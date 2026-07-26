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
  const exportAllControls = Array.from(
    form.querySelectorAll("[data-export-all]"),
  );
  const exportControls = [
    ...exportSelectedControls,
    ...exportAllControls,
  ];
  const statuses = Array.from(
    form.querySelectorAll("[data-selection-status]"),
  );
  const feedbackRegions = Array.from(
    form.querySelectorAll("[data-export-feedback]"),
  );
  let exportInProgress = false;
  let feedbackTimer;
  let lastSubmitter;

  const selectedCount = () => (
    checkboxes.filter((checkbox) => checkbox.checked).length
  );

  const updateSelectionState = () => {
    const count = selectedCount();
    for (const checkbox of checkboxes) {
      checkbox.disabled = exportInProgress;
    }
    for (const control of selectAllControls) {
      control.disabled = exportInProgress;
    }
    for (const control of clearAllControls) {
      control.disabled = exportInProgress;
    }
    for (const control of exportSelectedControls) {
      control.disabled = exportInProgress || count === 0;
    }
    for (const control of exportAllControls) {
      control.disabled = exportInProgress;
    }
    for (const status of statuses) {
      status.textContent = `${count} of ${checkboxes.length} selected`;
    }
  };

  const showFeedback = (state, message) => {
    window.clearTimeout(feedbackTimer);
    for (const region of feedbackRegions) {
      region.hidden = false;
      region.dataset.state = state;
      const messageElement = region.querySelector(
        "[data-export-feedback-message]",
      );
      if (messageElement) {
        messageElement.textContent = message;
      }
    }
  };

  const hideFeedback = () => {
    for (const region of feedbackRegions) {
      region.hidden = true;
      delete region.dataset.state;
    }
  };

  const finishExport = (state, message) => {
    exportInProgress = false;
    updateSelectionState();
    showFeedback(state, message);
    if (state === "success") {
      feedbackTimer = window.setTimeout(hideFeedback, 3500);
    }
  };

  const isIOSBrowser = () => (
    /iPad|iPhone|iPod/.test(window.navigator.userAgent)
    || (
      window.navigator.platform === "MacIntel"
      && window.navigator.maxTouchPoints > 1
    )
  );

  const exportFilename = (response) => {
    const disposition = response.headers.get("Content-Disposition") || "";
    const encodedMatch = disposition.match(/filename\*=UTF-8''([^;]+)/i);
    if (encodedMatch) {
      return decodeURIComponent(encodedMatch[1].replace(/^"|"$/g, ""));
    }
    const filenameMatch = disposition.match(/filename="?([^";]+)"?/i);
    return filenameMatch ? filenameMatch[1] : "CryoCheck_Exceptions.xlsx";
  };

  const prepareIOSContext = () => {
    if (!isIOSBrowser()) {
      return null;
    }
    const downloadContext = window.open("", "_blank");
    if (!downloadContext) {
      return false;
    }
    downloadContext.document.title = "CryoCheck Excel Export";
    downloadContext.document.body.textContent = "Preparing Excel\u2026";
    return downloadContext;
  };

  const deliverWorkbook = (blob, filename, downloadContext) => {
    const objectUrl = URL.createObjectURL(blob);
    if (downloadContext) {
      downloadContext.location.replace(objectUrl);
    } else {
      const downloadLink = document.createElement("a");
      downloadLink.href = objectUrl;
      downloadLink.download = filename;
      downloadLink.hidden = true;
      document.body.append(downloadLink);
      downloadLink.click();
      downloadLink.remove();
    }
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60000);
  };

  for (const selectAll of selectAllControls) {
    selectAll.addEventListener("click", () => {
      if (exportInProgress) {
        return;
      }
      for (const checkbox of checkboxes) {
        checkbox.checked = true;
      }
      updateSelectionState();
    });
  }

  for (const clearAll of clearAllControls) {
    clearAll.addEventListener("click", () => {
      if (exportInProgress) {
        return;
      }
      for (const checkbox of checkboxes) {
        checkbox.checked = false;
      }
      updateSelectionState();
    });
  }

  for (const control of exportControls) {
    control.addEventListener("click", () => {
      lastSubmitter = control;
    });
  }

  form.addEventListener("change", (event) => {
    if (event.target.matches("[data-exception-checkbox]")) {
      updateSelectionState();
    }
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (exportInProgress) {
      return;
    }

    const submitter = event.submitter || lastSubmitter;
    const scope = submitter ? submitter.value : "";
    if (!["selected", "all"].includes(scope)) {
      showFeedback("error", "Choose an export option and try again.");
      return;
    }
    if (scope === "selected" && selectedCount() === 0) {
      showFeedback("error", "Select at least one exception to export.");
      return;
    }

    const formData = new FormData(form);
    formData.set("scope", scope);
    exportInProgress = true;
    updateSelectionState();
    showFeedback("loading", "Preparing Excel\u2026");

    const downloadContext = prepareIOSContext();
    if (downloadContext === false) {
      finishExport(
        "error",
        "Safari blocked the download window. Allow pop-ups and try again.",
      );
      return;
    }

    try {
      const response = await fetch(form.action, {
        method: "POST",
        body: formData,
        credentials: "same-origin",
        cache: "no-store",
        headers: {
          Accept: (
            "application/vnd.openxmlformats-officedocument."
            + "spreadsheetml.sheet"
          ),
        },
      });
      if (!response.ok) {
        throw new Error(`Export failed with status ${response.status}`);
      }

      const workbook = await response.blob();
      if (workbook.size === 0) {
        throw new Error("Export returned an empty workbook");
      }
      deliverWorkbook(
        workbook,
        exportFilename(response),
        downloadContext,
      );
      finishExport("success", "Excel export ready.");
    } catch (error) {
      if (downloadContext) {
        downloadContext.close();
      }
      finishExport(
        "error",
        "Excel could not be prepared. Check your connection and try again.",
      );
    }
  });

  updateSelectionState();
})();
