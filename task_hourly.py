#!/usr/bin/env python3
"""
Silver Market Discord Bot
Fetches market data and forwards to Discord webhook
"""

import os
import json
import requests
import yfinance as yf
from datetime import datetime
from db_manager import DBManager
from data_fetcher import SilverDataFetcher
import pandas as pd
from io import BytesIO, StringIO
import pytz
import sys

WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
CACHE_DIR = "cache"
MSG_ID_FILE = os.path.join(CACHE_DIR, "discord_msg_id.txt")


def get_est_time():
    return datetime.now(pytz.timezone("America/New_York"))


def read_cache(db, name, ttl_hours=24):
    """Read cache from database if valid within TTL"""
    return db.get_cache(name, ttl_hours)


def write_cache(db, name, data):
    """Write cache to database"""
    db.set_cache(name, data)


# ============ HOURLY DATA (Real-time) ============


def fetch_metals_dev_price(metal, currency="USD"):
    """Fetch price from metals.dev API"""
    api_key = os.getenv("METALS_DEV_KEY")
    if not api_key:
        return None

    try:
        url = "https://api.metals.dev/v1/latest"
        headers = {"Accept": "application/json"}
        params = {"api_key": api_key, "currency": currency, "unit": "toz"}
        resp = requests.get(url, params=params, headers=headers, timeout=10)

        if resp.status_code == 200:
            data = resp.json()
            return data.get("metals", {}).get(metal)
    except Exception as e:
        print(f"⚠ Metals.dev failed: {e}")
    return None


def fetch_xagusd():
    """XAG/USD spot price - Try Barchart first, then Metals.dev, then YF"""
    # 1. Try Barchart (via SilverDataFetcher)
    try:
        fetcher = SilverDataFetcher()
        data = fetcher.get_spot_xagusd()
        if data and data.get("price"):
            return data["price"]
    except Exception as e:
        print(f"⚠ Barchart XAG failed: {e}")

    # 2. Try Metals.dev
    price = fetch_metals_dev_price("silver")
    if price:
        return price

    # 3. Fallback to Yahoo Finance
    try:
        t = yf.Ticker("SI=F")
        # Add custom headers to avoid 429
        t.session.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        return t.info.get("regularMarketPrice")
    except:
        return None


def fetch_shanghai_td():
    """Shanghai Ag T+D"""
    try:
        url = "https://www.barchart.com/futures/quotes/XOH26/overview"
        headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
        resp = requests.get(url, headers=headers, timeout=15)
        import re

        data = {}
        cny_rate = yf.Ticker("CNY=X").history(period="1d")["Close"].iloc[-1]

        price_match = re.search(r'"lastPrice":([0-9,]+)', resp.text)
        if price_match:
            price_cny = float(price_match.group(1).replace(",", ""))
            data["price_cny_kg"] = price_cny
            data["price_usd_oz"] = round((price_cny / cny_rate) / 32.1507, 2)

        pct_match = re.search(r'"percentChange":(-?[0-9.]+)', resp.text)
        if pct_match:
            data["change_pct"] = round(float(pct_match.group(1)) * 100, 2)

        raw = re.search(
            r"&quot;raw&quot;:\{[^}]*&quot;volume&quot;:([0-9]+)[^}]*&quot;openInterest&quot;:([0-9]+)",
            resp.text,
        )
        if raw:
            data["volume"] = int(raw.group(1))
            data["oi"] = int(raw.group(2))

        data["cny_rate"] = round(cny_rate, 4)
        return data if data else None
    except Exception as e:
        print(f"⚠ SHFE failed: {e}")
        return None


