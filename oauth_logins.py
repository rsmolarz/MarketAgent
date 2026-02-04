"""
OAuth Authentication for Apple, Google, and GitHub
Integrated with Replit's built-in authentication system
Supports multiple apps via APP_PREFIX environment variable
"""

import os
from flask import Blueprint, request, jsonify, session, redirect, url_for
from functools import wraps
import requests

oauth_bp = Blueprint('oauth', __name__, url_prefix='/api/oauth')

# App prefix for multi-app support (e.g., MARKETAGENT, MEDINVEST)
# Set via environment variable, defaults to MARKETAGENT
APP_PREFIX = os.getenv('OAUTH_APP_PREFIX', 'MARKETAGENT')

def get_prefixed_env(key, default=''):
    """Get environment variable with app prefix, falling back to non-prefixed version"""
    # Try prefixed first (e.g., MARKETAGENT_GOOGLE_CLIENT_ID)
    prefixed_value = os.getenv(f'{APP_PREFIX}_{key}', '')
    if prefixed_value:
        return prefixed_value
    # Fall back to non-prefixed (e.g., GOOGLE_OAUTH_CLIENT_ID)
    return os.getenv(key, default)

# OAuth Configuration with prefix support
OAUTH_CONFIG = {
    'google': {
        'client_id': get_prefixed_env('GOOGLE_OAUTH_CLIENT_ID') or get_prefixed_env('GOOGLE_CLIENT_ID'),
        'client_secret': get_prefixed_env('GOOGLE_OAUTH_CLIENT_SECRET') or get_prefixed_env('GOOGLE_CLIENT_SECRET'),
        'auth_uri': 'https://accounts.google.com/o/oauth2/v2/auth',
        'token_uri': 'https://oauth2.googleapis.com/token',
        'scopes': ['openid', 'email', 'profile']
    },
    'github': {
        'client_id': get_prefixed_env('GITHUB_OAUTH_CLIENT_ID') or get_prefixed_env('GITHUB_CLIENT_ID'),
        'client_secret': get_prefixed_env('GITHUB_OAUTH_CLIENT_SECRET') or get_prefixed_env('GITHUB_CLIENT_SECRET'),
        'auth_uri': 'https://github.com/login/oauth/authorize',
        'token_uri': 'https://github.com/login/oauth/access_token',
        'scopes': ['user:email', 'read:user']
    },
    'apple': {
        'client_id': get_prefixed_env('APPLE_CLIENT_ID'),
        'team_id': get_prefixed_env('APPLE_TEAM_ID'),
        'key_id': get_prefixed_env('APPLE_KEY_ID'),
        'private_key': get_prefixed_env('APPLE_PRIVATE_KEY'),
        'auth_uri': 'https://appleid.apple.com/auth/authorize',
        'token_uri': 'https://appleid.apple.com/auth/token',
        'scopes': ['openid', 'email', 'name']
    }
}

