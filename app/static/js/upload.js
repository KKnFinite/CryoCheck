(() => {
  const form = document.querySelector("[data-upload-form]");
  if (!form) {
    return;
  }

  const dropZone = form.querySelector("[data-drop-zone]");
  const fileInput = form.querySelector("[data-file-input]");
  const fileStatus = form.querySelector("[data-file-status]");

  const showStatus = (message, isError = false) => {
    fileStatus.textContent = message;
    fileStatus.classList.toggle("file-selection--error", isError);
  };

  const validateFile = (file) => {
    if (!file.name.toLowerCase().endsWith(".csv")) {
      fileInput.value = "";
      showStatus("Choose a file with a .csv extension.", true);
      return false;
    }

    showStatus(file.name);
    return true;
  };

  fileInput.addEventListener("change", () => {
    if (fileInput.files.length === 1) {
      validateFile(fileInput.files[0]);
    } else {
      showStatus("No file selected");
    }
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
  });
})();
