from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import current_user
from app import db
from models import Whitelist, User

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
