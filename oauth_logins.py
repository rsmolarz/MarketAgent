"""
Multi-Provider OAuth Authentication
Supports: Google, GitHub, Apple, Facebook, Email/Password
"""

import os
import uuid
import time
import json
import hashlib
import logging
from urllib.parse import urlencode, quote

import jwt
import requests
from flask import (
    Blueprint, request, redirect, url_for, session,
    flash, render_template, current_app, jsonify
)
from flask_login import login_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from models import User, Whitelist, db
from replit_auth import is_user_whitelisted

logger = logging.getLogger(__name__)

oauth_bp = Blueprint('oauth', __name__, url_prefix='/oauth')

APP_PREFIX = os.getenv('OAUTH_APP_PREFIX', 'MARKETAGENT')


def _env(key, default=''):
    override = os.getenv(f'OAUTH_OVERRIDE_{key}', '')
    if override:
        return override.strip()
    prefixed = os.getenv(f'{APP_PREFIX}_{key}', '')
    if prefixed:
        return prefixed.strip()
    val = os.getenv(key, default)
    return val.strip() if val else val


PROVIDERS = {
    'google': {
        'client_id_key': 'GOOGLE_OAUTH_CLIENT_ID',
        'client_secret_key': 'GOOGLE_OAUTH_CLIENT_SECRET',
        'auth_url': 'https://accounts.google.com/o/oauth2/v2/auth',
        'token_url': 'https://oauth2.googleapis.com/token',
        'userinfo_url': 'https://openidconnect.googleapis.com/v1/userinfo',
        'scopes': 'openid email profile',
    },
    'github': {
        'client_id_key': 'GITHUB_OAUTH_CLIENT_ID',
        'client_secret_key': 'GITHUB_OAUTH_CLIENT_SECRET',
        'auth_url': 'https://github.com/login/oauth/authorize',
        'token_url': 'https://github.com/login/oauth/access_token',
        'userinfo_url': 'https://api.github.com/user',
        'scopes': 'user:email read:user',
    },
    'facebook': {
        'client_id_key': 'FACEBOOK_APP_ID',
        'client_secret_key': 'FACEBOOK_APP_SECRET',
        'auth_url': 'https://www.facebook.com/v22.0/dialog/oauth',
        'token_url': 'https://graph.facebook.com/v22.0/oauth/access_token',
        'userinfo_url': 'https://graph.facebook.com/v22.0/me?fields=id,name,email,picture.type(large)',
        'scopes': 'email public_profile',
    },
    'apple': {
        'client_id_key': 'APPLE_CLIENT_ID',
        'auth_url': 'https://appleid.apple.com/auth/authorize',
        'token_url': 'https://appleid.apple.com/auth/token',
        'scopes': 'name email',
    },
}


def _get_client_id(provider):
    cfg = PROVIDERS.get(provider, {})
    key = cfg.get('client_id_key', '')
    return _env(key) or _env(key.replace('OAUTH_', ''))


def _get_client_secret(provider):
    cfg = PROVIDERS.get(provider, {})
    key = cfg.get('client_secret_key', '')
    if not key:
        return ''
    return _env(key) or _env(key.replace('OAUTH_', ''))


def _get_redirect_uri(provider):
    fb_override = os.getenv('FACEBOOK_REDIRECT_DOMAIN', '').strip()
    if provider == 'facebook' and fb_override:
        return 'https://' + fb_override.rstrip('/') + url_for('oauth.callback', provider=provider)
    base = request.host_url.rstrip('/')
    if base.startswith('http://') and request.headers.get('X-Forwarded-Proto') == 'https':
        base = 'https://' + base[7:]
    if not base.startswith('http://localhost') and base.startswith('http://'):
        base = 'https://' + base[7:]
    return base + url_for('oauth.callback', provider=provider)


