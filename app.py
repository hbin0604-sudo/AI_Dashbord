import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

from database import init_db, save_diagnostic, load_history, get_web_logs
from ai_engine import get_gemma_diagnosis, ask_ai_bot

conn = init_db()

st.set_page_config(
    page_title="AIOps-Guard: 관세행정 오프라인 관제 시스템",
    page_icon="🛡️",
    layout="wide"
)

# 세션 상태 초기화 (챗봇 대화 및 팝업 제어용)
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "selected_log_category" not in st.session_state:
    st.session_state.selected_log_category = None

st.title("🛡️ 통합 모니터링 대시보드")
st.markdown("---")

# 상단 지표 카드
col1, col2, col3, col4 = st.columns(4)
col1.metric("💚 시스템 Health", "98점", "↑ 최상")
col2.metric("💻 서버 CPU", "62%", "↓ -3%")
col3.metric("📈 수입신고 처리건수", "2,458", "↑ 5%")
col4.metric("📄 전자문서 송수신", "6,254", "↑ 2%")

st.markdown("### 🏢 관세행정 업무 처리 현황")

# 업무 분류 데이터 (클릭 인터랙션을 위해 데이터프레임 또는 버튼 활용)
work_data = [
    {"업무 분류": "전자문서 수신", "처리 건수": "3,254", "상태": "🟢 정상"},
    {"업무 분류": "수입신고서 처리", "처리 건수": "2,981", "상태": "🟢 정상"},
    {"업무 분류": "사전검증 처리", "처리 건수": "1,876", "상태": "🟢 정상"},
    {"업무 분류": "신고서 접수통보", "처리 건수": "1,203", "상태": "🟢 정상"},
    {"업무 분류": "고지서 생성", "처리 건수": "987", "상태": "🟢 정상"},
    {"업무 분류": "전산선별", "처리 건수": "856", "상태": "🟢 정상"},
]

# 표와 클릭 버튼 연동을 위한 UI 구성
cols = st.columns([2, 1, 1])
cols[0].markdown("**업무 분류**")
cols[1].markdown("**처리 건수**")
cols[2].markdown("**상태**")

for row in work_data:
    c1, c2, c3 = st.columns([2, 1, 1])
    # 업무 분류를 버튼 형태로 만들어 클릭 시 WEB Log 팝업 호출
    if c1.button(row["업무 분류"], key=f"btn_{row['업무 분류']}"):
        st.session_state.selected_log_category = row["업무 분류"]
    c2.text(row["처리 건수"])
    c3.text(row["상태"])

# 📌 WEB Log 상세 팝업 (두 번째 사진 구현)
if st.session_state.selected_log_category:
    @st.dialog(f"유니패스 WEB Log - [{st.session_state.selected_log_category}] 상세", width="large")
    def show_web_log_popup(category):
        st.markdown(f"### CSP WEB /log/ssw/httpsvr/csp/ssl_access_log")
        log_df = get_web_logs(category)
        st.dataframe(log_df, use_container_width=True)
        if st.button("닫기"):
            st.session_state.selected_log_category = None
            st.rerun()

    show_web_log_popup(st.session_state.selected_log_category)

st.markdown("---")

# 🤖 우측 하단 고정형 AI Bot 플로팅 버튼 및 챗봇 팝업 구현
st.markdown("""
    <style>
    /* 우측 하단 고정 버튼 스타일 */
    .chat-bot-container {
        position: fixed;
        bottom: 30px;
        right: 30px;
        z-index: 99999;
    }
    </style>
""", unsafe_allow_html=True)

# Streamlit popover를 활용한 AI Bot 챗봇 인터페이스 (화면 우측 하단 고정 효과)
with st.popover("🤖 AI Bot"):
    st.markdown("### 💬 Local Gemma 9B AI 어시스턴트")
    st.caption("폐쇄망 내부망 전용 실시간 질의응답 챗봇")
    
    # 대화 이력 출력
    chat_container = st.container(height=300)
    with chat_container:
        for role, message in st.session_state.chat_history:
            if role == "user":
                st.markdown(f"**나:** {message}")
            else:
                st.markdown(f"**AI 참모:** {message}")

    # 사용자 질의 입력창
    user_input = st.text_input("AI에게 질문을 입력하세요...", key="ai_bot_input")
    if st.button("전송", key="ai_bot_send"):
        if user_input:
            st.session_state.chat_history.append(("user", user_input))
            with st.spinner("Gemma가 답변 생성 중..."):
                ai_response = ask_ai_bot(user_input)
                st.session_state.chat_history.append(("assistant", ai_response))
            st.rerun()
