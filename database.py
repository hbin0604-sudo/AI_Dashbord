"""SQLite event history + multi-scenario deterministic synthetic measurements."""
import json
import math
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path

KST = timezone(timedelta(hours=9))


def now():
    return datetime.now(KST).isoformat(timespec='seconds')


def db_path():
    return Path(os.getenv('DASHBOARD_DB', str(Path(__file__).with_name('dashboard_events.db'))))


@contextmanager
def connect():
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    try:
        conn.execute('PRAGMA journal_mode=WAL')
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with connect() as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, data TEXT NOT NULL, updated_at TEXT NOT NULL)')


def save_event(event):
    with connect() as conn:
        conn.execute('INSERT INTO events VALUES (?, ?, ?) ON CONFLICT(id) DO UPDATE SET data=excluded.data, updated_at=excluded.updated_at',
                     (event['id'], json.dumps(event, ensure_ascii=False), now()))


def get_event(event_id):
    with connect() as conn:
        row = conn.execute('SELECT data FROM events WHERE id=?', (event_id,)).fetchone()
    return json.loads(row[0]) if row else None


def list_events():
    with connect() as conn:
        rows = conn.execute('SELECT data FROM events ORDER BY updated_at DESC LIMIT 200').fetchall()
    return [json.loads(row[0]) for row in rows]


def seed_initial_history():
    """초기 시연 시 알림 기록 및 자동 리포트 탭이 비어 보이지 않도록 과거 완료 이력 1건을 샘플로 삽입합니다."""
    if list_events():
        return
    base_time = datetime.now(KST) - timedelta(hours=2)
    detected = base_time.isoformat(timespec='seconds')
    resolved = (base_time + timedelta(minutes=8)).isoformat(timespec='seconds')
    evt_id = 'EVT-' + base_time.strftime('%Y%m%d-%H%M%S-') + 'demo01'
    snap = make_snapshot('cpu_spike', 10)
    snap['timestamp'] = detected
    rec_snap = make_snapshot('normal', 25)
    rec_snap['timestamp'] = resolved
    sample_event = {
        'id': evt_id,
        'detected_at': detected,
        'status': 'RESOLVED',
        'snapshot': snap,
        'diagnosis': {
            'anomaly': True,
            'summary': '민원 집중 시간대 트래픽 증가로 WAS-CORE-01 CPU 사용률이 임계치를 초과했습니다.',
            'reasons': ['CPU 과부하 (94.2%)', '응답 지연 심화 (2,640ms)'],
            'actions': [
                'CPU 상위 점유 프로세스 및 WAS 스레드 풀 상태를 확인하세요.',
                '유량 제어(Rate Limiting) 정책 적용 여부를 점검하세요.'
            ],
            'source': 'DEMO · 초기 시연 샘플'
        },
        'actions': [{
            'recorded_at': (base_time + timedelta(minutes=3)).isoformat(timespec='seconds'),
            'note': '대량 조회 API 캐싱 TTL 상향 및 유휴 커넥션 정리 수행',
            'kind': '담당자 입력 (초기 시연 데이터)'
        }],
        'resolved_at': resolved,
        'recovery_snapshot': rec_snap,
        'recovery_assessment': {
            'anomaly': False,
            'summary': '모든 인프라 및 보안 지표가 정상 범위 내에 있습니다.',
            'reasons': [],
            'actions': [],
            'source': 'DEMO · 초기 시연 샘플'
        },
        'report': '',
        'report_generated_at': None,
        'commit': None,
        'report_error': None
    }
    save_event(sample_event)