def _generate_apple_client_secret():
    team_id = _env('APPLE_TEAM_ID')
    key_id = _env('APPLE_KEY_ID')
    client_id = _get_client_id('apple')
    private_key = _env('APPLE_PRIVATE_KEY')

    missing = []
    if not team_id: missing.append('APPLE_TEAM_ID')
    if not key_id: missing.append('APPLE_KEY_ID')
    if not client_id: missing.append('APPLE_CLIENT_ID')
    if not private_key: missing.append('APPLE_PRIVATE_KEY')
    if missing:
        logger.error(f"Apple Sign-In missing config: {', '.join(missing)}")
        return None

    if '\\n' in private_key:
        private_key = private_key.replace('\\n', '\n')

    if not private_key.startswith('-----'):
        private_key = f"-----BEGIN PRIVATE KEY-----\n{private_key}\n-----END PRIVATE KEY-----"

    logger.info(f"Apple client secret: team={team_id}, key={key_id}, client={client_id}, pk_len={len(private_key)}")

    now = int(time.time())
    payload = {
        'iss': team_id,
        'iat': now,
        'exp': now + 86400 * 180,
        'aud': 'https://appleid.apple.com',
        'sub': client_id,
    }
    headers = {
        'kid': key_id,
        'alg': 'ES256',
    }
    try:
        return jwt.encode(payload, private_key, algorithm='ES256', headers=headers)
    except Exception as e:
        logger.error(f"Apple client secret generation failed: {e}", exc_info=True)
        return None


def _find_or_create_user(email, first_name=None, last_name=None, profile_image=None, provider='oauth'):
    if not email:
        return None

    email_lower = email.lower().strip()

    if not is_user_whitelisted(email_lower):
        return None

    user = User.query.filter_by(email=email_lower).first()
    if user:
        if first_name and not user.first_name:
            user.first_name = first_name
        if last_name and not user.last_name:
            user.last_name = last_name
        if profile_image and not user.profile_image_url:
            user.profile_image_url = profile_image
        if not user.auth_provider:
            user.auth_provider = provider
        db.session.commit()
        return user

    user = User()
    user.id = str(uuid.uuid4())
    user.email = email_lower
    user.first_name = first_name
    user.last_name = last_name
    user.profile_image_url = profile_image
    user.auth_provider = provider

    admin_emails = os.environ.get('ADMIN_EMAILS', '')
    if admin_emails:
        admin_list = [e.strip().lower() for e in admin_emails.split(',')]
        if email_lower in admin_list:
            user.is_admin = True

    db.session.add(user)
    db.session.commit()
    return user


@oauth_bp.route('/oauth-diag')
def oauth_diag():
    if True:
        diag = {}
        for provider in PROVIDERS:
            cid = _get_client_id(provider)
            diag[provider] = {
                'client_id_set': bool(cid),
                'client_id_preview': (cid[:8] + '...' + cid[-4:]) if cid and len(cid) > 12 else ('set' if cid else 'missing'),
                'redirect_uri': _get_redirect_uri(provider),
            }
            if provider == 'apple':
                team_id = _env('APPLE_TEAM_ID')
                key_id = _env('APPLE_KEY_ID')
                pk = _env('APPLE_PRIVATE_KEY')
                diag[provider]['team_id'] = team_id or 'missing'
                diag[provider]['key_id'] = key_id or 'missing'
                diag[provider]['private_key_len'] = len(pk) if pk else 0
                diag[provider]['private_key_starts'] = pk[:30] + '...' if pk else 'missing'
                try:
                    secret = _generate_apple_client_secret()
                    diag[provider]['jwt_generated'] = bool(secret)
                    if secret:
                        parts = secret.split('.')
                        diag[provider]['jwt_parts'] = len(parts)
                        import base64
                        header_b64 = parts[0] + '=='
                        header = json.loads(base64.urlsafe_b64decode(header_b64))
                        diag[provider]['jwt_header'] = header
                        payload_b64 = parts[1] + '=='
                        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
                        diag[provider]['jwt_payload'] = {k: v for k, v in payload.items() if k != 'exp'}
                except Exception as e:
                    diag[provider]['jwt_error'] = str(e)
            if provider == 'facebook':
                cfg = PROVIDERS[provider]
                fb_params = {
                    'client_id': cid,
                    'redirect_uri': _get_redirect_uri(provider),
                    'state': 'test',
                    'response_type': 'code',
                    'scope': cfg['scopes'],
                }
                diag[provider]['auth_url_preview'] = cfg['auth_url'] + '?' + urlencode(fb_params, quote_via=quote)
        diag['request_info'] = {
            'host': request.host,
            'host_url': request.host_url,
            'x_forwarded_proto': request.headers.get('X-Forwarded-Proto', 'none'),
            'x_forwarded_host': request.headers.get('X-Forwarded-Host', 'none'),
        }
        return jsonify(diag)
    return jsonify({'error': 'access denied'})


