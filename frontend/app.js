// Frontend State
const state = {
    currentView: 'dashboard', // 'dashboard' or 'detail'
    currentTab: 'active',     // 'active' or 'resolved'
    tickets: [],
    currentCaseId: null,
    currentCase: null,
    isLoading: false,
    isTyping: false
};

// Client-side image store: caseId -> array of data-URL strings, newest first.
// The backend does not persist uploaded photos, so we keep them here to show
// up to 3 thumbnails per issue.
const issueImages = {};

function addIssueImage(caseId, dataUrl) {
    if (!issueImages[caseId]) issueImages[caseId] = [];
    issueImages[caseId].unshift(dataUrl);
}

function fileToDataUrl(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = reject;
        reader.readAsDataURL(file);
    });
}

function getIssueImages(caseId, backendImages) {
    return (backendImages || []).concat(issueImages[caseId] || []).slice(0, 3);
}

function renderThumbsHtml(urls) {
    if (!urls.length) return "";
    return `<div class="card-images">${urls.map(url => `<img class="card-thumb" src="${url}" alt="issue photo">`).join("")}</div>`;
}

function renderDetailPhotos(data) {
    const urls = getIssueImages(state.currentCaseId, data.images);
    const section = document.querySelector("#detail-photos-section");
    const photos = document.querySelector("#detail-photos");
    if (!section || !photos) return;

    if (urls.length) {
        photos.innerHTML = urls.map(url => `<img class="detail-thumb" src="${url}" alt="issue photo">`).join("");
        section.style.display = "";
    } else {
        photos.innerHTML = "";
        section.style.display = "none";
    }
}

// Supported Models dictionary for local validation helper
const SUPPORTED_MODELS = {
    "SAMSUNG": ["RSG257", "RF263", "RF28T5001SR"],
    "GE": ["GSS25"],
    "WHIRLPOOL": ["WRS555", "WRFF3336SZ", "WFW95HEDW0"],
    "MAYTAG": ["MFI257"],
    "LG": ["LFXS26", "LDFC2423V", "WM3500"],
    "FRIGIDAIRE": ["FFHB2750"],
    "KITCHENAID": ["KDTM354"],
    "BOSCH": ["BC-70-62H-US(E)", "SHX863"],
    "TRANE": ["4TTR6048J1000AA"]
};

// DOM Elements
const elements = {
    // Views
    dashboardView: document.getElementById('dashboard-view'),
    detailView: document.getElementById('detail-view'),
    
    // Dashboard Components
    btnNewTicket: document.getElementById('btn-new-ticket'),
    ticketsSubtitle: document.getElementById('tickets-subtitle'),
    ticketsLoading: document.getElementById('tickets-loading'),
    ticketsEmpty: document.getElementById('tickets-empty'),
    ticketsGrid: document.getElementById('tickets-grid'),
    footerToggleLink: document.getElementById('footer-toggle-link'),
    footerText: document.getElementById('footer-text'),
    
    // Detail Panel Left
    btnBackToDashboard: document.getElementById('btn-back-to-dashboard'),
    detailStatusBadge: document.getElementById('detail-status-badge'),
    detailTitle: document.getElementById('detail-title'),
    detailMetaLine: document.getElementById('detail-meta-line'),
    detailSymptom: document.getElementById('detail-symptom'),
    detailDiagnosisText: document.getElementById('detail-diagnosis-text'),
    detailDiagnosisConfidence: document.getElementById('detail-diagnosis-confidence'),
    detailStepsList: document.getElementById('detail-steps-list'),
    detailNextStep: document.getElementById('detail-next-step'),
    btnEscalate: document.getElementById('btn-escalate'),
    btnResolve: document.getElementById('btn-resolve'),
    detailEscalationBlock: document.getElementById('detail-escalation-block'),
    escalationRecipient: document.getElementById('escalation-recipient'),
    escalationSubject: document.getElementById('escalation-subject'),
    escalationBody: document.getElementById('escalation-body'),
    
    // Detail Panel Right (Chat)
    chatMessages: document.getElementById('chat-messages'),
    chatTyping: document.getElementById('chat-typing'),
    chatForm: document.getElementById('chat-form'),
    chatInput: document.getElementById('chat-input'),
    btnChatAttach: document.getElementById('btn-chat-attach'),
    chatPhotoInput: document.getElementById('chat-photo-input'),
    btnSendMessage: document.getElementById('btn-send-message'),
    
    // Modal
    newTicketModal: document.getElementById('new-ticket-modal'),
    modalCloseBtn: document.getElementById('modal-close-btn'),
    newTicketForm: document.getElementById('new-ticket-form'),
    btnCancelModal: document.getElementById('btn-cancel-modal'),
    formAppliance: document.getElementById('form-appliance'),
    formBrand: document.getElementById('form-brand'),
    formModel: document.getElementById('form-model'),
    formPlateScan: document.getElementById('form-plate-scan'),
    btnTriggerScan: document.getElementById('btn-trigger-scan'),
    plateScanSpinner: document.getElementById('plate-scan-spinner'),
    plateScanStatus: document.getElementById('plate-scan-status'),
    formSymptom: document.getElementById('form-symptom'),
    formErrorCode: document.getElementById('form-error-code'),
    btnSubmitTicket: document.getElementById('btn-submit-ticket'),
    modelValidationStatus: document.getElementById('model-validation-status')
};

