import sqlite3
import pandas as pd

DB_NAME = "guard_history.db"

def init_db():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS diagnostics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            tps_value REAL,
            status TEXT,
            ai_report TEXT
        )
    """)
    conn.commit()
    return conn

def save_diagnostic(conn, timestamp, tps_value, status, ai_report):
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO diagnostics (timestamp, tps_value, status, ai_report) VALUES (?, ?, ?, ?)",
        (timestamp, tps_value, status, ai_report)
    )
    conn.commit()

def load_history(conn):
    return pd.read_sql(
        "SELECT timestamp AS '시간', tps_value AS '트래픽(TPS)', status AS '상태', ai_report AS 'AI 진단 리포트' FROM diagnostics ORDER BY id DESC", 
        conn
    )
