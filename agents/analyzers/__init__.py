"""
Modular Analyzers for Market Analysis Agents

Contains reusable analysis components that can be used by multiple agents.
"""

from .macro_bubble_detector import MacroBubbleDetector
from .cds_analyzer import CDSAnalyzer
from .structured_product_analyzer import StructuredProductAnalyzer
from .forecaster import ForecasterAnalyzer
from .regime_detector import RegimeDetector
from .ensemble import EnsemblePredictor

__all__ = [
    'MacroBubbleDetector',
    'CDSAnalyzer', 
    'StructuredProductAnalyzer',
    'ForecasterAnalyzer',
    'RegimeDetector',
    'EnsemblePredictor'
]
