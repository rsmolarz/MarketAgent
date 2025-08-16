/**
 * Findings JavaScript
 * Handles findings list, filtering, and detailed view
 */

class FindingsManager {
    constructor() {
        this.findings = [];
        this.filters = {};
        this.updateInterval = 30000; // 30 seconds
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
        
        if (!this.findings || this.findings.length === 0) {
            container.innerHTML = `
                <div class="text-center text-muted py-5">
                    <i data-feather="search" class="mb-3" width="48" height="48"></i>
                    <h5>No findings found</h5>
                    <p>Try adjusting your filters or check back later for new market anomalies.</p>
                </div>
            `;
            feather.replace();
            return;
        }
        
        const findingsHtml = this.findings.map(finding => this.renderFindingCard(finding)).join('');
        container.innerHTML = findingsHtml;
        feather.replace();
        
        // Add event listeners to finding cards
        this.attachFindingEventListeners();
    }
    
    renderFindingCard(finding) {
        const severityIcon = this.getSeverityIcon(finding.severity);
        const severityColor = this.getSeverityColor(finding.severity);
        
        return `
            <div class="finding-card card mb-3 severity-${finding.severity}" data-finding-id="${finding.id}">
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
                        <button class="btn btn-outline-primary btn-sm view-details" data-finding-id="${finding.id}">
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
        
        content.innerHTML = `
            <div class="row mb-4">
                <div class="col-12">
                    <h4 class="mb-2">
                        <span class="badge bg-${severityColor} me-2">${finding.severity.toUpperCase()}</span>
                        ${this.escapeHtml(finding.title)}
                    </h4>
                    <p class="text-muted">${this.escapeHtml(finding.description)}</p>
                </div>
            </div>
            
            <div class="row mb-4">
                <div class="col-md-6">
                    <div class="card bg-light">
                        <div class="card-body">
                            <h6 class="card-title">Basic Information</h6>
                            <table class="table table-sm table-borderless">
                                <tr>
                                    <td><strong>Agent:</strong></td>
                                    <td>${this.escapeHtml(finding.agent_name)}</td>
                                </tr>
                                <tr>
                                    <td><strong>Timestamp:</strong></td>
                                    <td>${new Date(finding.timestamp).toLocaleString()}</td>
                                </tr>
                                <tr>
                                    <td><strong>Confidence:</strong></td>
                                    <td>${Math.round(finding.confidence * 100)}%</td>
                                </tr>
                                <tr>
                                    <td><strong>Symbol:</strong></td>
                                    <td>${finding.symbol ? this.escapeHtml(finding.symbol) : 'N/A'}</td>
                                </tr>
                                <tr>
                                    <td><strong>Market Type:</strong></td>
                                    <td>${finding.market_type ? this.escapeHtml(finding.market_type).toUpperCase() : 'N/A'}</td>
                                </tr>
                            </table>
                        </div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card bg-light">
                        <div class="card-body">
                            <h6 class="card-title">Metadata</h6>
                            ${this.renderMetadata(finding.metadata)}
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        feather.replace();
        this.detailsModal.show();
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
                    <td><strong>${this.formatMetadataKey(key)}:</strong></td>
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
        const alertHtml = `
            <div class="alert alert-success alert-dismissible fade show" role="alert">
                <i data-feather="check-circle" class="me-2"></i>
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;
        
        const main = document.querySelector('main');
        main.insertAdjacentHTML('afterbegin', alertHtml);
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
        const alertHtml = `
            <div class="alert alert-danger alert-dismissible fade show" role="alert">
                <i data-feather="alert-circle" class="me-2"></i>
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;
        
        const main = document.querySelector('main');
        main.insertAdjacentHTML('afterbegin', alertHtml);
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
