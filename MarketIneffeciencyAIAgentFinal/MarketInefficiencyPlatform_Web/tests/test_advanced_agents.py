
import unittest
from unittest.mock import patch
from agents.short_interest_spike import ShortInterestSpikeAgent
from agents.whale_wallet_watcher import WhaleWalletWatcherAgent
from agents.etf_flow_shift import ETFFlowShiftAgent
from agents.regulatory_alert import RegulatoryAlertAgent
from agents.correlation_break import CorrelationBreakAgent
from agents.sentiment_divergence import SentimentDivergenceAgent
from agents.crypto_funding_rate import CryptoFundingRateAgent
from agents.satellite_data import SatelliteDataAgent

class TestAdvancedAgents(unittest.TestCase):

    @patch("requests.post")
    def test_short_interest_agent(self, mock_post):
        agent = ShortInterestSpikeAgent()
        results = agent.act()
        self.assertTrue(any("short" in r.lower() for r in results))

    @patch("requests.post")
    def test_whale_wallet_agent(self, mock_post):
        agent = WhaleWalletWatcherAgent()
        results = agent.act()
        self.assertTrue(any("whale" in r.lower() for r in results))

    @patch("requests.post")
    def test_etf_flow_agent(self, mock_post):
        agent = ETFFlowShiftAgent()
        results = agent.act()
        self.assertTrue(any("ETF" in r for r in results))

    @patch("requests.post")
    def test_regulatory_agent(self, mock_post):
        agent = RegulatoryAlertAgent()
        results = agent.act()
        self.assertTrue(any("regulatory" in r.lower() for r in results))

    @patch("requests.post")
    def test_correlation_break_agent(self, mock_post):
        agent = CorrelationBreakAgent()
        results = agent.act()
        self.assertTrue(any("correlation" in r.lower() for r in results))

    @patch("requests.post")
    def test_sentiment_divergence_agent(self, mock_post):
        agent = SentimentDivergenceAgent()
        results = agent.act()
        self.assertTrue(any("sentiment" in r.lower() for r in results))

    @patch("requests.post")
    def test_crypto_funding_agent(self, mock_post):
        agent = CryptoFundingRateAgent()
        results = agent.act()
        self.assertTrue(any("funding" in r.lower() for r in results))

    @patch("requests.post")
    def test_satellite_data_agent(self, mock_post):
        agent = SatelliteDataAgent()
        results = agent.act()
        self.assertTrue(any("tanker" in r.lower() or "satellite" in r.lower() for r in results))

if __name__ == "__main__":
    unittest.main()
