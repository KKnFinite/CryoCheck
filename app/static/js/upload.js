(() => {
  const form = document.querySelector("[data-upload-form]");
  if (!form) {
    return;
  }

  const dropZone = form.querySelector("[data-drop-zone]");
  const fileInput = form.querySelector("[data-file-input]");
  const fileStatus = form.querySelector("[data-file-status]");
  const replaceFile = form.querySelector("[data-replace-file]");
  const submitButton = form.querySelector("[data-submit-button]");
  const validationState = form.querySelector("[data-validation-state]");
  const phoneLayout = window.matchMedia("(max-width: 47.99rem)");
  let automaticSubmitTimer;
  let isSubmitting = false;

  const showStatus = (message, isError = false) => {
    fileStatus.textContent = message;
    fileStatus.classList.toggle("file-selection--error", isError);
  };

  const resetSelection = () => {
    window.clearTimeout(automaticSubmitTimer);
    fileInput.value = "";
    replaceFile.hidden = true;
    validationState.hidden = true;
    submitButton.disabled = false;
    form.removeAttribute("aria-busy");
    dropZone.classList.remove("upload-dropzone--validating");
    isSubmitting = false;
    showStatus("No file selected");
  };

  const beginValidation = () => {
    if (isSubmitting) {
      return false;
    }
    isSubmitting = true;
    window.clearTimeout(automaticSubmitTimer);
    replaceFile.hidden = true;
    validationState.hidden = false;
    submitButton.disabled = true;
    dropZone.classList.add("upload-dropzone--validating");
    form.setAttribute("aria-busy", "true");
    return true;
  };

  const validateFile = (file) => {
    if (!file.name.toLowerCase().endsWith(".csv")) {
      fileInput.value = "";
      replaceFile.hidden = true;
      showStatus("Choose a file with a .csv extension.", true);
      return false;
    }

    showStatus(file.name);
    replaceFile.hidden = !phoneLayout.matches;
    return true;
  };

  const scheduleAutomaticValidation = () => {
    window.clearTimeout(automaticSubmitTimer);
    if (!phoneLayout.matches) {
      return;
    }
    automaticSubmitTimer = window.setTimeout(() => {
      if (!isSubmitting && fileInput.files.length === 1) {
        form.requestSubmit(submitButton);
      }
    }, 450);
  };

  const handleSelectedFile = () => {
    if (fileInput.files.length !== 1) {
      resetSelection();
      return;
    }
    if (validateFile(fileInput.files[0])) {
      scheduleAutomaticValidation();
    }
  };

  fileInput.addEventListener("change", handleSelectedFile);

  replaceFile.addEventListener("click", () => {
    resetSelection();
    fileInput.click();
  });

  form.addEventListener("submit", (event) => {
    if (isSubmitting) {
      event.preventDefault();
      return;
    }
    if (
      fileInput.files.length !== 1
      || !validateFile(fileInput.files[0])
    ) {
      event.preventDefault();
      return;
    }
    beginValidation();
  });

  for (const eventName of ["dragenter", "dragover"]) {
    dropZone.addEventListener(eventName, (event) => {
      event.preventDefault();
      dropZone.classList.add("upload-dropzone--active");
    });
  }

  for (const eventName of ["dragleave", "drop"]) {
    dropZone.addEventListener(eventName, (event) => {
      event.preventDefault();
      dropZone.classList.remove("upload-dropzone--active");
    });
  }

  dropZone.addEventListener("drop", (event) => {
    const files = event.dataTransfer.files;
    if (files.length !== 1) {
      fileInput.value = "";
      showStatus("Drop one CSV file at a time.", true);
      return;
    }

    if (!validateFile(files[0])) {
      return;
    }

    const transfer = new DataTransfer();
    transfer.items.add(files[0]);
    fileInput.files = transfer.files;
    scheduleAutomaticValidation();
  });

  window.addEventListener("pageshow", (event) => {
    if (event.persisted) {
      resetSelection();
    }
  });
})();
