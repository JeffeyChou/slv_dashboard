# Discord Bot 修复说明

## 问题诊断

Bot 在自动更新一次后崩溃，无法响应 Discord 命令。

### 根本原因

1. **缺少超时保护** - 数据获取任务可能因网络问题挂起，导致整个 bot 进程卡死
2. **缺少错误处理** - 定时任务中的未捕获异常会导致 bot 崩溃
3. **缺少自动重启机制** - Bot 崩溃后无法自动恢复
4. **日志不完整** - 使用 `print()` 而不是 `logging`，导致难以追踪问题

## 已实施的修复

### 1. 添加超时保护

为所有异步任务添加了超时限制：

```python
# 每小时更新任务：2分钟超时
result = await asyncio.wait_for(
    loop.run_in_executor(executor, lambda: get_market_update_message(force=False)),
    timeout=120
)

# ETF 监控任务：1分钟超时
result = await asyncio.wait_for(
    loop.run_in_executor(executor, check_etf_changes),
    timeout=60
)
```

### 2. 增强错误处理

- 为每个定时任务添加了 `.error` 装饰器
- 捕获并记录所有异常，防止 bot 崩溃
- 使用 `exc_info=True` 记录完整的堆栈跟踪

### 3. 改进日志系统

- 将所有 `print()` 替换为 `logging` 模块
- 同时输出到控制台和文件 (`bot.log`)
- 统一的日志格式，便于问题追踪

### 4. 提供自动重启方案

创建了两种启动方式：

#### 方式 A: 简单启动脚本
```bash
./start_bot.sh
```

#### 方式 B: Systemd 服务（推荐）
```bash
./setup_service.sh
```

Systemd 服务会在 bot 崩溃时自动重启（10秒后）。

## 使用说明

### 启动 Bot

**推荐方式（自动重启）：**
```bash
cd /home/ubuntu/project/slv_dashboard
./setup_service.sh
```

**简单方式：**
```bash
cd /home/ubuntu/project/slv_dashboard
./start_bot.sh
```

### 检查 Bot 状态

```bash
./check_bot.py
```

### 查看日志

```bash
# 实时查看日志
tail -f bot.log

# 查看最近的日志
tail -50 bot.log

# 如果使用 systemd
journalctl --user -u discord-bot -f
```

### Systemd 管理命令

```bash
# 查看状态
systemctl --user status discord-bot

# 重启
systemctl --user restart discord-bot

# 停止
systemctl --user stop discord-bot

# 启动
systemctl --user start discord-bot

# 查看日志
journalctl --user -u discord-bot -f
```

## 文件说明

- `discord_bot.py` - 主 bot 程序（已修复）
- `start_bot.sh` - 快速启动脚本
- `check_bot.py` - 健康检查脚本
- `setup_service.sh` - Systemd 服务安装脚本
- `discord-bot.service` - Systemd 服务配置文件
- `bot.log` - Bot 运行日志

## 测试建议

1. 启动 bot 后，在 Discord 中测试所有命令：
   - `/status` - 查看 bot 状态
   - `/update_data` - 手动更新数据
   - `/update_plot` - 生成图表
   - `/autorun_on` - 启用自动更新
   - `/autorun_off` - 停用自动更新

2. 监控日志确保没有错误：
   ```bash
   tail -f bot.log
   ```

3. 如果使用 systemd，可以手动杀死进程测试自动重启：
   ```bash
   pkill -f discord_bot.py
   sleep 15
   systemctl --user status discord-bot  # 应该显示 running
   ```

## 预防措施

- Bot 现在会在遇到错误时记录日志但继续运行
- 网络请求超时不会导致 bot 崩溃
- 使用 systemd 可以确保 bot 在崩溃后自动重启
- 完整的日志记录便于快速定位问题

## 当前状态

✅ Bot 已启动并正常运行
✅ 所有命令可以在 Discord 中使用
✅ 日志系统正常工作
✅ 错误处理已完善
