import streamlit as st
import pandas as pd
import numpy as np
import time

# 1. 페이지 설정 및 한 화면 압축용 커스텀 CSS 주입
st.set_page_config(page_title="관세행정 AI 모니터링", layout="wide", initial_sidebar_state="expanded")
st.markdown("""
    <style>
    .block-container { padding-top: 1.2rem; padding-bottom: 1.2rem; }
    h1 { font-size: 1.4rem !important; margin-bottom: 0rem !important; }
    h2 { font-size: 1.1rem !important; margin-bottom: 0rem !important; }
    h3 { font-size: 0.95rem !important; margin-bottom: 0rem !important; }
    p, div, span, label { font-size: 0.85rem !important; }
    div[data-testid="metric-container"] { margin-bottom: -15px !important; }
    hr { margin: 0.5em 0 !important; }
    </style>
""", unsafe_allow_html=True)

# 2. 긴급 장애 팝업(다이얼로그) 함수 정의
@st.dialog("🚨 [긴급 경보] 시스템 이상 감지")
def alert_popup():
    st.error("**[CRITICAL] 수입신고서 트래픽 폭증 발생!**")
    st.markdown("""
    * **발생 시간:** 09:00
    * **현상:** 트래픽이 AI 예측 상한선을 대폭 초과했으며, 전체 CPU 점유율이 89%까지 치솟았습니다.
    * **요청:** 대시보드 하단의 **'AI 종합 진단 리포트'** 버튼을 눌러 즉각적인 조치 가이드를 확인하십시오.
    """)
    if st.button("확인 및 모니터링 계속하기"):
        st.rerun()

# 팝업 1회 실행을 위한 세션 상태 초기화
if "prev_simulate_error" not in st.session_state:
    st.session_state.prev_simulate_error = False
if "trigger_popup" not in st.session_state:
    st.session_state.trigger_popup = False

hours = [f"{i:02d}:00" for i in range(24)]

# 3. 사이드바 메뉴 설정
with st.sidebar:
    st.markdown("<h3 style='text-align: center;'>🏛️ AIOps-Guard</h3>", unsafe_allow_html=True)
    st.divider()
    
    menu = st.radio(
        "메뉴 이동", 
        [
            "🏠 통합 모니터링 대시보드", 
            "🖥️ 인프라 자원", 
            "📄 관세 행정 업무량", 
            "⚙️ 서비스 품질(SLA)", 
            "📊 사업 검증 데이터", 
            "📋 종합 보고서",
            "🤖 AI 실시간 진단 챗봇"
        ]
    )
    
    st.divider()
    st.markdown("### ⚠️ 발표용 AI 시뮬레이터")
    simulate_error = st.toggle("🚨 [09:00] 트래픽 폭증 발생")
    st.caption("AI 시뮬레이터 제어 스위치")

# 스위치가 켜지는 순간(False->True) 딱 1번만 팝업 트리거 활성화
if simulate_error and not st.session_state.prev_simulate_error:
    st.session_state.trigger_popup = True
    
st.session_state.prev_simulate_error = simulate_error

if st.session_state.trigger_popup:
    alert_popup()
    # 팝업 호출 직후 트리거를 해제하여 채팅 입력 등 화면 갱신 시 재호출 완벽 차단
    st.session_state.trigger_popup = False

