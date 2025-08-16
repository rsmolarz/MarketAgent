# 🚀 Deploying Market Inefficiency Platform on Render

Follow these steps to deploy your project publicly using Render:

## 1. Push Code to GitHub
Create a new GitHub repo and push the project files (including `render.yaml` and `requirements.txt`).

## 2. Sign Up for Render
Visit https://render.com and sign up (free).

## 3. Create New Web Service
- Click **"New +" > Web Service**
- Connect your GitHub repo
- Choose the repo with this project
- Render will detect `render.yaml` and configure it automatically

## 4. Wait for Build & Deployment
Render will:
- Install dependencies via `pip install -r requirements.txt`
- Start your app with `uvicorn ui.server:app`

## 5. Access Your App
Once deployed, you’ll get a public URL like:

```
https://market-inefficiency-platform.onrender.com
```

You can visit `/dashboard` or `/` to view the Plotly dashboard.

---

## ✅ Notes

- SQLite storage is ephemeral on free tier — use PostgreSQL if needed.
- Make sure you commit all key directories (`ui/`, `agents/`, `db/`, `notifiers/`).

Enjoy your deployment!