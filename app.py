"""전자통관 AI 관제시스템 — 토스 컬러 팔레트 기반 통합 인프라·보안·AP 품질 관제."""
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

AI_ANALYSIS_INTERVAL_SECONDS = 30

st.set_page_config(page_title='전자통관 AI 관제시스템', page_icon='📊', layout='wide')
db.init_db()
db.seed_initial_history()


@st.cache_resource
def workers():
    return ThreadPoolExecutor(max_workers=4), {}, threading.Lock()


pool, report_jobs, job_lock = workers()
s = st.session_state
for key, value in {
    'menu': 'AI 대시보드', 'running': False, 'active_scenarios': [],
    'generation': 0, 'tick': 0, 'samples': [], 'snapshot': db.make_snapshot([]),
    'assessment': None, 'assessed_at': '', 'ai_future': None, 'next_sample': 0.,
    'next_visual': 0., 'ai_error': '', 'active_id': None, 'normal_streak': 0,
    'popup': None, 'flash_until': 0., 'report_future': None, 'report_event': None,
    'report_notice': '', 'chat_open': False, 'chat_history': [], 'chat_future': None,
    'integration_future': None, 'integration_result': '', 'repo_data': None,
    'repo_text': '', 'repo_future': None, 'repo_error': '', 'interval': AI_ANALYSIS_INTERVAL_SECONDS,
    'show_action': False, 'booted': False, 'chart_choice': '응답 시간',
    'selected_farm': '전체 서버팜',
}.items():
    if key not in s:
        s[key] = value

# 이전 세션 메뉴명 호환 처리
menu_migration = {
    '한눈에 보기': 'AI 대시보드',
    'AI대시보드': 'AI 대시보드',
    '서버 상태': '인프라 관리',
    '관세행정 서비스 품질': '관세행정 서비스품질',
}
if s.menu in menu_migration:
    s.menu = menu_migration[s.menu]

if not s.booted:
    existing = next((e for e in db.list_events() if e['status'] == 'OPEN'), None)
    if existing:
        s.active_id = existing['id']
        s.active_scenarios = existing['snapshot'].get('active_scenarios', ['cpu_spike'])
        s.snapshot = db.make_snapshot(s.active_scenarios)
    anchor = datetime.fromisoformat(db.now())
    s.samples = []
    for i in range(60):
        sample = db.make_snapshot(s.active_scenarios, i)
        sample['timestamp'] = (anchor - timedelta(seconds=59 - i)).isoformat(timespec='seconds')
        s.samples.append(sample)
    s.tick = 59
    s.snapshot = s.samples[-1]
    s.booted = True


def esc(value):
    return html.escape(str(value))


def markup(text):
    st.markdown(text, unsafe_allow_html=True)


ICON_PATHS = {
    'cpu': '<rect x="6" y="6" width="12" height="12" rx="2"/><rect x="9" y="9" width="6" height="6" rx="1"/><path d="M9 3v3m6-3v3M9 18v3m6-3v3M3 9h3m-3 6h3m12-6h3m-3 6h3"/>',
    'clock': '<circle cx="12" cy="13" r="8"/><path d="M12 9v4l3 2M9 2h6m-3 0v3m6 1 2-2"/>',
    'alert': '<circle cx="12" cy="12" r="9"/><path d="M12 7v6m0 4h.01"/>',
    'traffic': '<path d="M4 7h15m-4-4 4 4-4 4M20 17H5m4-4-4 4 4 4"/>',
    'shield': '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
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
    'service': '<path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>',
}


def icon_svg(name, color='currentColor', size=24):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
            f'viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.8" '
            'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
            + ICON_PATHS[name] + '</svg>')


def button_icon_css(key, name):
    uri = 'data:image/svg+xml,' + quote(icon_svg(name, '#000000'), safe='')
    return (f'.st-key-{key} button::before {{content:"";display:inline-block;'
            f'width:20px;height:20px;flex:0 0 20px;margin-right:8px;background:currentColor;'
            f'-webkit-mask:url("{uri}") center/contain no-repeat;'
            f'mask:url("{uri}") center/contain no-repeat;}}')


