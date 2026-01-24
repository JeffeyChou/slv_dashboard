# Recall 命令使用说明

## 新增命令

### `/recall_data`
删除当前频道最新的数据消息（由 `/update_data` 创建的消息）

**使用场景：**
- 误调用 `/update_data` 但数据未更新
- 想要清除旧的数据消息
- 重新开始自动更新

**行为：**
- 删除存储的 `data_msg_id` 对应的消息
- 清除频道的 `data_msg_id`（设为 None）
- 可以多次调用，直到没有消息可删除

### `/recall_plot`
删除当前频道最新的图表消息（由 `/update_plot` 创建的消息）

**使用场景：**
- 误调用 `/update_plot` 但图表未更新
- 想要清除旧的图表消息
- 重新生成图表

**行为：**
- 删除存储的 `plot_msg_id` 对应的消息
- 清除频道的 `plot_msg_id`（设为 None）
- 可以多次调用，直到没有消息可删除

## 使用示例

### 场景 1: 撤销错误的数据更新

```
用户: /update_data
Bot: 🔄 Updating data...
Bot: [发送数据消息，但数据未更新]

用户: /recall_data
Bot: ✅ Deleted data message (ID: 123456789)

用户: /update_data
Bot: [重新发送正确的数据消息]
```

### 场景 2: 清理多个旧消息

```
用户: /recall_data
Bot: ✅ Deleted data message (ID: 111111111)

用户: /recall_data
Bot: ❌ No data message found in this channel.
```

### 场景 3: 消息已被手动删除

```
用户: /recall_data
Bot: ⚠️ Message not found (already deleted?). Cleared message ID.
```

## 工作流程

### 正常使用流程
1. `/autorun_on` - 启用自动更新
2. `/update_data` - 创建数据消息
3. `/update_plot` - 创建图表消息
4. Bot 自动更新这些消息

### 撤销流程
1. `/recall_data` - 删除数据消息
2. `/recall_plot` - 删除图表消息
3. `/update_data` - 重新创建数据消息
4. `/update_plot` - 重新创建图表消息

## 技术细节

### 数据结构
```python
active_channels = {
    channel_id: {
        "data_msg_id": int or None,  # 数据消息 ID
        "plot_msg_id": int or None   # 图表消息 ID
    }
}
```

### 删除逻辑
1. 检查频道是否在 `active_channels` 中
2. 检查对应的 message ID 是否存在
3. 尝试获取并删除消息
4. 清除 message ID（设为 None）
5. 记录日志

### 错误处理
- **消息不存在**: 清除 ID，提示用户
- **权限不足**: 显示错误信息
- **其他错误**: 显示错误详情

## 完整命令列表

| 命令 | 说明 |
|------|------|
| `/autorun_on` | 启用自动更新 |
| `/autorun_off` | 停用自动更新 |
| `/update_data` | 创建/更新数据消息 |
| `/update_plot` | 创建/更新图表消息 |
| `/recall_data` | 删除数据消息 ⭐ 新增 |
| `/recall_plot` | 删除图表消息 ⭐ 新增 |
| `/status` | 查看状态 |

## 注意事项

1. **只能删除最新的消息**
   - 每个频道只存储一个 data_msg_id 和一个 plot_msg_id
   - 删除后 ID 会被清除，无法再次删除同一条消息

2. **不影响其他频道**
   - 每个频道独立管理自己的消息
   - 在频道 A 删除不会影响频道 B

3. **自动更新会创建新消息**
   - 如果删除了消息但自动更新仍在运行
   - 下次更新时会发送新消息（因为 ID 为 None）

4. **需要 Bot 权限**
   - Bot 需要有删除消息的权限
   - 如果权限不足会显示错误

## 测试建议

```bash
# 在 Discord 中测试
/update_data          # 创建数据消息
/status               # 确认 message ID 已保存
/recall_data          # 删除消息
/status               # 确认 message ID 已清除
/recall_data          # 再次尝试删除（应该提示无消息）
```

## 日志示例

```
[2026-01-24 05:17:50] [INFO] Deleted data message 123456789 in channel 987654321
[2026-01-24 05:18:00] [INFO] Deleted plot message 111222333 in channel 987654321
```