@oauth_bp.route('/fb-debug')
def fb_debug():
    cid = _get_client_id('facebook')
    redirect_uri = _get_redirect_uri('facebook')
    cfg = PROVIDERS['facebook']
    params = {
        'client_id': cid,
        'redirect_uri': redirect_uri,
        'state': 'debug_test',
        'response_type': 'code',
        'scope': cfg['scopes'],
    }
    auth_url = cfg['auth_url'] + '?' + urlencode(params, quote_via=quote)
    html = f"""<!DOCTYPE html>
<html><head><title>Facebook OAuth Debug</title>
<style>body{{font-family:monospace;padding:20px;background:#1a1a2e;color:#e0e0e0}}
.box{{background:#16213e;padding:15px;border-radius:8px;margin:10px 0;word-break:break-all}}
.label{{color:#00d4ff;font-weight:bold}}
a{{color:#4fc3f7}}
.btn{{display:inline-block;background:#1877f2;color:white;padding:12px 24px;text-decoration:none;border-radius:6px;margin-top:15px;font-size:16px}}</style>
</head><body>
<h2>Facebook OAuth Debug</h2>
<div class="box"><span class="label">App ID:</span> {cid}</div>
<div class="box"><span class="label">Redirect URI:</span> {redirect_uri}</div>
<div class="box"><span class="label">Auth URL (v22.0):</span> {cfg['auth_url']}</div>
<div class="box"><span class="label">Scopes:</span> {cfg['scopes']}</div>
<div class="box"><span class="label">Your current domain:</span> {request.host}</div>
<h3>Required Facebook Console Settings:</h3>
<div class="box">
<p><span class="label">Settings > Basic > App Domains:</span> {request.host.split(':')[0]}</p>
<p><span class="label">Settings > Basic > Site URL:</span> https://{request.host.split(':')[0]}/</p>
<p><span class="label">Facebook Login > Settings > Valid OAuth Redirect URIs:</span> {redirect_uri}</p>
</div>
<h3>Full Authorization URL:</h3>
<div class="box" style="font-size:12px">{auth_url}</div>
<a class="btn" href="{auth_url}">Test Facebook Login</a>
</body></html>"""
    return html


@oauth_bp.route('/login')
def login_page():
    if current_user.is_authenticated and is_user_whitelisted(current_user.email):
        return redirect(url_for('dashboard.index'))

    providers_status = {}
    for p in PROVIDERS:
        providers_status[p] = bool(_get_client_id(p))

    return render_template('login.html', providers=providers_status)


@oauth_bp.route('/start/<provider>')
def start(provider):
    if provider not in PROVIDERS:
        flash('Unknown sign-in provider.', 'danger')
        return redirect(url_for('oauth.login_page'))

    client_id = _get_client_id(provider)
    if not client_id:
        flash(f'{provider.title()} sign-in is not configured.', 'warning')
        return redirect(url_for('oauth.login_page'))

    cfg = PROVIDERS[provider]
    state = os.urandom(24).hex()
    session[f'oauth_state_{provider}'] = state
    redirect_uri = _get_redirect_uri(provider)
    logger.info(f"OAuth {provider}: client_id={client_id[:15]}..., redirect_uri={redirect_uri}")

    params = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'state': state,
    }

    session[f'oauth_redirect_uri_{provider}'] = redirect_uri

    if provider == 'apple':
        params['response_type'] = 'code'
        params['scope'] = cfg['scopes']
        params['response_mode'] = 'form_post'
    else:
        params['response_type'] = 'code'
        params['scope'] = cfg['scopes']

    if provider == 'google':
        params['access_type'] = 'offline'
        params['prompt'] = 'select_account'

    auth_url = cfg['auth_url'] + '?' + urlencode(params, quote_via=quote)
    return redirect(auth_url)


