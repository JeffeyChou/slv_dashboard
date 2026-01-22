---
description: Deploy the Silver Market Bot to a Linux VPS
---

# Deploy to VPS

This workflow guides you through deploying the bot to a remote Linux VPS (e.g., Ubuntu/Debian).

## Prerequisites

*   A Linux VPS with root or sudo access.
*   Python 3.8+ installed.
*   Git installed.

## 1. Setup Environment

SSH into your VPS and run:

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python and Git
sudo apt install -y python3 python3-pip python3-venv git
```

## 2. Clone and Install

```bash
# Clone repository (replace with your repo URL)
git clone https://github.com/JeffeyChou/slv_dashboard.git
cd slv_dashboard

# Create virtual environment (optional but recommended on VPS)
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## 3. Configure

```bash
# Copy template
cp .env.template .env

# Edit .env with your actual keys
nano .env
```

## 4. Run the Bot

### Option A: Using `nohup` (Quick & Simple)

Use `nohup` to keep the process running after you disconnect.

```bash
# Run in background
nohup python3 discord_bot.py > bot.log 2>&1 &

# Check status
ps aux | grep discord_bot.py

# View logs
tail -f bot.log
```

**To stop it:**
```bash
pkill -f discord_bot.py
```

### Option B: Using `systemd` (Recommended for Production)

This ensures the bot restarts automatically if the server reboots or the bot crashes.

1.  Create a service file:
    ```bash
    sudo nano /etc/systemd/system/silverbot.service
    ```

2.  Paste the following (adjust paths/user):
    ```ini
    [Unit]
    Description=Silver Market Discord Bot
    After=network.target

    [Service]
    # Replace 'ubuntu' with your username
    User=ubuntu
    WorkingDirectory=/home/ubuntu/slv_dashboard
    # If using venv:
    ExecStart=/home/ubuntu/slv_dashboard/venv/bin/python discord_bot.py
    # If NOT using venv:
    # ExecStart=/usr/bin/python3 /home/ubuntu/slv_dashboard/discord_bot.py
    Restart=always

    [Install]
    WantedBy=multi-user.target
    ```

3.  Enable and start:
    ```bash
    sudo systemctl daemon-reload
    sudo systemctl enable silverbot
    sudo systemctl start silverbot
    ```

4.  Check status:
    ```bash
    sudo systemctl status silverbot
    ```

5.  View logs:
    ```bash
    journalctl -u silverbot -f
    ```