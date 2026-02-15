"""Tests for the AI Advisory Board multi-agent debate system."""

import pytest
from unittest.mock import patch, MagicMock

from advisory_board.personas import ADVISORS, get_advisor, MODERATOR_PROMPT
from advisory_board.frameworks import (
    BarbellAnalyzer,
    BlackSwanScanner,
    AlphaExtractor,
    ConvexityMapper,
)
from advisory_board.engine import AdvisoryBoardEngine


SAMPLE_PROPOSAL = (
    "We are considering acquiring a distressed competitor at 40 cents on the dollar. "
    "They have $200M in revenue but $150M in debt. Should we proceed?"
)


# ---------------------------------------------------------------
# Persona Tests
# ---------------------------------------------------------------
class TestPersonas:
    def test_all_four_advisors_registered(self):
        assert set(ADVISORS.keys()) == {"taleb", "spitznagel", "simons", "asness"}

    def test_each_advisor_has_required_fields(self):
        required = {"name", "role", "avatar", "color", "system_prompt", "expertise", "bias"}
        for aid, data in ADVISORS.items():
            missing = required - set(data.keys())
            assert not missing, f"{aid} missing fields: {missing}"

    def test_system_prompts_are_substantial(self):
        for aid, data in ADVISORS.items():
            assert len(data["system_prompt"]) > 1000, f"{aid} prompt too short"

    def test_get_advisor_valid(self):
        taleb = get_advisor("taleb")
        assert taleb is not None
        assert taleb["name"] == "Nassim Nicholas Taleb"

    def test_get_advisor_case_insensitive(self):
        assert get_advisor("TALEB") is not None

    def test_get_advisor_invalid(self):
        assert get_advisor("nonexistent") is None

    def test_moderator_prompt_exists(self):
        assert len(MODERATOR_PROMPT) > 200


# ---------------------------------------------------------------
# Framework Tests
# ---------------------------------------------------------------
class TestBarbellAnalyzer:
    def test_analyze_returns_structure(self):
        result = BarbellAnalyzer.analyze(SAMPLE_PROPOSAL)
        assert result["framework"] == "barbell_strategy"
        assert "safety_side" in result
        assert "upside_side" in result
        assert "forbidden_middle" in result
        assert "decision_matrix" in result

    def test_safety_criteria_count(self):
        result = BarbellAnalyzer.analyze(SAMPLE_PROPOSAL)
        assert len(result["safety_side"]["criteria"]) == 8

    def test_upside_criteria_count(self):
        result = BarbellAnalyzer.analyze(SAMPLE_PROPOSAL)
        assert len(result["upside_side"]["criteria"]) == 6

    def test_criteria_weights_sum_to_one(self):
        safety_sum = sum(c["weight"] for c in BarbellAnalyzer.SAFETY_CRITERIA)
        upside_sum = sum(c["weight"] for c in BarbellAnalyzer.UPSIDE_CRITERIA)
        assert abs(safety_sum - 1.0) < 0.01
        assert abs(upside_sum - 1.0) < 0.01

    def test_forbidden_middle_has_red_flags(self):
        result = BarbellAnalyzer.analyze(SAMPLE_PROPOSAL)
        assert len(result["forbidden_middle"]["red_flags"]) > 0


class TestBlackSwanScanner:
    def test_scan_returns_structure(self):
        result = BlackSwanScanner.scan(SAMPLE_PROPOSAL)
        assert result["framework"] == "black_swan_scan"
        assert "risk_categories" in result
        assert "severity_scale" in result
        assert "response_framework" in result

    def test_risk_categories_count(self):
        result = BlackSwanScanner.scan(SAMPLE_PROPOSAL)
        assert len(result["risk_categories"]) == 6

    def test_each_category_has_signals(self):
        for cat in BlackSwanScanner.RISK_CATEGORIES:
            assert len(cat["signals"]) >= 3, f"{cat['category']} has too few signals"

    def test_severity_scale_complete(self):
        result = BlackSwanScanner.scan(SAMPLE_PROPOSAL)
        expected = {"EXISTENTIAL", "SEVERE", "SIGNIFICANT", "MODERATE"}
        assert set(result["severity_scale"].keys()) == expected


class TestAlphaExtractor:
    def test_extract_returns_structure(self):
        result = AlphaExtractor.extract(SAMPLE_PROPOSAL)
        assert result["framework"] == "alpha_extraction"
        assert "signal_types" in result
        assert "quality_metrics" in result

    def test_signal_types_count(self):
        result = AlphaExtractor.extract(SAMPLE_PROPOSAL)
        assert len(result["signal_types"]) == 4

    def test_signal_types_have_decay(self):
        for st in AlphaExtractor.SIGNAL_TYPES:
            assert "decay_rate" in st


class TestConvexityMapper:
    def test_map_returns_structure(self):
        result = ConvexityMapper.map_payoff(SAMPLE_PROPOSAL)
        assert result["framework"] == "convexity_mapping"
        assert "payoff_profiles" in result
        assert "convex" in result["payoff_profiles"]
        assert "concave" in result["payoff_profiles"]
        assert "linear" in result["payoff_profiles"]


