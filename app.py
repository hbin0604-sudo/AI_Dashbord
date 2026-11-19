"""AI Dashboard — 기존 ai_engine.py / chatgpt_auth.py / .env와 함께 사용."""
import html
import json
import time
import threading
from urllib.parse import quote
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

import altair as alt
import pandas as pd
import streamlit as st
import ai_engine as ai
import database as db

AI_ANALYSIS_INTERVAL_SECONDS = 30  # 이전 분석 완료 후 대기 시간

st.set_page_config(page_title='AI Dashboard', page_icon='📊', layout='wide')
db.init_db()

@st.cache_resource
def workers():
    return ThreadPoolExecutor(max_workers=4), {}, threading.Lock()

pool, report_jobs, job_lock = workers()
s = st.session_state
for key, value in {
    'menu': '한눈에 보기', 'running': False, 'abnormal': False,
    'generation': 0, 'tick': 0, 'samples': [], 'snapshot': db.make_snapshot(),
    'assessment': None, 'assessed_at': '', 'ai_future': None, 'next_sample': 0.,
    'next_visual': 0., 'ai_error': '', 'active_id': None, 'normal_streak': 0,
    'popup': None, 'flash_until': 0., 'report_future': None, 'report_event': None,
    'report_notice': '', 'chat_open': False, 'chat_history': [], 'chat_future': None,
    'integration_future': None, 'integration_result': '', 'repo_data': None,
    'repo_text': '', 'repo_future': None, 'repo_error': '', 'interval': AI_ANALYSIS_INTERVAL_SECONDS,
    'show_action': False, 'booted': False, 'chart_choice': '응답 시간',
}.items():
    if key not in s:
        s[key] = value
if not s.booted:
    existing = next((e for e in db.list_events() if e['status'] == 'OPEN'), None)
    if existing:
        s.active_id = existing['id']
        s.abnormal = True
        s.snapshot = db.make_snapshot(True)
    # Synthetic pre-roll gives an immediately readable chart, not invented real history.
    anchor = datetime.fromisoformat(db.now())
    s.samples = []
    for i in range(60):
        sample = db.make_snapshot(s.abnormal, i)
        sample['timestamp'] = (anchor - timedelta(seconds=59-i)).isoformat(timespec='seconds')
        s.samples.append(sample)
    s.tick = 59
    s.snapshot = s.samples[-1]
    s.booted = True


def esc(value):
    return html.escape(str(value))


def markup(text):
    st.markdown(text, unsafe_allow_html=True)


# Inline vector paths: no emoji, icon-font download, or operating-system glyph dependency.
ICON_PATHS = {
    'cpu': '<rect x="6" y="6" width="12" height="12" rx="2"/><rect x="9" y="9" width="6" height="6" rx="1"/><path d="M9 3v3m6-3v3M9 18v3m6-3v3M3 9h3m-3 6h3m12-6h3m-3 6h3"/>',
    'clock': '<circle cx="12" cy="13" r="8"/><path d="M12 9v4l3 2M9 2h6m-3 0v3m6 1 2-2"/>',
    'alert': '<circle cx="12" cy="12" r="9"/><path d="M12 7v6m0 4h.01"/>',
    'traffic': '<path d="M4 7h15m-4-4 4 4-4 4M20 17H5m4-4-4 4 4 4"/>',
    'home': '<path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1Z"/>',
    'server': '<rect x="3" y="3" width="18" height="7" rx="2"/><rect x="3" y="14" width="18" height="7" rx="2"/><path d="M7 6.5h.01M7 17.5h.01M12 6.5h5m-5 11h5"/>',
    'bell': '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M9 21h6"/>',
    'report': '<path d="M14 3H5v18h14V8Z M14 3v5h5M8 12h8m-8 4h6"/>',
    'chat': '<path d="M21 11a9 9 0 0 1-9 9H9l-6 2 1-6a9 9 0 1 1 17-5Z"/>',
    'spark': '<path d="m12 2 2.8 7.2L22 12l-7.2 2.8L12 22l-2.8-7.2L2 12l7.2-2.8Z"/>',
    'play': '<path d="m8 4 12 8-12 8Z"/>',
    'pause': '<path d="M8 4v16M16 4v16"/>',
    'flask': '<path d="M9 3h6m-5 0v6L4 19a1 1 0 0 0 1 2h14a1 1 0 0 0 1-2L14 9V3M7 15h10"/>',
    'refresh': '<path d="M20 7V2m0 5h-5M4 17v5m0-5h5M20 7a9 9 0 0 0-16 2m0 8a9 9 0 0 0 16-2"/>',
    'check': '<circle cx="12" cy="12" r="9"/><path d="m7 12 3 3 7-7"/>',
    'close': '<path d="m6 6 12 12M18 6 6 18"/>',
}


