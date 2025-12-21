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
        
        // Right side confidence
        const rightDiv = document.createElement('div');
        rightDiv.className = 'ms-3';
        
        const confidenceBadge = document.createElement('div');
        confidenceBadge.className = 'badge bg-secondary';
        confidenceBadge.textContent = `${Math.round((finding.confidence || 0) * 100)}%`;
        
        rightDiv.appendChild(confidenceBadge);
        
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
    
    destroy() {
        this.stopAutoUpdate();
        if (this.chart) {
            this.chart.destroy();
        }
    }
}

// Initialize dashboard when DOM is ready
let dashboard;

document.addEventListener('DOMContentLoaded', function() {
    dashboard = new Dashboard();
});

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    if (dashboard) {
        dashboard.destroy();
    }
});