def fetch_comex_futures():
    """COMEX silver futures - Try Barchart first, then YF"""
    # 1. Try Barchart (via SilverDataFetcher)
    try:
        fetcher = SilverDataFetcher()
        data = fetcher.get_futures_data()
        if data and data.get("price"):
            return {
                "price": data["price"],
                "volume": data.get("volume", 0),
                "oi": data.get("open_interest", 0),
                "prev_close": data.get("previous_close"),
                "delta_oi": data.get("delta_oi"),
            }
    except Exception as e:
        print(f"⚠ Barchart COMEX failed: {e}")

    # 2. Fallback to Yahoo Finance
    try:
        si = yf.Ticker("SI=F")
        si.session.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        info = si.info
        return {
            "price": info.get("regularMarketPrice"),
            "volume": info.get("volume", 0),
            "oi": info.get("openInterest", 0),
            "prev_close": info.get("previousClose"),
        }
    except:
        return None


def fetch_slv_price():
    """SLV ETF price only (hourly)"""
    try:
        slv = yf.Ticker("SLV")
        slv.session.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        info = slv.info
        return {
            "price": info.get("regularMarketPrice"),
            "change_pct": round(
                (
                    (info.get("regularMarketPrice", 0) - info.get("previousClose", 1))
                    / info.get("previousClose", 1)
                )
                * 100,
                2,
            ),
            "volume": info.get("volume", 0),
        }
    except:
        return None


def fetch_gld_price():
    """GLD ETF price only (hourly)"""
    try:
        gld = yf.Ticker("GLD")
        gld.session.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        info = gld.info
        return {
            "price": info.get("regularMarketPrice"),
            "change_pct": round(
                (
                    (info.get("regularMarketPrice", 0) - info.get("previousClose", 1))
                    / info.get("previousClose", 1)
                )
                * 100,
                2,
            ),
            "volume": info.get("volume", 0),
        }
    except:
        return None


def fetch_gold_spot():
    """Gold spot price (hourly) - Try Metals.dev first, then YF"""
    # 1. Try Metals.dev
    price = fetch_metals_dev_price("gold")
    if price:
        return price

    # 2. Fallback to Yahoo Finance
    try:
        gc = yf.Ticker("GC=F")
        gc.session.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        hist = gc.history(period="1d")
        if not hist.empty:
            return round(hist["Close"].iloc[-1], 2)
    except:
        pass
    return None