def icon_svg(name, color='currentColor', size=24):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
            f'viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.8" '
            'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
            + ICON_PATHS[name] + '</svg>')


def button_icon_css(key, name):
    # Streamlit labels remain plain readable text; CSS draws a local vector icon.
    uri = 'data:image/svg+xml,' + quote(icon_svg(name, '#000000'), safe='')
    return (f'.st-key-{key} button::before {{content:"";display:inline-block;'
            f'width:23px;height:23px;flex:0 0 23px;margin-right:10px;background:currentColor;'
            f'-webkit-mask:url("{uri}") center/contain no-repeat;'
            f'mask:url("{uri}") center/contain no-repeat;}}')


markup('''<style>
:root {--blue:#3182f6;--ink:#191f28;--muted:#6b7684}
.stApp {background:#f5f7fb;color:var(--ink);font-family:"Pretendard","Malgun Gothic",sans-serif}
[data-testid="stHeader"] {background:transparent}
.block-container {padding:2rem 2rem 5rem;max-width:1800px}
h1,h2,h3,p,label {color:var(--ink)}
h1 {font-size:2.6rem!important;font-weight:800!important;letter-spacing:-1.5px}
button, input, textarea {font-family:inherit!important}
[data-testid="stButton"] button,[data-testid="stFormSubmitButton"] button {border-radius:13px;min-height:46px;font-weight:700;border:1px solid #dce2ec;color:#191f28;background:white}
[data-testid="stButton"] button[kind="primary"],[data-testid="stFormSubmitButton"] button[kind="primary"] {background:var(--blue);color:white;border-color:var(--blue)}
[data-testid="stButton"] button:hover {border-color:var(--blue);color:var(--blue)}
[data-testid="stButton"] button[kind="primary"]:hover {color:white;background:#2272eb}
[data-testid="stSidebar"] {background:white;border-right:1px solid #edf0f5;min-width:250px;max-width:280px}
[data-testid="stSidebar"] p,[data-testid="stSidebar"] span {color:#191f28}
[data-testid="stSidebar"] button {border:0;background:white;text-align:left;justify-content:flex-start;min-height:54px}
[data-testid="stSidebar"] button p {font-size:19px;font-weight:700;color:#191f28}
[data-testid="stSidebar"] button[kind="primary"] {background:#e8f1ff!important;color:#226cf3!important}
[data-testid="stSidebar"] button[kind="primary"] p {color:#226cf3!important}
[data-testid="stSidebar"] button:hover {background:#f2f6fc}
.st-key-bottom_nav {padding-top:25vh;border-top:0}
.brand {font-size:25px;font-weight:800;letter-spacing:-.8px;margin:8px 0 4px}
.brand-icon svg {display:block}.brand-icon {display:inline-flex;align-items:center;justify-content:center;width:36px;height:36px;background:#3182f6;color:white!important;border-radius:11px;margin-right:8px}
.brand-sub {font-size:12px;color:#6b7684;margin-bottom:34px}
.head {display:flex;align-items:center;justify-content:space-between;margin-bottom:20px;gap:10px}
.head h1 {margin:0;padding:0}
.badge {font-size:12px;font-weight:600;border-radius:20px;background:#e9edf4;color:#657083;padding:7px 12px;white-space:nowrap}
.kpi {background:white;border:1px solid #edf0f6;border-radius:20px;padding:23px 20px;box-shadow:0 4px 15px #20305005;min-height:130px}
.kpi-label {font-size:17px;font-weight:600;color:#333d4b;margin-bottom:10px}
.kpi-icon {display:inline-flex;align-items:center;color:#3182f6;margin-right:12px;vertical-align:middle}.kpi-icon.error {color:#f04452}
.kpi-value {font-size:clamp(28px,3vw,44px);font-weight:800;line-height:1.15;letter-spacing:-1px}
.ai-banner {display:flex;gap:18px;align-items:center;border-radius:18px;padding:23px 26px;background:linear-gradient(105deg,#2478f6,#408efa);color:white;margin:22px 0;font-size:clamp(20px,2vw,30px);font-weight:750;min-height:90px}
.ai-banner small {display:block;font-size:13px;font-weight:400;opacity:.9;margin-top:4px}
.ai-banner.idle {background:#eaf2ff;color:#245fa6}
.ai-banner.danger {background:#fff0f1;color:#c73e50}
.spinner {width:30px;height:30px;border:4px dotted currentColor;border-radius:50%;animation:spin 1.2s linear infinite;flex-shrink:0}
@keyframes spin {to{transform:rotate(360deg)}}
[data-testid="stVerticalBlockBorderWrapper"]>div {border-radius:20px!important;border-color:#edf0f6!important;background:white}
.summary-title {font-size:23px;font-weight:800;margin-bottom:15px}
.summary-row {font-size:15px;line-height:1.7;padding:13px 0;border-bottom:1px solid #edf0f4;overflow-wrap:anywhere}
.summary-row:last-child {border:0}
.summary-meta {color:#6b7684;font-size:12px;margin-top:15px}
.event-strip {background:white;border-radius:16px;padding:18px 20px;margin-top:20px;font-size:14px;color:#4e5968}
.st-key-chat_launcher {position:fixed;right:28px;bottom:25px;width:245px;z-index:90}
.st-key-chat_launcher button {background:#3182f6!important;color:white!important;border:0!important;border-radius:30px!important;box-shadow:0 8px 25px #3182f640;min-height:58px!important}
.st-key-chat_launcher button p {color:white;font-size:19px;font-weight:700}
.st-key-chat_panel {position:fixed;top:0;right:0;bottom:0;width:420px;background:white;padding:26px 24px;z-index:100;box-shadow:-8px 0 30px #23334d12;border-left:1px solid #e9edf4;overflow-y:auto}
.chat-empty {text-align:center;padding:35px 0 20px}
.chat-symbol {font-size:62px;color:#3182f6}
.chat-empty h3 {font-size:25px!important;margin:15px 0}
.chat-title {font-size:25px;font-weight:800;margin:0 0 12px}
.st-key-chat_panel [data-testid="stForm"] {border:0;padding:8px 0}
.st-key-chat_panel textarea {background:#f7f9fc;border-radius:12px}
.st-key-chat_panel [data-testid="stChatMessage"] {font-size:14px}
.dialog-heading {text-align:center;font-size:30px;font-weight:800;letter-spacing:-1px;margin:8px 0 4px}
.dialog-symbol {text-align:center;font-size:44px;font-weight:600}
.dialog-sub {text-align:center;color:#6b7684;margin-bottom:22px;font-size:15px}
.dialog-metrics {display:flex;justify-content:space-around;text-align:center;margin:20px 0}
.dialog-metrics span {display:block;font-size:13px;color:#6b7684}
.dialog-metrics strong {font-size:25px}
.dialog-box {background:#f5f6f8;border-radius:15px;padding:18px;margin:15px 0;line-height:1.7}
@media(max-width:1100px){.block-container {padding:1.5rem 1rem 5rem}.kpi{padding:16px 12px}.kpi-label{font-size:14px}}
@media(max-width:700px){.st-key-chat_panel{width:94vw}.head h1{font-size:1.8rem!important}}
</style>''')
if s.chat_open:
    markup('''<style>@media(min-width:1450px){[data-testid="stMain"] {margin-right:420px}} .st-key-chat_launcher{display:none}</style>''')


