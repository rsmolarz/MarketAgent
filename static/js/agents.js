/**
 * Agents JavaScript
 * Handles agent management interface and real-time status updates
 */

class AgentManager {
    constructor() {
        this.agents = [];
        this.updateInterval = 5000; // 5 seconds for better responsiveness
        this.updateTimer = null;
        this.settingsModal = null;
        this.confirmationModal = null;
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.initModals();
        this.loadAgents();
        this.startAutoUpdate();
    }
    
    setupEventListeners() {
        // Bulk actions
        document.getElementById('start-all-agents').addEventListener('click', () => {
            this.confirmBulkAction('start', 'Start All Agents', 'Are you sure you want to start all agents?');
        });
        
        document.getElementById('stop-all-agents').addEventListener('click', () => {
            this.confirmBulkAction('stop', 'Stop All Agents', 'Are you sure you want to stop all agents?');
        });
        
        const forceStartBtn = document.getElementById('force-start-all-agents');
        if (forceStartBtn) {
            forceStartBtn.addEventListener('click', () => {
                this.confirmBulkAction('force-start', 'Force Start All Agents', 
                    'This will start all agents, bypassing regime and drawdown restrictions. Are you sure?');
            });
        }
        
        const resetDrawdownBtn = document.getElementById('reset-drawdown');
        if (resetDrawdownBtn) {
            resetDrawdownBtn.addEventListener('click', () => {
                this.resetDrawdown();
            });
        }
        
        document.getElementById('refresh-agents').addEventListener('click', () => {
            this.loadAgents();
        });
        
        // Settings form
        document.getElementById('save-agent-settings').addEventListener('click', () => {
            this.saveAgentSettings();
        });
        
        // Confirmation modal
        document.getElementById('confirm-action').addEventListener('click', () => {
            this.executeConfirmedAction();
        });
    }
    
    initModals() {
        this.settingsModal = new bootstrap.Modal(document.getElementById('agent-settings-modal'));
        this.confirmationModal = new bootstrap.Modal(document.getElementById('confirmation-modal'));
    }
    
    async loadAgents() {
        try {
            const response = await fetch('/dashboard/api/agents');
            if (!response.ok) throw new Error('Failed to fetch agents');
            
            this.agents = await response.json();
            this.renderAgents();
            this.updateSummary();
            
        } catch (error) {
            console.error('Error loading agents:', error);
            this.showError('Failed to load agents');
        }
    }
    
    renderAgents() {
        const container = document.getElementById('agents-container');
        
        // Clear container safely
        while (container.firstChild) {
            container.removeChild(container.firstChild);
        }
        
        if (!this.agents || this.agents.length === 0) {
            const emptyState = this.createEmptyStateElement();
            container.appendChild(emptyState);
            feather.replace();
            return;
        }
        
        // Create agent elements using safe DOM methods
        this.agents.forEach(agent => {
            const agentElement = this.createAgentCardElement(agent);
            container.appendChild(agentElement);
        });
        
        feather.replace();
        
        // Add event listeners to agent cards
        this.attachAgentEventListeners();
    }
    
    createEmptyStateElement() {
        const emptyDiv = document.createElement('div');
        emptyDiv.className = 'text-center text-muted';
        
        const icon = document.createElement('i');
        icon.setAttribute('data-feather', 'cpu');
        icon.className = 'mb-2';
        
        const paragraph = document.createElement('p');
        paragraph.textContent = 'No agents configured';
        
        emptyDiv.appendChild(icon);
        emptyDiv.appendChild(paragraph);
        
        return emptyDiv;
    }
    
