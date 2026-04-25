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
import json
import concurrent.futures
from datetime import datetime
import pytz
import logging
import requests
import re

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)-8s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)

# Persistence for active channels
CHANNELS_FILE = os.path.join("cache", "active_channels.json")

def save_active_channels():
    try:
        os.makedirs(os.path.dirname(CHANNELS_FILE), exist_ok=True)
        with open(CHANNELS_FILE, "w") as f:
            json.dump(active_channels, f)
        logger.info(f"Saved {len(active_channels)} active channels to {CHANNELS_FILE}")
    except Exception as e:
        logger.error(f"Failed to save active channels: {e}")

def load_active_channels():
    global active_channels
    if os.path.exists(CHANNELS_FILE):
        try:
            with open(CHANNELS_FILE, "r") as f:
                data = json.load(f)
                # Convert keys back to int
                active_channels = {int(k): v for k, v in data.items()}
            logger.info(f"Loaded {len(active_channels)} active channels from {CHANNELS_FILE}")
        except Exception as e:
            logger.error(f"Failed to load active channels: {e}")
            active_channels = {}
    else:
        active_channels = {}

# Import tasks
from task_hourly import (
    get_market_update_message,
    fetch_slv_holdings,
    fetch_gld_holdings,
)
from task_daily_report import main as task_daily_main
from db_manager import DBManager
from rednote_monitor import RednoteMonitor

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Check if token exists
if not TOKEN:
    logger.error("DISCORD_BOT_TOKEN not found in .env file.")
    logger.error("Please add your bot token to .env to use slash commands.")
    sys.exit(1)

# Bot setup
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# Executor for running synchronous tasks
executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)

# Store multiple channels and their message IDs
# Format: {channel_id: {"data_msg_id": int, "plot_msg_id": int}}
active_channels = {}

# EST timezone
EST = pytz.timezone("America/New_York")


def append_fetch_stamp_to_copy(content):
    if not content:
        return content

    stamp = datetime.now(EST).strftime("%m-%d-%H:%M")
    stamped_lines = []
    pattern = re.compile(r"\[\d{2}-\d{2}-\d{2}:\d{2}\]$")

    for line in content.splitlines():
        if not line.strip() or pattern.search(line):
            stamped_lines.append(line)
            continue
        stamped_lines.append(f"{line} [{stamp}]")

    return "\n".join(stamped_lines)


# Global error handler
@bot.event
async def on_error(event, *args, **kwargs):
    logger.error(f"Unhandled error in {event}", exc_info=True)


def is_weekday():
    """Check if today is a weekday (Mon=0, Sun=6)"""
    now_est = datetime.now(EST)
    return now_est.weekday() < 5  # 0-4 are Mon-Fri


def is_market_hours():
    """Check if current time is within market hours (Mon-Fri 8:00-20:00 EST)"""
    now_est = datetime.now(EST)
    return is_weekday() and 8 <= now_est.hour < 20


def is_etf_monitor_window():
    """Check if current time is within ETF monitor window (Mon-Fri 16:00-21:00 EST)"""
    now_est = datetime.now(EST)
    return is_weekday() and 16 <= now_est.hour < 21


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


@tasks.loop(minutes=15)
async def rednote_monitor_task():
    """
    Monitor Rednote accounts for new posts.
    Runs every 15 minutes.
    """
    cookie = os.getenv("REDNOTE_COOKIE")
    user_ids_raw = os.getenv("REDNOTE_MONITOR_ID_LISTS", "")
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL") or os.getenv("DISCORD_WEBHOOK_URLS", "").split(",")[0]
    
    if not cookie or not user_ids_raw:
        logger.warning("Rednote monitor skipped: REDNOTE_COOKIE or REDNOTE_MONITOR_ID_LISTS not set.")
        return

    logger.info("🏮 Running scheduled Rednote scan...")
    try:
        user_ids = [uid.strip() for uid in user_ids_raw.split(",") if uid.strip()]
        monitor = RednoteMonitor(cookie, user_ids, webhook_url)
        
        # Run in executor because it's synchronous HTTP scraping
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(executor, monitor.scan_all)
    except Exception as e:
        logger.error(f"Rednote monitor task failed: {e}", exc_info=True)