# 토스(Toss) 디자인 시스템 컬러 팔레트 (위험=빨강, 주의=주황 반영)
markup('''<style>
:root {
    --blue:#3182f6;
    --blue-dark:#1b64da;
    --blue-soft:#e8f3ff;
    --ink:#191f28;
    --ink-sub:#4e5968;
    --muted:#8b95a1;
    --border:#e5e8eb;
    --bg:#f2f4f6;
    --red:#f04452;
    --red-soft:#ffeeee;
    --orange:#f57c00;
    --orange-soft:#fff4e5;
    --green:#03b26c;
    --green-soft:#e8f7f0;
}
.stApp {background:var(--bg);color:var(--ink);font-family:"Pretendard","Malgun Gothic",sans-serif}
[data-testid="stHeader"] {background:transparent}
.block-container {padding:1.8rem 2rem 5rem;max-width:1800px}
h1,h2,h3,p,label {color:var(--ink)}
h1 {font-size:2.35rem!important;font-weight:800!important;letter-spacing:-1.2px}
button, input, textarea {font-family:inherit!important}
[data-testid="stButton"] button,[data-testid="stFormSubmitButton"] button {border-radius:12px;min-height:44px;font-weight:700;border:1px solid var(--border);color:var(--ink);background:white;transition:all .15s ease}
[data-testid="stButton"] button[kind="primary"],[data-testid="stFormSubmitButton"] button[kind="primary"] {background:var(--blue);color:white;border-color:var(--blue)}
[data-testid="stButton"] button:hover {border-color:var(--blue);color:var(--blue);background:#f9fafb}
[data-testid="stButton"] button[kind="primary"]:hover {color:white;background:var(--blue-dark)}
[data-testid="stSidebar"] {background:white;border-right:1px solid var(--border);min-width:265px;max-width:295px}
[data-testid="stSidebar"] p,[data-testid="stSidebar"] span {color:var(--ink)}
[data-testid="stSidebar"] button {border:0;background:white;text-align:left;justify-content:flex-start;min-height:50px}
[data-testid="stSidebar"] button p {font-size:17px;font-weight:700;color:var(--ink-sub)}
[data-testid="stSidebar"] button[kind="primary"] {background:var(--blue-soft)!important;color:var(--blue)!important}
[data-testid="stSidebar"] button[kind="primary"] p {color:var(--blue)!important}
[data-testid="stSidebar"] button:hover {background:var(--bg)}
.st-key-bottom_nav {padding-top:12vh;border-top:0}
.brand-box {display:flex;align-items:center;gap:9px;margin:6px 0 6px}
.brand-icon svg {display:block}
.brand-icon {display:inline-flex;align-items:center;justify-content:center;width:32px;height:32px;flex:0 0 32px;background:var(--blue);color:white!important;border-radius:10px}
.brand-title {font-size:16.5px;font-weight:800;line-height:1.2;letter-spacing:-.6px;color:var(--ink);white-space:nowrap}
.brand-sub {font-size:12px;line-height:1.45;color:var(--muted);margin-bottom:22px;font-weight:600}
.head {display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;gap:10px}
.head h1 {margin:0;padding:0}
.badge-group {display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.badge {font-size:12px;font-weight:700;border-radius:20px;background:white;border:1px solid var(--border);color:var(--ink-sub);padding:6px 13px;white-space:nowrap}
.badge.ai {background:var(--blue-soft);border-color:transparent;color:var(--blue)}
.kpi {background:white;border:1px solid var(--border);border-radius:18px;padding:20px;box-shadow:0 2px 10px rgba(25,31,40,.03);min-height:118px}
.kpi-label {font-size:14px;font-weight:700;color:var(--ink-sub);margin-bottom:8px;display:flex;align-items:center}
.kpi-icon {display:inline-flex;align-items:center;color:var(--blue);margin-right:8px}.kpi-icon.error {color:var(--red)}.kpi-icon.warn {color:var(--orange)}
.kpi-value {font-size:clamp(24px,2.3vw,34px);font-weight:800;line-height:1.15;letter-spacing:-0.8px;color:var(--ink)}
.kpi-sub {font-size:12px;color:var(--muted);margin-top:6px;font-weight:500}
.ai-banner {display:flex;gap:16px;align-items:center;border-radius:18px;padding:20px 24px;background:var(--blue);color:white;margin:18px 0;font-size:clamp(18px,1.7vw,24px);font-weight:750;min-height:80px}
.ai-banner small {display:block;font-size:13px;font-weight:400;opacity:.92;margin-top:4px}
.ai-banner.idle {background:var(--blue-soft);color:var(--blue-dark)}
.ai-banner.danger {background:var(--red-soft);color:var(--red);border:1px solid #ffd8dc}
.spinner {width:26px;height:26px;border:4px dotted currentColor;border-radius:50%;animation:spin 1.2s linear infinite;flex-shrink:0}
@keyframes spin {to{transform:rotate(360deg)}}
[data-testid="stVerticalBlockBorderWrapper"]>div {border-radius:18px!important;border-color:var(--border)!important;background:white;box-shadow:0 2px 10px rgba(25,31,40,.02)}
.summary-title {font-size:19px;font-weight:800;margin-bottom:12px;display:flex;align-items:center;gap:8px;color:var(--ink)}
.summary-row {font-size:14px;line-height:1.6;padding:11px 0;border-bottom:1px solid var(--bg);overflow-wrap:anywhere;color:var(--ink-sub)}
.summary-row:last-child {border:0}
.summary-meta {color:var(--muted);font-size:12px;margin-top:12px}
.event-strip {background:white;border:1px solid var(--border);border-radius:14px;padding:14px 18px;margin-top:16px;font-size:14px;color:var(--ink-sub)}
/* 서버팜 요약 카드 */
.farm-card {background:white;border:1px solid var(--border);border-radius:18px;padding:20px;box-shadow:0 2px 10px rgba(25,31,40,.03)}
.farm-header {display:flex;justify-content:space-between;align-items:center;margin-bottom:12px}
.farm-title {font-size:18px;font-weight:800;color:var(--ink)}
.farm-badge {font-size:12px;font-weight:700;padding:4px 10px;border-radius:12px}
.fb-ok {background:var(--green-soft);color:var(--green)}
.fb-warn {background:var(--orange-soft);color:var(--orange)}
.fb-crit {background:var(--red-soft);color:var(--red)}
.farm-spec {font-size:13px;color:var(--muted);margin-bottom:14px;font-weight:600}
.bar-wrap {margin-bottom:11px}
.bar-label {display:flex;justify-content:space-between;font-size:13px;font-weight:700;color:var(--ink-sub);margin-bottom:5px}
.bar-track {width:100%;height:8px;background:var(--bg);border-radius:99px;overflow:hidden}
.bar-fill {height:100%;border-radius:99px;background:var(--blue)}
.bar-fill.warn {background:var(--orange)}
.bar-fill.crit {background:var(--red)}
/* 관세행정 서비스품질 카드 */
.svc-grid {display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin:14px 0 18px}
.svc-card {background:white;border:1px solid var(--border);border-radius:16px;padding:16px;box-shadow:0 2px 8px rgba(25,31,40,.02)}
.svc-top {display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}
.svc-name {font-size:15px;font-weight:800;color:var(--ink)}
.svc-code {font-size:11px;color:var(--muted);margin-bottom:10px;font-weight:600}
.svc-val {font-size:22px;font-weight:800;color:var(--ink);letter-spacing:-0.5px}
.svc-sub {font-size:12px;color:var(--ink-sub);margin-top:4px}
/* AI 운영 도우미 플로팅 패널 */
.st-key-chat_launcher {position:fixed;right:28px;bottom:25px;width:230px;z-index:90}
.st-key-chat_launcher button {background:var(--blue)!important;color:white!important;border:0!important;border-radius:30px!important;box-shadow:0 8px 24px rgba(49,130,246,.28);min-height:54px!important}
.st-key-chat_launcher button p {color:white;font-size:17px;font-weight:700}
.st-key-chat_panel {position:fixed;top:0;right:0;bottom:0;width:420px;background:white;padding:54px 22px 24px;z-index:999990;box-shadow:-8px 0 30px rgba(25,31,40,.08);border-left:1px solid var(--border);overflow-y:auto}
.chat-empty {text-align:center;padding:28px 0 16px}
.chat-symbol {font-size:54px;color:var(--blue)}
.chat-empty h3 {font-size:22px!important;margin:12px 0;color:var(--ink)}
.chat-title {font-size:22px;font-weight:800;margin:0 0 12px;color:var(--ink)}
.st-key-chat_panel [data-testid="stForm"] {border:0;padding:8px 0}
.st-key-chat_panel textarea {background:var(--bg);border-radius:12px}
.st-key-chat_panel [data-testid="stChatMessage"] {font-size:14px}
.dialog-heading {text-align:center;font-size:28px;font-weight:800;letter-spacing:-1px;margin:8px 0 4px}
.dialog-symbol {text-align:center;font-size:44px;font-weight:600}
.dialog-sub {text-align:center;color:var(--muted);margin-bottom:20px;font-size:14px}
.dialog-metrics {display:flex;justify-content:space-around;text-align:center;margin:18px 0}
.dialog-metrics span {display:block;font-size:13px;color:var(--muted)}
.dialog-metrics strong {font-size:24px}
.dialog-box {background:var(--bg);border-radius:14px;padding:16px;margin:14px 0;line-height:1.65;font-size:14px}
@media(max-width:1200px){.svc-grid{grid-template-columns:repeat(3,1fr)}}
@media(max-width:1100px){.block-container {padding:1.5rem 1rem 5rem}}
@media(max-width:700px){.st-key-chat_panel{width:94vw}.svc-grid{grid-template-columns:1fr}}
</style>''')
if s.chat_open:
    markup('''<style>@media(min-width:1450px){[data-testid="stMain"] {margin-right:420px}} .st-key-chat_launcher{display:none}</style>''')


