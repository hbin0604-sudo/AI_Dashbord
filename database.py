"""SQLite event history + deterministic synthetic measurements."""
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


def make_snapshot(abnormal=False, tick=0):
    """Illustrative correlated load, not measured production data or universal thresholds.

    Normal: CPU ~30–45%, 150–240ms; stressed: CPU ~92–98%, ~2.4–3.2s.
    The scenario changes promptly for presentation, with natural within-state variation.
    """
    wave = .65 * math.sin(tick / 7) + .35 * math.sin(tick * 1.7)
    cpu = round(min(98, 96 + 3 * wave) if abnormal else 38 + 7 * wave, 1)
    return {'timestamp': now(), 'service': 'WAS-DEMO-01', 'synthetic': True,
            'cpu_pct': cpu,
            'memory_pct': round((85 if abnormal else 59) + 2 * math.sin(tick / 17), 1),
            'tps': round((420 if abnormal else 120) + (35 if abnormal else 20) * wave),
            'error_pct': round((8.4 if abnormal else .2) + (1.5 if abnormal else .08) * wave, 2),
            'latency_ms': round((2800 if abnormal else 186) + (350 if abnormal else 40) * wave),
            'sensitive_hits': 0,
            'was_errors': max(1, round(14 + 4 * wave)) if abnormal else 0,
            'sample_ip': '198.51.100.20' if abnormal else '192.0.2.10',
            'sample_url': '/api/declarations' if abnormal else '/health',
            'http_status': 503 if abnormal else 200}


def transition(active_id, streak, snapshot, assessment):
    """Only fresh successful assessments enter here. Two normal samples to recover."""
    from ai_engine import evidence
    if assessment['anomaly']:
        if not active_id:
            event = new_event(snapshot, assessment)
            return event['id'], 0, ('alert', event['id'])
        return active_id, 0, None
    # LLM false-negative cannot resolve when deterministic evidence remains high.
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
    # Called on a worker, never from the dialog render path.
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
            save_event(event)  # Preserve AI result even if GitLab is unreachable.
        commit = commit_report(event_id, event['report'])
        event.update(commit=commit, report_error=None)
        save_event(event)
        return commit
    except IntegrationError as exc:
        event['report_error'] = str(exc)
        save_event(event)
        raise
