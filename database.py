"""SQLite event history + multi-farm infrastructure (30 nodes) + customs service quality data."""
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
            'summary': '민원 집중 시간대 트래픽 증가로 관세행정 WAS-01 CPU 사용률이 임계치를 초과했습니다.',
            'reasons': ['CPU 과부하 (95.2%)', '응답 지연 심화 (2,750ms)'],
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


def _build_farm_nodes(cpu, mem, db_conn, tps, is_cpu, is_db, is_sec, tick):
    """관세행정 · 유니패스 · 전자상거래 3개 서버팜 (각 WEB 4대, WAS 4대, DB 2대 = 총 30대) 자원 생성."""
    farms = [
        ('관세행정', 'CUS', '10.10', 1.00),
        ('유니패스', 'UNI', '10.20', 0.92),
        ('전자상거래', 'ECM', '10.30', 0.86),
    ]
    all_nodes = []
    for farm_name, code, subnet, scale in farms:
        # WEB 4대
        for idx in range(1, 5):
            jitter = ((idx * 3 + tick) % 7 - 3) * 1.4
            n_cpu = round(min(99.0, max(8.0, cpu * 0.58 * scale + jitter)), 1)
            n_mem = round(min(96.0, max(22.0, mem * 0.68 * scale + jitter * 0.8)), 1)
            n_disk = round(34.0 + idx * 4.5 + (scale * 5), 1)
            n_net = round(max(12.0, (tps * 0.42 * scale) + jitter * 3), 1)
            n_load = round(n_cpu / 25.0, 2)
            st = '주의' if (is_sec and farm_name == '관세행정' and idx == 1) else ('주의' if n_cpu >= 80 else '정상')
            all_nodes.append({
                'farm': farm_name,
                'tier': 'WEB',
                'hostname': f'{code}-WEB-0{idx}',
                'ip': f'{subnet}.1.{10 + idx}',
                'os': 'RHEL 8.9 (Nginx)',
                'cpu_pct': n_cpu,
                'mem_pct': n_mem,
                'disk_pct': n_disk,
                'net_mbps': n_net,
                'load_avg': n_load,
                'sessions': round(tps * 0.65 * scale) + idx * 12,
                'uptime': f'{42 + idx * 7}일',
                'status': st,
            })
        # WAS 4대
        for idx in range(1, 5):
            jitter = ((idx * 5 + tick) % 9 - 4) * 1.8
            boost = 1.0 if (farm_name == '관세행정' and idx <= 2 and (is_cpu or is_db)) else scale
            n_cpu = round(min(99.2, max(12.0, cpu * boost + jitter)), 1)
            n_mem = round(min(97.0, max(30.0, mem * boost + jitter * 0.9)), 1)
            n_disk = round(48.0 + idx * 5.2 + (scale * 6), 1)
            n_net = round(max(18.0, (tps * 0.55 * boost) + jitter * 4), 1)
            n_load = round(n_cpu / 18.0, 2)
            if n_cpu >= 90 or (is_db and farm_name == '관세행정' and idx <= 2):
                st = '위험'
            elif n_cpu >= 78 or is_db or is_cpu:
                st = '주의'
            else:
                st = '정상'
            all_nodes.append({
                'farm': farm_name,
                'tier': 'WAS',
                'hostname': f'{code}-WAS-0{idx}',
                'ip': f'{subnet}.2.{20 + idx}',
                'os': 'RHEL 8.9 (JEUS 8)',
                'cpu_pct': n_cpu,
                'mem_pct': n_mem,
                'disk_pct': n_disk,
                'net_mbps': n_net,
                'load_avg': n_load,
                'sessions': round(tps * 0.45 * boost) + idx * 8,
                'uptime': f'{28 + idx * 5}일',
                'status': st,
            })
        # DB 2대 (Active / Standby 구성)
        for idx in range(1, 3):
            role_tag = 'Active' if idx == 1 else 'Standby'
            role_factor = 1.0 if idx == 1 else 0.45
            jitter = ((idx * 2 + tick) % 5 - 2) * 1.2
            boost = 1.0 if (farm_name == '관세행정' and idx == 1 and (is_db or is_cpu)) else scale * role_factor
            n_cpu = round(min(97.5, max(10.0, db_conn * 0.88 * boost + jitter)), 1)
            n_mem = round(min(96.5, max(35.0, mem * 1.03 * (1.0 if idx == 1 else 0.78) + jitter)), 1)
            n_disk = round(64.0 + idx * 7.5 + (scale * 8), 1)
            n_net = round(max(25.0, (tps * 0.85 * boost) + jitter * 5), 1)
            n_load = round(n_cpu / 16.0, 2)
            if (is_db and farm_name == '관세행정' and idx == 1) or n_cpu >= 88:
                st = '위험'
            elif n_cpu >= 75:
                st = '주의'
            else:
                st = '정상'
            all_nodes.append({
                'farm': farm_name,
                'tier': 'DB',
                'hostname': f'{code}-DB-0{idx} ({role_tag})',
                'ip': f'{subnet}.3.{30 + idx}',
                'os': 'RHEL 8.9 (Tibero 7)',
                'cpu_pct': n_cpu,
                'mem_pct': n_mem,
                'disk_pct': n_disk,
                'net_mbps': n_net,
                'load_avg': n_load,
                'sessions': round(db_conn * 1.8 * role_factor),
                'uptime': f'{110 + idx * 14}일',
                'status': st,
            })
    return all_nodes


