#!/bin/bash
# Setup systemd service for Discord bot

SERVICE_FILE="/home/ubuntu/project/slv_dashboard/discord-bot.service"
SYSTEMD_DIR="$HOME/.config/systemd/user"

# Create systemd user directory if it doesn't exist
mkdir -p "$SYSTEMD_DIR"

# Copy service file
cp "$SERVICE_FILE" "$SYSTEMD_DIR/"

# Reload systemd
systemctl --user daemon-reload

# Enable and start service
systemctl --user enable discord-bot.service
systemctl --user start discord-bot.service

echo "✅ Systemd service installed and started"
echo ""
echo "Useful commands:"
echo "  systemctl --user status discord-bot    # Check status"
echo "  systemctl --user restart discord-bot   # Restart bot"
echo "  systemctl --user stop discord-bot      # Stop bot"
echo "  journalctl --user -u discord-bot -f    # View logs"
