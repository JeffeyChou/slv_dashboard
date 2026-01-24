# Silver Market Discord Bot - 管理命令

## 服务管理

```bash
# 启动 bot
sudo systemctl start slv-bot.service

# 停止 bot
sudo systemctl stop slv-bot.service

# 重启 bot
sudo systemctl restart slv-bot.service

# 查看状态
sudo systemctl status slv-bot.service

# 查看实时日志
tail -f /home/ubuntu/project/slv_dashboard/bot.log

# 健康检查
./check_bot.sh
```

## 自动重启功能

Bot 现在由 systemd 管理，具有以下保护：

- ✅ **自动重启**：崩溃后 10 秒自动重启
- ✅ **开机自启**：系统重启后自动运行
- ✅ **全局异常捕获**：记录所有错误到日志
- ✅ **内存监控**：systemd 显示内存使用情况

## 故障排查

```bash
# 查看最近的错误
grep -i "error\|exception" bot.log | tail -20

# 查看内存使用
free -h

# 查看进程信息
ps aux | grep discord_bot.py

# 查看 systemd 日志
sudo journalctl -u slv-bot.service -n 50
```