// Relative Time Formatter
function formatRelativeTime(dateString) {
    if (!dateString) return 'unknown';
    const date = new Date(dateString.replace('Z', ''));
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);
    
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays === 1) return '1d ago';
    return `${diffDays}d ago`;
}

// Local Model Validation Helper
function validateModelLocally(brand, model) {
    if (!brand || !model) return null;
    const b = brand.trim().toUpperCase();
    const m = model.trim().toUpperCase();
    
    let normM = m.replace(/\s+/g, "");
    if (normM.includes("/")) {
        normM = normM.split("/")[0];
    }
    if (normM.length > 4 && normM.endsWith("00")) {
        normM = normM.slice(0, -2);
    }
    
    const canonM = normM.replace(/O/g, "0").replace(/I/g, "1").replace(/L/g, "1");

    if (SUPPORTED_MODELS[b]) {
        for (const supported of SUPPORTED_MODELS[b]) {
            let normSup = supported.toUpperCase().replace(/\s+/g, "");
            const canonSup = normSup.replace(/O/g, "0").replace(/I/g, "1").replace(/L/g, "1");
            if (canonM === canonSup || canonM.includes(canonSup) || canonSup.includes(canonM)) {
                return supported;
            }
        }
    }
    
    for (const [key, models] of Object.entries(SUPPORTED_MODELS)) {
        if (b.includes(key) || key.includes(b)) {
            for (const supported of models) {
                let normSup = supported.toUpperCase().replace(/\s+/g, "");
                const canonSup = normSup.replace(/O/g, "0").replace(/I/g, "1").replace(/L/g, "1");
                if (canonM === canonSup || canonM.includes(canonSup) || canonSup.includes(canonM)) {
                    return supported;
                }
            }
        }
    }
    return null;
}

function updateModelValidationLabel() {
    const brand = elements.formBrand.value;
    const model = elements.formModel.value;
    
    if (!brand || !model) {
        elements.modelValidationStatus.classList.add('hidden');
        return;
    }
    
    const matched = validateModelLocally(brand, model);
    elements.modelValidationStatus.classList.remove('hidden');
    
    if (matched) {
        elements.modelValidationStatus.textContent = `✓ Supported Model recognized: ${matched}`;
        elements.modelValidationStatus.className = "validation-label valid";
    } else {
        elements.modelValidationStatus.textContent = `⚠ Model not recognized in database, but you may proceed.`;
        elements.modelValidationStatus.className = "validation-label invalid";
    }
}

// Show/Hide Views
function showView(view) {
    state.currentView = view;
    if (view === 'dashboard') {
        elements.detailView.classList.add('hidden');
        elements.dashboardView.classList.remove('hidden');
        loadTickets();
    } else if (view === 'detail') {
        elements.dashboardView.classList.add('hidden');
        elements.detailView.classList.remove('hidden');
    }
}