def make_snapshot(scenario='normal', tick=0):
    """다중 시나리오(복합 체크 지원), 30대 서버팜 자원 및 관세행정 서비스품질 합성 데이터 생성."""
    if isinstance(scenario, bool):
        active_scenarios = {'cpu_spike'} if scenario else set()
    elif isinstance(scenario, (list, set, tuple)):
        active_scenarios = set(scenario)
    elif scenario and scenario != 'normal':
        active_scenarios = {scenario}
    else:
        active_scenarios = set()

    is_cpu = 'cpu_spike' in active_scenarios
    is_db = 'db_error' in active_scenarios
    is_sec = 'security' in active_scenarios

    wave = .65 * math.sin(tick / 7) + .35 * math.sin(tick * 1.7)
    slow_wave = math.sin(tick / 17)

    cpu = round(36.5 + 6.5 * wave, 1)
    mem = round(58.0 + 2.0 * slow_wave, 1)
    tps = round(125 + 18 * wave)
    err = round(max(0.05, 0.18 + 0.07 * wave), 2)
    lat = round(178 + 32 * wave)
    db_conn = round(38.0 + 3.0 * slow_wave, 1)
    sec_hits = 0
    was_err = 0
    ip = '192.0.2.' + str(10 + (tick % 40))
    normal_urls = [
        '/csp/main/index.do',
        '/clip/cargo/trackStatus.do',
        '/rip/refund/checkEligibility.do',
        '/csp/edi/receiveDoc.do',
        '/clip/import/declarationView.do',
        '/rip/notice/billStatus.do',
    ]
    url = normal_urls[tick % len(normal_urls)]
    status = 200

    if is_cpu:
        cpu = round(min(98.5, 95.2 + 2.8 * wave), 1)
        mem = max(mem, round(84.5 + 2.5 * slow_wave, 1))
        tps = round(430 + 40 * wave)
        err = max(err, round(1.8 + 0.6 * wave, 2))
        lat = max(lat, round(2750 + 380 * wave))
        db_conn = max(db_conn, round(72.0 + 4.0 * slow_wave, 1))
        was_err += max(2, round(6 + 2 * wave))
        ip = '203.0.113.45'
        cpu_urls = [
            '/csp/clearance/batchProcess.do',
            '/clip/manifest/bulkQuery.do',
            '/rip/tax/calculateBatch.do',
        ]
        url = cpu_urls[tick % len(cpu_urls)]
        status = 504 if tick % 4 == 0 else 200

    if is_db:
        cpu = max(cpu, round(76.0 + 5.0 * wave, 1))
        mem = max(mem, round(88.0 + 2.0 * slow_wave, 1))
        tps = max(tps, round(190 + 25 * wave))
        err = round(8.6 + 1.4 * wave, 2)
        lat = max(lat, round(2420 + 310 * wave))
        db_conn = round(min(99.0, 92.5 + 4.5 * wave), 1)
        was_err += max(5, round(18 + 5 * wave))
        ip = '198.51.100.88'
        db_urls = [
            '/csp/declarations/submit.do',
            '/clip/bill/createNotice.do',
            '/rip/refund/approveDbTx.do',
        ]
        url = db_urls[tick % len(db_urls)]
        status = 503 if tick % 2 == 0 else 500

    if is_sec:
        sec_hits = 3 + (tick % 3)
        ip = '211.234.110.55'
        suspicious_urls = [
            '/csp/cgi-bin/download.do?file=../../../../etc/passwd',
            '/clip/admin/config/.env',
            "/rip/api/userInfo.do?id=1' OR '1'='1",
        ]
        url = suspicious_urls[tick % len(suspicious_urls)]
        status = 403

    scen_key = '+'.join(sorted(active_scenarios)) if active_scenarios else 'normal'
    farm_nodes = _build_farm_nodes(cpu, mem, db_conn, tps, is_cpu, is_db, is_sec, tick)

    # 관세행정 5대 핵심 서비스품질 지표
    delay_factor = 6.5 if (is_cpu or is_db) else 1.0
    err_penalty = 4.2 if is_db else (0.8 if is_cpu else 0.0)
    customs_services = [
        {
            'service_name': '수입신고',
            'code': 'IMP-DEC',
            'sla_ms': 500,
            'count': round(1420 + tick * 7 + (320 if is_cpu else 0)),
            'avg_ms': round((210 + 18 * wave) * delay_factor),
            'success_pct': round(max(91.0, 99.92 - err_penalty * 0.9), 2),
            'status': '지연' if (is_cpu or is_db) else '원활'
        },
        {
            'service_name': '전자문서 송수신',
            'code': 'EDI-MSG',
            'sla_ms': 300,
            'count': round(3850 + tick * 15 + (610 if is_cpu else 0)),
            'avg_ms': round((145 + 12 * wave) * (4.8 if is_cpu else 1.0)),
            'success_pct': round(max(94.5, 99.98 - err_penalty * 0.4), 2),
            'status': '주의' if is_cpu else '원활'
        },
        {
            'service_name': '고지서 생성',
            'code': 'BIL-GEN',
            'sla_ms': 600,
            'count': round(960 + tick * 4 + (110 if is_db else 0)),
            'avg_ms': round((310 + 25 * wave) * (7.2 if is_db else (2.1 if is_cpu else 1.0))),
            'success_pct': round(max(89.5, 99.89 - err_penalty * 1.3), 2),
            'status': '지연' if is_db else '원활'
        },
        {
            'service_name': '화물자동수리',
            'code': 'CRG-CLR',
            'sla_ms': 400,
            'count': round(2140 + tick * 9 + (450 if is_cpu else 0)),
            'avg_ms': round((185 + 15 * wave) * delay_factor),
            'success_pct': round(max(92.0, 99.95 - err_penalty * 0.7), 2),
            'status': '지연' if (is_cpu or is_db) else '원활'
        },
        {
            'service_name': '환급심사',
            'code': 'DRB-REV',
            'sla_ms': 800,
            'count': round(540 + tick * 2),
            'avg_ms': round((420 + 30 * wave) * (5.5 if is_db else 1.0)),
            'success_pct': round(max(93.0, 99.91 - err_penalty * 0.8), 2),
            'status': '주의' if is_db else '원활'
        }
    ]

    return {
        'timestamp': now(),
        'scenario': scen_key,
        'active_scenarios': sorted(active_scenarios),
        'service': 'CUS-WAS-01',
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
        'farm_nodes': farm_nodes,
        'customs_services': customs_services
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
