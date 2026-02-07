# Silver Market Bot 📊

[English](#english) | [中文](#中文)

---

## English

A unified silver market monitoring system providing real-time price tracking, ETF holdings analysis, and automated Discord reporting.

### 🚀 Features
- **Real-time Market Data**: Tracks Silver Spot (XAG/USD), COMEX Futures, SHFE Silver, and Gold/Silver ratios.
- **ETF Tracking**: Monitors GLD and SLV holdings with daily change analysis and visual charts.
- **Discord Integration**: 
  - Persistent bot with slash commands (`/update_data`, `/update_plot`, etc.)
  - Automated hourly market updates during Trading Hours.
  - 5-minute interval ETF change alerts.
- **Web API**: Flask-based REST API for manual triggers and health monitoring.
- **Persistent Storage**: Built-in SQLite database with Docker volume support.

### 🛠 Deployment (Docker Compose)
Recommended for VPS (e.g., Oracle ARM A1).

1. **Prepare Environment**:
   ```bash
   # Install Docker/Docker Compose (Ubuntu example)
   curl -fsSL https://get.docker.com -o get-docker.sh && sudo sh get-docker.sh
   sudo apt install -y docker-compose-plugin
   ```

2. **Setup Config**:
   ```bash
   cp .env.template .env
   # Edit .env with your DISCORD_BOT_TOKEN
   ```

3. **Launch**:
   ```bash
   docker compose up -d --build
   ```

### 🛰 API Endpoints
- `GET /health`: System health status.
- `GET /run/hourly`: Trigger manual market update.
- `GET /run/daily`: Generate and send daily charts.

---

## 中文

统一的白银市场监控系统，提供实时价格追踪、ETF 持仓分析和自动化的 Discord 报表。

### 🚀 核心功能
- **实时行情显示**: 追踪现货白银 (XAG/USD)、COMEX 期货、上期所 (SHFE) 白银以及金银比。
- **ETF 数据分析**: 监控 GLD 和 SLV 持仓，提供每日变动分析及可视化图表。
- **Discord 机器人**:
  - 支持斜杠命令 (`/update_data`, `/update_plot` 等)。
  - 交易时段内自动发送每小时行情更新。
  - 每 5 分钟检测一次 ETF 持仓异动并预警。
- **Web API**: 基于 Flask 的 REST API，支持手动触发和健康检查。
- **持久化存储**: 内置 SQLite 数据库，支持 Docker 数据卷挂载。

### 🛠 部署指南 (Docker Compose)
推荐用于 VPS (如 Oracle ARM A1)。

1. **环境准备**:
   ```bash
   # 安装 Docker (以 Ubuntu 为例)
   curl -fsSL https://get.docker.com -o get-docker.sh && sudo sh get-docker.sh
   sudo apt install -y docker-compose-plugin
   ```

2. **配置环境**:
   ```bash
   cp .env.template .env
   # 在 .env 中填入你的 DISCORD_BOT_TOKEN
   ```

3. **启动启动**:
   ```bash
   docker compose up -d --build
   ```

4. **防火墙配置**:
   - 确保在云平台安全组中开启 **10000** 端口。
   - 服务器上执行: `sudo ufw allow 10000/tcp`

### 🛰 API 接口
- `GET /health`: 系统健康状态检查。
- `GET /run/hourly`: 手动触发小时行情更新。
- `GET /run/daily`: 生成并发送每日报表图表。
