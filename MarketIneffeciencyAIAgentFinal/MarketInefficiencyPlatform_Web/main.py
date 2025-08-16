import argparse
from agents import AgentRegistry
from core.config import load_config

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--agents', nargs='+', default=['all'])
    parser.add_argument('--mode', default='realtime', choices=['realtime','backtest'])
    args = parser.parse_args()

    config = load_config('config.yaml')
    print("Market Inefficiencies Platform initialized.")
    print(f"Mode: {args.mode}")
    enabled = config.get("agents",{}).get("enabled",[])
    print(f"Config enabled agents: {enabled}")
    AgentRegistry.load_and_run_agents(args.agents, args.mode)

if __name__ == '__main__':
    main()
