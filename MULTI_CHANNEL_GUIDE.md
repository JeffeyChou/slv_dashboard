# Discord Bot 更新完成

## ✅ 已完成的需求

### 1. ETF 监控时间修改
- **原时间**: 周一到周五 17:00-19:00 EST
- **新时间**: 周一到周五 17:00-20:00 EST
- **间隔**: 5 分钟（保持不变）

### 2. 多服务器/多频道支持
- **原架构**: 单个频道，全局 message ID
- **新架构**: 支持多个频道，每个频道独立维护 message ID
- **数据结构**: `active_channels = {channel_id: {"data_msg_id": int, "plot_msg_id": int}}`

#### 工作原理
- 每个频道使用 `/autorun_on` 独立启用自动更新
- 每个频道维护自己的数据消息和图表消息 ID
- 定时任务会遍历所有活跃频道并更新
- 使用 `/autorun_off` 可以单独停止某个频道的更新

### 3. Systemd 服务自动重启
- **服务名称**: `discord-bot.service`
- **重启策略**: 崩溃后 10 秒自动重启
- **日志位置**: `/home/ubuntu/project/slv_dashboard/bot.log`
- **状态**: ✅ 已测试，自动重启正常工作

## 命令说明

### Discord 斜杠命令

| 命令 | 说明 |
|------|------|
| `/autorun_on` | 在当前频道启用自动更新 |
| `/autorun_off` | 在当前频道停止自动更新 |
| `/update_data` | 手动更新市场数据（创建可编辑的消息） |
| `/update_plot` | 生成 ETF 图表（创建可替换的消息） |
| `/status` | 查看 bot 状态和当前频道配置 |

### Systemd 管理命令

```bash
# 查看状态
systemctl --user status discord-bot

# 重启服务
systemctl --user restart discord-bot

# 停止服务
systemctl --user stop discord-bot

# 启动服务
systemctl --user start discord-bot

# 查看日志
journalctl --user -u discord-bot -f

# 或者查看文件日志
tail -f /home/ubuntu/project/slv_dashboard/bot.log
```

### 健康检查

```bash
cd /home/ubuntu/project/slv_dashboard
./check_bot.py
```

## 使用场景示例

### 场景 1: 单个服务器，单个频道
1. 在频道中输入 `/autorun_on`
2. 输入 `/update_data` 创建数据消息
3. Bot 会每小时自动编辑这条消息

### 场景 2: 多个服务器，多个频道
1. 在服务器 A 的频道 1 中输入 `/autorun_on`
2. 在服务器 B 的频道 2 中输入 `/autorun_on`
3. 在每个频道中输入 `/update_data`
4. Bot 会同时更新所有频道的消息

### 场景 3: 停止某个频道的更新
1. 在不需要更新的频道中输入 `/autorun_off`
2. 该频道停止接收更新，其他频道继续正常工作

## 自动更新时间表

| 任务 | 时间窗口 | 频率 |
|------|---------|------|
| 市场数据更新 | 周一-周五 8:00-20:00 EST | 每 60 分钟 |
| ETF 持仓监控 | 周一-周五 17:00-20:00 EST | 每 5 分钟 |

## 技术改进

1. **错误处理**
   - 所有定时任务都有超时保护
   - 异常不会导致 bot 崩溃
   - 完整的错误日志记录

2. **日志系统**
   - 使用 Python logging 模块
   - 同时输出到控制台和文件
   - 包含时间戳和日志级别

3. **可靠性**
   - Systemd 自动重启
   - 每个频道独立运行
   - 单个频道失败不影响其他频道

## 测试建议

1. **基本功能测试**
   ```
   在 Discord 中依次测试：
   /status          # 查看初始状态
   /autorun_on      # 启用自动更新
   /update_data     # 创建数据消息
   /update_plot     # 创建图表
   /status          # 确认消息 ID 已保存
   ```

2. **多频道测试**
   ```
   在不同频道重复上述步骤
   使用 /status 确认每个频道都有独立的 message ID
   ```

3. **自动重启测试**
   ```bash
   # 手动杀死进程
   pkill -9 -f discord_bot.py
   
   # 等待 15 秒
   sleep 15
   
   # 检查是否自动重启
   systemctl --user status discord-bot
   ```

## 文件清单

- `discord_bot.py` - 主程序（已更新）
- `discord-bot.service` - Systemd 服务配置
- `start_bot.sh` - 快速启动脚本
- `setup_service.sh` - Systemd 安装脚本
- `check_bot.py` - 健康检查脚本
- `bot.log` - 运行日志
- `MULTI_CHANNEL_GUIDE.md` - 本文档

## 当前状态

✅ Bot 正在运行（PID: 1499）
✅ Systemd 服务已启用
✅ 自动重启已测试通过
✅ 多频道支持已实现
✅ ETF 监控时间已更新为 17:00-20:00 EST

## 故障排查

### Bot 无响应
```bash
systemctl --user status discord-bot
journalctl --user -u discord-bot -n 50
```

### 查看错误日志
```bash
tail -100 /home/ubuntu/project/slv_dashboard/bot.log | grep ERROR
```

### 手动重启
```bash
systemctl --user restart discord-bot
```

### 完全重置
```bash
systemctl --user stop discord-bot
rm /home/ubuntu/project/slv_dashboard/bot.log
systemctl --user start discord-bot
```
