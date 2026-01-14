# DG-Lab WebSocket 通信协议文档

本文档描述了 PyDGLab-WS 与 DG-Lab App 之间的 WebSocket JSON 通信协议。

## 概述

```
┌─────────────┐     WebSocket/JSON      ┌─────────────┐     Bluetooth     ┌─────────────┐
│  第三方终端  │ <--------------------> │  DG-Lab App │ <---------------> │  郊狼硬件    │
│  (Client)   │                         │  (Target)   │                   │             │
└─────────────┘                         └─────────────┘                   └─────────────┘
```

通信基于 WebSocket 协议，消息格式为 JSON。

---

## 基础消息结构

所有 WebSocket 消息都遵循以下 JSON 结构：

```json
{
  "type": "<消息类型>",
  "clientId": "<终端UUID>",
  "targetId": "<AppUUID>",
  "message": "<消息内容>"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `type` | string | 消息类型，见下表 |
| `clientId` | string (UUID) | 第三方终端的 ID |
| `targetId` | string (UUID) | DG-Lab App 的 ID |
| `message` | string \| number | 消息内容或指令 |

### 消息类型 (type)

| 值 | 说明 |
|----|------|
| `heartbeat` | 心跳包 |
| `bind` | ID 关系绑定 |
| `msg` | 数据指令（波形/强度/清空等） |
| `break` | 连接断开通知 |
| `error` | 服务错误 |

---

## 连接流程

### 1. 终端注册

当终端连接到 WebSocket 服务端时，服务端会自动下发 `clientId`：

**服务端 → 终端：**
```json
{
  "type": "bind",
  "clientId": "550e8400-e29b-41d4-a716-446655440000",
  "targetId": "",
  "message": "targetId"
}
```

### 2. 生成二维码

终端使用获取的 `clientId` 生成二维码 URL，供 App 扫描：

```
https://www.dungeon-lab.com/app-download.php#DGLAB-SOCKET#ws://192.168.1.161:5678/550e8400-e29b-41d4-a716-446655440000
```

格式：`https://www.dungeon-lab.com/app-download.php#DGLAB-SOCKET#<WS服务地址>/<clientId>`

### 3. App 绑定

App 扫码后发起绑定请求：

**App → 服务端：**
```json
{
  "type": "bind",
  "clientId": "550e8400-e29b-41d4-a716-446655440000",
  "targetId": "660e8400-e29b-41d4-a716-446655440001",
  "message": "DGLAB"
}
```

**服务端 → 双方（绑定成功）：**
```json
{
  "type": "bind",
  "clientId": "550e8400-e29b-41d4-a716-446655440000",
  "targetId": "660e8400-e29b-41d4-a716-446655440001",
  "message": "200"
}
```

---

## 响应码 (RetCode)

| 码值 | 说明 |
|------|------|
| `200` | 成功 |
| `209` | 对方客户端已断开 |
| `210` | 二维码中没有有效的 clientId |
| `211` | 服务器迟迟不下发 App 端 ID |
| `400` | 此 ID 已被其他客户端绑定 |
| `401` | 要绑定的目标客户端不存在 |
| `402` | 收信方和寄信方不是绑定关系 |
| `403` | 发送的内容不是标准 JSON |
| `404` | 未找到收信人（离线） |
| `405` | message 长度大于 1950 |
| `500` | 服务器内部异常 |

---

## 数据指令 (msg 类型)

### 强度数据

#### App → 终端：强度更新通知

当 App 端强度发生变化时，向终端发送当前强度数据：

```json
{
  "type": "msg",
  "clientId": "<clientId>",
  "targetId": "<targetId>",
  "message": "strength-<A通道强度>+<B通道强度>+<A通道上限>+<B通道上限>"
}
```

**示例：**
```json
{
  "type": "msg",
  "clientId": "...",
  "targetId": "...",
  "message": "strength-50+30+100+100"
}
```

表示：A 通道强度 50，B 通道强度 30，A 上限 100，B 上限 100。

#### 终端 → App：设置强度

```json
{
  "type": "msg",
  "clientId": "<clientId>",
  "targetId": "<targetId>",
  "message": "strength-<通道>+<操作类型>+<数值>"
}
```

**参数说明：**

| 参数 | 值 | 说明 |
|------|-----|------|
| 通道 | `1` | A 通道 |
| 通道 | `2` | B 通道 |
| 操作类型 | `0` | 减少 |
| 操作类型 | `1` | 增加 |
| 操作类型 | `2` | 设定为指定值 |
| 数值 | 0-200 | 强度值 |

**示例：**
```json
{
  "type": "msg",
  "clientId": "...",
  "targetId": "...",
  "message": "strength-1+2+50"
}
```

表示：将 A 通道 (`1`) 强度设定为 (`2`) 50。

---

### 波形数据

#### 终端 → App：发送波形

```json
{
  "type": "msg",
  "clientId": "<clientId>",
  "targetId": "<targetId>",
  "message": "pulse-<通道>:[<波形数据数组>]"
}
```

