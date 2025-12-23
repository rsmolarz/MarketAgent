/**
 * Dashboard JavaScript
 * Handles real-time updates and chart rendering for the main dashboard
 */

class Dashboard {
    constructor() {
        this.updateInterval = 30000; // 30 seconds
        this.chart = null;
        this.updateTimer = null;
        this.timeWindowHours = 24; // Default time window
        this.currentAnalysisFinding = null; // For retry functionality
        
        this.init();
    }
    
    init() {
        this.loadSavedTimeWindow();
        this.setupEventListeners();
        this.loadInitialData();
        this.startAutoUpdate();
    }
    
    loadSavedTimeWindow() {
        const saved = localStorage.getItem('dashboardTimeWindow');
        if (saved) {
            this.timeWindowHours = parseInt(saved, 10) || 24;
            const select = document.getElementById('time-window-select');
            if (select) {
                select.value = this.timeWindowHours.toString();
            }
        }
    }
    
    setupEventListeners() {
        // Refresh button (if any)
        document.addEventListener('click', (e) => {
            if (e.target.id === 'refresh-dashboard') {
                this.loadInitialData();
            }
        });
        
        // Time window selector
        const timeWindowSelect = document.getElementById('time-window-select');
        if (timeWindowSelect) {
            timeWindowSelect.addEventListener('change', (e) => {
                this.timeWindowHours = parseInt(e.target.value, 10) || 24;
                localStorage.setItem('dashboardTimeWindow', this.timeWindowHours.toString());
                this.loadInitialData();
            });
        }
        
        // AI Analysis retry button
        const retryBtn = document.getElementById('ai-analysis-retry-btn');
        if (retryBtn) {
            retryBtn.addEventListener('click', () => {
                if (this.currentAnalysisFinding) {
                    this.analyzeWithAI(this.currentAnalysisFinding);
                }
            });
        }
    }
    
    async loadInitialData() {
        try {
            // Load all dashboard data concurrently
            await Promise.all([
                this.loadDashboardStats(),
                this.loadRecentFindings(),
                this.loadMarketData(),
                this.loadFindingsChart()
            ]);
        } catch (error) {
            console.error('Error loading dashboard data:', error);
            this.showError('Failed to load dashboard data');
        }
    }
    
    async loadDashboardStats() {
        try {
            const response = await fetch(`/api/dashboard/stats?hours=${this.timeWindowHours}`);
            if (!response.ok) throw new Error('Failed to fetch stats');
            
            const stats = await response.json();
            
            // Update stat cards
            document.getElementById('recent-findings-count').textContent = stats.recent_findings;
            document.getElementById('active-agents-count').textContent = stats.active_agents;
            document.getElementById('critical-findings-count').textContent = stats.critical_findings;
            document.getElementById('total-agents-count').textContent = stats.total_agents;
            
        } catch (error) {
            console.error('Error loading dashboard stats:', error);
        }
    }
    
    async loadRecentFindings() {
        try {
            const response = await fetch('/api/findings/recent?limit=10');
            if (!response.ok) throw new Error('Failed to fetch findings');
            
            const findings = await response.json();
            this.renderRecentFindings(findings);
            
        } catch (error) {
            console.error('Error loading recent findings:', error);
            this.showFindingsError('Failed to load recent findings');
        }
    }
    
    async loadMarketData() {
        try {
            console.log('Loading market data...');
            const response = await fetch(`/api/market_data?hours=${this.timeWindowHours}`);
            console.log('Market data response status:', response.status);
            
            if (!response.ok) throw new Error(`Failed to fetch market data: ${response.status}`);
            
            const marketData = await response.json();
            console.log('Market data received:', marketData);
            this.renderMarketData(marketData);
            
        } catch (error) {
            console.error('Error loading market data:', error);
            this.showMarketDataError('Failed to load market data');
        }
    }
    
