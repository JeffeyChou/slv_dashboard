#!/usr/bin/env python3
"""
Daily Report Generator for Silver Market
Generates charts similar to Jin10 style:
- Line charts for ETF holdings trends
- Bar charts for daily changes
"""

import os
import json
import requests
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
from db_manager import DBManager
from data_fetcher import SilverDataFetcher
import pandas as pd
import numpy as np

WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# Historical data for GLD daily changes (from user's data)
# Format: (date_str, change_tonnes)
GLD_HISTORICAL_CHANGES = [
    ("2026-01-21", -4.00),
    ("2026-01-20", -4.01),
    ("2026-01-19", 0.00),
    ("2026-01-16", 10.87),
    ("2026-01-15", 0.57),
    ("2026-01-14", 0.00),
    ("2026-01-13", 3.43),
    ("2026-01-12", 6.24),
    ("2026-01-09", -2.57),
    ("2026-01-08", 0.00),
    ("2026-01-07", 0.00),
    ("2026-01-06", 2.00),
    ("2026-01-05", 0.00),
    ("2026-01-02", -5.43),
    ("2026-01-01", 0.00),
    ("2025-12-31", -1.43),
    ("2025-12-30", 0.00),
    ("2025-12-29", 0.86),
    ("2025-12-26", 2.86),
    ("2025-12-25", 0.00),
]

# GLD total holdings - actual data from user (tonnes)
GLD_HISTORICAL_HOLDINGS = [
    ("2026-01-21", 1077.66),
    ("2026-01-20", 1081.66),
    ("2026-01-19", 1085.67),
    ("2026-01-16", 1085.67),
    ("2026-01-15", 1074.80),
    ("2026-01-14", 1074.23),
    ("2026-01-13", 1074.23),
    ("2026-01-12", 1070.80),
    ("2026-01-09", 1064.56),
    ("2026-01-08", 1067.13),
    ("2026-01-07", 1067.13),
    ("2026-01-06", 1067.13),
    ("2026-01-05", 1065.13),
    ("2026-01-02", 1065.13),
    ("2026-01-01", 1070.56),
    ("2025-12-31", 1070.56),
    ("2025-12-30", 1071.99),
    ("2025-12-29", 1071.99),
    ("2025-12-26", 1071.13),
    ("2025-12-25", 1068.27),
]

# SLV daily changes - corrected data from user
SLV_HISTORICAL_CHANGES = [
    ("2026-01-21", -56.38),
    ("2026-01-20", 149.42),
    ("2026-01-16", 11.28),
    ("2026-01-15", -180.44),
    ("2026-01-14", -78.94),
    ("2026-01-13", -26.79),
    ("2026-01-12", 39.47),
    ("2026-01-09", 93.05),
    ("2026-01-08", 115.60),
    ("2026-01-07", -18.33),
    ("2026-01-06", -235.44),
    ("2026-01-05", -90.54),
    ("2025-12-31", -11.28),
    ("2025-12-30", 149.46),
    ("2025-12-29", -84.60),
]

# SLV total holdings - actual data from user (tonnes)
SLV_HISTORICAL_HOLDINGS = [
    ("2026-01-21", 16166.10),
    ("2026-01-20", 16222.48),
    ("2026-01-16", 16073.06),
    ("2026-01-15", 16061.78),
    ("2026-01-14", 16242.22),
    ("2026-01-13", 16321.16),
    ("2026-01-12", 16347.95),
    ("2026-01-09", 16308.48),
    ("2026-01-08", 16215.43),
    ("2026-01-07", 16099.83),
    ("2026-01-06", 16118.16),
    ("2026-01-05", 16353.60),
    ("2025-12-31", 16444.14),
    ("2025-12-30", 16455.42),
    ("2025-12-29", 16305.96),
]

# Current holdings values
GLD_CURRENT_TONNES = 1077.66
SLV_CURRENT_TONNES = 16166.10