// Load tickets list
async function loadTickets() {
    elements.ticketsLoading.classList.remove('hidden');
    elements.ticketsGrid.innerHTML = '';
    elements.ticketsEmpty.classList.add('hidden');
    
    try {
        const openRes = await fetch(`/api/tickets?status=open`);
        const openTickets = await openRes.json();
        
        const resolvedRes = await fetch(`/api/tickets?status=resolved`);
        const resolvedTickets = await resolvedRes.json();
        
        // Update Title & Subtitle based on tab
        const titleH1 = elements.dashboardView.querySelector('.dashboard-title-group h1');
        if (state.currentTab === 'active') {
            titleH1.textContent = 'Open Issues';
            elements.ticketsSubtitle.textContent = `${openTickets.length} unresolved · sorted by most recently updated`;
            elements.footerText.innerHTML = `Showing open issues · <a href="#" id="footer-toggle-link">View resolved (${resolvedTickets.length})</a>`;
        } else {
            titleH1.textContent = 'Resolved Issues';
            elements.ticketsSubtitle.textContent = `${resolvedTickets.length} resolved · archived cases`;
            elements.footerText.innerHTML = `Showing resolved issues · <a href="#" id="footer-toggle-link">View open (${openTickets.length})</a>`;
        }
        
        // Re-bind footer toggle listener since we overwrote innerHTML
        document.getElementById('footer-toggle-link').addEventListener('click', (e) => {
            e.preventDefault();
            state.currentTab = state.currentTab === 'active' ? 'resolved' : 'active';
            loadTickets();
        });
        
        const displayedTickets = state.currentTab === 'active' ? openTickets : resolvedTickets;
        state.tickets = displayedTickets;
        
        elements.ticketsLoading.classList.add('hidden');
        
        if (displayedTickets.length === 0) {
            elements.ticketsEmpty.classList.remove('hidden');
            return;
        }
        
        displayedTickets.forEach(ticket => {
            const card = document.createElement('div');
            card.className = 'ticket-card';
            card.dataset.id = ticket.case_id;
            
            // Map status code to CSS class names
            let statusClass = 'diagnosing';
            if (ticket.status === 'awaiting_user') statusClass = 'awaiting';
            else if (ticket.status === 'escalated') statusClass = 'escalated';
            else if (ticket.status === 'resolved') statusClass = 'resolved';
            
            const badgeLabel = ticket.status === 'awaiting_user' ? 'AWAITING YOU' : ticket.status.toUpperCase();
            
            // Next step color scheme
            let stripBgClass = 'strip-blue';
            if (ticket.status === 'escalated') {
                stripBgClass = 'strip-red';
            }
            
            const actionText = ticket.status === 'escalated' ? 'Review' : 'Continue';
            const actionBtnClass = ticket.status === 'escalated' ? 'btn-secondary' : 'btn-primary';
            
            card.innerHTML = `
                <div class="card-indicator ${statusClass}"></div>
                <div class="card-content">
                    <div class="card-header">
                        <div class="card-title-group">
                            <h3>${ticket.title}</h3>
                            <div class="card-meta-row">
                                <span class="status-badge ${statusClass}">${badgeLabel}</span>
                                <span class="card-meta-text">Model Number ${ticket.model_number} · updated ${formatRelativeTime(ticket.updated_at)}</span>
                            </div>
                        </div>
                    </div>
                    <p class="card-symptom">Symptom: ${ticket.symptom || 'Not described'}</p>
                    ${renderThumbsHtml(getIssueImages(ticket.case_id, ticket.images))}
                    <div class="card-next-step-row">
                        <div class="card-next-step ${stripBgClass}">
                            <strong>Next →</strong> ${ticket.next_step}
                        </div>
                        <button class="btn ${actionBtnClass} card-action-btn">${actionText}</button>
                    </div>
                </div>
            `;
            
            card.addEventListener('click', (e) => {
                // Open ticket detail on card click
                openTicketDetail(ticket.case_id);
            });
            
            elements.ticketsGrid.appendChild(card);
        });
        
    } catch (e) {
        console.error("Error loading tickets:", e);
        elements.ticketsLoading.classList.add('hidden');
        elements.ticketsEmpty.classList.remove('hidden');
    }
}

// Open ticket detail
async function openTicketDetail(caseId) {
    state.currentCaseId = caseId;
    showView('detail');
    await refreshTicketDetails();
    
    // Scroll chat to bottom
    setTimeout(() => {
        elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
    }, 100);
}