    createAgentCardElement(agent) {
        const statusClass = agent.is_active ? 'agent-active' : (agent.error_count > 0 ? 'agent-error' : 'agent-inactive');
        const statusIndicator = agent.is_active ? 'status-active' : (agent.error_count > 0 ? 'status-error' : 'status-inactive');
        const lastRun = agent.last_run ? this.formatTimestamp(agent.last_run) : 'Never';
        
        // Create main column div
        const colDiv = document.createElement('div');
        colDiv.className = 'col-lg-4 col-md-6 mb-4';
        
        // Create card
        const cardDiv = document.createElement('div');
        cardDiv.className = `card agent-card ${statusClass}`;
        cardDiv.setAttribute('data-agent', agent.agent_name);
        
        // Create card header
        const headerDiv = document.createElement('div');
        headerDiv.className = 'card-header d-flex justify-content-between align-items-center';
        
        const titleElement = document.createElement('h6');
        titleElement.className = 'card-title mb-0';
        
        const statusSpan = document.createElement('span');
        statusSpan.className = `status-indicator ${statusIndicator}`;
        
        const titleText = document.createTextNode(agent.agent_name);
        
        titleElement.appendChild(statusSpan);
        titleElement.appendChild(titleText);
        
        // Create dropdown
        const dropdownDiv = document.createElement('div');
        dropdownDiv.className = 'dropdown';
        
        const dropdownButton = document.createElement('button');
        dropdownButton.className = 'btn btn-sm btn-outline-secondary';
        dropdownButton.type = 'button';
        dropdownButton.setAttribute('data-bs-toggle', 'dropdown');
        
        const dropdownIcon = document.createElement('i');
        dropdownIcon.setAttribute('data-feather', 'more-horizontal');
        dropdownButton.appendChild(dropdownIcon);
        
        const dropdownMenu = document.createElement('ul');
        dropdownMenu.className = 'dropdown-menu';
        
        // Start button
        const startLi = document.createElement('li');
        const startButton = document.createElement('button');
        startButton.className = 'dropdown-item agent-start';
        startButton.setAttribute('data-agent', agent.agent_name);
        if (agent.is_active) startButton.disabled = true;
        
        const startIcon = document.createElement('i');
        startIcon.setAttribute('data-feather', 'play');
        startIcon.className = 'me-2';
        const startText = document.createTextNode('Start');
        
        startButton.appendChild(startIcon);
        startButton.appendChild(startText);
        startLi.appendChild(startButton);
        
        // Stop button
        const stopLi = document.createElement('li');
        const stopButton = document.createElement('button');
        stopButton.className = 'dropdown-item agent-stop';
        stopButton.setAttribute('data-agent', agent.agent_name);
        if (!agent.is_active) stopButton.disabled = true;
        
        const stopIcon = document.createElement('i');
        stopIcon.setAttribute('data-feather', 'pause');
        stopIcon.className = 'me-2';
        const stopText = document.createTextNode('Stop');
        
        stopButton.appendChild(stopIcon);
        stopButton.appendChild(stopText);
        stopLi.appendChild(stopButton);
        
        // Settings button
        const settingsLi = document.createElement('li');
        const settingsButton = document.createElement('button');
        settingsButton.className = 'dropdown-item agent-settings';
        settingsButton.setAttribute('data-agent', agent.agent_name);
        
        const settingsIcon = document.createElement('i');
        settingsIcon.setAttribute('data-feather', 'settings');
        settingsIcon.className = 'me-2';
        const settingsText = document.createTextNode('Settings');
        
        settingsButton.appendChild(settingsIcon);
        settingsButton.appendChild(settingsText);
        settingsLi.appendChild(settingsButton);
        
        // Run button
        const runLi = document.createElement('li');
        const runButton = document.createElement('button');
        runButton.className = 'dropdown-item agent-run';
        runButton.setAttribute('data-agent', agent.agent_name);
        
        const runIcon = document.createElement('i');
        runIcon.setAttribute('data-feather', 'play-circle');
        runIcon.className = 'me-2';
        const runText = document.createTextNode('Run Once');
        
        runButton.appendChild(runIcon);
        runButton.appendChild(runText);
        runLi.appendChild(runButton);
        
        dropdownMenu.appendChild(startLi);
        dropdownMenu.appendChild(stopLi);
        dropdownMenu.appendChild(settingsLi);
        dropdownMenu.appendChild(runLi);
        
        dropdownDiv.appendChild(dropdownButton);
        dropdownDiv.appendChild(dropdownMenu);
        
        headerDiv.appendChild(titleElement);
        headerDiv.appendChild(dropdownDiv);
        
        // Create card body
        const bodyDiv = document.createElement('div');
        bodyDiv.className = 'card-body';
        
        // Status row
        const statusRow = document.createElement('div');
        statusRow.className = 'row text-center mb-3';
        
        const statusCol = document.createElement('div');
        statusCol.className = 'col';
        
        const statusLabel = document.createElement('small');
        statusLabel.className = 'text-muted d-block';
        statusLabel.textContent = 'Status';
        
        const statusBadge = document.createElement('span');
        statusBadge.className = agent.is_active ? 'badge bg-success' : 'badge bg-secondary';
        statusBadge.textContent = agent.is_active ? 'Running' : 'Stopped';
        
        statusCol.appendChild(statusLabel);
        statusCol.appendChild(statusBadge);
        statusRow.appendChild(statusCol);
        
        // Stats row
        const statsRow = document.createElement('div');
        statsRow.className = 'row text-center small text-muted';
        
        // Run count
        const runCountCol = document.createElement('div');
        runCountCol.className = 'col-4';
        const runCountLabel = document.createElement('div');
        runCountLabel.textContent = 'Runs';
        const runCountValue = document.createElement('div');
        runCountValue.className = 'fw-bold text-primary';
        runCountValue.textContent = String(agent.run_count || 0);
        runCountCol.appendChild(runCountLabel);
        runCountCol.appendChild(runCountValue);
        
        // Error count
        const errorCountCol = document.createElement('div');
        errorCountCol.className = 'col-4';
        const errorCountLabel = document.createElement('div');
        errorCountLabel.textContent = 'Errors';
        const errorCountValue = document.createElement('div');
        errorCountValue.className = agent.error_count > 0 ? 'fw-bold text-danger' : 'fw-bold text-success';
        errorCountValue.textContent = String(agent.error_count || 0);
        errorCountCol.appendChild(errorCountLabel);
        errorCountCol.appendChild(errorCountValue);
        
        // Last run
        const lastRunCol = document.createElement('div');
        lastRunCol.className = 'col-4';
        const lastRunLabel = document.createElement('div');
        lastRunLabel.textContent = 'Last Run';
        const lastRunValue = document.createElement('div');
        lastRunValue.className = 'fw-bold';
        lastRunValue.textContent = lastRun;
        lastRunCol.appendChild(lastRunLabel);
        lastRunCol.appendChild(lastRunValue);
        
        statsRow.appendChild(runCountCol);
        statsRow.appendChild(errorCountCol);
        statsRow.appendChild(lastRunCol);
        
        bodyDiv.appendChild(statusRow);
        bodyDiv.appendChild(statsRow);
        
        // Assemble the card
        cardDiv.appendChild(headerDiv);
        cardDiv.appendChild(bodyDiv);
        colDiv.appendChild(cardDiv);
        
        return colDiv;
    }
    