@rednote_monitor_task.error
async def rednote_monitor_task_error(error):
    logger.error(f"Critical error in Rednote monitor task: {error}", exc_info=True)


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
                logger.warning(f"Edit failed: {e}, sending new message")

        # Send new message
        if file:
            new_msg = await channel.send(content=content, file=file)
        else:
            new_msg = await channel.send(content=content)
        return new_msg.id
    except Exception as e:
        logger.error(f"Message send/edit failed: {e}")
        return None

def send_to_webhook(content=None, file_path=None):
    """Send message/file to the configured Discord Webhook URLs."""
    _raw = os.getenv("DISCORD_WEBHOOK_URLS") or os.getenv("DISCORD_WEBHOOK_URL") or ""
    urls = [u.strip() for u in _raw.split(",") if u.strip()]
    if not urls:
        return
    
    for url in urls:
        try:
            data = {}
            if content:
                data["content"] = append_fetch_stamp_to_copy(content)
            
            if file_path and os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    files = {"file": (os.path.basename(file_path), f)}
                    if content:
                        requests.post(url, data=data, files=files, timeout=30)
                    else:
                        requests.post(url, files=files, timeout=30)
            else:
                requests.post(url, json=data, timeout=10)
                
            logger.info("Message sent to Webhook")
        except Exception as e:
            logger.error(f"Failed to send to webhook: {e}")

@tasks.loop(minutes=1)
async def scheduled_daily_market_task():
    """
    Daily market update at 5:00 PM EST (Mon-Fri).
    Replaces the hourly update.
    """
    now_est = datetime.now(EST)
    
    # Check if weekday (Mon-Fri)
    if now_est.weekday() >= 5:
        return

    # Check if 17:00 (5 PM)
    if not (now_est.hour == 17 and now_est.minute == 0):
        return

    logger.info(f"🔄 [{now_est.strftime('%H:%M')} EST] Running daily 5 PM market update...")

    try:
        loop = asyncio.get_running_loop()
        # Fetch Data
        result = await asyncio.wait_for(
            loop.run_in_executor(
                executor, lambda: get_market_update_message(force=True)
            ),
            timeout=180
        )
        msg, etf_updated = result

        # 1. Send to Active Channels (Bot)
        if active_channels:
            for channel_id, msg_ids in active_channels.items():
                channel = bot.get_channel(channel_id)
                if channel:
                    # Send new message (user requested "no hourly update data", so maybe just send new one)
                    # For daily summary, a new message is cleaner than editing old one.
                    # But if we want to maintain the "dashboard" feel, we might edit.
                    # User said "trigger send message", implies a notification.
                    # I'll stick to sending a new message for visibility.
                    await channel.send(msg)
                    logger.info(f"✅ Daily update sent to channel {channel_id}")
        
        # 2. Send to Webhook (URL)
        send_to_webhook(content=msg)

    except Exception as e:
        logger.error(f"Daily update failed: {e}", exc_info=True)

@scheduled_daily_market_task.error
async def scheduled_daily_market_task_error(error):
    logger.error(f"Critical error in daily market task: {error}", exc_info=True)


