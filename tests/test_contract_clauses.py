"""
Tests for contract clause extraction.

Tests governing law, venue, and personal guarantee detection
to ensure extraction logic correctly identifies key contract terms.
"""

import pytest
from services.contract_extractor import extract_clauses


@pytest.mark.parametrize("text,expected", [
    (
        "This Agreement shall be governed by the laws of the State of New York.",
        "New York"
    ),
    (
        "This contract is governed by Texas law.",
        "Texas"
    ),
    (
        "The laws of California shall govern this Agreement.",
        "California"
    ),
    (
        "This Agreement is subject to the laws of Delaware.",
        "Delaware"
    ),
    (
        "Governed by the laws of the State of Florida without regard to conflicts of law.",
        "Florida"
    ),
])
def test_governing_law_extraction(text, expected):
    """Test that governing law is correctly extracted from various phrasings."""
    clauses = extract_clauses(text)
    assert clauses.get("governing_law") == expected


@pytest.mark.parametrize("text,expected", [
    (
        "Venue shall lie exclusively in Harris County, Texas.",
        "Harris County, Texas"
    ),
    (
        "The exclusive jurisdiction of the courts of New York County.",
        "New York County"
    ),
    (
        "The forum for any dispute shall be Los Angeles, California.",
        "Los Angeles, California"
    ),
])
def test_venue_extraction(text, expected):
    """Test that venue/forum clauses are correctly extracted."""
    clauses = extract_clauses(text)
    assert clauses.get("venue") == expected


@pytest.mark.parametrize("text", [
    "The undersigned personally guarantees all obligations.",
    "This note is personally guaranteed by the borrower.",
    "Borrower provides a personal guarantee for this loan.",
    "The individual shall personally guarantee payment.",
])
def test_personal_guarantee_detection(text):
    """Test that personal guarantee clauses are correctly detected."""
    clauses = extract_clauses(text)
    assert clauses.get("personal_guarantee") is True


@pytest.mark.parametrize("text", [
    "This is a standard loan agreement with no personal liability.",
    "The company is solely responsible for repayment.",
    "Corporate guarantee only.",
])
def test_no_personal_guarantee(text):
    """Test that non-guarantee text does not trigger false positives."""
    clauses = extract_clauses(text)
    assert clauses.get("personal_guarantee") is False


def test_full_contract_extraction():
    """Test extraction from a more realistic contract snippet."""
    contract = """
    LOAN AGREEMENT
    
    This Agreement shall be governed by the laws of the State of New York.
    Venue shall lie exclusively in New York County, New York.
    The undersigned personally guarantees all obligations under this Agreement.
    """
    
    clauses = extract_clauses(contract)
    
    assert clauses.get("governing_law") == "New York"
    assert clauses.get("venue") == "New York County, New York"
    assert clauses.get("personal_guarantee") is True


def test_empty_text():
    """Test that empty text returns None/False for all clauses."""
    clauses = extract_clauses("")
    
    assert clauses.get("governing_law") is None
    assert clauses.get("venue") is None
    assert clauses.get("personal_guarantee") is False
