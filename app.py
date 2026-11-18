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

# 세션 상태 초기화
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "selected_log_category" not in st.session_state:
    st.session_state.selected_log_category = None

# 📌 사이드바 네비게이션 메뉴 (요청하신 4개 메뉴 구성)
st.sidebar.header("🧭 관세청 AIOps 메뉴")
menu = st.sidebar.radio(
    "이동할 메뉴를 선택하세요:",
    [
        "통합 모니터링 대시보드", 
        "인프라 자원", 
        "관세행정업무량", 
        "AI 실시간 진단 챗봇"
    ]
)

st.sidebar.markdown("---")
st.sidebar.success("🟢 폐쇄망(On-Premise) 모드")
st.sidebar.info("🤖 Local LLM: Gemma 9B (Ollama)")

# ==========================================
# 1. 통합 모니터링 대시보드 메뉴
# ==========================================
if menu == "통합 모니터링 대시보드":
    st.title("🛡️ 통합 모니터링 대시보드")
    st.markdown("---")

    # 상단 지표 카드 (사진 1 참고)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("💚 시스템 Health", "98점", "↑ 최상")
    col2.metric("💻 서버 CPU", "62%", "↓ -3%")
    col3.metric("📈 수입신고 처리건수", "2,458", "↑ 5%")
    col4.metric("📄 전자문서 송수신", "6,254", "↑ 2%")

    st.markdown("---")
    
    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.markdown("### 🏢 관세행정 업무 처리 현황")
        work_data = [
            {"업무 분류": "전자문서 수신", "처리 건수": "3,254", "상태": "🟢 정상"},
            {"업무 분류": "수입신고서 처리", "처리 건수": "2,981", "상태": "🟢 정상"},
            {"업무 분류": "사전검증 처리", "처리 건수": "1,876", "상태": "🟢 정상"},
            {"업무 분류": "신고서 접수통보", "처리 건수": "1,203", "상태": "🟢 정상"},
            {"업무 분류": "고지서 생성", "처리 건수": "987", "상태": "🟢 정상"},
            {"업무 분류": "전산선별", "처리 건수": "856", "상태": "🟢 정상"},
        ]

        # 테이블 헤더
        cols = st.columns([2, 1, 1])
        cols[0].markdown("**업무 분류**")
        cols[1].markdown("**처리 건수**")
        cols[2].markdown("**상태**")

        for row in work_data:
            c1, c2, c3 = st.columns([2, 1, 1])
            if c1.button(row["업무 분류"], key=f"btn_{row['업무 분류']}"):
                st.session_state.selected_log_category = row["업무 분류"]
            c2.text(row["처리 건수"])
            c3.text(row["상태"])

    with col_right:
        st.markdown("### 📊 실시간 트래픽 추이 및 AI 예측선")
        np.random.seed(42)
        chart_data = pd.DataFrame(
            np.random.randn(20, 2) * 5 + [100, 20],
            columns=['수입신고(건)', 'AI_예측상한선']
        )
        st.line_chart(chart_data)

    # WEB Log 팝업 모달 처리
    if st.session_state.selected_log_category:
        @st.dialog(f"유니패스 WEB Log - [{st.session_state.selected_log_category}] 상세", width="large")
        def show_web_log_popup(category):
            st.markdown(f"### CSP WEB /log/ssw/httpsvr/csp/ssl_access_log")
            log_df = get_web_logs(category)
            st.dataframe(log_df, use_container_width=True)
            if st.button("닫기 팝업"):
                st.session_state.selected_log_category = None
                st.rerun()
        show_web_log_popup(st.session_state.selected_log_category)

# ==========================================
# 2. 인프라 자원 메뉴
# ==========================================
elif menu == "인프라 자원":
    st.title("💻 인프라 자원 관리 (Infra Resources)")
    st.markdown("---")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("WAS 서버 클러스터", "8대 가동중", "CPU 평균 58%")
    c2.metric("Ollama 로컬 컨테이너", "Gemma 9B 탑재", "VRAM 사용량 6.4GB")
    c3.metric("SQLite DB 저장소", "정상 작동", "용량 24.5MB")

    st.markdown("### ⚙️ 시스템 노드별 자원 점유율")
    resource_df = pd.DataFrame({
        "노드명": ["WAS-Node-01", "WAS-Node-02", "DB-Node-01", "AI-Inference-Node"],
        "CPU 사용률 (%)": [65, 58, 42, 88],
        "메모리 사용률 (%)": [72, 70, 55, 91],
        "네트워크 트래픽": ["1.2 GB/s", "1.1 GB/s", "450 MB/s", "2.4 GB/s"]
    })
    st.dataframe(resource_df, use_container_width=True)

# ==========================================
# 3. 관세행정업무량 메뉴
# ==========================================
elif menu == "관세행정업무량":
    st.title("📈 관세행정 업무량 통계 및 분석")
    st.markdown("---")
    
    st.markdown("### 🕒 시간대별 수입/수출 신고 건수 분석")
    time_data = pd.DataFrame(
        np.random.randint(100, 500, size=(24, 2)),
        columns=["수입신고 건수", "수출신고 건수"],
        index=[f"{i:02d}:00" for i in range(24)]
    )
    st.bar_chart(time_data)

# ==========================================
# 4. AI 실시간 진단 챗봇 메뉴
# ==========================================
elif menu == "AI 실시간 진단 챗봇":
    st.title("🤖 AI 실시간 진단 챗봇 (Gemma 9B)")
    st.markdown("---")
    st.caption("외부망이 완전히 차단된 로컬 폐쇄망 환경에서 동작하는 관세청 전용 AI 수석 참모입니다.")

    # 채팅 기록 출력 영역
    chat_box = st.container(height=450)
    with chat_box:
        if not st.session_state.chat_history:
            st.info("👋 안녕하세요! 관세청 인프라 관련 질문이나 로그 분석 요청을 남겨주세요.")
        for role, msg in st.session_state.chat_history:
            if role == "user":
                st.markdown(f"**👤 사용자:** {msg}")
            else:
                st.markdown(f"**🤖 AI 참모:** {msg}")

    # 입력 폼
    with st.form(key="chat_form", clear_on_submit=True):
        user_text = st.text_input("메시지를 입력하세요 (예: 현재 수입신고 지연 원인 분석해줘)")
        submit_btn = st.form_submit_button("전송하기")
        
        if submit_btn and user_text:
            st.session_state.chat_history.append(("user", user_text))
            with st.spinner("로컬 Gemma 9B가 답변을 추론 중입니다..."):
                reply = ask_ai_bot(user_text)
                st.session_state.chat_history.append(("assistant", reply))
            st.rerun()