def fetch_trump_medallions(db, force=False):
    """Fetch Trump medallion prices from realtrumpcoins.com using Shopify JSON API"""
    cache_key = "trump_medallions"
    
    if not force:
        cached, age = read_cache(db, cache_key, ttl_hours=24)
        if cached:
            print(f"✓ Trump Medallions (cached {age}h)")
            return cached, True
    
    try:
        import requests
        
        medallions = {}
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        
        # Silver medallion
        try:
            url_silver = "https://realtrumpcoins.com/products/1-oz-pf70-president-trump-second-edition-silver-medallion.js"
            resp = requests.get(url_silver, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                price = data.get('price', 0) / 100.0
                if price > 0:
                    medallions['silver'] = price
                    print(f"✓ Trump Silver: ${medallions['silver']}")
            else:
                print(f"⚠ Could not fetch silver price JSON (Status {resp.status_code})")
        except Exception as e:
            print(f"⚠ Trump Silver Medallion error: {e}")
        
        # Gold medallion
        try:
            url_gold = "https://realtrumpcoins.com/products/1oz-pf70-president-trump-second-edition-gold-medallion.js"
            resp = requests.get(url_gold, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                price = data.get('price', 0) / 100.0
                if price > 0:
                    medallions['gold'] = price
                    print(f"✓ Trump Gold: ${medallions['gold']}")
            else:
                print(f"⚠ Could not fetch gold price JSON (Status {resp.status_code})")
        except Exception as e:
            print(f"⚠ Trump Gold Medallion error: {e}")
        
        if medallions:
            # Get previous prices to calculate change (from previous day)
            today_str = get_est_time().strftime("%Y-%m-%d")
            
            if 'silver' in medallions:
                prev_silver = db.get_last_metric_value_before_date("trump_silver_price", today_str)
                medallions['silver_prev'] = prev_silver
                medallions['silver_change'] = (medallions['silver'] - prev_silver) if prev_silver else 0
            
            if 'gold' in medallions:
                prev_gold = db.get_last_metric_value_before_date("trump_gold_price", today_str)
                medallions['gold_prev'] = prev_gold
                medallions['gold_change'] = (medallions['gold'] - prev_gold) if prev_gold else 0
            
            write_cache(db, cache_key, medallions)
            return medallions, False
        
    except Exception as e:
        print(f"✗ Trump Medallions error: {e}")
    
    return None, False


# ============ DAILY DATA (24h cache) ============


def fetch_usdcny(db, force=False):
    """USD/CNY rate - daily"""
    cached, age = read_cache(db, "usdcny", 24)
    if cached and not force:
        print(f"✓ USD/CNY (cached {age}h)")
        return cached, True

    try:
        rate = yf.Ticker("CNY=X").history(period="1d")["Close"].iloc[-1]
        data = {"rate": round(rate, 4), "ts": datetime.now().isoformat()}
        write_cache(db, "usdcny", data)
        print(f"✓ USD/CNY: {rate:.4f} (fresh)")
        return data, False
    except Exception:
        return cached, True if cached else (None, False)


def fetch_slv_holdings(db, force=False):
    """SLV ETF holdings - daily"""
    cached, age = read_cache(db, "slv_holdings", 24)

    if cached and not force:
        print(f"✓ SLV holdings (cached {age}h)")
        return cached, True, False  # data, is_cached, etf_updated

    try:
        url = "https://www.ishares.com/us/products/239855/ishares-silver-trust-fund"
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        import re

        match = re.search(r"(\d{3},\d{3},\d{3}\.\d+)", resp.text)
        if match:
            holdings = float(match.group(1).replace(",", ""))

            # Get last different value from database
            prev_holdings = db.get_last_different_value("SLV_HOLDINGS", holdings)
            if not prev_holdings:
                prev_holdings = db.get_last_different_value("SLV", holdings)

            change = int(holdings - prev_holdings) if prev_holdings else 0
            data = {
                "holdings_oz": holdings,
                "change": change,
                "ts": datetime.now().isoformat(),
            }
            write_cache(db, "slv_holdings", data)
            print(f"✓ SLV holdings: {holdings:,.0f} oz ({change:+,} oz)")

            # === Sync to metrics table for chart generation ===
            oz_to_tonnes = 0.0000311035
            slv_tonnes = holdings * oz_to_tonnes
            latest_slv = db.get_latest_metric_value("SLV_Holdings_Tonnes")
            etf_updated = False

            if latest_slv is None or abs(slv_tonnes - latest_slv) > 0.01:
                today = get_est_time().strftime("%Y-%m-%d 00:00:00")
                db.insert_metric(today, "SLV_Holdings_Tonnes", slv_tonnes)
                if latest_slv:
                    daily_change = slv_tonnes - latest_slv
                    db.insert_metric(today, "SLV_Daily_Change_Tonnes", daily_change)
                    print(
                        f"  └ 📊 SLV metrics updated: {slv_tonnes:,.2f}t (Δ{daily_change:+,.2f}t)"
                    )
                else:
                    print(f"  └ 📊 SLV metrics initialized: {slv_tonnes:,.2f}t")
                etf_updated = True

            return data, False, etf_updated
    except Exception:
        pass
    return cached, True, False if cached else (None, False, False)


def fetch_gld_holdings(db, force=False):
    """GLD ETF holdings - daily"""
    cached, age = read_cache(db, "gld_holdings", 24)

    if cached and not force:
        print(f"✓ GLD holdings (cached {age}h)")
        return cached, True, False  # data, is_cached, etf_updated

    try:
        import time
        url = f"https://www.spdrgoldshares.com/assets/dynamic/GLD/GLD_US_archive_EN.csv?t={int(time.time())}"
        resp = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        df = pd.read_csv(StringIO(resp.text))

        last = df.iloc[-1]
        tonnes = float(
            last[" Total Net Asset Value Tonnes in the Trust as at 4.15 p.m. NYT"]
        )
        ounces = float(
            last[" Total Net Asset Value Ounces in the Trust as at 4.15 p.m. NYT"]
        )

        # Get last different value from database
        prev_tonnes = db.get_last_different_value(
            "GLD_HOLDINGS", tonnes, key="holdings_tonnes"
        )

        change_tonnes = tonnes - prev_tonnes if prev_tonnes else 0
        data = {
            "holdings_tonnes": tonnes,
            "holdings_oz": ounces,
            "change_tonnes": change_tonnes,
            "ts": datetime.now().isoformat(),
        }
        write_cache(db, "gld_holdings", data)
        print(f"✓ GLD holdings: {tonnes:,.2f} tonnes ({change_tonnes:+,.2f}t)")

        # === Sync to metrics table for chart generation ===
        latest_gld = db.get_latest_metric_value("GLD_Holdings_Tonnes")
        etf_updated = False

        if latest_gld is None or abs(tonnes - latest_gld) > 0.01:
            today = get_est_time().strftime("%Y-%m-%d 00:00:00")
            db.insert_metric(today, "GLD_Holdings_Tonnes", tonnes)
            if latest_gld:
                daily_change = tonnes - latest_gld
                db.insert_metric(today, "GLD_Daily_Change_Tonnes", daily_change)
                print(
                    f"  └ 📊 GLD metrics updated: {tonnes:,.2f}t (Δ{daily_change:+,.2f}t)"
                )
            else:
                print(f"  └ 📊 GLD metrics initialized: {tonnes:,.2f}t")
            etf_updated = True

        return data, False, etf_updated
    except Exception as e:
        print(f"⚠ GLD holdings failed: {e}")
    return cached, True, False if cached else (None, False, False)


def fetch_comex_inventory(db, force=False):
    """COMEX physical inventory - daily"""
    cached, age = read_cache(db, "comex_inv", 24)

    if cached and not force:
        print(f"✓ COMEX inventory (cached {age}h)")
        return cached, True

    try:
        url = "https://www.cmegroup.com/delivery_reports/Silver_stocks.xls"
        resp = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        df = pd.read_excel(BytesIO(resp.content), engine="xlrd")

        registered = eligible = None
        delta_reg = delta_elig = None
        registered_adjustment = eligible_adjustment = 0.0

        for _, row in df.iterrows():
            label = str(row.iloc[0]).strip()
            if label == "TOTAL REGISTERED":
                prev_total = float(row.iloc[2])  # PREV TOTAL
                registered_adjustment = float(row.iloc[6])  # ADJUSTMENT
                registered = float(row.iloc[7])  # TOTAL TODAY
                delta_reg = int(registered - prev_total)
            elif label == "TOTAL ELIGIBLE":
                prev_total = float(row.iloc[2])  # PREV TOTAL
                eligible_adjustment = float(row.iloc[6])  # ADJUSTMENT
                eligible = float(row.iloc[7])  # TOTAL TODAY
                delta_elig = int(eligible - prev_total)

        if registered and eligible:
            data = {
                "registered": registered,
                "eligible": eligible,
                "registered_adjustment": registered_adjustment,
                "eligible_adjustment": eligible_adjustment,
                "total": registered + eligible,
                "reg_ratio": round(registered / (registered + eligible) * 100, 2),
                "delta_registered": delta_reg if delta_reg is not None else 0,
                "delta_eligible": delta_elig if delta_elig is not None else 0,
                "ts": datetime.now().isoformat(),
            }
            write_cache(db, "comex_inv", data)
            print(f"✓ COMEX inventory: {registered:,.0f} oz ({delta_reg:+,} oz)")
            return data, False
    except Exception as e:
        print(f"⚠ COMEX inventory failed: {e}")

    return cached, True if cached else (None, False)


def send_discord(msg):
    if not WEBHOOK_URL:
        print("⚠ No Discord webhook URL configured")
        return

    os.makedirs(CACHE_DIR, exist_ok=True)

    # Try to edit existing message
    message_sent = False
    if os.path.exists(MSG_ID_FILE):
        with open(MSG_ID_FILE) as f:
            msg_id = f.read().strip()
        if msg_id:
            edit_url = f"{WEBHOOK_URL}/messages/{msg_id}"
            try:
                resp = requests.patch(edit_url, json={"content": msg}, timeout=10)
                if resp.status_code == 200:
                    print(f"✓ Discord message updated (ID: {msg_id})")
                    return
                else:
                    print(
                        f"⚠ Failed to edit message (status {resp.status_code}), sending new one"
                    )
            except Exception as e:
                print(f"⚠ Error editing message: {e}, sending new one")

    # Send new message and save ID
    try:
        resp = requests.post(
            f"{WEBHOOK_URL}?wait=true", json={"content": msg}, timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            msg_id = data.get("id", "")
            if msg_id:
                with open(MSG_ID_FILE, "w") as f:
                    f.write(msg_id)
                print(f"✓ New Discord message sent (ID: {msg_id})")
            else:
                print("✓ Discord message sent (no ID returned)")
        else:
            print(f"⚠ Failed to send Discord message (status {resp.status_code})")
    except Exception as e:
        print(f"⚠ Error sending Discord message: {e}")


def get_market_update_message(force=False):
    """Generate the market update message string"""
    db = DBManager()

    # === REAL-TIME DATA ===
    print("\n=== Real-time Data ===")
    xagusd = fetch_xagusd()
    shfe = fetch_shanghai_td()
    comex = fetch_comex_futures()
    slv = fetch_slv_price()
    gld = fetch_gld_price()
    gold_spot = fetch_gold_spot()

    # === GET ADDITIONAL DATA FROM MAIN FETCHER ===
    print("\n=== Fetching OI deltas and delivery data ===")
    try:
        fetcher = SilverDataFetcher()

        # Get futures data with OI delta
        futures_data = fetcher.get_futures_data()
        if futures_data and not futures_data.get("error"):
            if comex:
                comex["delta_oi"] = futures_data.get("delta_oi")
                print(f"✓ COMEX OI Delta: {comex.get('delta_oi')}")

        # Get SHFE data with OI delta - use the barchart data, not JSON file
        shfe_data = fetcher.get_shfe_data()
        if shfe_data and shfe_data.get("status") == "Success":
            if shfe:
                # Use the live barchart data but get delta from database
                shfe["delta_oi"] = shfe_data.get("delta_oi")
                print(f"✓ SHFE OI Delta: {shfe.get('delta_oi')}")
            else:
                # If no SHFE data from hourly fetch, use the main fetcher data
                shfe = {
                    "price_usd_oz": round(
                        (shfe_data.get("price", 0) / 6.96) / 32.1507, 2
                    )
                    if shfe_data.get("price")
                    else None,
                    "price_cny_kg": shfe_data.get("price"),
                    "volume": shfe_data.get("volume"),
                    "oi": shfe_data.get("oi"),
                    "delta_oi": shfe_data.get("delta_oi"),
                    "change_pct": 0,  # Default since we don't have this from main fetcher
                }
        else:
            # Fallback: if main fetcher fails, keep the barchart data but no delta
            if shfe:
                shfe["delta_oi"] = None
                print("⚠ SHFE OI Delta: Not available (main fetcher failed)")

        # Get 3-day delivery data
        delivery_3days = fetcher.pdf_parser.parse_last_3_days_silver()
        print(f"✓ 3-day delivery data: {delivery_3days.get('found', False)}")

    except Exception as e:
        print(f"⚠ Error fetching additional data: {e}")
        delivery_3days = {"error": str(e)}

    if xagusd:
        db.insert("XAGUSD", price=xagusd)
        print(f"✓ XAG/USD: ${xagusd}")
    if comex:
        db.insert("COMEX", price=comex["price"], raw_data=json.dumps(comex))
        print(f"✓ COMEX: ${comex['price']}")
    if shfe:
        db.insert("SHFE", raw_data=json.dumps(shfe))
        print(f"✓ SHFE: ${shfe.get('price_usd_oz')}/oz")
    if slv:
        db.insert("SLV", price=slv["price"], raw_data=json.dumps(slv))
        print(f"✓ SLV: ${slv['price']}")
    if gld:
        db.insert("GLD", price=gld["price"], raw_data=json.dumps(gld))
        print(f"✓ GLD: ${gld['price']}")
    if gold_spot:
        db.insert("GOLD_SPOT", price=gold_spot)
        print(f"✓ Gold Spot: ${gold_spot}")

    # === DAILY DATA (24h cache) ===
    print("\n=== Daily Data (24h cache) ===")
    usdcny, usdcny_cached = fetch_usdcny(db, force)
    slv_hold, slv_hold_cached, slv_etf_updated = fetch_slv_holdings(db, force)
    gld_hold, gld_hold_cached, gld_etf_updated = fetch_gld_holdings(db, force)
    comex_inv, comex_inv_cached = fetch_comex_inventory(db, force)
    trump_medallions, trump_cached = fetch_trump_medallions(db, force)

    # Track if any ETF data was updated
    etf_updated = slv_etf_updated or gld_etf_updated

    if comex_inv:
        db.insert("COMEX_INV", raw_data=json.dumps(comex_inv))
    if slv_hold:
        db.insert("SLV_HOLDINGS", raw_data=json.dumps(slv_hold))
    if gld_hold:
        db.insert("GLD_HOLDINGS", raw_data=json.dumps(gld_hold))
    if trump_medallions:
        db.insert("TRUMP_MEDALLIONS", raw_data=json.dumps(trump_medallions))
        # Store as metrics for delta tracking
        if trump_medallions.get('silver'):
            db.insert_metric(get_est_time().isoformat(), "trump_silver_price", trump_medallions['silver'])
        if trump_medallions.get('gold'):
            db.insert_metric(get_est_time().isoformat(), "trump_gold_price", trump_medallions['gold'])

    # === DISCORD MESSAGE ===
    est = get_est_time()
    ts = est.strftime("%Y-%m-%d %I:%M %p EST")

    msg = f"**📊 Silver Market Update** - {ts}\n\n"

    # Spot & Futures (30min)
    msg += "**💹 Real-time Prices**\n"
    if xagusd:
        msg += f"• XAG/USD Spot: **${xagusd:.2f}**/oz\n"
    if gold_spot:
        msg += f"• XAU/USD Spot: **${gold_spot:.2f}**/oz\n"
    if comex:
        price_val = comex['price']
        prev_close = comex.get('previous_close')
        change_str = ""
        if prev_close:
            diff = price_val - prev_close
            pct = (diff / prev_close) * 100
            arrow = "🔺" if diff > 0 else "🔻" if diff < 0 else "➡️"
            change_str = f" {arrow}${abs(diff):.2f} ({pct:+.2f}%)"
            
        msg += f"• COMEX (SIH26): **${price_val:.2f}**/oz{change_str}\n"
        if comex.get("oi"):
            msg += f"  └ OI: {comex['oi']:,}"
            if comex.get("delta_oi") is not None:
                msg += f" (ΔOI: {comex['delta_oi']:+,.0f})"
            msg += "\n"
            msg += f"  └ Physical equiv: {(comex['oi'] * 5000 / 32150.7):,.2f}t\n"
    if shfe:
        msg += f"• SHFE Ag (XOH26): **${shfe.get('price_usd_oz')}**/oz (¥{shfe.get('price_cny_kg', 0):,.0f}/kg)"
        if shfe.get("change_pct") is not None:
            msg += f" {shfe['change_pct']:+.2f}%"
        msg += "\n"
        if shfe.get("oi"):
            msg += f"  └ OI: {shfe['oi']:,}"
            if shfe.get("delta_oi") is not None:
                msg += f" (ΔOI: {shfe['delta_oi']:+,.0f})"
            msg += "\n"
            msg += f"  └ Physical equiv: {(shfe['oi'] * 15 / 1000):,.2f}t\n"
        if xagusd and shfe.get("price_usd_oz"):
            premium = shfe["price_usd_oz"] - xagusd
            msg += f"  └ Shanghai Premium: **${premium:+.2f}**\n"
    if slv:
        arrow = "🔺" if slv["change_pct"] > 0 else "🔻"
        msg += f"• SLV ETF: **${slv['price']:.2f}** {arrow}{slv['change_pct']:+.2f}%\n"
    if gld:
        arrow = "🔺" if gld["change_pct"] > 0 else "🔻"
        msg += f"• GLD ETF: **${gld['price']:.2f}** {arrow}{gld['change_pct']:+.2f}%\n"

    # Daily data - Physical Holdings (format: tonnes first, then oz)
    msg += f"\n**📦 Physical Holdings** `[Daily{'*' if not force else ' ✓'}]`\n"

    # Conversion constant
    oz_to_tonnes = 1 / 32150.7  # 1 oz = 0.0000311035 tonnes

    if comex_inv:
        # COMEX data is in oz, convert to tonnes for display
        reg_tonnes = comex_inv["registered"] * oz_to_tonnes
        elig_tonnes = comex_inv["eligible"] * oz_to_tonnes

        msg += f"• COMEX Registered: **{reg_tonnes:,.2f}** tonnes (**{comex_inv['registered']:,.0f}** oz)"
        if comex_inv.get("delta_registered") is not None:
            delta_oz = comex_inv["delta_registered"]
            delta_t = delta_oz * oz_to_tonnes
            msg += f" ({delta_t:+.2f}t / {delta_oz:+,} oz)"
        msg += "\n"
        msg += f"          └ Adjustment: {comex_inv['registered_adjustment']:,.0f} oz\n"

        msg += f"• COMEX Eligible: **{elig_tonnes:,.2f}** tonnes (**{comex_inv['eligible']:,.0f}** oz)"
        if comex_inv.get("delta_eligible") is not None:
            delta_oz = comex_inv["delta_eligible"]
            delta_t = delta_oz * oz_to_tonnes
            msg += f" ({delta_t:+.2f}t / {delta_oz:+,} oz)"
        msg += "\n"
        msg += f"          └ Adjustment: {comex_inv['eligible_adjustment']:,.0f} oz\n"
        msg += f"  └ Reg/Total: {comex_inv['reg_ratio']}%\n"

    if slv_hold:
        # SLV holdings in oz, convert to tonnes
        slv_tonnes = slv_hold["holdings_oz"] * oz_to_tonnes
        msg += f"• SLV Trust: **{slv_tonnes:,.2f}** tonnes (**{slv_hold['holdings_oz']:,.0f}** oz)"
        if slv_hold.get("change") is not None:
            delta_oz = slv_hold["change"]
            delta_t = delta_oz * oz_to_tonnes
            msg += f" ({delta_t:+.2f}t / {delta_oz:+,} oz)"
        msg += "\n"

    if gld_hold:
        # GLD already has both tonnes and oz
        msg += f"• GLD Trust: **{gld_hold['holdings_tonnes']:,.2f}** tonnes (**{gld_hold['holdings_oz']:,.0f}** oz)"
        if gld_hold.get("change_tonnes") is not None:
            # Calculate oz change from tonnes change
            change_oz = gld_hold["change_tonnes"] * 32150.7
            msg += f" ({gld_hold['change_tonnes']:+.2f}t / {change_oz:+,.0f} oz)"
        msg += "\n"

    msg += f"\n**💱 FX Rate** `[Daily{'*' if not force else ' ✓'}]`\n"
    if usdcny:
        msg += f"• USD/CNY: **{usdcny['rate']}**\n"

    # Add Trump Medallions
    if trump_medallions:
        msg += f"\n**🪙 Trump Medallions** `[Daily{'*' if not force else ' ✓'}]`\n"
        if trump_medallions.get('silver'):
            curr = trump_medallions['silver']
            prev = trump_medallions.get('silver_prev')
            change = trump_medallions.get('silver_change', 0)
            pct = (change / prev * 100) if prev and prev > 0 else 0
            arrow = "🔺" if change > 0 else "🔻" if change < 0 else "➡️"
            premium_vs_spot = curr - xagusd if xagusd else None
            
            msg += f"• Silver (1oz PF70): **${curr:.2f}**"
            if prev:
                msg += f" (Prev: ${prev:.2f}) {arrow}${abs(change):.2f} ({pct:+.2f}%)"
            if premium_vs_spot:
                msg += f" (Premium: ${premium_vs_spot:+.2f})"
            msg += "\n"
            
        if trump_medallions.get('gold'):
            curr = trump_medallions['gold']
            prev = trump_medallions.get('gold_prev')
            change = trump_medallions.get('gold_change', 0)
            pct = (change / prev * 100) if prev and prev > 0 else 0
            arrow = "🔺" if change > 0 else "🔻" if change < 0 else "➡️"
            premium_vs_gold = curr - gold_spot if gold_spot else None
            
            msg += f"• Gold (1oz PF70): **${curr:.2f}**"
            if prev:
                msg += f" (Prev: ${prev:.2f}) {arrow}${abs(change):.2f} ({pct:+.2f}%)"
            if premium_vs_gold:
                msg += f" (Premium: ${premium_vs_gold:+.2f})"
            msg += "\n"

    # Add 3-day delivery data
    if "delivery_3days" in locals():
        delivery_data = delivery_3days
        msg += f"\n**📦 COMEX Silver Deliveries (Last 3 Days)** `[Daily{'*' if not force else ' ✓'}]`\n"

        if delivery_data.get("error"):
            msg += f"• Error: {delivery_data['error']}\n"
        elif not delivery_data.get("found"):
            msg += "• No delivery data available\n"
        elif not delivery_data.get("data") or len(delivery_data["data"]) == 0:
            note = delivery_data.get("note", "No delivery data available")
            msg += f"• {note}\n"
        else:
            for day in delivery_data["data"]:
                msg += f"• {day['intent_date']}: **{day['daily_total']:,}** daily, **{day['total_cumulative']:,}** cumulative\n"

    # Metrics
    if comex and comex_inv and comex_inv.get("registered"):
        oi = comex.get("oi", 0)
        if oi:
            paper_oz = oi * 5000
            ratio = round(paper_oz / comex_inv["registered"], 2)
            msg += "\n**📈 Key Metrics**\n"
            msg += f"• Paper/Physical: **{ratio}x**\n"
            if xagusd and comex:
                basis = round(comex["price"] - xagusd, 3)
                msg += f"• Futures Basis: **${basis:+.3f}**\n"

    msg += "\n─────────────────────────────\n"
    msg += "`*` cached (24h) │ `Paper/Physical` = (OI×5000oz) / Registered │ `Basis` = Futures - Spot"

    return msg, etf_updated


def main(force=False):
    if "--force" in sys.argv:
        force = True

    if force:
        print("Force refresh enabled")

    msg, etf_updated = get_market_update_message(force)
    if etf_updated:
        print("📊 ETF data was updated in the database")
    send_discord(msg)


if __name__ == "__main__":
    main()
