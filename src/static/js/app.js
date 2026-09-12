/**
 * Loan Easier - Split-Screen HITL Verification Web Application Controller
 * Handles document ingestion, image viewport (pan/zoom/rotate),
 * field confidence evaluation & visual warning highlighting (< 0.80),
 * manual edit tracking, verification persistence, and PDF/CSV export.
 */

(function () {
    'use strict';

    // =========================================================================
    // Application State
    // =========================================================================
    const state = {
        currentLoanId: null,
        currentLoanData: null,
        currentProjectType: 'loan',
        originalValues: {},
        editedFields: new Set(),
        // Batch Tabular State
        isTabularMode: false,
        currentBatchId: null,
        batchRows: [],
        originalBatchRows: [],
        deletedRowIds: [],
        batchEngine: null,
        batchVerified: false,
        viewer: {
            scale: 1.0,
            translateX: 0,
            translateY: 0,
            rotation: 0,
            isDragging: false,
            startX: 0,
            startY: 0,
            panEnabled: true,
            naturalWidth: 0,
            naturalHeight: 0
        },
        confidenceThreshold: 0.80 // Fields with confidence < 0.80 marked low confidence
    };

    // =========================================================================
    // DOM Elements Mapping
    // =========================================================================
    const DOM = {
        // Dropzone & File Input
        dropzone: document.getElementById('dropzone'),
        fileInput: document.getElementById('file-input'),
        btnBrowse: document.getElementById('btn-browse'),
        btnQuickSample: document.getElementById('btn-quick-sample'),
        btnQuickSampleTabular: document.getElementById('btn-quick-sample-tabular'),

        // Dual Mode Tabs & Panes
        viewModeTabs: document.getElementById('view-mode-tabs'),
        tabBatchGrid: document.getElementById('tab-batch-grid'),
        tabSingleForm: document.getElementById('tab-single-form'),
        tabGridCountBadge: document.getElementById('tab-grid-count-badge'),
        singleFormContainer: document.getElementById('single-form-container'),
        dataGridContainer: document.getElementById('data-grid-container'),
        singleRecordView: document.getElementById('single-record-view'),
        batchGridView: document.getElementById('batch-grid-view'),
        paneHeaderIcon: document.getElementById('pane-header-icon'),
        paneHeaderText: document.getElementById('pane-header-text'),

        // Batch Status & Summary Bar
        batchStatusBanner: document.getElementById('batch-status-banner'),
        batchStatRecords: document.getElementById('batch-stat-records'),
        batchStatAmount: document.getElementById('batch-stat-amount'),
        batchStatLowConf: document.getElementById('batch-stat-low-conf'),
        batchEngineBadge: document.getElementById('batch-engine-badge'),
        batchFallbackAlert: document.getElementById('batch-fallback-alert'),
        batchFallbackReasonText: document.getElementById('batch-fallback-reason-text'),

        // Batch Grid Controls & Table
        btnAddGridRow: document.getElementById('btn-add-grid-row'),
        btnResetBatch: document.getElementById('btn-reset-batch'),
        gridStatusInfo: document.getElementById('grid-status-info'),
        batchGridTable: document.getElementById('batch-grid-table'),
        batchGridTbody: document.getElementById('batch-grid-tbody'),
        gridEmptyRow: document.getElementById('grid-empty-row'),
        gridFooterTotalAmount: document.getElementById('grid-footer-total-amount'),

        // Batch Action & Export Buttons
        btnSaveBatch: document.getElementById('btn-save-batch'),
        btnExportBatchCsv: document.getElementById('btn-export-batch-csv'),
        btnExportBatchExcel: document.getElementById('btn-export-batch-excel'),
        btnExportBatchPdf: document.getElementById('btn-export-batch-pdf'),
        btnExportBatchZip: document.getElementById('btn-export-batch-zip'),

        // Batch Telemetry
        batchTelemetryDetails: document.getElementById('batch-telemetry-details'),
        batchTelemetryId: document.getElementById('batch-telemetry-id'),
        batchTelemetryTime: document.getElementById('batch-telemetry-time'),
        batchTelemetryImgpath: document.getElementById('batch-telemetry-imgpath'),
        batchTelemetryRawText: document.getElementById('batch-telemetry-raw-text'),

        // Document Viewer
        viewerPane: document.getElementById('viewer-pane'),
        btnToggleViewer: document.getElementById('btn-toggle-viewer'),
        viewerFilename: document.getElementById('viewer-filename'),
        viewportContainer: document.getElementById('viewport-container'),
        viewportEmpty: document.getElementById('viewport-empty'),
        transformLayer: document.getElementById('transform-layer'),
        documentImage: document.getElementById('document-image'),
        viewerLoading: document.getElementById('viewer-loading'),
        zoomScaleText: document.getElementById('zoom-scale-text'),

        // Viewer Toolbar Controls
        btnZoomIn: document.getElementById('btn-zoom-in'),
        btnZoomOut: document.getElementById('btn-zoom-out'),
        btnZoomFit: document.getElementById('btn-zoom-fit'),
        btnZoomActual: document.getElementById('btn-zoom-actual'),
        btnRotate: document.getElementById('btn-rotate'),
        btnPanMode: document.getElementById('btn-pan-mode'),
        btnResetView: document.getElementById('btn-reset-view'),

        // Verification Form & Status
        verificationStateBadge: document.getElementById('verification-state-badge'),
        recordIdBadge: document.getElementById('record-id-badge'),
        engineBadge: document.getElementById('engine-badge'),
        overallConfidenceScore: document.getElementById('overall-confidence-score'),
        overallConfidenceBar: document.getElementById('overall-confidence-bar'),
        fallbackAlert: document.getElementById('fallback-alert'),
        fallbackReasonText: document.getElementById('fallback-reason-text'),

        // Form & Inputs
        form: document.getElementById('loan-verification-form'),
        inputSerialNumber: document.getElementById('input-serial-number'),
        inputName: document.getElementById('input-name'),
        inputMobile: document.getElementById('input-mobile'),
        inputAddress: document.getElementById('input-address'),
        inputAmount: document.getElementById('input-amount'),

        // Form Groups & Badges
        groupSerialNumber: document.getElementById('group-serial-number'),
        groupName: document.getElementById('group-name'),
        groupMobile: document.getElementById('group-mobile'),
        groupAddress: document.getElementById('group-address'),
        groupAmount: document.getElementById('group-amount'),

        badgeSerialNumber: document.getElementById('badge-serial-number'),
        badgeName: document.getElementById('badge-name'),
        badgeMobile: document.getElementById('badge-mobile'),
        badgeAddress: document.getElementById('badge-address'),
        badgeAmount: document.getElementById('badge-amount'),

        // Buttons
        btnSaveVerify: document.getElementById('btn-save-verify'),
        btnDownloadPdf: document.getElementById('btn-download-pdf'),
        btnResetForm: document.getElementById('btn-reset-form'),

        // Telemetry
        telemetryDetails: document.getElementById('telemetry-details'),
        telemetryTime: document.getElementById('telemetry-time'),
        telemetryImgpath: document.getElementById('telemetry-imgpath'),
        telemetryRawText: document.getElementById('telemetry-raw-text'),

        // Modals
        modalExportBackdrop: document.getElementById('modal-export-backdrop'),
        btnOpenExport: document.getElementById('btn-open-export'),
        btnCloseExportModal: document.getElementById('btn-close-export-modal'),
        btnCancelExportModal: document.getElementById('btn-cancel-export-modal'),
        exportMonthInput: document.getElementById('export-month-input'),
        btnRunCsvExport: document.getElementById('btn-run-csv-export'),
        btnRunExcelExport: document.getElementById('btn-run-excel-export'),

        modalRecentBackdrop: document.getElementById('modal-recent-backdrop'),
        btnOpenRecent: document.getElementById('btn-open-recent'),
        btnCloseRecentModal: document.getElementById('btn-close-recent-modal'),
        btnCancelRecentModal: document.getElementById('btn-cancel-recent-modal'),
        btnRefreshRecent: document.getElementById('btn-refresh-recent'),
        recentRecordsTbody: document.getElementById('recent-records-tbody'),

        // Toast
        toastContainer: document.getElementById('toast-container')
    };

    // Attribute mapping dictionary
    const FIELD_MAP = {
        serial_number: {
            input: DOM.inputSerialNumber,
            group: DOM.groupSerialNumber,
            badge: DOM.badgeSerialNumber,
            label: 'Serial Number'
        },
        name: {
            input: DOM.inputName,
            group: DOM.groupName,
            badge: DOM.badgeName,
            label: 'Borrower Name'
        },
        mobile: {
            input: DOM.inputMobile,
            group: DOM.groupMobile,
            badge: DOM.badgeMobile,
            label: 'Mobile Number'
        },
        address: {
            input: DOM.inputAddress,
            group: DOM.groupAddress,
            badge: DOM.badgeAddress,
            label: 'Address'
        },
        amount: {
            input: DOM.inputAmount,
            group: DOM.groupAmount,
            badge: DOM.badgeAmount,
            label: 'Loan Amount'
        }
    };

    // =========================================================================
    // Initialization
    // =========================================================================
    function init() {
        bindEvents();
        setDefaultExportMonth();
    }

    function setDefaultExportMonth() {
        const now = new Date();
        const year = now.getUTCFullYear();
        const month = String(now.getUTCMonth() + 1).padStart(2, '0');
        if (DOM.exportMonthInput) {
            DOM.exportMonthInput.value = `${year}-${month}`;
        }
    }

    function updateLabelsForProjectType(type) {
        const lblName = document.getElementById('label-input-name');
        const lblAmt = document.getElementById('label-input-amount');
        const thName = document.getElementById('th-col-name');
        const thAmt = document.getElementById('th-col-amount');

        if (type === 'training') {
            if (lblName) lblName.innerHTML = `2. Trainee Name (প্রশিক্ষণার্থীর নাম) <span class="required-star">*</span>`;
            if (lblAmt) lblAmt.innerHTML = `5. Allowance Amount (ভাতার পরিমাণ ৳) <span class="required-star">*</span>`;
            if (thName) thName.innerHTML = `Trainee Name / প্রশিক্ষণার্থীর নাম <span class="required-star">*</span>`;
            if (thAmt) thAmt.innerHTML = `Allowance / ভাতার পরিমাণ (৳) <span class="required-star">*</span>`;
            
            // update field map labels
            if (FIELD_MAP.name) FIELD_MAP.name.label = 'Trainee Name';
            if (FIELD_MAP.amount) FIELD_MAP.amount.label = 'Allowance Amount';
        } else {
            if (lblName) lblName.innerHTML = `2. Borrower Name <span class="required-star">*</span>`;
            if (lblAmt) lblAmt.innerHTML = `5. Loan Amount (৳) <span class="required-star">*</span>`;
            if (thName) thName.innerHTML = `Borrower Name / নাম <span class="required-star">*</span>`;
            if (thAmt) thAmt.innerHTML = `Amount / পরিমাণ (৳) <span class="required-star">*</span>`;
            
            // update field map labels
            if (FIELD_MAP.name) FIELD_MAP.name.label = 'Borrower Name';
            if (FIELD_MAP.amount) FIELD_MAP.amount.label = 'Loan Amount';
        }
        
        // Re-render grid to update placeholders if tabular mode is active
        if (state.batchRows && state.batchRows.length > 0) {
            renderBatchGrid();
        }
    }

    // =========================================================================
    // Event Listeners Registration
    // =========================================================================
    function bindEvents() {
        const projectTypeSelector = document.getElementById('project-type-selector');
        if (projectTypeSelector) {
            projectTypeSelector.addEventListener('change', (e) => {
                updateLabelsForProjectType(e.target.value);
            });
            // initial call
            updateLabelsForProjectType(projectTypeSelector.value);
        }

        // Upload & Dropzone Events
        if (DOM.btnBrowse && DOM.fileInput) {
            DOM.btnBrowse.addEventListener('click', () => DOM.fileInput.click());
        }

        if (DOM.dropzone) {
            DOM.dropzone.addEventListener('dragover', (e) => {
                e.preventDefault();
                DOM.dropzone.classList.add('dragover');
            });

            DOM.dropzone.addEventListener('dragleave', (e) => {
                e.preventDefault();
                DOM.dropzone.classList.remove('dragover');
            });

            DOM.dropzone.addEventListener('drop', (e) => {
                e.preventDefault();
                DOM.dropzone.classList.remove('dragover');
                if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                    handleFileUpload(e.dataTransfer.files[0]);
                }
            });
        }

        if (DOM.fileInput) {
            DOM.fileInput.addEventListener('change', (e) => {
                if (e.target.files && e.target.files.length > 0) {
                    handleFileUpload(e.target.files[0]);
                }
            });
        }

        // Quick Sample Document Generation
        if (DOM.btnQuickSample) {
            DOM.btnQuickSample.addEventListener('click', handleQuickSample);
        }
        if (DOM.btnQuickSampleTabular) {
            DOM.btnQuickSampleTabular.addEventListener('click', handleQuickSampleTabular);
        }

        // Dual Mode View Switcher Tabs
        if (DOM.tabBatchGrid) {
            DOM.tabBatchGrid.addEventListener('click', () => switchMode('grid'));
        }
        if (DOM.tabSingleForm) {
            DOM.tabSingleForm.addEventListener('click', () => switchMode('single'));
        }

        // Batch Data Grid Operations
        if (DOM.btnAddGridRow) {
            DOM.btnAddGridRow.addEventListener('click', handleAddGridRow);
        }
        if (DOM.btnToggleViewer) {
            DOM.btnToggleViewer.addEventListener('click', () => {
                DOM.viewerPane.classList.toggle('collapsed');
                // Trigger resize for canvas/data-grid adjustment
                setTimeout(() => window.dispatchEvent(new Event('resize')), 300);
            });
        }

        if (DOM.btnResetBatch) {
            DOM.btnResetBatch.addEventListener('click', handleResetBatchGrid);
        }
        if (DOM.btnSaveBatch) {
            DOM.btnSaveBatch.addEventListener('click', handleSaveBatch);
        }

        // Batch Export Operations
        if (DOM.btnExportBatchCsv) {
            DOM.btnExportBatchCsv.addEventListener('click', handleBatchExportCsv);
        }
        if (DOM.btnExportBatchExcel) {
            DOM.btnExportBatchExcel.addEventListener('click', handleBatchExportExcel);
        }
        if (DOM.btnExportBatchPdf) {
            DOM.btnExportBatchPdf.addEventListener('click', handleBatchExportPdf);
        }
        if (DOM.btnExportBatchZip) {
            DOM.btnExportBatchZip.addEventListener('click', handleBatchExportZip);
        }

        // Event Delegation for Table Grid Cells and Actions
        if (DOM.batchGridTbody) {
            DOM.batchGridTbody.addEventListener('input', (e) => {
                if (e.target.classList && e.target.classList.contains('grid-cell-input')) {
                    handleGridCellInput(e.target);
                }
            });
            DOM.batchGridTbody.addEventListener('change', (e) => {
                if (e.target.classList && e.target.classList.contains('grid-cell-input')) {
                    handleGridCellInput(e.target);
                }
            });
            DOM.batchGridTbody.addEventListener('keydown', handleGridKeydown);
            DOM.batchGridTbody.addEventListener('click', (e) => {
                const delBtn = e.target.closest('.btn-delete-row');
                if (delBtn) {
                    const rowIdx = parseInt(delBtn.getAttribute('data-row'), 10);
                    handleDeleteGridRow(rowIdx);
                }
            });
        }

        // Document Viewer Toolbar
        if (DOM.btnZoomIn) DOM.btnZoomIn.addEventListener('click', zoomIn);
        if (DOM.btnZoomOut) DOM.btnZoomOut.addEventListener('click', zoomOut);
        if (DOM.btnZoomFit) DOM.btnZoomFit.addEventListener('click', zoomFit);
        if (DOM.btnZoomActual) DOM.btnZoomActual.addEventListener('click', zoomActual);
        if (DOM.btnRotate) DOM.btnRotate.addEventListener('click', rotateDoc);
        if (DOM.btnPanMode) DOM.btnPanMode.addEventListener('click', togglePanMode);
        if (DOM.btnResetView) DOM.btnResetView.addEventListener('click', resetView);

        // Viewport Mouse Pan & Wheel Zoom
        if (DOM.viewportContainer) {
            DOM.viewportContainer.addEventListener('mousedown', onViewerMouseDown);
            window.addEventListener('mousemove', onViewerMouseMove);
            window.addEventListener('mouseup', onViewerMouseUp);
            DOM.viewportContainer.addEventListener('wheel', onViewerWheel, { passive: false });
        }

        // Verification Form Submission
        if (DOM.form) {
            DOM.form.addEventListener('submit', handleFormSubmit);
        }

        // Track user edits across the 5 loan fields
        Object.keys(FIELD_MAP).forEach((fieldKey) => {
            const field = FIELD_MAP[fieldKey];
            if (field.input) {
                field.input.addEventListener('input', () => onFieldInput(fieldKey));
                field.input.addEventListener('change', () => onFieldInput(fieldKey));
            }
        });

        // Form Action Buttons
        if (DOM.btnResetForm) {
            DOM.btnResetForm.addEventListener('click', handleResetForm);
        }

        if (DOM.btnDownloadPdf) {
            DOM.btnDownloadPdf.addEventListener('click', handleDownloadPdf);
        }

        // Export Modal
        if (DOM.btnOpenExport) DOM.btnOpenExport.addEventListener('click', openExportModal);
        if (DOM.btnCloseExportModal) DOM.btnCloseExportModal.addEventListener('click', closeExportModal);
        if (DOM.btnCancelExportModal) DOM.btnCancelExportModal.addEventListener('click', closeExportModal);
        if (DOM.btnRunCsvExport) DOM.btnRunCsvExport.addEventListener('click', runCsvExport);
        if (DOM.btnRunExcelExport) DOM.btnRunExcelExport.addEventListener('click', runExcelExport);

        // Recent Records Modal
        if (DOM.btnOpenRecent) DOM.btnOpenRecent.addEventListener('click', openRecentModal);
        if (DOM.btnCloseRecentModal) DOM.btnCloseRecentModal.addEventListener('click', closeRecentModal);
        if (DOM.btnCancelRecentModal) DOM.btnCancelRecentModal.addEventListener('click', closeRecentModal);
        if (DOM.btnRefreshRecent) DOM.btnRefreshRecent.addEventListener('click', loadRecentRecords);

        // Main Menu Dropdown
    const btnMainMenu = document.getElementById('btn-main-menu');
    const mainMenuContent = document.getElementById('main-menu-content');
    if (btnMainMenu && mainMenuContent) {
        btnMainMenu.addEventListener('click', (e) => {
            e.stopPropagation();
            mainMenuContent.style.display = mainMenuContent.style.display === 'none' ? 'block' : 'none';
        });
        document.addEventListener('click', () => {
            mainMenuContent.style.display = 'none';
        });
    }

        // Settings Modal
        const btnOpenSettings = document.getElementById('btn-open-settings');
        const modalSettings = document.getElementById('modal-settings-backdrop');
        const btnCloseSettings = document.getElementById('btn-close-settings-modal');
        const btnCancelSettings = document.getElementById('btn-cancel-settings-modal');
        const btnSaveSettings = document.getElementById('btn-save-settings');
        const inputInstName = document.getElementById('input-inst-name');
        const inputInstAddress = document.getElementById('input-inst-address');

        // Project Selection Modal bindings
        const btnSelectProjLoan = document.getElementById('btn-select-proj-loan');
        const btnSelectProjTraining = document.getElementById('btn-select-proj-training');
        const btnCancelProj = document.getElementById('btn-cancel-proj-selection');
        const modalProject = document.getElementById('modal-project-selection');

        if (btnSelectProjLoan) btnSelectProjLoan.addEventListener('click', () => proceedWithUpload('loan'));
        if (btnSelectProjTraining) btnSelectProjTraining.addEventListener('click', () => proceedWithUpload('training'));
        if (btnCancelProj) btnCancelProj.addEventListener('click', () => {
            if (modalProject) modalProject.style.display = 'none';
            pendingUploadFile = null;
        });

        // New Upload Reset
        const btnNewUpload = document.getElementById('btn-new-upload');
        if (btnNewUpload) btnNewUpload.addEventListener('click', () => {
            const activeFileBar = document.getElementById('active-file-bar');
            const uploadSection = document.getElementById('upload-section');
            if (activeFileBar && uploadSection) {
                activeFileBar.style.display = 'none';
                uploadSection.style.display = 'flex';
                // optional: clear the viewer
                if (DOM.viewportImage) DOM.viewportImage.style.display = 'none';
                if (DOM.viewportEmpty) DOM.viewportEmpty.style.display = 'flex';
            }
        });

        // Global Keyboard Shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key.toLowerCase() === 's') {
                e.preventDefault();
                if (state.isTabularMode && !DOM.btnSaveBatch.disabled) {
                    DOM.btnSaveBatch.click();
                } else if (!state.isTabularMode && !DOM.btnSaveVerify.disabled) {
                    DOM.btnSaveVerify.click();
                }
            }
        });

        if (btnOpenSettings) {
            btnOpenSettings.addEventListener('click', () => {
                inputInstName.value = localStorage.getItem('instName') || 'Loan Easier';
                inputInstAddress.value = localStorage.getItem('instAddress') || 'Dhaka, Bangladesh';
                modalSettings.style.display = 'flex';
            });
        }
        const closeSettings = () => { if (modalSettings) modalSettings.style.display = 'none'; };
        if (btnCloseSettings) btnCloseSettings.addEventListener('click', closeSettings);
        if (btnCancelSettings) btnCancelSettings.addEventListener('click', closeSettings);
        if (btnSaveSettings) {
            btnSaveSettings.addEventListener('click', () => {
                localStorage.setItem('instName', inputInstName.value.trim() || 'Loan Easier');
                localStorage.setItem('instAddress', inputInstAddress.value.trim() || 'Dhaka, Bangladesh');
                closeSettings();
                showToast('Settings saved successfully.', 'success');
            });
        }
    }

    // =========================================================================
    // Document Upload & OCR Triggering
    // =========================================================================
    let pendingUploadFile = null;

    async function handleFileUpload(file) {
        if (!file) return;

        // Validate MIME / extension
        const validExtensions = ['.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.webp', '.csv', '.json', '.md'];
        const fileName = file.name || 'uploaded_document.png';
        const fileExt = fileName.substring(fileName.lastIndexOf('.')).toLowerCase();

        if (!validExtensions.includes(fileExt)) {
            showToast(`Unsupported format '${fileExt}'. Allowed: PNG, JPEG, TIFF, BMP, WebP.`, 'error');
            return;
        }

        // Check 15MB size limit
        if (file.size > 15 * 1024 * 1024) {
            showToast('File size exceeds the 15MB maximum limit.', 'error');
            return;
        }

        pendingUploadFile = file;
        const modal = document.getElementById('modal-project-selection');
        if (modal) modal.style.display = 'flex';
    }

    async function proceedWithUpload(projectType) {
        if (!pendingUploadFile) return;
        const file = pendingUploadFile;
        pendingUploadFile = null;
        
        const modal = document.getElementById('modal-project-selection');
        if (modal) modal.style.display = 'none';

        const fileName = file.name || 'uploaded_document.png';

        // Preview image in viewport immediately
        const objectUrl = URL.createObjectURL(file);
        loadDocumentImage(objectUrl, fileName);

        // Show loading spinner
        setViewerLoading(true);

        const formData = new FormData();
        formData.append('file', file);
        formData.append('project_type', projectType);
        
        state.currentProjectType = projectType;
        updateLabelsForProjectType(projectType);
        
        // Hide dropzone, show active bar
        const activeFileBar = document.getElementById('active-file-bar');
        const activeFileName = document.getElementById('active-file-name');
        const uploadSection = document.getElementById('upload-section');
        if (activeFileBar && uploadSection && activeFileName) {
            activeFileName.textContent = fileName;
            uploadSection.style.display = 'none';
            activeFileBar.style.display = 'flex';
        }

        try {
            const response = await fetch('/api/documents/upload', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                const errMsg = errData.detail || `Upload failed with HTTP ${response.status}`;
                throw new Error(errMsg);
            }

            const data = await response.json();
            const isTabular = Boolean(
                data.is_tabular ||
                (Array.isArray(data.records) && data.records.length > 1) ||
                (Array.isArray(data.rows) && data.rows.length > 1)
            );

            if (isTabular) {
                populateBatchGrid(data);
                switchMode('grid');
                showToast(`Tabular batch processed (${state.batchRows.length} records) via ${state.batchEngine}`, 'success');
            } else {
                populateVerificationForm(data);
                switchMode('single');
                showToast(`Document processed successfully via ${data.ocr_engine_used || data.engine_name}`, 'success');
            }
        } catch (err) {
            console.error('Upload or OCR error:', err);
            showToast(err.message || 'Failed to process document image.', 'error');
            DOM.verificationStateBadge.textContent = 'Extraction Failed';
            DOM.verificationStateBadge.className = 'state-badge state-awaiting';
        } finally {
            setViewerLoading(false);
        }
    }

    // =========================================================================
    // Form Population & Confidence Highlighting (< 0.80 logic)
    // =========================================================================
    function populateVerificationForm(data) {
        state.currentLoanId = data.id || data.loan_id;
        state.currentLoanData = data;
        state.editedFields.clear();

        // 1. Update Header Badges and Project Type
        if (data.project_type) {
            state.currentProjectType = data.project_type;
            updateLabelsForProjectType(data.project_type);
        }

        DOM.recordIdBadge.textContent = `Record #${state.currentLoanId}`;

        if (data.verified) {
            DOM.verificationStateBadge.textContent = 'Verified ✓';
            DOM.verificationStateBadge.className = 'state-badge state-verified';
            DOM.btnDownloadPdf.disabled = false;
        } else {
            DOM.verificationStateBadge.textContent = 'Draft (Needs Review)';
            DOM.verificationStateBadge.className = 'state-badge state-draft';
            DOM.btnDownloadPdf.disabled = true;
        }

        // 2. Update OCR Engine Badge & Fallback Alert
        const engineUsed = data.ocr_engine_used || data.engine_name || 'Unknown';
        DOM.engineBadge.textContent = engineUsed;

        if (engineUsed.toLowerCase().includes('tesseract') || data.fallback_triggered) {
            DOM.engineBadge.className = 'badge badge-amber';
            DOM.fallbackAlert.style.display = 'flex';
            DOM.fallbackReasonText.textContent = data.fallback_reason ||
                'Primary Google Cloud Vision API was unavailable. Automatic failover to local Tesseract OCR engine occurred.';
        } else {
            DOM.engineBadge.className = 'badge badge-primary';
            DOM.fallbackAlert.style.display = 'none';
        }

        // 3. Populate Form Fields & Store Originals
        state.originalValues = {
            serial_number: data.serial_number || '',
            name: data.name || '',
            mobile: data.mobile || '',
            address: data.address || '',
            amount: (data.amount !== null && data.amount !== undefined) ? data.amount : ''
        };

        const confidences = data.confidences || {};
        let confidenceSum = 0;
        let confidenceCount = 0;

        Object.keys(FIELD_MAP).forEach((fieldKey) => {
            const field = FIELD_MAP[fieldKey];
            const originalVal = state.originalValues[fieldKey];
            field.input.value = originalVal;

            // Confidence score for this field (normalized 0.00 - 1.00)
            let conf = confidences[fieldKey];
            if (conf === undefined || conf === null) {
                conf = 0.0;
            }
            conf = Math.max(0.0, Math.min(1.0, parseFloat(conf)));

            confidenceSum += conf;
            confidenceCount++;

            // Render confidence highlight and badge
            applyFieldConfidenceVisuals(fieldKey, conf);
        });

        // 4. Overall Document Confidence Meter
        const overallScore = confidenceCount > 0 ? (confidenceSum / confidenceCount) : 0.0;
        const overallPct = Math.round(overallScore * 100);
        DOM.overallConfidenceScore.textContent = `${overallPct}%`;
        DOM.overallConfidenceBar.style.width = `${overallPct}%`;

        if (overallScore >= state.confidenceThreshold) {
            DOM.overallConfidenceBar.className = 'confidence-bar-fill bar-high';
        } else if (overallScore >= 0.60) {
            DOM.overallConfidenceBar.className = 'confidence-bar-fill bar-medium';
        } else {
            DOM.overallConfidenceBar.className = 'confidence-bar-fill bar-low';
        }

        // 5. Enable Buttons
        DOM.btnSaveVerify.disabled = false;
        DOM.btnResetForm.disabled = false;

        // 6. Update Telemetry Accordion
        DOM.telemetryTime.textContent = data.created_at || new Date().toISOString();
        DOM.telemetryImgpath.textContent = data.image_path || '--';
        DOM.telemetryRawText.textContent = data.raw_text || '(Raw text unavailable)';
    }

    /**
     * Applies strict low-confidence highlighting (< 0.80) or high-confidence badge
     */
    function applyFieldConfidenceVisuals(fieldKey, confidenceScore) {
        const field = FIELD_MAP[fieldKey];
        if (!field) return;

        const isLow = confidenceScore < state.confidenceThreshold;
        const pct = Math.round(confidenceScore * 100);

        // Remove previous visual state classes
        field.group.classList.remove('field-low-confidence', 'field-high-confidence', 'field-edited');

        if (isLow) {
            // Low Confidence (< 0.80): distinct high-contrast amber/red border + soft tinted background
            field.group.classList.add('field-low-confidence');
            field.badge.innerHTML = `
                <span class="badge badge-low-conf" title="Confidence is below 80% threshold. Please verify against document.">
                    ⚠️ Low Confidence (${pct}%) - Please Review
                </span>
            `;
        } else {
            // High Confidence (>= 0.80): green checkmark badge
            field.group.classList.add('field-high-confidence');
            field.badge.innerHTML = `
                <span class="badge badge-high-conf" title="High confidence extraction (${pct}%)">
                    ✓ High Confidence (${pct}%)
                </span>
            `;
        }
    }

    // =========================================================================
    // Manual Edit Tracking
    // =========================================================================
    function onFieldInput(fieldKey) {
        const field = FIELD_MAP[fieldKey];
        if (!field) return;

        const currentVal = field.input.value.trim();
        const origVal = String(state.originalValues[fieldKey] || '').trim();

        // Has the user modified the field?
        const isModified = currentVal !== origVal;

        if (isModified) {
            state.editedFields.add(fieldKey);
            // Transition container to .field-edited
            field.group.classList.remove('field-low-confidence', 'field-high-confidence');
            field.group.classList.add('field-edited');

            // Dynamic badge update to "✏️ Manually Edited"
            field.badge.innerHTML = `
                <span class="badge badge-edited" title="Value has been manually updated by user">
                    ✏️ Manually Edited
                </span>
            `;
        } else {
            state.editedFields.delete(fieldKey);
            // Restore original OCR confidence badge
            const confidences = (state.currentLoanData && state.currentLoanData.confidences) || {};
            const conf = confidences[fieldKey] !== undefined ? confidences[fieldKey] : 0.0;
            applyFieldConfidenceVisuals(fieldKey, conf);
        }
    }

    // =========================================================================
    // Form Actions & Verification Persistence
    // =========================================================================
    async function handleFormSubmit(e) {
        e.preventDefault();

        if (!state.currentLoanId) {
            showToast('No loan record loaded to verify.', 'error');
            return;
        }

        // Validate inputs
        const serial = DOM.inputSerialNumber.value.trim();
        const name = DOM.inputName.value.trim();
        const mobile = DOM.inputMobile.value.trim();
        const address = DOM.inputAddress.value.trim();
        const amountRaw = DOM.inputAmount.value.trim();
        const amount = parseFloat(amountRaw);

        if (!serial) {
            showToast('Serial Number is required.', 'error');
            DOM.inputSerialNumber.focus();
            return;
        }
        if (!name) {
            showToast('Borrower Legal Name is required.', 'error');
            DOM.inputName.focus();
            return;
        }
        if (!mobile) {
            showToast('Mobile Number is required.', 'error');
            DOM.inputMobile.focus();
            return;
        }
        if (!address) {
            showToast('Address is required.', 'error');
            DOM.inputAddress.focus();
            return;
        }
        if (isNaN(amount) || amount <= 0) {
            showToast('Principal Loan Amount must be greater than zero.', 'error');
            DOM.inputAmount.focus();
            return;
        }

        const payload = {
            serial_number: serial,
            name: name,
            mobile: mobile,
            address: address,
            amount: amount
        };

        DOM.btnSaveVerify.disabled = true;
        const originalText = DOM.btnSaveVerify.innerHTML;
        DOM.btnSaveVerify.innerHTML = '<span class="spinner" style="width: 16px; height: 16px; border-width: 2px; margin-bottom: 0;"></span> Verifying...';

        try {
            const response = await fetch(`/api/loans/${state.currentLoanId}/verify`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.detail || `Verification failed with HTTP ${response.status}`);
            }

            const updated = await response.json();
            state.currentLoanData = updated;

            // Update verification badge
            DOM.verificationStateBadge.textContent = 'Verified ✓';
            DOM.verificationStateBadge.className = 'state-badge state-verified';

            // Enable PDF Download button
            DOM.btnDownloadPdf.disabled = false;

            // Update original values to current verified values
            state.originalValues = {
                serial_number: updated.serial_number,
                name: updated.name,
                mobile: updated.mobile,
                address: updated.address,
                amount: updated.amount
            };
            state.editedFields.clear();

            showToast('Loan record verified and saved locally!', 'success');
        } catch (err) {
            console.error('Verification error:', err);
            showToast(err.message || 'Failed to verify loan record.', 'error');
        } finally {
            DOM.btnSaveVerify.disabled = false;
            DOM.btnSaveVerify.innerHTML = originalText;
        }
    }

    function handleResetForm() {
        if (!state.currentLoanData) return;

        Object.keys(FIELD_MAP).forEach((fieldKey) => {
            const field = FIELD_MAP[fieldKey];
            field.input.value = state.originalValues[fieldKey] || '';
            const confidences = state.currentLoanData.confidences || {};
            const conf = confidences[fieldKey] !== undefined ? confidences[fieldKey] : 0.0;
            applyFieldConfidenceVisuals(fieldKey, conf);
        });

        state.editedFields.clear();
        showToast('Form reset to original OCR extracted values.', 'info');
    }

    function handleDownloadPdf() {
        if (!state.currentLoanId) {
            showToast('No active loan record loaded.', 'error');
            return;
        }
        showToast('Generating formal loan agreement PDF...', 'info');
        window.open(`/api/loans/${state.currentLoanId}/pdf?${getLenderParams()}`, '_blank');
    }

    // =========================================================================
    // Tabular Batch HITL Data Grid & Dual Mode Controller (Milestone M2)
    // =========================================================================

    /**
     * Escape raw text safely for HTML insertion
     */
    function escapeHtml(str) {
        if (str === null || str === undefined) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    /**
     * Switch view between Batch Data Grid and Single Record Form
     */
    function switchMode(mode) {
        state.isTabularMode = (mode === 'grid');

        if (mode === 'grid') {
            if (DOM.singleFormContainer) DOM.singleFormContainer.style.display = 'none';
            if (DOM.dataGridContainer) DOM.dataGridContainer.style.display = 'flex';
            if (DOM.singleRecordView) DOM.singleRecordView.style.display = 'none';
            if (DOM.batchGridView) DOM.batchGridView.style.display = 'flex';
            if (DOM.tabBatchGrid) DOM.tabBatchGrid.classList.add('active');
            if (DOM.tabSingleForm) DOM.tabSingleForm.classList.remove('active');
            if (DOM.paneHeaderIcon) DOM.paneHeaderIcon.textContent = '📊';
            if (DOM.paneHeaderText) DOM.paneHeaderText.textContent = 'Batch Data Grid';
            if (DOM.recordIdBadge) {
                DOM.recordIdBadge.textContent = state.currentBatchId ? `Batch: ${state.currentBatchId}` : 'Batch: None';
            }

            if (state.batchVerified) {
                DOM.verificationStateBadge.textContent = 'Verified ✓';
                DOM.verificationStateBadge.className = 'state-badge state-verified';
            } else if (state.batchRows.length > 0) {
                DOM.verificationStateBadge.textContent = 'Draft (Needs Review)';
                DOM.verificationStateBadge.className = 'state-badge state-draft';
            } else {
                DOM.verificationStateBadge.textContent = 'Awaiting Document';
                DOM.verificationStateBadge.className = 'state-badge state-awaiting';
            }
        } else {
            if (DOM.singleFormContainer) DOM.singleFormContainer.style.display = 'flex';
            if (DOM.dataGridContainer) DOM.dataGridContainer.style.display = 'none';
            if (DOM.singleRecordView) DOM.singleRecordView.style.display = 'flex';
            if (DOM.batchGridView) DOM.batchGridView.style.display = 'none';
            if (DOM.tabBatchGrid) DOM.tabBatchGrid.classList.remove('active');
            if (DOM.tabSingleForm) DOM.tabSingleForm.classList.add('active');
            if (DOM.paneHeaderIcon) DOM.paneHeaderIcon.textContent = '✍️';
            if (DOM.paneHeaderText) DOM.paneHeaderText.textContent = 'Verification Form';
            if (DOM.recordIdBadge) {
                DOM.recordIdBadge.textContent = state.currentLoanId ? `Record #${state.currentLoanId}` : 'Record: None';
            }

            if (state.currentLoanData && state.currentLoanData.verified) {
                DOM.verificationStateBadge.textContent = 'Verified ✓';
                DOM.verificationStateBadge.className = 'state-badge state-verified';
            } else if (state.currentLoanId) {
                DOM.verificationStateBadge.textContent = 'Draft (Needs Review)';
                DOM.verificationStateBadge.className = 'state-badge state-draft';
            } else {
                DOM.verificationStateBadge.textContent = 'Awaiting Document';
                DOM.verificationStateBadge.className = 'state-badge state-awaiting';
            }
        }
    }

    /**
     * Populate Batch Data Grid state and UI from OCR extraction payload
     */
    function populateBatchGrid(data) {
        state.currentBatchId = data.batch_id || (`BATCH-${Date.now()}`);
        state.batchEngine = data.ocr_engine_used || data.engine_used || data.engine_name || 'Dual Engine';
        state.batchVerified = Boolean(data.verified);
        state.deletedRowIds = [];

        const rawRows = Array.isArray(data.records) ? data.records : (Array.isArray(data.rows) ? data.rows : []);

        state.batchRows = rawRows.map((r, idx) => {
            const confs = r.confidences || {};
            return {
                id: r.id || r.loan_id || null,
                row_index: r.row_index !== undefined ? r.row_index : (idx + 1),
                serial_number: String(r.serial_number || `LN-${idx + 1}`).trim(),
                name: String(r.name || '').trim(),
                mobile: String(r.mobile || '').trim(),
                address: String(r.address || '').trim(),
                amount: (r.amount !== null && r.amount !== undefined) ? (parseFloat(r.amount) || 0.0) : 0.0,
                confidences: {
                    serial_number: parseFloat(confs.serial_number ?? 1.0),
                    name: parseFloat(confs.name ?? 1.0),
                    mobile: parseFloat(confs.mobile ?? 1.0),
                    address: parseFloat(confs.address ?? 1.0),
                    amount: parseFloat(confs.amount ?? 1.0),
                },
                edited: {
                    serial_number: false,
                    name: false,
                    mobile: false,
                    address: false,
                    amount: false,
                },
                verified: Boolean(r.verified)
            };
        });

        // Update Project Type Selector
        if (data.project_type) {
            const ptSelector = document.getElementById('project-type-selector');
            if (ptSelector && ptSelector.value !== data.project_type) {
                ptSelector.value = data.project_type;
                updateLabelsForProjectType(data.project_type);
            }
        }

        // Store pristine copy for Reset capability
        state.originalBatchRows = JSON.parse(JSON.stringify(state.batchRows));

        // Update OCR Engine Badge
        if (DOM.batchEngineBadge) {
            DOM.batchEngineBadge.textContent = state.batchEngine;
            const isFallback = state.batchEngine.toLowerCase().includes('tesseract') || Boolean(data.fallback_triggered);
            DOM.batchEngineBadge.className = isFallback ? 'badge badge-amber' : 'badge badge-primary';
            if (DOM.batchFallbackAlert) {
                DOM.batchFallbackAlert.style.display = isFallback ? 'flex' : 'none';
                if (DOM.batchFallbackReasonText && data.fallback_reason) {
                    DOM.batchFallbackReasonText.textContent = data.fallback_reason;
                }
            }
        }

        // Update Batch Telemetry
        if (DOM.batchTelemetryId) DOM.batchTelemetryId.textContent = state.currentBatchId;
        if (DOM.batchTelemetryTime) {
            DOM.batchTelemetryTime.textContent = data.execution_time_ms ? `${Number(data.execution_time_ms).toFixed(1)} ms` : '--';
        }
        if (DOM.batchTelemetryImgpath) DOM.batchTelemetryImgpath.textContent = data.image_path || '--';
        if (DOM.batchTelemetryRawText) DOM.batchTelemetryRawText.textContent = data.raw_text || '(Raw text unavailable)';

        // Update Tab Counter
        if (DOM.tabGridCountBadge) DOM.tabGridCountBadge.textContent = state.batchRows.length;

        // Render Table & Recalculate Live Summaries
        renderBatchGrid();
        updateBatchSummary();

        // Configure Action Buttons
        if (DOM.btnSaveBatch) DOM.btnSaveBatch.disabled = state.batchRows.length === 0;
        if (DOM.btnExportBatchCsv) DOM.btnExportBatchCsv.disabled = !state.batchVerified;
        if (DOM.btnExportBatchExcel) DOM.btnExportBatchExcel.disabled = !state.batchVerified;
        if (DOM.btnExportBatchPdf) DOM.btnExportBatchPdf.disabled = !state.batchVerified;
        if (DOM.btnExportBatchZip) DOM.btnExportBatchZip.disabled = !state.batchVerified;
    }

    /**
     * Render the interactive data grid rows with cell confidence badges (< 0.80)
     */
    function renderBatchGrid() {
        if (!DOM.batchGridTbody) return;
        DOM.batchGridTbody.innerHTML = '';

        if (!state.batchRows || state.batchRows.length === 0) {
            const emptyTr = document.createElement('tr');
            emptyTr.id = 'grid-empty-row';
            emptyTr.innerHTML = '<td colspan="6" class="text-center py-4 text-muted" style="padding: 2rem; color: var(--neutral-500); text-align: center;">No records in batch. Click "+ Add Row" or upload a tabular document scan.</td>';
            DOM.batchGridTbody.appendChild(emptyTr);
            return;
        }

        state.batchRows.forEach((row, idx) => {
            const tr = document.createElement('tr');
            tr.setAttribute('data-row-index', idx);

            // 1. SL Cell
            const tdSl = document.createElement('td');
            tdSl.className = 'col-sl-cell font-mono font-bold';
            tdSl.textContent = row.row_index || (idx + 1);
            tr.appendChild(tdSl);

            // Determine placeholders based on project type
            const projType = state.currentProjectType || 'loan';
            const namePlaceholder = projType === 'training' ? 'Trainee Name (প্রশিক্ষণার্থীর নাম)' : 'Borrower Legal Name (নাম)';
            
            // 2. Name Cell
            const tdName = createGridCellTd({
                field: 'name',
                value: row.name,
                placeholder: namePlaceholder,
                rowIdx: idx,
                confidence: row.confidences.name ?? 1.0,
                isEdited: row.edited.name,
                isAmount: false
            });
            tr.appendChild(tdName);

            // 3. Mobile Cell
            const tdMobile = createGridCellTd({
                field: 'mobile',
                value: row.mobile,
                placeholder: '01XXXXXXXXX (মোবাইল)',
                rowIdx: idx,
                confidence: row.confidences.mobile ?? 1.0,
                isEdited: row.edited.mobile,
                isAmount: false,
                isMono: true
            });
            tr.appendChild(tdMobile);

            // 4. Address Cell
            const tdAddress = createGridCellTd({
                field: 'address',
                value: row.address,
                placeholder: 'Address (ঠিকানা)',
                rowIdx: idx,
                confidence: row.confidences.address ?? 1.0,
                isEdited: row.edited.address,
                isAmount: false
            });
            tr.appendChild(tdAddress);

            // 5. Amount Cell
            const tdAmount = createGridCellTd({
                field: 'amount',
                value: (row.amount !== null && row.amount !== undefined && row.amount > 0) ? Number(row.amount).toFixed(2) : '',
                placeholder: '0.00',
                rowIdx: idx,
                confidence: row.confidences.amount ?? 1.0,
                isEdited: row.edited.amount,
                isAmount: true,
                isMono: true
            });
            tr.appendChild(tdAmount);

            // 6. Actions Cell (Delete Row)
            const tdActions = document.createElement('td');
            tdActions.className = 'col-actions-cell';
            tdActions.innerHTML = `
                <button type="button" class="btn-delete-row" data-row="${idx}" title="Delete Row ${row.row_index || (idx + 1)}">
                    🗑️
                </button>
            `;
            tr.appendChild(tdActions);

            DOM.batchGridTbody.appendChild(tr);
        });
    }

    /**
     * Helper to construct a single grid cell TD with low-confidence (<0.80) or edited styling
     */
    function createGridCellTd(opts) {
        const td = document.createElement('td');
        const isLow = (opts.confidence < state.confidenceThreshold) && !opts.isEdited;

        if (opts.isEdited) {
            td.className = 'cell-edited';
        } else if (isLow) {
            td.className = 'cell-low-confidence';
        } else {
            td.className = 'cell-high-confidence';
        }

        const wrapper = document.createElement('div');
        wrapper.className = 'grid-cell-wrapper';

        if (opts.isAmount) {
            const sym = document.createElement('span');
            sym.className = 'cell-currency-symbol';
            sym.textContent = '৳';
            wrapper.appendChild(sym);
        }

        const input = document.createElement('input');
        input.type = opts.isAmount ? 'number' : (opts.field === 'mobile' ? 'tel' : 'text');
        if (opts.isAmount) {
            input.step = '0.01';
            input.min = '0.01';
            input.className = 'grid-cell-input font-mono amount-input input-grid-amount';
        } else if (opts.isMono) {
            input.className = `grid-cell-input font-mono input-grid-${opts.field}`;
        } else {
            input.className = `grid-cell-input input-grid-${opts.field}`;
        }

        input.value = opts.value;
        input.placeholder = opts.placeholder;
        input.setAttribute('data-row', opts.rowIdx);
        input.setAttribute('data-field', opts.field);
        input.autocomplete = 'off';

        wrapper.appendChild(input);

        // Badge indicator
        if (opts.isEdited) {
            const badge = document.createElement('span');
            badge.className = 'cell-badge-edited';
            badge.title = 'Manually Verified';
            badge.textContent = '✏️';
            wrapper.appendChild(badge);
        } else if (isLow) {
            const pct = Math.round(opts.confidence * 100);
            const badge = document.createElement('span');
            badge.className = 'cell-badge-low';
            badge.title = `Confidence: ${pct}% (< 80% threshold - Review required)`;
            badge.textContent = `⚠️ ${pct}%`;
            wrapper.appendChild(badge);
        }

        td.appendChild(wrapper);
        return td;
    }

    /**
     * Handle user inline edits in data grid cells
     */
    function handleGridCellInput(inputElem) {
        const rowIdx = parseInt(inputElem.getAttribute('data-row'), 10);
        const field = inputElem.getAttribute('data-field');
        const row = state.batchRows[rowIdx];
        if (!row) return;

        const val = inputElem.value;
        if (field === 'amount') {
            row.amount = parseFloat(val) || 0.0;
        } else {
            row[field] = val;
        }

        // When cell is edited: clear warning styling, mark as edited, and reset confidence to 1.00
        row.edited[field] = true;
        row.confidences[field] = 1.00;

        const td = inputElem.closest('td');
        if (td) {
            td.classList.remove('cell-low-confidence', 'cell-high-confidence');
            td.classList.add('cell-edited');

            // Remove existing badge and append edited badge
            const existingBadge = td.querySelector('.cell-badge-low, .cell-badge-edited');
            if (existingBadge) existingBadge.remove();

            const newBadge = document.createElement('span');
            newBadge.className = 'cell-badge-edited';
            newBadge.title = 'Manually Verified';
            newBadge.textContent = '✏️';
            const wrapper = td.querySelector('.grid-cell-wrapper');
            if (wrapper) wrapper.appendChild(newBadge);
        }

        // Dynamically update live summary totals
        updateBatchSummary();
    }

    /**
     * Keyboard navigation for data grid: Enter/Down moves vertically down, Up moves vertically up
     */
    function handleGridKeydown(e) {
        const input = e.target;
        if (!input.classList.contains('grid-cell-input')) return;

        const rowIdx = parseInt(input.getAttribute('data-row'), 10);
        const field = input.getAttribute('data-field');

        if (e.key === 'Enter' || e.key === 'ArrowDown') {
            if (rowIdx + 1 < state.batchRows.length) {
                e.preventDefault();
                const nextRow = DOM.batchGridTbody.children[rowIdx + 1];
                if (nextRow) {
                    const targetInput = nextRow.querySelector(`[data-field="${field}"]`);
                    if (targetInput) {
                        targetInput.focus();
                        targetInput.select();
                    }
                }
            }
        } else if (e.key === 'ArrowUp') {
            if (rowIdx > 0) {
                e.preventDefault();
                const prevRow = DOM.batchGridTbody.children[rowIdx - 1];
                if (prevRow) {
                    const targetInput = prevRow.querySelector(`[data-field="${field}"]`);
                    if (targetInput) {
                        targetInput.focus();
                        targetInput.select();
                    }
                }
            }
        }
    }

    /**
     * Dynamic Add Row: inserts a new loan record at the end of the grid
     */
    function handleAddGridRow() {
        const newIndex = state.batchRows.length + 1;
        const newRow = {
            id: null,
            row_index: newIndex,
            serial_number: `LN-NEW-${String(newIndex).padStart(3, '0')}`,
            name: '',
            mobile: '',
            address: '',
            amount: 0.0,
            confidences: {
                serial_number: 1.0,
                name: 1.0,
                mobile: 1.0,
                address: 1.0,
                amount: 1.0
            },
            edited: {
                serial_number: true,
                name: true,
                mobile: true,
                address: true,
                amount: true
            },
            verified: false
        };

        state.batchRows.push(newRow);
        renderBatchGrid();
        updateBatchSummary();

        // Focus the name input of the new row
        const newTr = DOM.batchGridTbody.lastElementChild;
        if (newTr) {
            const nameInput = newTr.querySelector('.input-grid-name');
            if (nameInput) nameInput.focus();
            newTr.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }

        showToast(`New row ${newIndex} added to batch.`, 'info');
    }

    /**
     * Dynamic Delete Row: removes a record from the grid
     */
    function handleDeleteGridRow(rowIdx) {
        const row = state.batchRows[rowIdx];
        if (!row) return;

        if (row.id) {
            state.deletedRowIds.push(row.id);
        }

        state.batchRows.splice(rowIdx, 1);

        // Re-number remaining row indexes sequentially
        state.batchRows.forEach((r, idx) => {
            r.row_index = idx + 1;
        });

        renderBatchGrid();
        updateBatchSummary();

        showToast(`Row deleted. (${state.batchRows.length} remaining)`, 'info');
    }

    /**
     * Live Batch Summary: recalculates Total Records, Total Amount, Pending Review count
     */
    function updateBatchSummary() {
        const totalRecords = state.batchRows.length;
        let totalAmount = 0.0;
        let lowConfCount = 0;

        state.batchRows.forEach(r => {
            totalAmount += parseFloat(r.amount) || 0.0;
            ['name', 'mobile', 'address', 'amount'].forEach(f => {
                if ((r.confidences[f] < state.confidenceThreshold) && !r.edited[f]) {
                    lowConfCount++;
                }
            });
        });

        const formattedAmount = '৳ ' + totalAmount.toLocaleString('en-US', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });

        if (DOM.batchStatRecords) DOM.batchStatRecords.textContent = totalRecords;
        if (DOM.batchStatAmount) DOM.batchStatAmount.textContent = formattedAmount;
        if (DOM.batchStatLowConf) DOM.batchStatLowConf.textContent = lowConfCount;
        if (DOM.gridFooterTotalAmount) DOM.gridFooterTotalAmount.textContent = formattedAmount;
        if (DOM.gridStatusInfo) DOM.gridStatusInfo.textContent = `${totalRecords} records | ${lowConfCount} pending review`;
        if (DOM.tabGridCountBadge) DOM.tabGridCountBadge.textContent = totalRecords;

        if (DOM.btnSaveBatch) DOM.btnSaveBatch.disabled = (totalRecords === 0);
    }

    /**
     * Reset Batch Data Grid to pristine extracted OCR values
     */
    function handleResetBatchGrid() {
        if (!state.originalBatchRows || state.originalBatchRows.length === 0) return;
        state.batchRows = JSON.parse(JSON.stringify(state.originalBatchRows));
        state.deletedRowIds = [];
        renderBatchGrid();
        updateBatchSummary();
        showToast('Batch data grid reset to original OCR values.', 'info');
    }

    /**
     * Verify & Save Batch: POST all grid rows to /api/batches/{batch_id}/verify
     */
    async function handleSaveBatch() {
        if (!state.batchRows || state.batchRows.length === 0) {
            showToast('No records in batch to verify.', 'error');
            return;
        }

        // Validate each row
        for (let i = 0; i < state.batchRows.length; i++) {
            const r = state.batchRows[i];
            if (!r.name || r.name.trim() === '') {
                showToast(`Row ${i + 1}: Borrower Name is required.`, 'error');
                const rowElem = DOM.batchGridTbody.children[i];
                if (rowElem) {
                    const inp = rowElem.querySelector('.input-grid-name');
                    if (inp) inp.focus();
                }
                return;
            }
            if (isNaN(r.amount) || r.amount <= 0) {
                showToast(`Row ${i + 1}: Principal Amount must be greater than zero.`, 'error');
                const rowElem = DOM.batchGridTbody.children[i];
                if (rowElem) {
                    const inp = rowElem.querySelector('.input-grid-amount');
                    if (inp) inp.focus();
                }
                return;
            }
        }

        const batchId = state.currentBatchId || `BATCH-${Date.now()}`;
        const recordsPayload = state.batchRows.map((r, idx) => ({
            id: r.id,
            row_index: r.row_index || (idx + 1),
            project_type: document.getElementById('project-type-selector') ? document.getElementById('project-type-selector').value : 'loan',
            serial_number: r.serial_number || `LN-${idx + 1}`,
            name: r.name.trim(),
            mobile: r.mobile.trim(),
            address: r.address.trim(),
            amount: parseFloat(r.amount) || 0.0,
            confidences: r.confidences,
            verified: true
        }));

        const payload = {
            batch_id: batchId,
            records: recordsPayload,
            rows: recordsPayload,
            deleted_ids: state.deletedRowIds
        };

        DOM.btnSaveBatch.disabled = true;
        const originalHtml = DOM.btnSaveBatch.innerHTML;
        DOM.btnSaveBatch.innerHTML = '<span class="spinner" style="width: 16px; height: 16px; border-width: 2px; margin-bottom: 0;"></span> Verifying Batch...';

        try {
            const response = await fetch(`/api/batches/${batchId}/verify`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.detail || `Batch verification failed with HTTP ${response.status}`);
            }

            const result = await response.json();

            // Mark batch rows as verified
            state.batchVerified = true;
            state.batchRows.forEach(r => {
                r.verified = true;
            });

            // Update UI State Badges
            DOM.verificationStateBadge.textContent = 'Verified ✓';
            DOM.verificationStateBadge.className = 'state-badge state-verified';

            // Enable Batch Exports
            if (DOM.btnExportBatchCsv) DOM.btnExportBatchCsv.disabled = false;
            if (DOM.btnExportBatchExcel) DOM.btnExportBatchExcel.disabled = false;
            if (DOM.btnExportBatchPdf) DOM.btnExportBatchPdf.disabled = false;
            if (DOM.btnExportBatchZip) DOM.btnExportBatchZip.disabled = false;

            showToast(`Batch verified & saved successfully! (${state.batchRows.length} records)`, 'success');
        } catch (err) {
            console.error('Batch verification error:', err);
            showToast(err.message || 'Failed to verify batch.', 'error');
        } finally {
            DOM.btnSaveBatch.disabled = false;
            DOM.btnSaveBatch.innerHTML = originalHtml;
        }
    }

    /**
     * Batch Export Action Handlers
     */
    function handleBatchExportCsv() {
        if (!state.currentBatchId) {
            showToast('No active batch to export.', 'error');
            return;
        }
        showToast('Exporting Batch RFC 4180 CSV...', 'info');
        window.open(`/api/export/batch/${state.currentBatchId}/csv`, '_blank');
    }

    function handleBatchExportExcel() {
        if (!state.currentBatchId) {
            showToast('No active batch to export.', 'error');
            return;
        }
        showToast('Exporting Batch Excel (.xlsx)...', 'info');
        window.open(`/api/export/batch/${state.currentBatchId}/excel`, '_blank');
    }

    function getLenderParams() {
        const name = localStorage.getItem('instName') || 'Loan Easier';
        const address = localStorage.getItem('instAddress') || 'Dhaka, Bangladesh';
        return `lender_name=${encodeURIComponent(name)}&lender_address=${encodeURIComponent(address)}`;
    }

    function handleBatchExportPdf() {
        if (!state.currentBatchId) {
            showToast('No active batch to export.', 'error');
            return;
        }
        showToast('Generating Combined Loan Agreement PDF...', 'info');
        window.open(`/api/export/batch/${state.currentBatchId}/pdf?${getLenderParams()}`, '_blank');
    }

    function handleBatchExportZip() {
        if (!state.currentBatchId) {
            showToast('No active batch to export.', 'error');
            return;
        }
        showToast('Generating Loan Agreements ZIP Archive...', 'info');
        window.open(`/api/export/batch/${state.currentBatchId}/zip?${getLenderParams()}`, '_blank');
    }

    /**
     * Tabular Sample Document Generator: creates synthetic multi-row Bengali ledger
     */
    function handleQuickSampleTabular() {
        showToast('Generating sample multi-row tabular ledger scan...', 'info');

        const canvas = document.createElement('canvas');
        canvas.width = 1000;
        canvas.height = 720;
        const ctx = canvas.getContext('2d');

        // Background
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        // Header Title
        ctx.fillStyle = '#0f172a';
        ctx.font = 'bold 22px Helvetica, Arial, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('সরকারি ঋণ বিতরণ ও আদায় খতিয়ান', canvas.width / 2, 45);

        ctx.font = '13px Helvetica, Arial, sans-serif';
        ctx.fillStyle = '#475569';
        ctx.fillText('শাখা: ঢাকা সদর | অর্থবছর: ২০২৬ | ফরম নং-০৭', canvas.width / 2, 72);

        // Table Coordinates
        const startX = 35;
        const startY = 100;
        const tableW = canvas.width - 70;
        const rowH = 46;
        const colWidths = [75, 230, 180, 275, 170];

        // Draw Table Header
        let curX = startX;
        ctx.fillStyle = '#f1f5f9';
        ctx.fillRect(startX, startY, tableW, rowH);
        ctx.strokeStyle = '#334155';
        ctx.lineWidth = 1.5;
        ctx.strokeRect(startX, startY, tableW, rowH);

        const headers = ['ক্রমিক নং', 'নাম', 'মোবাইল', 'ঠিকানা', 'পরিমাণ'];
        ctx.fillStyle = '#0f172a';
        ctx.font = 'bold 15px Helvetica, Arial, sans-serif';
        ctx.textAlign = 'left';

        headers.forEach((hdr, i) => {
            ctx.fillText(hdr, curX + 12, startY + 29);
            if (i > 0) {
                ctx.beginPath();
                ctx.moveTo(curX, startY);
                ctx.lineTo(curX, startY + rowH);
                ctx.stroke();
            }
            curX += colWidths[i];
        });

        // Sample Tabular Rows Data
        const sampleRows = [
            ['LN-001', 'আব্দুর রহিম', '01711223344', 'মিরপুর-১০, ঢাকা', '50,000.00'],
            ['LN-002', 'করিম উদ্দিন', '01822334455', 'উত্তরা, ঢাকা', '75,000.00'],
            ['LN-003', 'ফারহানা আক্তার', '01933445566', 'ধানমন্ডি, ঢাকা', '100,000.00'],
            ['LN-004', 'সালমা বেগম', '01644556677', 'বনশ্রী, ঢাকা', '60,000.00'],
        ];

        let curY = startY + rowH;
        sampleRows.forEach((row) => {
            curX = startX;
            ctx.strokeStyle = '#94a3b8';
            ctx.lineWidth = 1;
            ctx.strokeRect(startX, curY, tableW, rowH);

            ctx.font = '14px Helvetica, Arial, sans-serif';
            ctx.fillStyle = '#1e293b';

            row.forEach((cellText, cIdx) => {
                ctx.fillText(cellText, curX + 12, curY + 28);
                if (cIdx > 0) {
                    ctx.beginPath();
                    ctx.moveTo(curX, curY);
                    ctx.lineTo(curX, curY + rowH);
                    ctx.stroke();
                }
                curX += colWidths[cIdx];
            });

            curY += rowH;
        });

        // Total Row
        curX = startX;
        ctx.fillStyle = '#f8fafc';
        ctx.fillRect(startX, curY, tableW, rowH);
        ctx.strokeStyle = '#334155';
        ctx.lineWidth = 1.5;
        ctx.strokeRect(startX, curY, tableW, rowH);

        ctx.font = 'bold 15px Helvetica, Arial, sans-serif';
        ctx.fillStyle = '#0f172a';
        ctx.fillText('সর্বমোট (৪ জন)', startX + 12, curY + 29);

        const amountColX = startX + colWidths[0] + colWidths[1] + colWidths[2] + colWidths[3];
        ctx.fillText('285,000.00', amountColX + 12, curY + 29);

        // Verification & Signature Box
        curY += rowH + 45;
        ctx.font = 'italic 13px Georgia, serif';
        ctx.fillStyle = '#475569';
        ctx.fillText('যাচাইকারী কর্মকর্তার স্বাক্ষর ও সীলমোহর', startX + 40, curY);
        ctx.beginPath();
        ctx.moveTo(startX + 30, curY - 20);
        ctx.lineTo(startX + 280, curY - 20);
        ctx.stroke();

        ctx.fillText('শাখা ব্যবস্থাপক', canvas.width - 250, curY);
        ctx.beginPath();
        ctx.moveTo(canvas.width - 260, curY - 20);
        ctx.lineTo(canvas.width - 70, curY - 20);
        ctx.stroke();

        const randomNum = Math.floor(1000 + Math.random() * 9000);
        canvas.toBlob((blob) => {
            if (!blob) {
                showToast('Failed to render tabular sample canvas.', 'error');
                return;
            }
            const sampleFile = new File([blob], `tabular_ledger_${randomNum}.png`, { type: 'image/png' });
            handleFileUpload(sampleFile);
        }, 'image/png');
    }

    // =========================================================================
    // Document Viewport (Pan, Zoom, Rotate) Engine
    // =========================================================================
    function loadDocumentImage(src, filename) {
        DOM.viewerFilename.textContent = filename || 'Document Scan';
        
        const isTextFile = filename && (filename.toLowerCase().endsWith('.csv') || filename.toLowerCase().endsWith('.json') || filename.toLowerCase().endsWith('.md'));
        
        if (isTextFile) {
            // For text files, we don't try to load as image
            DOM.documentImage.style.display = 'none';
            DOM.viewportEmpty.style.display = 'flex';
            DOM.viewportEmpty.innerHTML = `<div class="empty-state-icon">📄</div><h3>Data File Loaded</h3><p class="text-muted">Data successfully imported from ${filename}.</p>`;
            DOM.transformLayer.style.display = 'none';
            return;
        }

        DOM.documentImage.style.display = 'block';
        DOM.documentImage.src = src;
        DOM.viewportEmpty.style.display = 'none';
        // Reset empty state in case it was a text file before
        DOM.viewportEmpty.innerHTML = `<div class="empty-state-icon">📄</div><h3>No Document Selected</h3><p class="text-muted">Upload a scan or ledger image to begin OCR extraction.</p>`;
        DOM.transformLayer.style.display = 'block';

        DOM.documentImage.onload = () => {
            state.viewer.naturalWidth = DOM.documentImage.naturalWidth;
            state.viewer.naturalHeight = DOM.documentImage.naturalHeight;
            resetView();
            zoomFit();
        };
    }

    function applyTransform() {
        const { scale, translateX, translateY, rotation } = state.viewer;
        DOM.transformLayer.style.transform =
            `translate(calc(-50% + ${translateX}px), calc(-50% + ${translateY}px)) ` +
            `scale(${scale}) ` +
            `rotate(${rotation}deg)`;

        const pct = Math.round(scale * 100);
        DOM.zoomScaleText.textContent = `${pct}%`;
    }

    function zoomIn() {
        state.viewer.scale = Math.min(4.0, state.viewer.scale + 0.25);
        applyTransform();
    }

    function zoomOut() {
        state.viewer.scale = Math.max(0.2, state.viewer.scale - 0.25);
        applyTransform();
    }

    function zoomActual() {
        state.viewer.scale = 1.0;
        state.viewer.translateX = 0;
        state.viewer.translateY = 0;
        applyTransform();
    }

    function zoomFit() {
        const viewportWidth = DOM.viewportContainer.clientWidth || 500;
        const viewportHeight = DOM.viewportContainer.clientHeight || 500;

        const isRotated90 = (state.viewer.rotation % 180 !== 0);
        const imgW = isRotated90 ? (state.viewer.naturalHeight || 800) : (state.viewer.naturalWidth || 600);
        const imgH = isRotated90 ? (state.viewer.naturalWidth || 600) : (state.viewer.naturalHeight || 800);

        const scaleW = (viewportWidth - 40) / imgW;
        const scaleH = (viewportHeight - 40) / imgH;
        state.viewer.scale = Math.max(0.2, Math.min(scaleW, scaleH, 1.5));
        state.viewer.translateX = 0;
        state.viewer.translateY = 0;
        applyTransform();
    }

    function rotateDoc() {
        state.viewer.rotation = (state.viewer.rotation + 90) % 360;
        applyTransform();
    }

    function resetView() {
        state.viewer.scale = 1.0;
        state.viewer.translateX = 0;
        state.viewer.translateY = 0;
        state.viewer.rotation = 0;
        applyTransform();
    }

    function togglePanMode() {
        state.viewer.panEnabled = !state.viewer.panEnabled;
        if (state.viewer.panEnabled) {
            DOM.btnPanMode.classList.add('active');
            DOM.viewportContainer.style.cursor = 'grab';
        } else {
            DOM.btnPanMode.classList.remove('active');
            DOM.viewportContainer.style.cursor = 'default';
        }
    }

    function onViewerMouseDown(e) {
        if (!state.viewer.panEnabled || e.button !== 0) return;
        state.viewer.isDragging = true;
        state.viewer.startX = e.clientX - state.viewer.translateX;
        state.viewer.startY = e.clientY - state.viewer.translateY;
        DOM.viewportContainer.classList.add('is-dragging');
    }

    function onViewerMouseMove(e) {
        if (!state.viewer.isDragging) return;
        state.viewer.translateX = e.clientX - state.viewer.startX;
        state.viewer.translateY = e.clientY - state.viewer.startY;
        applyTransform();
    }

    function onViewerMouseUp() {
        if (state.viewer.isDragging) {
            state.viewer.isDragging = false;
            DOM.viewportContainer.classList.remove('is-dragging');
        }
    }

    function onViewerWheel(e) {
        e.preventDefault();
        if (e.ctrlKey || e.metaKey) {
            // Zoom in/out
            const factor = e.deltaY < 0 ? 1.15 : 0.85;
            state.viewer.scale = Math.max(0.2, Math.min(4.0, state.viewer.scale * factor));
        } else {
            // Pan vertically or horizontally
            if (e.shiftKey) {
                state.viewer.translateX -= e.deltaY;
            } else {
                state.viewer.translateY -= e.deltaY;
            }
        }
        applyTransform();
    }

    function setViewerLoading(isLoading) {
        if (DOM.viewerLoading) {
            DOM.viewerLoading.style.display = isLoading ? 'flex' : 'none';
        }
    }

    // =========================================================================
    // Quick Sample Document Generator & Auto-Upload
    // =========================================================================
    function handleQuickSample() {
        showToast('Generating sample loan agreement scan...', 'info');

        // Draw realistic document on an in-memory HTML5 Canvas
        const canvas = document.createElement('canvas');
        canvas.width = 850;
        canvas.height = 1100;
        const ctx = canvas.getContext('2d');

        // Background paper texture
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        // Border frame
        ctx.strokeStyle = '#334155';
        ctx.lineWidth = 4;
        ctx.strokeRect(30, 30, canvas.width - 60, canvas.height - 60);

        ctx.strokeStyle = '#94a3b8';
        ctx.lineWidth = 1;
        ctx.strokeRect(36, 36, canvas.width - 72, canvas.height - 72);

        // Header Title
        ctx.fillStyle = '#0f172a';
        ctx.font = 'bold 26px Georgia, serif';
        ctx.textAlign = 'center';
        ctx.fillText('MUTUAL CAPITAL CREDIT UNION', canvas.width / 2, 85);

        ctx.font = 'bold 18px Helvetica, Arial, sans-serif';
        ctx.fillStyle = '#2563eb';
        ctx.fillText('PROMISSORY NOTE & FORMAL LOAN AGREEMENT', canvas.width / 2, 120);

        ctx.strokeStyle = '#2563eb';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(100, 135);
        ctx.lineTo(canvas.width - 100, 135);
        ctx.stroke();

        // Generate dynamic serial
        const randomNum = Math.floor(1000 + Math.random() * 9000);
        const sampleSerial = `LN-2026-${randomNum}`;

        // Structured Loan Data Fields
        ctx.textAlign = 'left';
        ctx.font = '16px Helvetica, Arial, sans-serif';
        ctx.fillStyle = '#1e293b';

        let y = 190;
        const lineSpacing = 42;

        const drawField = (label, value) => {
            ctx.font = 'bold 16px Helvetica, Arial, sans-serif';
            ctx.fillStyle = '#334155';
            ctx.fillText(label, 90, y);

            ctx.font = '16px Courier, monospace';
            ctx.fillStyle = '#0f172a';
            ctx.fillText(value, 300, y);

            // Field baseline
            ctx.strokeStyle = '#e2e8f0';
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(300, y + 6);
            ctx.lineTo(canvas.width - 90, y + 6);
            ctx.stroke();

            y += lineSpacing;
        };

        drawField('Serial Number:', sampleSerial);
        drawField('Borrower Name:', 'Sarah Connor');
        drawField('Mobile Number:', '+1 (555) 429-8821');
        drawField('Address:', '100 Cyberdyne Systems Blvd, Tech City, CA 94043');
        drawField('Principal Loan Amount:', '৳ 75,000.00');

        // Agreement Terms Text
        y += 20;
        ctx.font = 'bold 15px Helvetica, Arial, sans-serif';
        ctx.fillStyle = '#0f172a';
        ctx.fillText('TERMS AND CONDITIONS:', 90, y);

        y += 25;
        ctx.font = '13px Georgia, serif';
        ctx.fillStyle = '#475569';
        const terms = [
            '1. FOR VALUE RECEIVED, the Borrower promises to pay to the Lender the principal sum stated above.',
            '2. Repayment shall be executed in equal monthly installments commencing 30 days from execution date.',
            '3. This agreement is legally binding and entered into under full regulatory compliance.',
            '4. Human-in-the-Loop OCR audit verification record is required prior to capital disbursement.'
        ];
        terms.forEach((line) => {
            ctx.fillText(line, 90, y);
            y += 24;
        });

        // Signatures Block
        y = 940;
        ctx.strokeStyle = '#0f172a';
        ctx.lineWidth = 1.5;

        // Borrower signature line
        ctx.beginPath();
        ctx.moveTo(90, y);
        ctx.lineTo(340, y);
        ctx.stroke();

        ctx.font = 'italic 18px Georgia, serif';
        ctx.fillStyle = '#1e3a8a';
        ctx.fillText('Sarah Connor', 130, y - 8);

        ctx.font = '12px Helvetica, Arial, sans-serif';
        ctx.fillStyle = '#64748b';
        ctx.fillText('Borrower Signature & Date', 90, y + 20);

        // Lender Officer signature line
        ctx.beginPath();
        ctx.moveTo(canvas.width - 340, y);
        ctx.lineTo(canvas.width - 90, y);
        ctx.stroke();

        ctx.font = 'italic 18px Georgia, serif';
        ctx.fillStyle = '#1e3a8a';
        ctx.fillText('Arthur Dent, Loan Officer', canvas.width - 320, y - 8);

        ctx.font = '12px Helvetica, Arial, sans-serif';
        ctx.fillStyle = '#64748b';
        ctx.fillText('Authorized Lending Officer', canvas.width - 340, y + 20);

        // Convert canvas to Blob and upload
        canvas.toBlob((blob) => {
            if (!blob) {
                showToast('Failed to render sample document canvas.', 'error');
                return;
            }
            const sampleFile = new File([blob], `sample_${sampleSerial}.png`, { type: 'image/png' });
            handleFileUpload(sampleFile);
        }, 'image/png');
    }

    // =========================================================================
    // Monthly Export Modals & Endpoints
    // =========================================================================
    function openExportModal() {
        if (DOM.modalExportBackdrop) {
            DOM.modalExportBackdrop.style.display = 'flex';
        }
    }

    function closeExportModal() {
        if (DOM.modalExportBackdrop) {
            DOM.modalExportBackdrop.style.display = 'none';
        }
    }

    function runCsvExport() {
        const monthVal = DOM.exportMonthInput ? DOM.exportMonthInput.value : '';
        const projectType = document.getElementById('export-project-type') ? document.getElementById('export-project-type').value : 'loan';
        let url = `/api/export/csv?project_type=${encodeURIComponent(projectType)}`;
        if (monthVal) {
            url += `&month=${encodeURIComponent(monthVal)}`;
        }
        showToast('Initiating Monthly CSV Export...', 'info');
        window.location.href = url;
        closeExportModal();
    }

    function runExcelExport() {
        const monthVal = DOM.exportMonthInput ? DOM.exportMonthInput.value : '';
        const projectType = document.getElementById('export-project-type') ? document.getElementById('export-project-type').value : 'loan';
        let url = `/api/export/excel?project_type=${encodeURIComponent(projectType)}`;
        if (monthVal) {
            url += `&month=${encodeURIComponent(monthVal)}`;
        }
        showToast('Initiating Monthly Excel Export...', 'info');
        window.location.href = url;
        closeExportModal();
    }

    // =========================================================================
    // Recent Records Modal
    // =========================================================================
    function openRecentModal() {
        if (DOM.modalRecentBackdrop) {
            DOM.modalRecentBackdrop.style.display = 'flex';
            loadRecentRecords();
        }
    }

    function closeRecentModal() {
        if (DOM.modalRecentBackdrop) {
            DOM.modalRecentBackdrop.style.display = 'none';
        }
    }

    async function loadRecentRecords() {
        if (!DOM.recentRecordsTbody) return;
        DOM.recentRecordsTbody.innerHTML = '<tr><td colspan="7" class="text-center loading-cell">Loading records...</td></tr>';

        try {
            const res = await fetch('/api/loans?limit=50');
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const records = await res.json();

            if (!records || records.length === 0) {
                DOM.recentRecordsTbody.innerHTML = '<tr><td colspan="7" class="text-center loading-cell">No loan records stored yet.</td></tr>';
                return;
            }

            DOM.recentRecordsTbody.innerHTML = '';
            records.forEach((rec) => {
                const tr = document.createElement('tr');
                const verifiedTag = rec.verified
                    ? '<span class="badge" style="background:#dcfce7; color:#166534;">Verified</span>'
                    : '<span class="badge" style="background:#fffbeb; color:#92400e;">Draft</span>';

                const formattedAmount = '৳ ' + Number(rec.amount).toLocaleString('en-US', { minimumFractionDigits: 2 });

                tr.innerHTML = `
                    <td class="font-mono">#${rec.id}</td>
                    <td class="font-mono font-bold">${rec.serial_number}</td>
                    <td>${rec.name}</td>
                    <td class="font-mono">${formattedAmount}</td>
                    <td><span class="badge badge-neutral">${rec.ocr_engine_used}</span></td>
                    <td>${verifiedTag}</td>
                    <td>
                        <button type="button" class="btn btn-sm btn-outline btn-load-record" data-id="${rec.id}">
                            Load
                        </button>
                        ${rec.verified ? `<a href="/api/loans/${rec.id}/pdf" target="_blank" class="btn btn-sm btn-ghost" title="Download PDF">PDF</a>` : ''}
                    </td>
                `;
                DOM.recentRecordsTbody.appendChild(tr);
            });

            // Bind load buttons
            DOM.recentRecordsTbody.querySelectorAll('.btn-load-record').forEach((btn) => {
                btn.addEventListener('click', () => {
                    const id = btn.getAttribute('data-id');
                    loadRecordById(id);
                });
            });
        } catch (err) {
            console.error('Error loading recent records:', err);
            DOM.recentRecordsTbody.innerHTML = `<tr><td colspan="7" class="text-center loading-cell" style="color:red;">Failed to load records: ${err.message}</td></tr>`;
        }
    }

    async function loadRecordById(loanId) {
        try {
            showToast(`Loading record #${loanId}...`, 'info');
            const res = await fetch(`/api/loans/${loanId}`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();

            // Populate form
            populateVerificationForm(data);

            // If image path exists, load into viewer
            if (data.image_path) {
                const imgUrl = `/${data.image_path}`;
                loadDocumentImage(imgUrl, `loan_${data.serial_number}.png`);
            }

            closeRecentModal();
            showToast(`Record #${loanId} loaded into verification workspace.`, 'success');
        } catch (err) {
            console.error('Error loading loan by id:', err);
            showToast(`Unable to load record: ${err.message}`, 'error');
        }
    }

    // =========================================================================
    // Toast Notification System
    // =========================================================================
    function showToast(message, type = 'info') {
        if (!DOM.toastContainer) return;

        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;

        const icon = type === 'success' ? '✓' : (type === 'error' ? '✕' : 'ℹ');
        toast.innerHTML = `<span style="font-weight:700;">${icon}</span> <span>${message}</span>`;

        DOM.toastContainer.appendChild(toast);

        setTimeout(() => {
            toast.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(10px)';
            setTimeout(() => toast.remove(), 400);
        }, 4000);
    }

    // Initialize application on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
