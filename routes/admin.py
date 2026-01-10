from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import current_user
from models import Whitelist, User, db

admin_bp = Blueprint('admin', __name__)


def is_admin():
    """Check if current user is an admin"""
    if not current_user.is_authenticated:
        return False
    return current_user.is_admin


@admin_bp.before_request
def require_admin():
    """Protect all admin routes - always enforce auth/admin status"""
    if not current_user.is_authenticated:
        return redirect(url_for('replit_auth.login'))
    if not is_admin():
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('dashboard.index'))


@admin_bp.route('/')
def index():
    """Admin dashboard"""
    whitelist = Whitelist.query.order_by(Whitelist.added_at.desc()).all()
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/index.html', whitelist=whitelist, users=users)


@admin_bp.route('/whitelist/add', methods=['POST'])
def add_to_whitelist():
    """Add email to whitelist"""
    email = request.form.get('email', '').strip().lower()
    notes = request.form.get('notes', '').strip()
    
    if not email:
        flash('Email is required.', 'danger')
        return redirect(url_for('admin.index'))
    
    existing = Whitelist.query.filter_by(email=email).first()
    if existing:
        flash(f'{email} is already on the whitelist.', 'warning')
        return redirect(url_for('admin.index'))
    
    entry = Whitelist(
        email=email,
        added_by=current_user.email,
        notes=notes
    )
    db.session.add(entry)
    db.session.commit()
    
    flash(f'{email} has been added to the whitelist.', 'success')
    return redirect(url_for('admin.index'))


@admin_bp.route('/whitelist/remove/<int:entry_id>', methods=['POST'])
def remove_from_whitelist(entry_id):
    """Remove email from whitelist"""
    entry = Whitelist.query.get_or_404(entry_id)
    email = entry.email
    db.session.delete(entry)
    db.session.commit()
    
    flash(f'{email} has been removed from the whitelist.', 'success')
    return redirect(url_for('admin.index'))


@admin_bp.route('/users/toggle-admin/<user_id>', methods=['POST'])
def toggle_admin(user_id):
    """Toggle admin status for a user"""
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        flash('You cannot change your own admin status.', 'danger')
        return redirect(url_for('admin.index'))
    
    user.is_admin = not user.is_admin
    db.session.commit()
    
    status = 'granted admin access' if user.is_admin else 'removed from admin'
    flash(f'{user.email} has been {status}.', 'success')
    return redirect(url_for('admin.index'))


@admin_bp.route('/send-test-email', methods=['POST'])
def send_test_email():
    """Send a test daily summary email"""
    try:
        from services.daily_email_service import DailyEmailService
        service = DailyEmailService()
        
        if not service.notifier.is_configured():
            flash('SendGrid is not configured. Please add SENDGRID_API_KEY.', 'danger')
            return redirect(url_for('admin.index'))
        
        success = service.send_test_email(current_user.email)
        
        if success:
            flash(f'Test email sent to {current_user.email}', 'success')
        else:
            flash('Failed to send test email. Check logs for details.', 'danger')
            
    except Exception as e:
        flash(f'Error sending test email: {str(e)}', 'danger')
    
    return redirect(url_for('admin.index'))


@admin_bp.route('/send-daily-summary', methods=['POST'])
def send_daily_summary():
    """Send daily summary to all whitelisted users"""
    try:
        from services.daily_email_service import DailyEmailService
        service = DailyEmailService()
        
        if not service.notifier.is_configured():
            flash('SendGrid is not configured. Please add SENDGRID_API_KEY.', 'danger')
            return redirect(url_for('admin.index'))
        
        success = service.send_daily_summary()
        
        if success:
            emails = service.get_recipient_emails()
            flash(f'Daily summary sent to {len(emails)} recipients', 'success')
        else:
            flash('Failed to send daily summary. Check logs for details.', 'danger')
            
    except Exception as e:
        flash(f'Error sending daily summary: {str(e)}', 'danger')
    
    return redirect(url_for('admin.index'))


@admin_bp.route('/meta')
def meta_dashboard():
    """Meta supervisor dashboard showing agent performance and allocation"""
    import json
    from pathlib import Path
    p = Path("meta_supervisor/reports/meta_report.json")
    report = json.loads(p.read_text()) if p.exists() else {}
    return render_template('meta_dashboard.html', report=report)


@admin_bp.route('/agents')
def agents_oversight():
    """AI Oversight - View all agents, their status, and performance metrics"""
    from models import AgentStatus
    import json
    from pathlib import Path
    
    agents = AgentStatus.query.order_by(AgentStatus.agent_name).all()
    
    # Load telemetry data if available
    telemetry = {}
    tel_path = Path("telemetry/agent_runs.json")
    if tel_path.exists():
        try:
            telemetry = json.loads(tel_path.read_text())
        except:
            pass
    
    # Load quarantine data
    quarantine = {}
    q_path = Path("meta/quarantine_state.json")
    if q_path.exists():
        try:
            quarantine = json.loads(q_path.read_text())
        except:
            pass
    
    return render_template('admin/agents_oversight.html', 
                          agents=agents, telemetry=telemetry, quarantine=quarantine)


@admin_bp.route('/approvals')
def approvals():
    """Approvals - View pending and historical approval events"""
    from models import ApprovalEvent
    
    pending = ApprovalEvent.query.filter_by(status='pending').order_by(ApprovalEvent.created_at.desc()).all()
    approved = ApprovalEvent.query.filter_by(status='approved').order_by(ApprovalEvent.created_at.desc()).limit(20).all()
    rejected = ApprovalEvent.query.filter_by(status='rejected').order_by(ApprovalEvent.created_at.desc()).limit(20).all()
    
    return render_template('admin/approvals.html', 
                          pending=pending, approved=approved, rejected=rejected)
