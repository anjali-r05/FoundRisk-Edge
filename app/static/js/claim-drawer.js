const ClaimDrawer = (() => {
    const overlay = () => document.getElementById("claim-drawer-overlay");
    const body = () => document.getElementById("drawer-body");
    function metricLabel(type) { return {revenue:"Revenue",customer_count:"Customer Count",market_size:"Market Size"}[type] || type; }
    function badgeClass(label) { return {High:"badge-high",Medium:"badge-medium",Low:"badge-low"}[label] || "badge-neutral"; }
    function signal(present, label, detail) {
        return `<div class="drawer-signal ${present ? "present":"absent"}"><span>${present ? "✓":"—"}</span><div><strong>${label}</strong><small>${detail}</small></div></div>`;
    }
    async function open(evidenceId) {
        try {
            const {evidence} = await Api.getEvidence(evidenceId);
            const claim = evidence.claim || {};
            const source = evidence.source || claim.source || {};
            const normalized = evidence.value == null ? "—" : `${evidence.currency==="INR"?"₹":evidence.currency==="USD"?"$":""}${Number(evidence.value).toLocaleString("en-IN",{maximumFractionDigits:2})}`;
            const original = evidence.original_value == null ? "—" : `${evidence.currency==="INR"?"₹":evidence.currency==="USD"?"$":""}${escapeHtml(evidence.original_value)}${evidence.original_unit ? " "+escapeHtml(evidence.original_unit) : ""}`;
            const locationParts = [];
            if (source.page != null) locationParts.push(`Page ${source.page}`);
            if (source.sheet) locationParts.push(`Sheet ${escapeHtml(source.sheet)}`);
            if (source.cell) locationParts.push(`Cell ${escapeHtml(source.cell)}`);
            if (source.row != null) locationParts.push(`Row ${source.row}`);
            if (source.column) locationParts.push(`Column ${escapeHtml(source.column)}`);
            const location = locationParts.length ? locationParts.join(" · ") : "Source location unavailable";
            const hasSource = locationParts.length > 0;
            body().innerHTML = `
                <div class="drawer-kicker">EVIDENCE RECORD #${Number(evidence.id)}</div>
                <div class="drawer-title-row"><div><div class="drawer-eyebrow">${escapeHtml(metricLabel(evidence.metric_type))}</div><h2>${escapeHtml(evidence.period || "Period not confirmed")}</h2></div><span class="badge ${badgeClass(claim.confidence_label || evidence.confidence_label)}">${escapeHtml(claim.confidence_label || evidence.confidence_label || "Unrated")}</span></div>
                <div class="drawer-eyebrow">VALUE AS WRITTEN IN SOURCE</div>
                <div class="drawer-value">${original}</div>
                <div class="drawer-grid">
                    <div><span>Original value</span><strong>${original}</strong></div>
                    <div><span>Normalized value</span><strong>${escapeHtml(normalized)}</strong></div>
                    <div><span>Currency</span><strong>${escapeHtml(evidence.currency || "Not specified")}</strong></div>
                    <div><span>Period</span><strong>${escapeHtml(evidence.period || "Not confirmed")}</strong></div>
                </div>

                <div class="drawer-section">
                    <div class="drawer-eyebrow">SOURCE DOCUMENT</div>
                    <div class="source-document-card">
                        <span class="source-document-icon">▤</span>
                        <div><strong>${escapeHtml(evidence.document_filename || "Source document unavailable")}</strong><span>${escapeHtml(location)}</span></div>
                    </div>
                    <div class="provenance-status ${hasSource ? "captured" : "missing"}">${hasSource ? "✓ Source location captured during parsing" : "! Exact source location was not captured. No page, sheet, cell or row is inferred."}</div>
                </div>

                <div class="drawer-section">
                    <div class="drawer-section-head"><div><div class="drawer-eyebrow">WHY THIS WAS EXTRACTED</div><h3>Extraction signals</h3></div><span class="confidence-number">${Math.round((claim.confidence_score || 0)*100)}%</span></div>
                    <div class="signal-grid">
                        ${signal(!!(claim.signals && claim.signals.keyword),"Metric keyword", claim.matched_keyword ? `Matched “${escapeHtml(claim.matched_keyword)}”` : "No keyword")}
                        ${signal(!!(claim.signals && claim.signals.number),"Numeric value", claim.signals && claim.signals.number ? "A numeric value was detected" : "No numeric value")}
                        ${signal(!!(claim.signals && claim.signals.unit),"Unit / currency", claim.signals && claim.signals.unit ? "Currency or magnitude unit detected" : "No unit or currency")}
                        ${signal(!!(claim.signals && claim.signals.period),"Fiscal period", claim.signals && claim.signals.period ? "A period token was detected" : "Period not confirmed")}
                    </div>
                </div>

                <div class="drawer-section">
                    <div class="drawer-eyebrow">ORIGINAL SOURCE TEXT</div>
                    <div class="source-quote">${claim.raw_text ? `“${escapeHtml(claim.raw_text)}”` : "No original source excerpt was stored for this record."}</div>
                    <p class="drawer-note">This excerpt is the text captured by the parser. It is not an image or a full-page preview of the original file.</p>
                </div>

                <div class="drawer-section">
                    <div class="drawer-eyebrow">NORMALIZATION</div>
                    <div class="normalization-line"><span>Written in source</span><strong>${original}</strong></div>
                    <div class="normalization-line"><span>Stored as absolute value</span><strong>${escapeHtml(normalized)}</strong></div>
                    <p class="drawer-note">Currency is preserved as provided. FoundRisk Edge does not silently convert between currencies.</p>
                </div>
            `;
            overlay().classList.add("open");
            document.body.classList.add("drawer-open");
        } catch(e) { AppUI.toast(e.message || "Could not open evidence.", "error"); }
    }
    function close() { overlay().classList.remove("open"); document.body.classList.remove("drawer-open"); }
    function escapeHtml(str) { return AppUI.escapeHtml(str); }
    document.addEventListener("DOMContentLoaded", () => {
        const ov=overlay(); if(!ov) return;
        document.getElementById("drawer-close-btn").addEventListener("click", close);
        ov.addEventListener("click", e => { if(e.target===ov) close(); });
        document.addEventListener("keydown", e => { if(e.key==="Escape") close(); });
    });
    return {open,close};
})();
