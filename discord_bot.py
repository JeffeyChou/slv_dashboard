#!/usr/bin/env python3
"""
Silver Market Discord Bot - Main Entry Point
Usage: python discord_bot.py [--force]
"""
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from task_hourly import main

if __name__ == '__main__':
    main()
