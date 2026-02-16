import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta
import pandas as pd
import io
import json
import os
from cme_pdf_parser import CMEDeliveryParser


class SilverDataFetcher:
    """
    Fetches silver market data from Barchart and other sources.

    Data sources:
    - XAG/USD Spot: https://www.barchart.com/forex/quotes/%5EXAGUSD/overview
    - COMEX Futures (SIH26): https://www.barchart.com/futures/quotes/SIH26/overview
    - SHFE Ag (XOH26): https://www.barchart.com/futures/quotes/XOH26/overview
    - SLV Holdings: iShares website
    - COMEX Inventory: CME delivery reports
    """

    def __init__(self, cache_dir="./cache", db_manager=None):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        self.cache_dir = cache_dir
        self.db = db_manager
        self.pdf_parser = CMEDeliveryParser()
        os.makedirs(cache_dir, exist_ok=True)

        # Lazy import db_manager if not provided
        if self.db is None:
            from db_manager import DBManager

            self.db = DBManager()

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
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _write_cache(self, key, data):
        cache_path = self._get_cache_path(key)
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Warning: Could not write cache for {key}: {e}")

    def _fetch_barchart_data(self, url, symbol_name):
        """
        Generic method to fetch data from Barchart.
        Returns dict with: lastPrice, openInterest, volume, percentChange
        """
        try:
            resp = requests.get(url, headers=self.headers, timeout=15)
            if resp.status_code != 200:
                return {"error": f"HTTP {resp.status_code}"}

            data = {}

            # Extract lastPrice
            price_match = re.search(r'"lastPrice":"?([0-9,\.]+)"?', resp.text)
            if price_match:
                data["lastPrice"] = float(price_match.group(1).replace(",", ""))

            # Extract percentChange
            pct_match = re.search(r'"percentChange":"?(-?[0-9\.]+)"?', resp.text)
            if pct_match:
                data["percentChange"] = float(pct_match.group(1))

            # Extract openInterest (for futures)
            # Try multiple patterns
            oi_match = re.search(r'"openInterest":"?([0-9,]+)"?', resp.text)
            if oi_match:
                data["openInterest"] = int(oi_match.group(1).replace(",", ""))
            else:
                # Alternative pattern in raw data
                raw_oi = re.search(r"&quot;openInterest&quot;:([0-9]+)", resp.text)
                if raw_oi:
                    data["openInterest"] = int(raw_oi.group(1))

            # Extract volume
            vol_match = re.search(r'"volume":"?([0-9,]+)"?', resp.text)
            if vol_match:
                data["volume"] = int(vol_match.group(1).replace(",", ""))
            else:
                raw_vol = re.search(r"&quot;volume&quot;:([0-9]+)", resp.text)
                if raw_vol:
                    data["volume"] = int(raw_vol.group(1))

            # Extract previousClose
            prev_match = re.search(r'"previousClose":"?([0-9,\.]+)"?', resp.text)
            if prev_match:
                data["previousClose"] = float(prev_match.group(1).replace(",", ""))

            data["symbol"] = symbol_name
            data["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            data["source"] = "Barchart"

            return data

        except Exception as e:
            return {"error": str(e)}

    def get_spot_xagusd(self):
        """
        Fetch XAG/USD spot price from Barchart.
        Source: https://www.barchart.com/forex/quotes/%5EXAGUSD/overview
        """
        url = "https://www.barchart.com/forex/quotes/%5EXAGUSD/overview"
        data = self._fetch_barchart_data(url, "XAGUSD")

        if data.get("error"):
            return data

        result = {
            "price": data.get("lastPrice"),
            "change_pct": data.get("percentChange"),
            "previous_close": data.get("previousClose"),
            "timestamp": data.get("timestamp"),
            "source": "Barchart",
        }

        # Store to database
        if result.get("price"):
            self.db.insert(
                "XAGUSD_SPOT", price=result["price"], raw_data=json.dumps(result)
            )
            self.db.append_metrics({"XAGUSD_Spot": result["price"]})

        return result

    def _convert_symbol_to_cme_code(self, symbol):
        """
        Convert symbol like SIH26 to CME PDF code MAR26.
        Map: F=JAN, G=FEB, H=MAR, J=APR, K=MAY, M=JUN, N=JUL, Q=AUG, U=SEP, V=OCT, X=NOV, Z=DEC
        """
        cme_month_map = {
            'F': 'JAN', 'G': 'FEB', 'H': 'MAR', 'J': 'APR', 'K': 'MAY', 'M': 'JUN',
            'N': 'JUL', 'Q': 'AUG', 'U': 'SEP', 'V': 'OCT', 'X': 'NOV', 'Z': 'DEC'
        }
        
        # Assume format SI[MonthCode][Year] e.g. SIH26
        # regex to capture month code and year
        match = re.search(r"SI([FGHJKMNQUVXZ])(\d{2})", symbol)
        if match:
            code = match.group(1)
            year = match.group(2)
            month = cme_month_map.get(code)
            if month:
                return f"{month}{year}"
        return None

    def get_futures_data(self):
        """
        Fetch COMEX Silver Futures (SIH26 - March 2026).
        Prioritizes Barchart for contract specifics, falls back to Yahoo Finance.
        Uses CME Daily Bulletin for authoritative OI and Delta OI.
        """
        symbol = "SIH26"
        
        # 1. Fetch Real-time/Delayed Price from Barchart
        url = f"https://www.barchart.com/futures/quotes/{symbol}/overview"
        data = self._fetch_barchart_data(url, symbol)
        
        result = {
            "contract": "SIH26 (Mar 2026)",
            "price": None,
            "open_interest": None,
            "volume": None,
            "previous_close": None,
            "change_pct": None,
            "delta_oi": None,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": "Barchart",
        }

        # Barchart Data
        if not data.get("error"):
            result.update({
                "price": data.get("lastPrice"),
                "volume": data.get("volume"),
                "previous_close": data.get("previousClose"),
                "change_pct": data.get("percentChange"),
                "open_interest": data.get("openInterest"), # Fallback
            })
        else:
            print(f"⚠ Barchart {symbol} failed, trying Yahoo Finance...")
            try:
                import yfinance as yf
                t = yf.Ticker(f"{symbol}.CMX")
                info = t.info
                result.update({
                    "price": info.get("regularMarketPrice") or info.get("currentPrice"),
                    "volume": info.get("volume"),
                    "previous_close": info.get("previousClose"),
                    "open_interest": info.get("openInterest"),
                    "source": "Yahoo Finance (CME)",
                })
                if result["price"] and result["previous_close"]:
                    result["change_pct"] = round(((result["price"] - result["previous_close"]) / result["previous_close"]) * 100, 2)
            except Exception as e:
                print(f"⚠ Yahoo Finance {symbol} failed: {e}")

        cme_code = self._convert_symbol_to_cme_code(symbol)  # e.g. MAR26
        if cme_code and not result.get("open_interest"):
            try:
                parser = CMEDeliveryParser()
                pdf_data = parser.parse_section62_daily_bulletin(
                    target_contract_code=cme_code
                )

                if "error" not in pdf_data:
                    result["open_interest"] = pdf_data["open_interest"]
                    result["delta_oi"] = pdf_data["delta_oi"]
                    result["source"] += " + CME PDF"

                    # If we have no price yet, use PDF price (Close)
                    if not result["price"]:
                        result["price"] = pdf_data["price"]
                        # Logic for change matching pdf?
            except Exception as e:
                print(f"⚠ CME PDF Parsing failed: {e}")

        # 3. Fallback for Delta OI if not in PDF (e.g. PDF failed)
        if result["open_interest"] and result["delta_oi"] is None:
            result["delta_oi"] = self.db.get_metric_delta("COMEX_Futures_OI")
            
        # Record metrics
        if result["open_interest"]:
            self.db.append_metrics({
                "COMEX_Futures_OI": result["open_interest"],
                "COMEX_Futures_Price": result["price"]
            })
            
        if result["price"]:
            self.db.insert("COMEX_FUTURES", price=result["price"], raw_data=json.dumps(result))

        return result

    def get_shfe_data(self):
        """
        Fetch SHFE Silver Futures (XOH26 - March 2026) from Barchart.
        Source: https://www.barchart.com/futures/quotes/XOH26/overview
        Returns price in CNY/kg, converted to USD/oz.
        """
        url = "https://www.barchart.com/futures/quotes/XOH26/overview"
        data = self._fetch_barchart_data(url, "XOH26")

        if data.get("error"):
            return {"status": "Error", "note": data.get("error")}

        price_cny = data.get("lastPrice")
        if not price_cny:
            return {"status": "Error", "note": "Price not found"}

        # Get CNY/USD rate for conversion
        try:
            import yfinance as yf

            cny_rate = yf.Ticker("CNY=X").history(period="1d")["Close"].iloc[-1]
        except Exception:
            cny_rate = 7.25  # Fallback rate

        # Convert CNY/kg to USD/oz
        # 1 kg = 32.1507 oz
        price_usd_oz = round((price_cny / cny_rate) / 32.1507, 2)

        current_oi = data.get("openInterest")
        delta_oi = None
        if current_oi:
            delta_oi = self.db.get_metric_delta("OI_ag2603")

        result = {
            "contract": "ag2603 (XOH26)",
            "price": price_cny,
            "price_usd_oz": price_usd_oz,
            "oi": current_oi,
            "delta_oi": delta_oi,
            "change_pct": data.get("percentChange"),
            "cny_rate": round(cny_rate, 4),
            "timestamp": data.get("timestamp"),
            "status": "Success",
            "source": "Barchart",
        }

        # Store to database
        if current_oi:
            self.db.append_metrics(
                {"OI_ag2603": current_oi, "SHFE_ag2603_Price": price_cny}
            )
        self.db.insert("SHFE", raw_data=json.dumps(result))

        return result

    def get_slv_data(self):
        """Fetch SLV ETF holdings data from iShares."""
        url = "https://www.ishares.com/us/products/239855/ishares-silver-trust-fund"
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, "html.parser")
                text = soup.get_text()

                tonnes = "N/A"
                if "Tonnes in Trust" in text:
                    match = re.search(
                        r"Tonnes in Trust.*?([\d,]+\.?\d*)", text, re.DOTALL
                    )
                    if match:
                        tonnes = match.group(1)

                return {
                    "inventory_tonnes": tonnes,
                    "inventory_ounces": self._convert_tonnes_to_ounces(tonnes),
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
            else:
                return {"error": f"Status {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}

    def get_cme_data(self):
        """Fetch COMEX inventory data with delta calculation."""
        cache_key = "cme_data"

        cached = self._read_cache(cache_key)
        if cached and self._is_cache_valid(
            self._get_cache_path(cache_key), ttl_minutes=1440
        ):
            cached["source"] = "Cache"
            return cached

        url = "https://www.cmegroup.com/delivery_reports/Silver_stocks.xls"
        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            if response.status_code == 200:
                df = pd.read_excel(io.BytesIO(response.content), engine="xlrd")

                total_registered = None
                total_eligible = None

                for i, row in df.iterrows():
                    label = str(row.iloc[0]).strip()
                    if label == "TOTAL REGISTERED":
                        total_registered = float(row.iloc[7])
                    elif label == "TOTAL ELIGIBLE":
                        total_eligible = float(row.iloc[7])

                if total_registered is None or total_eligible is None:
                    return {"error": "Could not find TOTAL REGISTERED/ELIGIBLE rows"}

                total = total_registered + total_eligible
                reg_to_total = (total_registered / total) if total > 0 else 0

                delta_registered = self.db.get_metric_delta("COMEX_Silver_Registered")
                delta_eligible = self.db.get_metric_delta("COMEX_Silver_Eligible")

                result = {
                    "registered": total_registered,
                    "eligible": total_eligible,
                    "total": total,
                    "registered_to_total_ratio": round(reg_to_total, 4),
                    "delta_registered": delta_registered,
                    "delta_eligible": delta_eligible,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "source": "Live",
                }

                self._write_cache(cache_key, result)
                return result
            else:
                return {"error": f"Status {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}

    def _convert_tonnes_to_ounces(self, tonnes_str):
        try:
            if tonnes_str == "N/A":
                return "N/A"
            tonnes = float(str(tonnes_str).replace(",", ""))
            ounces = tonnes * 32150.7
            return ounces
        except Exception:
            return None

    def get_all_data_and_store(self):
        """
        Fetch all data, calculate P0 indicators, and store to database.
        """
        # Fetch all data from Barchart
        spot = self.get_spot_xagusd()
        futures = self.get_futures_data()
        shfe = self.get_shfe_data()

        # Other data sources
        cme = self.get_cme_data()
        slv = self.get_slv_data()

        # Calculate P0 indicators
        p0_data = {}

        # Spot price
        if spot.get("price") and not spot.get("error"):
            p0_data["XAGUSD_Spot"] = spot.get("price")

        # SHFE metrics
        if shfe.get("status") == "Success":
            p0_data["OI_ag2603"] = shfe.get("oi")
            p0_data["SHFE_ag2603_Price"] = shfe.get("price")

        # COMEX metrics
        if not cme.get("error"):
            p0_data["COMEX_Silver_Registered"] = cme.get("registered")
            p0_data["COMEX_Silver_Eligible"] = cme.get("eligible")
            p0_data["ΔCOMEX_Registered"] = cme.get("delta_registered")
            p0_data["Registered_to_Total"] = cme.get("registered_to_total_ratio")

        # COMEX Futures OI tracking
        if futures.get("open_interest"):
            p0_data["COMEX_Futures_OI"] = futures.get("open_interest")
            p0_data["ΔCOMEX_Futures_OI"] = futures.get("delta_oi")

        if futures.get("price") and not futures.get("error"):
            p0_data["COMEX_Futures_Price"] = futures.get("price")

        # Paper to Physical ratio
        if futures.get("open_interest") and cme.get("registered"):
            oi_oz = futures["open_interest"] * 5000
            p0_data["Paper_to_Physical"] = round(oi_oz / cme["registered"], 2)

        # SLV metrics
        if cme.get("registered") and slv.get("inventory_ounces"):
            slv_oz = slv["inventory_ounces"]
            if isinstance(slv_oz, (int, float)):
                p0_data["SLV_Coverage"] = round(cme["registered"] / slv_oz, 4)
                p0_data["SLV_Inventory_Ounces"] = slv_oz
                p0_data["SLV_Inventory_Tonnes"] = slv.get("inventory_tonnes")

        # COMEX Delivery data (PDF parsing with cache)
        cache_key_3days = "cme_delivery_3days"
        cached_3days = self._read_cache(cache_key_3days)

        if cached_3days and self._is_cache_valid(
            self._get_cache_path(cache_key_3days), ttl_minutes=1440
        ):
            delivery_3days = cached_3days
        else:
            delivery_3days = self.pdf_parser.parse_last_3_days_silver()
            if not delivery_3days.get("error"):
                self._write_cache(cache_key_3days, delivery_3days)

        # Store metrics to database
        self.db.append_metrics(p0_data)

        return {
            "spot": spot,
            "futures": futures,
            "shfe": shfe,
            "slv": slv,
            "cme": cme,
            "p0_indicators": p0_data,
            "delivery_3days": delivery_3days,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }


if __name__ == "__main__":
    fetcher = SilverDataFetcher()
    data = fetcher.get_all_data_and_store()
    print(json.dumps(data, indent=2, ensure_ascii=False))
