"""
Unified Database Manager for Silver Market Bot.

Combines functionality from:
- Original db_manager.py (raw data records)
- p0_storage.py (time series metrics)
- JSON cache files (now in SQLite cache table)
"""

import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path


class DBManager:
    """
    Unified database manager with three tables:
    - records: Raw data records by source
    - metrics: Time series metrics for delta calculations
    - cache: Key-value cache with TTL
    """

    def __init__(self, db_path="market_data.db"):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """Create all tables if they don't exist."""
        with self._get_conn() as conn:
            # Records table (from original db_manager)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    source TEXT NOT NULL,
                    price REAL,
                    raw_data TEXT
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_records_timestamp ON records(timestamp)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_records_source ON records(source)"
            )

            # Metrics table (from p0_storage)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS metrics (
                    timestamp TEXT,
                    metric_name TEXT,
                    value REAL,
                    PRIMARY KEY (timestamp, metric_name)
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON metrics(timestamp)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_metrics_name ON metrics(metric_name)"
            )

            # Cache table (replaces JSON files)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    data TEXT,
                    updated_at TEXT
                )
            """)

    # ============ Records Methods (from original db_manager) ============

    def insert(self, source, price=None, raw_data=None):
        """Insert a raw data record."""
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO records (timestamp, source, price, raw_data) VALUES (?, ?, ?, ?)",
                (datetime.utcnow().isoformat(), source, price, raw_data),
            )

    def get_recent(self, days=7):
        """Get recent records within specified days."""
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM records WHERE timestamp >= datetime('now', '-' || ? || ' days') ORDER BY timestamp",
                (days,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_last_different_value(
        self, source, current_value, field="raw_data", key="holdings_oz"
    ):
        """Get the last value that's different from current_value."""
        with self._get_conn() as conn:
            cursor = conn.execute(
                f"SELECT {field} FROM records WHERE source = ? ORDER BY timestamp DESC LIMIT 50",
                (source,),
            )
            for row in cursor.fetchall():
                if row[0]:
                    try:
                        data = json.loads(row[0])
                        if data.get(key) and data[key] != current_value:
                            return data[key]
                    except:
                        pass
            return None

    # ============ Metrics Methods (from p0_storage) ============

    def append_metrics(self, data_dict):
        """
        Append new metric data points.

        Args:
            data_dict: Dictionary with metric name -> value pairs
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with self._get_conn() as conn:
            for key, value in data_dict.items():
                if value is None or value == "N/A":
                    continue

                val_to_store = None
                try:
                    if isinstance(value, (int, float)):
                        val_to_store = float(value)
                    elif isinstance(value, str):
                        clean_val = value.replace(",", "")
                        val_to_store = float(clean_val)
                except:
                    continue

                if val_to_store is not None:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO metrics (timestamp, metric_name, value)
                        VALUES (?, ?, ?)
                    """,
                        (timestamp, key, val_to_store),
                    )

            # Cleanup old data (30 day retention)
            cutoff = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
            conn.execute("DELETE FROM metrics WHERE timestamp < ?", (cutoff,))

    def insert_metric(self, timestamp, metric_name, value):
        """
        Insert a metric with a specific timestamp.
        Useful for backfilling historical data.
        """
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO metrics (timestamp, metric_name, value)
                VALUES (?, ?, ?)
                """,
                (timestamp, metric_name, value),
            )

    def get_metric_history(self, metric_name, days=30):
        """
        Get historical data for a specific metric.

        Returns:
            List of dicts: [{'timestamp': '...', 'value': 123.4}, ...]
        """
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

        with self._get_conn() as conn:
            cursor = conn.execute(
                """
                SELECT timestamp, value FROM metrics
                WHERE metric_name = ? AND timestamp >= ?
                ORDER BY timestamp ASC
            """,
                (metric_name, cutoff),
            )

            return [{"timestamp": r[0], "value": r[1]} for r in cursor.fetchall()]

    def get_metric_delta(self, metric_name):
        """
        Calculate delta (change) for a specific metric.
        Compare current value with the most recent DIFFERENT value.
        """
        with self._get_conn() as conn:
            cursor = conn.execute(
                """
                SELECT value FROM metrics
                WHERE metric_name = ?
                ORDER BY timestamp DESC
            """,
                (metric_name,),
            )

            rows = cursor.fetchall()

            if len(rows) < 2:
                return None

            current = rows[0][0]

            # Find the most recent value that's different from current
            for i in range(1, len(rows)):
                previous = rows[i][0]
                if previous != current:
                    return current - previous

            return 0.0

    def get_latest_metric_value(self, metric_name):
        """Get the most recent value for a metric."""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT value FROM metrics WHERE metric_name = ? ORDER BY timestamp DESC LIMIT 1",
                (metric_name,),
            )
            row = cursor.fetchone()
            return row[0] if row else None

    # ============ Cache Methods (replaces JSON files) ============

    def get_cache(self, key, ttl_hours=24):
        """
        Read cached data if valid within TTL.

        Returns:
            tuple: (data_dict, age_hours) or (None, None) if not found/expired
        """
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT data, updated_at FROM cache WHERE key = ?", (key,)
            )
            row = cursor.fetchone()

            if row:
                try:
                    data = json.loads(row[0])
                    updated_at = datetime.fromisoformat(row[1])
                    age = datetime.now() - updated_at
                    age_hours = age.total_seconds() / 3600

                    if age_hours < ttl_hours:
                        return data, round(age_hours, 1)
                except:
                    pass

            return None, None

    def set_cache(self, key, data):
        """Store data in cache."""
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO cache (key, data, updated_at)
                VALUES (?, ?, ?)
            """,
                (key, json.dumps(data), datetime.now().isoformat()),
            )

    def clear_cache(self, key=None):
        """Clear cache entry or all cache if key is None."""
        with self._get_conn() as conn:
            if key:
                conn.execute("DELETE FROM cache WHERE key = ?", (key,))
            else:
                conn.execute("DELETE FROM cache")


