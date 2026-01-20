import sqlite3
import os
from datetime import datetime, timedelta
import pandas as pd

class P0TimeSeriesStorage:
    """
    Time-series storage for P0 indicators using SQLite.
    Stores all data points with timestamps for historical analysis.
    """
    def __init__(self, db_file='p0_timeseries.db'):
        self.db_file = db_file
        self._initialize_db()
    
    def _get_conn(self):
        return sqlite3.connect(self.db_file)

    def _initialize_db(self):
        """Create table if it doesn't exist"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # Schema: timestamp, metric_name, value
        # We store each metric as a separate row to be flexible
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS measurements (
                timestamp TEXT,
                metric_name TEXT,
                value REAL,
                PRIMARY KEY (timestamp, metric_name)
            )
        ''')
        
        # Index for fast time-range queries
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON measurements(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_metric ON measurements(metric_name)')
        
        conn.commit()
        conn.close()
    
    def append_data(self, data_dict):
        """
        Append new data points.
        
        Args:
            data_dict: Dictionary with P0 indicator values. 
                       Can be nested or flat. We only store numeric/string values.
        """
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            for key, value in data_dict.items():
                if value is None or value == 'N/A':
                    continue
                
                # If value is numeric, store it. If it's a string that looks like a number, convert it.
                # We skip complex objects or non-numeric strings for the time series (unless we want to store them as text?)
                # Requirement says "value" (implied numeric for charts).
                
                val_to_store = None
                try:
                    if isinstance(value, (int, float)):
                        val_to_store = float(value)
                    elif isinstance(value, str):
                        # Try to clean string (remove commas)
                        clean_val = value.replace(',', '')
                        val_to_store = float(clean_val)
                except:
                    continue
                
                if val_to_store is not None:
                    cursor.execute('''
                        INSERT OR REPLACE INTO measurements (timestamp, metric_name, value)
                        VALUES (?, ?, ?)
                    ''', (timestamp, key, val_to_store))
            
            conn.commit()
            
            # Cleanup old data (Retention: 30 days)
            self._cleanup_old_data(cursor)
            conn.commit()
            
        except Exception as e:
            print(f"Error appending data: {e}")
        finally:
            conn.close()
    
    def append_data_with_timestamp(self, data_dict, timestamp):
        """
        Append data with a specific timestamp (for backfilling).
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            for key, value in data_dict.items():
                if value is None or value == 'N/A':
                    continue
                
                val_to_store = None
                try:
                    if isinstance(value, (int, float)):
                        val_to_store = float(value)
                    elif isinstance(value, str):
                        clean_val = value.replace(',', '')
                        val_to_store = float(clean_val)
                except:
                    continue
                
                if val_to_store is not None:
                    cursor.execute('''
                        INSERT OR REPLACE INTO measurements (timestamp, metric_name, value)
                        VALUES (?, ?, ?)
                    ''', (timestamp, key, val_to_store))
            
            conn.commit()
        except Exception as e:
            print(f"Error appending backfill data: {e}")
        finally:
            conn.close()

    def _cleanup_old_data(self, cursor):
        """Delete data older than 30 days"""
        cutoff = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('DELETE FROM measurements WHERE timestamp < ?', (cutoff,))
        
    def get_history(self, metric_name, days=30):
        """
        Get historical data for a specific metric.
        
        Returns:
            List of dicts: [{'timestamp': '...', 'value': 123.4}, ...]
        """
        cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
        
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT timestamp, value FROM measurements
            WHERE metric_name = ? AND timestamp >= ?
            ORDER BY timestamp ASC
        ''', (metric_name, cutoff))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [{'timestamp': r[0], 'value': r[1]} for r in rows]

    def get_delta(self, metric_name, lag=1):
        """
        Calculate delta (change) for a specific metric.
        Compare current value with the most recent DIFFERENT value.
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # Get all values ordered by timestamp DESC
        cursor.execute('''
            SELECT value FROM measurements
            WHERE metric_name = ?
            ORDER BY timestamp DESC
        ''', (metric_name,))
        
        rows = cursor.fetchall()
        conn.close()
        
        if len(rows) < 2:
            return None
        
        current = rows[0][0]
        
        # Find the most recent value that's different from current
        for i in range(1, len(rows)):
            previous = rows[i][0]
            if previous != current:
                return current - previous
        
        # All values are the same
        return 0.0

if __name__ == "__main__":
    # Test the storage system
    storage = P0TimeSeriesStorage()
    
    # Example data point
    test_data = {
        'OI_ag2603': 222892,
        'VOL_ag2603': 2299506,
        'Turnover_ag2603': 10.32,
        'Paper_to_Physical': 4.32,
        'COMEX_Silver_Registered': 128163446,
        'COMEX_Futures_Price': 70.92
    }
    
    storage.append_data(test_data)
    print("Data appended successfully")
    
    # Get history
    hist = storage.get_history('COMEX_Futures_Price')
    print(f"\nHistory for COMEX_Futures_Price ({len(hist)} points):")
    print(hist[:5])
    
    # Test delta
    delta = storage.get_delta('COMEX_Silver_Registered')
    print(f"\nΔRegistered: {delta}")

