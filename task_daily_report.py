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
    """Get ETF daily changes data from database"""
    db = DBManager()

    # Fetch GLD changes
    gld_history = db.get_metric_history("GLD_Daily_Change_Tonnes", days=90)
    gld_changes = {}
    for record in gld_history:
        try:
            dt = datetime.strptime(record["timestamp"], "%Y-%m-%d %H:%M:%S")
            gld_changes[dt.date()] = record["value"]
        except ValueError:
            continue

    # Fetch SLV changes
    slv_history = db.get_metric_history("SLV_Daily_Change_Tonnes", days=90)
    slv_changes = {}
    for record in slv_history:
        try:
            dt = datetime.strptime(record["timestamp"], "%Y-%m-%d %H:%M:%S")
            slv_changes[dt.date()] = record["value"]
        except ValueError:
            continue

    return gld_changes, slv_changes


def get_etf_holdings_data():
    """Get ETF holdings time series from database"""
    db = DBManager()

    # Fetch GLD holdings
    gld_history = db.get_metric_history("GLD_Holdings_Tonnes", days=90)
    gld_dates = []
    gld_holdings = []
    for record in gld_history:
        try:
            dt = datetime.strptime(record["timestamp"], "%Y-%m-%d %H:%M:%S")
            gld_dates.append(dt.date())
            gld_holdings.append(record["value"])
        except ValueError:
            continue

    # Fetch SLV holdings
    slv_history = db.get_metric_history("SLV_Holdings_Tonnes", days=90)
    slv_dates = []
    slv_holdings = []
    for record in slv_history:
        try:
            dt = datetime.strptime(record["timestamp"], "%Y-%m-%d %H:%M:%S")
            slv_dates.append(dt.date())
            slv_holdings.append(record["value"])
        except ValueError:
            continue

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

    # Get current tonnes
    current_gld_tonnes = gld_holdings_sorted[-1] if gld_holdings_sorted else 0

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
        f"GLD Holdings: {current_gld_tonnes:,.2f} tonnes",
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

    # Get current tonnes
    current_slv_tonnes = slv_holdings_sorted[-1] if slv_holdings_sorted else 0

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
        f"SLV Holdings: {current_slv_tonnes:,.2f} tonnes",
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

    # Filter out zero changes and sort by date (descending)
    gld_changes_filtered = {d: v for d, v in gld_changes.items() if abs(v) > 0.001}
    gld_change_dates = sorted(gld_changes_filtered.keys(), reverse=True)[:12]
    gld_change_values = [gld_changes_filtered[d] for d in gld_change_dates]
    gld_change_labels = [d.strftime("%m-%d") for d in gld_change_dates]

    if gld_change_values:
        colors_gld = ["#4CAF50" if v >= 0 else "#F44336" for v in gld_change_values]
        bars_gld = ax3.barh(
            gld_change_labels, gld_change_values, color=colors_gld, height=0.6
        )

        # Calculate max absolute value for symmetric x-axis
        max_val = max(abs(v) for v in gld_change_values)
        limit = max_val * 1.3  # Add 30% padding
        ax3.set_xlim(-limit, limit)

        # Add value labels
        for bar, val in zip(bars_gld, gld_change_values):
            width = bar.get_width()
            # Adjust label position based on value
            label_x = width + (limit * 0.05) if width >= 0 else width - (limit * 0.05)
            ha = "left" if width >= 0 else "right"
            ax3.text(
                label_x,
                bar.get_y() + bar.get_height() / 2,
                f"{val:+.2f}t",
                va="center",
                ha=ha,
                fontsize=9,
            )
    else:
        ax3.text(0.5, 0.5, "No recent changes", ha="center", va="center")

    ax3.axvline(x=0, color="black", linewidth=0.5)
    ax3.set_title("GLD Daily Changes (tonnes)", fontsize=14, fontweight="bold")
    ax3.set_xlabel("Change (tonnes)", fontsize=12)
    ax3.invert_yaxis()  # Most recent at top

    # ===== BOTTOM RIGHT: SLV Daily Changes Bar Chart =====
    ax4 = axes[1, 1]

    # Filter out zero changes and sort by date (descending)
    slv_changes_filtered = {d: v for d, v in slv_changes.items() if abs(v) > 0.001}
    slv_change_dates = sorted(slv_changes_filtered.keys(), reverse=True)[:12]
    slv_change_values = [slv_changes_filtered[d] for d in slv_change_dates]
    slv_change_labels = [d.strftime("%m-%d") for d in slv_change_dates]

    if slv_change_values:
        colors_slv = ["#4CAF50" if v >= 0 else "#F44336" for v in slv_change_values]
        bars_slv = ax4.barh(
            slv_change_labels, slv_change_values, color=colors_slv, height=0.6
        )

        # Calculate max absolute value for symmetric x-axis
        max_val = max(abs(v) for v in slv_change_values)
        limit = max_val * 1.3  # Add 30% padding
        ax4.set_xlim(-limit, limit)

        # Add value labels
        for bar, val in zip(bars_slv, slv_change_values):
            width = bar.get_width()
            # Adjust label position based on value
            label_x = width + (limit * 0.05) if width >= 0 else width - (limit * 0.05)
            ha = "left" if width >= 0 else "right"
            ax4.text(
                label_x,
                bar.get_y() + bar.get_height() / 2,
                f"{val:+.2f}t",
                va="center",
                ha=ha,
                fontsize=9,
            )
    else:
        ax4.text(0.5, 0.5, "No recent changes", ha="center", va="center")

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