def set_scenario(abnormal):
    s.abnormal = abnormal
    s.generation += 1
    s.normal_streak = 0
    s.assessment = None
    s.ai_error = ''
    s.next_sample = 0.
    s.next_visual = 0.
    s.tick += 1
    s.snapshot = db.make_snapshot(abnormal, s.tick)
    s.samples = (s.samples + [s.snapshot])[-180:]
    s.running = True


def show_popup(kind, event_id, flash=True):
    s.popup = (kind, event_id)
    s.flash_until = time.time() + 5 if flash else 0


def submit_report(event_id):
    with job_lock:
        future = report_jobs.get(event_id)
        if future is None or future.done():
            future = pool.submit(db.create_and_commit_report, event_id)
            report_jobs[event_id] = future
        s.report_future = future
        s.report_event = event_id
        s.report_notice = 'AI 보고서를 작성하고 GitLab에 저장하고 있어요…'


def ask(question):
    if s.chat_future is not None:
        return
    context = {'latest_sample': s.snapshot, 'last_assessment': s.assessment,
               'assessment_time': s.assessed_at, 'recent_messages': s.chat_history[-6:]}
    prompt = ('당신은 WEB/WAS 운영 도우미입니다. 다음 자료는 가상 시연 데이터입니다. '
              '관측과 추정을 구분하고 실제 조치가 실행됐다고 단정하지 마세요. '
              '이전 분석 시각과 현재 관측 시각이 다를 수 있습니다. 한국어로 간결하게 답하세요.\n'
              + json.dumps(context, ensure_ascii=False) + '\n질문: ' + question)
    s.chat_history.append(('user', question))
    s.chat_future = pool.submit(ai.ask_ai_bot, prompt)


