/**
 * ERB Maps - Frontend Interactions & Dynamic Behavior
 */

document.addEventListener('DOMContentLoaded', () => {
    // 1. Mobile Menu Toggle
    const mobileBtn = document.getElementById('btn-mobile-nav');
    const mainNav = document.getElementById('main-nav');
    if (mobileBtn && mainNav) {
        mobileBtn.addEventListener('click', () => {
            mainNav.classList.toggle('open');
            mobileBtn.setAttribute('aria-expanded', String(mainNav.classList.contains('open')));
        });
    }

    // 2. Drag & Drop File Upload Handler
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const fileInfo = document.getElementById('file-info');
    const fileNameDisplay = document.getElementById('file-name-display');
    const fileSizeDisplay = document.getElementById('file-size-display');
    const sheetGroup = document.getElementById('sheet-selection-group');
    const sheetSelect = document.getElementById('sheet_name');
    const uploadForm = document.getElementById('upload-form');
    const uploadSpinner = document.getElementById('upload-spinner');
    const btnSubmit = document.getElementById('btn-submit-upload');

    if (dropZone && fileInput) {
        // Drag over / leave effects
        ['dragenter', 'dragover'].forEach(eventName => {
            dropZone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropZone.classList.add('dragover');
            }, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropZone.classList.remove('dragover');
            }, false);
        });

        // Drop file
        dropZone.addEventListener('drop', (e) => {
            const dt = e.dataTransfer;
            const files = dt.files;
            if (files && files.length > 0) {
                fileInput.files = files;
                handleFileSelected(files[0]);
            }
        });

        // File input change
        fileInput.addEventListener('change', () => {
            if (fileInput.files && fileInput.files.length > 0) {
                handleFileSelected(fileInput.files[0]);
            }
        });
    }

    function formatBytes(bytes, decimals = 2) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const dm = decimals < 0 ? 0 : decimals;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
    }

    async function handleFileSelected(file) {
        if (!file) return;

        // Atualizar display
        if (fileInfo && fileNameDisplay && fileSizeDisplay) {
            fileNameDisplay.innerText = file.name;
            fileSizeDisplay.innerText = formatBytes(file.size);
            fileInfo.style.display = 'flex';
        }

        // Tentar obter as abas via AJAX
        if (sheetGroup && sheetSelect) {
            const formData = new FormData();
            formData.append('file', file);

            try {
                const res = await fetch('/upload/sheets', {
                    method: 'POST',
                    body: formData
                });
                const data = await res.json();
                
                if (data.success && data.sheets && data.sheets.length > 1) {
                    sheetSelect.innerHTML = '<option value="">-- Primeira Aba (Padrão) --</option>';
                    data.sheets.forEach(sheet => {
                        const opt = document.createElement('option');
                        opt.value = sheet;
                        opt.textContent = sheet;
                        sheetSelect.appendChild(opt);
                    });
                    sheetGroup.style.display = 'block';
                } else {
                    sheetGroup.style.display = 'none';
                }
            } catch (err) {
                console.warn('Não foi possível carregar as abas dinamicamente:', err);
                sheetGroup.style.display = 'none';
            }
        }
    }

    // Spinner no submit
    if (uploadForm && btnSubmit && uploadSpinner) {
        uploadForm.addEventListener('submit', () => {
            btnSubmit.disabled = true;
            uploadSpinner.style.display = 'inline-block';
            const btnText = btnSubmit.querySelector('.btn-text');
            if (btnText) {
                btnText.textContent = 'Processando Planilha...';
            }
        });
    }
});
