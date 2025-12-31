import pandas as pd
import os
from datetime import datetime
import json

class P0TimeSeriesStorage:
    """
    Time-series storage for P0 indicators using CSV with pandas.
    Stores all data points with timestamps for 24-hour continuous charts.
    """
    def __init__(self, csv_file='p0_timeseries.csv'):
        self.csv_file = csv_file
        self.columns = [
            'timestamp',
            # SHFE Contract Metrics
            'OI_ag2603', 'VOL_ag2603', 'Turnover_ag2603', 'ΔOI_ag2603',
            'Front6_OI_sum_SHFE', 'OI_concentration_2603', 'Curve_slope_SHFE_3m6m',
            # SHFE Inventory
            'SHFE_Daily_Warrant_Ag', 'SHFE_Weekly_Inventory_Ag',
            # COMEX Inventory
            'COMEX_Silver_Registered', 'COMEX_Silver_Eligible', 
            'ΔCOMEX_Registered', 'Registered_to_Total',
            # COMEX Delivery
            'COMEX_IssuesStops_Silver', 'COMEX_Deliveries_MTD',
            # Basis & Premium
            'Paper_to_Physical', 'Basis_USD_COMEX', 
            'Shanghai_Premium_Implied', 'SGE_SHAG_vs_Overseas',
            # LBMA
            'LBMA_London_Vault_Silver',
            # Additional context
            'COMEX_Futures_Price', 'XAGUSD_Spot', 'SHFE_ag2603_Price'
        ]
        self._initialize_csv()
    
    def _initialize_csv(self):
        """Create CSV with headers if it doesn't exist"""
        if not os.path.exists(self.csv_file):
            df = pd.DataFrame(columns=self.columns)
            df.to_csv(self.csv_file, index=False)
    
    def append_data(self, data_dict):
        """
        Append a new data point with current timestamp.
        
        Args:
            data_dict: Dictionary with P0 indicator values
        """
        # Add timestamp
        data_dict['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Create DataFrame from single row
        df_new = pd.DataFrame([data_dict])
        
        # Fill missing columns with None
        for col in self.columns:
            if col not in df_new.columns:
                df_new[col] = None
        
        # Ensure column order
        df_new = df_new[self.columns]
        
        # Append to CSV
        df_new.to_csv(self.csv_file, mode='a', header=False, index=False)
    
    def get_recent_data(self, hours=24):
        """
        Get data from last N hours for charting.
        
        Args:
            hours: Number of hours to retrieve (default 24)
        
        Returns:
            pandas DataFrame with timestamp index
        """
        try:
            df = pd.read_csv(self.csv_file)
            if df.empty:
                return df
            
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Filter for last N hours
            cutoff = datetime.now() - pd.Timedelta(hours=hours)
            df_recent = df[df['timestamp'] >= cutoff]
            
            return df_recent.set_index('timestamp')
        except Exception as e:
            print(f"Error reading time series: {e}")
            return pd.DataFrame()
    
    def get_latest(self):
        """Get the most recent data point"""
        try:
            df = pd.read_csv(self.csv_file)
            if df.empty:
                return {}
            return df.iloc[-1].to_dict()
        except:
            return {}
    
    def get_delta(self, column, lag=1):
        """
        Calculate delta (change) for a specific column.
        
        Args:
            column: Column name to calculate delta for
            lag: Number of rows to look back (default 1 for previous point)
        
        Returns:
            Delta value or None
        """
        try:
            df = pd.read_csv(self.csv_file)
            if len(df) < lag + 1:
                return None
            
            current = df[column].iloc[-1]
            previous = df[column].iloc[-(lag+1)]
            
            if pd.isna(current) or pd.isna(previous):
                return None
            
            return current - previous
        except:
            return None

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
    
    # Get recent data
    recent = storage.get_recent_data(hours=1)
    print(f"\nRecent data ({len(recent)} points):")
    print(recent.head())
    
    # Test delta calculation
    delta = storage.get_delta('COMEX_Silver_Registered')
    print(f"\nΔRegistered: {delta}")
