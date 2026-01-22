#!/usr/bin/env python3
"""
Silver Market Discord Bot
Runs a persistent bot that listens for slash commands.

Features:
- Hourly market updates (Mon-Fri 8:00-20:00 EST)
- ETF holdings monitor (Mon-Fri 17:00-19:00 EST, every 5 mins)
- Message editing mode: auto-updates edit existing messages
"""

import os
import sys
import asyncio
import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv
import concurrent.futures
from datetime import datetime
import pytz

# Import tasks
from task_hourly import (
    get_market_update_message,
    fetch_slv_holdings,
    fetch_gld_holdings,
)
from task_daily_report import main as task_daily_main
from db_manager import DBManager

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Check if token exists
if not TOKEN:
    print("Error: DISCORD_BOT_TOKEN not found in .env file.")
    print("Please add your bot token to .env to use slash commands.")
    sys.exit(1)

# Bot setup
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# Executor for running synchronous tasks
executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)

# Store the channel ID and message IDs for updates
target_channel_id = None
data_message_id = None  # Message ID for market data updates
plot_message_id = None  # Message ID for chart updates

# EST timezone
EST = pytz.timezone("America/New_York")


def is_weekday():
    """Check if today is a weekday (Mon=0, Sun=6)"""
    now_est = datetime.now(EST)
    return now_est.weekday() < 5  # 0-4 are Mon-Fri


def is_market_hours():
    """Check if current time is within market hours (Mon-Fri 8:00-20:00 EST)"""
    now_est = datetime.now(EST)
    return is_weekday() and 8 <= now_est.hour < 20


def is_etf_monitor_window():
    """Check if current time is within ETF monitor window (Mon-Fri 17:00-19:00 EST)"""
    now_est = datetime.now(EST)
    return is_weekday() and 17 <= now_est.hour < 19


def check_etf_changes():
    """
    Check if ETF holdings have changed compared to database.
    Returns: (slv_changed, gld_changed, slv_data, gld_data)
    """
    db = DBManager()

    # Force fetch fresh data (bypass cache)
    slv_data, _, slv_updated = fetch_slv_holdings(db, force=True)
    gld_data, _, gld_updated = fetch_gld_holdings(db, force=True)

    return slv_updated, gld_updated, slv_data, gld_data


async def send_or_edit_message(channel, content, message_id=None, file=None):
    """
    Send a new message or edit an existing one.
    Returns the message ID.
    """
    try:
        if message_id:
            try:
                message = await channel.fetch_message(message_id)
                # For file attachments, we need to delete and resend
                if file:
                    await message.delete()
                    new_msg = await channel.send(content=content, file=file)
                    return new_msg.id
                else:
                    await message.edit(content=content)
                    return message_id
            except discord.NotFound:
                # Message was deleted, send new one
                pass
            except discord.HTTPException as e:
                print(f"⚠ Edit failed: {e}, sending new message")

        # Send new message
        if file:
            new_msg = await channel.send(content=content, file=file)
        else:
            new_msg = await channel.send(content=content)
        return new_msg.id
    except Exception as e:
        print(f"❌ Message send/edit failed: {e}")
        return None


@tasks.loop(minutes=60)
async def scheduled_hourly_task():
    """Hourly market update task (Mon-Fri 8:00-20:00 EST)"""
    global data_message_id

    if not target_channel_id:
        return  # Silent skip if no channel set

    # Check if within market hours
    if not is_market_hours():
        now_est = datetime.now(EST)
        print(
            f"⏰ [{now_est.strftime('%H:%M')} EST] Outside market hours, skipping hourly update"
        )
        return

    now_est = datetime.now(EST)
    print(f"🔄 [{now_est.strftime('%H:%M')} EST] Running scheduled hourly update...")

    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            executor, lambda: get_market_update_message(force=False)
        )
        msg, etf_updated = result

        channel = bot.get_channel(target_channel_id)
        if channel:
            # Edit existing message or send new if no message ID stored
            data_message_id = await send_or_edit_message(channel, msg, data_message_id)

            # If ETF data was updated, send a separate notification
            if etf_updated:
                await channel.send(
                    "📊 **ETF data updated!** Use `/update_plot` to refresh the chart."
                )
            print(f"✅ Hourly update {'edited' if data_message_id else 'sent'}")
        else:
            print(f"❌ Could not find channel {target_channel_id}")

    except Exception as e:
        print(f"❌ Scheduled update failed: {e}")


