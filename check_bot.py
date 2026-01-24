#!/usr/bin/env python3
"""
Discord Bot Health Check
Checks if bot is running and responsive
"""

import os
import sys
import subprocess
from datetime import datetime

def check_process():
    """Check if bot process is running"""
    result = subprocess.run(
        ["pgrep", "-f", "python.*discord_bot.py"],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        pids = result.stdout.strip().split('\n')
        print(f"✅ Bot is running (PID: {', '.join(pids)})")
        return True
    else:
        print("❌ Bot is NOT running")
        return False

def check_logs():
    """Check recent logs"""
    log_files = ["bot.log", "nohup.out"]
    
    for log_file in log_files:
        if os.path.exists(log_file):
            print(f"\n📝 Last 10 lines of {log_file}:")
            print("=" * 60)
            subprocess.run(["tail", "-10", log_file])
            print("=" * 60)
            return
    
    print("\n⚠️  No log files found")

def check_env():
    """Check environment variables"""
    from dotenv import load_dotenv
    load_dotenv()
    
    token = os.getenv("DISCORD_BOT_TOKEN")
    if token:
        print(f"✅ DISCORD_BOT_TOKEN is set (length: {len(token)})")
    else:
        print("❌ DISCORD_BOT_TOKEN is NOT set")
        return False
    return True

def main():
    print("🔍 Discord Bot Health Check")
    print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    env_ok = check_env()
    print()
    
    process_ok = check_process()
    print()
    
    if not process_ok:
        print("\n💡 To start the bot:")
        print("   ./start_bot.sh")
        print("\n💡 Or use systemd (auto-restart):")
        print("   ./setup_service.sh")
    
    check_logs()
    
    return 0 if (env_ok and process_ok) else 1

if __name__ == "__main__":
    sys.exit(main())
