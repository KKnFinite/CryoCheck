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
  let nativeFinishTimer;
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
    window.clearTimeout(nativeFinishTimer);
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
    downloadContext.name = `cryocheck-export-${Date.now()}`;
    return downloadContext;
  };

  const serverErrorMessage = async (response) => {
    const fallbackMessages = {
      400: (
        "CryoCheck rejected the export request. "
        + "Refresh Results and try again."
      ),
      403: (
        "CryoCheck could not authorize this export. "
        + "Refresh Results and try again."
      ),
      413: (
        "This export request is too large. "
        + "Import a smaller CSV and try again."
      ),
    };
    const fallback = (
      fallbackMessages[response.status]
      || (
        response.status >= 500
          ? (
            `CryoCheck could not prepare Excel (server error `
            + `${response.status}). Try again.`
          )
          : `Excel export failed (HTTP ${response.status}).`
      )
    );

    try {
      const contentType = response.headers.get("Content-Type") || "";
      if (contentType.includes("application/json")) {
        const payload = await response.json();
        return payload.error || payload.message || fallback;
      }
      const responseBody = await response.text();
      const errorDocument = new DOMParser().parseFromString(
        responseBody,
        "text/html",
      );
      const detail = errorDocument.querySelector(
        "[data-export-error-message]",
      );
      if (detail && detail.textContent.trim()) {
        return detail.textContent.trim();
      }
      const title = errorDocument.querySelector("#error-title");
      if (title && title.textContent.trim()) {
        return `${title.textContent.trim()}. ${fallback}`;
      }
    } catch (error) {
      // Fall through to the status-specific message.
    }
    return fallback;
  };

  const submitNativeDownload = (formData, downloadContext) => {
    if (
      !downloadContext
      || downloadContext.closed
      || !downloadContext.name
    ) {
      throw new Error("The Safari download window is unavailable");
    }

    const nativeForm = document.createElement("form");
    nativeForm.action = form.action;
    nativeForm.method = "post";
    nativeForm.target = downloadContext.name;
    nativeForm.hidden = true;
    formData.forEach((value, name) => {
      if (typeof value !== "string") {
        return;
      }
      const field = document.createElement("input");
      field.type = "hidden";
      field.name = name;
      field.value = value;
      nativeForm.append(field);
    });
    document.body.append(nativeForm);
    nativeForm.submit();
    nativeForm.remove();
  };

  const startNativeDownload = (
    formData,
    downloadContext,
    successMessage,
  ) => {
    formData.set("delivery", "native");
    try {
      submitNativeDownload(formData, downloadContext);
    } catch (error) {
      if (downloadContext && !downloadContext.closed) {
        downloadContext.close();
      }
      finishExport(
        "error",
        (
          "Safari could not open the secure Excel download. "
          + "Allow pop-ups and try again."
        ),
      );
      return;
    }
    nativeFinishTimer = window.setTimeout(() => {
      finishExport("success", successMessage);
    }, 1500);
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

    const iosDownload = Boolean(downloadContext);
    const requestData = new FormData();
    formData.forEach((value, name) => {
      requestData.append(name, value);
    });
    if (iosDownload) {
      requestData.set("delivery", "validate");
    }

    let response;
    try {
      response = await fetch(form.action, {
        method: "POST",
        body: requestData,
        credentials: "same-origin",
        cache: "no-store",
        headers: {
          Accept: (
            iosDownload
              ? "application/json"
              : (
                "application/vnd.openxmlformats-officedocument."
                + "spreadsheetml.sheet"
              )
          ),
        },
      });
    } catch (error) {
      if (iosDownload) {
        startNativeDownload(
          formData,
          downloadContext,
          (
            "Safari opened the secure Excel download directly. "
            + "If it does not appear, check your connection and try again."
          ),
        );
        return;
      }
      finishExport(
        "error",
        (
          "CryoCheck could not reach the export service. "
          + "Check your connection and try again."
        ),
      );
      return;
    }

    if (!response.ok) {
      if (downloadContext) {
        downloadContext.close();
      }
      finishExport("error", await serverErrorMessage(response));
      return;
    }

    if (iosDownload) {
      try {
        const validation = await response.json();
        if (!validation.ok) {
          throw new Error("CryoCheck did not approve the export");
        }
      } catch (error) {
        startNativeDownload(
          formData,
          downloadContext,
          "Safari opened the secure Excel download directly.",
        );
        return;
      }
      startNativeDownload(
        formData,
        downloadContext,
        "Excel download opened in Safari.",
      );
      return;
    }

    const contentType = response.headers.get("Content-Type") || "";
    if (!contentType.includes(
      "application/vnd.openxmlformats-officedocument."
      + "spreadsheetml.sheet",
    )) {
      finishExport(
        "error",
        "CryoCheck returned an unexpected export response. Try again.",
      );
      return;
    }

    let workbook;
    try {
      workbook = await response.blob();
    } catch (error) {
      finishExport(
        "error",
        (
          "Excel was prepared, but this browser could not read the download. "
          + "Try again or use the browser download menu."
        ),
      );
      return;
    }
    if (workbook.size === 0) {
      finishExport(
        "error",
        "CryoCheck returned an empty workbook. Try the export again.",
      );
      return;
    }

    try {
      deliverWorkbook(
        workbook,
        exportFilename(response),
        downloadContext,
      );
      finishExport("success", "Excel export ready.");
    } catch (error) {
      finishExport(
        "error",
        (
          "Excel was prepared, but the browser could not start the download. "
          + "Check download permissions and try again."
        ),
      );
    }
  });

  updateSelectionState();
})();