# ---------------------------------------------------------------
# Engine Tests
# ---------------------------------------------------------------
class TestAdvisoryBoardEngine:
    def setup_method(self):
        self.engine = AdvisoryBoardEngine()

    def test_create_session(self):
        sid = self.engine.create_session("user-1")
        assert len(sid) == 16
        session = self.engine.get_session(sid)
        assert session["user_id"] == "user-1"
        assert session["turns"] == []

    def test_get_session_nonexistent(self):
        assert self.engine.get_session("fake-id") is None

    @patch("advisory_board.engine._call_llm")
    def test_ask_advisor(self, mock_llm):
        mock_llm.return_value = "This is dangerously fragile. Let me explain..."
        result = self.engine.ask_advisor("taleb", SAMPLE_PROPOSAL)
        assert result["advisor"] == "Nassim Nicholas Taleb"
        assert result["advisor_id"] == "taleb"
        assert result["color"] == "#D32F2F"
        assert "response" in result
        mock_llm.assert_called_once()

    def test_ask_advisor_invalid(self):
        result = self.engine.ask_advisor("buffett", SAMPLE_PROPOSAL)
        assert "error" in result

    @patch("advisory_board.engine._call_llm")
    def test_convene_panel(self, mock_llm):
        mock_llm.return_value = "Analysis response"
        result = self.engine.convene_panel(SAMPLE_PROPOSAL)
        assert result["type"] == "panel"
        assert result["advisor_count"] == 4
        assert set(result["responses"].keys()) == {"taleb", "spitznagel", "simons", "asness"}

    @patch("advisory_board.engine._call_llm")
    def test_convene_panel_subset(self, mock_llm):
        mock_llm.return_value = "Analysis response"
        result = self.engine.convene_panel(SAMPLE_PROPOSAL, advisors=["taleb", "simons"])
        assert result["advisor_count"] == 2

    @patch("advisory_board.engine._call_llm")
    def test_run_debate(self, mock_llm):
        mock_llm.return_value = "Detailed analysis with cross-examination"
        result = self.engine.run_debate(SAMPLE_PROPOSAL, include_frameworks=True)
        assert result["type"] == "debate"
        assert "frameworks" in result
        assert "advisor_responses" in result
        assert "cross_examination" in result
        assert "synthesis" in result
        assert "structured_output" in result

    @patch("advisory_board.engine._call_llm")
    def test_stream_debate_yields_events(self, mock_llm):
        mock_llm.return_value = "Streaming analysis response"
        events = list(self.engine.stream_debate(SAMPLE_PROPOSAL))
        event_types = [e["event"] for e in events]
        assert "phase" in event_types
        assert "advisor_start" in event_types
        assert "advisor_complete" in event_types
        assert "complete" in event_types

    @patch("advisory_board.engine._call_llm")
    def test_session_tracks_turns(self, mock_llm):
        mock_llm.return_value = "Response"
        sid = self.engine.create_session()
        self.engine.ask_advisor("taleb", SAMPLE_PROPOSAL, sid)
        session = self.engine.get_session(sid)
        assert len(session["turns"]) == 1
        assert session["turns"][0]["type"] == "individual"


# ---------------------------------------------------------------
# Flask Route Tests
# ---------------------------------------------------------------
class TestAdvisoryBoardRoutes:
    @pytest.fixture(autouse=True)
    def setup_app(self):
        import os
        os.environ.setdefault("REPL_ID", "test")
        from app import app
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_advisory_board_page(self):
        resp = self.client.get("/advisory-board")
        assert resp.status_code == 200
        assert b"AI Advisory Board" in resp.data

    def test_list_advisors(self):
        resp = self.client.get("/api/advisory-board/advisors")
        data = resp.get_json()
        assert resp.status_code == 200
        assert len(data["advisors"]) == 4
        names = {a["id"] for a in data["advisors"]}
        assert names == {"taleb", "spitznagel", "simons", "asness"}

    def test_create_session(self):
        resp = self.client.post("/api/advisory-board/session",
                                json={"user_id": "test"})
        data = resp.get_json()
        assert resp.status_code == 200
        assert "session_id" in data

    def test_ask_missing_fields(self):
        resp = self.client.post("/api/advisory-board/ask", json={})
        assert resp.status_code == 400

    def test_ask_invalid_advisor(self):
        resp = self.client.post("/api/advisory-board/ask",
                                json={"advisor_id": "buffett", "proposal": "test"})
        assert resp.status_code == 400

    def test_panel_missing_proposal(self):
        resp = self.client.post("/api/advisory-board/panel", json={})
        assert resp.status_code == 400

    def test_debate_missing_proposal(self):
        resp = self.client.post("/api/advisory-board/debate", json={})
        assert resp.status_code == 400

    def test_frameworks_endpoint(self):
        resp = self.client.post("/api/advisory-board/frameworks",
                                json={"proposal": "Test proposal",
                                      "frameworks": ["barbell"]})
        data = resp.get_json()
        assert resp.status_code == 200
        assert "barbell" in data["frameworks"]