    renderAgentCard(agent) {
        const statusClass = agent.is_active ? 'agent-active' : (agent.error_count > 0 ? 'agent-error' : 'agent-inactive');
        const statusIndicator = agent.is_active ? 'status-active' : (agent.error_count > 0 ? 'status-error' : 'status-inactive');
        const lastRun = agent.last_run ? this.formatTimestamp(agent.last_run) : 'Never';
        
        return `
            <div class="col-lg-4 col-md-6 mb-4">
                <div class="card agent-card ${statusClass}" data-agent="${this.escapeHtml(agent.agent_name)}">
                    <div class="card-header d-flex justify-content-between align-items-center">
                        <h6 class="card-title mb-0">
                            <span class="status-indicator ${statusIndicator}"></span>
                            ${this.escapeHtml(agent.agent_name)}
                        </h6>
                        <div class="dropdown">
                            <button class="btn btn-sm btn-outline-secondary" type="button" data-bs-toggle="dropdown">
                                <i data-feather="more-horizontal"></i>
                            </button>
                            <ul class="dropdown-menu">
                                <li>
                                    <button class="dropdown-item agent-start" data-agent="${this.escapeHtml(agent.agent_name)}" 
                                            ${agent.is_active ? 'disabled' : ''}>
                                        <i data-feather="play" class="me-2"></i>Start
                                    </button>
                                </li>
                                <li>
                                    <button class="dropdown-item agent-stop" data-agent="${this.escapeHtml(agent.agent_name)}" 
                                            ${!agent.is_active ? 'disabled' : ''}>
                                        <i data-feather="pause" class="me-2"></i>Stop
                                    </button>
                                </li>
                                <li><hr class="dropdown-divider"></li>
                                <li>
                                    <button class="dropdown-item agent-settings" data-agent="${this.escapeHtml(agent.agent_name)}">
                                        <i data-feather="settings" class="me-2"></i>Settings
                                    </button>
                                </li>
                            </ul>
                        </div>
                    </div>
                    <div class="card-body">
                        <div class="row text-center mb-3">
                            <div class="col-4">
                                <div class="text-success">
                                    <strong>${this.escapeHtml(String(agent.run_count || 0))}</strong>
                                    <br><small>Runs</small>
                                </div>
                            </div>
                            <div class="col-4">
                                <div class="text-danger">
                                    <strong>${this.escapeHtml(String(agent.error_count || 0))}</strong>
                                    <br><small>Errors</small>
                                </div>
                            </div>
                            <div class="col-4">
                                <div class="text-info">
                                    <strong>${this.escapeHtml(String(agent.schedule_interval || 0))}m</strong>
                                    <br><small>Interval</small>
                                </div>
                            </div>
                        </div>
                        
                        <div class="agent-info">
                            <div class="d-flex justify-content-between align-items-center mb-2">
                                <small class="text-muted">Status:</small>
                                <span class="badge bg-${agent.is_active ? 'success' : 'secondary'}">
                                    ${agent.is_active ? 'Active' : 'Inactive'}
                                </span>
                            </div>
                            <div class="d-flex justify-content-between align-items-center mb-2">
                                <small class="text-muted">Last Run:</small>
                                <small>${lastRun}</small>
                            </div>
                            ${agent.last_error ? `
                            <div class="mt-2">
                                <small class="text-danger">
                                    <i data-feather="alert-triangle" class="me-1"></i>
                                    ${this.escapeHtml(agent.last_error).substring(0, 100)}...
                                </small>
                            </div>
                            ` : ''}
                        </div>
                    </div>
                </div>
            </div>
        `;
    }
    
