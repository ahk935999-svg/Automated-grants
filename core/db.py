import os
import sqlite3
from contextlib import contextmanager

SCHEMA = """
CREATE TABLE IF NOT EXISTS opportunities (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 title TEXT NOT NULL,
 url TEXT NOT NULL UNIQUE,
 source TEXT NOT NULL,
 summary TEXT DEFAULT '',
 country TEXT,
 deadline TEXT,
 funding TEXT,
 opportunity_type TEXT DEFAULT 'scholarship',
 eligibility_score REAL DEFAULT 0,
 profile_match_score REAL DEFAULT 0,
 funding_score REAL DEFAULT 0,
 urgency_score REAL DEFAULT 0,
 competitiveness_score REAL DEFAULT 0,
 confidence_score REAL DEFAULT 0,
 overall_priority REAL DEFAULT 0,
 decision TEXT DEFAULT 'REVIEW',
 status TEXT DEFAULT 'DISCOVERED',
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
 updated_at TEXT DEFAULT CURRENT_TIMESTAMP
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
"""

@contextmanager
def connect(path: str):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db(path: str):
    with connect(path) as conn:
        conn.executescript(SCHEMA)

def record_event(path, event_type, entity_type, entity_id=None, payload="{}"):
    with connect(path) as conn:
        conn.execute(
            "INSERT INTO events(event_type,entity_type,entity_id,payload) VALUES(?,?,?,?)",
            (event_type, entity_type, entity_id, payload),
        )
