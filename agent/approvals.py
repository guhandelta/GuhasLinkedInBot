"""Internal approval ledger. Transport adapters must authenticate the owner."""

import hashlib
import json
import secrets
import sqlite3
import time
from contextlib import contextmanager


class ApprovalLedger:
    def __init__(self, path):
        self.path = str(path)
        with self._connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS versions (
                    draft_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    payload TEXT NOT NULL,
                    expires_at REAL NOT NULL,
                    state TEXT NOT NULL DEFAULT 'pending',
                    decision_channel TEXT,
                    feedback TEXT,
                    decided_at REAL,
                    PRIMARY KEY (draft_id, version)
                );
                CREATE TABLE IF NOT EXISTS tokens (
                    digest TEXT PRIMARY KEY,
                    draft_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    channel TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS publish_jobs (
                    draft_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    state TEXT NOT NULL DEFAULT 'queued',
                    PRIMARY KEY (draft_id, version)
                );
            """)

    @contextmanager
    def _connection(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def _digest(token):
        return hashlib.sha256(token.encode()).hexdigest()

    def request(self, draft_id, payload, ttl_seconds=86400):
        """Create a version and channel tokens, closing any earlier pending one.

        Payload must include final text, destinations and immutable graphic content
        or a content-addressed asset reference (never a mutable image URL).
        """
        if not draft_id or ttl_seconds <= 0:
            raise ValueError('Draft ID and positive expiry are required')
        encoded = json.dumps(payload, sort_keys=True, allow_nan=False)
        tokens = {channel: secrets.token_urlsafe(32)
                  for channel in ('email', 'telegram')}
        with self._connection() as db:
            db.execute('BEGIN IMMEDIATE')
            latest = db.execute(
                'SELECT version, state FROM versions WHERE draft_id=? '
                'ORDER BY version DESC LIMIT 1', (draft_id,)
            ).fetchone()
            if latest and latest['state'] == 'approved':
                raise ValueError('An approved draft is immutable; use a new draft ID')
            version = latest['version'] + 1 if latest else 1
            db.execute("UPDATE versions SET state='superseded' "
                       "WHERE draft_id=? AND state='pending'", (draft_id,))
            db.execute('INSERT INTO versions '
                       '(draft_id, version, payload, expires_at) VALUES (?, ?, ?, ?)',
                       (draft_id, version, encoded, time.time() + ttl_seconds))
            db.executemany('INSERT INTO tokens VALUES (?, ?, ?, ?)',
                           [(self._digest(token), draft_id, version, channel)
                            for channel, token in tokens.items()])
        return {'draft_id': draft_id, 'version': version, 'tokens': tokens}

    def decide(self, token, channel, action, feedback=''):
        """Atomically accept the first valid action; never publish directly."""
        if channel not in ('email', 'telegram'):
            raise ValueError('Unknown channel')
        if action not in ('approve', 'changes', 'reject'):
            raise ValueError('Unknown action')
        if action == 'changes' and not feedback.strip():
            raise ValueError('Correction feedback is required')
        with self._connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute(
                'SELECT v.* FROM tokens t JOIN versions v '
                'ON v.draft_id=t.draft_id AND v.version=t.version '
                'WHERE t.digest=? AND t.channel=?',
                (self._digest(token), channel)
            ).fetchone()
            if row is None:
                return {'accepted': False, 'state': 'invalid'}
            result = {'draft_id': row['draft_id'], 'version': row['version']}
            if row['state'] != 'pending':
                return dict(result, accepted=False, state=row['state'])
            now = time.time()
            state = ('expired' if now >= row['expires_at'] else
                     {'approve': 'approved', 'changes': 'changes_requested',
                      'reject': 'rejected'}[action])
            db.execute('UPDATE versions SET state=?, decision_channel=?, '
                       'feedback=?, decided_at=? WHERE draft_id=? AND version=?',
                       (state, channel, feedback, now,
                        row['draft_id'], row['version']))
            if state == 'approved':
                db.execute('INSERT INTO publish_jobs (draft_id, version) VALUES (?, ?)',
                           (row['draft_id'], row['version']))
            return dict(result, accepted=state != 'expired', state=state)