@tasks.loop(minutes=5)
async def etf_monitor_task():
    """
    Monitor ETF holdings changes every 5 minutes.
    Active window: Mon-Fri 16:00-21:00 EST.
    """
    # Check if within window (16:00 - 21:00 EST)
    now_est = datetime.now(EST)
    if not (now_est.weekday() < 5 and 16 <= now_est.hour < 21):
        return  # Outside monitor window

    logger.info(f"🔍 [{now_est.strftime('%H:%M')} EST] Checking ETF holdings...")

    try:
        loop = asyncio.get_running_loop()
        # Add timeout to prevent hanging
        result = await asyncio.wait_for(
            loop.run_in_executor(executor, check_etf_changes),
            timeout=60  # 1 minute timeout
        )
        slv_updated, gld_updated, slv_data, gld_data = result

        # Filter: Only send notifications within ETF monitor window (16:00-21:00 EST)
        if not (now_est.weekday() < 5 and 16 <= now_est.hour < 21):
            logger.info(f"   Skipping notification - outside ETF monitor window ({now_est.strftime('%H:%M EST')})")
            return

        if slv_updated or gld_updated:
            # Build notification message
            changes = []
            oz_to_tonnes = 1 / 32150.7

            if slv_updated and slv_data and slv_data.get("holdings_oz"):
                slv_tonnes = slv_data["holdings_oz"] * oz_to_tonnes
                change_oz = slv_data.get("change", 0)
                change_t = change_oz * oz_to_tonnes
                # Filter: Skip tiny changes (< 0.1 tonnes) as noise
                if abs(change_t) >= 0.1 or abs(slv_tonnes) > 0:
                    changes.append(
                        f"• SLV: **{slv_tonnes:,.2f}** tonnes ({change_t:+.2f}t)"
                    )

            if gld_updated and gld_data and gld_data.get("holdings_tonnes"):
                gld_tonnes = gld_data["holdings_tonnes"]
                change_t = gld_data.get("change_tonnes", 0)
                # Filter: Skip tiny changes (< 0.1 tonnes) as noise
                if abs(change_t) >= 0.1 or abs(gld_tonnes) > 0:
                    changes.append(
                        f"• GLD: **{gld_tonnes:,.2f}** tonnes ({change_t:+.2f}t)"
                    )

            # Filter: Skip if no actual data changes (blank update)
            if not changes:
                logger.info("   Skipping blank ETF update - no valid data changes")
                return

            msg = f"🚨 **ETF Holdings Update Detected!** - {now_est.strftime('%H:%M EST')}\n\n"
            msg += "\n".join(changes)
            msg += "\n\n📊 Use `/update_plot` to refresh the chart."
            msg = append_fetch_stamp_to_copy(msg)

            # Send to all active channels
            for channel_id in active_channels.keys():
                channel = bot.get_channel(channel_id)
                if channel:
                    await channel.send(msg)
                    logger.info(f"✅ ETF change notification sent to channel {channel_id}")
            
            # Send to Webhook
            send_to_webhook(content=msg)
        else:
            logger.info("   No changes detected in ETF holdings")

    except asyncio.TimeoutError:
        logger.error(f"ETF monitor timed out after 60s")
    except Exception as e:
        logger.error(f"ETF monitor failed: {e}", exc_info=True)



@etf_monitor_task.error
async def etf_monitor_task_error(error):
    """Handle errors in ETF monitor task to prevent bot crash"""
    logger.error(f"Critical error in ETF monitor: {error}", exc_info=True)


@tasks.loop(minutes=1)
async def daily_plot_task():
    """
    Generate and send Market Update and ETF chart daily at 8:30 PM EST (Mon-Fri).
    """
    now_est = datetime.now(EST)
    
    # Check if it's a weekday (Mon-Fri)
    if now_est.weekday() >= 5:
        return

    # Check if time is 20:30 (8:30 PM)
    if not (now_est.hour == 20 and now_est.minute == 30):
        return
        
    logger.info(f"📊 [20:30 EST] Running daily 8:30 PM report task...")

    try:
        loop = asyncio.get_running_loop()
        
        # 1. Fetch Latest Market Data Message
        market_result = await loop.run_in_executor(
            executor, lambda: get_market_update_message(force=True)
        )
        market_msg, _ = market_result
        
        # 2. Generate ETF Chart
        chart_path = await loop.run_in_executor(
            executor, lambda: task_daily_main(send_discord=False)
        )

        full_msg = f"**🏁 End of Day Market Report** - {now_est.strftime('%Y-%m-%d %H:%M EST')}\n\n{market_msg}"
        full_msg = append_fetch_stamp_to_copy(full_msg)

        if chart_path and os.path.exists(chart_path):
            file_name = "etf_holdings_report.png"

            # 1. Send to Active Channels
            if active_channels:
                for channel_id in active_channels.keys():
                    channel = bot.get_channel(channel_id)
                    if channel:
                        file = discord.File(chart_path, filename=file_name)
                        await channel.send(content=full_msg, file=file)
                        logger.info(f"✅ Daily report sent to channel {channel_id}")
            
            # 2. Send to Webhook
            send_to_webhook(content=full_msg, file_path=chart_path)
            
        else:
            # Send without chart if chart failed
            if active_channels:
                for channel_id in active_channels.keys():
                    channel = bot.get_channel(channel_id)
                    if channel:
                        await channel.send(content=full_msg)
            send_to_webhook(content=full_msg)
            logger.info("Daily report sent without chart (generation failed)")

    except Exception as e:
        logger.error(f"Daily report task failed: {e}", exc_info=True)