# ==========================================
# 탭 1: 통합 모니터링 대시보드
# ==========================================
if menu == "🏠 통합 모니터링 대시보드":
    col_title, col_date = st.columns([5, 1])
    with col_title: st.title("통합 모니터링 대시보드")
    with col_date: st.markdown("<div style='text-align: right; color: gray;'>2026.10.23</div>", unsafe_allow_html=True)
    
    col_health, col1, col2, col3 = st.columns(4)
    with col_health: st.metric("💚 시스템 Health", f"{42 if simulate_error else 98}점", "-56점" if simulate_error else "최상", help="AI가 산출한 종합 건강도")
    with col1: st.metric("🖥️ 서버 CPU", "89%" if simulate_error else "62%", "27%" if simulate_error else "-3%")
    with col2: st.metric("🔄 수입신고 처리건수", "8,512" if simulate_error else "2,458", "85%" if simulate_error else "5%")
    with col3: st.metric("📨 전자문서 송수신", "12,850" if simulate_error else "6,254", "105%" if simulate_error else "2%")
    
    st.divider()

    base_traffic = [5, 5, 4, 3, 5, 8, 15, 25, 40, 50, 45, 40, 35, 40, 45, 30, 25, 20, 15, 12, 10, 8, 6, 5]
    if simulate_error: base_traffic[9] = 180 

    df_line = pd.DataFrame({"시간": hours, "수입신고(건)": base_traffic}).set_index("시간")
    df_line['AI_예측상한선'] = df_line['수입신고(건)'].rolling(3, min_periods=1).mean() + (df_line['수입신고(건)'].rolling(3, min_periods=1).std().fillna(0) * 2)

    chart_col1, chart_col2 = st.columns([6, 4])
    with chart_col1:
        st.subheader("📈 실시간 트래픽 추이 및 AI 예측선", help="수학적 시계열 모델 기반 동적 임계치")
        st.line_chart(df_line[['수입신고(건)', 'AI_예측상한선']], height=180)
        
        with st.expander("ℹ️ AI 예측 모델 산출 기준 상세히 보기"):
            st.markdown("""
            **[수학적 시계열 모델 기반 동적 임계치]**
            - **산출 공식:** `과거 3시간 이동평균 + (과거 3시간 표준편차 × 2)`
            - **도입 효과:** 일시적인 데이터 스파이크와 실제 장애를 구분하여 오탐지를 줄입니다.
            """)
            
    with chart_col2:
        st.subheader("📋 관세행정 업무 처리 현황")
        df_table = pd.DataFrame({
            "업무 분류": ["전자문서 수신", "수입신고서 처리", "사전검증 처리", "신고서 접수통보", "고지서 생성", "전산선별"],
            "처리 건수": ["3,254", "8,512" if simulate_error else "2,981", "1,876", "1,203", "987", "856"],
            "상태": ["🟢 정상", "🔴 폭증" if simulate_error else "🟢 정상", "🟢 정상", "🟢 정상", "🟢 정상", "🟢 정상"]
        })
        st.dataframe(df_table, hide_index=True, use_container_width=True)

    log_col, report_col = st.columns([5, 5])
    with log_col:
        st.subheader("🚨 실시간 AI 탐지 로그")
        log_data = pd.DataFrame({
            "시간": ["09:05", "09:02", "08:50"],
            "레벨": ["CRITICAL", "WARNING", "INFO"] if simulate_error else ["INFO", "INFO", "INFO"],
            "이벤트": ["수입신고서 DB Connection Timeout", "EDI WAS 임계치 80% 초과", "사전검증 정기 Batch 대기"]
        })
        st.dataframe(log_data, hide_index=True, use_container_width=True)

    with report_col:
        st.subheader("🤖 AI 종합 진단 리포트 (시뮬레이터)")
        if st.button("✨ 리포트 생성 (내부 엔진)"):
            with st.spinner("임시 시뮬레이터가 지표를 분석 중입니다..."):
                time.sleep(1.5)
                if simulate_error:
                    st.error("**[🚨 긴급 조치 권고]** 09:00 기준 수입신고서 트래픽이 예측치를 대폭 초과했습니다. 사전검증 배치를 야간으로 연기하고, EDI WAS 서버 증설을 즉시 승인해 주십시오.")
                else:
                    st.success("**[✅ 정상 가동 진단]** 모든 자원 및 비즈니스 트랜잭션이 AI가 예측한 정상 오차 범위 안에서 원활하게 작동 중입니다.")

# ==========================================
# 탭 2: 인프라 자원
# ==========================================
elif menu == "🖥️ 인프라 자원":
    st.title("🖥️ 인프라 자원 상세 모니터링")
    st.caption("서버별 임계치 예측 및 선제적 인프라 증설 검토 지표")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("WEB (Socket)", "85%")
    with col2: st.metric("WAS (FD)", "42%" if simulate_error else "78%", "-36%" if simulate_error else "1%")
    with col3: st.metric("DB (Connection)", "99%" if simulate_error else "45%", "54%" if simulate_error else "-2%")
    with col4: st.metric("GPFS 사용률", "61%")
    
    st.divider()
    
    infra_row1_col1, infra_row1_col2 = st.columns(2)
    infra_row2_col1, infra_row2_col2 = st.columns(2)
    
    cpu_data = np.random.randint(20, 50, size=24)
    mem_data = np.random.randint(40, 60, size=24)
    db_conn = np.random.randint(10, 30, size=24)
    net_io = np.random.randint(100, 300, size=24)
    if simulate_error: 
        cpu_data[9] = 95; mem_data[9] = 90; db_conn[9] = 150; net_io[9] = 1200
        
    df_infra = pd.DataFrame({"시간": hours, "CPU(%)": cpu_data, "Memory(%)": mem_data, "DB_Conn": db_conn, "Net_IO(Mbps)": net_io}).set_index("시간")

    with infra_row1_col1:
        st.subheader("1. 서버 CPU 사용률 (Area)")
        st.area_chart(df_infra[['CPU(%)']], height=200)
    with infra_row1_col2:
        st.subheader("2. 메모리 사용률 (Line)")
        st.line_chart(df_infra[['Memory(%)']], height=200, color="#FF4B4B")
    with infra_row2_col1:
        st.subheader("3. DB Connection 활성 수 (Bar)")
        st.bar_chart(df_infra[['DB_Conn']], height=200, color="#0068C9")
    with infra_row2_col2:
        st.subheader("4. 네트워크 I/O 트래픽 (Area)")
        st.area_chart(df_infra[['Net_IO(Mbps)']], height=200, color="#29B09D")

