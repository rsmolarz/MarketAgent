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
                this.loadFindingsChart(),
                this.loadUncertaintyDecay(),
                this.loadSubstitutionStatus(),
                this.loadUncertaintyBanner()
            ]);
        } catch (error) {
            console.error('Error loading dashboard data:', error);
            this.showError('Failed to load dashboard data');
        }
    }
    
    async loadDashboardStats() {
        try {
            const response = await fetch(`/dashboard/api/stats?hours=${this.timeWindowHours}`);
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
            const response = await fetch('/dashboard/api/findings/recent?limit=10');
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
            const response = await fetch(`/dashboard/api/market_data?hours=${this.timeWindowHours}`);
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
            const response = await fetch('/dashboard/api/chart_data?days=7');
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
            const response = await fetch('/api/analyze', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    finding_id: finding.id,
                    force: false
                })
            });
            
            const result = await response.json();
            
            if (result.reason === 'already_analyzed') {
                if (loadingDiv) loadingDiv.style.display = 'none';
                if (contentDiv) contentDiv.style.display = 'block';
                
                if (alertTitle) alertTitle.textContent = finding.title || 'Market Alert';
                const freshFinding = await this.fetchFindingDetails(finding.id);
                if (analysisText) analysisText.innerHTML = this.formatExistingAnalysis(freshFinding || finding);
                feather.replace();
            } else if (result.ok) {
                if (loadingDiv) loadingDiv.style.display = 'none';
                if (contentDiv) contentDiv.style.display = 'block';
                
                if (alertTitle) alertTitle.textContent = finding.title || 'Market Alert';
                if (analysisText) analysisText.innerHTML = this.formatTripleConfirmation(result, finding);
                feather.replace();
            } else {
                if (loadingDiv) loadingDiv.style.display = 'none';
                if (errorDiv) errorDiv.style.display = 'block';
                
                if (errorMessage) {
                    errorMessage.textContent = result.reason || result.error || 'Failed to analyze alert. Please try again.';
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
    
    formatTripleConfirmation(result, finding) {
        const esc = (t) => this.escapeHtml(t);
        const ta = result.ta || {};
        const council = result.council || {};
        
        let html = '';
        
        if (result.triple_confirmed) {
            html += `<div class="alert alert-success mb-3">
                <i data-feather="check-circle" class="me-2"></i>
                <strong>Triple Confirmed:</strong> All three gates (severity, LLM council, TA) agree. 
                ${result.alerted ? 'Auto-alert sent to whitelist.' : ''}
            </div>`;
        }
        
        if (council.disagreement) {
            html += `<div class="alert alert-warning mb-3">
                <i data-feather="alert-triangle" class="me-2"></i>
                <strong>Disagreement Detected:</strong> LLMs did not reach full consensus.
            </div>`;
        }
        
        const consensusColors = { 'ACT': 'success', 'WATCH': 'warning', 'IGNORE': 'secondary' };
        const consensusAction = council.action || council.consensus || 'WATCH';
        const councilColor = consensusColors[consensusAction] || 'info';
        const councilConf = Math.round((council.confidence || 0) * 100);
        
        html += `<div class="card mb-3 border-${councilColor}">
            <div class="card-header bg-${councilColor} text-white d-flex justify-content-between align-items-center">
                <span><strong>LLM Council:</strong> ${esc(consensusAction)}</span>
                <span class="badge bg-light text-dark">${councilConf}% Confidence</span>
            </div>
            <div class="card-body">`;
        
        if (council.votes) {
            html += '<ul class="mb-0">';
            for (const [model, vote] of Object.entries(council.votes)) {
                html += `<li><strong>${esc(model)}:</strong> ${esc(vote)}</li>`;
            }
            html += '</ul>';
        }
        html += '</div></div>';
        
        const taVote = ta.vote || 'N/A';
        const taColor = consensusColors[taVote] || 'info';
        const taScore = Math.round((ta.score || 0.5) * 100);
        
        html += `<div class="card mb-3 border-${taColor}">
            <div class="card-header bg-${taColor} text-white d-flex justify-content-between align-items-center">
                <span><strong>Technical Analysis:</strong> ${esc(taVote)}</span>
                <span class="badge bg-light text-dark">${taScore}% Score</span>
            </div>
            <div class="card-body">
                <p class="mb-0">${esc(ta.reason || 'RSI and moving average analysis')}</p>
            </div>
        </div>`;
        
        html += `<div class="mt-3 small text-muted">
            <strong>Finding:</strong> ${esc(finding.title || '')} | 
            <strong>Agent:</strong> ${esc(finding.agent_name || '')} | 
            <strong>Severity:</strong> ${esc(finding.severity || '')}
        </div>`;
        
        return html;
    }
    
    formatExistingAnalysis(finding) {
        const esc = (t) => this.escapeHtml(t);
        const consensusColors = { 'ACT': 'success', 'WATCH': 'warning', 'IGNORE': 'secondary' };
        
        const action = finding.consensus_action || 'N/A';
        const actionColor = consensusColors[action] || 'info';
        const conf = Math.round((finding.consensus_confidence || 0) * 100);
        
        let html = `<div class="alert alert-info mb-3">
            <i data-feather="info" class="me-2"></i>
            This finding was previously analyzed.
        </div>`;
        
        html += `<div class="card mb-3 border-${actionColor}">
            <div class="card-header bg-${actionColor} text-white d-flex justify-content-between align-items-center">
                <span><strong>LLM Council:</strong> ${esc(action)}</span>
                <span class="badge bg-light text-dark">${conf}% Confidence</span>
            </div>
            <div class="card-body">`;
        
        if (finding.llm_votes) {
            html += '<ul class="mb-0">';
            for (const [model, vote] of Object.entries(finding.llm_votes)) {
                html += `<li><strong>${esc(model)}:</strong> ${esc(vote)}</li>`;
            }
            html += '</ul>';
        }
        html += '</div></div>';
        
        if (finding.ta_regime) {
            const taColor = consensusColors[finding.ta_regime] || 'info';
            html += `<div class="card mb-3 border-${taColor}">
                <div class="card-header bg-${taColor} text-white">
                    <strong>TA Regime:</strong> ${esc(finding.ta_regime)}
                </div>
            </div>`;
        }
        
        if (finding.alerted) {
            html += `<div class="alert alert-success mt-3">
                <i data-feather="mail" class="me-2"></i>
                Email alert was sent for this finding.
            </div>`;
        }
        
        if (finding.analyzed_at) {
            html += `<div class="mt-3 small text-muted">
                <strong>Analyzed:</strong> ${new Date(finding.analyzed_at).toLocaleString()}
            </div>`;
        }
        
        return html;
    }
    
    async fetchFindingDetails(findingId) {
        try {
            const resp = await fetch(`/api/findings?limit=1000`);
            if (!resp.ok) return null;
            const findings = await resp.json();
            return findings.find(f => f.id === findingId) || null;
        } catch (e) {
            console.error('Error fetching finding details:', e);
            return null;
        }
    }
    
    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = String(text);
        return div.innerHTML;
    }
    
    formatCouncilAnalysis(result) {
        const consensus = result.consensus;
        if (!consensus) {
            return '<p class="text-muted">No consensus available from LLM council.</p>';
        }
        
        const esc = (t) => this.escapeHtml(t);
        
        const verdictColors = {
            'ACT': 'success',
            'WATCH': 'warning',
            'IGNORE': 'secondary'
        };
        const verdict = esc(consensus.verdict);
        const verdictColor = verdictColors[consensus.verdict] || 'info';
        const confidencePct = Math.round((consensus.confidence || 0) * 100);
        
        let html = '';
        
        if (result.uncertainty_spike) {
            html += `<div class="alert alert-warning mb-3">
                <i data-feather="alert-triangle" class="me-2"></i>
                <strong>Uncertainty Detected:</strong> LLMs disagreed on this analysis. Confidence has been adjusted.
            </div>`;
        }
        
        html += `<div class="card mb-3 border-${verdictColor}">
            <div class="card-header bg-${verdictColor} text-white d-flex justify-content-between align-items-center">
                <span><strong>Consensus Verdict:</strong> ${verdict}</span>
                <span class="badge bg-light text-dark">${confidencePct}% Confidence</span>
            </div>
            <div class="card-body">
                <p><strong>Time Horizon:</strong> ${esc(consensus.time_horizon || 'N/A')}</p>
                <p><strong>Positioning:</strong> ${esc(consensus.positioning?.bias || 'neutral')}</p>
                <p>${esc(consensus.one_paragraph_summary || '')}</p>
            </div>
        </div>`;
        
        if (consensus.key_drivers && consensus.key_drivers.length > 0) {
            html += `<div class="mb-3">
                <h6>Key Drivers</h6>
                <ul>${consensus.key_drivers.map(d => `<li>${esc(d)}</li>`).join('')}</ul>
            </div>`;
        }
        
        if (consensus.what_to_verify && consensus.what_to_verify.length > 0) {
            html += `<div class="mb-3">
                <h6>What to Verify</h6>
                <ul>${consensus.what_to_verify.map(v => `<li>${esc(v)}</li>`).join('')}</ul>
            </div>`;
        }
        
        if (consensus.positioning?.suggested_actions && consensus.positioning.suggested_actions.length > 0) {
            html += `<div class="mb-3">
                <h6>Suggested Actions</h6>
                <ul>${consensus.positioning.suggested_actions.map(a => `<li>${esc(a)}</li>`).join('')}</ul>
            </div>`;
        }
        
        if (result.models && result.models.length > 0) {
            html += `<hr><h6 class="mt-3">Model Responses</h6>
            <div class="row">`;
            
            for (const model of result.models) {
                const statusBadge = model.ok 
                    ? '<span class="badge bg-success">OK</span>'
                    : `<span class="badge bg-danger">Error</span>`;
                const latency = model.latency_ms ? `${model.latency_ms}ms` : 'N/A';
                
                html += `<div class="col-md-4 mb-2">
                    <div class="card h-100">
                        <div class="card-header py-1 d-flex justify-content-between align-items-center">
                            <strong>${esc(model.model)}</strong>
                            ${statusBadge}
                        </div>
                        <div class="card-body py-2 small">
                            <p class="mb-1"><strong>Latency:</strong> ${latency}</p>`;
                
                if (model.ok && model.parsed) {
                    html += `<p class="mb-1"><strong>Verdict:</strong> ${esc(model.parsed.verdict || 'N/A')}</p>
                             <p class="mb-0"><strong>Conf:</strong> ${Math.round((model.parsed.confidence || 0) * 100)}%</p>`;
                } else if (model.error) {
                    html += `<p class="text-danger mb-0">${esc(model.error)}</p>`;
                }
                
                html += `</div></div></div>`;
            }
            
            html += `</div>`;
        }
        
        const majority = consensus.majority || {};
        html += `<div class="mt-3 small text-muted">
            <strong>Vote Distribution:</strong> 
            ACT: ${majority.ACT || 0}, WATCH: ${majority.WATCH || 0}, IGNORE: ${majority.IGNORE || 0}
        </div>`;
        
        return html;
    }
    
    async loadUncertaintyDecay() {
        try {
            const response = await fetch('/api/agents/decay');
            if (!response.ok) return;
            
            const data = await response.json();
            const container = document.getElementById('uncertainty-decay-container');
            const badge = document.getElementById('overall-uncertainty-badge');
            
            if (!container) return;
            
            if (!data.agents || data.agents.length === 0) {
                container.innerHTML = '<p class="text-muted text-center">No uncertainty data available yet</p>';
                return;
            }
            
            const maxU = Math.max(...data.agents.map(a => a.uncertainty));
            if (badge) {
                const statusClass = maxU < 0.3 ? 'bg-success' : (maxU < 0.7 ? 'bg-warning text-dark' : 'bg-danger');
                badge.className = `badge ${statusClass}`;
                badge.textContent = `Max: ${(maxU * 100).toFixed(0)}%`;
            }
            
            let html = `<div class="small text-muted mb-2">Regime: ${data.regime}</div>`;
            html += '<div class="row">';
            
            for (const agent of data.agents) {
                const colorClass = agent.status === 'stable' ? 'bg-success' : 
                                   (agent.status === 'degrading' ? 'bg-warning' : 'bg-danger');
                html += `
                    <div class="col-md-6 mb-2">
                        <div class="d-flex align-items-center justify-content-between">
                            <span class="text-truncate" style="max-width: 140px;">${agent.agent.replace('Agent', '')}</span>
                            <div>
                                <span class="badge ${colorClass}">${(agent.decay * 100).toFixed(0)}%</span>
                            </div>
                        </div>
                        <div class="progress" style="height: 4px;">
                            <div class="progress-bar ${colorClass}" style="width: ${agent.decay * 100}%"></div>
                        </div>
                    </div>
                `;
            }
            
            html += '</div>';
            container.innerHTML = html;
        } catch (error) {
            console.error('Error loading uncertainty decay:', error);
        }
    }
    
    async loadSubstitutionStatus() {
        try {
            const response = await fetch('/api/substitution/status');
            if (!response.ok) return;
            
            const data = await response.json();
            const container = document.getElementById('substitution-status-container');
            
            if (!container) return;
            
            if (!data.agents || data.agents.length === 0) {
                container.innerHTML = '<p class="text-muted text-center">No substitution data available</p>';
                return;
            }
            
            const demoted = data.agents.filter(a => a.demoted);
            
            let html = '';
            if (demoted.length === 0) {
                html = '<div class="text-center text-success"><i data-feather="check-circle" class="me-2"></i>All agents operating normally</div>';
            } else {
                html = '<div class="list-group list-group-flush">';
                for (const agent of demoted) {
                    html += `
                        <div class="list-group-item px-0">
                            <div class="d-flex justify-content-between align-items-center">
                                <div>
                                    <span class="text-danger">${agent.agent.replace('Agent', '')}</span>
                                    <span class="badge bg-danger ms-2">${(agent.uncertainty * 100).toFixed(0)}% uncertain</span>
                                </div>
                            </div>
                            <small class="text-muted">Backups: ${agent.backups.join(', ') || 'None'}</small>
                        </div>
                    `;
                }
                html += '</div>';
            }
            
            container.innerHTML = html;
            if (typeof feather !== 'undefined') feather.replace();
        } catch (error) {
            console.error('Error loading substitution status:', error);
        }
    }
    
    async loadUncertaintyBanner() {
        try {
            const [latestRes, transitionRes] = await Promise.all([
                fetch('/api/uncertainty/latest'),
                fetch('/api/uncertainty/transition')
            ]);
            
            const banner = document.getElementById('uncertaintyBanner');
            const txt = document.getElementById('uncertaintyText');
            const badge = document.getElementById('uncertaintyBadge');
            const transitionWarn = document.getElementById('transitionWarning');
            
            if (!banner) return;
            
            let showBanner = false;
            
            if (latestRes.ok) {
                const data = await latestRes.json();
                const level = Number(data.level || 0);
                
                if (data.provisional || level >= 0.7 || (data.label && data.label !== 'normal' && data.label !== 'calm')) {
                    showBanner = true;
                    
                    banner.className = 'alert mb-4';
                    if (level >= 0.8) {
                        banner.classList.add('alert-danger');
                    } else if (level >= 0.6) {
                        banner.classList.add('alert-warning');
                    } else {
                        banner.classList.add('alert-info');
                    }
                    
                    if (txt) {
                        txt.textContent = `— uncertainty=${level.toFixed(2)} (${data.label || 'elevated'}), regime=${data.regime || 'unknown'}`;
                    }
                    
                    if (badge) {
                        badge.className = level >= 0.7 ? 'badge bg-danger' : 'badge bg-warning text-dark';
                        badge.textContent = `${(level * 100).toFixed(0)}%`;
                    }
                }
            }
            
            if (transitionRes.ok) {
                const trans = await transitionRes.json();
                if (trans.transition && transitionWarn) {
                    showBanner = true;
                    transitionWarn.style.display = 'inline';
                    transitionWarn.textContent = trans.severity === 'high' 
                        ? 'Regime Transition Imminent' 
                        : 'Regime Transition Likely';
                } else if (transitionWarn) {
                    transitionWarn.style.display = 'none';
                }
            }
            
            banner.style.display = showBanner ? 'block' : 'none';
            if (typeof feather !== 'undefined') feather.replace();
            
        } catch (error) {
            console.error('Error loading uncertainty banner:', error);
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