**通道值：**
- `A` - A 通道
- `B` - B 通道

**波形数据格式：**

每条波形数据代表 **100ms** 的输出，格式为 16 位十六进制字符串：

```
<freq1><freq2><freq3><freq4><str1><str2><str3><str4>
```

- 前 4 字节：频率值（每 25ms 一个），范围 10-240
- 后 4 字节：强度百分比（每 25ms 一个），范围 0-100

**示例：**
```json
{
  "type": "msg",
  "clientId": "...",
  "targetId": "...",
  "message": "pulse-A:[\"0a0a0a0a64646464\",\"0a0a0a0a00000000\"]"
}
```

解析 `0a0a0a0a64646464`：
- `0a0a0a0a` = 频率 [10, 10, 10, 10]
- `64646464` = 强度 [100, 100, 100, 100]

**Python 转换示例：**
```python
def dump_pulse_operation(pulse):
    """
    pulse 格式: ((freq1, freq2, freq3, freq4), (str1, str2, str3, str4))
    """
    pulse_bytes = bytes().join(
        value.to_bytes(1, 'big')
        for operation in pulse
        for value in operation
    )
    return pulse_bytes.hex()

# 示例
pulse = ((10, 10, 10, 10), (100, 100, 100, 100))
result = dump_pulse_operation(pulse)  # "0a0a0a0a64646464"
```

**限制：**
- 数组最大长度：86 条（计算公式：`(1950 - 129 + 1) // 21`）
- App 波形队列最大容量：500 条（50 秒数据）
- 超出部分会被丢弃

---

### 清空波形队列

#### 终端 → App：清空指定通道波形

```json
{
  "type": "msg",
  "clientId": "<clientId>",
  "targetId": "<targetId>",
  "message": "clear-<通道>"
}
```

**示例：**
```json
{
  "type": "msg",
  "clientId": "...",
  "targetId": "...",
  "message": "clear-1"
}
```

表示：清空 A 通道波形队列。

---

### App 反馈按钮

#### App → 终端：按钮触发通知

```json
{
  "type": "msg",
  "clientId": "<clientId>",
  "targetId": "<targetId>",
  "message": "feedback-<按钮编号>"
}
```

**按钮编号：**

| 编号 | 位置 |
|------|------|
| 0-4 | A 通道 5 个按钮（从左至右） |
| 5-9 | B 通道 5 个按钮（从左至右） |

**示例：**
```json
{
  "type": "msg",
  "clientId": "...",
  "targetId": "...",
  "message": "feedback-0"
}
```

表示：App 按下了 A 通道第一个按钮。

---

## 心跳包

服务端定期向所有连接发送心跳包：

```json
{
  "type": "heartbeat",
  "clientId": "<接收方ID>",
  "targetId": "<绑定方ID>",
  "message": "200"
}
```

---

## 断开连接通知

当一方断开连接时，服务端通知另一方：

```json
{
  "type": "break",
  "clientId": "<终端ID>",
  "targetId": "<AppID>",
  "message": "209"
}
```

---

## 完整通信时序图

```
终端                        服务端                        App
 │                            │                            │
 │──── WebSocket 连接 ────────>│                            │
 │                            │                            │
 │<─── bind (targetId) ───────│                            │
 │     获取 clientId           │                            │
 │                            │                            │
 │     生成二维码              │                            │
 │     ════════════════       │                            │
 │                            │                            │
 │                            │<──── WebSocket 连接 ────────│
 │                            │                            │
 │                            │<──── bind (DGLAB) ─────────│
 │                            │      请求绑定               │
 │                            │                            │
 │<─── bind (200) ────────────│───── bind (200) ──────────>│
 │     绑定成功                │                            │
 │                            │                            │
 │<─── msg (strength-...) ────│<──── strength 更新 ────────│
 │     强度数据                │                            │
 │                            │                            │
 │──── msg (pulse-A:[...]) ───│───── 波形数据 ────────────>│
 │     发送波形                │                            │
 │                            │                            │
 │<─── msg (feedback-0) ──────│<──── 按钮反馈 ─────────────│
 │     按钮触发                │                            │
 │                            │                            │
 │<─── heartbeat (200) ───────│───── heartbeat (200) ─────>│
 │     心跳包                  │                            │
 │                            │                            │
```

---

## 注意事项

1. **消息长度限制**：`message` 字段最大长度为 1950 字符
2. **波形连续性**：建议发送间隔略小于波形数据时长以保证连续
3. **UUID 格式**：所有 ID 使用标准 UUID 格式
4. **JSON 序列化**：使用驼峰命名法（`clientId`, `targetId`）

---

## 参考

- [DG-Lab 官方 Socket 文档](https://github.com/DG-LAB-OPENSOURCE/DG-LAB-OPENSOURCE/blob/main/socket/README.md)
- [PyDGLab-WS 完整文档](https://pydglab-ws.readthedocs.io)