# ==========================================
# 탭 3: 관세 행정 업무량
# ==========================================
elif menu == "📄 관세 행정 업무량":
    st.title("📄 관세 행정 업무량 (비즈니스 트랜잭션)")
    st.caption("주요 관세 행정 업무량 실시간 병목 및 밀도 분석")
    st.divider()

    biz_row1_col1, biz_row1_col2 = st.columns(2)
    biz_row2_col1, biz_row2_col2 = st.columns(2)

    with biz_row1_col1:
        st.subheader("1. 단위 업무별 처리 소요시간 (Scatter)")
        scatter_data = pd.DataFrame({
            "시간대": np.random.choice(hours, 100),
            "처리시간(ms)": np.random.randint(10, 500, 100),
            "업무유형": np.random.choice(["전자문서 수신", "사전검증 처리", "고지생성", "전산선별"], 100)
        })
        if simulate_error:
            error_scatter = pd.DataFrame({"시간대": ["09:00"] * 30, "처리시간(ms)": np.random.randint(2000, 5000, 30), "업무유형": ["수입신고서 처리"] * 30})
            scatter_data = pd.concat([scatter_data, error_scatter])
        st.scatter_chart(scatter_data, x="시간대", y="처리시간(ms)", color="업무유형", height=200)

    with biz_row1_col2:
        st.subheader("2. 시간대별 대기열(Queue) 길이 (Line)")
        queue_data = np.random.randint(0, 5, size=24)
        if simulate_error: queue_data[9] = 120
        df_queue = pd.DataFrame({"시간": hours, "대기열 건수": queue_data}).set_index("시간")
        st.line_chart(df_queue, height=200, color="#FF8700")

    with biz_row2_col1:
        st.subheader("3. 실시간 업무 접속 세션 수 (Area)")
        session_data = np.random.randint(500, 1000, size=24)
        if simulate_error: session_data[9] = 4500
        df_session = pd.DataFrame({"시간": hours, "세션 수": session_data}).set_index("시간")
        st.area_chart(df_session, height=200, color="#7D44CF")

    with biz_row2_col2:
        st.subheader("4. 주요 업무별 에러 발생률 (Bar)")
        error_rates = [0.1, 0.2, 0.1, 0.05, 0.1]
        if simulate_error: error_rates = [1.2, 45.5, 0.5, 0.1, 0.2]
        df_error = pd.DataFrame({
            "업무명": ["전자문서", "수입신고서", "사전검증", "신고서접수", "고지서생성"],
            "에러율(%)": error_rates
        }).set_index("업무명")
        st.bar_chart(df_error, height=200, color="#FF2B2B")

# ==========================================
# 탭 7: AI 실시간 진단 챗봇 (시뮬레이터 모드)
# ==========================================
elif menu == "🤖 AI 실시간 진단 챗봇":
    st.title("🤖 실시간 AI 시스템 진단 (시뮬레이터 모드)")
    st.caption("현재 환경에서는 로컬 LLM 대신 임시 시뮬레이터가 키워드 기반으로 응답합니다.")
    
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": "안녕하세요. AIOps-Guard 진단 AI (시뮬레이터) 입니다. 장애 상황이나 조치 방안에 대해 질문해 주세요."}
        ]

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("질문을 입력하세요..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("시뮬레이터가 지표를 분석 중입니다..."):
                time.sleep(1.0) 
                
                if "날씨" in prompt or "기온" in prompt:
                    ai_answer = "저는 폐쇄망 내 인프라 감시 전용 AI라 기상 정보를 알 수 없지만, 시스템 상태는 아주 좋습니다! ☀️" if not simulate_error else "기상 상태는 '매우 흐림'입니다. 트래픽 과부하를 점검하세요! ⛈️"
                elif "장애" in prompt or "상황" in prompt or "무슨" in prompt or "이유" in prompt or "원인" in prompt:
                    ai_answer = "현재 09:00 기준으로 **수입신고서 DB**에 예측치 대비 엄청난 폭증(180건)이 발생하여 전체 CPU 점유율이 89%까지 치솟은 심각한 부하 상황입니다." if simulate_error else "현재 09:00 기준 전체 인프라 자원은 정상 범주에 있습니다. 특이 징후는 발견되지 않았습니다."
                elif "조치" in prompt or "해결" in prompt or "방안" in prompt or "어떻게" in prompt:
                    ai_answer = "즉각적인 부하 분산을 위해 **1) 사전검증 일시 중단**, **2) EDI 수신부 WAS 증설**을 권장합니다." if simulate_error else "현재 모든 업무가 원활히 진행 중이므로 필요한 별도 조치 사항은 없습니다."
                else:
                    ai_answer = f"'{prompt}'에 대해 현재 시스템 지표를 분석한 결과, 특이 징후는 검출되지 않았습니다. '장애 상황'이나 '조치 방안' 등을 질문하시면 더 정확히 진단해 드립니다."
                
                st.markdown(ai_answer)
                st.session_state.messages.append({"role": "assistant", "content": ai_answer})

# ==========================================
# 나머지 미구현 탭 처리
# ==========================================
else:
    st.title(menu)
    st.info("해당 메뉴의 세부 지표는 현재 데이터 연동 및 개발 진행 중입니다.")
