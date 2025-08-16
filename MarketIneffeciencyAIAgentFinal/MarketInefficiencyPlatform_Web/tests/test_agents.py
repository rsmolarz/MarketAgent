
import unittest
from unittest.mock import patch, MagicMock
from agents.arbitrage_finder import ArbitrageFinderAgent
from agents.macro_watcher import MacroWatcherAgent

class TestArbitrageFinderAgent(unittest.TestCase):
    @patch("ccxt.binance")
    @patch("ccxt.coinbase")
    @patch("ccxt.kraken")
    def test_arbitrage_act(self, mock_kraken, mock_coinbase, mock_binance):
        agent = ArbitrageFinderAgent()

        # Mock exchange price data
        for mock_exchange in [mock_binance, mock_coinbase, mock_kraken]:
            instance = MagicMock()
            instance.fetch_ticker.return_value = {'last': 10000 + 1000 * mock_exchange.__name__.count('o')}
            mock_exchange.return_value = instance

        results = agent.act()
        self.assertIsInstance(results, list)
        self.assertTrue(any('spread_percent' in r for r in results), "No arbitrage opportunities detected")

class TestMacroWatcherAgent(unittest.TestCase):
    def test_macro_act(self):
        agent = MacroWatcherAgent()

        with patch("requests.post") as mock_post:
            alerts = agent.act()
            self.assertIsInstance(alerts, list)
            self.assertGreaterEqual(len(alerts), 1)
            self.assertTrue(any("GDP" in a or "sentiment" in a for a in alerts))

if __name__ == '__main__':
    unittest.main()
