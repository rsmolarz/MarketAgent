/**
 * Agents JavaScript
 * Handles agent management interface and real-time status updates
 */

class AgentManager {
    constructor() {
        this.agents = [];
        this.updateInterval = 15000; // 15 seconds
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
            const response = await fetch('/api/agents');
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
        
        if (!this.agents || this.agents.length === 0) {
            container.innerHTML = `
                <div class="text-center text-muted">
                    <i data-feather="cpu" class="mb-2"></i>
                    <p>No agents configured</p>
                </div>
            `;
            feather.replace();
            return;
        }
        
        const agentsHtml = this.agents.map(agent => this.renderAgentCard(agent)).join('');
        container.innerHTML = agentsHtml;
        feather.replace();
        
        // Add event listeners to agent cards
        this.attachAgentEventListeners();
    }
    
    renderAgentCard(agent) {
        const statusClass = agent.is_active ? 'agent-active' : (agent.error_count > 0 ? 'agent-error' : 'agent-inactive');
        const statusIndicator = agent.is_active ? 'status-active' : (agent.error_count > 0 ? 'status-error' : 'status-inactive');
        const lastRun = agent.last_run ? this.formatTimestamp(agent.last_run) : 'Never';
        
        return `
            <div class="col-lg-4 col-md-6 mb-4">
                <div class="card agent-card ${statusClass}" data-agent="${agent.agent_name}">
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
                                    <button class="dropdown-item agent-start" data-agent="${agent.agent_name}" 
                                            ${agent.is_active ? 'disabled' : ''}>
                                        <i data-feather="play" class="me-2"></i>Start
                                    </button>
                                </li>
                                <li>
                                    <button class="dropdown-item agent-stop" data-agent="${agent.agent_name}" 
                                            ${!agent.is_active ? 'disabled' : ''}>
                                        <i data-feather="pause" class="me-2"></i>Stop
                                    </button>
                                </li>
                                <li><hr class="dropdown-divider"></li>
                                <li>
                                    <button class="dropdown-item agent-settings" data-agent="${agent.agent_name}">
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
                                    <strong>${agent.run_count}</strong>
                                    <br><small>Runs</small>
                                </div>
                            </div>
                            <div class="col-4">
                                <div class="text-danger">
                                    <strong>${agent.error_count}</strong>
                                    <br><small>Errors</small>
                                </div>
                            </div>
                            <div class="col-4">
                                <div class="text-info">
                                    <strong>${agent.schedule_interval}m</strong>
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
        
        // Show agent info
        const infoContainer = document.getElementById('agent-info-container');
        infoContainer.innerHTML = `
            <div class="card bg-light">
                <div class="card-body">
                    <h6 class="card-title">${this.escapeHtml(agentName)}</h6>
                    <div class="row">
                        <div class="col-6">
                            <small class="text-muted">Total Runs:</small>
                            <div>${agent.run_count}</div>
                        </div>
                        <div class="col-6">
                            <small class="text-muted">Error Count:</small>
                            <div>${agent.error_count}</div>
                        </div>
                    </div>
                    ${agent.last_error ? `
                    <div class="mt-2">
                        <small class="text-muted">Last Error:</small>
                        <div class="text-danger small">${this.escapeHtml(agent.last_error)}</div>
                    </div>
                    ` : ''}
                </div>
            </div>
        `;
        
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
