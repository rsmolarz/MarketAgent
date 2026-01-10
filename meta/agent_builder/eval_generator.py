import re
from pathlib import Path


EVAL_TEMPLATE = '''"""
Eval suite for {class_name}
"""
import pytest
from unittest.mock import patch, MagicMock

from agents.{module_name} import {class_name}


class Test{class_name}:
    """Smoke tests for {class_name}."""
    
    def test_init(self):
        """Test agent initialization."""
        agent = {class_name}()
        assert agent.name == "{class_name}"
    
    def test_analyze_returns_list(self):
        """Test that analyze returns a list."""
        agent = {class_name}()
        result = agent.analyze()
        assert isinstance(result, list)
    
    def test_finding_schema(self):
        """Test that findings follow required schema."""
        agent = {class_name}()
        findings = agent.analyze()
        
        required_keys = ["title", "description", "severity", "confidence", "metadata"]
        
        for finding in findings:
            for key in required_keys:
                assert key in finding, f"Missing required key: {{key}}"
            
            assert finding["severity"] in ("low", "medium", "high")
            assert 0 <= finding["confidence"] <= 1
            assert isinstance(finding["metadata"], dict)
    
    def test_plan(self):
        """Test that plan returns a dict with steps."""
        agent = {class_name}()
        plan = agent.plan()
        assert isinstance(plan, dict)
        assert "steps" in plan
    
    def test_reflect(self):
        """Test reflection on results."""
        agent = {class_name}()
        findings = [
            {{"title": "Test", "description": "Desc", "severity": "high", "confidence": 0.9, "metadata": {{}}}},
            {{"title": "Test2", "description": "Desc2", "severity": "low", "confidence": 0.5, "metadata": {{}}}}
        ]
        reflection = agent.reflect(findings)
        assert reflection["finding_count"] == 2
        assert reflection["high_severity_count"] == 1


class Test{class_name}Offline:
    """Offline tests using fixtures (no network)."""
    
    @pytest.fixture
    def mock_data(self):
        """Fixture providing mock data for testing."""
        return {{
            "sample_input": {{}},
            "expected_output_count": 0
        }}
    
    def test_with_fixture(self, mock_data):
        """Test with offline fixture data."""
        agent = {class_name}()
        # In real implementation, inject mock_data into agent
        result = agent.analyze()
        assert isinstance(result, list)
'''


def to_snake_case(name: str) -> str:
    """Convert CamelCase to snake_case."""
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def generate_eval(class_name: str) -> Path:
    """
    Generate eval test suite for an agent.
    
    Args:
        class_name: The agent class name
    
    Returns:
        Path to the created test file
    """
    if not class_name.endswith("Agent"):
        class_name = f"{class_name}Agent"
    
    module_name = to_snake_case(class_name)
    
    eval_code = EVAL_TEMPLATE.format(
        class_name=class_name,
        module_name=module_name
    )
    
    tests_dir = Path("tests/agents")
    tests_dir.mkdir(parents=True, exist_ok=True)
    
    test_file = tests_dir / f"test_{module_name}.py"
    test_file.write_text(eval_code)
    
    return test_file
