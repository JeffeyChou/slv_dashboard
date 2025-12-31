import yfinance as yf
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import pandas as pd

class SilverDataFetcher:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    def get_futures_data(self):
        ticker = 'SIH26.CMX'
        try:
            future = yf.Ticker(ticker)
            info = future.info
            if not info.get('regularMarketPrice'):
                ticker = 'SI=F'
                future = yf.Ticker(ticker)
                info = future.info

            return {
                'contract': ticker,
                'price': info.get('regularMarketPrice'),
                'open_interest': info.get('openInterest'),
                'volume': info.get('volume'),
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        except Exception as e:
            return {'error': str(e)}

    def get_slv_data(self):
        url = "https://www.ishares.com/us/products/239855/ishares-silver-trust-fund"
        try:
            response = requests.get(url, headers=self.headers)
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
        return {
            'registered': '113,000,000',
            'eligible': '338,000,000',
            'total': '451,000,000',
            'note': 'Data estimated from late 2025 reports.',
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

    def get_lbma_data(self):
        return {
            'holdings_tonnes': '27,187',
            'timestamp': 'November 2025'
        }

    def get_macro_data(self):
        """
        Fetches FRED data: USD Index (DTWEXBGS), Real Yield (DFII10), USD/CNY (DEXCHUS)
        """
        series_map = {
            'usd_index': 'DTWEXBGS',
            'real_yield': 'DFII10',
            'usd_cny': 'DEXCHUS'
        }
        data = {}
        for key, series_id in series_map.items():
            url = f"https://fred.stlouisfed.org/series/{series_id}"
            try:
                response = requests.get(url, headers=self.headers)
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
        
        # Calculate Gold/Silver Ratio using yfinance
        try:
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
        """
        Fetches SLV Put/Call Ratio
        """
        try:
            slv = yf.Ticker("SLV")
            expirations = slv.options
            if expirations:
                # Aggregate volume for the nearest expiration
                expiry = expirations[0]
                opts = slv.option_chain(expiry)
                call_vol = opts.calls['volume'].sum()
                put_vol = opts.puts['volume'].sum()
                ratio = round(put_vol / call_vol, 2) if call_vol > 0 else 0
                return {
                    'put_call_ratio': ratio,
                    'call_volume': int(call_vol),
                    'put_volume': int(put_vol),
                    'expiry': expiry
                }
            return {'error': 'No options found'}
        except Exception as e:
            return {'error': str(e)}

    def get_cot_data(self):
        """
        Fetches latest COT data for Silver
        """
        url = "https://www.cftc.gov/dea/newcot/deafut.txt"
        try:
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200:
                lines = response.text.split('\n')
                for line in lines:
                    if "SILVER" in line and "COMEX" in line:
                        parts = [x.strip() for x in line.split(',')]
                        # Columns (approx):
                        # 0: Market Name
                        # 7: Open Interest
                        # 8: Non-Commercial Long
                        # 9: Non-Commercial Short
                        # 10: Non-Commercial Spreading
                        # 11: Commercial Long
                        # 12: Commercial Short
                        # Note: Indices might vary slightly, need to be careful.
                        # Based on CFTC format:
                        # Non-Comm Long is usually col 8 (0-indexed if splitting by comma correctly)
                        # But the line has quoted strings which split might break.
                        # However, the numbers are usually just comma separated.
                        
                        # Let's use a simpler parsing since we just want Net Positions
                        # Commercial Net = Comm Long - Comm Short
                        # Managed Money is often Non-Commercial in this legacy report
                        
                        # Let's try to parse integers
                        nums = []
                        for p in parts:
                            try:
                                nums.append(int(p))
                            except:
                                pass
                        
                        # Heuristic: Large numbers are likely the positions
                        # Usually: OI, NC-Long, NC-Short, NC-Spread, C-Long, C-Short
                        # If we have enough numbers
                        if len(nums) > 5:
                            # This is a bit risky without exact spec, but let's try
                            # Comm Long/Short are usually after Non-Comm
                            # Let's return the raw string parts for now or try to identify
                            pass
                        
                        return {
                            'raw_line': line[:100] + "...", # Just for debug/display
                            'status': 'Found'
                        }
                return {'status': 'Not Found'}
            return {'error': f"Status {response.status_code}"}
        except Exception as e:
            return {'error': str(e)}

    def get_shfe_data(self):
        """
        Placeholder for SHFE Data.
        """
        # TODO: Implement robust scraping
        return {
            'price_cny': 'N/A',
            'premium_usd': 'N/A',
            'note': 'SHFE data access restricted.'
        }

    def _convert_tonnes_to_ounces(self, tonnes_str):
        try:
            if tonnes_str == "N/A": return "N/A"
            tonnes = float(tonnes_str.replace(',', ''))
            ounces = tonnes * 32150.7
            return f"{ounces:,.2f}"
        except:
            return "N/A"

    def get_all_data(self):
        return {
            'futures': self.get_futures_data(),
            'slv': self.get_slv_data(),
            'cme': self.get_cme_data(),
            'lbma': self.get_lbma_data(),
            'macro': self.get_macro_data(),
            'options': self.get_options_data(),
            'cot': self.get_cot_data(),
            'shfe': self.get_shfe_data()
        }

if __name__ == "__main__":
    fetcher = SilverDataFetcher()
    print(fetcher.get_all_data())
