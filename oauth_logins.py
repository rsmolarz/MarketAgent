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
        'client_id_fallback': 'MARKETAGENT_APPLE_CLIENT_ID',
        'auth_url': 'https://appleid.apple.com/auth/authorize',
        'token_url': 'https://appleid.apple.com/auth/token',
        'scopes': 'name email',
    },
}


def _get_client_id(provider):
    cfg = PROVIDERS.get(provider, {})
    key = cfg.get('client_id_key', '')
    fallback = cfg.get('client_id_fallback', '')
    val = _env(key) or _env(key.replace('OAUTH_', ''))
    if not val and fallback:
        val = _env(fallback) or _env(fallback.replace('OAUTH_', ''))
    return val


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
    apple_override = os.getenv('APPLE_REDIRECT_DOMAIN', '').strip()
    if provider == 'apple' and apple_override:
        return 'https://' + apple_override.rstrip('/') + url_for('oauth.callback', provider=provider)
    base = request.host_url.rstrip('/')
    if base.startswith('http://') and request.headers.get('X-Forwarded-Proto') == 'https':
        base = 'https://' + base[7:]
    if not base.startswith('http://localhost') and base.startswith('http://'):
        base = 'https://' + base[7:]
    return base + url_for('oauth.callback', provider=provider)


def _get_apple_credentials():
    cid_apple = os.environ.get('APPLE_CLIENT_ID', '').strip()
    cid_market = os.environ.get('MARKETAGENT_APPLE_CLIENT_ID', '').strip()
    client_id = cid_apple or cid_market
    if cid_apple and cid_market and cid_apple != cid_market:
        logger.warning(f"Apple client_id mismatch: APPLE_CLIENT_ID={cid_apple} vs MARKETAGENT_APPLE_CLIENT_ID={cid_market}. Using APPLE_CLIENT_ID={cid_apple}")
    team_id = (os.environ.get('APPLE_TEAM_ID', '') or os.environ.get('MARKETAGENT_APPLE_TEAM_ID', '')).strip()
    key_id = (os.environ.get('APPLE_KEY_ID', '') or os.environ.get('MARKETAGENT_APPLE_KEY_ID', '')).strip()
    private_key = (os.environ.get('APPLE_PRIVATE_KEY', '') or os.environ.get('MARKETAGENT_APPLE_PRIVATE_KEY', '')).strip()
    if private_key:
        private_key = private_key.replace('\\n', '\n')
    logger.info(f"Apple credentials resolved: client_id={client_id}, team_id={team_id}, key_id={key_id}, pk_len={len(private_key)}")
    return client_id, team_id, key_id, private_key


def _generate_apple_client_secret():
    client_id, team_id, key_id, private_key = _get_apple_credentials()

    missing = []
    if not team_id: missing.append('APPLE_TEAM_ID')
    if not key_id: missing.append('APPLE_KEY_ID')
    if not client_id: missing.append('APPLE_CLIENT_ID')
    if not private_key: missing.append('APPLE_PRIVATE_KEY')
    if missing:
        logger.error(f"Apple Sign-In missing config: {', '.join(missing)}")
        return None

    pk = private_key.strip()
    if '\\n' in pk:
        pk = pk.replace('\\n', '\n')

    if not pk.startswith('-----BEGIN'):
        key_data = pk.replace(' ', '').replace('\n', '')
        key_lines = [key_data[i:i+64] for i in range(0, len(key_data), 64)]
        pk = '-----BEGIN PRIVATE KEY-----\n' + '\n'.join(key_lines) + '\n-----END PRIVATE KEY-----'

    logger.info(f"Apple client secret: team={team_id[:4]}..., key={key_id[:4]}..., client={client_id}, pk_len={len(pk)}")

    headers = {
        'kid': key_id,
        'alg': 'ES256',
    }
    payload = {
        'iss': team_id,
        'iat': int(time.time()),
        'exp': int(time.time()) + 600,
        'aud': 'https://appleid.apple.com',
        'sub': client_id,
    }
    try:
        return jwt.encode(payload, pk, algorithm='ES256', headers=headers)
    except Exception as e:
        logger.error(f"Apple client secret generation failed: {e}", exc_info=True)
        return None