// Refresh ticket detail information
async function refreshTicketDetails() {
    if (!state.currentCaseId) return;
    
    try {
        const res = await fetch(`/api/tickets/${state.currentCaseId}`);
        if (!res.ok) throw new Error("Failed to load details");
        
        const data = await res.json();
        state.currentCase = data;
        
        // Update header & meta texts
        elements.detailTitle.textContent = `${data.brand} · ${data.appliance}`;
        elements.detailMetaLine.textContent = `Model Number ${data.model_number}`;
        
        // Symptom text
        elements.detailSymptom.textContent = data.symptom_text;
        elements.detailNextStep.textContent = data.next_step;
        
        // Status Badge
        elements.detailStatusBadge.textContent = data.status === 'awaiting_user' ? 'AWAITING YOU' : data.status.toUpperCase();
        
        let statusClass = 'diagnosing';
        if (data.status === 'awaiting_user') statusClass = 'awaiting';
        else if (data.status === 'escalated') statusClass = 'escalated';
        else if (data.status === 'resolved') statusClass = 'resolved';
        elements.detailStatusBadge.className = `status-badge ${statusClass}`;
        
        // Hide actions if resolved or escalated
        if (data.status === 'resolved') {
            elements.btnEscalate.classList.add('hidden');
            elements.btnResolve.classList.add('hidden');
        } else if (data.status === 'escalated') {
            elements.btnEscalate.classList.add('hidden');
            elements.btnResolve.classList.remove('hidden');
        } else {
            elements.btnEscalate.classList.remove('hidden');
            elements.btnResolve.classList.remove('hidden');
        }
        
        // Diagnosis Box (rendered inline or text format)
        const diagnosisHeader = document.querySelector('.summary-section h3[data-diagnosis]');
        if (data.diagnosis && data.diagnosis.hypothesis) {
            elements.detailDiagnosisText.classList.remove('hidden');
            elements.detailDiagnosisConfidence.classList.remove('hidden');
            
            elements.detailDiagnosisText.textContent = data.diagnosis.hypothesis;
            const conf = data.diagnosis.confidence || 0;
            const percentage = Math.round(conf * 100);
            
            let confidenceText = 'low';
            if (conf >= 0.8) confidenceText = 'high';
            else if (conf >= 0.5) confidenceText = 'medium';
            elements.detailDiagnosisConfidence.textContent = `(confidence: ${confidenceText})`;
        } else {
            elements.detailDiagnosisText.textContent = 'None identified yet.';
            elements.detailDiagnosisConfidence.classList.add('hidden');
        }
        
        // Checklist steps (rendered as dots and indexed labels)
        elements.detailStepsList.innerHTML = '';
        if (data.steps && data.steps.length > 0) {
            data.steps.forEach((step, idx) => {
                const item = document.createElement('div');
                item.className = 'step-dot-item';
                
                let outcomeClass = 'unsure';
                if (step.outcome) outcomeClass = step.outcome.toLowerCase().replace('_', '-');
                
                // Map outcomes
                let displayOutcome = 'pending';
                if (step.outcome === 'resolved') displayOutcome = 'done';
                else if (step.outcome === 'not_resolved') displayOutcome = 'failed';
                else if (step.outcome === 'skipped') displayOutcome = 'skipped';
                
                item.innerHTML = `
                    <span class="step-dot ${outcomeClass}"></span>
                    <span class="step-text">${idx + 1}. ${step.instruction} — <span class="step-outcome">${displayOutcome}</span></span>
                `;
                elements.detailStepsList.appendChild(item);
            });
        } else {
            elements.detailStepsList.innerHTML = `
                <div class="step-dot-item">
                    <span class="step-dot unsure"></span>
                    <span class="step-text">No steps taken yet. Start chat.</span>
                </div>
            `;
        }
        
        // Next Step Strip layout class
        const nextStepBox = document.querySelector('.next-step-strip-box');
        if (data.status === 'escalated') {
            nextStepBox.style.backgroundColor = '#FEF2F2';
            elements.detailNextStep.style.color = '#991B1B';
        } else {
            nextStepBox.style.backgroundColor = '#EFF6FF';
            elements.detailNextStep.style.color = '#1E40AF';
        }
        
        // Escalation Box details
        if (data.status === 'escalated' && data.escalation) {
            elements.detailEscalationBlock.classList.remove('hidden');
            elements.escalationRecipient.textContent = data.escalation.recipient || 'support@appliance-repair.com';
            elements.escalationSubject.textContent = `Service Request: Escalation for case ${data.case_id}`;
            elements.escalationBody.value = data.escalation.drafted_email || '';
        } else {
            elements.detailEscalationBlock.classList.add('hidden');
        }
        
        // Render uploaded photos for this issue
        renderDetailPhotos(data);

        // Render Chat History
        renderChatHistory(data.chat_history);
        
    } catch (e) {
        console.error("Error refreshing ticket details:", e);
    }
}

