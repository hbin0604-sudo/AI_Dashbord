import sqlite3
import pandas as pd
import random

DB_NAME = "guard_history.db"

def init_db():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
        JSON 테이블 등 기본 이력 관리...
    """)
    conn.commit()
    return conn

# 기존 함수들 유지 (save_diagnostic, load_history 등)

def get_web_logs(category_name):
    """ 선택한 업무 분류(예: 전자문서 수신)에 맞는 WEB 로그 가상 데이터 생성 """
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