@oauth_bp.route('/callback/<provider>', methods=['GET', 'POST'])
def callback(provider):
    if provider not in PROVIDERS:
        flash('Unknown provider.', 'danger')
        return redirect(url_for('oauth.login_page'))

    code = request.args.get('code') or request.form.get('code')
    state = request.args.get('state') or request.form.get('state')

    expected_state = session.pop(f'oauth_state_{provider}', None)
    if not state or state != expected_state:
        logger.warning(f"OAuth {provider} state mismatch: received={state[:20] if state else 'None'}... expected={expected_state[:20] if expected_state else 'None (session lost)'}...")
        if expected_state is None:
            flash('Authentication failed: session expired or cookies blocked. Please enable cookies and try again.', 'danger')
        else:
            flash('Authentication failed: invalid state. Please try again.', 'danger')
        return redirect(url_for('oauth.login_page'))

    if not code:
        error = request.args.get('error') or request.form.get('error', 'unknown')
        flash(f'Authentication was cancelled or failed: {error}', 'warning')
        return redirect(url_for('oauth.login_page'))

    try:
        if provider == 'google':
            user = _handle_google_callback(code)
        elif provider == 'github':
            user = _handle_github_callback(code)
        elif provider == 'facebook':
            user = _handle_facebook_callback(code)
        elif provider == 'apple':
            user = _handle_apple_callback(code)
        else:
            flash('Provider not implemented.', 'danger')
            return redirect(url_for('oauth.login_page'))

        if user is None:
            flash('Your email is not on the approved access list. Contact an administrator.', 'warning')
            return redirect(url_for('oauth.login_page'))

        from replit_auth import sync_user_role
        login_user(user)
        sync_user_role(user)
        next_url = session.pop('next_url', None)
        return redirect(next_url or url_for('dashboard.index'))

    except Exception as e:
        logger.error(f"OAuth callback error for {provider}: {e}", exc_info=True)
        flash(f'Sign-in failed: {str(e)}', 'danger')
        return redirect(url_for('oauth.login_page'))


def _handle_google_callback(code):
    cfg = PROVIDERS['google']
    redirect_uri = _get_redirect_uri('google')

    resp = requests.post(cfg['token_url'], data={
        'client_id': _get_client_id('google'),
        'client_secret': _get_client_secret('google'),
        'code': code,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code',
    }, timeout=15)
    resp.raise_for_status()
    tokens = resp.json()

    access_token = tokens.get('access_token')
    userinfo = requests.get(cfg['userinfo_url'], headers={
        'Authorization': f'Bearer {access_token}'
    }, timeout=10).json()

    email = userinfo.get('email')
    first_name = userinfo.get('given_name')
    last_name = userinfo.get('family_name')
    picture = userinfo.get('picture')

    return _find_or_create_user(email, first_name, last_name, picture, 'google')


def _handle_github_callback(code):
    cfg = PROVIDERS['github']

    resp = requests.post(cfg['token_url'], data={
        'client_id': _get_client_id('github'),
        'client_secret': _get_client_secret('github'),
        'code': code,
    }, headers={'Accept': 'application/json'}, timeout=15)
    resp.raise_for_status()
    tokens = resp.json()

    access_token = tokens.get('access_token')
    headers = {'Authorization': f'Bearer {access_token}', 'Accept': 'application/json'}

    userinfo = requests.get(cfg['userinfo_url'], headers=headers, timeout=10).json()

    email = userinfo.get('email')
    if not email:
        emails_resp = requests.get('https://api.github.com/user/emails', headers=headers, timeout=10).json()
        for e in emails_resp:
            if e.get('primary') and e.get('verified'):
                email = e['email']
                break
        if not email and emails_resp:
            email = emails_resp[0].get('email')

    name = userinfo.get('name', '')
    parts = name.split(' ', 1) if name else ['', '']
    first_name = parts[0]
    last_name = parts[1] if len(parts) > 1 else ''
    picture = userinfo.get('avatar_url')

    return _find_or_create_user(email, first_name, last_name, picture, 'github')


def _handle_facebook_callback(code):
    cfg = PROVIDERS['facebook']
    redirect_uri = _get_redirect_uri('facebook')
    client_id = _get_client_id('facebook')
    client_secret = _get_client_secret('facebook')

    logger.info(f"Facebook callback: client_id={client_id}, redirect_uri={redirect_uri}")

    resp = requests.get(cfg['token_url'], params={
        'client_id': client_id,
        'client_secret': client_secret,
        'code': code,
        'redirect_uri': redirect_uri,
    }, timeout=15)

    if resp.status_code != 200:
        logger.error(f"Facebook token exchange failed: {resp.status_code} {resp.text[:500]}")
        raise Exception(f'Facebook authentication failed (token exchange error)')

    tokens = resp.json()
    if 'error' in tokens:
        logger.error(f"Facebook token error: {tokens['error']}")
        raise Exception(f"Facebook authentication failed: {tokens['error'].get('message', 'unknown')}")

    access_token = tokens.get('access_token')
    userinfo = requests.get(cfg['userinfo_url'], params={
        'access_token': access_token,
    }, timeout=10).json()

    if 'error' in userinfo:
        logger.error(f"Facebook userinfo error: {userinfo['error']}")
        raise Exception('Failed to get user info from Facebook')

    email = userinfo.get('email')
    name = userinfo.get('name', '')
    parts = name.split(' ', 1) if name else ['', '']
    first_name = parts[0]
    last_name = parts[1] if len(parts) > 1 else ''
    picture = None
    pic_data = userinfo.get('picture', {})
    if isinstance(pic_data, dict):
        picture = pic_data.get('data', {}).get('url')

    return _find_or_create_user(email, first_name, last_name, picture, 'facebook')