// Render message list
function renderChatHistory(chatHistory) {
    elements.chatMessages.innerHTML = '';
    
    if (!chatHistory || chatHistory.length === 0) {
        appendChatBubble('assistant', `Hi there! I am your Appliance Diagnostics Assistant. I see that you have initialized a case for your ${state.currentCase?.brand} ${state.currentCase?.appliance}. Let me know how I can help, or say 'recap' to see the current checklist!`);
        return;
    }
    
    chatHistory.forEach(msg => {
        let role = msg.role === 'user' ? 'user' : 'assistant';
        let text = msg.text;
        appendChatBubble(role, text);
    });
}

// Append bubble to chat messages
function appendChatBubble(role, text) {
    const bubble = document.createElement('div');
    bubble.className = `message-bubble ${role}`;
    
    if (role === 'assistant' && text.startsWith('Safety Alert:')) {
        bubble.className = `message-bubble warning`;
        bubble.innerHTML = `⚠️ ${text}`;
    } else if (text.startsWith('[Executing') || text.startsWith('[System:')) {
        bubble.className = `message-bubble system`;
        bubble.innerHTML = `${text}`;
    } else {
        bubble.textContent = text;
    }
    
    elements.chatMessages.appendChild(bubble);
    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
}

// Submit chat message
elements.chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const text = elements.chatInput.value.trim();
    if (!text || state.isTyping) return;
    
    elements.chatInput.value = '';
    appendChatBubble('user', text);
    
    state.isTyping = true;
    elements.chatTyping.classList.remove('hidden');
    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
    
    try {
        const res = await fetch(`/api/tickets/${state.currentCaseId}/message`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text })
        });
        
        if (!res.ok) throw new Error("Failed to send message");
        const data = await res.json();
        
        state.isTyping = false;
        elements.chatTyping.classList.add('hidden');
        
        appendChatBubble('assistant', data.response);
        await refreshTicketDetails();
        
    } catch (e) {
        state.isTyping = false;
        elements.chatTyping.classList.add('hidden');
        appendChatBubble('assistant', "I encountered a communication error. Please retry.");
        console.error(e);
    }
});

// Photo scanner in chat details
elements.btnChatAttach.addEventListener('click', () => {
    elements.chatPhotoInput.click();
});

elements.chatPhotoInput.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    // Capture the photo client-side so it shows in the issue overview
    fileToDataUrl(file).then(url => addIssueImage(state.currentCaseId, url));

    appendChatBubble('user', `[Uploaded photo: ${file.name}]`);
    
    state.isTyping = true;
    elements.chatTyping.classList.remove('hidden');
    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        const res = await fetch(`/api/tickets/${state.currentCaseId}/plate`, {
            method: 'POST',
            body: formData
        });
        
        if (!res.ok) throw new Error("Plate scan failed");
        const details = await res.json();
        
        state.isTyping = false;
        elements.chatTyping.classList.add('hidden');
        
        const descText = `[System: Spec plate photo scanned. Extracted brand: ${details.brand || 'Unknown'}, model: ${details.model_number || 'Unknown'}, error code: ${details.error_code || 'None'}]`;
        appendChatBubble('assistant', descText);
        
        state.isTyping = true;
        elements.chatTyping.classList.remove('hidden');
        
        const instructMsg = `I just uploaded a spec plate photo and got these details: Brand is ${details.brand || 'Unknown'}, Model is ${details.model_number || 'Unknown'}, Error Code is ${details.error_code || 'None'}. Please verify these details and update the case if needed.`;
        
        const messageRes = await fetch(`/api/tickets/${state.currentCaseId}/message`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: instructMsg })
        });
        
        const messageData = await messageRes.json();
        state.isTyping = false;
        elements.chatTyping.classList.add('hidden');
        appendChatBubble('assistant', messageData.response);
        
        await refreshTicketDetails();
        
    } catch (err) {
        state.isTyping = false;
        elements.chatTyping.classList.add('hidden');
        appendChatBubble('assistant', "Could not extract details from the image. Please enter manually.");
        console.error(err);
    }
});

