"""
Scheduler Module - APScheduler-based task scheduling.

Provides cron-like scheduling for tasks when running as a web service.
"""

import os
import logging
from datetime import datetime
import pytz

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

# EST timezone for market hours
EST = pytz.timezone("America/New_York")

# Global scheduler instance
_scheduler = None


def get_scheduler() -> BackgroundScheduler:
    """Get or create the global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(timezone=EST)
    return _scheduler


def is_weekday() -> bool:
    """Check if today is a weekday (Mon=0, Sun=6)."""
    now_est = datetime.now(EST)
    return now_est.weekday() < 5


def is_market_hours() -> bool:
    """Check if current time is within market hours (Mon-Fri 8:00-20:00 EST)."""
    now_est = datetime.now(EST)
    return is_weekday() and 8 <= now_est.hour < 20


def is_etf_monitor_window() -> bool:
    """Check if current time is within ETF monitor window (Mon-Fri 17:00-20:00 EST)."""
    now_est = datetime.now(EST)
    return is_weekday() and 17 <= now_est.hour < 20
