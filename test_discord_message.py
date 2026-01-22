#!/usr/bin/env python3
"""
Local test script for Discord Bot message.
Forces fresh data fetch from all sources and prints the message that would be sent to Discord.

Usage: python test_discord_message.py
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
import re


def get_est_time():
    return datetime.now(pytz.timezone("America/New_York"))


# ============ FORCE FETCH ALL DATA ============


def fetch_xagusd():
    """XAG/USD spot price"""
    try:
        t = yf.Ticker("SI=F")
        return t.info.get("regularMarketPrice")
    except Exception as e:
        print(f"⚠ XAG/USD failed: {e}")
        return None


def fetch_shanghai_td():
    """Shanghai Ag T+D from barchart"""
    try:
        url = "https://www.barchart.com/futures/quotes/XOH26/overview"
        headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
        resp = requests.get(url, headers=headers, timeout=15)

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
    """COMEX silver futures"""
    try:
        si = yf.Ticker("SI=F")
        info = si.info
        return {
            "price": info.get("regularMarketPrice"),
            "volume": info.get("volume", 0),
            "oi": info.get("openInterest", 0),
            "prev_close": info.get("previousClose"),
        }
    except Exception as e:
        print(f"⚠ COMEX failed: {e}")
        return None


def fetch_slv_price():
    """SLV ETF price"""
    try:
        slv = yf.Ticker("SLV")
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
    except Exception as e:
        print(f"⚠ SLV failed: {e}")
        return None


def fetch_gld_price():
    """GLD ETF price"""
    try:
        gld = yf.Ticker("GLD")
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
    except Exception as e:
        print(f"⚠ GLD failed: {e}")
        return None


def fetch_gold_spot():
    """Gold spot price"""
    try:
        gc = yf.Ticker("GC=F")
        hist = gc.history(period="1d")
        if not hist.empty:
            return round(hist["Close"].iloc[-1], 2)
    except Exception as e:
        print(f"⚠ Gold spot failed: {e}")
    return None


def fetch_usdcny():
    """USD/CNY rate - FORCE FRESH"""
    try:
        rate = yf.Ticker("CNY=X").history(period="1d")["Close"].iloc[-1]
        return {"rate": round(rate, 4), "ts": datetime.now().isoformat()}
    except Exception as e:
        print(f"⚠ USD/CNY failed: {e}")
        return None


def fetch_slv_holdings(db):
    """SLV ETF holdings - FORCE FRESH"""
    try:
        url = "https://www.ishares.com/us/products/239855/ishares-silver-trust-fund"
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)

        match = re.search(r"(\d{3},\d{3},\d{3}\.\d+)", resp.text)
        if match:
            holdings = float(match.group(1).replace(",", ""))
            prev_holdings = db.get_last_different_value("SLV_HOLDINGS", holdings)
            if not prev_holdings:
                prev_holdings = db.get_last_different_value("SLV", holdings)

            change = int(holdings - prev_holdings) if prev_holdings else 0
            return {
                "holdings_oz": holdings,
                "change": change,
                "ts": datetime.now().isoformat(),
            }
    except Exception as e:
        print(f"⚠ SLV holdings failed: {e}")
    return None


def fetch_gld_holdings(db):
    """GLD ETF holdings - FORCE FRESH"""
    try:
        url = "https://www.spdrgoldshares.com/assets/dynamic/GLD/GLD_US_archive_EN.csv"
        resp = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        df = pd.read_csv(pd.io.common.StringIO(resp.text))

        last = df.iloc[-1]
        tonnes = float(
            last[" Total Net Asset Value Tonnes in the Trust as at 4.15 p.m. NYT"]
        )
        ounces = float(
            last[" Total Net Asset Value Ounces in the Trust as at 4.15 p.m. NYT"]
        )

        prev_tonnes = db.get_last_different_value(
            "GLD_HOLDINGS", tonnes, key="holdings_tonnes"
        )
        change_tonnes = tonnes - prev_tonnes if prev_tonnes else 0

        return {
            "holdings_tonnes": tonnes,
            "holdings_oz": ounces,
            "change_tonnes": change_tonnes,
            "ts": datetime.now().isoformat(),
        }
    except Exception as e:
        print(f"⚠ GLD holdings failed: {e}")
    return None


def fetch_comex_inventory():
    """COMEX physical inventory - FORCE FRESH"""
    try:
        url = "https://www.cmegroup.com/delivery_reports/Silver_stocks.xls"
        resp = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        df = pd.read_excel(BytesIO(resp.content), engine="xlrd")

        registered = eligible = None
        delta_reg = delta_elig = None

        for _, row in df.iterrows():
            label = str(row.iloc[0]).strip()
            if label == "TOTAL REGISTERED":
                prev_total = float(row.iloc[2])
                registered = float(row.iloc[7])
                delta_reg = int(registered - prev_total)
            elif label == "TOTAL ELIGIBLE":
                prev_total = float(row.iloc[2])
                eligible = float(row.iloc[7])
                delta_elig = int(eligible - prev_total)

        if registered and eligible:
            return {
                "registered": registered,
                "eligible": eligible,
                "total": registered + eligible,
                "reg_ratio": round(registered / (registered + eligible) * 100, 2),
                "delta_registered": delta_reg if delta_reg is not None else 0,
                "delta_eligible": delta_elig if delta_elig is not None else 0,
                "ts": datetime.now().isoformat(),
            }
    except Exception as e:
        print(f"⚠ COMEX inventory failed: {e}")
    return None


def build_discord_message(
    xagusd,
    gold_spot,
    comex,
    shfe,
    slv,
    gld,
    usdcny,
    slv_hold,
    gld_hold,
    comex_inv,
    delivery_3days,
):
    """Build the Discord message without sending it"""
    est = get_est_time()
    ts = est.strftime("%Y-%m-%d %I:%M %p EST")

    msg = f"**📊 Silver Market Update** - {ts}\n\n"

    # Spot & Futures
    msg += "**💹 Real-time Prices** `[30min]`\n"
    if xagusd:
        msg += f"• XAG/USD Spot: **${xagusd:.2f}**/oz\n"
    if gold_spot:
        msg += f"• XAU/USD Spot: **${gold_spot:.2f}**/oz\n"
    if comex:
        msg += f"• COMEX Futures: **${comex['price']:.2f}**/oz"
        if comex.get("oi"):
            msg += f" (OI: {comex['oi']:,}"
            if comex.get("delta_oi") is not None:
                msg += f" {comex['delta_oi']:+,}"
            msg += ")"
        msg += "\n"
    if shfe:
        msg += f"• SHFE Ag: **${shfe.get('price_usd_oz')}**/oz (¥{shfe.get('price_cny_kg', 0):,.0f}/kg)"
        if shfe.get("change_pct") is not None:
            msg += f" {shfe['change_pct']:+.2f}%"
        msg += "\n"
        if shfe.get("volume") and shfe.get("oi"):
            msg += f"  └ Vol: {shfe['volume']:,} | OI: {shfe['oi']:,}"
            if shfe.get("delta_oi") is not None:
                msg += f" ({shfe['delta_oi']:+,})"
            msg += "\n"
        if comex and shfe.get("price_usd_oz"):
            premium = shfe["price_usd_oz"] - comex["price"]
            msg += f"  └ Shanghai Premium: **${premium:+.2f}**\n"
    if slv:
        arrow = "🔺" if slv["change_pct"] > 0 else "🔻"
        msg += f"• SLV ETF: **${slv['price']:.2f}** {arrow}{slv['change_pct']:+.2f}%\n"
    if gld:
        arrow = "🔺" if gld["change_pct"] > 0 else "🔻"
        msg += f"• GLD ETF: **${gld['price']:.2f}** {arrow}{gld['change_pct']:+.2f}%\n"

    # Daily data
    msg += "\n**📦 Physical Holdings** `[Daily ✓]`\n"
    if comex_inv:
        oz_to_tonnes = 0.0000311035
        msg += f"• COMEX Registered: **{comex_inv['registered']:,.0f}** oz"
        if comex_inv.get("delta_registered") is not None:
            delta_oz = comex_inv["delta_registered"]
            delta_t = delta_oz * oz_to_tonnes
            msg += f" ({delta_oz:+,} oz / {delta_t:+.2f}t)"
        msg += "\n"

        msg += f"• COMEX Eligible: **{comex_inv['eligible']:,.0f}** oz"
        if comex_inv.get("delta_eligible") is not None:
            delta_oz = comex_inv["delta_eligible"]
            delta_t = delta_oz * oz_to_tonnes
            msg += f" ({delta_oz:+,} oz / {delta_t:+.2f}t)"
        msg += "\n"
        msg += f"  └ Reg/Total: {comex_inv['reg_ratio']}%\n"
    if slv_hold:
        oz_to_tonnes = 0.0000311035
        msg += f"• SLV Trust: **{slv_hold['holdings_oz']:,.0f}** oz"
        if slv_hold.get("change") is not None:
            delta_oz = slv_hold["change"]
            delta_t = delta_oz * oz_to_tonnes
            msg += f" ({delta_oz:+,} oz / {delta_t:+.2f}t)"
        msg += "\n"
    if gld_hold:
        msg += f"• GLD Trust: **{gld_hold['holdings_tonnes']:,.2f}** tonnes (**{gld_hold['holdings_oz']:,.0f}** oz)"
        if gld_hold.get("change_tonnes") is not None:
            msg += f" ({gld_hold['change_tonnes']:+,.2f}t)"
        msg += "\n"

    msg += "\n**💱 FX Rate** `[Daily ✓]`\n"
    if usdcny:
        msg += f"• USD/CNY: **{usdcny['rate']}**\n"

    # Delivery data
    if delivery_3days:
        msg += "\n**📦 COMEX Silver Deliveries (Last 3 Days)** `[Daily ✓]`\n"
        if delivery_3days.get("error"):
            msg += f"• Error: {delivery_3days['error']}\n"
        elif not delivery_3days.get("found"):
            msg += "• No delivery data available\n"
        elif not delivery_3days.get("data") or len(delivery_3days["data"]) == 0:
            note = delivery_3days.get("note", "No delivery data available")
            msg += f"• {note}\n"
        else:
            for day in delivery_3days["data"]:
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

    return msg


def main():
    print("=" * 60)
    print("LOCAL TEST - Discord Message Preview")
    print("Force fetching ALL data from sources...")
    print("=" * 60)

    db = DBManager()

    # === HOURLY DATA (30min) ===
    print("\n=== Fetching 30min Data ===")
    xagusd = fetch_xagusd()
    print(f"✓ XAG/USD: ${xagusd}" if xagusd else "✗ XAG/USD failed")

    shfe = fetch_shanghai_td()
    print(f"✓ SHFE: ${shfe.get('price_usd_oz')}/oz" if shfe else "✗ SHFE failed")

    comex = fetch_comex_futures()
    print(f"✓ COMEX: ${comex['price']}" if comex else "✗ COMEX failed")

    slv = fetch_slv_price()
    print(f"✓ SLV: ${slv['price']}" if slv else "✗ SLV failed")

    gld = fetch_gld_price()
    print(f"✓ GLD: ${gld['price']}" if gld else "✗ GLD failed")

    gold_spot = fetch_gold_spot()
    print(f"✓ Gold Spot: ${gold_spot}" if gold_spot else "✗ Gold Spot failed")

    # Get OI deltas from fetcher
    try:
        fetcher = SilverDataFetcher(db_manager=db)

        futures_data = fetcher.get_futures_data()
        if futures_data and not futures_data.get("error") and comex:
            comex["delta_oi"] = futures_data.get("delta_oi")
            print(f"✓ COMEX OI Delta: {comex.get('delta_oi')}")

        shfe_data = fetcher.get_shfe_data()
        if shfe_data and shfe_data.get("status") == "Success" and shfe:
            shfe["delta_oi"] = shfe_data.get("delta_oi")
            print(f"✓ SHFE OI Delta: {shfe.get('delta_oi')}")

        delivery_3days = fetcher.pdf_parser.parse_last_3_days_silver()
        print(f"✓ 3-day delivery: {delivery_3days.get('found', False)}")
    except Exception as e:
        print(f"⚠ Additional fetcher error: {e}")
        delivery_3days = {"error": str(e)}

    # === DAILY DATA (Force Fresh) ===
    print("\n=== Fetching Daily Data (Force Fresh) ===")
    usdcny = fetch_usdcny()
    print(f"✓ USD/CNY: {usdcny['rate']}" if usdcny else "✗ USD/CNY failed")

    slv_hold = fetch_slv_holdings(db)
    print(
        f"✓ SLV Holdings: {slv_hold['holdings_oz']:,.0f} oz"
        if slv_hold
        else "✗ SLV Holdings failed"
    )

    gld_hold = fetch_gld_holdings(db)
    print(
        f"✓ GLD Holdings: {gld_hold['holdings_tonnes']:,.2f} tonnes"
        if gld_hold
        else "✗ GLD Holdings failed"
    )

    comex_inv = fetch_comex_inventory()
    print(
        f"✓ COMEX Inventory: {comex_inv['registered']:,.0f} oz"
        if comex_inv
        else "✗ COMEX Inventory failed"
    )

    # === BUILD MESSAGE ===
    print("\n" + "=" * 60)
    print("DISCORD MESSAGE PREVIEW:")
    print("=" * 60 + "\n")

    msg = build_discord_message(
        xagusd,
        gold_spot,
        comex,
        shfe,
        slv,
        gld,
        usdcny,
        slv_hold,
        gld_hold,
        comex_inv,
        delivery_3days,
    )

    print(msg)

    print("\n" + "=" * 60)
    print(f"Message length: {len(msg)} characters")
    print("=" * 60)


if __name__ == "__main__":
    main()
