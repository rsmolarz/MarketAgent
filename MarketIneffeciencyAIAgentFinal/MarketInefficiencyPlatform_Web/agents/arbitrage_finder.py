
import ccxt
import requests
from agents import BaseAgent, AgentRegistry

class ArbitrageFinderAgent(BaseAgent):
    name = "ArbitrageFinderAgent"
    api_url = "http://localhost:5000/findings"

    def plan(self):
        return "Scan for arbitrage opportunities across multiple exchanges using BTC/USDT price."

    def act(self, context=None):
        exchanges = ['binance', 'coinbase', 'kraken']
        prices = {}

        for ex_id in exchanges:
            try:
                exchange_class = getattr(ccxt, ex_id)
                exchange = exchange_class()
                ticker = exchange.fetch_ticker('BTC/USDT')
                prices[ex_id] = ticker['last']
            except Exception as e:
                print(f"[{self.name}] Failed to fetch from {ex_id}: {e}")

        opportunities = []
        for ex1 in prices:
            for ex2 in prices:
                if ex1 != ex2:
                    spread = (prices[ex2] - prices[ex1]) / prices[ex1] * 100
                    if spread > 1:
                        opportunity = {
                            'buy_from': ex1,
                            'sell_to': ex2,
                            'buy_price': prices[ex1],
                            'sell_price': prices[ex2],
                            'spread_percent': round(spread, 2)
                        }
                        opportunities.append(opportunity)

                        # Submit finding to API
                        finding = {
                            "title": "Arbitrage Opportunity",
                            "description": f"Buy from {ex1} at {prices[ex1]:.2f}, sell to {ex2} at {prices[ex2]:.2f} — spread {spread:.2f}%",
                            "severity": "high",
                            "agent": self.name,
                            "timestamp": "now"
                        }
                        try:
                            requests.post(self.api_url, json=finding)
                        except Exception as post_err:
                            print(f"[{self.name}] Failed to post to API: {post_err}")

        return opportunities

    def reflect(self, result=None):
        return f"Posted {len(result)} arbitrage opportunities." if result else "No opportunities found."

    def run(self, mode="realtime"):
        print(f"[{self.name}] running in {mode} mode")
        print(self.plan())
        result = self.act()
        print(self.reflect(result))

AgentRegistry.register(ArbitrageFinderAgent())
