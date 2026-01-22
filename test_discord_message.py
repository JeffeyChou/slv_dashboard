#!/usr/bin/env python3
"""
Local test script for Discord Bot message.
Forces fresh data fetch from all sources and prints the message without sending.

Usage: python test_discord_message.py

Data Sources:
- XAG/USD Spot: https://www.barchart.com/forex/quotes/%5EXAGUSD/overview
- COMEX Futures (SIH26): https://www.barchart.com/futures/quotes/SIH26/overview
- SHFE Ag (XOH26): https://www.barchart.com/futures/quotes/XOH26/overview
"""

import os
import json
import requests
from datetime import datetime
from db_manager import DBManager
from data_fetcher import SilverDataFetcher
import pandas as pd
from io import BytesIO
import pytz
import re


def get_est_time():
    return datetime.now(pytz.timezone("America/New_York"))


# ============ ETF DATA (from yfinance) ============


def fetch_slv_price():
    """SLV ETF price"""
    try:
        import yfinance as yf

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
        import yfinance as yf

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
    """Gold spot price from Barchart"""
    try:
        url = "https://www.barchart.com/forex/quotes/%5EXAUUSD/overview"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=15)

        price_match = re.search(r'"lastPrice":"?([0-9,\.]+)"?', resp.text)
        if price_match:
            return float(price_match.group(1).replace(",", ""))
    except Exception as e:
        print(f"⚠ Gold spot failed: {e}")
    return None


# ============ DAILY DATA (FORCE FRESH) ============


def fetch_usdcny():
    """USD/CNY rate - FORCE FRESH"""
    try:
        import yfinance as yf

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
    spot,
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

    # XAG/USD Spot
    if spot and spot.get("price"):
        msg += f"• XAG/USD Spot: **${spot['price']:.2f}**/oz\n"

    # Gold Spot
    if gold_spot:
        msg += f"• XAU/USD Spot: **${gold_spot:.2f}**/oz\n"

    # COMEX Futures
    if comex and comex.get("price"):
        msg += f"• COMEX Futures (SIH26): **${comex['price']:.2f}**/oz"
        if comex.get("open_interest"):
            msg += f" (OI: {comex['open_interest']:,}"
            if comex.get("delta_oi") is not None:
                msg += f" {comex['delta_oi']:+,.0f}"
            msg += ")"
        msg += "\n"

    # SHFE Ag
    if shfe and shfe.get("status") == "Success":
        msg += f"• SHFE Ag (XOH26): **${shfe.get('price_usd_oz')}**/oz (¥{shfe.get('price', 0):,.0f}/kg)"
        if shfe.get("change_pct") is not None:
            msg += f" {shfe['change_pct']:+.2f}%"
        msg += "\n"
        if shfe.get("oi"):
            msg += f"  └ OI: {shfe['oi']:,}"
            if shfe.get("delta_oi") is not None:
                msg += f" ({shfe['delta_oi']:+,.0f})"
            msg += "\n"
        # Shanghai Premium
        if spot and spot.get("price") and shfe.get("price_usd_oz"):
            premium = shfe["price_usd_oz"] - spot["price"]
            msg += f"  └ Shanghai Premium: **${premium:+.2f}**\n"

    # ETFs
    if slv:
        arrow = "🔺" if slv["change_pct"] > 0 else "🔻"
        msg += f"• SLV ETF: **${slv['price']:.2f}** {arrow}{slv['change_pct']:+.2f}%\n"
    if gld:
        arrow = "🔺" if gld["change_pct"] > 0 else "🔻"
        msg += f"• GLD ETF: **${gld['price']:.2f}** {arrow}{gld['change_pct']:+.2f}%\n"

    # Daily data - Physical Holdings (format: tonnes first, then oz)
    msg += "\n**📦 Physical Holdings** `[Daily ✓]`\n"

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

        msg += f"• COMEX Eligible: **{elig_tonnes:,.2f}** tonnes (**{comex_inv['eligible']:,.0f}** oz)"
        if comex_inv.get("delta_eligible") is not None:
            delta_oz = comex_inv["delta_eligible"]
            delta_t = delta_oz * oz_to_tonnes
            msg += f" ({delta_t:+.2f}t / {delta_oz:+,} oz)"
        msg += "\n"
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
    if (
        comex
        and comex.get("open_interest")
        and comex_inv
        and comex_inv.get("registered")
    ):
        oi = comex.get("open_interest", 0)
        if oi:
            paper_oz = oi * 5000
            ratio = round(paper_oz / comex_inv["registered"], 2)
            msg += "\n**📈 Key Metrics**\n"
            msg += f"• Paper/Physical: **{ratio}x**\n"
            if spot and spot.get("price") and comex.get("price"):
                basis = round(comex["price"] - spot["price"], 3)
                msg += f"• Futures Basis: **${basis:+.3f}**\n"

    msg += "\n─────────────────────────────\n"
    msg += "`Paper/Physical` = (OI×5000oz) / Registered │ `Basis` = Futures - Spot"

    return msg


def main():
    print("=" * 60)
    print("LOCAL TEST - Discord Message Preview")
    print("Force fetching ALL data from Barchart...")
    print("=" * 60)

    db = DBManager()
    fetcher = SilverDataFetcher(db_manager=db)

    # === BARCHART DATA (30min) ===
    print("\n=== Fetching 30min Data from Barchart ===")

    # XAG/USD Spot
    spot = fetcher.get_spot_xagusd()
    if spot and not spot.get("error"):
        print(f"✓ XAG/USD Spot: ${spot['price']:.2f}")
    else:
        print(f"✗ XAG/USD Spot failed: {spot.get('error') if spot else 'No data'}")

    # COMEX Futures (SIH26)
    comex = fetcher.get_futures_data()
    if comex and not comex.get("error"):
        print(
            f"✓ COMEX SIH26: ${comex['price']:.2f} (OI: {comex.get('open_interest', 'N/A'):,}, ΔOI: {comex.get('delta_oi')})"
        )
    else:
        print(f"✗ COMEX SIH26 failed: {comex.get('error') if comex else 'No data'}")

    # SHFE Ag (XOH26)
    shfe = fetcher.get_shfe_data()
    if shfe and shfe.get("status") == "Success":
        print(
            f"✓ SHFE XOH26: ${shfe['price_usd_oz']}/oz (OI: {shfe.get('oi', 'N/A'):,}, ΔOI: {shfe.get('delta_oi')})"
        )
    else:
        print(f"✗ SHFE XOH26 failed: {shfe.get('note') if shfe else 'No data'}")

    # Gold Spot
    gold_spot = fetch_gold_spot()
    print(f"✓ XAU/USD Spot: ${gold_spot:.2f}" if gold_spot else "✗ XAU/USD Spot failed")

    # ETFs
    slv = fetch_slv_price()
    print(f"✓ SLV: ${slv['price']:.2f}" if slv and slv.get("price") else "✗ SLV failed")

    gld = fetch_gld_price()
    print(f"✓ GLD: ${gld['price']:.2f}" if gld and gld.get("price") else "✗ GLD failed")

    # Delivery data
    try:
        delivery_3days = fetcher.pdf_parser.parse_last_3_days_silver()
        print(f"✓ 3-day delivery: {delivery_3days.get('found', False)}")
    except Exception as e:
        print(f"⚠ Delivery data failed: {e}")
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
        spot,
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