    async loadFindingsChart() {
        try {
            const response = await fetch('/api/findings/chart_data?days=7');
            if (!response.ok) throw new Error('Failed to fetch chart data');
            
            const chartData = await response.json();
            this.renderFindingsChart(chartData);
            
        } catch (error) {
            console.error('Error loading chart data:', error);
            this.showChartError('Failed to load chart data');
        }
    }
    
    renderRecentFindings(findings) {
        const container = document.getElementById('recent-findings-container');
        
        // Clear container safely
        while (container.firstChild) {
            container.removeChild(container.firstChild);
        }
        
        if (!findings || findings.length === 0) {
            const emptyDiv = document.createElement('div');
            emptyDiv.className = 'text-center text-muted';
            
            const icon = document.createElement('i');
            icon.setAttribute('data-feather', 'inbox');
            icon.className = 'mb-2';
            
            const text = document.createElement('p');
            text.textContent = 'No recent findings';
            
            emptyDiv.appendChild(icon);
            emptyDiv.appendChild(text);
            container.appendChild(emptyDiv);
            feather.replace();
            return;
        }
        
        findings.forEach(finding => {
            const findingCard = this.createFindingElement(finding);
            container.appendChild(findingCard);
        });
        
        feather.replace();
    }
    
    createFindingElement(finding) {
        // Create main card structure
        const cardDiv = document.createElement('div');
        cardDiv.className = `finding-card card mb-2 severity-${this.sanitizeClassName(finding.severity)}`;
        
        const cardBody = document.createElement('div');
        cardBody.className = 'card-body';
        
        const flexContainer = document.createElement('div');
        flexContainer.className = 'd-flex justify-content-between align-items-start';
        
        // Left side content
        const leftDiv = document.createElement('div');
        leftDiv.className = 'flex-grow-1';
        
        // Title with severity badge
        const titleH6 = document.createElement('h6');
        titleH6.className = 'card-title mb-1';
        
        const severityBadge = document.createElement('span');
        severityBadge.className = `badge bg-${this.getSeverityColor(finding.severity)} me-2`;
        severityBadge.textContent = (finding.severity || '').toUpperCase();
        
        const titleText = document.createTextNode(finding.title || '');
        
        titleH6.appendChild(severityBadge);
        titleH6.appendChild(titleText);
        
        // Description
        const descriptionP = document.createElement('p');
        descriptionP.className = 'card-text text-muted mb-2';
        descriptionP.textContent = finding.description || '';
        
        // Metadata line
        const metaSmall = document.createElement('small');
        metaSmall.className = 'text-muted';
        
        const cpuIcon = document.createElement('i');
        cpuIcon.setAttribute('data-feather', 'cpu');
        cpuIcon.className = 'me-1';
        
        const agentText = document.createTextNode(finding.agent_name || '');
        
        metaSmall.appendChild(cpuIcon);
        metaSmall.appendChild(agentText);
        
        if (finding.symbol) {
            const symbolText = document.createTextNode(` • ${finding.symbol}`);
            metaSmall.appendChild(symbolText);
        }
        
        const clockIcon = document.createElement('i');
        clockIcon.setAttribute('data-feather', 'clock');
        clockIcon.className = 'ms-2 me-1';
        
        const timestampText = document.createTextNode(this.formatTimestamp(finding.timestamp));
        
        metaSmall.appendChild(clockIcon);
        metaSmall.appendChild(timestampText);
        
        // Right side - confidence and AI button
        const rightDiv = document.createElement('div');
        rightDiv.className = 'ms-3 text-end';
        
        const confidenceBadge = document.createElement('div');
        confidenceBadge.className = 'badge bg-secondary mb-2';
        confidenceBadge.textContent = `${Math.round((finding.confidence || 0) * 100)}%`;
        
        const aiButton = document.createElement('button');
        aiButton.className = 'btn btn-outline-primary btn-sm btn-ai-analyze d-block w-100';
        aiButton.setAttribute('data-finding-id', finding.id || '');
        aiButton.setAttribute('title', 'Get AI trading analysis');
        
        const aiIcon = document.createElement('i');
        aiIcon.setAttribute('data-feather', 'cpu');
        aiIcon.className = 'me-1';
        aiIcon.style.width = '12px';
        aiIcon.style.height = '12px';
        
        const aiText = document.createTextNode('Analyze');
        
        aiButton.appendChild(aiIcon);
        aiButton.appendChild(aiText);
        
        aiButton.addEventListener('click', (e) => {
            e.stopPropagation();
            this.analyzeWithAI(finding);
        });
        
        rightDiv.appendChild(confidenceBadge);
        rightDiv.appendChild(aiButton);
        
        // Assemble the structure
        leftDiv.appendChild(titleH6);
        leftDiv.appendChild(descriptionP);
        leftDiv.appendChild(metaSmall);
        
        flexContainer.appendChild(leftDiv);
        flexContainer.appendChild(rightDiv);
        
        cardBody.appendChild(flexContainer);
        cardDiv.appendChild(cardBody);
        
        return cardDiv;
    }
    
