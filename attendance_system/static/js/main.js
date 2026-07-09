document.addEventListener('DOMContentLoaded', function () {
    const themeToggle = document.querySelector('.theme-toggle');
    const body = document.body;
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';

    const storedTheme = localStorage.getItem('attendance-theme');
    if (storedTheme) {
        body.setAttribute('data-theme', storedTheme);
    }

    const applyTheme = (theme) => {
        body.setAttribute('data-theme', theme);
        localStorage.setItem('attendance-theme', theme);
        if (themeToggle) {
            const icon = themeToggle.querySelector('i');
            if (icon) icon.className = theme === 'dark' ? 'fa-solid fa-sun' : 'fa-solid fa-moon';
        }
    };

    if (themeToggle) {
        themeToggle.addEventListener('click', function () {
            const currentTheme = body.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
            applyTheme(currentTheme);
            fetch('/settings/theme', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-CSRFToken': csrfToken
                },
                body: `theme=${currentTheme}`
            });
        });
    }

    const form = document.getElementById('markAttendanceForm');
    if (form) {
        form.addEventListener('submit', async function (event) {
            event.preventDefault();
            const formData = new FormData(form);
            const response = await fetch('/attendance/mark', {
                method: 'POST',
                headers: { 'X-CSRFToken': csrfToken },
                body: formData
            });
            const result = await response.json();
            Swal.fire({ icon: result.success ? 'success' : 'warning', title: result.message || 'Done' });
            form.reset();
        });
    }

    const uploadForm = document.getElementById('uploadForm');
    const fileInput = document.getElementById('fileInput');
    const dropZone = document.getElementById('dropZone');
    const progressBar = document.getElementById('uploadProgress');
    const previewBtn = document.getElementById('previewBtn');

    if (uploadForm && fileInput && dropZone) {
        ['dragenter', 'dragover'].forEach(eventName => dropZone.addEventListener(eventName, (event) => {
            event.preventDefault();
            dropZone.classList.add('border-primary');
        }));
        ['dragleave', 'drop'].forEach(eventName => dropZone.addEventListener(eventName, (event) => {
            event.preventDefault();
            dropZone.classList.remove('border-primary');
        }));
        dropZone.addEventListener('drop', (event) => {
            const files = event.dataTransfer.files;
            if (files.length) {
                fileInput.files = files;
            }
        });

        uploadForm.addEventListener('submit', function () {
            const interval = setInterval(() => {
                const currentWidth = parseInt(progressBar.style.width || '0', 10);
                if (currentWidth >= 100) {
                    clearInterval(interval);
                    return;
                }
                progressBar.style.width = `${Math.min(currentWidth + 20, 100)}%`;
            }, 250);
        });
    }

    if (previewBtn && fileInput) {
        previewBtn.addEventListener('click', function () {
            const file = fileInput.files[0];
            if (!file) {
                Swal.fire({ icon: 'warning', title: 'No file selected' });
                return;
            }
            Swal.fire({ icon: 'info', title: file.name, text: `${(file.size / 1024).toFixed(1)} KB` });
        });
    }

    const themeAction = document.getElementById('themeAction');
    if (themeAction) {
        themeAction.addEventListener('click', function () {
            const currentTheme = body.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
            applyTheme(currentTheme);
            Swal.fire({ icon: 'success', title: `Theme switched to ${currentTheme}` });
        });
    }

    const cameraAction = document.getElementById('cameraAction');
    const cameraPreview = document.getElementById('cameraPreview');
    if (cameraAction && cameraPreview) {
        cameraAction.addEventListener('click', async function () {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
                cameraPreview.srcObject = stream;
                Swal.fire({ icon: 'success', title: 'Camera opened' });
            } catch (error) {
                Swal.fire({ icon: 'error', title: 'Camera access denied' });
            }
        });
    }

    const backupAction = document.getElementById('backupAction');
    if (backupAction) {
        backupAction.addEventListener('click', function () {
            Swal.fire({
                title: 'Create backup?',
                text: 'This will create a database backup file.',
                icon: 'warning',
                showCancelButton: true,
                confirmButtonText: 'Yes, backup now',
                cancelButtonText: 'Cancel'
            }).then(async (result) => {
                if (!result.isConfirmed) return;
                const response = await fetch('/settings/backup', {
                    method: 'POST',
                    headers: { 'X-CSRFToken': csrfToken }
                });
                const data = await response.json();
                Swal.fire({ icon: data.success ? 'success' : 'error', title: data.message || 'Backup complete' });
            });
        });
    }

    const restoreForm = document.getElementById('restoreForm');
    if (restoreForm) {
        restoreForm.addEventListener('submit', function (event) {
            event.preventDefault();
            Swal.fire({
                title: 'Restore backup?',
                text: 'This will restore the uploaded backup file.',
                icon: 'warning',
                showCancelButton: true,
                confirmButtonText: 'Yes, restore now',
                cancelButtonText: 'Cancel'
            }).then(async (result) => {
                if (!result.isConfirmed) return;
                const formData = new FormData(restoreForm);
                const response = await fetch('/settings/restore', {
                    method: 'POST',
                    headers: { 'X-CSRFToken': csrfToken },
                    body: formData
                });
                const data = await response.json();
                Swal.fire({ icon: data.success ? 'success' : 'error', title: data.message || 'Restore complete' });
            });
        });
    }
});
