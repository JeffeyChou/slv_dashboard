import yfinance as yf
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
    Fetches silver market data from multiple sources.

    Used methods:
    - get_futures_data() - COMEX futures with OI delta
    - get_slv_data() - SLV ETF holdings
    - get_cme_data() - COMEX inventory
    - get_shfe_data() - SHFE data from barchart
    - get_all_data_and_store() - Aggregate all data
    """

    def __init__(self, cache_dir="./cache", db_manager=None):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
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
        except:
            return None

    def _write_cache(self, key, data):
        cache_path = self._get_cache_path(key)
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Warning: Could not write cache for {key}: {e}")

    def get_futures_data(self):
        """Fetch COMEX futures data with OI delta calculation."""
        try:
            future = yf.Ticker("SI=F")
            info = future.info

            if not info.get("regularMarketPrice"):
                future = yf.Ticker("SIH26.CMX")
                info = future.info

            # Calculate OI delta from database
            current_oi = info.get("openInterest")
            delta_oi = None
            if current_oi:
                delta_oi = self.db.get_metric_delta("COMEX_Futures_OI")

            return {
                "contract": "SI=F (Active)",
                "price": info.get("regularMarketPrice"),
                "open_interest": current_oi,
                "volume": info.get("volume"),
                "previous_close": info.get("previousClose"),
                "delta_oi": delta_oi,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        except Exception as e:
            return {"error": str(e)}

    def get_slv_data(self):
        """Fetch SLV ETF holdings data."""
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

    def get_shfe_data(self):
        """Fetch SHFE data from barchart.com with delta calculation."""
        try:
            url = "https://www.barchart.com/futures/quotes/XOH26/overview"
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
            }
            resp = requests.get(url, headers=headers, timeout=15)

            cny_rate = yf.Ticker("CNY=X").history(period="1d")["Close"].iloc[-1]

            # Extract price
            price_match = re.search(r'"lastPrice":([0-9,]+)', resp.text)
            if not price_match:
                return {"status": "Error", "note": "Price not found on barchart"}

            price_cny = float(price_match.group(1).replace(",", ""))
            price_usd_oz = round((price_cny / cny_rate) / 32.1507, 2)

            # Extract volume and OI
            raw = re.search(
                r"&quot;raw&quot;:\{[^}]*&quot;volume&quot;:([0-9]+)[^}]*&quot;openInterest&quot;:([0-9]+)",
                resp.text,
            )
            if not raw:
                return {"status": "Error", "note": "Volume/OI not found on barchart"}

            volume = int(raw.group(1))
            oi = int(raw.group(2))

            turnover = round(volume / oi, 4) if oi > 0 else 0

            # Delta OI from database
            delta_oi = self.db.get_metric_delta("OI_ag2603")

            return {
                "contract": "ag2603",
                "price": price_cny,
                "price_usd_oz": price_usd_oz,
                "oi": oi,
                "volume": volume,
                "turnover_ratio": turnover,
                "delta_oi": delta_oi,
                "cny_rate": round(cny_rate, 4),
                "status": "Success",
                "source": "Barchart Live",
            }

        except Exception as e:
            return {"status": "Error", "note": str(e)}

    def _convert_tonnes_to_ounces(self, tonnes_str):
        try:
            if tonnes_str == "N/A":
                return "N/A"
            tonnes = float(str(tonnes_str).replace(",", ""))
            ounces = tonnes * 32150.7
            return ounces
        except:
            return None

    def get_all_data_and_store(self):
        """
        Fetch all data, calculate P0 indicators, and store to database.
        Simplified version - removed unused API calls.
        """
        # Fetch base data
        shfe = self.get_shfe_data()
        cme = self.get_cme_data()
        futures = self.get_futures_data()
        slv = self.get_slv_data()

        # Calculate P0 indicators
        p0_data = {}

        # SHFE metrics
        if shfe.get("status") == "Success":
            p0_data["OI_ag2603"] = shfe.get("oi")
            p0_data["VOL_ag2603"] = shfe.get("volume")
            p0_data["Turnover_ag2603"] = shfe.get("turnover_ratio")
            p0_data["ΔOI_ag2603"] = shfe.get("delta_oi")
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

        # Price data
        if futures.get("price") and not futures.get("error"):
            p0_data["COMEX_Futures_Price"] = futures.get("price")
            p0_data["XAGUSD_Spot"] = futures.get("price")  # Use futures as spot proxy

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
            "futures": futures,
            "slv": slv,
            "cme": cme,
            "shfe": shfe,
            "p0_indicators": p0_data,
            "delivery_3days": delivery_3days,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }


if __name__ == "__main__":
    fetcher = SilverDataFetcher()
    data = fetcher.get_all_data_and_store()
    print(json.dumps(data, indent=2, ensure_ascii=False))