def new_event(snapshot, diagnosis):
    event = {'id': 'EVT-' + datetime.now(KST).strftime('%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:8],
             'detected_at': now(), 'status': 'OPEN', 'snapshot': snapshot,
             'diagnosis': diagnosis, 'actions': [], 'resolved_at': None,
             'recovery_snapshot': None, 'recovery_assessment': None,
             'report': '', 'report_generated_at': None, 'commit': None, 'report_error': None}
    save_event(event)
    return event


def record_action(event_id, note):
    event = get_event(event_id)
    if not event or event['status'] != 'OPEN':
        raise ValueError('진행 중인 이벤트만 조치를 기록할 수 있습니다.')
    if not note.strip():
        raise ValueError('조치 내용을 입력하세요.')
    event['actions'].append({'recorded_at': now(), 'note': note.strip()[:2000],
                             'kind': '담당자 입력 (실제 서버 수행 여부는 별도 확인)'})
    save_event(event)
    return event


def resolve_event(event_id, snapshot, assessment):
    event = get_event(event_id)
    if event['status'] == 'OPEN':
        event.update(status='RESOLVED', resolved_at=now(), recovery_snapshot=snapshot,
                     recovery_assessment=assessment)
        save_event(event)
    return event


def make_snapshot(scenario='normal', tick=0):
    """4가지 시나리오별 상관관계가 반영된 합성 인프라·보안 관측 데이터 생성.
    
    scenario:
      - 'normal': 정상 운영 상태
      - 'cpu_spike': 트래픽 폭주 및 CPU 과부하 (CPU 92~98%, 응답 지연 2.4~3.2s)
      - 'db_error': DB 커넥션 고갈 및 WAS 5xx 오류 급증 (5xx 7~10%, DB Conn 88~96%)
      - 'security': 외부 비인가 IP의 민감 경로 접근 탐지 (sensitive_hits > 0)
    """
    if isinstance(scenario, bool):
        scenario = 'cpu_spike' if scenario else 'normal'

    wave = .65 * math.sin(tick / 7) + .35 * math.sin(tick * 1.7)
    slow_wave = math.sin(tick / 17)

    if scenario == 'cpu_spike':
        cpu = round(min(98.5, 95.2 + 2.8 * wave), 1)
        mem = round(84.5 + 2.5 * slow_wave, 1)
        tps = round(430 + 40 * wave)
        err = round(1.8 + 0.6 * wave, 2)
        lat = round(2750 + 380 * wave)
        db_conn = round(72.0 + 4.0 * slow_wave, 1)
        sec_hits = 0
        was_err = max(2, round(6 + 2 * wave))
        ip = '203.0.113.45'
        url = '/api/v1/customs/clearance-batch'
        status = 504 if tick % 4 == 0 else 200
    elif scenario == 'db_error':
        cpu = round(76.0 + 5.0 * wave, 1)
        mem = round(88.0 + 2.0 * slow_wave, 1)
        tps = round(190 + 25 * wave)
        err = round(8.6 + 1.4 * wave, 2)
        lat = round(2420 + 310 * wave)
        db_conn = round(min(99.0, 92.5 + 4.5 * wave), 1)
        sec_hits = 0
        was_err = max(5, round(18 + 5 * wave))
        ip = '198.51.100.88'
        url = '/api/v1/declarations/submit'
        status = 503 if tick % 2 == 0 else 500
    elif scenario == 'security':
        cpu = round(42.0 + 6.0 * wave, 1)
        mem = round(61.0 + 2.0 * slow_wave, 1)
        tps = round(145 + 22 * wave)
        err = round(1.2 + 0.4 * wave, 2)
        lat = round(215 + 35 * wave)
        db_conn = round(44.0 + 3.0 * slow_wave, 1)
        sec_hits = 3 + (tick % 3)
        was_err = 0
        ip = '211.234.110.55'
        suspicious_urls = [
            '/cgi-bin/vulnerable.cgi?file=/etc/passwd',
            '/admin/config/.env',
            "/api/user?id=1' OR '1'='1"
        ]
        url = suspicious_urls[tick % len(suspicious_urls)]
        status = 403
    else:  # 'normal'
        cpu = round(36.5 + 6.5 * wave, 1)
        mem = round(58.0 + 2.0 * slow_wave, 1)
        tps = round(125 + 18 * wave)
        err = round(max(0.05, 0.18 + 0.07 * wave), 2)
        lat = round(178 + 32 * wave)
        db_conn = round(38.0 + 3.0 * slow_wave, 1)
        sec_hits = 0
        was_err = 0
        ip = '192.0.2.' + str(10 + (tick % 40))
        normal_urls = ['/health', '/api/v1/status', '/api/v1/cargo/track', '/index.do']
        url = normal_urls[tick % len(normal_urls)]
        status = 200

    # 다중 노드별 세부 상태 생성
    nodes = [
        {
            'node': 'WEB-FRONT-01',
            'role': 'Nginx Reverse Proxy',
            'cpu': round(max(12.0, cpu * 0.65), 1),
            'mem': round(max(25.0, mem * 0.72), 1),
            'conn': round(tps * 2.4),
            'status': '주의' if scenario == 'security' else ('과부하' if cpu >= 90 else '정상')
        },
        {
            'node': 'WAS-CORE-01',
            'role': 'Main Business WAS',
            'cpu': cpu,
            'mem': mem,
            'conn': round(tps * 1.2),
            'status': '위험' if (cpu >= 90 or err >= 5) else '정상'
        },
        {
            'node': 'WAS-CORE-02',
            'role': 'Secondary Business WAS',
            'cpu': round(max(15.0, cpu * 0.88), 1),
            'mem': round(max(30.0, mem * 0.91), 1),
            'conn': round(tps * 1.1),
            'status': '주의' if (cpu >= 90 or err >= 5) else '정상'
        },
        {
            'node': 'DB-MAIN-01',
            'role': 'Primary RDBMS',
            'cpu': round(min(96.0, db_conn * 0.85), 1),
            'mem': round(min(95.0, mem * 1.02), 1),
            'conn': f"{db_conn}%",
            'status': '위험' if db_conn >= 85 else '정상'
        }
    ]

    return {
        'timestamp': now(),
        'scenario': scenario,
        'service': 'WAS-CORE-01',
        'synthetic': True,
        'cpu_pct': cpu,
        'memory_pct': mem,
        'tps': tps,
        'error_pct': err,
        'latency_ms': lat,
        'db_conn_pct': db_conn,
        'sensitive_hits': sec_hits,
        'was_errors': was_err,
        'sample_ip': ip,
        'sample_url': url,
        'http_status': status,
        'nodes': nodes
    }


def transition(active_id, streak, snapshot, assessment):
    """Only fresh successful assessments enter here. Two normal samples to recover."""
    from ai_engine import evidence
    if assessment['anomaly']:
        if not active_id:
            event = new_event(snapshot, assessment)
            return event['id'], 0, ('alert', event['id'])
        return active_id, 0, None
    if evidence(snapshot):
        return active_id, 0, None
    if active_id:
        streak += 1
        if streak >= 2:
            resolve_event(active_id, snapshot, assessment)
            return None, 0, ('recovery', active_id)
        return active_id, streak, None
    return None, 0, None


def create_and_commit_report(event_id):
    from ai_engine import report_text, commit_report, IntegrationError
    event = get_event(event_id)
    if not event or event['status'] != 'RESOLVED':
        raise IntegrationError('복구가 확인된 이벤트만 보고서를 생성할 수 있습니다.')
    if event['commit']:
        return event['commit']
    try:
        if not event['report']:
            event['report'] = report_text(event)
            event['report_generated_at'] = now()
            save_event(event)
        commit = commit_report(event_id, event['report'])
        event.update(commit=commit, report_error=None)
        save_event(event)
        return commit
    except IntegrationError as exc:
        event['report_error'] = str(exc)
        save_event(event)
        raise