# Migration helper
def migrate_from_old_databases():
    """
    Migrate data from old databases to the new unified database.
    Call this once to migrate existing data.
    """
    new_db = DBManager("market_data.db")

    # Migrate from silver_data.db
    if Path("silver_data.db").exists():
        print("Migrating from silver_data.db...")
        old_conn = sqlite3.connect("silver_data.db")
        cursor = old_conn.execute(
            "SELECT timestamp, source, price, raw_data FROM silver_data"
        )

        with new_db._get_conn() as conn:
            for row in cursor.fetchall():
                conn.execute(
                    "INSERT OR IGNORE INTO records (timestamp, source, price, raw_data) VALUES (?, ?, ?, ?)",
                    row,
                )
        old_conn.close()
        print("  ✓ Migrated records from silver_data.db")

    # Migrate from p0_timeseries.db
    if Path("p0_timeseries.db").exists():
        print("Migrating from p0_timeseries.db...")
        old_conn = sqlite3.connect("p0_timeseries.db")
        cursor = old_conn.execute(
            "SELECT timestamp, metric_name, value FROM measurements"
        )

        with new_db._get_conn() as conn:
            for row in cursor.fetchall():
                conn.execute(
                    "INSERT OR IGNORE INTO metrics (timestamp, metric_name, value) VALUES (?, ?, ?)",
                    row,
                )
        old_conn.close()
        print("  ✓ Migrated metrics from p0_timeseries.db")

    # Migrate JSON cache files
    cache_dir = Path("./cache")
    if cache_dir.exists():
        print("Migrating JSON cache files...")
        for json_file in cache_dir.glob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                key = json_file.stem  # filename without extension
                new_db.set_cache(key, data)
                print(f"  ✓ Migrated {json_file.name}")
            except Exception as e:
                print(f"  ⚠ Failed to migrate {json_file.name}: {e}")

    print("\nMigration complete!")
    return new_db


if __name__ == "__main__":
    # Run migration if called directly
    migrate_from_old_databases()
