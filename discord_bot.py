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
import logging

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
    """Check if current time is within ETF monitor window (Mon-Fri 17:00-20:00 EST)"""
    now_est = datetime.now(EST)
    return is_weekday() and 17 <= now_est.hour < 20


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


@tasks.loop(minutes=60)
async def scheduled_hourly_task():
    """Hourly market update task (Mon-Fri 8:00-20:00 EST)"""
    if not active_channels:
        return  # Silent skip if no channels set

    # Check if within market hours
    if not is_market_hours():
        now_est = datetime.now(EST)
        logger.info(
            f"⏰ [{now_est.strftime('%H:%M')} EST] Outside market hours, skipping hourly update"
        )
        return

    now_est = datetime.now(EST)
    logger.info(f"🔄 [{now_est.strftime('%H:%M')} EST] Running scheduled hourly update...")

    try:
        loop = asyncio.get_running_loop()
        # Add timeout to prevent hanging
        result = await asyncio.wait_for(
            loop.run_in_executor(
                executor, lambda: get_market_update_message(force=False)
            ),
            timeout=120  # 2 minute timeout
        )
        msg, etf_updated = result

        # Update all active channels
        for channel_id, msg_ids in active_channels.items():
            channel = bot.get_channel(channel_id)
            if channel:
                # Edit existing message or send new if no message ID stored
                new_msg_id = await send_or_edit_message(channel, msg, msg_ids.get("data_msg_id"))
                active_channels[channel_id]["data_msg_id"] = new_msg_id

                # If ETF data was updated, send a separate notification
                if etf_updated:
                    await channel.send(
                        "📊 **ETF data updated!** Use `/update_plot` to refresh the chart."
                    )
                logger.info(f"✅ Hourly update sent to channel {channel_id}")
            else:
                logger.error(f"Could not find channel {channel_id}")

    except asyncio.TimeoutError:
        logger.error(f"Scheduled update timed out after 120s")
    except Exception as e:
        logger.error(f"Scheduled update failed: {e}", exc_info=True)


@scheduled_hourly_task.error
async def scheduled_hourly_task_error(error):
    """Handle errors in scheduled task to prevent bot crash"""
    logger.error(f"Critical error in hourly task: {error}", exc_info=True)


@tasks.loop(minutes=5)
async def etf_monitor_task():
    """
    Monitor ETF holdings changes every 5 minutes.
    Only active during Mon-Fri 17:00-19:00 EST.
    """
@tasks.loop(minutes=5)
async def etf_monitor_task():
    """
    Monitor ETF holdings changes every 5 minutes.
    Only active during Mon-Fri 17:00-20:00 EST.
    """
    if not active_channels:
        return  # Silent skip if no channels set

    # Check if within monitor window (weekdays 17:00-20:00 EST)
    if not is_etf_monitor_window():
        return  # Outside monitor window, skip silently

    now_est = datetime.now(EST)
    logger.info(f"🔍 [{now_est.strftime('%H:%M')} EST] Checking ETF holdings...")

    try:
        loop = asyncio.get_running_loop()
        # Add timeout to prevent hanging
        result = await asyncio.wait_for(
            loop.run_in_executor(executor, check_etf_changes),
            timeout=60  # 1 minute timeout
        )
        slv_updated, gld_updated, slv_data, gld_data = result

        if slv_updated or gld_updated:
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

            # Send to all active channels
            for channel_id in active_channels.keys():
                channel = bot.get_channel(channel_id)
                if channel:
                    await channel.send(msg)
                    logger.info(f"✅ ETF change notification sent to channel {channel_id}")
        else:
            logger.info("   No changes detected")

    except asyncio.TimeoutError:
        logger.error(f"ETF monitor timed out after 60s")
    except Exception as e:
        logger.error(f"ETF monitor failed: {e}", exc_info=True)


@etf_monitor_task.error
async def etf_monitor_task_error(error):
    """Handle errors in ETF monitor task to prevent bot crash"""
    logger.error(f"Critical error in ETF monitor: {error}", exc_info=True)


@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    logger.info("=" * 50)
    logger.info("Schedule:")
    logger.info("  • Hourly updates: Mon-Fri 8:00-20:00 EST")
    logger.info("  • ETF monitor: Mon-Fri 17:00-20:00 EST (every 5 mins)")
    logger.info("=" * 50)
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} commands")
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}")


@bot.tree.command(
    name="autorun_on",
    description="Enable automatic updates and ETF monitor in this channel",
)
async def autorun_on(interaction: discord.Interaction):
    """Enable automatic hourly updates and ETF monitor"""
    channel_id = interaction.channel_id
    
    # Add channel to active channels
    if channel_id not in active_channels:
        active_channels[channel_id] = {"data_msg_id": None, "plot_msg_id": None}

    tasks_started = []

    if not scheduled_hourly_task.is_running():
        scheduled_hourly_task.start()
        tasks_started.append("hourly updates (Mon-Fri 8:00-20:00 EST)")

    if not etf_monitor_task.is_running():
        etf_monitor_task.start()
        tasks_started.append("ETF monitor (Mon-Fri 17:00-20:00 EST)")

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

    # Defer immediately to avoid 3-second timeout
    await interaction.response.defer(ephemeral=True, thinking=True)

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

    # Defer immediately to avoid 3-second timeout
    await interaction.response.defer(ephemeral=True, thinking=True)

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
            active_channels[channel_id]["plot_msg_id"] = new_msg.id

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
        f"• Hourly updates: {'🟢 Running' if scheduled_hourly_task.is_running() else '🔴 Stopped'}",
        f"• ETF monitor: {'🟢 Running' if etf_monitor_task.is_running() else '🔴 Stopped'}",
        "",
        f"**Current Time Windows:**",
        f"• Market hours (8:00-20:00): {'✅ Active' if is_market_hours() else '❌ Inactive'}",
        f"• ETF monitor (17:00-20:00): {'✅ Active' if is_etf_monitor_window() else '❌ Inactive'}",
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


if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
