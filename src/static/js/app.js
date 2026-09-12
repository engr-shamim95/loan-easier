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
        originalValues: {},
        editedFields: new Set(),
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

        // Document Viewer
        viewerPane: document.getElementById('viewer-pane'),
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

    // =========================================================================
    // Event Listeners Registration
    // =========================================================================
    function bindEvents() {
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
    }

    // =========================================================================
    // Document Upload & OCR Triggering
    // =========================================================================
    async function handleFileUpload(file) {
        if (!file) return;

        // Validate MIME / extension
        const validExtensions = ['.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.webp'];
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

        // Preview image in viewport immediately
        const objectUrl = URL.createObjectURL(file);
        loadDocumentImage(objectUrl, fileName);

        // Show loading spinner
        setViewerLoading(true);

        const formData = new FormData();
        formData.append('file', file);

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
            populateVerificationForm(data);
            showToast(`Document processed successfully via ${data.ocr_engine_used}`, 'success');
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

        // 1. Update Header Badges
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
        window.open(`/api/loans/${state.currentLoanId}/pdf`, '_blank');
    }

    // =========================================================================
    // Document Viewport (Pan, Zoom, Rotate) Engine
    // =========================================================================
    function loadDocumentImage(src, filename) {
        DOM.documentImage.src = src;
        DOM.viewerFilename.textContent = filename || 'Document Scan';
        DOM.viewportEmpty.style.display = 'none';
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
        const factor = e.deltaY < 0 ? 1.15 : 0.85;
        state.viewer.scale = Math.max(0.2, Math.min(4.0, state.viewer.scale * factor));
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
        drawField('Principal Loan Amount:', '$ 75,000.00');

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
        const url = monthVal ? `/api/export/csv?month=${encodeURIComponent(monthVal)}` : '/api/export/csv';
        showToast('Initiating Monthly CSV Export...', 'info');
        window.location.href = url;
        closeExportModal();
    }

    function runExcelExport() {
        const monthVal = DOM.exportMonthInput ? DOM.exportMonthInput.value : '';
        const url = monthVal ? `/api/export/excel?month=${encodeURIComponent(monthVal)}` : '/api/export/excel';
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

                const formattedAmount = '$' + Number(rec.amount).toLocaleString('en-US', { minimumFractionDigits: 2 });

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
