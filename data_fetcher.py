import yfinance as yf
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta
import pandas as pd
import io
import json
import os
from p0_storage import P0TimeSeriesStorage
from cme_pdf_parser import CMEDeliveryParser

class SilverDataFetcher:
    def __init__(self, cache_dir='./cache'):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        self.cache_dir = cache_dir
        self.storage = P0TimeSeriesStorage()
        self.pdf_parser = CMEDeliveryParser()
        os.makedirs(cache_dir, exist_ok=True)
        # metals.dev API key (100 calls/month = max 3 calls per day)
        # User should set this as environment variable
        self.metals_dev_key = os.getenv('METALS_DEV_KEY', '')
    
    def _get_cache_path(self, key):
        return os.path.join(self.cache_dir, f"{key}.json")
    
    def _is_cache_valid(self, cache_path, ttl_minutes):
        if not os.path.exists(cache_path):
            return False
        modified_time = datetime.fromtimestamp(os.path.getmtime(cache_path))
        age = datetime.now() - modified_time
        return age.total_seconds() < (ttl_minutes * 60)
    
    def _read_cache(self, key):
        cache_path = self._get_cache_path(key)
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return None
    
    def _write_cache(self, key, data):
        cache_path = self._get_cache_path(key)
        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Warning: Could not write cache for {key}: {e}")

    def get_metals_prices(self):
        """
        Get precious metal prices from metals.dev API.
        STRICT LIMIT: 100 calls/month = max 3 calls per 24 hours.
        Cache TTL: 8 hours (3 calls per day = every 8 hours).
        
        Returns dict with silver, gold, lbma_silver, etc.
        """
        cache_key = 'metals_dev_prices'
        
        # Check cache with 8-hour TTL (480 minutes)
        cached = self._read_cache(cache_key)
        if cached and self._is_cache_valid(self._get_cache_path(cache_key), ttl_minutes=480):
            cached['source'] = 'Cache'
            return cached
        
        if not self.metals_dev_key:
            # Fallback: use futures as proxy
            try:
                si = yf.Ticker('SI=F')
                gc = yf.Ticker('GC=F')
                silver_price = si.info.get('regularMarketPrice')
                gold_price = gc.info.get('regularMarketPrice')
                
                result = {
                    'silver': silver_price,
                    'gold': gold_price,
                    'lbma_silver': None,
                    'gold_silver_ratio': round(gold_price / silver_price, 2) if silver_price else None,
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'source': 'Futures Proxy (no API key)',
                    'note': 'Set METALS_DEV_KEY env var for metals.dev API'
                }
                self._write_cache(cache_key, result)
                return result
            except:
                return {'error': 'No API key and futures fetch failed'}
        
        # Fetch from metals.dev (CAREFUL: limited calls!)
        url = f"https://api.metals.dev/v1/latest?api_key={self.metals_dev_key}&currency=USD&unit=toz"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    metals = data.get('metals', {})
                    result = {
                        'silver': metals.get('silver'),
                        'gold': metals.get('gold'),
                        'lbma_silver': metals.get('lbma_silver'),
                        'lbma_gold_am': metals.get('lbma_gold_am'),
                        'lbma_gold_pm': metals.get('lbma_gold_pm'),
                        'gold_silver_ratio': round(metals.get('gold', 0) / metals.get('silver', 1), 2) if metals.get('silver') else None,
                        'platinum': metals.get('platinum'),
                        'palladium': metals.get('palladium'),
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'api_timestamp': data.get('timestamps', {}).get('metal'),
                        'source': 'metals.dev API'
                    }
                    self._write_cache(cache_key, result)
                    print(f"[metals.dev] API call successful - cached for 8 hours")
                    return result
            return {'error': f"metals.dev returned {response.status_code}"}
        except Exception as e:
            return {'error': str(e)}
    
    def get_realtime_spot(self):
        """
        Get real-time spot prices using yfinance futures as proxy.
        This is called every 5 minutes for dashboard updates.
        
        Periodically (every 8 hours), metals.dev API is called to calibrate.
        This approach keeps data fresh while respecting API limits.
        """
        try:
            si = yf.Ticker('SI=F')
            gc = yf.Ticker('GC=F')
            
            silver_price = si.info.get('regularMarketPrice')
            gold_price = gc.info.get('regularMarketPrice')
            
            # Get metals.dev baseline (cached 8 hours)
            metals_baseline = self.get_metals_prices()
            
            result = {
                'silver': silver_price,
                'gold': gold_price,
                'gold_silver_ratio': round(gold_price / silver_price, 2) if silver_price else None,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'source': 'Real-time (yfinance futures)',
                # Include metals.dev cached values for reference
                'metals_dev_silver': metals_baseline.get('silver'),
                'metals_dev_lbma': metals_baseline.get('lbma_silver'),
                'metals_dev_timestamp': metals_baseline.get('timestamp'),
                'metals_dev_source': metals_baseline.get('source')
            }
            return result
        except Exception as e:
            return {'error': str(e)}

    def get_futures_data(self):
        ticker = 'SI=F'
        try:
            future = yf.Ticker('SI=F')
            info = future.info
            
            if not info.get('regularMarketPrice'):
                future = yf.Ticker('SIH26.CMX')
                info = future.info

            return {
                'contract': 'SI=F (Active)',
                'price': info.get('regularMarketPrice'),
                'open_interest': info.get('openInterest'),
                'volume': info.get('volume'),
                'previous_close': info.get('previousClose'),
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        except Exception as e:
            return {'error': str(e)}

    def get_slv_data(self):
        url = "https://www.ishares.com/us/products/239855/ishares-silver-trust-fund"
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                text = soup.get_text()
                
                tonnes = "N/A"
                if "Tonnes in Trust" in text:
                    match = re.search(r"Tonnes in Trust.*?([\d,]+\.\d+)", text, re.DOTALL)
                    if match:
                        tonnes = match.group(1)
                
                return {
                    'inventory_tonnes': tonnes,
                    'inventory_ounces': self._convert_tonnes_to_ounces(tonnes),
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            else:
                return {'error': f"Status {response.status_code}"}
        except Exception as e:
            return {'error': str(e)}

    def get_cme_data(self):
        cache_key = 'cme_data'
        
        cached = self._read_cache(cache_key)
        if cached and self._is_cache_valid(self._get_cache_path(cache_key), ttl_minutes=1440):
            cached['source'] = 'Cache'
            return cached
        
        url = "https://www.cmegroup.com/delivery_reports/Silver_stocks.xls"
        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            if response.status_code == 200:
                df = pd.read_excel(io.BytesIO(response.content), engine='xlrd')
                
                header_row_idx = None
                for i, row in df.iterrows():
                    row_str = " ".join([str(x) for x in row.values])
                    if "TOTAL TODAY" in row_str and "DEPOSITORY" in row_str:
                        header_row_idx = i
                        break
                
                if header_row_idx is None:
                    return {'error': "Could not find header row"}
                
                headers = df.iloc[header_row_idx]
                col_total = None
                for idx, val in enumerate(headers):
                    if str(val).strip() == "TOTAL TODAY":
                        col_total = idx
                        break
                
                if col_total is None:
                    col_total = 7

                total_registered = 0
                total_eligible = 0
                
                for i in range(header_row_idx + 1, len(df)):
                    row = df.iloc[i]
                    category = str(row.iloc[0]).strip()
                    val = row.iloc[col_total]
                    
                    try:
                        val_float = float(val)
                    except:
                        continue
                        
                    if category == "Registered":
                        total_registered += val_float
                    elif category == "Eligible":
                        total_eligible += val_float

                total = total_registered + total_eligible
                reg_to_total = (total_registered / total) if total > 0 else 0
                
                # Calculate delta from previous
                delta_registered = self.storage.get_delta('COMEX_Silver_Registered')
                
                result = {
                    'registered': total_registered,
                    'eligible': total_eligible,
                    'total': total,
                    'registered_to_total_ratio': round(reg_to_total, 4),
                    'delta_registered': delta_registered,
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'source': 'Live'
                }
                
                self._write_cache(cache_key, result)
                return result
            else:
                return {'error': f"Status {response.status_code}"}
        except Exception as e:
            return {'error': str(e)}

    def get_lbma_data(self):
        cache_key = 'lbma_data'
        cached = self._read_cache(cache_key)
        if cached and self._is_cache_valid(self._get_cache_path(cache_key), ttl_minutes=1440):
            cached['source'] = 'Cache'
            return cached
        
        result = {
            'holdings_tonnes': '27,187',
            'timestamp': 'November 2025 (Estimate)',
            'source': 'Estimate'
        }
        self._write_cache(cache_key, result)
        return result

    def get_macro_data(self):
        """Get macro indicators - USD Index from yfinance, others from FRED"""
        series_map = {
            'real_yield': 'DFII10',
            'usd_cny': 'DEXCHUS'
        }
        data = {}
        
        # Get USD Index from yfinance (DX-Y.NYB) - more accurate than FRED
        try:
            dxy = yf.Ticker('DX-Y.NYB')
            dxy_price = dxy.info.get('regularMarketPrice')
            if dxy_price:
                data['usd_index'] = round(dxy_price, 4)
            else:
                data['usd_index'] = None
        except:
            data['usd_index'] = None
        
        # Get other series from FRED
        for key, series_id in series_map.items():
            url = f"https://fred.stlouisfed.org/series/{series_id}"
            try:
                response = requests.get(url, headers=self.headers, timeout=10)
                if response.status_code == 200:
                    match = re.search(r'class="series-meta-observation-value">([\d\.]+)<', response.text)
                    if match:
                        data[key] = float(match.group(1))
                    else:
                        data[key] = None
                else:
                    data[key] = None
            except:
                data[key] = None
        
        # Gold/Silver ratio from real-time or metals.dev
        try:
            realtime = self.get_realtime_spot()
            if realtime.get('gold_silver_ratio'):
                data['gold_silver_ratio'] = realtime['gold_silver_ratio']
            else:
                gold = yf.Ticker("GC=F").info.get('regularMarketPrice')
                silver = yf.Ticker("SI=F").info.get('regularMarketPrice')
                if gold and silver:
                    data['gold_silver_ratio'] = round(gold / silver, 2)
                else:
                    data['gold_silver_ratio'] = None
        except:
            data['gold_silver_ratio'] = None

        return data

    def get_options_data(self):
        try:
            slv = yf.Ticker("SLV")
            expirations = slv.options
            if expirations:
                expiry = expirations[0]
                opts = slv.option_chain(expiry)
                call_vol = opts.calls['volume'].sum()
                put_vol = opts.puts['volume'].sum()
                ratio = round(put_vol / call_vol, 2) if call_vol > 0 else 0
                
                current_price = slv.history(period='1d')['Close'].iloc[-1]
                
                put_strike = current_price * 0.9
                call_strike = current_price * 1.1
                
                put_iv = 0
                call_iv = 0
                
                try:
                    nr_put = opts.puts.iloc[(opts.puts['strike'] - put_strike).abs().argsort()[:1]]
                    nr_call = opts.calls.iloc[(opts.calls['strike'] - call_strike).abs().argsort()[:1]]
                    
                    if not nr_put.empty: put_iv = nr_put['impliedVolatility'].values[0]
                    if not nr_call.empty: call_iv = nr_call['impliedVolatility'].values[0]
                except:
                    pass

                iv_skew = round(put_iv - call_iv, 4)

                return {
                    'put_call_ratio': ratio,
                    'call_volume': int(call_vol),
                    'put_volume': int(put_vol),
                    'iv_skew_10pct': iv_skew,
                    'expiry': expiry
                }
            return {'error': 'No options found'}
        except Exception as e:
            return {'error': str(e)}

    def get_cot_data(self):
        url = "https://www.cftc.gov/dea/newcot/deafut.txt"
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                lines = response.text.split('\n')
                for line in lines:
                    if "SILVER" in line and "COMEX" in line:
                        parts = [x.strip() for x in line.split(',')]
                        return {
                            'description': "Found Silver COMEX COT",
                            'raw_preview': line[:50] + "...",
                            'status': 'Found'
                        }
                return {'status': 'Not Found'}
            return {'error': f"Status {response.status_code}"}
        except Exception as e:
            return {'error': str(e)}

    def get_shfe_data(self):
        """Load SHFE + calculate all derived metrics"""
        json_file = 'shfe_market_data.json'
        
        if os.path.exists(json_file):
            file_age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(json_file))
            if file_age.total_seconds() < 1800:  # 30 min
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    if not data:
                        return {'status': 'No Data'}
                    
                    # Find main contract (highest OI)
                    main_contract = max(data, key=lambda x: int(x.get('持仓量', '0').replace(',', '') or '0'))
                    
                    oi = int(main_contract.get('持仓量', '0').replace(',', '') or '0')
                    vol = int(main_contract.get('成交量', '0').replace(',', '') or '0')
                    
                    # Front 6 months sum
                    sorted_contracts = sorted(data, key=lambda x: x.get('合约名称', ''))[:6]
                    front6_oi = sum([int(x.get('持仓量', '0').replace(',', '') or '0') for x in sorted_contracts])
                    
                    # Concentration
                    concentration = round(oi / front6_oi, 4) if front6_oi > 0 else 0
                    
                    # Turn over
                    turnover = round(vol / oi, 4) if oi > 0 else 0
                    
                    # Curve slope (3m vs 6m) - ag2603 vs ag2606
                    price_2603 = None
                    price_2606 = None
                    for contract in data:
                        name = contract.get('合约名称', '')
                        if name == 'ag2603':
                            price_2603 = float(contract.get('最新价', '0').replace(',', '') or '0')
                        elif name == 'ag2606':
                            price_2606 = float(contract.get('最新价', '0').replace(',', '') or '0')
                    
                    curve_slope = None
                    if price_2603 and price_2606:
                        curve_slope = round(price_2606 - price_2603, 2)
                    
                    # Delta OI from previous stored value
                    delta_oi = self.storage.get_delta('OI_ag2603')
                    
                    return {
                        'contract': main_contract.get('合约名称'),
                        'price': float(main_contract.get('最新价', '0').replace(',', '') or '0'),
                        'oi': oi,
                        'volume': vol,
                        'turnover_ratio': turnover,
                        'front6_oi_sum': front6_oi,
                        'oi_concentration': concentration,
                        'curve_slope_3m6m': curve_slope,
                        'delta_oi': delta_oi,
                        'date': datetime.fromtimestamp(os.path.getmtime(json_file)).strftime('%Y-%m-%d %H:%M'),
                        'status': 'Success',
                        'source': 'Cached JSON'
                    }
                except Exception as e:
                    return {'status': 'Error', 'note': str(e)}
        
        return {'status': 'Unavailable', 'note': 'Run scrape_shfe_selenium.py'}

    def _convert_tonnes_to_ounces(self, tonnes_str):
        try:
            if tonnes_str == "N/A": return "N/A"
            tonnes = float(str(tonnes_str).replace(',', ''))
            ounces = tonnes * 32150.7
            return ounces
        except:
            return None

    def get_all_data_and_store(self):
        """
        Fetch all data, calculate all 20 P0 indicators, and store to CSV
        """
        # Fetch base data
        shfe = self.get_shfe_data()
        macro = self.get_macro_data()
        cme = self.get_cme_data()
        futures = self.get_futures_data()
        slv = self.get_slv_data()
        
        # Get metals prices - hybrid approach:
        # 1. metals.dev baseline (8hr cache) for accuracy
        # 2. Real-time futures overlay for 5-min updates
        metals_baseline = self.get_metals_prices()  # 8-hour cached
        realtime_spot = self.get_realtime_spot()  # Real-time futures proxy
        
        # Calculate P0 indicators
        p0_data = {}
        
        # SHFE metrics (already in shfe object)
        if shfe.get('status') == 'Success':
            p0_data['OI_ag2603'] = shfe.get('oi')
            p0_data['VOL_ag2603'] = shfe.get('volume')
            p0_data['Turnover_ag2603'] = shfe.get('turnover_ratio')
            p0_data['ΔOI_ag2603'] = shfe.get('delta_oi')
            p0_data['Front6_OI_sum_SHFE'] = shfe.get('front6_oi_sum')
            p0_data['OI_concentration_2603'] = shfe.get('oi_concentration')
            p0_data['Curve_slope_SHFE_3m6m'] = shfe.get('curve_slope_3m6m')
            p0_data['SHFE_ag2603_Price'] = shfe.get('price')
        
        # COMEX metrics
        if not cme.get('error'):
            p0_data['COMEX_Silver_Registered'] = cme.get('registered')
            p0_data['COMEX_Silver_Eligible'] = cme.get('eligible')
            p0_data['ΔCOMEX_Registered'] = cme.get('delta_registered')
            p0_data['Registered_to_Total'] = cme.get('registered_to_total_ratio')
        
        # Basis & Premium (use real-time spot)
        if futures.get('price') and not futures.get('error'):
            p0_data['COMEX_Futures_Price'] = futures.get('price')
            
            if realtime_spot.get('silver') and not realtime_spot.get('error'):
                p0_data['XAGUSD_Spot'] = realtime_spot.get('silver')
                p0_data['Basis_USD_COMEX'] = round(futures['price'] - realtime_spot['silver'], 2)
        
        # Paper to Physical
        if futures.get('open_interest') and cme.get('registered'):
            oi_oz = futures['open_interest'] * 5000
            p0_data['Paper_to_Physical'] = round(oi_oz / cme['registered'], 2)
        
        # SLV Coverage (CME Registered / SLV Ounces)
        if cme.get('registered') and slv.get('inventory_ounces'):
            slv_oz = slv['inventory_ounces']
            if isinstance(slv_oz, (int, float)):
                p0_data['SLV_Coverage'] = round(cme['registered'] / slv_oz, 4)
        
        # COMEX Dominance (COMEX OI in oz / SLV Ounces)
        if futures.get('open_interest') and slv.get('inventory_ounces'):
            slv_oz = slv['inventory_ounces']
            if isinstance(slv_oz, (int, float)):
                oi_oz = futures['open_interest'] * 5000
                p0_data['COMEX_Dominance'] = round(oi_oz / slv_oz, 2)
        
        # Shanghai Premium (use real-time spot)
        if shfe.get('price') and macro.get('usd_cny') and realtime_spot.get('silver'):
            shfe_price_cny_kg = shfe['price']
            shfe_usd_oz = (shfe_price_cny_kg / 1000 / 31.1035) / macro['usd_cny']
            p0_data['Shanghai_Premium_Implied'] = round(shfe_usd_oz - realtime_spot['silver'], 2)
        
        # LBMA (use metals.dev baseline for LBMA silver price)
        if metals_baseline.get('lbma_silver'):
            p0_data['LBMA_London_Vault_Silver'] = metals_baseline.get('lbma_silver')
        
        # COMEX Delivery (PDF parsing - daily cache)
        cache_key_delivery = 'cme_delivery_daily'
        cached_delivery = self._read_cache(cache_key_delivery)
        
        if cached_delivery and self._is_cache_valid(self._get_cache_path(cache_key_delivery), ttl_minutes=1440):
            # Use cached (24hr TTL)
            delivery_daily = cached_delivery
        else:
            # Fetch fresh
            delivery_daily = self.pdf_parser.parse_daily_issues_stops()
            if not delivery_daily.get('error'):
                self._write_cache(cache_key_delivery, delivery_daily)
        
        if delivery_daily.get('found'):
            p0_data['COMEX_IssuesStops_Silver'] = delivery_daily.get('issued', 0) + delivery_daily.get('stopped', 0)
        
        # MTD Delivery
        cache_key_mtd = 'cme_delivery_mtd'
        cached_mtd = self._read_cache(cache_key_mtd)
        
        if cached_mtd and self._is_cache_valid(self._get_cache_path(cache_key_mtd), ttl_minutes=1440):
            delivery_mtd = cached_mtd
        else:
            delivery_mtd = self.pdf_parser.parse_mtd_deliveries()
            if not delivery_mtd.get('error'):
                self._write_cache(cache_key_mtd, delivery_mtd)
        
        if delivery_mtd.get('found'):
            p0_data['COMEX_Deliveries_MTD'] = delivery_mtd.get('mtd_issued', 0)
        
        # Store to time series
        self.storage.append_data(p0_data)
        
        # Return full dataset
        lbma = self.get_lbma_data()  # Still need estimate for vault tonnes
        
        return {
            'futures': futures,
            'slv': slv,
            'cme': cme,
            'lbma': lbma,
            'macro': macro,
            'options': self.get_options_data(),
            'cot': self.get_cot_data(),
            'shfe': shfe,
            'metals_baseline': metals_baseline,  # 8-hour metals.dev cache
            'realtime_spot': realtime_spot,  # Real-time futures proxy
            'p0_indicators': p0_data,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

if __name__ == "__main__":
    fetcher = SilverDataFetcher()
    data = fetcher.get_all_data_and_store()
    print(json.dumps(data, indent=2, ensure_ascii=False))
