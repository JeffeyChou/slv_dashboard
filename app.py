#!/usr/bin/env python3
"""
Silver Market Bot - Unified Entry Point

Supports multiple execution modes:
1. Web Server: python app.py serve (or just python app.py)
2. CLI Commands: python app.py hourly|daily|etf-check
3. Health Check: python app.py health

Environment Variables:
- PORT: Web server port (default: 10000)
- DISCORD_WEBHOOK_URL: For sending notifications
- DISCORD_BOT_TOKEN: For Discord bot mode
"""

import os
import sys
import logging
import argparse
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)-8s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# Load environment variables
from dotenv import load_dotenv

load_dotenv()


def create_app():
    """Create Flask application with all routes."""
    from flask import Flask, jsonify, request
    from core.tasks import run_hourly, run_daily, run_etf_check, health_check

    app = Flask(__name__)

    @app.route("/")
    def index():
        """Root endpoint - service info."""
        return jsonify(
            {
                "service": "Silver Market Bot",
                "version": "2.0.0",
                "endpoints": {
                    "/health": "Health check",
                    "/run/hourly": "Run hourly market update",
                    "/run/daily": "Run daily report (charts)",
                    "/run/etf-check": "Check ETF holdings changes",
                },
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

    @app.route("/health")
    def health():
        """Health check endpoint for Render."""
        result = health_check()
        status_code = 200 if result.success else 500
        return jsonify(result.to_dict()), status_code

    def verify_token():
        """Verify API token from request."""
        from urllib.parse import unquote

        token = request.args.get("token", "")
        token = unquote(token)  # Handle URL-encoded tokens
        expected = os.getenv("API_SECRET_TOKEN")
        return not expected or token == expected

    @app.route("/run/hourly")
    def api_hourly():
        """Run hourly market update via HTTP."""
        if not verify_token():
            return jsonify({"error": "Unauthorized"}), 401

        force = request.args.get("force", "false").lower() == "true"
        result = run_hourly(force=force)

        # Optionally send to Discord webhook
        if result.success and os.getenv("DISCORD_WEBHOOK_URL"):
            send_to_webhook(result.message)

        return jsonify(result.to_dict())

    @app.route("/run/daily")
    def api_daily():
        """Run daily report via HTTP."""
        if not verify_token():
            return jsonify({"error": "Unauthorized"}), 401

        result = run_daily()
        return jsonify(result.to_dict())

    @app.route("/run/etf-check")
    def api_etf_check():
        """Check ETF holdings changes via HTTP."""
        if not verify_token():
            return jsonify({"error": "Unauthorized"}), 401

        result = run_etf_check()

        # Send notification if changes detected
        if result.success and result.etf_updated and os.getenv("DISCORD_WEBHOOK_URL"):
            send_to_webhook(f"🚨 **{result.message}**")

        return jsonify(result.to_dict())

    @app.route("/download/db")
    def download_db():
        """Download SQLite database for backup."""
        from flask import send_file

        if not verify_token():
            return jsonify({"error": "Unauthorized"}), 401

        db_path = os.path.join(os.path.dirname(__file__), "market_data.db")
        if os.path.exists(db_path):
            return send_file(db_path, as_attachment=True)
        return jsonify({"error": "Database not found"}), 404

    return app


def send_to_webhook(message: str):
    """Send message to Discord webhook."""
    import requests

    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        return

    try:
        requests.post(webhook_url, json={"content": message}, timeout=10)
        logger.info("Message sent to Discord webhook")
    except Exception as e:
        logger.error(f"Failed to send webhook: {e}")


def cli_hourly(args):
    """CLI: Run hourly task."""
    from core.tasks import run_hourly

    result = run_hourly(force=args.force)
    print(result.message)
    if args.webhook and result.success:
        send_to_webhook(result.message)
    return 0 if result.success else 1


def cli_daily(args):
    """CLI: Run daily task."""
    from core.tasks import run_daily

    result = run_daily()
    print(f"Result: {result.message}")
    if result.file_path:
        print(f"Chart: {result.file_path}")
    return 0 if result.success else 1


def cli_etf_check(args):
    """CLI: Run ETF check."""
    from core.tasks import run_etf_check

    result = run_etf_check()
    print(result.message)
    if args.webhook and result.success and result.etf_updated:
        send_to_webhook(f"🚨 **{result.message}**")
    return 0 if result.success else 1


def cli_health(args):
    """CLI: Health check."""
    from core.tasks import health_check

    result = health_check()
    print(f"Status: {'OK' if result.success else 'FAIL'}")
    print(f"Details: {result.data}")
    return 0 if result.success else 1


def cli_serve(args):
    """CLI: Start web server."""
    app = create_app()
    port = int(os.getenv("PORT", args.port))
    host = args.host
    logger.info(f"Starting web server on {host}:{port}")
    app.run(host=host, port=port, debug=args.debug)
    return 0


def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        description="Silver Market Bot - Unified Entry Point"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # serve command (default)
    serve_parser = subparsers.add_parser("serve", help="Start web server")
    serve_parser.add_argument("--port", type=int, default=10000)
    serve_parser.add_argument("--host", type=str, default="0.0.0.0")
    serve_parser.add_argument("--debug", action="store_true")
    serve_parser.set_defaults(func=cli_serve)

    # hourly command
    hourly_parser = subparsers.add_parser("hourly", help="Run hourly update")
    hourly_parser.add_argument("--force", action="store_true")
    hourly_parser.add_argument("--webhook", action="store_true")
    hourly_parser.set_defaults(func=cli_hourly)

    # daily command
    daily_parser = subparsers.add_parser("daily", help="Run daily report")
    daily_parser.set_defaults(func=cli_daily)

    # etf-check command
    etf_parser = subparsers.add_parser("etf-check", help="Check ETF changes")
    etf_parser.add_argument("--webhook", action="store_true")
    etf_parser.set_defaults(func=cli_etf_check)

    # health command
    health_parser = subparsers.add_parser("health", help="Health check")
    health_parser.set_defaults(func=cli_health)

    args = parser.parse_args()

    # Default to serve if no command specified
    if args.command is None:
        args.command = "serve"
        args.port = 10000
        args.debug = False
        args.func = cli_serve

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
