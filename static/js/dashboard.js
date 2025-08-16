/**
 * Dashboard JavaScript
 * Handles real-time updates and chart rendering for the main dashboard
 */

class Dashboard {
    constructor() {
        this.updateInterval = 30000; // 30 seconds
        this.chart = null;
        this.updateTimer = null;
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.loadInitialData();
        this.startAutoUpdate();
    }
    
    setupEventListeners() {
        // Refresh button (if any)
        document.addEventListener('click', (e) => {
            if (e.target.id === 'refresh-dashboard') {
                this.loadInitialData();
            }
        });
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
            const response = await fetch('/api/dashboard/stats');
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
            const symbols = ['BTC', 'ETH', 'SPY', 'VIX'];
            const response = await fetch(`/api/market_data?${symbols.map(s => `symbols=${s}`).join('&')}`);
            if (!response.ok) throw new Error('Failed to fetch market data');
            
            const marketData = await response.json();
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
        
        if (!findings || findings.length === 0) {
            container.innerHTML = `
                <div class="text-center text-muted">
                    <i data-feather="inbox" class="mb-2"></i>
                    <p>No recent findings</p>
                </div>
            `;
            feather.replace();
            return;
        }
        
        const findingsHtml = findings.map(finding => `
            <div class="finding-card card mb-2 severity-${finding.severity}">
                <div class="card-body">
                    <div class="d-flex justify-content-between align-items-start">
                        <div class="flex-grow-1">
                            <h6 class="card-title mb-1">
                                <span class="badge bg-${this.getSeverityColor(finding.severity)} me-2">
                                    ${finding.severity.toUpperCase()}
                                </span>
                                ${this.escapeHtml(finding.title)}
                            </h6>
                            <p class="card-text text-muted mb-2">${this.escapeHtml(finding.description)}</p>
                            <small class="text-muted">
                                <i data-feather="cpu" class="me-1"></i>
                                ${this.escapeHtml(finding.agent_name)}
                                ${finding.symbol ? ` • ${this.escapeHtml(finding.symbol)}` : ''}
                                <i data-feather="clock" class="ms-2 me-1"></i>
                                ${this.formatTimestamp(finding.timestamp)}
                            </small>
                        </div>
                        <div class="ms-3">
                            <div class="badge bg-secondary">
                                ${Math.round(finding.confidence * 100)}%
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `).join('');
        
        container.innerHTML = findingsHtml;
        feather.replace();
    }
    
    renderMarketData(marketData) {
        const container = document.getElementById('market-data-container');
        
        if (!marketData || Object.keys(marketData).length === 0) {
            container.innerHTML = `
                <div class="text-center text-muted">
                    <i data-feather="trending-down" class="mb-2"></i>
                    <p>No market data available</p>
                </div>
            `;
            feather.replace();
            return;
        }
        
        const marketHtml = Object.entries(marketData).map(([symbol, data]) => {
            const price = data.price ? data.price.toFixed(2) : 'N/A';
            return `
                <div class="market-item">
                    <div>
                        <div class="market-symbol">${symbol}</div>
                        <small class="text-muted">${data.data_source || 'Market'}</small>
                    </div>
                    <div class="text-end">
                        <div class="market-price">$${price}</div>
                        <small class="text-muted">
                            <i data-feather="clock" class="me-1"></i>
                            ${this.formatTimestamp(data.timestamp)}
                        </small>
                    </div>
                </div>
            `;
        }).join('');
        
        container.innerHTML = marketHtml;
        feather.replace();
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
    
    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    showError(message) {
        const alertHtml = `
            <div class="alert alert-danger alert-dismissible fade show" role="alert">
                <i data-feather="alert-circle" class="me-2"></i>
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;
        
        // Insert at top of main container
        const main = document.querySelector('main');
        main.insertAdjacentHTML('afterbegin', alertHtml);
        feather.replace();
    }
    
    showFindingsError(message) {
        const container = document.getElementById('recent-findings-container');
        container.innerHTML = `
            <div class="text-center text-danger">
                <i data-feather="alert-triangle" class="mb-2"></i>
                <p>${message}</p>
                <button class="btn btn-outline-secondary btn-sm" onclick="dashboard.loadRecentFindings()">
                    <i data-feather="refresh-cw" class="me-1"></i>
                    Retry
                </button>
            </div>
        `;
        feather.replace();
    }
    
    showMarketDataError(message) {
        const container = document.getElementById('market-data-container');
        container.innerHTML = `
            <div class="text-center text-danger">
                <i data-feather="alert-triangle" class="mb-2"></i>
                <p>${message}</p>
                <button class="btn btn-outline-secondary btn-sm" onclick="dashboard.loadMarketData()">
                    <i data-feather="refresh-cw" class="me-1"></i>
                    Retry
                </button>
            </div>
        `;
        feather.replace();
    }
    
    showChartError(message) {
        const ctx = document.getElementById('findings-chart');
        ctx.style.display = 'none';
        
        const container = ctx.parentElement;
        container.innerHTML = `
            <div class="text-center text-danger">
                <i data-feather="alert-triangle" class="mb-2"></i>
                <p>${message}</p>
                <button class="btn btn-outline-secondary btn-sm" onclick="dashboard.loadFindingsChart()">
                    <i data-feather="refresh-cw" class="me-1"></i>
                    Retry
                </button>
            </div>
        `;
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