def set_scenarios(scenario_list):
    s.active_scenarios = list(scenario_list)
    s.generation += 1
    s.normal_streak = 0
    s.assessment = None
    s.ai_error = ''
    s.next_sample = 0.
    s.next_visual = 0.
    s.tick += 1
    s.snapshot = db.make_snapshot(s.active_scenarios, s.tick)
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
        s.report_notice = '로컬 LLM이 보고서를 작성하고 GitLab에 저장하고 있어요…'


def ask(question):
    if s.chat_future is not None:
        return
    context = {'latest_sample': ai.compact_snapshot(s.snapshot), 'last_assessment': s.assessment,
               'assessment_time': s.assessed_at, 'recent_messages': s.chat_history[-6:]}
    prompt = ('당신은 전자통관 인프라·보안·AP 품질관리 통합관제 도우미입니다. '
              '관측과 추정을 구분하고 실제 조치가 실행됐다고 단정하지 마세요. 한국어로 간결하게 답하세요.\n'
              + json.dumps(context, ensure_ascii=False) + '\n질문: ' + question)
    s.chat_history.append(('user', question))
    s.chat_future = pool.submit(ai.ask_ai_bot, prompt)


icon_buttons = {
    'nav_overview': 'home', 'nav_servers': 'server', 'nav_customs': 'service',
    'nav_alerts': 'bell', 'nav_reports': 'report',
    'run_toggle': 'pause' if s.running else 'play',
    'restore': 'refresh', 'open_chat': 'chat', 'close_chat': 'close',
}
markup('<style>' + ''.join(button_icon_css(key, icon) for key, icon in icon_buttons.items()) +
       '.st-key-close_chat button {min-width:38px;padding:8px}.st-key-close_chat button p {display:none}'
       '.st-key-close_chat button::before {margin:0}' + '</style>')

with st.sidebar:
    markup(
        '<div class="brand-box">'
        '<span class="brand-icon">' + icon_svg('server', 'white', 20) + '</span>'
        '<div class="brand-title">전자통관 AI 관제시스템</div>'
        '</div>'
        '<div class="brand-sub">인프라·보안·AP 품질관리 통합관제</div>'
    )
    for item, nav_key in [
        ('AI 대시보드', 'overview'),
        ('인프라 관리', 'servers'),
        ('관세행정 서비스품질', 'customs'),
        ('알림 기록', 'alerts')
    ]:
        if st.button(item, key='nav_' + nav_key, use_container_width=True,
                     type='primary' if s.menu == item else 'secondary'):
            s.menu = item
            st.rerun()
    with st.container(key='bottom_nav'):
        if st.button('자동 리포트', key='nav_reports', use_container_width=True,
                     type='primary' if s.menu == '자동 리포트' else 'secondary'):
            s.menu = '자동 리포트'
            st.rerun()

    st.divider()
    st.caption('로컬 LLM · 저장소 연동 점검')
    if st.button('로컬 LLM · GitLab 연결 테스트', use_container_width=True, disabled=s.integration_future is not None):
        def _run_checks():
            a_res = ai.check_ai()
            g_res = ai.check_gitlab()
            return f"{a_res['mode']}: {a_res['message']} | GitLab: {g_res['project']} ({g_res['branch']})"
        s.integration_future = pool.submit(_run_checks)
        st.rerun()
    if s.integration_future:
        st.info('연결 상태 확인 중…')
    if s.integration_result:
        st.caption(s.integration_result)


def render_controls():
    c1, c2, c3, _ = st.columns([1.1, 1.35, 1.0, 2.5])
    if c1.button('일시 정지' if s.running else '모니터링 시작', key='run_toggle',
                 type='primary', use_container_width=True):
        s.running = not s.running
        s.generation += 1
        s.next_sample = 0.
        s.next_visual = 0.
        st.rerun()
    with c2:
        with st.popover('🧪 이상 상황 테스트', use_container_width=True):
            st.markdown('**시뮬레이션할 장애/보안 유형 선택**')
            st.caption('복수 항목을 동시에 선택하여 복합 장애를 연출할 수 있습니다.')
            chk_cpu = st.checkbox('트래픽 폭주 / CPU 과부하 (95%+)', value='cpu_spike' in s.active_scenarios, key='chk_cpu')
            chk_db = st.checkbox('DB 커넥션 고갈 / WAS 5xx 오류 급증', value='db_error' in s.active_scenarios, key='chk_db')
            chk_sec = st.checkbox('WAF 비인가 IP 민감 경로 접근 탐지', value='security' in s.active_scenarios, key='chk_sec')
            if st.button('선택 시나리오 즉시 적용', type='primary', use_container_width=True, key='apply_scen'):
                selected = []
                if chk_cpu:
                    selected.append('cpu_spike')
                if chk_db:
                    selected.append('db_error')
                if chk_sec:
                    selected.append('security')
                set_scenarios(selected)
                st.rerun()
    if c3.button('정상 복구', key='restore', use_container_width=True, disabled=not s.active_scenarios):
        set_scenarios([])
        st.rerun()