class OAuth2Handler:
    """Handle OAuth2 authentication for multiple providers"""
    
    def __init__(self, provider):
        self.provider = provider
        self.config = OAUTH_CONFIG.get(provider, {})
        self.client_id = self.config.get('client_id')
        self.client_secret = self.config.get('client_secret')
    
    def get_authorization_url(self, redirect_uri, state):
        """Generate authorization URL for the provider"""
        params = {
            'client_id': self.client_id,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': ' '.join(self.config.get('scopes', [])),
            'state': state
        }
        auth_uri = self.config.get('auth_uri', '')
        return f"{auth_uri}?{'&'.join(f'{k}={v}' for k, v in params.items())}"
    
    def exchange_code_for_token(self, code, redirect_uri):
        """Exchange authorization code for access token"""
        token_uri = self.config.get('token_uri', '')
        payload = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'code': code,
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code'
        }
        
        try:
            response = requests.post(token_uri, data=payload, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            return {'error': str(e)}
    
    def get_user_info(self, access_token):
        """Fetch user information using access token"""
        if self.provider == 'google':
            user_info_uri = 'https://openidconnect.googleapis.com/v1/userinfo'
        elif self.provider == 'github':
            user_info_uri = 'https://api.github.com/user'
        elif self.provider == 'apple':
            # Apple doesn't provide user info endpoint in same way
            return self.decode_apple_jwt(access_token)
        else:
            return {'error': 'Unknown provider'}
        
        headers = {'Authorization': f'Bearer {access_token}'}
        try:
            response = requests.get(user_info_uri, headers=headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            return {'error': str(e)}

# Route: Initiate OAuth login
@oauth_bp.route('/<provider>/login', methods=['GET'])
def oauth_login(provider):
    """Initiate OAuth login flow"""
    
    if provider not in OAUTH_CONFIG:
        return jsonify({'error': 'Invalid provider'}), 400
    
    if not OAUTH_CONFIG[provider].get('client_id'):
        return jsonify({
            'error': f'{provider.upper()} is not configured',
            'status': 'NOT_CONFIGURED'
        }), 503
    
    handler = OAuth2Handler(provider)
    redirect_uri = request.host_url.rstrip('/') + url_for('oauth.oauth_callback', provider=provider)
    state = os.urandom(24).hex()
    session[f'{provider}_state'] = state
    
    auth_url = handler.get_authorization_url(redirect_uri, state)
    return jsonify({'auth_url': auth_url}), 200

# Route: OAuth callback
@oauth_bp.route('/<provider>/callback', methods=['GET'])
def oauth_callback(provider):
    """Handle OAuth callback from provider"""
    
    if provider not in OAUTH_CONFIG:
        return jsonify({'error': 'Invalid provider'}), 400
    
    code = request.args.get('code')
    state = request.args.get('state')
    
    # Verify state
    if state != session.get(f'{provider}_state'):
        return jsonify({'error': 'State mismatch'}), 401
    
    handler = OAuth2Handler(provider)
    redirect_uri = request.host_url.rstrip('/') + url_for('oauth.oauth_callback', provider=provider)
    
    # Exchange code for token
    token_response = handler.exchange_code_for_token(code, redirect_uri)
    if 'error' in token_response:
        return jsonify(token_response), 400
    
    access_token = token_response.get('access_token')
    
    # Get user info
    user_info = handler.get_user_info(access_token)
    if 'error' in user_info:
        return jsonify(user_info), 400
    
    # Store user in session
    session['user'] = {
        'provider': provider,
        'email': user_info.get('email'),
        'name': user_info.get('name'),
        'id': user_info.get('id', user_info.get('sub')),
        'access_token': access_token
    }
    
    return jsonify({
        'status': 'success',
        'user': session['user']
    }), 200

# Route: Check OAuth status
@oauth_bp.route('/status', methods=['GET'])
def oauth_status():
    """Check OAuth configuration status"""
    
    status = {
        'app_prefix': APP_PREFIX,
        'providers': {}
    }
    for provider in OAUTH_CONFIG:
        config = OAUTH_CONFIG[provider]
        is_configured = bool(config.get('client_id'))
        status['providers'][provider] = {
            'configured': is_configured,
            'client_id': '***' if is_configured else None,
            'has_secret': bool(config.get('client_secret')) or bool(config.get('private_key'))
        }
    
    return jsonify(status), 200

# Route: Get current user
@oauth_bp.route('/user', methods=['GET'])
def get_current_user():
    """Get current authenticated user"""
    
    user = session.get('user')
    if not user:
        return jsonify({'error': 'Not authenticated'}), 401
    
    return jsonify(user), 200

# Route: Logout
@oauth_bp.route('/logout', methods=['POST'])
def logout():
    """Logout current user"""
    
    session.clear()
    return jsonify({'status': 'success'}), 200

# Decorator: Require authentication
def require_oauth(f):
    """Decorator to require OAuth authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = session.get('user')
        if not user:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function

