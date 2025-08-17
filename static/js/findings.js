/**
 * Findings JavaScript
 * Handles findings list, filtering, and detailed view
 */

class FindingsManager {
    constructor() {
        this.findings = [];
        this.filters = {};
        this.updateInterval = 5000; // 5 seconds for better responsiveness
        this.updateTimer = null;
        this.detailsModal = null;
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.initModals();
        this.loadFindings();
        this.populateFilterOptions();
        this.startAutoUpdate();
    }
    
    setupEventListeners() {
        // Filter form
        document.getElementById('findings-filter-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.applyFilters();
        });
        
        document.getElementById('clear-filters').addEventListener('click', () => {
            this.clearFilters();
        });
        
        document.getElementById('refresh-findings').addEventListener('click', () => {
            this.loadFindings();
        });
        
        document.getElementById('export-findings').addEventListener('click', () => {
            this.exportFindings();
        });
    }
    
    initModals() {
        this.detailsModal = new bootstrap.Modal(document.getElementById('finding-details-modal'));
    }
    
    async loadFindings() {
        try {
            const params = new URLSearchParams(this.filters);
            const response = await fetch(`/api/findings?${params.toString()}`);
            if (!response.ok) throw new Error('Failed to fetch findings');
            
            this.findings = await response.json();
            this.renderFindings();
            this.updateStatistics();
            
        } catch (error) {
            console.error('Error loading findings:', error);
            this.showError('Failed to load findings');
        }
    }
    
    async populateFilterOptions() {
        try {
            // Get unique agents
            const agentsResponse = await fetch('/api/agents');
            if (agentsResponse.ok) {
                const agents = await agentsResponse.json();
                const agentSelect = document.getElementById('agent-filter');
                
                agents.forEach(agent => {
                    const option = document.createElement('option');
                    option.value = agent.agent_name;
                    option.textContent = agent.agent_name;
                    agentSelect.appendChild(option);
                });
            }
        } catch (error) {
            console.error('Error populating filter options:', error);
        }
    }
    
    renderFindings() {
        const container = document.getElementById('findings-container');
        const countElement = document.getElementById('findings-count');
        
        countElement.textContent = this.findings.length;
        
        // Clear container safely
        while (container.firstChild) {
            container.removeChild(container.firstChild);
        }
        
        if (!this.findings || this.findings.length === 0) {
            const emptyState = this.createEmptyStateElement();
            container.appendChild(emptyState);
            feather.replace();
            return;
        }
        
        // Create findings elements using safe DOM methods
        this.findings.forEach(finding => {
            const findingElement = this.createFindingCardElement(finding);
            container.appendChild(findingElement);
        });
        
        feather.replace();
        
        // Add event listeners to finding cards
        this.attachFindingEventListeners();
    }
    
    createEmptyStateElement() {
        const emptyDiv = document.createElement('div');
        emptyDiv.className = 'text-center text-muted py-5';
        
        const icon = document.createElement('i');
        icon.setAttribute('data-feather', 'search');
        icon.className = 'mb-3';
        icon.setAttribute('width', '48');
        icon.setAttribute('height', '48');
        
        const heading = document.createElement('h5');
        heading.textContent = 'No findings found';
        
        const paragraph = document.createElement('p');
        paragraph.textContent = 'Try adjusting your filters or check back later for new market anomalies.';
        
        emptyDiv.appendChild(icon);
        emptyDiv.appendChild(heading);
        emptyDiv.appendChild(paragraph);
        
        return emptyDiv;
    }
    
    createFindingCardElement(finding) {
        const severityIcon = this.getSeverityIcon(finding.severity);
        const severityColor = this.getSeverityColor(finding.severity);
        
        // Create main card div
        const cardDiv = document.createElement('div');
        cardDiv.className = `finding-card card mb-3 severity-${finding.severity}`;
        cardDiv.setAttribute('data-finding-id', String(finding.id));
        
        // Create card header
        const headerDiv = document.createElement('div');
        headerDiv.className = 'card-header';
        
        const headerRow = document.createElement('div');
        headerRow.className = 'row align-items-center';
        
        const titleCol = document.createElement('div');
        titleCol.className = 'col';
        
        const titleContainer = document.createElement('div');
        titleContainer.className = 'd-flex align-items-center';
        
        const icon = document.createElement('i');
        icon.setAttribute('data-feather', severityIcon);
        icon.className = `text-${severityColor} me-2`;
        
        const title = document.createElement('h6');
        title.className = 'mb-0';
        title.textContent = finding.title;
        
        titleContainer.appendChild(icon);
        titleContainer.appendChild(title);
        
        if (finding.symbol) {
            const symbolBadge = document.createElement('span');
            symbolBadge.className = 'badge bg-secondary ms-2';
            symbolBadge.textContent = finding.symbol;
            titleContainer.appendChild(symbolBadge);
        }
        
        titleCol.appendChild(titleContainer);
        
        const badgesCol = document.createElement('div');
        badgesCol.className = 'col-auto';
        
        const severityBadge = document.createElement('span');
        severityBadge.className = `badge bg-${severityColor}`;
        severityBadge.textContent = finding.severity.toUpperCase();
        
        const confidenceBadge = document.createElement('span');
        confidenceBadge.className = 'badge bg-secondary ms-1';
        confidenceBadge.textContent = `${Math.round(finding.confidence * 100)}%`;
        
        badgesCol.appendChild(severityBadge);
        badgesCol.appendChild(confidenceBadge);
        
        headerRow.appendChild(titleCol);
        headerRow.appendChild(badgesCol);
        headerDiv.appendChild(headerRow);
        
        // Create card body
        const bodyDiv = document.createElement('div');
        bodyDiv.className = 'card-body';
        
        const description = document.createElement('p');
        description.className = 'card-text';
        description.textContent = finding.description;
        
        const infoRow = document.createElement('div');
        infoRow.className = 'row text-muted small';
        
        // Agent info
        const agentCol = document.createElement('div');
        agentCol.className = 'col-md-4';
        
        const agentIcon = document.createElement('i');
        agentIcon.setAttribute('data-feather', 'cpu');
        agentIcon.className = 'me-1';
        
        const agentLabel = document.createElement('strong');
        agentLabel.textContent = 'Agent:';
        
        const agentText = document.createTextNode(` ${finding.agent_name}`);
        
        agentCol.appendChild(agentIcon);
        agentCol.appendChild(agentLabel);
        agentCol.appendChild(agentText);
        
        // Time info
        const timeCol = document.createElement('div');
        timeCol.className = 'col-md-4';
        
        const timeIcon = document.createElement('i');
        timeIcon.setAttribute('data-feather', 'clock');
        timeIcon.className = 'me-1';
        
        const timeLabel = document.createElement('strong');
        timeLabel.textContent = 'Time:';
        
        const timeText = document.createTextNode(` ${this.formatTimestamp(finding.timestamp)}`);
        
        timeCol.appendChild(timeIcon);
        timeCol.appendChild(timeLabel);
        timeCol.appendChild(timeText);
        
        // Market info
        const marketCol = document.createElement('div');
        marketCol.className = 'col-md-4';
        
        const marketIcon = document.createElement('i');
        marketIcon.setAttribute('data-feather', 'tag');
        marketIcon.className = 'me-1';
        
        const marketLabel = document.createElement('strong');
        marketLabel.textContent = 'Market:';
        
        const marketText = document.createTextNode(` ${finding.market_type ? finding.market_type.toUpperCase() : 'N/A'}`);
        
        marketCol.appendChild(marketIcon);
        marketCol.appendChild(marketLabel);
        marketCol.appendChild(marketText);
        
        infoRow.appendChild(agentCol);
        infoRow.appendChild(timeCol);
        infoRow.appendChild(marketCol);
        
        // Create button container
        const buttonContainer = document.createElement('div');
        buttonContainer.className = 'mt-3';
        
        const detailsButton = document.createElement('button');
        detailsButton.className = 'btn btn-outline-primary btn-sm view-details';
        detailsButton.setAttribute('data-finding-id', String(finding.id));
        
        const buttonIcon = document.createElement('i');
        buttonIcon.setAttribute('data-feather', 'info');
        buttonIcon.className = 'me-1';
        
        const buttonText = document.createTextNode('View Details');
        
        detailsButton.appendChild(buttonIcon);
        detailsButton.appendChild(buttonText);
        buttonContainer.appendChild(detailsButton);
        
        bodyDiv.appendChild(description);
        bodyDiv.appendChild(infoRow);
        bodyDiv.appendChild(buttonContainer);
        
        // Assemble the card
        cardDiv.appendChild(headerDiv);
        cardDiv.appendChild(bodyDiv);
        
        return cardDiv;
    }
    
    renderFindingCard(finding) {
        const severityIcon = this.getSeverityIcon(finding.severity);
        const severityColor = this.getSeverityColor(finding.severity);
        
        return `
            <div class="finding-card card mb-3 severity-${finding.severity}" data-finding-id="${this.escapeHtml(String(finding.id))}">
                <div class="card-header">
                    <div class="row align-items-center">
                        <div class="col">
                            <div class="d-flex align-items-center">
                                <i data-feather="${severityIcon}" class="text-${severityColor} me-2"></i>
                                <h6 class="mb-0">${this.escapeHtml(finding.title)}</h6>
                                ${finding.symbol ? `<span class="badge bg-secondary ms-2">${this.escapeHtml(finding.symbol)}</span>` : ''}
                            </div>
                        </div>
                        <div class="col-auto">
                            <span class="badge bg-${severityColor}">${finding.severity.toUpperCase()}</span>
                            <span class="badge bg-secondary ms-1">${Math.round(finding.confidence * 100)}%</span>
                        </div>
                    </div>
                </div>
                <div class="card-body">
                    <p class="card-text">${this.escapeHtml(finding.description)}</p>
                    
                    <div class="row text-muted small">
                        <div class="col-md-4">
                            <i data-feather="cpu" class="me-1"></i>
                            <strong>Agent:</strong> ${this.escapeHtml(finding.agent_name)}
                        </div>
                        <div class="col-md-4">
                            <i data-feather="clock" class="me-1"></i>
                            <strong>Time:</strong> ${this.formatTimestamp(finding.timestamp)}
                        </div>
                        <div class="col-md-4">
                            <i data-feather="tag" class="me-1"></i>
                            <strong>Market:</strong> ${finding.market_type ? this.escapeHtml(finding.market_type).toUpperCase() : 'N/A'}
                        </div>
                    </div>
                    
                    <div class="mt-3">
                        <button class="btn btn-outline-primary btn-sm view-details" data-finding-id="${this.escapeHtml(String(finding.id))}">
                            <i data-feather="info" class="me-1"></i>
                            View Details
                        </button>
                    </div>
                </div>
            </div>
        `;
    }
    
    attachFindingEventListeners() {
        document.querySelectorAll('.view-details').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const findingId = e.target.closest('[data-finding-id]').dataset.findingId;
                this.showFindingDetails(findingId);
            });
        });
    }
    
    showFindingDetails(findingId) {
        const finding = this.findings.find(f => f.id == findingId);
        if (!finding) return;
        
        const content = document.getElementById('finding-details-content');
        const severityColor = this.getSeverityColor(finding.severity);
        
        // Clear content safely
        while (content.firstChild) {
            content.removeChild(content.firstChild);
        }
        
        // Create details element using safe DOM methods
        const detailsElement = this.createFindingDetailsElement(finding, severityColor);
        content.appendChild(detailsElement);
        
        feather.replace();
        this.detailsModal.show();
    }
    
    createFindingDetailsElement(finding, severityColor) {
        const container = document.createElement('div');
        
        // Header row
        const headerRow = document.createElement('div');
        headerRow.className = 'row mb-4';
        
        const headerCol = document.createElement('div');
        headerCol.className = 'col-12';
        
        const heading = document.createElement('h4');
        heading.className = 'mb-2';
        
        const severityBadge = document.createElement('span');
        severityBadge.className = `badge bg-${severityColor} me-2`;
        severityBadge.textContent = finding.severity.toUpperCase();
        
        const titleText = document.createTextNode(finding.title);
        
        heading.appendChild(severityBadge);
        heading.appendChild(titleText);
        
        const description = document.createElement('p');
        description.className = 'text-muted';
        description.textContent = finding.description;
        
        headerCol.appendChild(heading);
        headerCol.appendChild(description);
        headerRow.appendChild(headerCol);
        
        // Content row
        const contentRow = document.createElement('div');
        contentRow.className = 'row mb-4';
        
        // Basic info card
        const basicInfoCol = document.createElement('div');
        basicInfoCol.className = 'col-md-6';
        
        const basicInfoCard = document.createElement('div');
        basicInfoCard.className = 'card bg-light';
        
        const basicInfoBody = document.createElement('div');
        basicInfoBody.className = 'card-body';
        
        const basicInfoTitle = document.createElement('h6');
        basicInfoTitle.className = 'card-title';
        basicInfoTitle.textContent = 'Basic Information';
        
        const basicInfoTable = document.createElement('table');
        basicInfoTable.className = 'table table-sm table-borderless';
        
        const basicInfoData = [
            { label: 'Agent', value: finding.agent_name },
            { label: 'Timestamp', value: new Date(finding.timestamp).toLocaleString() },
            { label: 'Confidence', value: `${Math.round(finding.confidence * 100)}%` },
            { label: 'Symbol', value: finding.symbol || 'N/A' },
            { label: 'Market Type', value: finding.market_type ? finding.market_type.toUpperCase() : 'N/A' }
        ];
        
        basicInfoData.forEach(item => {
            const row = document.createElement('tr');
            
            const labelCell = document.createElement('td');
            const labelStrong = document.createElement('strong');
            labelStrong.textContent = `${item.label}:`;
            labelCell.appendChild(labelStrong);
            
            const valueCell = document.createElement('td');
            valueCell.textContent = item.value;
            
            row.appendChild(labelCell);
            row.appendChild(valueCell);
            basicInfoTable.appendChild(row);
        });
        
        basicInfoBody.appendChild(basicInfoTitle);
        basicInfoBody.appendChild(basicInfoTable);
        basicInfoCard.appendChild(basicInfoBody);
        basicInfoCol.appendChild(basicInfoCard);
        
        // Metadata card
        const metadataCol = document.createElement('div');
        metadataCol.className = 'col-md-6';
        
        const metadataCard = document.createElement('div');
        metadataCard.className = 'card bg-light';
        
        const metadataBody = document.createElement('div');
        metadataBody.className = 'card-body';
        
        const metadataTitle = document.createElement('h6');
        metadataTitle.className = 'card-title';
        metadataTitle.textContent = 'Metadata';
        
        const metadataElement = this.createMetadataElement(finding.metadata);
        
        metadataBody.appendChild(metadataTitle);
        metadataBody.appendChild(metadataElement);
        metadataCard.appendChild(metadataBody);
        metadataCol.appendChild(metadataCard);
        
        contentRow.appendChild(basicInfoCol);
        contentRow.appendChild(metadataCol);
        
        container.appendChild(headerRow);
        container.appendChild(contentRow);
        
        return container;
    }
    
    createMetadataElement(metadata) {
        if (!metadata || Object.keys(metadata).length === 0) {
            const noMetadata = document.createElement('p');
            noMetadata.className = 'text-muted';
            noMetadata.textContent = 'No additional metadata available.';
            return noMetadata;
        }
        
        const table = document.createElement('table');
        table.className = 'table table-sm table-borderless';
        
        Object.entries(metadata).forEach(([key, value]) => {
            const row = document.createElement('tr');
            
            const labelCell = document.createElement('td');
            const labelStrong = document.createElement('strong');
            labelStrong.textContent = `${this.formatMetadataKey(key)}:`;
            labelCell.appendChild(labelStrong);
            
            const valueCell = document.createElement('td');
            
            let displayValue = value;
            // Format different types of values
            if (typeof value === 'number') {
                if (key.includes('percent') || key.includes('change')) {
                    displayValue = `${(value * 100).toFixed(2)}%`;
                } else {
                    displayValue = value.toFixed(4);
                }
            } else if (typeof value === 'boolean') {
                displayValue = value ? 'Yes' : 'No';
            } else if (typeof value === 'object') {
                displayValue = JSON.stringify(value, null, 2);
            }
            
            valueCell.textContent = String(displayValue);
            
            row.appendChild(labelCell);
            row.appendChild(valueCell);
            table.appendChild(row);
        });
        
        return table;
    }
    
    renderMetadata(metadata) {
        if (!metadata || Object.keys(metadata).length === 0) {
            return '<p class="text-muted">No additional metadata available.</p>';
        }
        
        const rows = Object.entries(metadata).map(([key, value]) => {
            let displayValue = value;
            
            // Format different types of values
            if (typeof value === 'number') {
                if (key.includes('percent') || key.includes('change')) {
                    displayValue = `${(value * 100).toFixed(2)}%`;
                } else {
                    displayValue = value.toFixed(4);
                }
            } else if (typeof value === 'boolean') {
                displayValue = value ? 'Yes' : 'No';
            } else if (typeof value === 'object') {
                displayValue = JSON.stringify(value, null, 2);
            }
            
            return `
                <tr>
                    <td><strong>${this.escapeHtml(this.formatMetadataKey(key))}:</strong></td>
                    <td>${this.escapeHtml(String(displayValue))}</td>
                </tr>
            `;
        }).join('');
        
        return `
            <table class="table table-sm table-borderless">
                ${rows}
            </table>
        `;
    }
    
    formatMetadataKey(key) {
        return key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }
    
    applyFilters() {
        const form = document.getElementById('findings-filter-form');
        const formData = new FormData(form);
        
        this.filters = {};
        for (const [key, value] of formData.entries()) {
            if (value.trim()) {
                this.filters[key] = value.trim();
            }
        }
        
        this.loadFindings();
    }
    
    clearFilters() {
        document.getElementById('findings-filter-form').reset();
        this.filters = {};
        this.loadFindings();
    }
    
    updateStatistics() {
        const stats = this.calculateStatistics();
        
        document.getElementById('critical-count').textContent = stats.critical;
        document.getElementById('high-count').textContent = stats.high;
        document.getElementById('medium-count').textContent = stats.medium;
        document.getElementById('low-count').textContent = stats.low;
    }
    
    calculateStatistics() {
        const stats = { critical: 0, high: 0, medium: 0, low: 0 };
        
        this.findings.forEach(finding => {
            stats[finding.severity] = (stats[finding.severity] || 0) + 1;
        });
        
        return stats;
    }
    
    exportFindings() {
        if (this.findings.length === 0) {
            this.showError('No findings to export');
            return;
        }
        
        try {
            const csv = this.convertToCSV(this.findings);
            const blob = new Blob([csv], { type: 'text/csv' });
            const url = window.URL.createObjectURL(blob);
            
            const a = document.createElement('a');
            a.href = url;
            a.download = `market_findings_${new Date().toISOString().split('T')[0]}.csv`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            
            window.URL.revokeObjectURL(url);
            this.showSuccess('Findings exported successfully');
            
        } catch (error) {
            console.error('Error exporting findings:', error);
            this.showError('Failed to export findings');
        }
    }
    
    convertToCSV(findings) {
        const headers = ['ID', 'Agent', 'Title', 'Description', 'Severity', 'Confidence', 'Symbol', 'Market Type', 'Timestamp'];
        const rows = findings.map(finding => [
            finding.id,
            finding.agent_name,
            finding.title,
            finding.description.replace(/"/g, '""'),
            finding.severity,
            finding.confidence,
            finding.symbol || '',
            finding.market_type || '',
            finding.timestamp
        ]);
        
        const csvContent = [
            headers.join(','),
            ...rows.map(row => row.map(field => `"${field}"`).join(','))
        ].join('\n');
        
        return csvContent;
    }
    
    startAutoUpdate() {
        this.updateTimer = setInterval(() => {
            this.loadFindings();
        }, this.updateInterval);
    }
    
    stopAutoUpdate() {
        if (this.updateTimer) {
            clearInterval(this.updateTimer);
            this.updateTimer = null;
        }
    }
    
    getSeverityIcon(severity) {
        const icons = {
            'critical': 'alert-circle',
            'high': 'alert-triangle',
            'medium': 'info',
            'low': 'check-circle'
        };
        return icons[severity] || 'circle';
    }
    
    getSeverityColor(severity) {
        const colors = {
            'critical': 'danger',
            'high': 'warning',
            'medium': 'info',
            'low': 'success'
        };
        return colors[severity] || 'secondary';
    }
    
    formatTimestamp(timestamp) {
        if (!timestamp) return 'Unknown';
        
        const date = new Date(timestamp);
        const now = new Date();
        const diffInMinutes = Math.floor((now - date) / (1000 * 60));
        
        if (diffInMinutes < 1) {
            return 'Just now';
        } else if (diffInMinutes < 60) {
            return `${diffInMinutes}m ago`;
        } else if (diffInMinutes < 1440) {
            return `${Math.floor(diffInMinutes / 60)}h ago`;
        } else {
            return date.toLocaleDateString();
        }
    }
    
    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    showSuccess(message) {
        const alertDiv = document.createElement('div');
        alertDiv.className = 'alert alert-success alert-dismissible fade show';
        alertDiv.setAttribute('role', 'alert');
        
        const icon = document.createElement('i');
        icon.setAttribute('data-feather', 'check-circle');
        icon.className = 'me-2';
        
        const messageText = document.createTextNode(message);
        
        const closeButton = document.createElement('button');
        closeButton.type = 'button';
        closeButton.className = 'btn-close';
        closeButton.setAttribute('data-bs-dismiss', 'alert');
        
        alertDiv.appendChild(icon);
        alertDiv.appendChild(messageText);
        alertDiv.appendChild(closeButton);
        
        const main = document.querySelector('main');
        main.insertBefore(alertDiv, main.firstChild);
        feather.replace();
        
        setTimeout(() => {
            const alert = main.querySelector('.alert-success');
            if (alert) {
                const bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            }
        }, 3000);
    }
    
    showError(message) {
        const alertDiv = document.createElement('div');
        alertDiv.className = 'alert alert-danger alert-dismissible fade show';
        alertDiv.setAttribute('role', 'alert');
        
        const icon = document.createElement('i');
        icon.setAttribute('data-feather', 'alert-circle');
        icon.className = 'me-2';
        
        const messageText = document.createTextNode(message);
        
        const closeButton = document.createElement('button');
        closeButton.type = 'button';
        closeButton.className = 'btn-close';
        closeButton.setAttribute('data-bs-dismiss', 'alert');
        
        alertDiv.appendChild(icon);
        alertDiv.appendChild(messageText);
        alertDiv.appendChild(closeButton);
        
        const main = document.querySelector('main');
        main.insertBefore(alertDiv, main.firstChild);
        feather.replace();
    }
    
    destroy() {
        this.stopAutoUpdate();
    }
}

// Initialize findings manager when DOM is ready
let findingsManager;

document.addEventListener('DOMContentLoaded', function() {
    findingsManager = new FindingsManager();
});

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    if (findingsManager) {
        findingsManager.destroy();
    }
});