def seed_historical_data():
    """Seed database with historical ETF holdings data from the image"""
    db = DBManager()

    # Calculate GLD historical holdings (working backwards from current)
    gld_holdings = GLD_CURRENT_TONNES
    gld_history = []
    for date_str, change in GLD_HISTORICAL_CHANGES:
        gld_history.append((date_str, gld_holdings))
        gld_holdings -= change  # Go backwards

    # Calculate SLV historical holdings (working backwards from current)
    slv_holdings = SLV_CURRENT_TONNES
    slv_history = []
    for date_str, change in SLV_HISTORICAL_CHANGES:
        slv_history.append((date_str, slv_holdings))
        slv_holdings -= change  # Go backwards

    # Store in metrics table
    for date_str, tonnes in gld_history:
        db.append_metrics(
            {
                "GLD_Holdings_Tonnes": tonnes,
                "GLD_Daily_Change_Tonnes": next(
                    (c for d, c in GLD_HISTORICAL_CHANGES if d == date_str), 0
                ),
            }
        )

    for date_str, tonnes in slv_history:
        db.append_metrics(
            {
                "SLV_Holdings_Tonnes": tonnes,
                "SLV_Daily_Change_Tonnes": next(
                    (c for d, c in SLV_HISTORICAL_CHANGES if d == date_str), 0
                ),
            }
        )

    print("✓ Historical data seeded")


def get_daily_data(days=30):
    """Get daily aggregated data from database"""
    db = DBManager()
    data = db.get_recent(days=days)

    # Group by date and get latest values per day
    daily_data = {}

    for record in data:
        date = datetime.fromisoformat(record["timestamp"]).date()
        if date not in daily_data:
            daily_data[date] = {}

        # Parse raw_data if available
        if record["raw_data"]:
            try:
                raw = json.loads(record["raw_data"])
                daily_data[date][record["source"]] = {
                    "price": record["price"],
                    "raw": raw,
                    "timestamp": record["timestamp"],
                }
            except Exception:
                pass

    return daily_data


def get_etf_changes_data():
    """Get ETF daily changes data - uses historical constants only (verified data)"""
    # Use only verified historical data from constants
    gld_changes = {
        datetime.strptime(d, "%Y-%m-%d").date(): c for d, c in GLD_HISTORICAL_CHANGES
    }
    slv_changes = {
        datetime.strptime(d, "%Y-%m-%d").date(): c for d, c in SLV_HISTORICAL_CHANGES
    }

    return gld_changes, slv_changes


def get_etf_holdings_data():
    """Get ETF holdings time series - uses actual data for both GLD and SLV"""
    # Use actual GLD holdings data from user
    gld_dates = []
    gld_holdings = []

    for date_str, holdings in GLD_HISTORICAL_HOLDINGS:
        date = datetime.strptime(date_str, "%Y-%m-%d").date()
        gld_dates.append(date)
        gld_holdings.append(holdings)

    # Use actual SLV holdings data from user
    slv_dates = []
    slv_holdings = []

    for date_str, holdings in SLV_HISTORICAL_HOLDINGS:
        date = datetime.strptime(date_str, "%Y-%m-%d").date()
        slv_dates.append(date)
        slv_holdings.append(holdings)

    return (gld_dates, gld_holdings), (slv_dates, slv_holdings)