def _create_signed_apple_state(redirect_uri):
    import hashlib
    import hmac
    import base64
    secret = os.environ.get('SESSION_SECRET', 'fallback')
    nonce = os.urandom(16).hex()
    timestamp = int(time.time())
    data = json.dumps({'p': 'apple', 'r': redirect_uri, 't': timestamp, 'n': nonce})
    payload_b64 = base64.urlsafe_b64encode(data.encode()).decode()
    sig = hmac.new(secret.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{payload_b64}.{sig}"


def _verify_signed_apple_state(state, max_age=600):
    import hashlib
    import hmac
    import base64
    try:
        if not state or '.' not in state:
            return None
        payload_b64, sig = state.rsplit('.', 1)
        secret = os.environ.get('SESSION_SECRET', 'fallback')
        expected_sig = hmac.new(secret.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()[:16]
        if not hmac.compare_digest(sig, expected_sig):
            logger.warning("Apple OAuth: signed state signature mismatch")
            return None
        padding = len(payload_b64) % 4
        if padding:
            payload_b64 += '=' * (4 - padding)
        data = json.loads(base64.urlsafe_b64decode(payload_b64).decode())
        if int(time.time()) - data.get('t', 0) > max_age:
            logger.warning("Apple OAuth: signed state expired")
            return None
        return data
    except Exception as e:
        logger.error(f"Apple state verification failed: {e}")
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
                a_cid, a_tid, a_kid, a_pk = _get_apple_credentials()
                diag[provider]['client_id_direct'] = a_cid or 'missing'
                diag[provider]['team_id'] = (a_tid[:4] + '...') if a_tid else 'missing'
                diag[provider]['key_id'] = (a_kid[:4] + '...') if a_kid else 'missing'
                diag[provider]['private_key_len'] = len(a_pk) if a_pk else 0
                diag[provider]['env_prefix_client_id'] = _env('APPLE_CLIENT_ID') or 'missing'
                diag[provider]['direct_client_id'] = a_cid or 'missing'
                diag[provider]['client_ids_match'] = (a_cid == _env('APPLE_CLIENT_ID')) if a_cid else False
                try:
                    secret = _generate_apple_client_secret()
                    diag[provider]['jwt_generated'] = bool(secret)
                    if secret:
                        import base64
                        parts = secret.split('.')
                        header_b64 = parts[0] + '=='
                        header = json.loads(base64.urlsafe_b64decode(header_b64))
                        diag[provider]['jwt_header'] = header
                        payload_b64 = parts[1] + '=='
                        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
                        diag[provider]['jwt_payload'] = {k: v for k, v in payload.items() if k != 'exp'}
                        diag[provider]['jwt_exp_seconds'] = payload.get('exp', 0) - payload.get('iat', 0)
                        import requests as req
                        test_resp = req.post('https://appleid.apple.com/auth/token', data={
                            'client_id': a_cid,
                            'client_secret': secret,
                            'code': 'diag_test',
                            'redirect_uri': _get_redirect_uri(provider),
                            'grant_type': 'authorization_code',
                        }, timeout=10)
                        diag[provider]['token_test_status'] = test_resp.status_code
                        diag[provider]['token_test_response'] = test_resp.json()
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

    apple_direct_url = None
    apple_client_id, _, _, _ = _get_apple_credentials()
    if apple_client_id:
        providers_status['apple'] = True
        redirect_uri = _get_redirect_uri('apple')
        logger.info(f"Apple redirect_uri being sent: {redirect_uri}")
        logger.info(f"Apple client_id being used: {apple_client_id}")
        state = _create_signed_apple_state(redirect_uri)
        apple_params = {
            'client_id': apple_client_id,
            'redirect_uri': redirect_uri,
            'state': state,
            'response_type': 'code',
            'scope': 'name email',
            'response_mode': 'form_post',
        }
        apple_direct_url = 'https://appleid.apple.com/auth/authorize?' + urlencode(apple_params, quote_via=quote)

    return render_template('login.html', providers=providers_status, apple_direct_url=apple_direct_url)


@oauth_bp.route('/start/<provider>')
def start(provider):
    if provider not in PROVIDERS:
        flash('Unknown sign-in provider.', 'danger')
        return redirect(url_for('oauth.login_page'))

    if provider == 'apple':
        client_id, _, _, _ = _get_apple_credentials()
    else:
        client_id = _get_client_id(provider)
    if not client_id:
        flash(f'{provider.title()} sign-in is not configured.', 'warning')
        return redirect(url_for('oauth.login_page'))

    cfg = PROVIDERS[provider]
    state = os.urandom(24).hex()
    session[f'oauth_state_{provider}'] = state
    redirect_uri = _get_redirect_uri(provider)
    logger.info(f"OAuth {provider}: client_id={client_id}, redirect_uri={redirect_uri}")

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

    if provider == 'apple':
        return f'''<!DOCTYPE html>
<html><head>
<meta http-equiv="refresh" content="0;url={auth_url}">
<title>Redirecting to Apple Sign-In...</title>
</head><body style="background:#111;color:#fff;display:flex;align-items:center;justify-content:center;height:100vh;font-family:system-ui">
<div style="text-align:center">
<p>Redirecting to Apple Sign-In...</p>
<p style="margin-top:1rem"><a href="{auth_url}" style="color:#0a84ff">Click here if not redirected</a></p>
</div>
<script>window.location.href="{auth_url}";</script>
</body></html>'''

    return redirect(auth_url)


@oauth_bp.route('/callback/<provider>', methods=['GET', 'POST'])
def callback(provider):
    if provider not in PROVIDERS:
        flash('Unknown provider.', 'danger')
        return redirect(url_for('oauth.login_page'))

    code = request.args.get('code') or request.form.get('code')
    state = request.args.get('state') or request.form.get('state')

    if provider == 'apple':
        state_data = _verify_signed_apple_state(state)
        if not state_data:
            logger.warning(f"Apple OAuth: signed state verification failed, proceeding with fallback")
        redirect_uri_from_state = state_data.get('r') if state_data else None
    else:
        expected_state = session.pop(f'oauth_state_{provider}', None)
        if not state or state != expected_state:
            logger.warning(f"OAuth {provider} state mismatch: received={state[:20] if state else 'None'}... expected={expected_state[:20] if expected_state else 'None (session lost)'}...")
            if expected_state is None:
                flash('Authentication failed: session expired or cookies blocked. Please enable cookies and try again.', 'danger')
            else:
                flash('Authentication failed: invalid state. Please try again.', 'danger')
            return redirect(url_for('oauth.login_page'))
        redirect_uri_from_state = None

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
            user = _handle_apple_callback(code, redirect_uri_from_state)
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
    client_id = _get_client_id('google')
    client_secret = _get_client_secret('google')

    logger.info(f"Google token exchange: client_id={client_id[:20]}... redirect_uri={redirect_uri}")
    logger.info(f"Google client_secret present: {bool(client_secret)}, length={len(client_secret) if client_secret else 0}")

    resp = requests.post(cfg['token_url'], data={
        'client_id': client_id,
        'client_secret': client_secret,
        'code': code,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code',
    }, timeout=15)

    if resp.status_code != 200:
        logger.error(f"Google token exchange failed: {resp.status_code} {resp.text[:500]}")
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


def _handle_apple_callback(code, redirect_uri_from_state=None):
    apple_client_id, apple_team_id, apple_key_id, apple_pk = _get_apple_credentials()
    client_secret = _generate_apple_client_secret()
    if not client_secret:
        raise Exception('Apple Sign-In is not properly configured. Check server logs for details.')

    redirect_uri = redirect_uri_from_state or _get_redirect_uri('apple')

    import base64 as b64mod
    import hashlib
    jwt_payload = {}
    try:
        jwt_parts = client_secret.split('.')
        jwt_header = json.loads(b64mod.urlsafe_b64decode(jwt_parts[0] + '=='))
        jwt_payload = json.loads(b64mod.urlsafe_b64decode(jwt_parts[1] + '=='))
        logger.info(f"APPLE CALLBACK JWT header: {jwt_header}")
        logger.info(f"APPLE CALLBACK JWT payload: sub={jwt_payload.get('sub')}, iss={jwt_payload.get('iss')}, aud={jwt_payload.get('aud')}, iat={jwt_payload.get('iat')}, exp={jwt_payload.get('exp')}")
        logger.info(f"APPLE CALLBACK JWT length: {len(client_secret)}, parts: {len(jwt_parts[0])}/{len(jwt_parts[1])}/{len(jwt_parts[2])}")
    except Exception as je:
        logger.error(f"APPLE CALLBACK JWT decode error: {je}")

    pk_hash = hashlib.sha256(apple_pk.encode()).hexdigest()[:16] if apple_pk else 'none'
    logger.info(f"APPLE CALLBACK: client_id={apple_client_id}, redirect_uri={redirect_uri}, redirect_uri_from_state={redirect_uri_from_state}, code_len={len(code) if code else 0}, pk_hash={pk_hash}")

    try:
        from cryptography.hazmat.primitives.serialization import load_pem_private_key
        pk_bytes = apple_pk.encode() if apple_pk else b''
        if pk_bytes:
            priv_key = load_pem_private_key(pk_bytes, password=None)
            pub_key = priv_key.public_key()
            verified_payload = jwt.decode(client_secret, pub_key, algorithms=['ES256'], audience='https://appleid.apple.com')
            logger.info(f"APPLE CALLBACK: JWT self-verification PASSED, sub={verified_payload.get('sub')}")
    except Exception as verify_err:
        logger.error(f"APPLE CALLBACK: JWT self-verification FAILED: {verify_err}")

    diag_resp = requests.post('https://appleid.apple.com/auth/token', data={
        'client_id': apple_client_id,
        'client_secret': client_secret,
        'code': 'diag_test_from_callback',
        'grant_type': 'authorization_code',
        'redirect_uri': redirect_uri,
    }, timeout=10)
    logger.info(f"APPLE CALLBACK DIAG TEST: status={diag_resp.status_code} body={diag_resp.text[:300]}")

    from urllib.parse import urlencode as ue
    token_body = ue({
        'client_id': apple_client_id,
        'client_secret': client_secret,
        'code': code,
        'grant_type': 'authorization_code',
        'redirect_uri': redirect_uri,
    })
    logger.info(f"APPLE CALLBACK: encoded body length={len(token_body)}, client_id_in_body={'client_id=' + apple_client_id in token_body}")

    token_response = requests.post(
        'https://appleid.apple.com/auth/token',
        data=token_body,
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        timeout=15
    )

    if not token_response.ok:
        logger.error(f"Apple token exchange FAILED: status={token_response.status_code} body={token_response.text[:500]}")
        logger.error(f"Apple token request: client_id={apple_client_id}, team_id={apple_team_id}, key_id={apple_key_id}, redirect_uri={redirect_uri}, code_len={len(code) if code else 0}")
        logger.error(f"Apple JWT claims: sub={jwt_payload.get('sub')}, iss={jwt_payload.get('iss')}, exp_in={jwt_payload.get('exp', 0) - jwt_payload.get('iat', 0)}s")
        logger.error(f"Apple response headers: {dict(token_response.headers)}")
        try:
            err_json = token_response.json()
            apple_error = err_json.get('error', 'unknown')
            apple_desc = err_json.get('error_description', '')
        except Exception:
            apple_error = f"HTTP {token_response.status_code}"
            apple_desc = token_response.text[:200]
        raise Exception(f'Apple token exchange: {apple_error} - {apple_desc} [redirect_uri={redirect_uri}]')

    tokens = token_response.json()
    id_token = tokens.get('id_token')
    if not id_token:
        raise Exception('No ID token received from Apple.')

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
