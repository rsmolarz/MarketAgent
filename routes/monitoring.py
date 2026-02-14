from flask import Blueprint, render_template_string
from replit_auth import require_login
import logging

logger = logging.getLogger(__name__)

monitoring_bp = Blueprint('monitoring', __name__)

@monitoring_bp.route('/dashboard/monitoring')
@require_login
def monitoring_dashboard():
    """Render monitoring dashboard."""
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>MarketAgent Monitoring Dashboard</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto; background: #0f1419; color: #e0e0e0; }
            .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
            header { margin-bottom: 30px; border-bottom: 2px solid #1e293b; padding-bottom: 20px; display: flex; align-items: center; justify-content: space-between; }
            h1 { font-size: 28px; margin-bottom: 10px; color: #fff; }
            .timestamp { font-size: 12px; color: #64748b; }
            .dashboard { display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; }
            .widget { background: #1e293b; border-radius: 8px; padding: 20px; border: 1px solid #334155; }
            .widget-title { font-size: 18px; font-weight: 600; margin-bottom: 15px; color: #f1f5f9; border-bottom: 1px solid #334155; padding-bottom: 10px; }
            .stat { margin: 15px 0; display: flex; justify-content: space-between; align-items: center; }
            .stat-label { color: #94a3b8; }
            .stat-value { font-size: 24px; font-weight: 700; color: #0ea5e9; }
            .status-good { color: #10b981; }
            .status-warning { color: #f59e0b; }
            .status-critical { color: #ef4444; }
            .list { max-height: 300px; overflow-y: auto; }
            .list-item { padding: 10px; background: #0f1419; margin: 5px 0; border-radius: 4px; border-left: 3px solid #ef4444; font-size: 12px; }
            .list-item .agent { font-weight: 600; }
            .list-item .error { color: #fca5a5; margin-top: 3px; }
            .refresh-btn { padding: 8px 16px; background: #0ea5e9; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: 600; }
            .refresh-btn:hover { background: #0284c7; }
            .loading { color: #94a3b8; text-align: center; padding: 20px; }
            .back-link { color: #0ea5e9; text-decoration: none; font-size: 14px; }
            .back-link:hover { text-decoration: underline; }
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <div>
                    <h1>MarketAgent Monitoring Dashboard</h1>
                    <div class="timestamp">Last updated: <span id="last-update">-</span></div>
                </div>
                <div>
                    <a href="/" class="back-link">Back to Dashboard</a>
                    <button class="refresh-btn" onclick="refreshDashboard()" style="margin-left: 10px;">Refresh</button>
                </div>
            </header>
            
            <div class="dashboard">
                <div class="widget">
                    <div class="widget-title">Feed Status Overview</div>
                    <div id="feed-status" class="loading">Loading feeds...</div>
                </div>
                
                <div class="widget">
                    <div class="widget-title">Agent Health</div>
                    <div id="agent-health" class="loading">Loading agents...</div>
                </div>
                
                <div class="widget">
                    <div class="widget-title">Recent Startup Failures</div>
                    <div id="startup-failures" class="loading">Loading failures...</div>
                </div>
            </div>
        </div>

        <script>
            async function refreshDashboard() {
                document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
                await Promise.all([loadFeedsStatus(), loadAgentsStatus(), loadStartupFailures()]);
            }

            async function loadFeedsStatus() {
                try {
                    const response = await fetch('/api/feeds/status');
                    const data = await response.json();
                    const totalFeeds = data.total_feeds || 0;
                    const healthyFeeds = Object.values(data.feeds || {})
                        .filter(f => f.status === 'healthy').length;
                    
                    document.getElementById('feed-status').innerHTML = `
                        <div class="stat">
                            <span class="stat-label">Total Feeds</span>
                            <span class="stat-value">${totalFeeds}</span>
                        </div>
                        <div class="stat">
                            <span class="stat-label">Healthy Feeds</span>
                            <span class="stat-value status-good">${healthyFeeds}</span>
                        </div>
                        <div class="stat">
                            <span class="stat-label">Issues</span>
                            <span class="stat-value ${totalFeeds - healthyFeeds > 0 ? 'status-warning' : 'status-good'}">${totalFeeds - healthyFeeds}</span>
                        </div>
                    `;
                } catch (e) {
                    document.getElementById('feed-status').innerHTML = `<div style="color: #ef4444;">Error loading feeds: ${e.message}</div>`;
                }
            }

            async function loadAgentsStatus() {
                try {
                    const response = await fetch('/api/agents/status');
                    const data = await response.json();
                    const healthClass = data.health_status === 'healthy' ? 'status-good' : 
                                      data.health_status === 'warning' ? 'status-warning' : 'status-critical';
                    
                    document.getElementById('agent-health').innerHTML = `
                        <div class="stat">
                            <span class="stat-label">Total Agents</span>
                            <span class="stat-value">${data.total_agents}</span>
                        </div>
                        <div class="stat">
                            <span class="stat-label">Running</span>
                            <span class="stat-value status-good">${data.running_count}</span>
                        </div>
                        <div class="stat">
                            <span class="stat-label">Uptime</span>
                            <span class="stat-value">${data.uptime_percent.toFixed(1)}%</span>
                        </div>
                        <div class="stat">
                            <span class="stat-label">Health Status</span>
                            <span class="stat-value ${healthClass}">${data.health_status.toUpperCase()}</span>
                        </div>
                    `;
                } catch (e) {
                    document.getElementById('agent-health').innerHTML = `<div style="color: #ef4444;">Error loading agents: ${e.message}</div>`;
                }
            }

            async function loadStartupFailures() {
                try {
                    const response = await fetch('/api/monitoring/startup-failures');
                    const data = await response.json();
                    const failures = data.failures || [];
                    
                    if (failures.length === 0) {
                        document.getElementById('startup-failures').innerHTML = '<div style="color: #10b981; padding: 20px; text-align: center;">No startup failures!</div>';
                    } else {
                        const html = failures.slice(0, 10).map(f => `
                            <div class="list-item">
                                <div class="agent">${f.agent_name}</div>
                                <div class="error">${f.error_message}</div>
                                <div style="color: #64748b; font-size: 10px;">${new Date(f.timestamp).toLocaleString()} (${f.retry_count} retries)</div>
                            </div>
                        `).join('');
                        document.getElementById('startup-failures').innerHTML = html;
                    }
                } catch (e) {
                    document.getElementById('startup-failures').innerHTML = `<div style="color: #ef4444;">Error loading failures: ${e.message}</div>`;
                }
            }

            refreshDashboard();
            setInterval(refreshDashboard, 30000);
        </script>
    </body>
    </html>
    '''
    return render_template_string(html)
