import json
import os
import sqlite3
from contextlib import contextmanager

from .lifecycle import can_transition

SCHEMA="""
CREATE TABLE IF NOT EXISTS opportunities (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 title TEXT NOT NULL,
 url TEXT NOT NULL UNIQUE,
 source TEXT NOT NULL,
 source_trust TEXT DEFAULT 'unknown',
 summary TEXT DEFAULT '',
 country TEXT,
 deadline TEXT,
 funding TEXT,
 opportunity_type TEXT DEFAULT 'scholarship',
 verification_status TEXT DEFAULT 'REVIEW',
 verification_reason TEXT DEFAULT '',
 eligibility_status TEXT DEFAULT 'UNKNOWN',
 eligibility_reasons TEXT DEFAULT '[]',
 blockers TEXT DEFAULT '[]',
 eligibility_score REAL DEFAULT 0,
 profile_match_score REAL DEFAULT 0,
 funding_score REAL DEFAULT 0,
 urgency_score REAL DEFAULT 0,
 competitiveness_score REAL DEFAULT 0,
 confidence_score REAL DEFAULT 0,
 overall_priority REAL DEFAULT 0,
 decision TEXT DEFAULT 'REVIEW',
 status TEXT DEFAULT 'DISCOVERED',
 first_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
 last_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
 created_at TEXT DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS applications (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 opportunity_id INTEGER NOT NULL UNIQUE,
 state TEXT NOT NULL DEFAULT 'DISCOVERED',
 intervention TEXT,
 notes TEXT DEFAULT '',
 created_at TEXT DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(opportunity_id) REFERENCES opportunities(id)
);

CREATE TABLE IF NOT EXISTS events (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 event_type TEXT NOT NULL,
 entity_type TEXT NOT NULL,
 entity_id TEXT,
 payload TEXT DEFAULT '{}',
 created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS email_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 message_id TEXT UNIQUE,
 sender TEXT,
 subject TEXT,
 category TEXT,
 application_id INTEGER,
 received_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS runs (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 started_at TEXT DEFAULT CURRENT_TIMESTAMP,
 finished_at TEXT,
 status TEXT DEFAULT 'RUNNING',
 discovered_count INTEGER DEFAULT 0,
 priority_count INTEGER DEFAULT 0,
 email_count INTEGER DEFAULT 0,
 error_count INTEGER DEFAULT 0,
 report_path TEXT
);
"""

MIGRATIONS={
    "opportunities":{
        "source_trust":"TEXT","verification_status":"TEXT","verification_reason":"TEXT",
        "eligibility_status":"TEXT","eligibility_reasons":"TEXT","blockers":"TEXT",
        "first_seen_at":"TEXT","last_seen_at":"TEXT",
    }
}

@contextmanager
def connect(path):
    directory=os.path.dirname(path)
    if directory:
        os.makedirs(directory,exist_ok=True)
    conn=sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory=sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db(path):
    with connect(path) as conn:
        conn.executescript(SCHEMA)
        existing={row["name"] for row in conn.execute("PRAGMA table_info(opportunities)")}
        for name,definition in MIGRATIONS["opportunities"].items():
            if name not in existing:
                conn.execute(f"ALTER TABLE opportunities ADD COLUMN {name} {definition}")
        conn.execute(
            "UPDATE opportunities SET first_seen_at=COALESCE(first_seen_at,CURRENT_TIMESTAMP),"
            "last_seen_at=COALESCE(last_seen_at,CURRENT_TIMESTAMP),"
            "source_trust=COALESCE(source_trust,'unknown'),"
            "verification_status=COALESCE(verification_status,'REVIEW'),"
            "verification_reason=COALESCE(verification_reason,''),"
            "eligibility_status=COALESCE(eligibility_status,'UNKNOWN'),"
            "eligibility_reasons=COALESCE(eligibility_reasons,'[]'),"
            "blockers=COALESCE(blockers,'[]')"
        )

def start_run(conn):
    return conn.execute("INSERT INTO runs(status) VALUES('RUNNING')").lastrowid

