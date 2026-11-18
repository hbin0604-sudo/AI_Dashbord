import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

# 분리한 모듈 임포트
from database import init_db, save_diagnostic, load_history
from ai_engine import get_gemma_diagnosis

# DB 연결 초기화
conn = init_db()

# 페이지 설정
st.set_page_config(
    page_title="AIOps-Guard: 관세행정 오프라인 관제 시스템",
    page_icon="🛡️",
    layout="wide"
)

st.title("🛡️ AIOps-Guard: 관세행정 지능형 오프라인 관제 시스템")
st.markdown("---")

# 사이드바: 시스템 상태 표시
st.sidebar.header("⚙️ 시스템 인프라 현황")
st.sidebar.success("🟢 폐쇄망(On-Premise) 모드 활성화")
st.sidebar.info("🤖 Local LLM: Gemma 9B (Ollama)")
st.sidebar.warning("🔒 외부 인터넷 연결: 차단됨 (Offline)")
st.sidebar.markdown("💾 **아키텍처:** 모듈화 적용 (`app.py`, `database.py`, `ai_engine.py`)")

# 메인 지표 카드 섹션
col1, col2, col3, col4 = st.columns(4)
col1.metric("실시간 수입신고 처리량", "1,420 TPS", "+12%")
col2.metric("현재 시스템 에러율", "0.02%", "-0.01%")
col3.metric("AI 이상 탐지 상태", "정상 (Normal)", "Stability 99.8%")
col4.metric("AI 참모 응답 속도", "0.12초", "Local sLLM")

st.markdown("### 📊 실시간 트래픽 및 동적 임계치 모니터링")
st.markdown("*(공식: 3시간 이동평균 + 2 × 표준편차 기반 동적 이상 징후 감지)*")

# 시뮬레이션 데이터 생성 및 이동평균 계산
np.random.seed(42)
raw_data = np.random.randn(30) * 8 + 100
df = pd.DataFrame({'TPS': raw_data})
df['Rolling_Mean'] = df['TPS'].rolling(window=3, min_periods=1).mean()
df['Rolling_Std'] = df['TPS'].rolling(window=3, min_periods=1).std().fillna(0)
df['Dynamic_Threshold'] = df['Rolling_Mean'] + (2 * df['Rolling_Std'])

st.line_chart(df[['TPS', 'Dynamic_Threshold']])

st.markdown("---")

# AI 긴급 진단 및 조치 가이드 섹션
st.markdown("### 🤖 Gemma 9B 오프라인 AI 참모 진단 리포트")

if st.button("🚨 실시간 시스템 로그 AI 정밀 진단 실행 및 DB 기록"):
    with st.spinner("로컬 Ollama(Gemma 9B)가 폐쇄망 환경에서 로그를 분석 중입니다..."):
        
        result = get_gemma_diagnosis()
        
        if result:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # DB 모듈을 통해 안전하게 저장
            save_diagnostic(conn, current_time, 1420.0, "Warning", result)
            
            st.success("✅ AI 진단 완료 및 로컬 DB 기록 저장 완료!")
            st.markdown(f"> **[AI 진단 결과]**\n\n{result}")
        else:
            st.error("⚠️ 로컬 Ollama 서버 연결 실패: Ollama 백그라운드 실행 여부를 확인해 주세요!")

st.markdown("---")

# 하단: 과거 AI 진단 이력 조회
st.markdown("### 📜 과거 AI 진단 및 장애 대응 이력 (SQLite 저장소)")
history_df = load_history(conn)

if not history_df.empty:
    st.dataframe(history_df, use_container_width=True)
else:
    st.info("아직 기록된 진단 이력이 없습니다. 위 버튼을 눌러 첫 번째 진단을 실행해 보세요!")
