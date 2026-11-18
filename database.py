import sqlite3
import pandas as pd
import random

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
    """ AI 진단 결과 및 로그를 SQLite DB에 영구 저장하는 함수 """
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO diagnostics (timestamp, tps_value, status, ai_report) VALUES (?, ?, ?, ?)",
        (timestamp, tps_value, status, ai_report)
    )
    conn.commit()

def load_history(conn):
    """ 과거 AI 진단 이력을 DataFrame 형태로 조회하는 함수 """
    return pd.read_sql(
        "SELECT timestamp AS '시간', tps_value AS '트래픽(TPS)', status AS '상태', ai_report AS 'AI 진단 리포트' FROM diagnostics ORDER BY id DESC", 
        conn
    )

def get_web_logs(category_name):
    """ 선택한 업무 분류에 맞는 유니패스 WEB 로그 가상 데이터 생성 함수 """
    countries = ["필리핀(마닐라)", "인도네시아", "도미니카공화국", "베네수엘라", "러시아", "콜롬비아", "미국", "페루"]
    ips = [f"124.105.{random.randint(1,255)}.{random.randint(1,255)}" for _ in range(15)]
    
    data = []
    for i in range(1, 16):
        data.append({
            "no": 100 - i,
            "date": "2026년 11월 5일 목요일",
            "time": f"03:{(i*2):02d}:{i:02d}",
            "IP": random.choice(ips),
            "국가": random.choice(countries),
            "method": "POST",
            "Parameter": f"trmFilePathNm=3e5/dircsp/FilePathNiend/c_{category_name}"
        })
    return pd.DataFrame(data)
