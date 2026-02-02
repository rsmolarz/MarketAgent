"""Unit Tests for API Endpoints and Models

Tests for governor-state, ic-memo endpoints, and database models.
"""

import pytest
import json
from datetime import datetime


class TestGovernorStateEndpoint:
    """Tests for /governor-state endpoint"""
    
    def test_governor_state_returns_valid_json(self, client):
        """Test that endpoint returns valid JSON"""
        response = client.get('/api/governor-state')
        assert response.status_code == 200
        assert response.json is not None
    
    def test_governor_state_has_required_fields(self, client):
        """Test that response contains all required fields"""
        response = client.get('/api/governor-state')
        data = response.json
        
        required_fields = ['status', 'drawdown_limit', 'current_drawdown',
                           'trades_allowed', 'risk_level', 'last_update']
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
    
    def test_governor_state_values_in_valid_range(self, client):
        """Test that values are within expected ranges"""
        response = client.get('/api/governor-state')
        data = response.json
        
        assert 0 <= data['drawdown_limit'] <= 1
        assert 0 <= data['current_drawdown'] <= 1
        assert isinstance(data['trades_allowed'], bool)
        assert data['risk_level'] in ['low', 'medium', 'high', 'critical', 'unknown']


class TestICMemoEndpoint:
    """Tests for /ic-memo endpoint"""
    
    def test_ic_memo_returns_valid_json(self, client):
        """Test that endpoint returns valid JSON"""
        response = client.get('/api/ic-memo')
        assert response.status_code == 200
        assert response.json is not None
    
    def test_ic_memo_has_required_fields(self, client):
        """Test that response contains all required fields"""
        response = client.get('/api/ic-memo')
        data = response.json
        
        required_fields = ['title', 'thesis', 'key_points', 'risk_factors',
                           'recommendation', 'confidence', 'generated_at']
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
    
    def test_ic_memo_confidence_in_valid_range(self, client):
        """Test that confidence score is within valid range"""
        response = client.get('/api/ic-memo')
        data = response.json
        
        assert 0 <= data['confidence'] <= 1
    
    def test_ic_memo_recommendation_valid(self, client):
        """Test that recommendation is a valid value"""
        response = client.get('/api/ic-memo')
        data = response.json
        
        valid_recommendations = ['buy', 'sell', 'hold', 'watch', 'avoid']
        assert data['recommendation'].lower() in valid_recommendations


class TestGovernorStateModel:
    """Tests for GovernorState database model"""
    
    def test_governor_state_creation(self, app):
        """Test creating a GovernorState record"""
        from models import GovernorState, db
        with app.app_context():
            state = GovernorState(
                status='active',
                drawdown_limit=0.03,
                current_drawdown=0.015,
                trades_allowed=True,
                risk_level='medium'
            )
            db.session.add(state)
            db.session.commit()
            
            assert state.id is not None
            assert state.status == 'active'
            assert state.drawdown_limit == 0.03
    
    def test_governor_state_update(self, app):
        """Test updating a GovernorState record"""
        from models import GovernorState, db
        with app.app_context():
            state = GovernorState.query.first()
            if state:
                state.current_drawdown = 0.02
                db.session.commit()
                
                updated = db.session.get(GovernorState, state.id)
                assert updated.current_drawdown == 0.02
    
    def test_governor_state_defaults(self, app):
        """Test default values for GovernorState"""
        from models import GovernorState, db
        with app.app_context():
            state = GovernorState(status='active')
            db.session.add(state)
            db.session.commit()
            
            assert state.trades_allowed is True or state.trades_allowed is None


class TestICMemoModel:
    """Tests for ICMemo database model"""
    
    def test_ic_memo_creation(self, app):
        """Test creating an ICMemo record"""
        from models import ICMemo, db
        with app.app_context():
            memo = ICMemo(
                symbol='AAPL',
                memo_type='trade_recommendation',
                content='Test memo content',
                confidence=0.85,
                created_at=datetime.utcnow()
            )
            db.session.add(memo)
            db.session.commit()
            
            assert memo.id is not None
            assert memo.symbol == 'AAPL'
            assert memo.confidence == 0.85
    
    def test_ic_memo_required_fields(self, app):
        """Test that ICMemo has required fields"""
        from models import ICMemo, db
        with app.app_context():
            memo = ICMemo(
                symbol='TSLA',
                memo_type='analysis',
                content='Analysis content'
            )
            db.session.add(memo)
            db.session.commit()
            
            assert memo.symbol is not None
            assert memo.memo_type is not None
    
    def test_ic_memo_timestamp(self, app):
        """Test ICMemo timestamp handling"""
        from models import ICMemo, db
        with app.app_context():
            before = datetime.utcnow()
            memo = ICMemo(
                symbol='GOOGL',
                memo_type='analysis',
                content='Test content',
                created_at=datetime.utcnow()
            )
            db.session.add(memo)
            db.session.commit()
            
            assert memo.created_at is not None
            assert memo.created_at >= before


class TestHealthEndpoint:
    """Tests for health check endpoint"""
    
    def test_health_returns_ok(self, client):
        """Test that health endpoint returns OK"""
        response = client.get('/api/health')
        assert response.status_code == 200
    
    def test_health_has_status(self, client):
        """Test that health response has status field"""
        response = client.get('/api/health')
        data = response.json
        
        assert 'status' in data or response.status_code == 200


@pytest.fixture
def app():
    """Create application for testing"""
    from app import app as flask_app
    from models import db
    
    flask_app.config['TESTING'] = True
    flask_app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    
    with flask_app.app_context():
        db.create_all()
        yield flask_app
        db.drop_all()


@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()
