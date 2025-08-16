
import unittest
from unittest.mock import patch
from agents.supply_chain_disruption import SupplyChainDisruptionAgent
from agents.options_skew import OptionsSkewAgent
from agents.insider_trading_alert import InsiderTradingAlertAgent
from agents.patent_surge import PatentSurgeAgent
from agents.alt_data_signal import AltDataSignalAgent
from agents.geopolitical_risk import GeopoliticalRiskAgent
from agents.energy_disruption import EnergyDisruptionAgent

class TestNewAgents(unittest.TestCase):

    @patch("requests.post")
    def test_supply_chain_agent(self, mock_post):
        agent = SupplyChainDisruptionAgent()
        results = agent.act()
        self.assertTrue(any("Shipping" in r for r in results))

    @patch("requests.post")
    def test_options_skew_agent(self, mock_post):
        agent = OptionsSkewAgent()
        results = agent.act()
        self.assertTrue(any("skew" in r.lower() for r in results))

    @patch("requests.post")
    def test_insider_trading_agent(self, mock_post):
        agent = InsiderTradingAlertAgent()
        results = agent.act()
        self.assertTrue(any("insider" in r.lower() for r in results))

    @patch("requests.post")
    def test_patent_surge_agent(self, mock_post):
        agent = PatentSurgeAgent()
        results = agent.act()
        self.assertTrue(any("patent" in r.lower() for r in results))

    @patch("requests.post")
    def test_alt_data_agent(self, mock_post):
        agent = AltDataSignalAgent()
        results = agent.act()
        self.assertTrue(any("stars" in r.lower() or "attention" in r.lower() for r in results))

    @patch("requests.post")
    def test_geo_risk_agent(self, mock_post):
        agent = GeopoliticalRiskAgent()
        results = agent.act()
        self.assertTrue(any("geo" in r.lower() or "risk" in r.lower() for r in results))

    @patch("requests.post")
    def test_energy_disruption_agent(self, mock_post):
        agent = EnergyDisruptionAgent()
        results = agent.act()
        self.assertTrue(any("grid" in r.lower() or "energy" in r.lower() for r in results))

if __name__ == '__main__':
    unittest.main()