def _handle_apple_callback(code):
    client_id = _get_client_id('apple')
    client_secret = _generate_apple_client_secret()
    if not client_secret:
        raise Exception('Apple Sign-In is not properly configured. Check server logs for details.')

    cfg = PROVIDERS['apple']
    stored_redirect_uri = session.pop(f'oauth_redirect_uri_apple', None)
    current_redirect_uri = _get_redirect_uri('apple')
    redirect_uri = stored_redirect_uri or current_redirect_uri

    logger.info(f"Apple callback: client_id={client_id}")
    logger.info(f"Apple callback: stored_redirect_uri={stored_redirect_uri}")
    logger.info(f"Apple callback: current_redirect_uri={current_redirect_uri}")
    logger.info(f"Apple callback: using redirect_uri={redirect_uri}")
    logger.info(f"Apple callback: client_secret_len={len(client_secret)}, code_len={len(code)}")

    resp = requests.post(cfg['token_url'], data={
        'client_id': client_id,
        'client_secret': client_secret,
        'code': code,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code',
    }, timeout=15)

    if resp.status_code != 200:
        error_body = resp.text[:500]
        logger.error(f"Apple token exchange FAILED: status={resp.status_code}")
        logger.error(f"Apple token exchange response: {error_body}")
        logger.error(f"Apple request data: client_id={client_id}, redirect_uri={redirect_uri}, code_prefix={code[:20]}...")
        try:
            err_json = resp.json()
            apple_error = err_json.get('error', 'unknown')
            apple_desc = err_json.get('error_description', '')
        except Exception:
            apple_error = f"HTTP {resp.status_code}"
            apple_desc = error_body
        raise Exception(f'Apple token exchange: {apple_error} - {apple_desc} [redirect_uri={redirect_uri}]')

    tokens = resp.json()
    if 'error' in tokens:
        logger.error(f"Apple token error: {tokens}")
        raise Exception(f"Apple token error: {tokens.get('error', 'unknown')} - {tokens.get('error_description', '')}")

    id_token = tokens.get('id_token')
    claims = jwt.decode(id_token, options={"verify_signature": False})
    email = claims.get('email')

    user_data = request.form.get('user', '{}')
    try:
        user_json = json.loads(user_data)
        name_obj = user_json.get('name', {})
        first_name = name_obj.get('firstName', '')
        last_name = name_obj.get('lastName', '')
    except (json.JSONDecodeError, AttributeError):
        first_name = ''
        last_name = ''

    return _find_or_create_user(email, first_name, last_name, None, 'apple')


@oauth_bp.route('/email/login', methods=['POST'])
def email_login():
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '').strip()

    if not email or not password:
        flash('Please enter both email and password.', 'warning')
        return redirect(url_for('oauth.login_page'))

    if not is_user_whitelisted(email):
        flash('Your email is not on the approved access list.', 'warning')
        return redirect(url_for('oauth.login_page'))

    user = User.query.filter_by(email=email).first()

    if user and user.password_hash:
        if check_password_hash(user.password_hash, password):
            from replit_auth import sync_user_role
            login_user(user)
            sync_user_role(user)
            next_url = session.pop('next_url', None)
            return redirect(next_url or url_for('dashboard.index'))
        else:
            flash('Invalid email or password.', 'danger')
            return redirect(url_for('oauth.login_page'))
    elif user and not user.password_hash:
        flash('This account uses social sign-in. Please use the appropriate provider button.', 'info')
        return redirect(url_for('oauth.login_page'))
    else:
        flash('No account found with that email.', 'danger')
        return redirect(url_for('oauth.login_page'))