def generate_etf_holdings_charts():
    """Generate ETF holdings charts like the Jin10 style image"""
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle("ETF Holdings Report", fontsize=18, fontweight="bold", y=0.98)

    gld_data, slv_data = get_etf_holdings_data()
    gld_changes, slv_changes = get_etf_changes_data()

    # ===== TOP LEFT: GLD Holdings Line Chart =====
    ax1 = axes[0, 0]
    gld_dates, gld_holdings = gld_data

    # Sort by date
    sorted_gld = sorted(zip(gld_dates, gld_holdings))
    gld_dates_sorted = [d for d, h in sorted_gld]
    gld_holdings_sorted = [h for d, h in sorted_gld]

    ax1.plot(
        gld_dates_sorted,
        gld_holdings_sorted,
        "o-",
        color="#FF6B35",
        linewidth=2,
        markersize=4,
    )
    ax1.fill_between(gld_dates_sorted, gld_holdings_sorted, alpha=0.1, color="#FF6B35")
    ax1.set_title(
        f"GLD Holdings: {GLD_CURRENT_TONNES:,.2f} tonnes",
        fontsize=14,
        fontweight="bold",
    )
    ax1.set_ylabel("Tonnes", fontsize=12)
    ax1.grid(True, alpha=0.3)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    # Set Y-axis to show actual data range with padding
    if gld_holdings_sorted:
        y_min = min(gld_holdings_sorted) * 0.995
        y_max = max(gld_holdings_sorted) * 1.005
        ax1.set_ylim(y_min, y_max)

    # ===== TOP RIGHT: SLV Holdings Line Chart =====
    ax2 = axes[0, 1]
    slv_dates, slv_holdings = slv_data

    # Sort by date
    sorted_slv = sorted(zip(slv_dates, slv_holdings))
    slv_dates_sorted = [d for d, h in sorted_slv]
    slv_holdings_sorted = [h for d, h in sorted_slv]

    ax2.plot(
        slv_dates_sorted,
        slv_holdings_sorted,
        "o-",
        color="#4A90D9",
        linewidth=2,
        markersize=4,
    )
    ax2.fill_between(slv_dates_sorted, slv_holdings_sorted, alpha=0.1, color="#4A90D9")
    ax2.set_title(
        f"SLV Holdings: {SLV_CURRENT_TONNES:,.2f} tonnes",
        fontsize=14,
        fontweight="bold",
    )
    ax2.set_ylabel("Tonnes", fontsize=12)
    ax2.grid(True, alpha=0.3)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    # Set Y-axis to show actual data range with padding (NOT starting from 0)
    if slv_holdings_sorted:
        y_min = min(slv_holdings_sorted) * 0.99
        y_max = max(slv_holdings_sorted) * 1.01
        ax2.set_ylim(y_min, y_max)

    # ===== BOTTOM LEFT: GLD Daily Changes Bar Chart =====
    ax3 = axes[1, 0]

    # Sort GLD changes by date (descending for display) - show all available data
    gld_change_dates = sorted(gld_changes.keys(), reverse=True)[:12]
    gld_change_values = [gld_changes[d] for d in gld_change_dates]
    gld_change_labels = [d.strftime("%m-%d") for d in gld_change_dates]

    colors_gld = ["#4CAF50" if v >= 0 else "#F44336" for v in gld_change_values]
    bars_gld = ax3.barh(
        gld_change_labels, gld_change_values, color=colors_gld, height=0.6
    )

    # Add value labels
    for bar, val in zip(bars_gld, gld_change_values):
        width = bar.get_width()
        label_x = width + 0.5 if width >= 0 else width - 0.5
        ha = "left" if width >= 0 else "right"
        ax3.text(
            label_x,
            bar.get_y() + bar.get_height() / 2,
            f"{val:+.2f}t",
            va="center",
            ha=ha,
            fontsize=9,
        )

    ax3.axvline(x=0, color="black", linewidth=0.5)
    ax3.set_title("GLD Daily Changes (tonnes)", fontsize=14, fontweight="bold")
    ax3.set_xlabel("Change (tonnes)", fontsize=12)
    ax3.invert_yaxis()  # Most recent at top

    # ===== BOTTOM RIGHT: SLV Daily Changes Bar Chart =====
    ax4 = axes[1, 1]

    # Sort SLV changes by date (descending for display) - show all available data
    slv_change_dates = sorted(slv_changes.keys(), reverse=True)[:12]
    slv_change_values = [slv_changes[d] for d in slv_change_dates]
    slv_change_labels = [d.strftime("%m-%d") for d in slv_change_dates]

    colors_slv = ["#4CAF50" if v >= 0 else "#F44336" for v in slv_change_values]
    bars_slv = ax4.barh(
        slv_change_labels, slv_change_values, color=colors_slv, height=0.6
    )

    # Add value labels
    for bar, val in zip(bars_slv, slv_change_values):
        width = bar.get_width()
        label_x = width + 5 if width >= 0 else width - 5
        ha = "left" if width >= 0 else "right"
        ax4.text(
            label_x,
            bar.get_y() + bar.get_height() / 2,
            f"{val:+.2f}t",
            va="center",
            ha=ha,
            fontsize=9,
        )

    ax4.axvline(x=0, color="black", linewidth=0.5)
    ax4.set_title("SLV Daily Changes (tonnes)", fontsize=14, fontweight="bold")
    ax4.set_xlabel("Change (tonnes)", fontsize=12)
    ax4.invert_yaxis()  # Most recent at top

    plt.tight_layout()
    chart_path = "./etf_holdings_report.png"
    plt.savefig(chart_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()

    return chart_path


def generate_price_chart(daily_data):
    """Generate price trends chart with subplots"""
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    fig.suptitle("Silver Market - Price Trends", fontsize=16, fontweight="bold")

    dates = sorted(daily_data.keys())

    # XAG/USD (Silver Spot)
    silver_prices = []
    for date in dates:
        if "XAGUSD_SPOT" in daily_data[date]:
            silver_prices.append(daily_data[date]["XAGUSD_SPOT"]["price"])
        elif "COMEX_FUTURES" in daily_data[date]:
            silver_prices.append(daily_data[date]["COMEX_FUTURES"]["price"])
        else:
            silver_prices.append(None)

    axes[0, 0].plot(
        dates, silver_prices, "o-", color="silver", linewidth=2, markersize=4
    )
    axes[0, 0].set_title("XAG/USD Silver Spot")
    axes[0, 0].set_ylabel("Price (USD/oz)")
    axes[0, 0].grid(True, alpha=0.3)

    # COMEX Futures
    comex_prices = []
    for date in dates:
        if "COMEX_FUTURES" in daily_data[date]:
            comex_prices.append(daily_data[date]["COMEX_FUTURES"]["price"])
        elif "COMEX" in daily_data[date]:
            comex_prices.append(daily_data[date]["COMEX"]["price"])
        else:
            comex_prices.append(None)

    axes[0, 1].plot(dates, comex_prices, "o-", color="blue", linewidth=2, markersize=4)
    axes[0, 1].set_title("COMEX Silver Futures (SIH26)")
    axes[0, 1].set_ylabel("Price (USD/oz)")
    axes[0, 1].grid(True, alpha=0.3)

    # SHFE Ag Price
    shfe_prices = []
    for date in dates:
        if "SHFE" in daily_data[date]:
            raw = daily_data[date]["SHFE"]["raw"]
            if raw and "price_usd_oz" in raw:
                shfe_prices.append(raw["price_usd_oz"])
            else:
                shfe_prices.append(None)
        else:
            shfe_prices.append(None)

    axes[1, 0].plot(dates, shfe_prices, "o-", color="red", linewidth=2, markersize=4)
    axes[1, 0].set_title("SHFE Ag Price (XOH26) - USD/oz")
    axes[1, 0].set_ylabel("Price (USD/oz)")
    axes[1, 0].grid(True, alpha=0.3)

    # Shanghai Premium
    premium = []
    for i, date in enumerate(dates):
        if shfe_prices[i] and silver_prices[i]:
            premium.append(shfe_prices[i] - silver_prices[i])
        else:
            premium.append(None)

    axes[1, 1].bar(
        dates,
        [p if p else 0 for p in premium],
        color=["green" if p and p > 0 else "red" for p in premium],
        alpha=0.7,
    )
    axes[1, 1].axhline(y=0, color="black", linestyle="-", linewidth=0.5)
    axes[1, 1].set_title("Shanghai Premium (SHFE - XAG/USD)")
    axes[1, 1].set_ylabel("Premium (USD/oz)")
    axes[1, 1].grid(True, alpha=0.3)

    # Format x-axis for all subplots
    for ax in axes.flat:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=5))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)

    plt.tight_layout()
    chart_path = "./silver_prices_daily.png"
    plt.savefig(chart_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()
    return chart_path


def send_discord_images(*chart_paths):
    """Send charts to Discord"""
    if not WEBHOOK_URL:
        print("No webhook URL configured")
        return

    for i, chart_path in enumerate(chart_paths):
        filename = os.path.basename(chart_path)
        with open(chart_path, "rb") as f:
            files = {"file": (filename, f, "image/png")}
            if i == 0:
                payload = {
                    "content": f"**📊 Daily Silver Report** - {datetime.utcnow().strftime('%Y-%m-%d')}"
                }
            else:
                payload = {}
            requests.post(WEBHOOK_URL, data=payload, files=files)


def main():
    print("Generating daily silver report...")

    # Get 30 days of data
    daily_data = get_daily_data(days=30)

    print(f"Found data for {len(daily_data)} days")

    # Generate ETF holdings charts (line + bar)
    etf_chart = generate_etf_holdings_charts()
    print(f"✓ ETF holdings chart: {etf_chart}")

    # Generate price chart
    # if daily_data:
    #     price_chart = generate_price_chart(daily_data)
    #     print(f"✓ Price chart: {price_chart}")

    #     # Send to Discord
    #     send_discord_images(etf_chart, price_chart)
    # else:
    #     send_discord_images(etf_chart)
    send_discord_images(etf_chart)

    print("✅ Daily report charts generated")


if __name__ == "__main__":
    main()