@daily_plot_task.error
async def daily_plot_task_error(error):
    """Handle errors in daily plot task"""
    logger.error(f"Critical error in daily plot task: {error}", exc_info=True)


@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    
    # Load persisted active channels
    load_active_channels()
    
    # Start tasks automatically
    if not scheduled_daily_market_task.is_running():
        scheduled_daily_market_task.start()
        logger.info("Started scheduled_daily_market_task")
        
    if not etf_monitor_task.is_running():
        etf_monitor_task.start()
        logger.info("Started etf_monitor_task")
        
    if not daily_plot_task.is_running():
        daily_plot_task.start()
        logger.info("Started daily_plot_task")

    if not rednote_monitor_task.is_running():
        rednote_monitor_task.start()
        logger.info("Started rednote_monitor_task")

    logger.info("=" * 50)
    logger.info("Schedule (EST):")
    logger.info("  • Daily Market Update: Mon-Fri 17:00 (5 PM)")
    logger.info("  • ETF Monitor: Mon-Fri 16:00-21:00 (Every 5 mins)")
    logger.info("  • Daily Report (Data+Chart): Mon-Fri 20:30 (8:30 PM)")
    logger.info("  • Rednote Monitor: Every 15 mins")
    logger.info("=" * 50)
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} commands")
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}")


@bot.tree.command(
    name="autorun_on",
    description="Enable automatic daily updates and ETF monitor in this channel",
)
async def autorun_on(interaction: discord.Interaction):
    """Enable automatic daily updates and ETF monitor"""
    channel_id = interaction.channel_id
    
    # Add channel to active channels
    if channel_id not in active_channels:
        active_channels[channel_id] = {"data_msg_id": None, "plot_msg_id": None}
        save_active_channels()

    tasks_started = []

    if not scheduled_daily_market_task.is_running():
        scheduled_daily_market_task.start()
        tasks_started.append("Daily Market Update (Mon-Fri 17:00 EST)")

    if not etf_monitor_task.is_running():
        etf_monitor_task.start()
        tasks_started.append("ETF Monitor (Mon-Fri 16:00-21:00 EST)")

    if not daily_plot_task.is_running():
        daily_plot_task.start()
        tasks_started.append("Daily Final Report (Mon-Fri 20:30 EST)")

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
            f"✅ This channel added to active channels. Tasks already running.",
            ephemeral=True,
        )


@bot.tree.command(
    name="autorun_off", description="Disable automatic updates in this channel"
)
async def autorun_off(interaction: discord.Interaction):
    """Remove this channel from automatic updates"""
    channel_id = interaction.channel_id
    
    if channel_id in active_channels:
        del active_channels[channel_id]
        save_active_channels()
        await interaction.response.send_message(
            f"🛑 This channel removed from automatic updates.\n"
            f"📝 Remaining active channels: {len(active_channels)}",
            ephemeral=True,
        )
    else:
        await interaction.response.send_message(
            "ℹ️ This channel was not receiving automatic updates.",
            ephemeral=True,
        )


