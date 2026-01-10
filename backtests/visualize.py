from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime

import pandas as pd

from backtests.data_yahoo import fetch_daily


def load_signals(jsonl_path: str) -> pd.DataFrame:
    """Load backtest results from JSONL file."""
    rows = []
    with open(jsonl_path, "r") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return pd.DataFrame(rows)


def generate_html_overlay(
    signals_df: pd.DataFrame,
    price_data: Dict[str, pd.DataFrame],
    output_path: str = "backtests/overlay.html"
) -> str:
    """
    Generate an HTML page with price chart + signal overlay.
    Uses Chart.js for visualization.
    """
    if signals_df.empty:
        return ""
    
    signals_df["asof_dt"] = pd.to_datetime(signals_df["asof"])
    
    spy_df = price_data.get("SPY", pd.DataFrame())
    if spy_df.empty:
        return ""
    
    spy_df = spy_df.reset_index()
    
    date_col = None
    close_col = None
    for c in spy_df.columns:
        if isinstance(c, str):
            if c.lower() == 'date' or c.lower() == 'index':
                date_col = c
            elif c.lower() == 'close':
                close_col = c
    
    if date_col is None:
        date_col = spy_df.columns[0]
    if close_col is None:
        close_col = 'Close' if 'Close' in spy_df.columns else spy_df.columns[1]
    
    spy_df['date'] = pd.to_datetime(spy_df[date_col])
    spy_df['close'] = spy_df[close_col].astype(float)
    
    price_labels = spy_df['date'].dt.strftime('%Y-%m-%d').tolist()
    price_values = spy_df['close'].tolist()
    
    vix_signals = signals_df[signals_df['symbol'] == '^VIX'].copy()
    correction_signals = signals_df[signals_df['title'].str.contains('Correction', case=False, na=False)].copy()
    breadth_signals = signals_df[signals_df['title'].str.contains('Breadth', case=False, na=False)].copy()
    
    def make_annotations(df, color, label):
        annots = []
        for _, row in df.iterrows():
            annots.append({
                "type": "line",
                "xMin": row['asof'][:10],
                "xMax": row['asof'][:10],
                "borderColor": color,
                "borderWidth": 1,
                "label": {"content": label, "enabled": False}
            })
        return annots
    
    vix_dates = vix_signals['asof'].str[:10].unique().tolist()[:100]
    correction_dates = correction_signals['asof'].str[:10].unique().tolist()[:50]
    breadth_dates = breadth_signals['asof'].str[:10].unique().tolist()[:50]
    
    by_agent = signals_df.groupby('agent').size().to_dict()
    by_severity = signals_df.groupby('severity').size().to_dict()
    
    html = f'''<!DOCTYPE html>
<html>
<head>
    <title>Backtest Signal Overlay</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns"></script>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #1a1a2e; color: #eee; }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        h1 {{ color: #00d4ff; }}
        .chart-container {{ background: #16213e; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
        .stats {{ display: flex; gap: 20px; margin-bottom: 20px; }}
        .stat-box {{ background: #0f3460; padding: 15px 25px; border-radius: 8px; }}
        .stat-value {{ font-size: 24px; font-weight: bold; color: #00d4ff; }}
        .stat-label {{ color: #888; }}
        .legend {{ display: flex; gap: 20px; margin: 10px 0; }}
        .legend-item {{ display: flex; align-items: center; gap: 5px; }}
        .legend-dot {{ width: 12px; height: 12px; border-radius: 50%; }}
        table {{ width: 100%; border-collapse: collapse; background: #16213e; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #333; }}
        th {{ background: #0f3460; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Backtest Signal Overlay (2007-2026)</h1>
        
        <div class="stats">
            <div class="stat-box">
                <div class="stat-value">{len(signals_df)}</div>
                <div class="stat-label">Total Signals</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">{len(signals_df['agent'].unique())}</div>
                <div class="stat-label">Agents</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">{len(vix_signals)}</div>
                <div class="stat-label">VIX Alerts</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">{len(correction_signals)}</div>
                <div class="stat-label">Correction Signals</div>
            </div>
        </div>
        
        <div class="legend">
            <div class="legend-item"><div class="legend-dot" style="background:#ff6384"></div> VIX Signals</div>
            <div class="legend-item"><div class="legend-dot" style="background:#ffcd56"></div> Correction Signals</div>
            <div class="legend-item"><div class="legend-dot" style="background:#4bc0c0"></div> Breadth Signals</div>
        </div>
        
        <div class="chart-container">
            <canvas id="priceChart" height="400"></canvas>
        </div>
        
        <h2>Signal Breakdown</h2>
        <div class="stats">
            {"".join(f'<div class="stat-box"><div class="stat-value">{count}</div><div class="stat-label">{agent}</div></div>' for agent, count in by_agent.items())}
        </div>
        
        <h2>By Severity</h2>
        <table>
            <tr><th>Severity</th><th>Count</th></tr>
            {"".join(f'<tr><td>{sev}</td><td>{count}</td></tr>' for sev, count in sorted(by_severity.items()))}
        </table>
    </div>
    
    <script>
        const ctx = document.getElementById('priceChart').getContext('2d');
        
        const priceData = {{
            labels: {json.dumps(price_labels)},
            datasets: [{{
                label: 'SPY Price',
                data: {json.dumps(price_values)},
                borderColor: '#00d4ff',
                backgroundColor: 'rgba(0, 212, 255, 0.1)',
                fill: true,
                tension: 0.1,
                pointRadius: 0
            }}]
        }};
        
        const vixDates = {json.dumps(vix_dates)};
        const correctionDates = {json.dumps(correction_dates)};
        const breadthDates = {json.dumps(breadth_dates)};
        
        const annotations = {{}};
        
        vixDates.forEach((d, i) => {{
            annotations['vix' + i] = {{
                type: 'line',
                xMin: d,
                xMax: d,
                borderColor: 'rgba(255, 99, 132, 0.5)',
                borderWidth: 1
            }};
        }});
        
        correctionDates.forEach((d, i) => {{
            annotations['corr' + i] = {{
                type: 'line',
                xMin: d,
                xMax: d,
                borderColor: 'rgba(255, 205, 86, 0.7)',
                borderWidth: 2
            }};
        }});
        
        new Chart(ctx, {{
            type: 'line',
            data: priceData,
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                scales: {{
                    x: {{
                        type: 'category',
                        ticks: {{
                            maxTicksLimit: 20,
                            color: '#888'
                        }},
                        grid: {{ color: '#333' }}
                    }},
                    y: {{
                        ticks: {{ color: '#888' }},
                        grid: {{ color: '#333' }}
                    }}
                }},
                plugins: {{
                    legend: {{
                        labels: {{ color: '#eee' }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>'''
    
    Path(output_path).write_text(html)
    return output_path


def main():
    jsonl_path = "backtests/results_2007.jsonl"
    
    if not Path(jsonl_path).exists():
        print(f"No results file found at {jsonl_path}")
        print("Run: python backtests/run_2007.py first")
        return
    
    print("Loading signals...")
    signals_df = load_signals(jsonl_path)
    print(f"Loaded {len(signals_df)} signals")
    
    print("\nFetching price data...")
    symbols = ["SPY", "QQQ", "IWM", "DIA", "^VIX", "^TNX", "TLT"]
    price_data = fetch_daily(symbols, start="2007-01-01", end="2026-12-31")
    
    print("\nGenerating overlay HTML...")
    output = generate_html_overlay(signals_df, price_data)
    print(f"Saved: {output}")
    print("\nOpen backtests/overlay.html in a browser to view the visualization.")


if __name__ == "__main__":
    main()
