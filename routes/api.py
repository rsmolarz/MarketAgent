from flask import Blueprint, request, jsonify, current_app
from flask_login import current_user
from models import Finding, AgentStatus, MarketData, db
from datetime import datetime, timedelta
import logging
from functools import wraps
import yfinance as yf

logger = logging.getLogger(__name__)
api_bp = Blueprint('api', __name__)

SEVERITY_COLOR = {
    "low": "#22c55e",
    "medium": "#eab308",
    "high": "#f97316",
    "critical": "#ef4444",
}


def api_login_required(f):
    """Decorator to require login for API endpoints"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function

@api_bp.route('/health')
def api_health():
    """Lightweight JSON health check endpoint for deployment systems"""
    return jsonify({
        'status': 'healthy', 
        'timestamp': datetime.utcnow().isoformat(),
        'service': 'Market Inefficiency Detection Platform API'
    }), 200

@api_bp.route('/healthz')  
def api_healthz():
    """Alternative health check endpoint"""
    return jsonify({'status': 'ok'}), 200

@api_bp.route('/findings', methods=['GET', 'POST'])
@api_login_required
def findings():
    """Get or create findings"""
    if request.method == 'GET':
        try:
            # Query parameters
            agent_name = request.args.get('agent_name')
            symbol = request.args.get('symbol')
            severity = request.args.get('severity')
            market_type = request.args.get('market_type')
            hours = request.args.get('hours', 24, type=int)
            limit = request.args.get('limit', 100, type=int)
            
            # Build query
            query = Finding.query
            
            if agent_name:
                query = query.filter_by(agent_name=agent_name)
            
            if symbol:
                query = query.filter_by(symbol=symbol)
            
            if severity:
                query = query.filter_by(severity=severity)
            
            if market_type:
                query = query.filter_by(market_type=market_type)
            
            # Filter by time
            if hours:
                start_time = datetime.utcnow() - timedelta(hours=hours)
                query = query.filter(Finding.timestamp >= start_time)
            
            findings = query.order_by(
                Finding.timestamp.desc()
            ).limit(limit).all()
            
            return jsonify([finding.to_dict() for finding in findings])
            
        except Exception as e:
            logger.error(f"Error getting findings: {e}")
            return jsonify({'error': str(e)}), 500
    
    elif request.method == 'POST':
        try:
            data = request.get_json()
            
            finding = Finding()
            finding.agent_name = data.get('agent_name')
            finding.title = data.get('title')
            finding.description = data.get('description')
            finding.severity = data.get('severity', 'medium')
            finding.confidence = data.get('confidence', 0.5)
            finding.finding_metadata = data.get('metadata', {})
            finding.symbol = data.get('symbol')
            finding.market_type = data.get('market_type')
            
            db.session.add(finding)
            db.session.commit()
            
            return jsonify(finding.to_dict()), 201
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating finding: {e}")
            return jsonify({'error': str(e)}), 500
    
    # Default return for unexpected method
    return jsonify({'error': 'Method not allowed'}), 405

@api_bp.route('/agents', methods=['GET'])
@api_login_required
def get_agents():
    """Get all agent statuses"""
    try:
        statuses = AgentStatus.query.all()
        return jsonify([status.to_dict() for status in statuses])
        
    except Exception as e:
        logger.error(f"Error getting agents: {e}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/agents/<agent_name>/start', methods=['POST'])
@api_login_required
def start_agent(agent_name):
    """Start an agent"""
    try:
        scheduler = current_app.extensions.get('scheduler')
        if not scheduler:
            return jsonify({'error': 'Scheduler not available'}), 503
        success = scheduler.start_agent(agent_name)
        if success:
            return jsonify({'message': f'Agent {agent_name} started'})
        else:
            return jsonify({'error': f'Failed to start agent {agent_name}'}), 400
            
    except Exception as e:
        logger.error(f"Error starting agent {agent_name}: {e}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/agents/<agent_name>/stop', methods=['POST'])
@api_login_required
def stop_agent(agent_name):
    """Stop an agent"""
    try:
        scheduler = current_app.extensions.get('scheduler')
        if not scheduler:
            return jsonify({'error': 'Scheduler not available'}), 503
        success = scheduler.stop_agent(agent_name)
        if success:
            return jsonify({'message': f'Agent {agent_name} stopped'})
        else:
            return jsonify({'error': f'Failed to stop agent {agent_name}'}), 400
            
    except Exception as e:
        logger.error(f"Error stopping agent {agent_name}: {e}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/agents/<agent_name>/force-start', methods=['POST'])
@api_login_required
def force_start_agent(agent_name):
    """Force-start an agent, bypassing regime/drawdown restrictions"""
    try:
        scheduler = current_app.extensions.get('scheduler')
        if not scheduler:
            return jsonify({'error': 'Scheduler not available'}), 503
        success = scheduler.start_agent(agent_name, force=True)
        if success:
            return jsonify({'message': f'Agent {agent_name} force-started (bypassing restrictions)'})
        else:
            return jsonify({'error': f'Failed to force-start agent {agent_name}'}), 400
            
    except Exception as e:
        logger.error(f"Error force-starting agent {agent_name}: {e}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/agents/force-start-all', methods=['POST'])
@api_login_required
def force_start_all_agents():
    """Force-start all inactive agents, bypassing regime/drawdown restrictions"""
    try:
        scheduler = current_app.extensions.get('scheduler')
        if not scheduler:
            return jsonify({'error': 'Scheduler not available'}), 503
        
        statuses = AgentStatus.query.filter_by(is_active=False).all()
        started = []
        failed = []
        
        for status in statuses:
            try:
                success = scheduler.start_agent(status.agent_name, force=True)
                if success:
                    started.append(status.agent_name)
                else:
                    failed.append(status.agent_name)
            except Exception as e:
                logger.error(f"Error force-starting {status.agent_name}: {e}")
                failed.append(status.agent_name)
        
        return jsonify({
            'message': f'Force-started {len(started)} agents',
            'started': started,
            'failed': failed
        })
            
    except Exception as e:
        logger.error(f"Error force-starting all agents: {e}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/governance/reset-drawdown', methods=['POST'])
@api_login_required
def reset_drawdown():
    """Reset drawdown state by archiving telemetry events"""
    try:
        from services.drawdown_governor import reset_drawdown_state
        result = reset_drawdown_state()
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error resetting drawdown: {e}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/agents/<agent_name>/interval', methods=['PUT'])
@api_login_required
def update_agent_interval(agent_name):
    """Update agent scheduling interval"""
    try:
        data = request.get_json()
        interval = data.get('interval')
        
        if not interval or interval < 1:
            return jsonify({'error': 'Invalid interval'}), 400
        
        scheduler = current_app.extensions.get('scheduler')
        if not scheduler:
            return jsonify({'error': 'Scheduler not available'}), 503
        success = scheduler.update_agent_interval(agent_name, interval)
        if success:
            return jsonify({'message': f'Agent {agent_name} interval updated to {interval} minutes'})
        else:
            return jsonify({'error': f'Failed to update agent {agent_name}'}), 400
            
    except Exception as e:
        logger.error(f"Error updating agent interval: {e}")
        return jsonify({'error': str(e)}), 500

# Removed duplicate endpoints - these are now in dashboard.py only

@api_bp.route('/market_data', methods=['POST'])
@api_login_required
def store_market_data():
    """Store market data (POST endpoint)"""
    try:
        data = request.get_json()
        
        market_data = MarketData()
        market_data.symbol = data.get('symbol')
        market_data.price = data.get('price')
        market_data.volume = data.get('volume')
        market_data.market_cap = data.get('market_cap')
        market_data.data_source = data.get('data_source')
        market_data.raw_data = data.get('raw_data', {})
        
        db.session.add(market_data)
        db.session.commit()
        
        return jsonify(market_data.to_dict()), 201
        
    except Exception as e:
        logger.error(f"Error storing market data: {e}")
        return jsonify({'error': str(e)}), 500



@api_bp.route('/agents/<agent_name>/run', methods=['POST'])
@api_login_required
def run_agent_now(agent_name):
    """Manually run an agent immediately"""
    try:
        scheduler = current_app.extensions.get('scheduler')
        if not scheduler:
            return jsonify({'error': 'Scheduler not available'}), 503
        
        # Run the agent immediately
        success = scheduler.run_agent_immediately(agent_name)
        if success:
            return jsonify({'message': f'Agent {agent_name} executed successfully'})
        else:
            return jsonify({'error': f'Failed to run agent {agent_name}'}), 400
            
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500


@api_bp.route('/series/spy')
def spy_series():
    """
    Returns SPY daily closes for charting.
    Query params:
      - period: default '6mo' (e.g., '1y', '2y', 'max')
    """
    period = request.args.get("period", "6mo")

    try:
        df = yf.download("SPY", period=period, interval="1d", progress=False)
        if df is None or df.empty:
            return jsonify({"symbol": "SPY", "points": []})

        df = df.reset_index()
        points = []
        for idx in range(len(df)):
            row = df.iloc[idx]
            d = row["Date"]
            if hasattr(d, "to_pydatetime"):
                d = d.to_pydatetime()
            elif hasattr(d, 'iloc'):
                d = d.iloc[0].to_pydatetime() if hasattr(d.iloc[0], 'to_pydatetime') else d.iloc[0]
            
            close_val = row["Close"]
            if hasattr(close_val, 'iloc'):
                close_val = close_val.iloc[0]
            if hasattr(close_val, 'item'):
                close_val = close_val.item()
            
            date_str = d.strftime("%Y-%m-%d") if hasattr(d, 'strftime') else str(d)[:10]
            points.append({
                "t": date_str,
                "close": float(close_val),
            })

        return jsonify({"symbol": "SPY", "points": points})
    except Exception as e:
        logger.error(f"Error fetching SPY series: {e}")
        return jsonify({"symbol": "SPY", "points": [], "error": str(e)})


@api_bp.route('/signals')
def signals():
    """
    Returns recent Finding rows for a symbol for chart markers.
    Query params:
      - symbol: default 'SPY'
      - limit: default 200
    """
    symbol = request.args.get("symbol", "SPY")
    limit = int(request.args.get("limit", "200"))

    try:
        rows = (
            Finding.query
            .filter(Finding.symbol == symbol)
            .order_by(Finding.timestamp.desc())
            .limit(limit)
            .all()
        )

        out = []
        for f in rows:
            meta = f.finding_metadata or {}
            out.append({
                "id": f.id,
                "t": f.timestamp.strftime("%Y-%m-%d"),
                "title": f.title,
                "severity": f.severity,
                "color": SEVERITY_COLOR.get(f.severity, "#64748b"),
                "confidence": float(f.confidence or 0.0),
                "agent": f.agent_name,
                "meta": meta,
            })

        return jsonify({"symbol": symbol, "signals": out})
    except Exception as e:
        logger.error(f"Error fetching signals: {e}")
        return jsonify({"symbol": symbol, "signals": [], "error": str(e)})


@api_bp.route('/dashboard/signals')
def dashboard_signals():
    """
    Returns all signals with Meta-Agent weight info for dashboard overlay.
    Includes agent enabled status and weight for opacity rendering.
    """
    from backtests.registry import load_schedule
    
    try:
        schedule = load_schedule()
        
        rows = (
            Finding.query
            .order_by(Finding.timestamp.desc())
            .limit(1000)
            .all()
        )
        
        out = []
        for f in rows:
            agent_cfg = schedule.get(f.agent_name, {})
            enabled = agent_cfg.get("enabled", True)
            weight = agent_cfg.get("weight", 1.0)
            rank = agent_cfg.get("rank")
            
            out.append({
                "timestamp": f.timestamp.isoformat() if f.timestamp else None,
                "t": f.timestamp.strftime("%Y-%m-%d") if f.timestamp else None,
                "agent": f.agent_name,
                "severity": f.severity,
                "symbol": f.symbol,
                "title": f.title,
                "confidence": float(f.confidence or 0.0),
                "color": SEVERITY_COLOR.get(f.severity, "#64748b"),
                "enabled": enabled,
                "weight": weight,
                "rank": rank,
            })
        
        return jsonify({"signals": out, "schedule": schedule})
    except Exception as e:
        logger.error(f"Error fetching dashboard signals: {e}")
        return jsonify({"signals": [], "error": str(e)})


@api_bp.route('/eval/heatmap')
def eval_heatmap():
    """
    Forward return heatmap: agent x horizon matrix view.
    Uses cached SPY data and limits to recent findings for performance.
    """
    import pandas as pd
    from data_sources.price_loader import load_spy
    from meta.agent_scorer import label_forward_returns
    
    try:
        spy = load_spy(start="2020-01-01", use_cache=True)
        
        cutoff = datetime.utcnow() - timedelta(days=365)
        findings = (
            Finding.query
            .filter(Finding.timestamp >= cutoff)
            .order_by(Finding.timestamp.asc())
            .limit(5000)
            .all()
        )
        
        if not findings:
            return jsonify({
                "agents": [],
                "columns": ["fwd_ret_1d", "fwd_ret_5d", "fwd_ret_20d"],
                "values": []
            })
        
        rows = [{
            "timestamp": f.timestamp,
            "agent_name": f.agent_name,
            "severity": f.severity,
            "symbol": f.symbol,
            "title": f.title,
        } for f in findings]
        
        events = pd.DataFrame(rows)
        labeled = label_forward_returns(events, spy, horizons=[1, 5, 20])
        
        if labeled.empty:
            return jsonify({
                "agents": [],
                "columns": ["fwd_ret_1d", "fwd_ret_5d", "fwd_ret_20d"],
                "values": []
            })
        
        pivot = labeled.pivot_table(
            index="agent_name",
            values=["fwd_ret_1d", "fwd_ret_5d", "fwd_ret_20d"],
            aggfunc="mean"
        ).fillna(0.0)
        
        return jsonify({
            "agents": pivot.index.tolist(),
            "columns": pivot.columns.tolist(),
            "values": pivot.values.tolist(),
        })
    except Exception as e:
        logger.error(f"Error computing heatmap: {e}")
        return jsonify({"error": str(e), "agents": [], "columns": [], "values": []})


@api_bp.route('/eval/regimes')
def eval_regimes():
    """
    Return daily regime classifications (risk_on, risk_off, transition).
    """
    from meta.regime import load_regime_data
    
    try:
        df = load_regime_data(start="2007-01-01")
        
        if df.empty:
            return jsonify([])
        
        result = []
        for _, r in df.iterrows():
            result.append({
                "date": r["Date"].isoformat(),
                "regime": r["regime"],
                "vix": float(r["VIX"]),
                "close": float(r["Close"]),
                "ma200": float(r["ma200"]) if r["ma200"] else None
            })
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error computing regimes: {e}")
        return jsonify({"error": str(e)})


@api_bp.route('/eval/regime_heatmap')
def regime_heatmap():
    """
    Returns regime x time effectiveness matrix for visualization.
    """
    import numpy as np
    from collections import defaultdict
    from meta.regime_classifier import attach_regimes, RegimeClassifier
    from data_sources.price_loader import load_spy
    from meta.agent_scorer import label_forward_returns
    
    try:
        cutoff = datetime.utcnow() - timedelta(days=365 * 2)
        findings = (
            Finding.query
            .filter(Finding.timestamp >= cutoff)
            .order_by(Finding.timestamp.asc())
            .limit(5000)
            .all()
        )
        
        if not findings:
            return jsonify([])
        
        spy = load_spy(start="2020-01-01", use_cache=True)
        
        rows = [{
            "timestamp": f.timestamp,
            "agent_name": f.agent_name,
            "severity": f.severity,
            "symbol": f.symbol,
        } for f in findings]
        
        import pandas as pd
        events = pd.DataFrame(rows)
        labeled = label_forward_returns(events, spy, horizons=[20])
        
        if labeled.empty:
            return jsonify([])
        
        from meta.regime import load_regime_data
        regime_df = load_regime_data(start="2020-01-01")
        regime_map = {}
        for _, r in regime_df.iterrows():
            regime_map[r["Date"].date()] = r["regime"]
        
        records = []
        for _, row in labeled.iterrows():
            ts = row.get("timestamp")
            if hasattr(ts, 'date'):
                date_key = ts.date()
            else:
                date_key = pd.to_datetime(ts).date()
            
            regime = regime_map.get(date_key, "unknown")
            fwd_ret = row.get("fwd_ret_20d", 0.0)
            
            if fwd_ret is not None and not np.isnan(fwd_ret):
                records.append({
                    "date": str(date_key),
                    "agent": row.get("agent_name"),
                    "regime": regime,
                    "forward_return_20d": float(fwd_ret)
                })
        
        bucket = defaultdict(list)
        for r in records:
            key = (r["regime"], r["date"])
            bucket[key].append(r["forward_return_20d"])
        
        heatmap = []
        for (regime, date), vals in bucket.items():
            arr = np.array(vals)
            heatmap.append({
                "date": date,
                "regime": regime,
                "mean_return": float(np.mean(arr)),
                "hit_rate": float((arr > 0).mean()),
                "count": len(vals)
            })
        
        heatmap.sort(key=lambda x: x["date"])
        
        return jsonify(heatmap)
    except Exception as e:
        logger.error(f"Error computing regime heatmap: {e}")
        return jsonify({"error": str(e)})


@api_bp.route('/regime_state')
def regime_state():
    """
    Returns current market regime with confidence and transition state.
    Uses softmax probability engine with hysteresis for stable regime detection.
    """
    from regime import extract_features, score_regimes, regime_confidence
    from regime.confidence import get_cached_regime, cache_regime
    from data_sources.price_loader import load_spy
    import yfinance as yf
    
    try:
        spy = load_spy(start="2020-01-01", use_cache=True)
        
        try:
            vix = yf.download("^VIX", period="3mo", progress=False)
        except Exception:
            vix = spy.copy()
            vix["Close"] = 20.0
        
        try:
            tnx = yf.download("^TNX", period="3mo", progress=False)
        except Exception:
            tnx = spy.copy()
            tnx["Close"] = 4.0
        
        try:
            gld = yf.download("GLD", period="3mo", progress=False)
        except Exception:
            gld = None
        
        if len(spy) < 20 or len(vix) < 20 or len(tnx) < 20:
            return jsonify({"error": "Insufficient market data", "active_regime": "unknown", "confidence": 0.0})
        
        features = extract_features(spy, vix, tnx, gld)
        scores = score_regimes(features)
        
        state = regime_confidence(
            features,
            scores,
            prev_regime=get_cached_regime()
        )
        
        cache_regime(state["active_regime"])
        
        state["features"] = features
        state["scores"] = scores
        
        return jsonify(state)
    except Exception as e:
        logger.error(f"Error computing regime state: {e}")
        return jsonify({"error": str(e), "active_regime": "unknown", "confidence": 0.0})


@api_bp.route('/regime_report')
def regime_report():
    """
    Generate regime-conditioned rotation report explaining agent decisions.
    """
    from meta.regime_report import generate_rotation_report, load_regime_stats
    from portfolio.agent_decay import AgentDecayModel
    import json
    
    try:
        with open("agent_schedule.json", "r") as f:
            schedule = json.load(f)
        
        agents = list(schedule.keys())
        base_weights = {}
        for agent, cfg in schedule.items():
            if isinstance(cfg, dict):
                base_weights[agent] = cfg.get("weight", 1.0)
            else:
                base_weights[agent] = 1.0
        
        decay_model = AgentDecayModel()
        decay_factors = {}
        for agent, cfg in schedule.items():
            if isinstance(cfg, dict):
                score = cfg.get("score", 0.0)
                days = cfg.get("days_since_eval", 30)
                decay_factors[agent] = decay_model.decay_factor(score, days)
            else:
                decay_factors[agent] = 1.0
        
        from regime.confidence import get_cached_regime
        regime = get_cached_regime() or "risk_on"
        
        from routes.api import regime_state as get_state
        state_resp = get_state()
        state_data = state_resp.get_json() if hasattr(state_resp, 'get_json') else {}
        confidence = state_data.get("confidence", 0.5)
        
        report = generate_rotation_report(
            agents, regime, confidence, base_weights, decay_factors
        )
        
        return jsonify(report)
    except Exception as e:
        logger.error(f"Error generating regime report: {e}")
        return jsonify({"error": str(e)})


@api_bp.route('/ensemble')
def ensemble_signal():
    """
    Get current ensemble meta-agent vote.
    """
    from meta.ensemble_agent import run_ensemble
    from portfolio.agent_decay import AgentDecayModel
    import json
    
    try:
        from regime.confidence import get_cached_regime
        
        with open("agent_schedule.json", "r") as f:
            schedule = json.load(f)
        
        decay_model = AgentDecayModel()
        decay_factors = {}
        for agent, cfg in schedule.items():
            if isinstance(cfg, dict):
                score = cfg.get("score", 0.0)
                days = cfg.get("days_since_eval", 30)
                decay_factors[agent] = decay_model.decay_factor(score, days)
            else:
                decay_factors[agent] = 1.0
        
        findings = [
            {
                "agent": f.agent_name,
                "title": f.title,
                "description": f.description,
                "severity": f.severity,
            }
            for f in Finding.query.order_by(Finding.timestamp.desc()).limit(200).all()
        ]
        
        regime = get_cached_regime() or "risk_on"
        
        from routes.api import regime_state as get_state
        state_resp = get_state()
        state_data = state_resp.get_json() if hasattr(state_resp, 'get_json') else {}
        confidence = state_data.get("confidence", 0.5)
        
        result = run_ensemble(findings, regime, confidence, decay_factors)
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error computing ensemble signal: {e}")
        return jsonify({"error": str(e), "ensemble_signal": "NEUTRAL", "score": 0.0})


@api_bp.route('/regime_council')
def regime_council():
    """
    Run multi-LLM regime council (GPT + Claude + Gemini).
    Returns ensemble regime probabilities with disagreement detection.
    """
    from meta.regime_council import RegimeCouncil, build_signals_from_findings
    from datetime import datetime
    
    try:
        findings = [
            {
                "agent": f.agent_name,
                "title": f.title,
                "description": f.description,
                "severity": f.severity,
            }
            for f in Finding.query.order_by(Finding.timestamp.desc()).limit(50).all()
        ]
        
        import yfinance as yf
        market_data = {}
        try:
            vix = yf.download("^VIX", period="5d", progress=False)
            if len(vix) > 0:
                market_data["vix"] = float(vix["Close"].iloc[-1])
            spy = yf.download("SPY", period="5d", progress=False)
            if len(spy) >= 2:
                market_data["spy_return"] = float((spy["Close"].iloc[-1] / spy["Close"].iloc[-2]) - 1)
            tnx = yf.download("^TNX", period="5d", progress=False)
            if len(tnx) > 0:
                market_data["rates_10y"] = float(tnx["Close"].iloc[-1]) / 100
        except Exception:
            pass
        
        signals = build_signals_from_findings(findings, market_data)
        
        council = RegimeCouncil()
        asof = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
        
        result = council.run(asof_utc=asof, signals=signals)
        
        from meta.uncertainty_state import UncertaintyState
        if result.get("ok"):
            disagreement = result.get("disagreement", {})
            UncertaintyState.set_uncertainty(
                active=disagreement.get("uncertainty_spike", False),
                entropy=result.get("ensemble", {}).get("entropy", 0.0),
                prob_var=disagreement.get("prob_var", 0.0),
                vote_split=disagreement.get("vote_split", 0),
                source="regime_council"
            )
            result["uncertainty_state"] = UncertaintyState.to_dict()
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error running regime council: {e}")
        return jsonify({"ok": False, "error": str(e)})


@api_bp.route('/substitution')
def substitution_report():
    """
    Get agent substitution report showing cluster-based capital flow.
    """
    from meta.agent_substitution import get_substitution_report, load_clusters
    from meta.regime_rotation import apply_regime_rotation
    import json
    
    try:
        with open("agent_schedule.json", "r") as f:
            schedule = json.load(f)
        
        base_weights = {}
        for agent, cfg in schedule.items():
            if isinstance(cfg, dict):
                base_weights[agent] = cfg.get("weight", 1.0) if cfg.get("enabled", True) else 0.0
            else:
                base_weights[agent] = 1.0
        
        from regime.confidence import get_cached_regime
        regime = get_cached_regime() or "risk_on"
        
        from routes.api import regime_state as get_state
        state_resp = get_state()
        state_data = state_resp.get_json() if hasattr(state_resp, 'get_json') else {}
        confidence = state_data.get("confidence", 0.5)
        
        rotated = apply_regime_rotation(base_weights, regime, confidence)
        
        report = get_substitution_report(rotated, regime)
        report["base_weights"] = base_weights
        report["rotated_weights"] = rotated
        report["confidence"] = confidence
        
        return jsonify(report)
    except Exception as e:
        logger.error(f"Error computing substitution report: {e}")
        return jsonify({"error": str(e)})


@api_bp.route('/uncertainty')
def uncertainty_status():
    """
    Get current uncertainty state and decay status.
    """
    from meta.uncertainty_state import UncertaintyState
    from meta.uncertainty_decay import get_decay_status
    from models import UncertaintyEvent
    from datetime import datetime
    
    try:
        latest = UncertaintyEvent.query.order_by(UncertaintyEvent.timestamp.desc()).first()
        recent = UncertaintyEvent.query.order_by(UncertaintyEvent.timestamp.desc()).limit(10).all()
        
        return jsonify({
            "state": UncertaintyState.to_dict(),
            "decay": get_decay_status(datetime.utcnow()),
            "latest_event": latest.to_dict() if latest else None,
            "recent_events": [e.to_dict() for e in recent],
        })
    except Exception as e:
        logger.error(f"Error getting uncertainty status: {e}")
        return jsonify({"error": str(e)})


@api_bp.route('/early_warnings')
def early_warnings():
    """
    Get early regime transition warnings based on agent failures.
    """
    from meta.uncertainty_failure import get_early_warnings, get_failure_summary
    
    try:
        return jsonify({
            "warnings": get_early_warnings(),
            "summary": get_failure_summary(),
        })
    except Exception as e:
        logger.error(f"Error getting early warnings: {e}")
        return jsonify({"error": str(e)})


@api_bp.route('/decay')
def decay_view():
    """
    Get agent decay curves for visualization.
    """
    from meta.decay import _decay
    from models import UncertaintyEvent
    
    try:
        latest_unc = UncertaintyEvent.query.order_by(UncertaintyEvent.timestamp.desc()).first()
        uncertainty_score = latest_unc.score if latest_unc else 0.0
        uncertainty_spike = latest_unc.spike if latest_unc else False
        
        return jsonify({
            "agents": _decay.all_series(last_n=50),
            "uncertainty_score": uncertainty_score,
            "uncertainty_spike": uncertainty_spike,
        })
    except Exception as e:
        logger.error(f"Error getting decay data: {e}")
        return jsonify({"error": str(e)})


@api_bp.route('/agent_heatmap')
def agent_heatmap():
    """
    Get agent failure heatmap data showing performance across regimes.
    """
    from meta.heatmap import _failure_heatmap
    
    try:
        return jsonify(_failure_heatmap.get_heatmap_data())
    except Exception as e:
        logger.error(f"Error getting heatmap data: {e}")
        return jsonify({"error": str(e)})


@api_bp.route('/uncertainty/latest')
def uncertainty_latest():
    """
    Get the latest uncertainty state for dashboard banner.
    Returns level, label, and whether signals should be marked provisional.
    """
    from models import UncertaintyEvent
    
    try:
        ev = UncertaintyEvent.query.order_by(UncertaintyEvent.timestamp.desc()).first()
        
        if not ev:
            return jsonify({
                "level": 0.0,
                "label": "normal",
                "provisional": False,
                "created_at": None,
                "disagreement": 0.0,
                "regime": "unknown"
            })
        
        level = float(ev.score or 0.0)
        label = ev.label or "normal"
        
        provisional = level >= 0.7 or label not in ("normal", "calm")
        
        return jsonify({
            "level": round(level, 3),
            "label": label,
            "provisional": provisional,
            "created_at": ev.timestamp.isoformat() if ev.timestamp else None,
            "disagreement": round(float(ev.disagreement or 0.0), 3),
            "regime": ev.active_regime or "unknown",
            "spike": ev.spike,
            "cadence_multiplier": ev.cadence_multiplier,
            "decay_multiplier": ev.decay_multiplier
        })
    except Exception as e:
        logger.error(f"Error getting latest uncertainty: {e}")
        return jsonify({"error": str(e), "level": 0.0, "label": "error", "provisional": False}), 500


@api_bp.route('/uncertainty/transition')
def uncertainty_transition():
    """
    Get early-warning transition detection status.
    """
    try:
        from regime.transition_detector import detect_transition
        result = detect_transition(window_minutes=60, spike_threshold=0.5)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error checking transition: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@api_bp.route('/council/stats')
def council_stats():
    """
    Get agent council voting statistics for fail-first analysis.
    """
    try:
        from meta.council_learning import fail_first_ranking
        from regime.confidence import get_cached_regime
        
        regime = get_cached_regime() or "unknown"
        ranking = fail_first_ranking(min_n=5, regime=regime)
        
        return jsonify({
            "regime": regime,
            "ranking": ranking,
            "count": len(ranking)
        })
    except Exception as e:
        logger.error(f"Error getting council stats: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route('/uncertainty/spy')
def spy_uncertainty():
    """
    Get SPY price data with uncertainty bands for visualization.
    """
    try:
        from telemetry.uncertainty_events import load_recent_uncertainty
        import yfinance as yf
        from datetime import datetime, timedelta
        
        end = datetime.now()
        start = end - timedelta(days=180)
        
        spy = yf.download("SPY", start=start.strftime("%Y-%m-%d"), 
                          end=end.strftime("%Y-%m-%d"), progress=False)
        
        if spy.empty:
            return jsonify({"error": "No SPY data available"}), 404
        
        uncertainty = load_recent_uncertainty()
        max_u = max(uncertainty.values()) if uncertainty else 0.0
        
        dates = spy.index.strftime("%Y-%m-%d").tolist()
        prices = spy["Close"].tolist()
        
        band_width = [max_u * 0.03 * p for p in prices]
        
        return jsonify({
            "dates": dates,
            "price": prices,
            "uncertainty": max_u,
            "band_upper": [p + b for p, b in zip(prices, band_width)],
            "band_lower": [p - b for p, b in zip(prices, band_width)]
        })
    except Exception as e:
        logger.error(f"Error getting SPY uncertainty data: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route('/agents/decay')
def agents_decay():
    """
    Get agent decay heatmap by regime for visualization.
    """
    try:
        from telemetry.uncertainty_events import load_recent_uncertainty
        from regime.confidence import get_cached_regime
        
        regime = get_cached_regime() or "unknown"
        uncertainty = load_recent_uncertainty()
        
        agents = [
            {
                "agent": agent,
                "uncertainty": round(u, 3),
                "decay": round(1 - u, 3),
                "status": "stable" if u < 0.3 else ("degrading" if u < 0.7 else "decayed")
            }
            for agent, u in uncertainty.items()
        ]
        
        agents.sort(key=lambda x: x["decay"])
        
        return jsonify({
            "regime": regime,
            "agents": agents
        })
    except Exception as e:
        logger.error(f"Error getting agent decay data: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route('/substitution/status')
def substitution_status():
    """
    Get current agent substitution status based on uncertainty.
    """
    try:
        from telemetry.uncertainty_events import load_recent_uncertainty
        from meta.substitution import get_substitution_status, load_substitution_map
        
        uncertainty = load_recent_uncertainty()
        substitution_map = load_substitution_map()
        
        from scheduler import _regime_weights
        status = get_substitution_status(uncertainty, _regime_weights or {})
        
        return jsonify({
            "substitution_map": substitution_map,
            "agents": status
        })
    except Exception as e:
        logger.error(f"Error getting substitution status: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route('/agent/explain/<agent_name>')
@api_login_required
def agent_explain(agent_name):
    """
    Get explanation for why an agent is inactive or substituted.
    This is the institutional-grade transparency layer.
    """
    try:
        from backtests.regime_report import build_regime_report
        from regime.confidence import get_cached_regime
        
        regime = get_cached_regime() or "unknown"
        report = build_regime_report(agent_name, regime)
        
        return jsonify(report)
    except Exception as e:
        logger.error(f"Error getting agent explanation for {agent_name}: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route('/agents/inactive/explain')
def inactive_agents_explain():
    """
    Get explanations for all inactive agents in current regime.
    """
    try:
        from backtests.regime_report import get_inactive_agents_explanation
        from regime.confidence import get_cached_regime
        
        regime = get_cached_regime() or "unknown"
        explanations = get_inactive_agents_explanation(regime)
        
        return jsonify({
            "regime": regime,
            "inactive_agents": explanations
        })
    except Exception as e:
        logger.error(f"Error getting inactive agents explanation: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route('/analyze', methods=['POST'])
@api_login_required
def analyze_finding():
    """
    Run 3-LLM council + TA analysis on a finding.
    
    Request body:
        finding_id: int - ID of finding to analyze
        force: bool - Re-analyze even if already done (optional)
    
    Response:
        ok: bool
        ta: dict - TA engine vote result
        council: dict - LLM council consensus
        triple_confirmed: bool - Whether all gates passed
        alerted: bool - Whether email was sent
    """
    from services.auto_triage import auto_analyze_and_alert
    from models import Finding, LLMCouncilResult, db
    
    try:
        data = request.get_json() or {}
        finding_id = data.get("finding_id")
        force = data.get("force", False)
        
        if not finding_id:
            return jsonify({"error": "finding_id required"}), 400
        
        result = auto_analyze_and_alert(finding_id, force=force)
        
        if result.get("ok"):
            f = Finding.query.get(finding_id)
            if f:
                council_result = LLMCouncilResult(
                    finding_id=finding_id,
                    agent_name=f.agent_name,
                    consensus=f.consensus_action,
                    agreement=f.consensus_confidence,
                    uncertainty=1.0 if f.llm_disagreement else 0.0,
                    raw_votes=f.llm_votes,
                    severity=f.severity,
                    confidence=f.confidence,
                )
                db.session.add(council_result)
                db.session.commit()
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error analyzing finding: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route('/analyze/batch', methods=['POST'])
@api_login_required
def analyze_batch():
    """
    Batch analyze multiple findings.
    
    Request body:
        finding_ids: list[int] - IDs to analyze
        force: bool - Re-analyze (optional)
    """
    from services.auto_triage import auto_analyze_and_alert
    
    try:
        data = request.get_json() or {}
        finding_ids = data.get("finding_ids", [])
        force = data.get("force", False)
        
        results = []
        for fid in finding_ids[:50]:
            result = auto_analyze_and_alert(fid, force=force)
            results.append({"finding_id": fid, **result})
        
        return jsonify({"results": results, "count": len(results)})
    except Exception as e:
        logger.error(f"Error batch analyzing: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route('/triage/summary')
@api_login_required
def triage_summary():
    """
    Get summary of auto-triage results.
    """
    from services.auto_triage import get_triage_summary
    
    try:
        limit = request.args.get("limit", 50, type=int)
        summary = get_triage_summary(limit)
        return jsonify(summary)
    except Exception as e:
        logger.error(f"Error getting triage summary: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route('/findings/action-required')
@api_login_required
def action_required_findings():
    """
    Get findings that require action based on LLM council consensus.
    
    For equities/crypto: BOTH ta_council AND fund_council must be 'act'
    For real estate: real_estate_council must be 'act'
    """
    try:
        from sqlalchemy import or_, and_
        
        limit = request.args.get("limit", 50, type=int)
        hours = request.args.get("hours", 168, type=int)
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        findings = Finding.query.filter(
            Finding.timestamp >= cutoff,
            or_(
                and_(
                    Finding.market_type.in_(['equity', 'crypto', 'technical']),
                    Finding.ta_council == 'act',
                    Finding.fund_council == 'act'
                ),
                and_(
                    Finding.market_type == 'real_estate',
                    Finding.real_estate_council == 'act'
                )
            )
        ).order_by(Finding.timestamp.desc()).limit(limit).all()
        
        return jsonify({
            "count": len(findings),
            "findings": [f.to_dict() for f in findings]
        })
        
    except Exception as e:
        logger.error(f"Error getting action-required findings: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route('/findings/backfill-council', methods=['POST'])
@api_login_required
def backfill_trade_council():
    """
    Run existing findings through LLM Trade Council to populate
    ta_council, fund_council, and real_estate_council fields.
    """
    import os
    from openai import OpenAI
    
    try:
        limit = request.args.get("limit", 100, type=int)
        
        api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY")
        base_url = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")
        
        if not api_key:
            return jsonify({"error": "OpenAI API key not configured"}), 500
        
        client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
        
        findings = Finding.query.filter(
            Finding.ta_council.is_(None),
            Finding.fund_council.is_(None)
        ).order_by(Finding.timestamp.desc()).limit(limit).all()
        
        processed = 0
        act_count = 0
        results = []
        
        for finding in findings:
            try:
                asset_type = 'crypto' if any(c in (finding.symbol or '').upper() for c in ['BTC', 'ETH', 'SOL', 'USDT', 'USDC']) else \
                             'real_estate' if 'property' in (finding.agent_name or '').lower() or 'distress' in (finding.agent_name or '').lower() else \
                             'equity'
                
                prompt = f"""Analyze this market finding and provide trade verdicts:
