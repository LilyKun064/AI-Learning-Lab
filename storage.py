"""Separate v4 database; original trials and corrections are not overwritten."""
import json
import os
import sqlite3
from pathlib import Path
from config import ROOT
from core import now


class Store:
    def __init__(self, path=None):
        self.path = Path(path or os.getenv('TUTOR_DB_PATH') or ROOT / 'data' / 'attempts-v4.sqlite3')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as c:
            c.execute('CREATE TABLE IF NOT EXISTS attempts (id TEXT PRIMARY KEY, payload TEXT NOT NULL, updated TEXT NOT NULL)')

    def save(self, attempt):
        with sqlite3.connect(self.path) as c:
            c.execute('INSERT OR REPLACE INTO attempts VALUES (?, ?, ?)',
                      (attempt['attempt_id'], json.dumps(attempt, ensure_ascii=False), now()))

    def list(self):
        with sqlite3.connect(self.path) as c:
            return [json.loads(row[0]) for row in c.execute('SELECT payload FROM attempts ORDER BY updated DESC')]