@tasks.loop(minutes=5)
async def etf_monitor_task():
    """
    Monitor ETF holdings changes every 5 minutes.
    Only active during Mon-Fri 17:00-19:00 EST.
    """
    if not target_channel_id:
        return  # Silent skip if no channel set

    # Check if within monitor window (weekdays 17:00-19:00 EST)
    if not is_etf_monitor_window():
        return  # Outside monitor window, skip silently

    now_est = datetime.now(EST)
    print(f"🔍 [{now_est.strftime('%H:%M')} EST] Checking ETF holdings...")

    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(executor, check_etf_changes)
        slv_updated, gld_updated, slv_data, gld_data = result

        if slv_updated or gld_updated:
            channel = bot.get_channel(target_channel_id)
            if channel:
                # Build notification message
                changes = []
                oz_to_tonnes = 1 / 32150.7

                if slv_updated and slv_data:
                    slv_tonnes = slv_data["holdings_oz"] * oz_to_tonnes
                    change_oz = slv_data.get("change", 0)
                    change_t = change_oz * oz_to_tonnes
                    changes.append(
                        f"• SLV: **{slv_tonnes:,.2f}** tonnes ({change_t:+.2f}t)"
                    )

                if gld_updated and gld_data:
                    gld_tonnes = gld_data["holdings_tonnes"]
                    change_t = gld_data.get("change_tonnes", 0)
                    changes.append(
                        f"• GLD: **{gld_tonnes:,.2f}** tonnes ({change_t:+.2f}t)"
                    )

                msg = f"🚨 **ETF Holdings Update Detected!** - {now_est.strftime('%H:%M EST')}\n\n"
                msg += "\n".join(changes)
                msg += "\n\n📊 Use `/update_plot` to refresh the chart."

                await channel.send(msg)
                print(
                    f"✅ ETF change notification sent: SLV={slv_updated}, GLD={gld_updated}"
                )
        else:
            print("   No changes detected")

    except Exception as e:
        print(f"❌ ETF monitor failed: {e}")


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("=" * 50)
    print("Schedule:")
    print("  • Hourly updates: Mon-Fri 8:00-20:00 EST")
    print("  • ETF monitor: Mon-Fri 17:00-19:00 EST (every 5 mins)")
    print("=" * 50)
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(f"Failed to sync commands: {e}")


@bot.tree.command(
    name="autorun_on",
    description="Enable automatic updates and ETF monitor in this channel",
)
async def autorun_on(interaction: discord.Interaction):
    """Enable automatic hourly updates and ETF monitor"""
    global target_channel_id
    target_channel_id = interaction.channel_id

    tasks_started = []

    if not scheduled_hourly_task.is_running():
        scheduled_hourly_task.start()
        tasks_started.append("hourly updates (Mon-Fri 8:00-20:00 EST)")

    if not etf_monitor_task.is_running():
        etf_monitor_task.start()
        tasks_started.append("ETF monitor (Mon-Fri 17:00-19:00 EST)")

    if tasks_started:
        await interaction.response.send_message(
            f"✅ Enabled:\n• "
            + "\n• ".join(tasks_started)
            + f"\n\n📍 Target channel: this channel\n"
            f"💡 Use `/update_data` to create a new message that will be auto-updated.",
            ephemeral=True,
        )
    else:
        await interaction.response.send_message(
            "✅ Target channel updated. All tasks already running.",
            ephemeral=True,
        )


@bot.tree.command(
    name="autorun_off", description="Disable automatic updates and ETF monitor"
)
async def autorun_off(interaction: discord.Interaction):
    """Disable automatic hourly updates and ETF monitor"""
    global data_message_id, plot_message_id
    tasks_stopped = []

    if scheduled_hourly_task.is_running():
        scheduled_hourly_task.cancel()
        tasks_stopped.append("hourly updates")

    if etf_monitor_task.is_running():
        etf_monitor_task.cancel()
        tasks_stopped.append("ETF monitor")

    # Clear message IDs
    data_message_id = None
    plot_message_id = None

    if tasks_stopped:
        await interaction.response.send_message(
            f"🛑 Stopped: {', '.join(tasks_stopped)}\n" f"📝 Message IDs cleared.",
            ephemeral=True,
        )
    else:
        await interaction.response.send_message(
            "ℹ️ No tasks were running.", ephemeral=True
        )


