import sqlite3
from datetime import datetime
from pathlib import Path

class DBManager:
    def __init__(self, db_path='silver_data.db'):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS silver_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    source TEXT NOT NULL,
                    price REAL,
                    raw_data TEXT
                )
            ''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON silver_data(timestamp)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_source ON silver_data(source)')
    
    def insert(self, source, price=None, raw_data=None):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                'INSERT INTO silver_data (timestamp, source, price, raw_data) VALUES (?, ?, ?, ?)',
                (datetime.utcnow().isoformat(), source, price, raw_data)
            )
    
    def get_recent(self, days=7):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM silver_data WHERE timestamp >= datetime('now', '-' || ? || ' days') ORDER BY timestamp",
                (days,)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def get_last_different_value(self, source, current_value, field='raw_data', key='holdings_oz'):
        """Get the last value that's different from current_value"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                f"SELECT {field} FROM silver_data WHERE source = ? ORDER BY timestamp DESC LIMIT 50",
                (source,)
            )
            import json
            for row in cursor.fetchall():
                if row[0]:
                    try:
                        data = json.loads(row[0])
                        if data.get(key) and data[key] != current_value:
                            return data[key]
                    except:
                        pass
            return None