// Escalate Action
elements.btnEscalate.addEventListener('click', async () => {
    if (!state.currentCaseId) return;
    if (!confirm("Are you sure you want to escalate this troubleshooting issue to a professional repair service?")) return;
    
    try {
        const res = await fetch(`/api/tickets/${state.currentCaseId}/escalate`, { method: 'POST' });
        if (!res.ok) throw new Error("Failed to escalate");
        await refreshTicketDetails();
    } catch (e) {
        alert("Escalation failed.");
        console.error(e);
    }
});

// Resolve Action
elements.btnResolve.addEventListener('click', async () => {
    if (!state.currentCaseId) return;
    if (!confirm("Confirm that this appliance issue is fully resolved. This will archive the issue.")) return;

    try {
        const res = await fetch(`/api/tickets/${state.currentCaseId}/resolve`, { method: 'POST' });
        if (!res.ok) throw new Error("Failed to resolve");

        alert("Issue archived as resolved!");
        showView('dashboard');
    } catch (e) {
        alert("Resolution failed.");
        console.error(e);
    }
});

// Back to Dashboard
elements.btnBackToDashboard.addEventListener('click', () => {
    showView('dashboard');
});

// Modal Actions
elements.btnNewTicket.addEventListener('click', () => {
    elements.newTicketModal.classList.remove('hidden');
    elements.newTicketForm.reset();
    elements.modelValidationStatus.classList.add('hidden');
    elements.plateScanStatus.classList.add('hidden');
});

elements.modalCloseBtn.addEventListener('click', () => {
    elements.newTicketModal.classList.add('hidden');
});

elements.btnCancelModal.addEventListener('click', () => {
    elements.newTicketModal.classList.add('hidden');
});

// Live validation on Brand and Model fields
elements.formBrand.addEventListener('input', updateModelValidationLabel);
elements.formModel.addEventListener('input', updateModelValidationLabel);

// Modal Spec Plate OCR Image Upload
elements.btnTriggerScan.addEventListener('click', () => {
    elements.formPlateScan.click();
});

elements.formPlateScan.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    
    elements.plateScanSpinner.classList.remove('hidden');
    elements.plateScanStatus.classList.add('hidden');
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        const res = await fetch(`/api/tickets/new/plate`, {
            method: 'POST',
            body: formData
        });
        
        elements.plateScanSpinner.classList.add('hidden');
        if (!res.ok) throw new Error("Plate scan failed");
        
        const details = await res.json();
        
        if (details.brand) elements.formBrand.value = details.brand;
        if (details.model_number) elements.formModel.value = details.model_number;
        if (details.error_code) elements.formErrorCode.value = details.error_code;
        
        elements.plateScanStatus.classList.remove('hidden');
        updateModelValidationLabel();
        
    } catch (err) {
        elements.plateScanSpinner.classList.add('hidden');
        alert("Failed to scan spec plate image. Please fill form manually.");
        console.error(err);
    }
});

// Submit Ticket Form
elements.newTicketForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const payload = {
        appliance: elements.formAppliance.value,
        brand: elements.formBrand.value,
        model_number: elements.formModel.value,
        symptom_text: elements.formSymptom.value,
        error_code: elements.formErrorCode.value || null
    };
    
    try {
        const res = await fetch('/api/tickets', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (!res.ok) throw new Error("Failed to initialize ticket");
        const data = await res.json();
        elements.newTicketModal.classList.add('hidden');
        
        openTicketDetail(data.case_id);
        
    } catch (err) {
        alert("Failed to create diagnostics case.");
        console.error(err);
    }
});

// Initialize dashboard view on load
window.addEventListener('DOMContentLoaded', () => {
    loadTickets();
});