    attachAgentEventListeners() {
        // Start agent buttons
        document.querySelectorAll('.agent-start').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const agentName = e.target.closest('[data-agent]').dataset.agent;
                this.startAgent(agentName);
            });
        });
        
        // Stop agent buttons
        document.querySelectorAll('.agent-stop').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const agentName = e.target.closest('[data-agent]').dataset.agent;
                this.stopAgent(agentName);
            });
        });
        
        // Settings buttons
        document.querySelectorAll('.agent-settings').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const agentName = e.target.closest('[data-agent]').dataset.agent;
                this.showAgentSettings(agentName);
            });
        });
    }
    
    async startAgent(agentName) {
        try {
            const response = await fetch(`/api/agents/${agentName}/start`, {
                method: 'POST'
            });
            
            if (!response.ok) throw new Error('Failed to start agent');
            
            this.showSuccess(`Agent ${agentName} started successfully`);
            this.loadAgents(); // Refresh agent list
            
        } catch (error) {
            console.error('Error starting agent:', error);
            this.showError(`Failed to start agent ${agentName}`);
        }
    }
    
    async stopAgent(agentName) {
        try {
            const response = await fetch(`/api/agents/${agentName}/stop`, {
                method: 'POST'
            });
            
            if (!response.ok) throw new Error('Failed to stop agent');
            
            this.showSuccess(`Agent ${agentName} stopped successfully`);
            this.loadAgents(); // Refresh agent list
            
        } catch (error) {
            console.error('Error stopping agent:', error);
            this.showError(`Failed to stop agent ${agentName}`);
        }
    }
    
    showAgentSettings(agentName) {
        const agent = this.agents.find(a => a.agent_name === agentName);
        if (!agent) return;
        
        // Populate settings form
        document.getElementById('settings-agent-name').value = agentName;
        document.getElementById('agent-interval').value = agent.schedule_interval;
        
        // Show agent info using safe DOM manipulation
        const infoContainer = document.getElementById('agent-info-container');
        
        // Clear container safely
        while (infoContainer.firstChild) {
            infoContainer.removeChild(infoContainer.firstChild);
        }
        
        // Create main card structure
        const card = document.createElement('div');
        card.className = 'card bg-light';
        
        const cardBody = document.createElement('div');
        cardBody.className = 'card-body';
        
        // Create title
        const title = document.createElement('h6');
        title.className = 'card-title';
        title.textContent = agentName;
        cardBody.appendChild(title);
        
        // Create stats row
        const row = document.createElement('div');
        row.className = 'row';
        
        // Total runs column
        const runCol = document.createElement('div');
        runCol.className = 'col-6';
        const runLabel = document.createElement('small');
        runLabel.className = 'text-muted';
        runLabel.textContent = 'Total Runs:';
        const runValue = document.createElement('div');
        runValue.textContent = String(agent.run_count || 0);
        runCol.appendChild(runLabel);
        runCol.appendChild(runValue);
        
        // Error count column
        const errorCol = document.createElement('div');
        errorCol.className = 'col-6';
        const errorLabel = document.createElement('small');
        errorLabel.className = 'text-muted';
        errorLabel.textContent = 'Error Count:';
        const errorValue = document.createElement('div');
        errorValue.textContent = String(agent.error_count || 0);
        errorCol.appendChild(errorLabel);
        errorCol.appendChild(errorValue);
        
        row.appendChild(runCol);
        row.appendChild(errorCol);
        cardBody.appendChild(row);
        
        // Add last error if exists
        if (agent.last_error) {
            const errorSection = document.createElement('div');
            errorSection.className = 'mt-2';
            
            const errorLabelDiv = document.createElement('small');
            errorLabelDiv.className = 'text-muted';
            errorLabelDiv.textContent = 'Last Error:';
            
            const errorMessageDiv = document.createElement('div');
            errorMessageDiv.className = 'text-danger small';
            errorMessageDiv.textContent = agent.last_error;
            
            errorSection.appendChild(errorLabelDiv);
            errorSection.appendChild(errorMessageDiv);
            cardBody.appendChild(errorSection);
        }
        
        card.appendChild(cardBody);
        infoContainer.appendChild(card);
        
        this.settingsModal.show();
    }
    
    async saveAgentSettings() {
        const agentName = document.getElementById('settings-agent-name').value;
        const interval = parseInt(document.getElementById('agent-interval').value);
        
        if (!agentName || !interval || interval < 1) {
            this.showError('Please provide valid settings');
            return;
        }
        
        try {
            const response = await fetch(`/api/agents/${agentName}/interval`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ interval })
            });
            
            if (!response.ok) throw new Error('Failed to update agent settings');
            
            this.showSuccess(`Agent ${agentName} settings updated successfully`);
            this.settingsModal.hide();
            this.loadAgents(); // Refresh agent list
            
        } catch (error) {
            console.error('Error saving agent settings:', error);
            this.showError(`Failed to update agent ${agentName} settings`);
        }
    }
    
    confirmBulkAction(action, title, message) {
        document.getElementById('confirmation-title').textContent = title;
        document.getElementById('confirmation-message').textContent = message;
        
        // Store action for execution
        document.getElementById('confirm-action').dataset.action = action;
        
        this.confirmationModal.show();
    }
    
    async executeConfirmedAction() {
        const action = document.getElementById('confirm-action').dataset.action;
        
        if (action === 'start') {
            await this.startAllAgents();
        } else if (action === 'stop') {
            await this.stopAllAgents();
        } else if (action === 'force-start') {
            await this.forceStartAllAgents();
        }
        
        this.confirmationModal.hide();
    }
    
    async startAllAgents() {
        const inactiveAgents = this.agents.filter(agent => !agent.is_active);
        
        for (const agent of inactiveAgents) {
            try {
                await this.startAgent(agent.agent_name);
            } catch (error) {
                console.error(`Failed to start agent ${agent.agent_name}:`, error);
            }
        }
        
        this.showSuccess(`Started ${inactiveAgents.length} agents`);
    }
    
    async stopAllAgents() {
        const activeAgents = this.agents.filter(agent => agent.is_active);
        
        for (const agent of activeAgents) {
            try {
                await this.stopAgent(agent.agent_name);
            } catch (error) {
                console.error(`Failed to stop agent ${agent.agent_name}:`, error);
            }
        }
        
        this.showSuccess(`Stopped ${activeAgents.length} agents`);
    }
    
    async forceStartAllAgents() {
        try {
            const response = await fetch('/api/agents/force-start-all', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const data = await response.json();
            
            if (response.ok) {
                this.showSuccess(`Force-started ${data.started?.length || 0} agents (bypassing restrictions)`);
                this.loadAgents();
            } else {
                this.showError(data.error || 'Failed to force-start agents');
            }
        } catch (error) {
            console.error('Failed to force-start all agents:', error);
            this.showError('Failed to force-start agents');
        }
    }
    
    async resetDrawdown() {
        try {
            const response = await fetch('/api/governance/reset-drawdown', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const data = await response.json();
            
            if (data.ok) {
                this.showSuccess(data.message || 'Drawdown state reset');
            } else {
                this.showError(data.error || 'Failed to reset drawdown');
            }
        } catch (error) {
            console.error('Failed to reset drawdown:', error);
            this.showError('Failed to reset drawdown');
        }
    }
    
    updateSummary() {
        const activeCount = this.agents.filter(agent => agent.is_active).length;
        const inactiveCount = this.agents.filter(agent => !agent.is_active && agent.error_count === 0).length;
        const errorCount = this.agents.filter(agent => agent.error_count > 0).length;
        
        document.getElementById('active-agents-summary').textContent = activeCount;
        document.getElementById('inactive-agents-summary').textContent = inactiveCount;
        document.getElementById('error-agents-summary').textContent = errorCount;
    }
    
    startAutoUpdate() {
        this.updateTimer = setInterval(() => {
            this.loadAgents();
        }, this.updateInterval);
    }
    
    stopAutoUpdate() {
        if (this.updateTimer) {
            clearInterval(this.updateTimer);
            this.updateTimer = null;
        }
    }
    
    formatTimestamp(timestamp) {
        if (!timestamp) return 'Never';
        
        // Handle both ISO strings and raw timestamp strings
        const date = new Date(timestamp);
        if (isNaN(date.getTime())) return 'Invalid date';
        
        const now = new Date();
        const diffInSeconds = Math.floor((now - date) / 1000);
        
        if (diffInSeconds < 30) {
            return 'Just now';
        } else if (diffInSeconds < 60) {
            return `${diffInSeconds}s ago`;
        } else if (diffInSeconds < 3600) {
            const minutes = Math.floor(diffInSeconds / 60);
            return `${minutes}m ago`;
        } else if (diffInSeconds < 86400) {
            const hours = Math.floor(diffInSeconds / 3600);
            return `${hours}h ago`;
        } else {
            return date.toLocaleDateString();
        }
    }
    
    escapeHtml(text) {
        if (!text) return '';
        // Use a more explicit escaping approach that satisfies static analysis
        return text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#x27;');
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
        
        // Auto dismiss after 3 seconds
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

// Initialize agent manager when DOM is ready
let agentManager;

document.addEventListener('DOMContentLoaded', function() {
    agentManager = new AgentManager();
});

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    if (agentManager) {
        agentManager.destroy();
    }
});
