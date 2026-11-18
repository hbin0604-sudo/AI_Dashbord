import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

from database import init_db, save_diagnostic, load_history, get_web_logs
from ai_engine import ask_ai_bot, push_log_to_github

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
if "detected_incident" not in st.session_state:
    st.session_state.detected_incident = None

if "live_logs" not in st.session_state:
    st.session_state.live_logs = [
        {"time": "03:10:12", "ip": "124.105.21.9", "method": "GET", "url": "/index.do", "status": 200},
        {"time": "03:10:15", "ip": "124.105.21.9", "method": "POST", "url": "/customs/search.do", "status": 200},
    ]

# 📌 우측 하단 동그란 노란색 "AI 챗봇" 플로팅 버튼 고정 CSS
st.markdown("""
<style>
div[data-testid="stPopover"] {
    position: fixed !important;
    bottom: 30px !important;
    right: 30px !important;
    top: auto !important;
    left: auto !important;
    z-index: 99999999 !important;
    width: auto !important;
    max-width: none !important;
}

div[data-testid="stPopover"] > div {
    width: auto !important;
    max-width: none !important;
}

div[data-testid="stPopover"] > button,
div[data-testid="stPopover"] button {
    width: 70px !important;
    height: 70px !important;
    min-width: 70px !important;
    min-height: 70px !important;
    max-width: 70px !important;
    max-height: 70px !important;
    border-radius: 50% !important;
    background-color: #FFD54F !important;
    color: #333333 !important;
    font-weight: bold !important;
    font-size: 13px !important;
    box-shadow: 0px 8px 25px rgba(0,0,0,0.5) !important;
    border: 3px solid #FFC107 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    padding: 0px !important;
    text-align: center !important;
    white-space: pre-wrap !important;
    line-height: 1.2 !important;
    flex: none !important;
}

div[data-testid="stPopover"] > button:hover {
    background-color: #FFC107 !important;
    transform: scale(1.08);
}
</style>
""", unsafe_allow_html=True)

# 📌 사이드바 네비게이션 메뉴 (관제 로그 메뉴 분리 추가)
st.sidebar.header("🧭 관세청 AIOps 메뉴")
menu = st.sidebar.radio(
    "이동할 메뉴를 선택하세요:",
    [
        "통합 모니터링 대시보드", 
        "인프라 자원", 
        "관세행정 서비스 품질",
        "실시간 로그 스트림 및 관제"
    ]
)

st.sidebar.markdown("---")
st.sidebar.success("🟢 하이브리드(Cloud AI) 모드")
st.sidebar.info("🤖 Cloud LLM: GPT-4o-mini")

# ==========================================
# 🔍 [백그라운드 엔진] 로그 스캐너 및 침해사고 자동 감지
# ==========================================
def scan_logs_for_threats():
    for log in st.session_state.live_logs:
        url_str = str(log.get("url", ""))
        if "/etc/passwd" in url_str or "passwd" in url_str:
            return log
    return None

current_threat = scan_logs_for_threats()
if current_threat and not st.session_state.detected_incident:
    st.session_state.detected_incident = current_threat

# 공통 침해사고 자동 감지 팝업 (어떤 화면에 있든 발동)
if st.session_state.detected_incident:
    @st.dialog("🚨 [CRITICAL] 시스템 무단 접근(침해사고) 자동 탐지됨", width="large")
    def show_auto_incident_dialog(threat):
        st.error(f"⚠️ **실시간 로그 스트림 분석 중 중요 침해 패턴이 감지되었습니다!**\n\n- **탐지 시간:** {threat['time']}\n- **공격자 IP:** {threat['ip']}\n- **대상 경로:** `{threat['url']}`")
        
        with st.spinner("🚀 클라우드 AI가 실시간으로 침해 로그를 분석하고 방어 가이드를 생성 중입니다..."):
            prompt = f"보안 침해 사고 감지: 공격자 IP {threat['ip']}가 다음 경로로 시스템 파일에 접근했습니다: {threat['url']}. 1) 공격 위협도 평가, 2) 긴급 차단 조치 가이드를 3줄 이내로 요약해줘."
            ai_report = ask_ai_bot(prompt)

        st.markdown(f"> **[클라우드 AI 참모 긴급 진단 결과]**\n\n{ai_report}")
        
        st.markdown("---")
        with st.spinner("🚀 GitHub 레포지토리(AI_Dashbord)에 탐지 로그 자동 백업 중..."):
            github_res = push_log_to_github(f"침해사고 탐지 - {threat['url']}", ai_report)
            st.info(github_res)

        if st.button("🚨 상황 확인 완료 및 경보 해제"):
            st.session_state.live_logs = [l for l in st.session_state.live_logs if l != threat]
            st.session_state.detected_incident = None
            st.rerun()

    show_auto_incident_dialog(st.session_state.detected_incident)


