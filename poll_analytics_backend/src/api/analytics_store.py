import sqlite3
from datetime import datetime
from typing import List, Optional, Dict, Tuple

from .analytics_models import PollEventIn, PollEventDb, EventFilter, PollAnalyticsSummary

DB_PATH = "analytics_events.db"


def _get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def _init_db():
    """Initializes the analytics db/tables if not exist."""
    conn = _get_connection()
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS poll_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id TEXT NOT NULL,
        poll_id TEXT NOT NULL,
        event_type TEXT NOT NULL,
        user_choice TEXT,
        timestamp TEXT NOT NULL,
        user_id TEXT,
        session_id TEXT,
        device_type TEXT,
        platform TEXT,
        app_version TEXT,
        geo TEXT,
        additional TEXT,
        received_at TEXT NOT NULL
    );
    """)
    c.execute("""
    CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_eventid ON poll_events(event_id);
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_pollid_type_ts ON poll_events(poll_id, event_type, timestamp);")
    conn.commit()
    conn.close()


_init_db()


# PUBLIC_INTERFACE
def log_event(event: PollEventIn) -> Tuple[bool, bool, Optional[str]]:
    """
    Stores the event in db. Deduplicates on event_id.
    Returns: (was_deduplicated, was_stored, reason)
    """
    conn = _get_connection()
    c = conn.cursor()
    # dedup: check if event_id already exists
    c.execute("SELECT id FROM poll_events WHERE event_id=?", (event.event_id,))
    if c.fetchone():
        conn.close()
        return True, False, "Duplicate event"

    # Store the event
    try:
        c.execute("""
        INSERT INTO poll_events (
            event_id, poll_id, event_type, user_choice, timestamp,
            user_id, session_id, device_type, platform, app_version, geo, additional, received_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event.event_id,
            event.poll_id,
            event.event_type,
            event.user_choice,
            event.timestamp.isoformat(),
            event.metadata.user_id,
            event.metadata.session_id,
            event.metadata.device_type,
            event.metadata.platform,
            event.metadata.app_version,
            event.metadata.geo,
            str(event.metadata.additional) if event.metadata.additional else None,
            datetime.utcnow().isoformat()
        ))
        conn.commit()
        conn.close()
        return False, True, None
    except Exception as e:
        conn.close()
        return False, False, str(e)


# PUBLIC_INTERFACE
def query_events(filter: EventFilter, limit: int = 100, offset: int = 0) -> Tuple[List[PollEventDb], int]:
    """
    Query events with filtering. Returns list of events and total count (for pagination).
    """
    conn = _get_connection()
    c = conn.cursor()
    # Build SQL
    conds = []
    params = []
    if filter.poll_id:
        conds.append("poll_id = ?")
        params.append(filter.poll_id)
    if filter.event_type:
        conds.append("event_type = ?")
        params.append(filter.event_type)
    if filter.event_id:
        conds.append("event_id = ?")
        params.append(filter.event_id)
    if filter.user_id:
        conds.append("user_id = ?")
        params.append(filter.user_id)
    if filter.start_time:
        conds.append("timestamp >= ?")
        params.append(filter.start_time.isoformat())
    if filter.end_time:
        conds.append("timestamp <= ?")
        params.append(filter.end_time.isoformat())
    where = f"WHERE {' AND '.join(conds)}" if conds else ""

    count_q = f"SELECT COUNT(*) FROM poll_events {where}"
    c.execute(count_q, params)
    total_count = c.fetchone()[0]

    sql = f"""
    SELECT id, event_id, poll_id, event_type, user_choice, timestamp, user_id, session_id, device_type, platform, app_version, geo, additional, received_at
    FROM poll_events {where} ORDER BY timestamp DESC LIMIT ? OFFSET ?
    """
    c.execute(sql, params + [limit, offset])
    rows = c.fetchall()
    events = []
    for row in rows:
        meta = {
            "device_type": row[8],
            "platform": row[9],
            "app_version": row[10],
            "user_id": row[6],
            "session_id": row[7],
            "geo": row[11],
            "additional": eval(row[12]) if row[12] else None
        }
        events.append(PollEventDb(
            id=row[0],
            event_id=row[1],
            poll_id=row[2],
            event_type=row[3],
            user_choice=row[4],
            timestamp=datetime.fromisoformat(row[5]),
            metadata=meta,
            received_at=datetime.fromisoformat(row[13])
        ))
    conn.close()
    return events, total_count


def _stats_count(query, params=()):
    conn = _get_connection()
    c = conn.cursor()
    c.execute(query, params)
    out = c.fetchone()
    conn.close()
    return out[0] if out else 0


def _stats_group(query, params=()) -> Dict[str, int]:
    conn = _get_connection()
    c = conn.cursor()
    c.execute(query, params)
    out = c.fetchall()
    conn.close()
    return {r[0]: r[1] for r in out if r[0]}


# PUBLIC_INTERFACE
def poll_summary_analytics(poll_id: str) -> Optional[PollAnalyticsSummary]:
    """
    Returns main analytics summary for a poll (counts, breakdowns)- or None if not found.
    """
    # Totals
    ti = _stats_count("SELECT COUNT(DISTINCT event_id) FROM poll_events WHERE poll_id=? AND event_type='impression'", (poll_id,))
    tv = _stats_count("SELECT COUNT(DISTINCT event_id) FROM poll_events WHERE poll_id=? AND event_type='vote'", (poll_id,))
    participants = _stats_count("SELECT COUNT(DISTINCT user_id) FROM poll_events WHERE poll_id=? AND event_type='vote' AND user_id IS NOT NULL", (poll_id,))
    votedist = _stats_group("SELECT user_choice, COUNT(*) FROM poll_events WHERE poll_id=? AND event_type='vote' GROUP BY user_choice", (poll_id,))
    deviceb = _stats_group("SELECT device_type, COUNT(*) FROM poll_events WHERE poll_id=? GROUP BY device_type", (poll_id,))
    platb = _stats_group("SELECT platform, COUNT(*) FROM poll_events WHERE poll_id=? GROUP BY platform", (poll_id,))
    geob = _stats_group("SELECT geo, COUNT(*) FROM poll_events WHERE poll_id=? GROUP BY geo", (poll_id,))
    # Events
    conn = _get_connection()
    c = conn.cursor()
    c.execute("SELECT MIN(timestamp), MAX(timestamp) FROM poll_events WHERE poll_id=?", (poll_id,))
    minmax = c.fetchone()
    conn.close()
    return PollAnalyticsSummary(
        poll_id=poll_id,
        total_impressions=ti,
        total_votes=tv,
        participants=participants,
        vote_distribution=votedist,
        device_breakdown=deviceb,
        platform_breakdown=platb,
        geo_breakdown=geob,
        first_event_at=datetime.fromisoformat(minmax[0]) if minmax and minmax[0] else None,
        last_event_at=datetime.fromisoformat(minmax[1]) if minmax and minmax[1] else None
    )

