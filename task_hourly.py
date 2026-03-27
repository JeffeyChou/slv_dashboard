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
from io import BytesIO
import pytz
import sys

# Support comma-separated list: DISCORD_WEBHOOK_URLS=url1,url2,...
# Falls back to legacy DISCORD_WEBHOOK_URL if DISCORD_WEBHOOK_URLS is not set
_raw_webhooks = os.getenv("DISCORD_WEBHOOK_URLS") or os.getenv("DISCORD_WEBHOOK_URL") or ""
WEBHOOK_URLS = [u.strip() for u in _raw_webhooks.split(",") if u.strip()]
CACHE_DIR = "cache"
MSG_ID_FILE = os.path.join(CACHE_DIR, "discord_msg_id.txt")


def get_est_time():
    return datetime.now(pytz.timezone("America/New_York"))


def get_fetch_stamp():
    return get_est_time().strftime("%m-%d-%H:%M")


def append_fetch_stamp_to_message(msg, stamp):
    stamped_lines = []
    for line in msg.splitlines():
        stripped = line.strip()
        if not stripped:
            stamped_lines.append(line)
            continue
        if stripped.startswith("────────────────") or stripped.startswith("`*"):
            stamped_lines.append(line)
            continue
        stamped_lines.append(f"{line} [{stamp}]")
    return "\n".join(stamped_lines)


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


# DISABLED: XOH26 (SHFE) future price & OI tracking removed
# def fetch_shanghai_td(): ...