@bot.tree.command(
    name="update_data",
    description="Force update market data (creates new message for auto-updates)",
)
async def update_data(interaction: discord.Interaction):
    """Force update all data and send new message (becomes the target for auto-updates)"""
    global data_message_id

    await interaction.response.send_message(
        "🔄 Updating data... This may take a moment.", ephemeral=True
    )

    try:
        # Run synchronous task in thread pool
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            executor, lambda: get_market_update_message(force=True)
        )
        msg, etf_updated = result

        # Always send NEW message (this becomes the edit target)
        new_msg = await interaction.channel.send(msg)
        data_message_id = new_msg.id

        # If ETF data was updated, notify to use /update_plot
        if etf_updated:
            await interaction.channel.send(
                "📊 **ETF data updated!** Use `/update_plot` to refresh the chart."
            )
            await interaction.followup.send(
                f"✅ Data sent! Message ID: `{data_message_id}`\n"
                f"📝 Future auto-updates will edit this message.\n"
                f"📊 ETF charts available via `/update_plot`",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                f"✅ Data sent! Message ID: `{data_message_id}`\n"
                f"📝 Future auto-updates will edit this message.",
                ephemeral=True,
            )
    except Exception as e:
        await interaction.followup.send(
            f"❌ Error updating data: {str(e)}", ephemeral=True
        )


@bot.tree.command(
    name="update_plot",
    description="Generate ETF chart (creates new message for auto-updates)",
)
async def update_plot(interaction: discord.Interaction):
    """Generate and send ETF chart (becomes the target for auto-updates)"""
    global plot_message_id

    await interaction.response.send_message("📊 Generating chart...", ephemeral=True)

    try:
        # Run synchronous task in thread pool
        loop = asyncio.get_running_loop()
        chart_path = await loop.run_in_executor(executor, task_daily_main)

        # Send to the channel where command was invoked
        if chart_path and os.path.exists(chart_path):
            file = discord.File(chart_path, filename="etf_holdings_report.png")
            now_est = datetime.now(EST)
            content = (
                f"**📊 ETF Holdings Report** - {now_est.strftime('%Y-%m-%d %H:%M EST')}"
            )

            # Always send NEW message (this becomes the edit target)
            new_msg = await interaction.channel.send(content=content, file=file)
            plot_message_id = new_msg.id

            await interaction.followup.send(
                f"✅ Chart sent! Message ID: `{plot_message_id}`\n"
                f"📝 Future chart updates will replace this message.",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                "❌ Chart generation failed (no file returned).", ephemeral=True
            )

    except Exception as e:
        await interaction.followup.send(
            f"❌ Error generating chart: {str(e)}", ephemeral=True
        )


@bot.tree.command(name="status", description="Show current bot status and settings")
async def status(interaction: discord.Interaction):
    """Show current bot status"""
    now_est = datetime.now(EST)

    status_lines = [
        f"**🤖 Bot Status** - {now_est.strftime('%Y-%m-%d %H:%M EST')}",
        "",
        f"**Schedule:**",
        f"• Hourly updates: {'🟢 Running' if scheduled_hourly_task.is_running() else '🔴 Stopped'}",
        f"• ETF monitor: {'🟢 Running' if etf_monitor_task.is_running() else '🔴 Stopped'}",
        "",
        f"**Current Time Windows:**",
        f"• Market hours (8:00-20:00): {'✅ Active' if is_market_hours() else '❌ Inactive'}",
        f"• ETF monitor (17:00-19:00): {'✅ Active' if is_etf_monitor_window() else '❌ Inactive'}",
        "",
        f"**Message IDs:**",
        f"• Data message: `{data_message_id or 'Not set'}`",
        f"• Plot message: `{plot_message_id or 'Not set'}`",
    ]

    if target_channel_id:
        status_lines.append(f"\n📍 Target channel: <#{target_channel_id}>")
    else:
        status_lines.append("\n⚠️ No target channel set. Use `/autorun_on` first.")

    await interaction.response.send_message("\n".join(status_lines), ephemeral=True)


if __name__ == "__main__":
    bot.run(TOKEN)
