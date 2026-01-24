"""
Core Tasks Module - Unified task execution layer.

This module provides the single source of truth for all task logic.
Both Discord commands and scheduled jobs call these functions.
"""

import os
import sys
import logging
from datetime import datetime
from typing import Tuple, Optional, Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from task_hourly import (
    get_market_update_message,
    fetch_slv_holdings,
    fetch_gld_holdings,
)
from task_daily_report import generate_etf_holdings_charts
from db_manager import DBManager

logger = logging.getLogger(__name__)


class TaskResult:
    """Standardized task result container."""

    def __init__(
        self,
        success: bool,
        message: str = "",
        data: Optional[Dict[str, Any]] = None,
        file_path: Optional[str] = None,
        etf_updated: bool = False
    ):
        self.success = success
        self.message = message
        self.data = data or {}
        self.file_path = file_path
        self.etf_updated = etf_updated
        self.timestamp = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "message": self.message,
            "data": self.data,
            "file_path": self.file_path,
            "etf_updated": self.etf_updated,
            "timestamp": self.timestamp,
        }


def run_hourly(force: bool = False) -> TaskResult:
    """
    Execute hourly market data update.

    This is the unified entry point for:
    - Discord /update_data command
    - HTTP API /run/hourly endpoint
    - Scheduled hourly task
    - CLI: python app.py hourly

    Args:
        force: If True, bypass cache and fetch fresh data

    Returns:
        TaskResult with message content and metadata
    """
    logger.info(f"Running hourly task (force={force})")

    try:
        message, etf_updated = get_market_update_message(force=force)

        logger.info(f"Hourly task completed. ETF updated: {etf_updated}")

        return TaskResult(
            success=True,
            message=message,
            etf_updated=etf_updated,
            data={"force": force}
        )

    except Exception as e:
        logger.error(f"Hourly task failed: {e}", exc_info=True)
        return TaskResult(
            success=False,
            message=f"Error: {str(e)}",
            data={"error": str(e)}
        )


def run_daily() -> TaskResult:
    """
    Execute daily report generation (ETF charts).

    This is the unified entry point for:
    - Discord /update_plot command
    - HTTP API /run/daily endpoint
    - Scheduled daily task
    - CLI: python app.py daily

    Returns:
        TaskResult with chart file path
    """
    logger.info("Running daily report task")

    try:
        chart_path = generate_etf_holdings_charts()

        if chart_path and os.path.exists(chart_path):
            logger.info(f"Daily report generated: {chart_path}")
            return TaskResult(
                success=True,
                message="ETF Holdings Report generated",
                file_path=chart_path
            )
        else:
            return TaskResult(
                success=False,
                message="Chart generation failed - no file created"
            )

    except Exception as e:
        logger.error(f"Daily task failed: {e}", exc_info=True)
        return TaskResult(
            success=False,
            message=f"Error: {str(e)}",
            data={"error": str(e)}
        )


def run_etf_check() -> TaskResult:
    """
    Check for ETF holdings changes.

    This is the unified entry point for:
    - Discord ETF monitor task
    - HTTP API /run/etf-check endpoint
    - Scheduled ETF monitor

    Returns:
        TaskResult with change information
    """
    logger.info("Running ETF check task")

    try:
        db = DBManager()

        # Force fetch fresh data (bypass cache)
        slv_data, _, slv_updated = fetch_slv_holdings(db, force=True)
        gld_data, _, gld_updated = fetch_gld_holdings(db, force=True)

        changes = []
        oz_to_tonnes = 1 / 32150.7

        if slv_updated and slv_data:
            slv_tonnes = slv_data["holdings_oz"] * oz_to_tonnes
            change_oz = slv_data.get("change", 0)
            change_t = change_oz * oz_to_tonnes
            changes.append({
                "etf": "SLV",
                "holdings_tonnes": round(slv_tonnes, 2),
                "change_tonnes": round(change_t, 2)
            })

        if gld_updated and gld_data:
            gld_tonnes = gld_data["holdings_tonnes"]
            change_t = gld_data.get("change_tonnes", 0)
            changes.append({
                "etf": "GLD",
                "holdings_tonnes": round(gld_tonnes, 2),
                "change_tonnes": round(change_t, 2)
            })

        has_changes = len(changes) > 0

        if has_changes:
            msg_parts = []
            for c in changes:
                msg_parts.append(
                    f"• {c['etf']}: **{c['holdings_tonnes']:,.2f}** tonnes "
                    f"({c['change_tonnes']:+.2f}t)"
                )
            message = "ETF Holdings Update Detected!\n\n" + "\n".join(msg_parts)
        else:
            message = "No ETF changes detected"

        logger.info(f"ETF check completed. Changes: {has_changes}")

        return TaskResult(
            success=True,
            message=message,
            etf_updated=has_changes,
            data={
                "slv_updated": slv_updated,
                "gld_updated": gld_updated,
                "changes": changes
            }
        )

    except Exception as e:
        logger.error(f"ETF check failed: {e}", exc_info=True)
        return TaskResult(
            success=False,
            message=f"Error: {str(e)}",
            data={"error": str(e)}
        )


def health_check() -> TaskResult:
    """
    Perform system health check.

    Returns:
        TaskResult with health status
    """
    try:
        # Check database
        db = DBManager()
        with db._get_conn() as conn:
            conn.execute("SELECT 1")

        return TaskResult(
            success=True,
            message="OK",
            data={
                "database": "connected",
                "timestamp": datetime.utcnow().isoformat()
            }
        )

    except Exception as e:
        return TaskResult(
            success=False,
            message=f"Health check failed: {str(e)}",
            data={"error": str(e)}
        )