def finish_run(conn,run_id,status,discovered,priority,emails,errors,report_path=None):
    conn.execute(
        "UPDATE runs SET finished_at=CURRENT_TIMESTAMP,status=?,discovered_count=?,"
        "priority_count=?,email_count=?,error_count=?,report_path=? WHERE id=?",
        (status,discovered,priority,emails,errors,report_path,run_id)
    )

def upsert_opportunity(conn,op,verification,eligibility,evaluation):
    if verification.status=="VERIFIED" and eligibility.status=="ELIGIBLE":
        status="ELIGIBLE"
    elif eligibility.status=="INELIGIBLE":
        status="REJECTED"
    else:
        status="REVIEW"
    conn.execute(
        """INSERT INTO opportunities
        (title,url,source,source_trust,summary,country,deadline,funding,opportunity_type,
         verification_status,verification_reason,eligibility_status,eligibility_reasons,
         blockers,eligibility_score,profile_match_score,funding_score,urgency_score,
         competitiveness_score,confidence_score,overall_priority,decision,status,last_seen_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
        ON CONFLICT(url) DO UPDATE SET
          title=excluded.title,source=excluded.source,source_trust=excluded.source_trust,
          summary=excluded.summary,country=excluded.country,deadline=excluded.deadline,
          funding=excluded.funding,opportunity_type=excluded.opportunity_type,
          verification_status=excluded.verification_status,verification_reason=excluded.verification_reason,
          eligibility_status=excluded.eligibility_status,eligibility_reasons=excluded.eligibility_reasons,
          blockers=excluded.blockers,eligibility_score=excluded.eligibility_score,
          profile_match_score=excluded.profile_match_score,funding_score=excluded.funding_score,
          urgency_score=excluded.urgency_score,competitiveness_score=excluded.competitiveness_score,
          confidence_score=excluded.confidence_score,overall_priority=excluded.overall_priority,
          decision=excluded.decision,status=excluded.status,last_seen_at=CURRENT_TIMESTAMP,
          updated_at=CURRENT_TIMESTAMP""",
        (
            op.title,op.url,op.source,verification.trust,op.summary,op.country,op.deadline,
            op.funding,op.opportunity_type,verification.status,verification.reason,
            eligibility.status,json.dumps(eligibility.reasons,ensure_ascii=False),
            json.dumps(eligibility.blockers,ensure_ascii=False),
            evaluation["eligibility_score"],evaluation["profile_match_score"],
            evaluation["funding_score"],evaluation["urgency_score"],
            evaluation["competitiveness_score"],evaluation["confidence_score"],
            evaluation["overall_priority"],evaluation["decision"],status
        )
    )
    return conn.execute("SELECT id FROM opportunities WHERE url=?",(op.url,)).fetchone()["id"]

def upsert_application(conn,opportunity_id,desired_state,intervention=None,notes=""):
    existing=conn.execute(
        "SELECT id,state FROM applications WHERE opportunity_id=?",(opportunity_id,)
    ).fetchone()
    if not existing:
        cursor=conn.execute(
            "INSERT INTO applications(opportunity_id,state,intervention,notes) VALUES(?,?,?,?)",
            (opportunity_id,desired_state,intervention,notes)
        )
        return cursor.lastrowid,desired_state,True

    current=existing["state"]
    if current==desired_state or can_transition(current,desired_state):
        conn.execute(
            "UPDATE applications SET state=?,intervention=?,notes=?,updated_at=CURRENT_TIMESTAMP "
            "WHERE opportunity_id=?",
            (desired_state,intervention,notes,opportunity_id)
        )
        return existing["id"],desired_state,True

    return existing["id"],current,False

def insert_event(conn,event_type,entity_type,entity_id=None,payload=None):
    conn.execute(
        "INSERT INTO events(event_type,entity_type,entity_id,payload) VALUES(?,?,?,?)",
        (event_type,entity_type,entity_id,json.dumps(payload or {},ensure_ascii=False))
    )

def record_event(path,event_type,entity_type,entity_id=None,payload=None):
    with connect(path) as conn:
        insert_event(conn,event_type,entity_type,entity_id,payload)
