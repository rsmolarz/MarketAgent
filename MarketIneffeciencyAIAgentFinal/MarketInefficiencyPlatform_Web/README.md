# Market Inefficiency Platform (Web App)

Run as a **web app on Replit** with agents executing in paper mode.

## Quickstart (Local)
```bash
bash setup.sh
python main.py --agents all --mode realtime
```

## Quickstart (Replit Web App)
1. Create a new Python Repl.
2. Upload this project (files or zip → extract).
3. Ensure `.replit` and `replit.nix` exist (included).
4. Click **Run**. You'll get:
   - Agents running in background (paper mode)
   - Web app at the Replit URL (`/`, `/agents`, `/health`)

## Endpoints
- `/` - status JSON
- `/agents` - list registered agents
- `/health` - simple health check

## Config
Edit `config.yaml`. Use `.env` for secrets (see `.env.example`).

## Notes
This is a scaffold. Fill in real data connectors, features, signals, strategies, and backtests.