def render_metrics():
    snap = s.snapshot
    values = [
        ('서버 CPU 사용률', f"{snap['cpu_pct']:g}%", f"메모리 {snap['memory_pct']:g}% · DB Conn {snap.get('db_conn_pct', 0):g}%", 'cpu', 'error' if snap['cpu_pct'] >= 90 else ''),
        ('AP 평균 응답 시간', f"{snap['latency_ms']:,}ms", f"초당 처리량 {snap['tps']} TPS", 'clock', 'error' if snap['latency_ms'] >= 2000 else ''),
        ('WEB 5xx 오류율', f"{snap['error_pct']:g}%", f"WAS 누적 오류 {snap['was_errors']}건", 'alert', 'error' if snap['error_pct'] >= 5 else ''),
        ('WAF 민감 경로 탐지', f"{snap['sensitive_hits']}건", f"최근 IP {snap['sample_ip']}", 'shield', 'error' if snap['sensitive_hits'] > 0 else '')
    ]
    for col, (label, value, sub, icon, state_cls) in zip(st.columns(4), values):
        with col:
            icon_class = f"kpi-icon {state_cls}".strip()
            markup(f'<div class="kpi"><div class="kpi-label"><span class="{icon_class}">{icon_svg(icon, size=22)}</span>{label}</div><div class="kpi-value">{value}</div><div class="kpi-sub">{sub}</div></div>')


def render_status():
    if s.ai_error:
        title, sub, cls = '로컬 LLM 분석 결과를 확인하지 못했어요', '정상으로 판정하지 않고 기존 상태를 유지합니다.', 'danger'
    elif s.ai_future:
        title, sub, cls = '로컬 LLM이 인프라·보안·AP 품질 상태를 분석하고 있어요', '최신 관측값과 파라미터·로그 패턴을 바탕으로 이상 징후를 검토합니다.', ''
    elif s.active_id:
        title, sub, cls = '이상 징후를 확인하고 있어요', f'연속 정상 확인 {s.normal_streak}/2 · 담당자 조치와 복구 상태를 확인하세요.', 'danger'
    elif not s.running:
        title, sub, cls = '모니터링을 시작해 보세요', '상단의 [모니터링 시작] 또는 [이상 상황 테스트] 버튼을 누르면 실시간 관제와 로컬 LLM 분석이 작동합니다.', 'idle'
    elif s.assessment:
        title, sub, cls = '최근 분석에서 정상 범위를 확인했어요', f'지표는 1초마다 갱신 · 다음 로컬 LLM 분석까지 {max(0, int(s.next_sample - time.monotonic()))}초', 'idle'
    else:
        title, sub, cls = '최신 데이터를 확인하고 있어요', '로컬 LLM 분석을 준비합니다.', 'idle'
    if ai.settings()['provider'] == 'demo':
        sub += ' (로컬 LLM 규칙 기반 시뮬레이션 모드)'
    icon = '<span class="spinner"></span>' if s.ai_future else icon_svg('spark', size=26)
    markup(f'<div class="ai-banner {cls}">{icon}<div>{esc(title)}<small>{esc(sub)}</small></div></div>')
    if s.ai_error:
        st.error(s.ai_error)