# ==========================================
# 1. 통합 모니터링 대시보드 메뉴 (원래 디자인 완벽 유지)
# ==========================================
if menu == "통합 모니터링 대시보드":
    st.title("🛡️ 통합 모니터링 대시보드")
    st.markdown("---")

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
    c2.metric("클라우드 AI 연동", "GPT-4o-mini 탑재", "응답속도 초고속")
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
# 3. 관세행정 서비스 품질 메뉴
# ==========================================
elif menu == "관세행정 서비스 품질":
    st.title("📈 관세행정 서비스 품질 및 업무량 분석")
    st.markdown("---")
    
    st.markdown("### 🕒 시간대별 수입/수출 신고 처리 서비스 품질 현황")
    time_data = pd.DataFrame(
        np.random.randint(100, 500, size=(24, 2)),
        columns=["수입신고 건수", "수출신고 건수"],
        index=[f"{i:02d}:00" for i in range(24)]
    )
    st.bar_chart(time_data)

# ==========================================
# 4. 실시간 로그 스트림 및 관제 메뉴 (시뮬레이터 분리)
# ==========================================
elif menu == "실시간 로그 스트림 및 관제":
    st.title("📡 실시간 웹 로그 스트림 및 침해사고 모의 관제")
    st.markdown("---")
    st.info("💡 이곳에서 임의의 공격 로그(예: `/etc/passwd` 탈취 시도)를 주입하면, 백그라운드 스캐너가 즉시 감지하여 긴급 팝업과 GitHub 백업을 트리거합니다.")

    with st.expander("🛠️ 실시간 웹 로그 임의 인입 시뮬레이터", expanded=True):
        col_a, col_b = st.columns(2)
        with col_a:
            test_ip = st.text_input("공격자 IP 입력", value="211.234.110.55")
            test_url = st.text_input("요청 URL/Parameter 입력", value="/cgi-bin/vulnerable.cgi?file=/etc/passwd")
        with col_b:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("📥 이 로그를 시스템 로그 스트림에 주입하기"):
                new_log = {
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "ip": test_ip,
                    "method": "GET",
                    "url": test_url,
                    "status": 403
                }
                st.session_state.live_logs.insert(0, new_log)
                st.success("✅ 로그 주입 완료! 상단 및 백그라운드 AI 엔진이 즉시 위협을 탐지합니다.")
                st.rerun()

    st.markdown("### 📋 실시간 유입 웹 로그 스트림 (Access Log)")
    log_stream_df = pd.DataFrame(st.session_state.live_logs)
    st.dataframe(log_stream_df, use_container_width=True)


# ==========================================
# 🤖 우측 하단 동그란 노란색 "AI 챗봇" 플로팅 버튼 팝업 (모든 화면 공통)
# ==========================================
with st.popover("AI\n챗봇"):
    st.markdown("### 💬 클라우드 AI 인프라 참모")
    st.caption("초고속 클라우드 LLM 기반 실시간 응답")
    
    floating_chat_box = st.container(height=210)
    with floating_chat_box:
        if not st.session_state.chat_history:
            st.info("궁금한 점을 바로 물어보세요!")
        for role, msg in st.session_state.chat_history:
            if role == "user":
                st.markdown(f"**나:** {msg}")
            else:
                st.markdown(f"**AI:** {msg}")

    float_input = st.text_input("빠른 질문 입력...", key="floating_bot_input")
    if st.button("보내기", key="floating_bot_send"):
        if float_input:
            st.session_state.chat_history.append(("user", float_input))
            with st.spinner("클라우드 AI 응답 생성 중..."):
                reply = ask_ai_bot(float_input)
                st.session_state.chat_history.append(("assistant", reply))
            st.rerun()

    st.markdown("---")
    if st.button("🚀 탐지 로그 GitHub 백업"):
        with st.spinner("GitHub 레포지토리에 로그 기록 중..."):
            last_msg = st.session_state.chat_history[-1][1] if st.session_state.chat_history else "초기 시스템 정상 가동 상태"
            res_msg = push_log_to_github("AIOps 수동 진단 및 챗봇 로그 백업", last_msg)
            st.info(res_msg)