Agent: {finding.agent_name}, Symbol: {finding.symbol}, Severity: {finding.severity}, Confidence: {finding.confidence}
Title: {finding.title}
Description: {(finding.description or '')[:400]}

For each council, respond ACT (trade now), WATCH (monitor), or HOLD (no action):
ta_council=ACT|WATCH|HOLD
fund_council=ACT|WATCH|HOLD
real_estate_council=ACT|WATCH|HOLD|N/A"""

                response = client.chat.completions.create(
                    model='gpt-4o-mini',
                    messages=[{'role': 'user', 'content': prompt}],
                    max_tokens=80,
                    temperature=0.2
                )
                
                text = response.choices[0].message.content or ''
                
                for line in text.strip().split('\n'):
                    if '=' in line:
                        key, val = line.split('=', 1)
                        key = key.strip().lower()
                        val = val.strip().lower()
                        if val in ['act', 'watch', 'hold']:
                            if 'ta' in key:
                                finding.ta_council = val
                            elif 'fund' in key:
                                finding.fund_council = val
                            elif 'real' in key:
                                finding.real_estate_council = val
                
                if finding.ta_council == 'act' and finding.fund_council == 'act':
                    act_count += 1
                    results.append({
                        "id": finding.id,
                        "title": finding.title[:50],
                        "agent": finding.agent_name,
                        "action_required": True
                    })
                
                processed += 1
                
                if processed % 10 == 0:
                    db.session.commit()
                    
            except Exception as e:
                logger.warning(f"Error processing finding {finding.id}: {e}")
                continue
        
        db.session.commit()
        
        return jsonify({
            "processed": processed,
            "action_required_count": act_count,
            "action_items": results
        })
        
    except Exception as e:
        logger.error(f"Error in backfill: {e}")
        return jsonify({"error": str(e)}), 500