def render_overview_chart():
    fields = {
        '응답 시간': ('latency_ms', 'ms'),
        '서버 사용률': ('cpu_pct', '%'),
        '오류 비율': ('error_pct', '%'),
        'DB 커넥션': ('db_conn_pct', '%'),
        '보안 탐지 건수': ('sensitive_hits', '건')
    }
    left, right = st.columns([2.1, 1], gap='medium')
    with left, st.container(border=True):
        st.markdown('### ' + s.chart_choice + ' 추이')
        choice = st.selectbox('표시 지표', list(fields), key='chart_choice', label_visibility='collapsed')
        field, unit = fields[choice]
        frame = pd.DataFrame(s.samples)
        frame['시각'] = frame['timestamp'].str[11:19]
        base = alt.Chart(frame).encode(
            x=alt.X('시각:O', sort=None, title=None, axis=alt.Axis(labelAngle=0, values=frame['시각'].iloc[::max(1, len(frame) // 6)].tolist())),
            y=alt.Y(field + ':Q', title=unit, scale=alt.Scale(zero=True)),
            tooltip=[alt.Tooltip('시각:N'), alt.Tooltip(field + ':Q', title=choice + ' (' + unit + ')')])
        chart = (base.mark_area(color='#3182f6', opacity=.08) + base.mark_line(color='#3182f6', strokeWidth=2.6)).properties(height=250)
        st.altair_chart(chart, use_container_width=True)
        st.caption('최근 관측 추이 · 1초 간격 실시간 갱신 · KST')
    with right, st.container(border=True):
        markup('<div class="summary-title">' + icon_svg('spark', '#3182f6', 22) + f' 로컬 AI 상태 요약 · {esc(choice)}</div>')
        snap = s.snapshot
        metric_insights = {
            '응답 시간': f"현재 AP 평균 응답 지연 {snap['latency_ms']:,}ms ({'임계치 2,000ms 초과 · 병목 의심' if snap['latency_ms'] >= 2000 else '정상 응답 구간 유지'})",
            '서버 사용률': f"핵심 WAS CPU {snap['cpu_pct']:g}% · 메모리 {snap['memory_pct']:g}% ({'자원 포화 경계' if snap['cpu_pct'] >= 90 else '여유 자원 안정'})",
            '오류 비율': f"WEB 5xx 오류율 {snap['error_pct']:g}% · WAS 예외 {snap['was_errors']}건 ({'오류 급증 대응 필요' if snap['error_pct'] >= 5 else '오류율 정상'})",
            'DB 커넥션': f"Primary DB 커넥션 파라미터 점유율 {snap.get('db_conn_pct', 0):g}% ({'커넥션 풀 고갈 임박' if snap.get('db_conn_pct', 0) >= 85 else '세션 풀 안정'})",
            '보안 탐지 건수': f"WAF 민감 경로 접근 {snap['sensitive_hits']}건 · 최근 IP {snap['sample_ip']} ({'비인가 접근 차단 확인 필요' if snap['sensitive_hits'] > 0 else '보안 위협 미탐지'})"
        }
        rows = [metric_insights.get(choice, '')]
        if s.ai_error:
            rows.append('최근 로컬 LLM 정밀 분석 실패 · 상태 확인 필요')
        elif s.assessment:
            rows.append(s.assessment['summary'])
            if s.assessment['actions']:
                rows.append('확인 제안: ' + s.assessment['actions'][0])
        else:
            rows.append('상세 로컬 LLM 분석 대기 중입니다.')
        for row in rows:
            if row:
                markup('<div class="summary-row">' + esc(row) + '</div>')
        if s.assessed_at:
            markup('<div class="summary-meta">최근 분석 관측 시각 ' + esc(s.assessed_at[11:19]) + ' KST</div>')

    # 추가 패널: 3대 서버팜 상태 요약 & 핵심 런타임 파라미터 점유율
    p_left, p_right = st.columns([1.15, 1], gap='medium')
    with p_left, st.container(border=True):
        st.markdown('#### 3대 서버팜 실시간 헬스 요약')
        nodes = s.snapshot.get('farm_nodes', [])
        if nodes:
            ndf = pd.DataFrame(nodes)
            f_cols = st.columns(3)
            for fc, fname in zip(f_cols, ['관세행정', '유니패스', '전자상거래']):
                sub_df = ndf[ndf['farm'] == fname]
                crit_n = int((sub_df['status'] == '위험').sum())
                warn_n = int((sub_df['status'] == '주의').sum())
                avg_c = round(sub_df['cpu_pct'].mean(), 1)
                if crit_n > 0:
                    st_lbl, st_cls = f'위험 {crit_n}대', 'fb-crit'
                elif warn_n > 0:
                    st_lbl, st_cls = f'주의 {warn_n}대', 'fb-warn'
                else:
                    st_lbl, st_cls = '정상 운영', 'fb-ok'
                with fc:
                    markup(
                        f'<div style="border:1px solid var(--border);border-radius:14px;padding:14px;background:#fafbfc">'
                        f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">'
                        f'<span style="font-weight:800;font-size:15px">{esc(fname)}</span>'
                        f'<span class="farm-badge {st_cls}">{esc(st_lbl)}</span></div>'
                        f'<div style="font-size:12px;color:var(--ink-sub);font-weight:600">평균 CPU {avg_c}% · 10대 가동</div>'
                        f'</div>'
                    )

    with p_right, st.container(border=True):
        st.markdown('#### 핵심 AP · DB 런타임 파라미터 점유율')
        snap = s.snapshot
        thread_pct = min(99.0, round(snap['cpu_pct'] * 0.92, 1))
        db_pool_pct = snap.get('db_conn_pct', 38.0)
        heap_pct = snap['memory_pct']
        params = [
            ('WAS Thread Pool 점유율', thread_pct, thread_pct >= 85),
            ('DB Connection Pool 점유율', db_pool_pct, db_pool_pct >= 85),
            ('JVM Heap Memory 사용률', heap_pct, heap_pct >= 85),
        ]
        bars_html = []
        for p_name, p_val, is_crit in params:
            fill_cls = 'crit' if is_crit else ('warn' if p_val >= 75 else '')
            bars_html.append(
                f'<div class="bar-wrap">'
                f'<div class="bar-label"><span>{esc(p_name)}</span><span>{p_val}%</span></div>'
                f'<div class="bar-track"><div class="bar-fill {fill_cls}" style="width:{min(100, p_val)}%"></div></div>'
                f'</div>'
            )
        markup(''.join(bars_html))

    with st.container(border=True):
        st.markdown('#### 실시간 유입 웹 · WAF 보안 로그 스트림 (최근 8건)')
        recent_logs = []
        for item in reversed(s.samples[-8:]):
            recent_logs.append({
                '시각 (KST)': item['timestamp'][11:19],
                '출발지 IP': item['sample_ip'],
                '요청 경로 (URL)': item['sample_url'],
                'HTTP 상태': item['http_status'],
                'WAF 보안 탐지': f"탐지 ({item['sensitive_hits']}건)" if item['sensitive_hits'] > 0 else '정상',
                '응답 지연': f"{item['latency_ms']}ms"
            })
        st.dataframe(pd.DataFrame(recent_logs), hide_index=True, use_container_width=True)

    events = db.list_events()
    latest = ('최근 알림 없음' if not events else
              ('복구 확인' if events[0]['status'] == 'RESOLVED' else '이상 감지') + ' · ' + events[0]['detected_at'][11:19])
    markup('<div class="event-strip"><b>최근 이벤트 이력</b>　 ·　' + esc(latest) + '</div>')


def render_infra_management():
    """인프라 관리 전용 화면: 위험=빨간색, 주의=주황색 강조 적용."""
    nodes = s.snapshot.get('farm_nodes', [])
    if not nodes:
        st.info('서버팜 데이터를 불러오는 중입니다.')
        return

    df = pd.DataFrame(nodes)
    total_cnt = len(df)
    ok_cnt = int((df['status'] == '정상').sum())
    warn_cnt = int((df['status'] == '주의').sum())
    crit_cnt = int((df['status'] == '위험').sum())
    avg_cpu = round(df['cpu_pct'].mean(), 1)
    avg_mem = round(df['mem_pct'].mean(), 1)
    avg_disk = round(df['disk_pct'].mean(), 1)

    kpi_state = 'error' if crit_cnt > 0 else ('warn' if warn_cnt > 0 else '')
    kpis = [
        ('전체 관리 호스트', f"{total_cnt}대", f"정상 {ok_cnt} · 주의 {warn_cnt} · 위험 {crit_cnt}", 'server', kpi_state),
        ('전체 평균 CPU 사용률', f"{avg_cpu}%", f"최고 부하 노드 {df.loc[df['cpu_pct'].idxmax(), 'hostname']}", 'cpu', 'error' if avg_cpu >= 80 else ('warn' if avg_cpu >= 65 else '')),
        ('전체 평균 메모리 사용률', f"{avg_mem}%", f"최고 점유 노드 {df.loc[df['mem_pct'].idxmax(), 'hostname']}", 'traffic', ''),
        ('스토리지(Disk) 평균 점유', f"{avg_disk}%", 'SAN / NAS 볼륨 통합 평균', 'report', '')
    ]
    for col, (label, val, sub, ic, st_cls) in zip(st.columns(4), kpis):
        with col:
            ic_cls = f"kpi-icon {st_cls}".strip()
            markup(f'<div class="kpi"><div class="kpi-label"><span class="{ic_cls}">{icon_svg(ic, size=22)}</span>{label}</div><div class="kpi-value">{val}</div><div class="kpi-sub">{sub}</div></div>')

    st.markdown('### 서버팜별 자원 운영 현황')
    farm_cols = st.columns(3, gap='medium')
    for col, farm_name in zip(farm_cols, ['관세행정', '유니패스', '전자상거래']):
        fdf = df[df['farm'] == farm_name]
        f_cpu = round(fdf['cpu_pct'].mean(), 1)
        f_mem = round(fdf['mem_pct'].mean(), 1)
        f_disk = round(fdf['disk_pct'].mean(), 1)
        f_crit = int((fdf['status'] == '위험').sum())
        f_warn = int((fdf['status'] == '주의').sum())
        if f_crit > 0:
            badge_txt, badge_cls = f'위험 {f_crit}대', 'fb-crit'
        elif f_warn > 0:
            badge_txt, badge_cls = f'주의 {f_warn}대', 'fb-warn'
        else:
            badge_txt, badge_cls = '전 노드 정상', 'fb-ok'

        cpu_cls = 'crit' if f_cpu >= 80 else ('warn' if f_cpu >= 65 else '')
        mem_cls = 'crit' if f_mem >= 85 else ('warn' if f_mem >= 75 else '')
        with col:
            markup(f'''
            <div class="farm-card">
                <div class="farm-header">
                    <span class="farm-title">{esc(farm_name)} 서버팜</span>
                    <span class="farm-badge {badge_cls}">{esc(badge_txt)}</span>
                </div>
                <div class="farm-spec">WEB · WAS · DB 3계층 클러스터 운영</div>
                <div class="bar-wrap">
                    <div class="bar-label"><span>평균 CPU 사용률</span><span>{f_cpu}%</span></div>
                    <div class="bar-track"><div class="bar-fill {cpu_cls}" style="width:{min(100, f_cpu)}%"></div></div>
                </div>
                <div class="bar-wrap">
                    <div class="bar-label"><span>평균 메모리 사용률</span><span>{f_mem}%</span></div>
                    <div class="bar-track"><div class="bar-fill {mem_cls}" style="width:{min(100, f_mem)}%"></div></div>
                </div>
                <div class="bar-wrap" style="margin-bottom:0">
                    <div class="bar-label"><span>평균 디스크 사용률</span><span>{f_disk}%</span></div>
                    <div class="bar-track"><div class="bar-fill" style="width:{min(100, f_disk)}%"></div></div>
                </div>
            </div>
            ''')

    st.markdown('### 호스트별 상세 자원 모니터링 인벤토리')
    f_col1, f_col2, _ = st.columns([1.2, 1.2, 2.6])
    farm_filter = f_col1.selectbox('서버팜 선택', ['전체 서버팜', '관세행정', '유니패스', '전자상거래'], key='farm_filter_box')
    tier_filter = f_col2.selectbox('티어(계층) 구분', ['전체 계층', 'WEB', 'WAS', 'DB'], key='tier_filter_box')

    filtered_df = df.copy()
    if farm_filter != '전체 서버팜':
        filtered_df = filtered_df[filtered_df['farm'] == farm_filter]
    if tier_filter != '전체 계층':
        filtered_df = filtered_df[filtered_df['tier'] == tier_filter]

    with st.container(border=True):
        disp = filtered_df[['farm', 'tier', 'hostname', 'ip', 'cpu_pct', 'mem_pct', 'disk_pct', 'net_mbps', 'load_avg', 'sessions', 'uptime', 'status']].copy()
        disp.columns = ['서버팜', '계층', '호스트명', '내부 IP', 'CPU (%)', '메모리 (%)', '디스크 (%)', '네트워크 (Mbps)', 'Load Avg', '활성 세션', '가동시간', '상태']

        def _style_server_status(val):
            if val == '위험':
                return 'color: #f04452; background-color: #ffeeee; font-weight: 800;'
            if val == '주의':
                return 'color: #f57c00; background-color: #fff4e5; font-weight: 800;'
            if val == '정상':
                return 'color: #03b26c; font-weight: 700;'
            return ''

        styled_disp = disp.style.map(_style_server_status, subset=['상태'])
        st.dataframe(styled_disp, hide_index=True, use_container_width=True, height=460)


def render_customs_quality():
    """관세행정 서비스품질 전용 화면: 토스 모노톤 & 블루/레드 포인트 적용."""
    services = s.snapshot.get('customs_services', [])
    if not services:
        return

    total_cnt = sum(sv['count'] for sv in services)
    avg_lat = round(sum(sv['avg_ms'] for sv in services) / len(services))
    avg_succ = round(sum(sv['success_pct'] for sv in services) / len(services), 2)
    delayed_cnt = sum(1 for sv in services if sv['status'] != '원활')

    kpis = [
        ('금일 누적 행정 처리 건수', f"{total_cnt:,}건", '5대 핵심 관세 업무 합계', 'traffic', ''),
        ('평균 업무 처리 응답속도', f"{avg_lat:,}ms", '목표 SLA 500ms 이내', 'clock', 'error' if avg_lat >= 1000 else ''),
        ('평균 전자처리 성공률', f"{avg_succ}%", '오류 및 재전송 포함 집계', 'check', 'error' if avg_succ < 99.0 else ''),
        ('지연/주의 서비스 수', f"{delayed_cnt}개 / {len(services)}개", '실시간 임계치 감시 기준', 'alert', 'error' if delayed_cnt > 0 else '')
    ]
    for col, (label, val, sub, ic, st_cls) in zip(st.columns(4), kpis):
        with col:
            ic_cls = f"kpi-icon {st_cls}".strip()
            markup(f'<div class="kpi"><div class="kpi-label"><span class="{ic_cls}">{icon_svg(ic, size=22)}</span>{label}</div><div class="kpi-value">{val}</div><div class="kpi-sub">{sub}</div></div>')

    st.markdown('### 5대 핵심 관세행정 업무 실시간 품질 현황')
    cards_html = ['<div class="svc-grid">']
    for sv in services:
        if sv['status'] == '지연':
            pill_cls = 'fb-crit'
        elif sv['status'] == '주의':
            pill_cls = 'fb-warn'
        else:
            pill_cls = 'fb-ok'
        cards_html.append(
            f'<div class="svc-card">'
            f'<div class="svc-top"><span class="svc-name">{esc(sv["service_name"])}</span><span class="farm-badge {pill_cls}">{esc(sv["status"])}</span></div>'
            f'<div class="svc-code">{esc(sv["code"])} · SLA {sv["sla_ms"]}ms</div>'
            f'<div class="svc-val">{sv["count"]:,}건</div>'
            f'<div class="svc-sub">응답 <b>{sv["avg_ms"]:,}ms</b> · 성공률 <b>{sv["success_pct"]}%</b></div>'
            f'</div>'
        )
    cards_html.append('</div>')
    markup(''.join(cards_html))

    srv_df = pd.DataFrame(services)
    c_left, c_right = st.columns(2, gap='medium')
    with c_left, st.container(border=True):
        st.markdown('**업무별 누적 처리 건수 (건)**')
        bar_cnt = alt.Chart(srv_df).mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6, color='#3182f6').encode(
            x=alt.X('service_name:N', sort=None, title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y('count:Q', title='처리 건수'),
            tooltip=[alt.Tooltip('service_name:N', title='업무명'), alt.Tooltip('count:Q', title='처리 건수', format=',')]
        ).properties(height=230)
        st.altair_chart(bar_cnt, use_container_width=True)
    with c_right, st.container(border=True):
        st.markdown('**업무별 평균 처리 응답속도 (ms)**')
        bar_ms = alt.Chart(srv_df).mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6).encode(
            x=alt.X('service_name:N', sort=None, title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y('avg_ms:Q', title='응답속도 (ms)'),
            color=alt.condition(alt.datum.avg_ms >= 1000, alt.value('#f04452'), alt.value('#3182f6')),
            tooltip=[alt.Tooltip('service_name:N', title='업무명'), alt.Tooltip('avg_ms:Q', title='응답속도 (ms)', format=',')]
        ).properties(height=230)
        st.altair_chart(bar_ms, use_container_width=True)

    with st.container(border=True):
        st.markdown('**관세행정 서비스품질 상세 내역**')
        disp_df = srv_df[['service_name', 'code', 'sla_ms', 'count', 'avg_ms', 'success_pct', 'status']].copy()
        disp_df.columns = ['서비스 업무명', '업무 코드', '목표 SLA (ms)', '누적 처리 건수 (건)', '평균 응답속도 (ms)', '처리 성공률 (%)', '품질 상태']
        st.dataframe(disp_df, hide_index=True, use_container_width=True)


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
            answer = str(exc) if isinstance(exc, ai.IntegrationError) else '로컬 LLM 응답 처리 실패'
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
                s.ai_error = str(exc) if isinstance(exc, ai.IntegrationError) else '로컬 LLM 분석 처리 오류'
                s.normal_streak = 0
                if ai.settings()['provider'] == 'chatgpt':
                    s.running = False
                    full_refresh = True
    if s.running and time.monotonic() >= s.next_visual:
        s.tick += 1
        s.snapshot = db.make_snapshot(s.active_scenarios, s.tick)
        s.samples = (s.samples + [s.snapshot])[-180:]
        s.next_visual = time.monotonic() + 1
    if s.running and s.ai_future is None and time.monotonic() >= s.next_sample:
        snapshot = dict(s.snapshot)
        s.ai_future = (pool.submit(ai.assess, snapshot), snapshot, s.generation)
        s.next_sample = float('inf')
    if full_refresh:
        st.rerun()

    if s.menu == 'AI 대시보드':
        render_metrics()
        render_status()
        render_overview_chart()
    elif s.menu == '인프라 관리':
        render_infra_management()
    elif s.menu == '관세행정 서비스품질':
        render_customs_quality()


heading = {
    'AI 대시보드': 'AI 대시보드 · 통합 관제',
    '인프라 관리': '인프라 자원 관리',
    '관세행정 서비스품질': '관세행정 서비스품질 현황',
    '알림 기록': '알림 및 대응 기록',
    '자동 리포트': '자동 리포트 저장소'
}
scen_map = {'cpu_spike': 'CPU 폭주', 'db_error': 'DB/5xx 오류', 'security': 'WAF 보안 접근'}
scen_text = '시나리오: ' + ' + '.join(scen_map[x] for x in s.active_scenarios) if s.active_scenarios else '정상 시나리오'
markup(f'<div class="head"><h1>{heading.get(s.menu, "AI 대시보드 · 통합 관제")}</h1><div class="badge-group"><span class="badge ai">{esc(ai.provider_label())}</span><span class="badge">{esc(scen_text)}</span></div></div>')

if s.menu in ('AI 대시보드', '인프라 관리', '관세행정 서비스품질'):
    render_controls()
monitor()

if s.active_id and s.menu != '자동 리포트':
    with st.expander('진행 중인 이상 징후 · 담당자 조치 기록', expanded=s.show_action):
        if st.button('현재 이상 알림 다시 열기'):
            show_popup('alert', s.active_id, flash=False)
            st.rerun()
        with st.form('action_form'):
            note = st.text_input('수행한 조치 내용', placeholder='예: 유량 제어(Rate Limit) 적용 및 WAF 비인가 IP 차단 완료')
            if st.form_submit_button('조치 내용·현재 시각 저장'):
                if note.strip():
                    db.record_action(s.active_id, note)
                    st.success('조치 기록을 저장했어요.')
                else:
                    st.warning('조치 내용을 입력하세요.')

if s.menu == '알림 기록':
    events = db.list_events()
    if not events:
        st.info('아직 발생한 알림이 없어요.')
    for event in events:
        with st.expander(('복구 완료' if event['status'] == 'RESOLVED' else '확인 필요') + ' · ' + event['detected_at']):
            st.write(event['diagnosis']['summary'])
            st.caption(event['id'])
            st.write('탐지:', event['detected_at'], ' / 복구:', event['resolved_at'] or '확인 중')
            for action in event['actions']:
                st.write(action['recorded_at'] + ' · ' + action['note'])
            if st.button('알림 상세 보기', key='event_' + event['id']):
                show_popup('recovery' if event['status'] == 'RESOLVED' else 'alert', event['id'], False)
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
        title, close = st.columns([5, 1])
        with title:
            markup('<div class="chat-title">로컬 AI 운영 도우미</div>')
        if close.button('닫기', key='close_chat', help='상담창 닫기'):
            s.chat_open = False
            st.rerun()
        if not s.chat_history:
            markup('<div class="chat-empty"><div class="chat-symbol">' + icon_svg('chat', '#3182f6', 64) + '</div><h3>무엇을 확인할까요?</h3></div>')
            for question in ['현재 인프라 및 WAF 보안 상태 요약', '가장 부하가 높은 서버팜 분석', '현재 상황 권장 대응 절차']:
                if st.button(question, key='suggest_' + question, use_container_width=True, disabled=s.chat_future is not None):
                    ask(question)
                    st.rerun()
        else:
            if st.button('← 초기 화면으로', key='chat_back_home', use_container_width=True, disabled=s.chat_future is not None):
                s.chat_history = []
                st.rerun()
            with st.container(height=360):
                for role, message in s.chat_history:
                    with st.chat_message(role):
                        st.markdown(message)
        if s.chat_future:
            st.info('로컬 LLM이 답변을 작성하고 있어요…')
        with st.form('chat_form', clear_on_submit=True):
            question = st.text_area('궁금한 내용을 입력하세요', height=88)
            if st.form_submit_button('보내기', type='primary', use_container_width=True, disabled=s.chat_future is not None) and question.strip():
                ask(question.strip())
                st.rerun()
else:
    with st.container(key='chat_launcher'):
        if st.button('AI에게 물어보기', key='open_chat', use_container_width=True):
            s.chat_open = True
            st.rerun()


def popup_css(kind):
    color = '240,68,82' if kind == 'alert' else '3,178,108'
    solid = '#f04452' if kind == 'alert' else '#03b26c'
    elapsed = max(0., 5 - (s.flash_until - time.time()))
    animation = (f'incidentPulse 1s ease-in-out 5;animation-delay:-{elapsed:.3f}s;'
                 'animation-fill-mode:forwards') if elapsed < 5 else 'none'
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
    [data-testid="stDialog"] .dialog-heading {{color:{solid};font-size:28px}}
    [data-testid="stDialog"] .dialog-box {{background:rgba({color},.06)}}
    .st-key-close_recovery button {{color:{solid}!important;border-color:rgba({color},.35)!important}}
    </style>''')


@st.dialog('상태 알림', width='small', dismissible=False)
def incident_dialog(kind, event_id):
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
    color = '#f04452' if is_alert else '#03b26c'
    if is_alert:
        if snap.get('sensitive_hits', 0) > 0:
            title = 'WAF 보안 민감 경로 접근 탐지'
        elif snap['latency_ms'] >= 2000:
            title = 'AP 응답이 느려졌어요'
        else:
            title = '이상 징후를 발견했어요'
    else:
        title = '정상 상태로 돌아왔어요'
    symbol = icon_svg("alert" if is_alert else "check", color, 54)
    markup(f'<div class="dialog-symbol" style="color:{color}">{symbol}</div><div class="dialog-heading">{title}</div><div class="dialog-sub">{"로컬 LLM이 확인한 이상 징후" if is_alert else "연속 2회 정상 확인"}</div>')
    markup(f'<div class="dialog-metrics"><div><span>AP 응답 시간</span><strong>{snap["latency_ms"]:,}ms</strong></div><div><span>서버 CPU</span><strong>{snap["cpu_pct"]:g}%</strong></div><div><span>WAF/5xx</span><strong>{snap["sensitive_hits"]}건 / {snap["error_pct"]:g}%</strong></div></div>')
    if is_alert:
        st.write(event['diagnosis']['summary'])
        actions = ''.join('<div>• ' + esc(a) + '</div>' for a in event['diagnosis']['actions'])
        markup('<div class="dialog-box"><b>권장 확인 사항</b>' + actions + '</div>')
        st.caption(event['diagnosis']['source'] + ' · 탐지 ' + event['detected_at'][11:19] + ' KST')
        if st.button('조치 기록 · 모니터링 계속', key='ack_alert', type='primary', use_container_width=True):
            s.show_action = True
            s.popup = None
            st.rerun()
    else:
        notes = '<br>'.join(esc(a['recorded_at'][11:19] + ' · ' + a['note']) for a in event['actions']) or '담당자 조치 기록 없음'
        markup('<div class="dialog-box">발생 ' + esc(event['detected_at']) + '<br>복구 ' + esc(event['resolved_at']) + '<br>' + notes + '</div>')
        if event['commit']:
            st.success('GitLab에 보고서를 저장했어요.')
            st.link_button('저장된 보고서 열기', event['commit']['web_url'])
        else:
            if st.button('GitLab 저장 재시도' if event['report'] else '자동 리포트 생성', key='generate_report', type='primary', use_container_width=True, disabled=s.report_future is not None):
                submit_report(event_id)
                st.rerun()
        if s.report_event == event_id and s.report_notice:
            st.info(s.report_notice)
        if event['report_error']:
            st.error(event['report_error'])
        if event['report']:
            with st.expander('보고서 미리보기'):
                st.markdown(event['report'])
            st.download_button('보고서 다운로드', event['report'], file_name=event['id'] + '.md')
        if st.button('닫기', key='close_recovery', use_container_width=True):
            s.popup = None
            st.rerun()


if s.popup:
    incident_dialog(*s.popup)