icon_buttons = {
    'nav_overview':'home', 'nav_servers':'server', 'nav_alerts':'bell',
    'nav_reports':'report', 'run_toggle':'pause' if s.running else 'play',
    'inject':'flask', 'restore':'refresh', 'open_chat':'chat', 'close_chat':'close',
}
markup('<style>'+''.join(button_icon_css(key, icon) for key, icon in icon_buttons.items())+
       '.st-key-close_chat button {min-width:36px;padding:8px}.st-key-close_chat button p {display:none}'
       '.st-key-close_chat button::before {margin:0}'+'</style>')

with st.sidebar:
    markup('<div class="brand"><span class="brand-icon">'+icon_svg('server','white',25)+'</span>AI Dashboard</div><div class="brand-sub">WEB / WAS 인프라 모니터링</div>')
    for item, nav_key in [('한눈에 보기','overview'),('서버 상태','servers'),('알림 기록','alerts')]:
        if st.button(item, key='nav_'+nav_key, use_container_width=True,
                     type='primary' if s.menu == item else 'secondary'):
            s.menu = item
            st.rerun()
    with st.container(key='bottom_nav'):
        if st.button('자동 리포트', key='nav_reports', use_container_width=True,
                     type='primary' if s.menu == '자동 리포트' else 'secondary'):
            s.menu = '자동 리포트'
            st.rerun()
    if ai.settings()['provider'] == 'demo':
        st.caption('샘플 데이터 · 규칙 기반 테스트 모드')


def render_controls():
    c1,c2,c3,_ = st.columns([1.1,1.25,1,1])
    if c1.button('일시 정지' if s.running else '모니터링 시작', key='run_toggle',
                 type='primary', use_container_width=True):
        s.running = not s.running
        s.generation += 1
        s.next_sample = 0.
        s.next_visual = 0.
        st.rerun()
    if c2.button('이상 상황 테스트', key='inject', use_container_width=True, disabled=s.abnormal):
        set_scenario(True)
        st.rerun()
    if c3.button('정상 복구', key='restore', use_container_width=True, disabled=not s.abnormal):
        set_scenario(False)
        st.rerun()


def render_metrics():
    snap = s.snapshot
    values = [('서버 사용률',f"{snap['cpu_pct']:g}%",'cpu'),
              ('응답 시간',f"{snap['latency_ms']:,}ms",'clock'),
              ('오류 비율',f"{snap['error_pct']:g}%",'alert'),
              ('초당 요청',f"{snap['tps']}/s",'traffic')]
    for col, (label, value, icon) in zip(st.columns(4), values):
        with col:
            icon_class = "kpi-icon error" if icon == "alert" else "kpi-icon"
            markup(f'<div class="kpi"><div class="kpi-label"><span class="{icon_class}">{icon_svg(icon, size=32)}</span>{label}</div><div class="kpi-value">{value}</div></div>')


def render_status():
    if s.ai_error:
        title, sub, cls = 'AI 분석 결과를 확인하지 못했어요', '정상으로 판정하지 않고 기존 상태를 유지합니다.', 'danger'
    elif s.ai_future:
        title, sub, cls = 'AI가 상태를 분석하고 있어요', '최신 관측값을 바탕으로 이상 징후와 확인할 사항을 검토합니다.', ''
    elif s.active_id:
        title, sub, cls = '이상 징후를 확인하고 있어요', f'연속 정상 확인 {s.normal_streak}/2 · 담당자 조치와 복구 상태를 확인하세요.', 'danger'
    elif not s.running:
        title, sub, cls = '모니터링을 시작해 보세요', '시작하면 그래프가 실시간으로 움직이고 AI 분석을 진행합니다.', 'idle'
    elif s.assessment:
        title, sub, cls = '최근 분석에서 정상 범위를 확인했어요', f'지표는 1초마다 갱신 · 다음 AI 분석까지 {max(0, int(s.next_sample-time.monotonic()))}초', 'idle'
    else:
        title, sub, cls = '최신 데이터를 확인하고 있어요', 'AI 분석을 준비합니다.', 'idle'
    if ai.settings()['provider'] == 'demo':
        sub = '규칙 기반 테스트 모드 · 실제 AI 호출 없음'
    icon = '<span class="spinner"></span>' if s.ai_future else icon_svg('spark',size=30)
    markup(f'<div class="ai-banner {cls}">{icon}<div>{esc(title)}<small>{esc(sub)}</small></div></div>')
    if s.ai_error:
        st.error(s.ai_error)


