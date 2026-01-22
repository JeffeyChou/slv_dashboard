#!/usr/bin/env python3
"""
Silver Market Discord Bot
Runs a persistent bot that listens for slash commands.
"""

import os
import sys
import asyncio
import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv
import concurrent.futures

# Import tasks
from task_hourly import main as task_hourly_main
from task_daily_report import main as task_daily_main

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
executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)


@tasks.loop(minutes=60)
async def scheduled_hourly_task():
    print("🔄 Running scheduled hourly update...")
    try:
        loop = asyncio.get_running_loop()
        # Run with force=False for regular updates
        await loop.run_in_executor(executor, lambda: task_hourly_main(force=False))
        print("✅ Scheduled update completed")
    except Exception as e:
        print(f"❌ Scheduled update failed: {e}")


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(f"Failed to sync commands: {e}")


@bot.tree.command(name="autorun_on", description="Enable automatic hourly updates")
async def autorun_on(interaction: discord.Interaction):
    """Enable automatic hourly updates"""
    if not scheduled_hourly_task.is_running():
        scheduled_hourly_task.start()
        await interaction.response.send_message(
            "✅ Automatic updates enabled (runs every 60 mins).", ephemeral=True
        )
    else:
        await interaction.response.send_message(
            "ℹ️ Automatic updates are already running.", ephemeral=True
        )


@bot.tree.command(name="autorun_off", description="Disable automatic hourly updates")
async def autorun_off(interaction: discord.Interaction):
    """Disable automatic hourly updates"""
    if scheduled_hourly_task.is_running():
        scheduled_hourly_task.cancel()
        await interaction.response.send_message(
            "🛑 Automatic updates disabled.", ephemeral=True
        )
    else:
        await interaction.response.send_message(
            "ℹ️ Automatic updates are already disabled.", ephemeral=True
        )


@bot.tree.command(
    name="update_data", description="Force update all market data and send report"
)
async def update_data(interaction: discord.Interaction):
    """Force update all data and send new message"""
    await interaction.response.send_message(
        "🔄 Updating data... This may take a moment.", ephemeral=True
    )

    try:
        # Run synchronous task in thread pool
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(executor, lambda: task_hourly_main(force=True))

        await interaction.followup.send("✅ Data updated and sent!", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(
            f"❌ Error updating data: {str(e)}", ephemeral=True
        )


@bot.tree.command(
    name="update_plot", description="Generate and send ETF holdings chart"
)
async def update_plot(interaction: discord.Interaction):
    """Generate and send ETF chart"""
    await interaction.response.send_message("📊 Generating chart...", ephemeral=True)

    try:
        # Run synchronous task in thread pool
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(executor, task_daily_main)

        await interaction.followup.send("✅ Chart generated and sent!", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(
            f"❌ Error generating chart: {str(e)}", ephemeral=True
        )


if __name__ == "__main__":
    bot.run(TOKEN)
