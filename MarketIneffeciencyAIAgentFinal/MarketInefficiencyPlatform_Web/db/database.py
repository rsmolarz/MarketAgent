
import sqlite3
from datetime import datetime

DB_PATH = "db/findings.db"

def add_finding(finding):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO findings (title, description, severity, agent, timestamp, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (
            finding.get("title"),
            finding.get("description"),
            finding.get("severity"),
            finding.get("agent"),
            finding.get("timestamp", "now"),
            datetime.now().isoformat()
        )
    )
    conn.commit()
    conn.close()

def get_recent_findings(limit=10):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, description, severity, agent, timestamp, created_at FROM findings ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    keys = ["id", "title", "description", "severity", "agent", "timestamp", "created_at"]
    return [dict(zip(keys, row)) for row in rows]