def render_chart():
    fields = {'응답 시간':('latency_ms','ms'),'서버 사용률':('cpu_pct','%'),'오류 비율':('error_pct','%')}
    left, right = st.columns([2.1,1], gap='medium')
    with left, st.container(border=True):
        st.markdown('### 응답 시간 추이' if s.chart_choice == '응답 시간' else '### '+s.chart_choice+' 추이')
        choice = st.selectbox('표시 지표', list(fields), key='chart_choice', label_visibility='collapsed')
        field, unit = fields[choice]
        frame = pd.DataFrame(s.samples)
        frame['시각'] = frame['timestamp'].str[11:19]
        frame['순서'] = range(len(frame))
        # Ordinal clock strings avoid browser timezone conversion of KST labels.
        base = alt.Chart(frame).encode(
            x=alt.X('시각:O', sort=None, title=None, axis=alt.Axis(labelAngle=0, values=frame['시각'].iloc[::max(1,len(frame)//6)].tolist())),
            y=alt.Y(field+':Q',title=unit,scale=alt.Scale(zero=True)),
            tooltip=[alt.Tooltip('시각:N'), alt.Tooltip(field+':Q',title=choice+' ('+unit+')')])
        chart = (base.mark_area(color='#3182f6',opacity=.09) + base.mark_line(color='#3182f6',strokeWidth=2.8)).properties(height=260)
        st.altair_chart(chart, use_container_width=True)
        st.caption('최근 3분 · 샘플 데이터 · 1초 간격 갱신 · KST')
    with right, st.container(border=True):
        markup('<div class="summary-title">'+icon_svg('spark','#7664ff',25)+' AI 상태 요약</div>')
        if s.ai_error:
            rows = ['최근 분석 실패 · 상태 확인 필요', '이전 판정만으로 정상 여부를 확정하지 않습니다.']
        elif s.assessment:
            rows = [s.assessment['summary']] + s.assessment['reasons'][:2]
            if s.assessment['actions']:
                rows.append('확인 제안: '+s.assessment['actions'][0])
        else:
            rows = ['아직 분석 결과가 없어요.', '분석이 완료되면 확인된 내용과 대응 제안을 표시합니다.']
        for row in rows:
            markup('<div class="summary-row">'+esc(row)+'</div>')
        markup(f'<div class="summary-row">현재 CPU {s.snapshot["cpu_pct"]:g}% · 메모리 {s.snapshot["memory_pct"]:g}%</div>')
        if s.assessed_at:
            markup('<div class="summary-meta">최근 분석 관측 시각 '+esc(s.assessed_at[11:19])+' KST</div>')
    events = db.list_events()
    latest = ('최근 알림 없음' if not events else
              ('복구 확인' if events[0]['status']=='RESOLVED' else '이상 감지')+' · '+events[0]['detected_at'][11:19])
    markup('<div class="event-strip"><b>최근 이벤트</b>　 ·　'+esc(latest)+'</div>')


@st.fragment(run_every='1s')
def monitor():
    full_refresh = False
    if s.integration_future is not None and s.integration_future.done():
        try:
            s.integration_result = str(s.integration_future.result())
        except Exception as exc:
            s.integration_result = str(exc) if isinstance(exc, ai.IntegrationError) else '연결 검사 처리 실패'
        s.integration_future = None
        full_refresh = True
    if s.chat_future is not None and s.chat_future.done():
        try:
            answer = s.chat_future.result()
        except Exception as exc:
            answer = str(exc) if isinstance(exc, ai.IntegrationError) else 'AI 응답 처리 실패'
        s.chat_history.append(('assistant', answer))
        s.chat_future = None
        full_refresh = True
    if s.report_future is not None and s.report_future.done():
        try:
            result = s.report_future.result()
            s.report_notice = 'GitLab 커밋 완료: ' + result['id'][:12]
            s.repo_data = None
        except Exception as exc:
            s.report_notice = str(exc) if isinstance(exc, ai.IntegrationError) else '보고서 처리 실패. 재시도하세요.'
        s.report_future = None
        full_refresh = True
    if s.repo_future is not None and s.repo_future[1].done():
        kind, future = s.repo_future
        try:
            value = future.result()
            if kind == 'list':
                s.repo_data = value
                s.repo_text = ''
            else:
                s.repo_text = value
            s.repo_error = ''
        except Exception as exc:
            s.repo_error = str(exc) if isinstance(exc, ai.IntegrationError) else '저장소 조회 실패'
        s.repo_future = None
        full_refresh = True
    if s.ai_future is not None and s.ai_future[0].done():
        future, snapshot, generation = s.ai_future
        s.ai_future = None
        if generation == s.generation:
            s.next_sample = time.monotonic() + s.interval
            try:
                assessment = future.result()
                s.assessment = assessment
                s.assessed_at = snapshot['timestamp']
                s.ai_error = ''
                s.active_id, s.normal_streak, event = db.transition(
                    s.active_id, s.normal_streak, snapshot, assessment)
                if event:
                    show_popup(*event)
                    full_refresh = True
            except Exception as exc:
                s.ai_error = str(exc) if isinstance(exc, ai.IntegrationError) else 'AI 분석 처리 오류'
                s.normal_streak = 0  # Failed calls do not count as normal recovery samples.
                if ai.settings()['provider'] == 'chatgpt':
                    s.running = False  # Stop on auth/quota errors; never open a login browser.
                    full_refresh = True
    # Visual samples run every second, independent of the slower model request.
    if s.running and time.monotonic() >= s.next_visual:
        s.tick += 1
        s.snapshot = db.make_snapshot(s.abnormal, s.tick)
        s.samples = (s.samples + [s.snapshot])[-180:]
        s.next_visual = time.monotonic() + 1
    if s.running and s.ai_future is None and time.monotonic() >= s.next_sample:
        snapshot = dict(s.snapshot)
        s.ai_future = (pool.submit(ai.assess, snapshot), snapshot, s.generation)
        s.next_sample = float('inf')  # Re-armed on completion, not request start.
    if full_refresh:
        st.rerun()
    if s.menu in ('한눈에 보기','서버 상태'):
        render_metrics()
        render_status()
        render_chart()
        if s.menu == '서버 상태':
            st.dataframe(pd.DataFrame([{'서버':s.snapshot['service'], 'CPU %':s.snapshot['cpu_pct'],
                '메모리 %':s.snapshot['memory_pct'], '초당 요청':s.snapshot['tps'],
                'WAS 오류':s.snapshot['was_errors']}]), hide_index=True, use_container_width=True)
            with st.expander('최근 관측 데이터'):
                st.dataframe(pd.DataFrame(s.samples[-30:]), hide_index=True)


heading = {'한눈에 보기':'서비스 상태를 한눈에','서버 상태':'서버 상태','알림 기록':'알림 기록','자동 리포트':'자동 리포트'}
markup(f'<div class="head"><h1>{heading.get(s.menu,"서비스 상태를 한눈에")}</h1><span class="badge">샘플 데이터</span></div>')
if s.menu in ('한눈에 보기','서버 상태'):
    render_controls()
monitor()

if s.active_id and s.menu != '자동 리포트':
    with st.expander('진행 중인 이상 징후 · 조치 기록', expanded=s.show_action):
        if st.button('현재 이상 알림 다시 열기'):
            show_popup('alert', s.active_id, flash=False)
            st.rerun()
        with st.form('action_form'):
            note = st.text_input('수행한 조치', placeholder='예: 요청량 확인 후 요청 제한 적용')
            if st.form_submit_button('조치 내용·현재 시각 저장'):
                if note.strip():
                    db.record_action(s.active_id,note)
                    st.success('조치 기록을 저장했어요.')
                else:
                    st.warning('조치 내용을 입력하세요.')

if s.menu == '알림 기록':
    events = db.list_events()
    if not events:
        st.info('아직 발생한 알림이 없어요.')
    for event in events:
        with st.expander(('복구 완료' if event['status']=='RESOLVED' else '확인 필요')+' · '+event['detected_at']):
            st.write(event['diagnosis']['summary'])
            st.caption(event['id'])
            st.write('탐지:',event['detected_at'],' / 복구:',event['resolved_at'] or '확인 중')
            for action in event['actions']:
                st.write(action['recorded_at']+' · '+action['note'])
            if st.button('알림 상세 보기',key='event_'+event['id']):
                show_popup('recovery' if event['status']=='RESOLVED' else 'alert',event['id'],False)
                st.rerun()

if s.menu == '자동 리포트':
    if s.repo_data is None and s.repo_future is None and not s.repo_error:
        s.repo_future = ('list', pool.submit(ai.repository_reports))
    st.subheader('GitLab 저장소 · reports/')
    st.caption('저장된 분석 보고서를 확인하세요.')
    if st.button('GitLab 저장소 새로고침', disabled=s.repo_future is not None):
        s.repo_future = ('list', pool.submit(ai.repository_reports))
        st.rerun()
    if s.repo_future:
        st.info('GitLab 조회 중…')
    if s.repo_error:
        st.error(s.repo_error)
    if s.repo_data:
        st.write(s.repo_data['project'].get('path_with_namespace', 'GitLab'), ' / ', s.repo_data['branch'])
        st.link_button('GitLab 원본 열기', s.repo_data['project']['web_url'])
        paths = [f['path'] for f in s.repo_data['files']]
        if paths:
            selected = st.selectbox('저장소 보고서', paths)
            if st.button('선택한 보고서 열기', disabled=s.repo_future is not None):
                s.repo_future = ('read', pool.submit(ai.read_repository_report, selected))
                st.rerun()
        else:
            st.info('아직 reports/에 Markdown 보고서가 없습니다.')
        if s.repo_data['truncated']:
            st.warning('목록은 최대 1,000개 항목까지만 조회합니다.')
        if s.repo_text:
            with st.container(border=True):
                st.markdown(s.repo_text)
    st.divider()
    st.subheader('로컬 이벤트 / 커밋 재시도')
    events = db.list_events()
    if not events:
        st.info('아직 탐지된 이벤트가 없습니다.')
    for event in events:
        with st.expander(f"{event['id']} · {event['status']} · {'커밋 완료' if event['commit'] else '미커밋'}"):
            st.write('탐지:', event['detected_at'], ' / 복구:', event['resolved_at'] or '미복구')
            if event['status'] == 'RESOLVED':
                if st.button('복구 알림 / 보고서 열기', key='history_' + event['id']):
                    show_popup('recovery', event['id'], flash=False)
                    st.rerun()
            if event['report']:
                st.download_button('로컬 보고서 다운로드', event['report'], file_name=event['id'] + '.md', key='dl_' + event['id'])


if s.chat_open:
    with st.container(key='chat_panel'):
        title, close = st.columns([5,1])
        with title:
            markup('<div class="chat-title">AI 운영 도우미</div>')
        if close.button('닫기', key='close_chat', help='상담창 닫기'):
            s.chat_open = False
            st.rerun()
        if not s.chat_history:
            markup('<div class="chat-empty"><div class="chat-symbol">'+icon_svg('chat','#3182f6',72)+'</div><h3>무엇을 확인할까요?</h3></div>')
            for question in ['지금 상태 요약','느려진 이유','대처 방법']:
                if st.button(question, key='suggest_'+question, use_container_width=True, disabled=s.chat_future is not None):
                    ask(question)
                    st.rerun()
        else:
            with st.container(height=410):
                for role,message in s.chat_history:
                    with st.chat_message(role):
                        st.markdown(message)
        if s.chat_future:
            st.info('AI가 답변을 작성하고 있어요…')
        with st.form('chat_form', clear_on_submit=True):
            question = st.text_area('궁금한 내용을 입력하세요',height=95)
            if st.form_submit_button('보내기',type='primary',use_container_width=True,disabled=s.chat_future is not None) and question.strip():
                ask(question.strip())
                st.rerun()
else:
    with st.container(key='chat_launcher'):
        if st.button('AI에게 물어보기',key='open_chat',use_container_width=True):
            s.chat_open = True
            st.rerun()


def popup_css(kind):
    color = '240,68,82' if kind == 'alert' else '22,163,106'
    solid = '#e53949' if kind == 'alert' else '#12915e'
    elapsed = max(0., 5 - (s.flash_until-time.time()))
    animation = (f'incidentPulse 1s ease-in-out 5;animation-delay:-{elapsed:.3f}s;'
                 'animation-fill-mode:forwards') if elapsed < 5 else 'none'
    # Reset only ancestors of the actual dialog, never the card/content itself.
    # This also covers versions that add a wrapper around the BaseWeb modal.
    markup(f'''<style>
    @keyframes incidentPulse {{0%,100%{{background-color:rgba({color},.24)}}50%{{background-color:rgba({color},.64)}}}}
    [data-testid="stDialog"] {{position:fixed!important;inset:0!important;
        background:transparent!important;isolation:isolate;width:100%!important;
        max-width:none!important;margin:0!important;padding:0!important;
        border:0!important;border-radius:0!important;box-shadow:none!important}}
    [data-testid="stDialog"] div:has([role="dialog"]) {{background:transparent!important;
        box-shadow:none!important;border:0!important;border-radius:0!important;
        width:100%!important;max-width:none!important;min-width:0!important;
        margin:0!important;padding:0!important}}
    [data-testid="stDialog"]::before {{content:"";position:fixed;inset:0;pointer-events:none;
        background-color:rgba({color},.24);animation:{animation};z-index:0}}
    [data-testid="stDialog"] div:has(> [role="dialog"]) {{position:relative;z-index:1;
        min-height:100vh!important;min-height:100dvh!important;box-sizing:border-box;
        display:flex;justify-content:center!important;align-items:center!important;
        padding:28px 16px!important}}
    [data-testid="stDialog"] [role="dialog"]:not(:has([role="dialog"])) {{background:#fff!important;color:#191f28!important;
        position:relative;z-index:1;box-sizing:border-box;flex:0 1 560px;
        animation:none!important;opacity:1!important;width:560px!important;max-width:calc(100vw - 32px)!important;
        min-width:0!important;min-height:0!important;margin:0!important;border-radius:25px!important;
        max-height:calc(100vh - 56px);max-height:calc(100dvh - 56px);overflow-y:auto;
        border:1px solid rgba({color},.22)!important;border-top:5px solid {solid}!important;
        box-shadow:0 24px 80px rgba({color},.25)!important}}
    [data-testid="stDialog"] button[kind="primary"] {{background:{solid}!important;
        border-color:{solid}!important;color:white!important}}
    [data-testid="stDialog"] button[kind="primary"] p {{color:white!important}}
    [data-testid="stDialog"] button[kind="primary"]:hover {{filter:brightness(.93)}}
    [data-testid="stDialog"] button[kind="primary"]:disabled {{opacity:.55}}
    [data-testid="stDialog"] .dialog-symbol svg {{display:block;margin:0 auto}}
    [data-testid="stDialog"] .dialog-heading {{color:{solid};font-size:29px}}
    [data-testid="stDialog"] .dialog-box {{background:rgba({color},.06)}}
    .st-key-close_recovery button {{color:{solid}!important;border-color:rgba({color},.35)!important}}
    </style>''')


@st.dialog('상태 알림',width='small',dismissible=False)
def incident_dialog(kind,event_id):
    popup_css(kind)
    event = db.get_event(event_id)
    if not event:
        st.error('알림을 찾을 수 없습니다.')
        if st.button('닫기'):
            s.popup = None
            st.rerun()
        return
    is_alert = kind == 'alert'
    snap = event['snapshot'] if is_alert else event['recovery_snapshot']
    color = '#f04452' if is_alert else '#18a66a'
    title = ('응답이 느려졌어요' if snap['latency_ms'] >= 2000 else '이상 징후를 발견했어요') if is_alert else '정상 상태로 돌아왔어요'
    symbol = icon_svg("alert" if is_alert else "check", color, 58)
    markup(f'<div class="dialog-symbol" style="color:{color}">{symbol}</div><div class="dialog-heading">{title}</div><div class="dialog-sub">{"AI가 확인한 이상 징후" if is_alert else "연속 2회 정상 확인"}</div>')
    markup(f'<div class="dialog-metrics"><div><span>응답 시간</span><strong>{snap["latency_ms"]:,}ms</strong></div><div><span>서버 사용률</span><strong>{snap["cpu_pct"]:g}%</strong></div><div><span>오류 비율</span><strong>{snap["error_pct"]:g}%</strong></div></div>')
    if is_alert:
        st.write(event['diagnosis']['summary'])
        actions = ''.join('<div>• '+esc(a)+'</div>' for a in event['diagnosis']['actions'])
        markup('<div class="dialog-box"><b>권장 확인 사항</b>'+actions+'</div>')
        st.caption(event['diagnosis']['source']+' · 탐지 '+event['detected_at'][11:19]+' KST')
        if st.button('조치 기록 · 모니터링 계속',key='ack_alert',type='primary',use_container_width=True):
            s.show_action = True
            s.popup = None
            st.rerun()
    else:
        notes = '<br>'.join(esc(a['recorded_at'][11:19]+' · '+a['note']) for a in event['actions']) or '담당자 조치 기록 없음'
        markup('<div class="dialog-box">발생 '+esc(event['detected_at'])+'<br>복구 '+esc(event['resolved_at'])+'<br>'+notes+'</div>')
        if event['commit']:
            st.success('GitLab에 보고서를 저장했어요.')
            st.link_button('저장된 보고서 열기',event['commit']['web_url'])
        else:
            if st.button('GitLab 저장 재시도' if event['report'] else '자동 리포트 생성',key='generate_report',type='primary',use_container_width=True,disabled=s.report_future is not None):
                submit_report(event_id)
                st.rerun()
        if s.report_event == event_id and s.report_notice:
            st.info(s.report_notice)
        if event['report_error']:
            st.error(event['report_error'])
        if event['report']:
            with st.expander('보고서 미리보기'):
                st.markdown(event['report'])
            st.download_button('보고서 다운로드',event['report'],file_name=event_id+'.md')
        if st.button('닫기',key='close_recovery',use_container_width=True):
            s.popup = None
            st.rerun()

if s.popup:
    incident_dialog(*s.popup)