@oauth_bp.route('/email/register', methods=['POST'])
def email_register():
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '').strip()
    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()

    if not email or not password:
        flash('Please enter both email and password.', 'warning')
        return redirect(url_for('oauth.login_page'))

    if len(password) < 8:
        flash('Password must be at least 8 characters.', 'warning')
        return redirect(url_for('oauth.login_page'))

    if not is_user_whitelisted(email):
        flash('Your email is not on the approved access list. Contact an administrator.', 'warning')
        return redirect(url_for('oauth.login_page'))

    existing = User.query.filter_by(email=email).first()
    if existing:
        flash('An account with this email already exists. Try signing in.', 'info')
        return redirect(url_for('oauth.login_page'))

    user = User()
    user.id = str(uuid.uuid4())
    user.email = email
    user.first_name = first_name or None
    user.last_name = last_name or None
    user.password_hash = generate_password_hash(password)
    user.auth_provider = 'email'

    admin_emails = os.environ.get('ADMIN_EMAILS', '')
    if admin_emails:
        admin_list = [e.strip().lower() for e in admin_emails.split(',')]
        if email in admin_list:
            user.is_admin = True

    db.session.add(user)
    db.session.commit()

    from replit_auth import sync_user_role
    login_user(user)
    sync_user_role(user)
    flash('Account created successfully!', 'success')
    next_url = session.pop('next_url', None)
    return redirect(next_url or url_for('dashboard.index'))


@oauth_bp.route('/facebook/deauthorize', methods=['GET', 'POST'])
def facebook_deauthorize():
    from flask import jsonify
    return jsonify({'url': request.host_url.rstrip('/') + url_for('oauth.facebook_deauthorize'), 'confirmation_code': 'ok'}), 200


@oauth_bp.route('/facebook/data-deletion', methods=['GET', 'POST'])
def facebook_data_deletion():
    from flask import jsonify
    import hashlib, hmac, base64, json as _json
    signed_request = request.form.get('signed_request', '')
    confirmation_code = hashlib.sha256(signed_request.encode()).hexdigest()[:10]
    status_url = request.host_url.rstrip('/') + url_for('oauth.facebook_deletion_status', code=confirmation_code)
    return jsonify({'url': status_url, 'confirmation_code': confirmation_code}), 200


@oauth_bp.route('/facebook/deletion-status/<code>')
def facebook_deletion_status(code):
    return render_template('base.html', content=f'Data deletion request {code} is being processed.'), 200


@oauth_bp.route('/logout')
def logout():
    from flask_login import logout_user as flask_logout
    flask_logout()
    return redirect(url_for('oauth.login_page'))


@oauth_bp.route('/status')
def status():
    result = {}
    for p in PROVIDERS:
        result[p] = bool(_get_client_id(p))
    result['email'] = True
    from flask import jsonify
    return jsonify(result)


@oauth_bp.route('/debug/redirect-uris')
def debug_redirect_uris():
    from flask import jsonify
    uris = {}
    for p in PROVIDERS:
        uris[p] = {
            'redirect_uri': _get_redirect_uri(p),
            'configured': bool(_get_client_id(p)),
            'client_id_preview': (_get_client_id(p) or '')[:15] + '...',
        }
    uris['_request_info'] = {
        'host_url': request.host_url,
        'host': request.host,
        'scheme': request.scheme,
        'x_forwarded_proto': request.headers.get('X-Forwarded-Proto', ''),
        'x_forwarded_host': request.headers.get('X-Forwarded-Host', ''),
    }
    uris['_info'] = 'Register these EXACT redirect URIs in each provider console'
    return jsonify(uris)


@oauth_bp.route('/debug/session-test')
def debug_session_test():
    """Test if sessions work correctly on this deployment."""
    from flask import jsonify
    test_val = session.get('_debug_session_test')
    if test_val:
        session.pop('_debug_session_test', None)
        return jsonify({
            'status': 'OK',
            'message': 'Session cookies are working correctly',
            'stored_value': test_val,
            'session_cookie_config': {
                'secure': current_app.config.get('SESSION_COOKIE_SECURE'),
                'samesite': current_app.config.get('SESSION_COOKIE_SAMESITE'),
                'httponly': current_app.config.get('SESSION_COOKIE_HTTPONLY'),
            }
        })
    else:
        session['_debug_session_test'] = 'test_' + os.urandom(8).hex()
        return jsonify({
            'status': 'STEP1',
            'message': 'Session value set. Refresh this page to verify it persists.',
            'hint': 'If refreshing shows status OK, sessions work. If it shows STEP1 again, session cookies are broken.',
            'session_cookie_config': {
                'secure': current_app.config.get('SESSION_COOKIE_SECURE'),
                'samesite': current_app.config.get('SESSION_COOKIE_SAMESITE'),
                'httponly': current_app.config.get('SESSION_COOKIE_HTTPONLY'),
            }
        })