@bot.tree.command(
    name="update_data",
    description="Force update market data (creates new message for auto-updates)",
)
async def update_data(interaction: discord.Interaction):
    """Force update all data and send new message (becomes the target for auto-updates)"""
    channel_id = interaction.channel_id
    
    # Ensure channel is in active_channels
    if channel_id not in active_channels:
        active_channels[channel_id] = {"data_msg_id": None, "plot_msg_id": None}

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
        active_channels[channel_id]["data_msg_id"] = new_msg.id
        save_active_channels()

        # If ETF data was updated, notify to use /update_plot
        if etf_updated:
            await interaction.channel.send(
                "📊 **ETF data updated!** Use `/update_plot` to refresh the chart."
            )
            await interaction.followup.send(
                f"✅ Data sent! Message ID: `{new_msg.id}`\n"
                f"📝 Future auto-updates will edit this message.\n"
                f"📊 ETF charts available via `/update_plot`",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                f"✅ Data sent! Message ID: `{new_msg.id}`\n"
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
    channel_id = interaction.channel_id
    
    # Ensure channel is in active_channels
    if channel_id not in active_channels:
        active_channels[channel_id] = {"data_msg_id": None, "plot_msg_id": None}

    await interaction.response.send_message("📊 Generating chart...", ephemeral=True)

    try:
        # Run synchronous task in thread pool
        loop = asyncio.get_running_loop()
        chart_path = await loop.run_in_executor(
            executor, lambda: task_daily_main(send_discord=False)
        )

        # Send to the channel where command was invoked
        if chart_path and os.path.exists(chart_path):
            file = discord.File(chart_path, filename="etf_holdings_report.png")
            now_est = datetime.now(EST)
            content = (
                f"**📊 ETF Holdings Report** - {now_est.strftime('%Y-%m-%d %H:%M EST')}"
            )
            content = append_fetch_stamp_to_copy(content)

            # Always send NEW message (this becomes the edit target)
            new_msg = await interaction.channel.send(content=content, file=file)
            active_channels[channel_id]["plot_msg_id"] = new_msg.id
            save_active_channels()

            await interaction.followup.send(
                f"✅ Chart sent! Message ID: `{new_msg.id}`\n"
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
    channel_id = interaction.channel_id

    status_lines = [
        f"**🤖 Bot Status** - {now_est.strftime('%Y-%m-%d %H:%M EST')}",
        "",
        f"**Schedule:**",
        f"• Daily Update (17:00): {'🟢 Running' if scheduled_daily_market_task.is_running() else '🔴 Stopped'}",
        f"• ETF Monitor (16:00-21:00): {'🟢 Running' if etf_monitor_task.is_running() else '🔴 Stopped'}",
        f"• Daily Report (20:30): {'🟢 Running' if daily_plot_task.is_running() else '🔴 Stopped'}",
        f"• Rednote Monitor: {'🟢 Running' if rednote_monitor_task.is_running() else '🔴 Stopped'}",
        "",
        f"• Market hours (8:00-20:00): {'✅ Active' if is_market_hours() else '❌ Inactive'}",
        f"• ETF monitor (16:00-21:00): {'✅ Active' if is_etf_monitor_window() else '❌ Inactive'}",

        "",
        f"**Active Channels:** {len(active_channels)}",
    ]

    if channel_id in active_channels:
        msg_ids = active_channels[channel_id]
        status_lines.append(f"\n**This Channel:**")
        status_lines.append(f"• Data message: `{msg_ids['data_msg_id'] or 'Not set'}`")
        status_lines.append(f"• Plot message: `{msg_ids['plot_msg_id'] or 'Not set'}`")
    else:
        status_lines.append("\n⚠️ This channel is not active. Use `/autorun_on` first.")


    await interaction.response.send_message("\n".join(status_lines), ephemeral=True)


@bot.tree.command(name="recall_data", description="Delete the latest data message in this channel")
async def recall_data(interaction: discord.Interaction):
    """Delete the most recent data message"""
    channel_id = interaction.channel_id
    
    if channel_id not in active_channels or not active_channels[channel_id]["data_msg_id"]:
        await interaction.response.send_message(
            "❌ No data message found in this channel.",
            ephemeral=True
        )
        return
    
    msg_id = active_channels[channel_id]["data_msg_id"]
    
    try:
        message = await interaction.channel.fetch_message(msg_id)
        await message.delete()
        active_channels[channel_id]["data_msg_id"] = None
        await interaction.response.send_message(
            f"✅ Deleted data message (ID: `{msg_id}`)",
            ephemeral=True
        )
        logger.info(f"Deleted data message {msg_id} in channel {channel_id}")
    except discord.NotFound:
        active_channels[channel_id]["data_msg_id"] = None
        await interaction.response.send_message(
            "⚠️ Message not found (already deleted?). Cleared message ID.",
            ephemeral=True
        )
    except Exception as e:
        await interaction.response.send_message(
            f"❌ Error deleting message: {str(e)}",
            ephemeral=True
        )


@bot.tree.command(name="recall_plot", description="Delete the latest plot message in this channel")
async def recall_plot(interaction: discord.Interaction):
    """Delete the most recent plot message"""
    channel_id = interaction.channel_id
    
    if channel_id not in active_channels or not active_channels[channel_id]["plot_msg_id"]:
        await interaction.response.send_message(
            "❌ No plot message found in this channel.",
            ephemeral=True
        )
        return
    
    msg_id = active_channels[channel_id]["plot_msg_id"]
    
    try:
        message = await interaction.channel.fetch_message(msg_id)
        await message.delete()
        active_channels[channel_id]["plot_msg_id"] = None
        await interaction.response.send_message(
            f"✅ Deleted plot message (ID: `{msg_id}`)",
            ephemeral=True
        )
        logger.info(f"Deleted plot message {msg_id} in channel {channel_id}")
    except discord.NotFound:
        active_channels[channel_id]["plot_msg_id"] = None
        await interaction.response.send_message(
            "⚠️ Message not found (already deleted?). Cleared message ID.",
            ephemeral=True
        )
    except Exception as e:
        await interaction.response.send_message(
            f"❌ Error deleting message: {str(e)}",
            ephemeral=True
        )



@bot.tree.command(
    name="send_to_webhook_data",
    description="Manually update data and send to the external Webhook URL",
)
async def send_to_webhook_data(interaction: discord.Interaction):
    """Force update data and send to the external Webhook URL"""
    _raw = os.getenv("DISCORD_WEBHOOK_URLS") or os.getenv("DISCORD_WEBHOOK_URL") or ""
    urls = [u.strip() for u in _raw.split(",") if u.strip()]
    if not urls:
        await interaction.response.send_message(
            "❌ Webhook URL not configured in .env", ephemeral=True
        )
        return

    await interaction.response.send_message(
        "🔄 Fetching data and sending to Webhook...", ephemeral=True
    )

    try:
        # Run synchronous task in thread pool
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            executor, lambda: get_market_update_message(force=True)
        )
        msg, _ = result
        msg = append_fetch_stamp_to_copy(msg)

        # Send to Webhook
        def _send():
            success = True
            for url in urls:
                resp = requests.post(url, json={"content": msg}, timeout=10)
                if resp.status_code not in [200, 204]:
                    success = False
            return success

        is_success = await loop.run_in_executor(executor, _send)

        if is_success:
            await interaction.followup.send("✅ Data sent to Webhook successfully!", ephemeral=True)
        else:
            await interaction.followup.send(
                f"⚠️ One or more Webhook sends failed", ephemeral=True
            )

    except Exception as e:
        await interaction.followup.send(
            f"❌ Error sending to Webhook: {str(e)}", ephemeral=True
        )


@bot.tree.command(
    name="send_to_webhook_chart",
    description="Manually generate chart and send to the external Webhook URL",
)
async def send_to_webhook_chart(interaction: discord.Interaction):
    """Generate chart and send to the external Webhook URL"""
    _raw = os.getenv("DISCORD_WEBHOOK_URLS") or os.getenv("DISCORD_WEBHOOK_URL") or ""
    urls = [u.strip() for u in _raw.split(",") if u.strip()]
    if not urls:
        await interaction.response.send_message(
            "❌ Webhook URL not configured in .env", ephemeral=True
        )
        return

    await interaction.response.send_message(
        "📊 Generating chart and sending to Webhook...", ephemeral=True
    )

    try:
        # Run synchronous task in thread pool
        loop = asyncio.get_running_loop()
        chart_path = await loop.run_in_executor(
            executor, lambda: task_daily_main(send_discord=False)
        )

        if chart_path and os.path.exists(chart_path):
            # Send to Webhook with file
            def _send():
                success = True
                for url in urls:
                    with open(chart_path, "rb") as f:
                        now_est = datetime.now(EST)
                        content = f"**📊 Daily ETF Holdings Report** - {now_est.strftime('%Y-%m-%d %H:%M EST')}"
                        content = append_fetch_stamp_to_copy(content)
                        files = {"file": ("etf_holdings_report.png", f)}
                        data = {"content": content}
                        resp = requests.post(url, data=data, files=files, timeout=30)
                        if resp.status_code not in [200, 204]:
                            success = False
                return success

            is_success = await loop.run_in_executor(executor, _send)

            if is_success:
                await interaction.followup.send("✅ Chart sent to Webhook successfully!", ephemeral=True)
            else:
                await interaction.followup.send(
                    f"⚠️ One or more Webhook sends failed", ephemeral=True
                )
        else:
            await interaction.followup.send(
                "❌ Chart generation failed (no file returned).", ephemeral=True
            )

    except Exception as e:
        await interaction.followup.send(
            f"❌ Error sending to Webhook: {str(e)}", ephemeral=True
        )


if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