# DISABLED: SIH26 (COMEX) future price & OI tracking removed
# def fetch_comex_futures(): ...


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
        import re

        url = "https://api.spdrgoldshares.com/api/v1/data"
        params = {"product": "gld", "exchange": "nyse", "lang": "en"}
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64)",
            "Accept": "application/json",
        }
        resp = requests.get(url, params=params, timeout=20, headers=headers)
        resp.raise_for_status()

        data_json = resp.json().get("data", {})

        def parse_number(value):
            if value is None:
                return None
            cleaned = re.sub(r"[^0-9.,-]", "", str(value)).replace(",", "")
            return float(cleaned) if cleaned else None

        tonnes = parse_number(data_json.get("total_tonnes", {}).get("value"))
        ounces = parse_number(data_json.get("total_ounces", {}).get("value"))
        nav_usd = parse_number(data_json.get("total_nav_usd", {}).get("value"))
        as_of_date = (
            data_json.get("total_nav_usd", {}).get("date")
            or data_json.get("total_ounces", {}).get("date")
            or data_json.get("total_tonnes", {}).get("date")
        )

        if tonnes is None or ounces is None:
            raise ValueError("Missing total_tonnes or total_ounces in GLD overview API")

        # Get last different value from database
        prev_tonnes = db.get_last_different_value(
            "GLD_HOLDINGS", tonnes, key="holdings_tonnes"
        )

        change_tonnes = tonnes - prev_tonnes if prev_tonnes else 0
        data = {
            "holdings_tonnes": tonnes,
            "holdings_oz": ounces,
            "change_tonnes": change_tonnes,
            "total_nav_usd": nav_usd,
            "as_of_date": as_of_date,
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
    if not WEBHOOK_URLS:
        print("⚠ No Discord webhook URL(s) configured")
        return

    os.makedirs(CACHE_DIR, exist_ok=True)

    for idx, webhook_url in enumerate(WEBHOOK_URLS):
        # Each webhook gets its own message-ID cache file
        id_file = MSG_ID_FILE if idx == 0 else f"{MSG_ID_FILE}.{idx}"
        label = f"webhook[{idx}]"

        # Try to edit existing message for this webhook
        if os.path.exists(id_file):
            with open(id_file) as f:
                msg_id = f.read().strip()
            if msg_id:
                edit_url = f"{webhook_url}/messages/{msg_id}"
                try:
                    resp = requests.patch(edit_url, json={"content": msg}, timeout=10)
                    if resp.status_code == 200:
                        print(f"✓ Discord {label} updated (ID: {msg_id})")
                        continue
                    else:
                        print(f"⚠ {label}: edit failed ({resp.status_code}), sending new")
                except Exception as e:
                    print(f"⚠ {label}: edit error: {e}, sending new")

        # Send new message and save its ID
        try:
            resp = requests.post(
                f"{webhook_url}?wait=true", json={"content": msg}, timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                msg_id = data.get("id", "")
                if msg_id:
                    with open(id_file, "w") as f:
                        f.write(msg_id)
                    print(f"✓ {label} new message sent (ID: {msg_id})")
                else:
                    print(f"✓ {label} message sent (no ID returned)")
            else:
                print(f"⚠ {label}: send failed (status {resp.status_code})")
        except Exception as e:
            print(f"⚠ {label}: send error: {e}")

def fetch_wti_brent_spread():
    """Fetch WTI (CL=F) and Brent (BZ=F) prices and compute spread.
    Spread narrowing = potential short signal for crude."""
    try:
        wti = yf.Ticker("CL=F")
        brent = yf.Ticker("BZ=F")
        wti_price = wti.history(period="2d")["Close"].iloc[-1]
        brent_price = brent.history(period="2d")["Close"].iloc[-1]
        spread = round(wti_price - brent_price, 2)  # normally negative (Brent > WTI)
        return {
            "wti": round(float(wti_price), 2),
            "brent": round(float(brent_price), 2),
            "spread": spread,  # WTI - Brent
        }
    except Exception as e:
        print(f"⚠ WTI-Brent spread failed: {e}")
        return None


def fetch_fedwatch_probability():
    """Live Fed Funds Futures implied EFFR from ZQ=F (front-month).
    ZQ price = 100 - avg(EFFR for current month).
    Used as a directional indicator for rate expectations.
    Note: CME FedWatch exact cut/hold/hike % requires paid API.
    """
    try:
        zq = yf.Ticker("ZQ=F")
        hist = zq.history(period="5d")
        if not hist.empty:
            price = float(hist["Close"].iloc[-1])
            implied_rate = round(100.0 - price, 4)
            return {
                "probability": None,          # exact cut prob needs CME paid API
                "implied_rate": implied_rate,  # e.g. 3.695%
                "futures_price": round(price, 4),
                "source": "ZQ=F (yfinance)",
            }
    except Exception as e:
        print(f"  ZQ=F fetch failed: {e}")
    return None


FEDWATCH_ALERT_LOW = 35.0
FEDWATCH_ALERT_HIGH = 55.0


def fetch_polymarket_ceasefire():
    """Fetch ceasefire / Hormuz probability from Polymarket API.
    Tracks three time windows:
    - Short-term: ceasefire before end of April
    - Q2: ceasefire before end of June
    - Long-term: general Hormuz reopening / end of conflict
    Returns dict with probabilities (0-100).
    """
    import re

    MARKETS = [
        # Verified live slugs as of 2026-03-26 (browser-confirmed)
        {
            "key": "ceasefire_june",
            "label": "Israel-Hamas Ceasefire Phase II <= Jun 30",
            "slug": "israel-x-hamas-ceasefire-phase-ii-by-june-30",
            "keyword": "ceasefire june",
        },
        {
            "key": "hormuz_normal",
            "label": "Hormuz Traffic Normal by Apr 30",
            "slug": "strait-of-hormuz-traffic-returns-to-normal-by-april-30",
            "keyword": "hormuz normal",
        },
    ]

    results = {}
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        "Accept": "application/json",
    }

    def _extract_prob(market):
        prices_raw = market.get("outcomePrices")
        if not prices_raw:
            return None
        try:
            prices = json.loads(prices_raw) if isinstance(prices_raw, str) else prices_raw
            return round(float(prices[0]) * 100, 1)
        except Exception:
            return None

    def _search_keyword(keyword):
        """Fallback: search Polymarket events by keyword."""
        try:
            from urllib.parse import quote
            url = f"https://gamma-api.polymarket.com/events?title={quote(keyword)}&closed=false&limit=5"
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                events = resp.json()
                if isinstance(events, list):
                    kw_lower = keyword.lower()
                    for ev in events:
                        title = (ev.get("title") or "").lower()
                        if any(w in title for w in kw_lower.split()):
                            mkt_list = ev.get("markets", [])
                            if mkt_list:
                                return mkt_list[0], ev.get("title", keyword)
        except Exception as e:
            print(f"  Polymarket keyword search '{keyword}': {e}")
        return None, None

    for mkt in MARKETS:
        try:
            market_data = None
            question = mkt["label"]

            # 1. Try exact slug
            url = f"https://gamma-api.polymarket.com/markets?slug={mkt['slug']}"
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and data:
                    candidate = data[0]
                    if _extract_prob(candidate) is not None:
                        market_data = candidate
                        question = candidate.get("question", mkt["label"])

            # 2. Fallback: keyword search via events endpoint
            if not market_data:
                market_data, ev_title = _search_keyword(mkt.get("keyword", mkt["key"]))
                if ev_title:
                    question = ev_title

            if market_data:
                yes_prob = _extract_prob(market_data)
                if yes_prob is not None:
                    results[mkt["key"]] = {
                        "label": mkt["label"],
                        "probability": yes_prob,
                        "question": question,
                    }
                    print(f"\u2713 Polymarket {mkt['key']}: {yes_prob}% ({question[:60]})")
                else:
                    print(f"\u26a0 Polymarket {mkt['key']}: no outcomePrices")
            else:
                print(f"\u26a0 Polymarket {mkt['key']}: no data found")
        except Exception as e:
            print(f"\u26a0 Polymarket {mkt['key']} failed: {e}")

    return results if results else None


def get_market_update_message(force=False):
    """Generate the market update message string"""
    db = DBManager()

    # === REAL-TIME DATA ===
    print("\n=== Real-time Data ===")
    xagusd = fetch_xagusd()
    slv = fetch_slv_price()
    gld = fetch_gld_price()
    gold_spot = fetch_gold_spot()
    # SIH26 (COMEX futures) and XOH26 (SHFE futures) disabled
    comex = None
    shfe = None

    # === NEW ALPHA FACTORS ===
    print("\n=== Alpha Factors ===")
    wti_brent = fetch_wti_brent_spread()
    fedwatch = fetch_fedwatch_probability()
    polymarket = fetch_polymarket_ceasefire()
    if wti_brent:
        print(f"✓ WTI: ${wti_brent['wti']} | Brent: ${wti_brent['brent']} | Spread: ${wti_brent['spread']}")
    if fedwatch:
        print(f"✓ FedWatch cut prob: {fedwatch['probability']}% [{fedwatch['source']}]")
    if polymarket:
        for k, v in polymarket.items():
            print(f"✓ Polymarket {k}: {v['probability']}%")

    # === GET ADDITIONAL DATA FROM MAIN FETCHER ===
    print("\n=== Fetching delivery data ===")
    try:
        fetcher = SilverDataFetcher()
        # Get 3-day delivery data (still active)
        delivery_3days = fetcher.pdf_parser.parse_last_3_days_silver()
        print(f"✓ 3-day delivery data: {delivery_3days.get('found', False)}")
    except Exception as e:
        print(f"⚠ Error fetching delivery data: {e}")
        delivery_3days = {"error": str(e)}

    if xagusd:
        db.insert("XAGUSD", price=xagusd)
        print(f"✓ XAG/USD: ${xagusd}")
    if slv:
        db.insert("SLV", price=slv["price"], raw_data=json.dumps(slv))
        print(f"✓ SLV: ${slv['price']}")
    if gld:
        db.insert("GLD", price=gld["price"], raw_data=json.dumps(gld))
        print(f"✓ GLD: ${gld['price']}")
    if gold_spot:
        db.insert("GOLD_SPOT", price=gold_spot)
        print(f"✓ Gold Spot: ${gold_spot}")
    if wti_brent:
        db.insert("WTI_BRENT_SPREAD", price=wti_brent["spread"], raw_data=json.dumps(wti_brent))
        print(f"✓ WTI-Brent spread stored")

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

    # Spot Prices
    msg += "**💹 Real-time Prices**\n"
    if xagusd:
        msg += f"• XAG/USD Spot: **${xagusd:.2f}**/oz\n"
    if gold_spot:
        msg += f"• XAU/USD Spot: **${gold_spot:.2f}**/oz\n"
    if slv:
        arrow = "🔺" if slv["change_pct"] > 0 else "🔻"
        msg += f"• SLV ETF: **${slv['price']:.2f}** {arrow}{slv['change_pct']:+.2f}%\n"
    if gld:
        arrow = "🔺" if gld["change_pct"] > 0 else "🔻"
        msg += f"• GLD ETF: **${gld['price']:.2f}** {arrow}{gld['change_pct']:+.2f}%\n"

    # ── Alpha Factor 2: WTI-Brent Spread ──
    if wti_brent:
        spread = wti_brent["spread"]
        spread_signal = ""
        # Spread narrows (becomes less negative) → potential short signal
        if spread > -2.0:
            spread_signal = " 🚨 *Narrow spread – potential crude short signal*"
        elif spread > -4.0:
            spread_signal = " ⚠️ *Spread tightening*"
        msg += f"\n**🛢️ Crude Oil Spread** (War Inflection Gauge)\n"
        msg += f"• WTI: **${wti_brent['wti']:.2f}** │ Brent: **${wti_brent['brent']:.2f}**\n"
        msg += f"• WTI–Brent Spread: **${spread:+.2f}**{spread_signal}\n"

    # ── Alpha Factor 3: CME FedWatch (ZQ=F indicator) ──
    if fedwatch:
        implied = fedwatch.get("implied_rate")
        price = fedwatch.get("futures_price")
        if implied is not None:
            msg += f"\n**\U0001f3e6 Fed Funds Futures** `ZQ=F` — implied EFFR: **{implied:.3f}%** (futures: {price:.4f})\n"
            msg += f"\u2022 *Directional indicator only — exact cut/hold/hike % from [CME FedWatch](https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html)*\n"

    # ── Alpha Factor 1: Geopolitical Risk (Ceasefire / Hormuz) ──
    if polymarket:
        msg += f"\n**\U0001f54a\ufe0f Geopolitical Risk** (Polymarket Probabilities)\n"
        june = polymarket.get("ceasefire_june")
        hormuz = polymarket.get("hormuz_normal")
        if june:
            msg += f"\u2022 Israel-Hamas Phase II Ceasefire \u2264 Jun 30: **{june['probability']:.1f}%**\n"
        if hormuz:
            msg += f"\u2022 Hormuz Traffic Normal by Apr 30: **{hormuz['probability']:.1f}%** (blockade risk: {round(100-hormuz['probability'],1):.1f}%)\n"

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

    msg += "\n─────────────────────────────\n"
    msg += "`*` cached (24h) │ `WTI–Brent` narrowing = potential crude short │ `FedWatch` alert: 35–55%"

    fetch_stamp = get_fetch_stamp()
    msg = append_fetch_stamp_to_message(msg, fetch_stamp)

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