    sanitizeClassName(className) {
        // Only allow alphanumeric characters and hyphens for CSS class names
        return (className || '').replace(/[^a-zA-Z0-9-]/g, '');
    }
    
    createErrorElement(message, retryCallback) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'text-center text-danger';
        
        const icon = document.createElement('i');
        icon.setAttribute('data-feather', 'alert-triangle');
        icon.className = 'mb-2';
        
        const messageP = document.createElement('p');
        messageP.textContent = message || 'An error occurred';
        
        const retryButton = document.createElement('button');
        retryButton.className = 'btn btn-outline-secondary btn-sm';
        retryButton.addEventListener('click', retryCallback);
        
        const refreshIcon = document.createElement('i');
        refreshIcon.setAttribute('data-feather', 'refresh-cw');
        refreshIcon.className = 'me-1';
        
        const retryText = document.createTextNode('Retry');
        
        retryButton.appendChild(refreshIcon);
        retryButton.appendChild(retryText);
        
        errorDiv.appendChild(icon);
        errorDiv.appendChild(messageP);
        errorDiv.appendChild(retryButton);
        
        return errorDiv;
    }
    
    renderMarketData(marketData) {
        const container = document.getElementById('market-data-container');
        
        // Clear container safely
        while (container.firstChild) {
            container.removeChild(container.firstChild);
        }
        
        if (!marketData || marketData.length === 0) {
            const emptyDiv = document.createElement('div');
            emptyDiv.className = 'text-center text-muted';
            
            const icon = document.createElement('i');
            icon.setAttribute('data-feather', 'trending-down');
            icon.className = 'mb-2';
            
            const text = document.createElement('p');
            text.textContent = 'No market data available';
            
            emptyDiv.appendChild(icon);
            emptyDiv.appendChild(text);
            container.appendChild(emptyDiv);
            feather.replace();
            return;
        }
        
        marketData.forEach(data => {
            const marketItem = this.createMarketItemElement(data);
            container.appendChild(marketItem);
        });
        
        feather.replace();
    }
    
    createMarketItemElement(data) {
        const marketItem = document.createElement('div');
        marketItem.className = 'market-item d-flex justify-content-between align-items-center py-2 border-bottom';
        
        // Left side with symbol and name
        const leftDiv = document.createElement('div');
        
        const symbolDiv = document.createElement('div');
        symbolDiv.className = 'fw-bold';
        symbolDiv.textContent = data.symbol || '';
        
        const nameSmall = document.createElement('small');
        nameSmall.className = 'text-muted';
        nameSmall.textContent = data.name || data.symbol;
        
        leftDiv.appendChild(symbolDiv);
        leftDiv.appendChild(nameSmall);
        
        // Right side with change and findings count
        const rightDiv = document.createElement('div');
        rightDiv.className = 'text-end';
        
        const changeDiv = document.createElement('div');
        changeDiv.className = data.price_change >= 0 ? 'text-success' : 'text-danger';
        const changeText = data.price_change >= 0 ? `+${data.price_change}%` : `${data.price_change}%`;
        changeDiv.textContent = changeText;
        
        const findingsSmall = document.createElement('small');
        findingsSmall.className = 'text-muted';
        findingsSmall.textContent = `${data.findings_count || 0} findings`;
        
        rightDiv.appendChild(changeDiv);
        rightDiv.appendChild(findingsSmall);
        
        marketItem.appendChild(leftDiv);
        marketItem.appendChild(rightDiv);
        
        return marketItem;
    }
    
    renderFindingsChart(chartData) {
        const ctx = document.getElementById('findings-chart').getContext('2d');
        
        // Destroy existing chart if it exists
        if (this.chart) {
            this.chart.destroy();
        }
        
        this.chart = new Chart(ctx, {
            type: 'line',
            data: chartData,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                    },
                    title: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            stepSize: 1
                        }
                    },
                    x: {
                        type: 'category',
                        ticks: {
                            maxTicksLimit: 12
                        }
                    }
                },
                elements: {
                    line: {
                        tension: 0.1
                    },
                    point: {
                        radius: 3
                    }
                }
            }
        });
    }
    
    startAutoUpdate() {
        this.updateTimer = setInterval(() => {
            this.loadInitialData();
        }, this.updateInterval);
    }
    
    stopAutoUpdate() {
        if (this.updateTimer) {
            clearInterval(this.updateTimer);
            this.updateTimer = null;
        }
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
    

    
    showError(message) {
        const alertDiv = document.createElement('div');
        alertDiv.className = 'alert alert-danger alert-dismissible fade show';
        alertDiv.setAttribute('role', 'alert');
        
        const icon = document.createElement('i');
        icon.setAttribute('data-feather', 'alert-circle');
        icon.className = 'me-2';
        
        const messageText = document.createTextNode(message || 'An error occurred');
        
        const closeButton = document.createElement('button');
        closeButton.type = 'button';
        closeButton.className = 'btn-close';
        closeButton.setAttribute('data-bs-dismiss', 'alert');
        
        alertDiv.appendChild(icon);
        alertDiv.appendChild(messageText);
        alertDiv.appendChild(closeButton);
        
        // Insert at top of main container
        const main = document.querySelector('main');
        main.insertBefore(alertDiv, main.firstChild);
        feather.replace();
    }
    
    showFindingsError(message) {
        const container = document.getElementById('recent-findings-container');
        
        // Clear container safely
        while (container.firstChild) {
            container.removeChild(container.firstChild);
        }
        
        const errorDiv = this.createErrorElement(message, () => this.loadRecentFindings());
        container.appendChild(errorDiv);
        feather.replace();
    }
    
    showMarketDataError(message) {
        const container = document.getElementById('market-data-container');
        
        // Clear container safely
        while (container.firstChild) {
            container.removeChild(container.firstChild);
        }
        
        const errorDiv = this.createErrorElement(message, () => this.loadMarketData());
        container.appendChild(errorDiv);
        feather.replace();
    }
    
    showChartError(message) {
        const ctx = document.getElementById('findings-chart');
        ctx.style.display = 'none';
        
        const container = ctx.parentElement;
        
        // Clear container safely
        while (container.firstChild) {
            container.removeChild(container.firstChild);
        }
        
        const errorDiv = this.createErrorElement(message, () => this.loadFindingsChart());
        container.appendChild(errorDiv);
        feather.replace();
    }
    
    async analyzeWithAI(finding) {
        this.currentAnalysisFinding = finding;
        
        const modal = document.getElementById('aiAnalysisModal');
        const loadingDiv = document.getElementById('ai-analysis-loading');
        const contentDiv = document.getElementById('ai-analysis-content');
        const errorDiv = document.getElementById('ai-analysis-error');
        const alertTitle = document.getElementById('ai-analysis-alert-title');
        const analysisText = document.getElementById('ai-analysis-text');
        const errorMessage = document.getElementById('ai-analysis-error-message');
        
        if (!modal || !loadingDiv || !contentDiv || !errorDiv) {
            console.error('AI Analysis modal elements not found in DOM');
            alert('Unable to open AI analysis. Please refresh the page and try again.');
            return;
        }
        
        if (loadingDiv) loadingDiv.style.display = 'block';
        if (contentDiv) contentDiv.style.display = 'none';
        if (errorDiv) errorDiv.style.display = 'none';
        
        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();
        feather.replace();
        
        try {
            const requestBody = finding.id 
                ? { finding_id: finding.id }
                : { finding_data: finding };
            
            const response = await fetch('/api/analyze_alert', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestBody)
            });
            
            const result = await response.json();
            
            if (result.success) {
                if (loadingDiv) loadingDiv.style.display = 'none';
                if (contentDiv) contentDiv.style.display = 'block';
                
                if (alertTitle) alertTitle.textContent = finding.title || 'Market Alert';
                if (analysisText) analysisText.innerHTML = this.formatAnalysisText(result.analysis);
                feather.replace();
            } else {
                if (loadingDiv) loadingDiv.style.display = 'none';
                if (errorDiv) errorDiv.style.display = 'block';
                
                if (errorMessage) {
                    if (result.error === 'budget_exceeded') {
                        errorMessage.textContent = result.message || 'Cloud budget exceeded. Please upgrade to continue.';
                    } else {
                        errorMessage.textContent = result.message || 'Failed to analyze alert. Please try again.';
                    }
                }
                feather.replace();
            }
        } catch (error) {
            console.error('AI Analysis error:', error.message || error);
            if (loadingDiv) loadingDiv.style.display = 'none';
            if (errorDiv) errorDiv.style.display = 'block';
            const errMsg = error.message || 'Unknown error';
            if (errorMessage) errorMessage.textContent = `Error: ${errMsg}. Please try again.`;
            feather.replace();
        }
    }
    
    formatAnalysisText(text) {
        if (!text) return '';
        
        let formatted = text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
        
        formatted = formatted
            .replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
            .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.+?)\*/g, '<em>$1</em>');
        
        formatted = formatted.replace(/^#{1,3}\s*(.+)$/gm, '<h2>$1</h2>');
        
        const lines = formatted.split('\n');
        let result = [];
        let inList = false;
        
        for (let line of lines) {
            const trimmed = line.trim();
            
            if (trimmed.match(/^[\-\*]\s+/)) {
                if (!inList) {
                    result.push('<ul>');
                    inList = true;
                }
                result.push('<li>' + trimmed.replace(/^[\-\*]\s+/, '') + '</li>');
            } else if (trimmed.match(/^\d+\.\s+/)) {
                if (!inList) {
                    result.push('<ol>');
                    inList = true;
                }
                result.push('<li>' + trimmed.replace(/^\d+\.\s+/, '') + '</li>');
            } else {
                if (inList) {
                    result.push(result[result.length - 1].startsWith('<ol>') ? '</ol>' : '</ul>');
                    inList = false;
                }
                if (trimmed) {
                    if (!trimmed.startsWith('<h2>')) {
                        result.push('<p>' + trimmed + '</p>');
                    } else {
                        result.push(trimmed);
                    }
                }
            }
        }
        
        if (inList) {
            result.push('</ul>');
        }
        
        return result.join('\n');
    }
    
    destroy() {
        this.stopAutoUpdate();
        if (this.chart) {
            this.chart.destroy();
        }
    }
}

// Initialize dashboard when DOM is ready
window.dashboard = null;

document.addEventListener('DOMContentLoaded', function() {
    window.dashboard = new Dashboard();
});

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    if (window.dashboard) {
        window.dashboard.destroy();
    }
});
