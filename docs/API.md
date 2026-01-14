# API 参考

本文档详细说明 PyDGLab-WS (YCY Fork) 提供的所有接口。

## 目录

- [扫描设备](#扫描设备)
- [连接管理](#连接管理)
- [DG-Lab 兼容接口](#dg-lab-兼容接口)
- [役次元扩展接口](#役次元扩展接口)
- [枚举类型](#枚举类型)

---

## 扫描设备

### `YCYScanner.scan()`

扫描附近的役次元设备。

```python
from pydglab_ws import YCYScanner

devices = await YCYScanner.scan(timeout=5.0)
for device in devices:
    print(f"{device.name} ({device.address})")
```

**参数:**
- `timeout` (float): 扫描超时时间，单位秒，默认 5.0

**返回:**
- `List[YCYDevice]`: 发现的设备列表

---

## 连接管理

### `YCYBLEClient`

役次元 BLE 客户端，支持上下文管理器。

```python
from pydglab_ws import YCYBLEClient

# 方式 1: 上下文管理器 (推荐)
async with YCYBLEClient(device.address) as client:
    # 使用 client...
    pass

# 方式 2: 手动管理
client = YCYBLEClient(device.address)
await client.connect()
# 使用 client...
await client.disconnect()
```

**构造参数:**
- `device` (str | BLEDevice | YCYDevice): 设备地址或设备对象
- `strength_limit` (int): 虚拟强度上限，默认 200 (DG-Lab 兼容)

### `client.connected`

**属性** - 是否已连接。

```python
if client.connected:
    print("已连接")
```

---

## DG-Lab 兼容接口

以下接口与原版 PyDGLab-WS 兼容，方便迁移现有代码。

### `client.set_strength()`

设置通道强度。

```python
from pydglab_ws import Channel, StrengthOperationType

# 设置 A 通道强度为 50
await client.set_strength(Channel.A, StrengthOperationType.SET_TO, 50)

# 增加 A 通道强度 10
await client.set_strength(Channel.A, StrengthOperationType.INCREASE, 10)

# 减少 B 通道强度 5
await client.set_strength(Channel.B, StrengthOperationType.DECREASE, 5)
```

**参数:**
- `channel` (Channel): 通道选择 (`Channel.A` 或 `Channel.B`)
- `operation_type` (StrengthOperationType): 操作类型
- `value` (int): 强度值 (DG-Lab 范围 0-200)

**返回:**
- `bool`: 是否成功

**说明:**
- 强度值自动映射: DG-Lab 0-200 → YCY 1-276
- 强度为 0 时自动禁用通道

### `client.add_pulses()`

添加波形到队列 (软件模拟)。

```python
from pydglab_ws import Channel

# 添加波形数据
await client.add_pulses(Channel.A, "0A0A0A0A", "14141414")
```

**参数:**
- `channel` (Channel): 通道选择
- `*pulses` (PulseOperation): 波形数据 (每条 100ms)

**返回:**
- `bool`: 是否成功

**说明:**
- 波形通过软件队列播放，每 100ms 下发一次
- 需要持续添加波形以维持输出

### `client.clear_pulses()`

清空波形队列。

```python
await client.clear_pulses(Channel.A)
```

**参数:**
- `channel` (Channel): 通道选择

**返回:**
- `bool`: 是否成功

### `client.strength_data`

**属性** - 获取当前强度数据。

```python
data = client.strength_data
print(f"A通道: {data.a}, B通道: {data.b}")
print(f"A上限: {data.a_limit}, B上限: {data.b_limit}")
```

**返回:**
- `StrengthData`: 包含 a, b, a_limit, b_limit 字段

### `client.client_id` / `client.target_id`

**属性** - DG-Lab 兼容的 ID (基于设备地址生成的 UUID)。

```python
print(f"Client ID: {client.client_id}")
print(f"Target ID: {client.target_id}")
```

### `client.not_registered` / `client.not_bind`

**属性** - 连接状态 (DG-Lab 兼容)。

```python
# BLE 模式下 not_registered 始终为 False
# not_bind 等同于 not connected
if not client.not_bind:
    print("已绑定")
```

### `client.bind()` / `client.rebind()` / `client.ensure_bind()`

DG-Lab 兼容方法，BLE 模式下连接即绑定。

```python
ret = await client.bind()
if ret == RetCode.SUCCESS:
    print("绑定成功")
```

---

## 役次元扩展接口

以下接口为役次元设备特有功能。

### `client.get_battery()`

获取电池电量。

```python
battery = await client.get_battery()
print(f"电量: {battery}%")
```

**返回:**
- `int`: 电量百分比 (0-100)，失败返回 -1

### `client.set_motor()`

控制马达。

```python
from pydglab_ws.ble import MotorState

# 开启马达
await client.set_motor(MotorState.ON)

# 关闭马达
await client.set_motor(MotorState.OFF)

# 预设频率
await client.set_motor(MotorState.PRESET_1)
await client.set_motor(MotorState.PRESET_2)
await client.set_motor(MotorState.PRESET_3)
```

**参数:**
- `state` (MotorState): 马达状态

**返回:**
- `bool`: 是否成功

### `client.set_mode()`

设置通道模式 (16 种预设模式)。

```python
from pydglab_ws import Channel
from pydglab_ws.ble import YCYMode

await client.set_mode(Channel.A, YCYMode.PRESET_1)
await client.set_mode(Channel.B, YCYMode.PRESET_10)
```

**参数:**
- `channel` (Channel): 通道选择
- `mode` (YCYMode): 模式 (PRESET_1 ~ PRESET_16)

**返回:**
- `bool`: 是否成功

### `client.set_custom_wave()`

设置自定义波形。

```python
from pydglab_ws import Channel

# 设置频率 50Hz, 脉冲宽度 50us
await client.set_custom_wave(Channel.A, frequency=50, pulse_width=50)
```

**参数:**
- `channel` (Channel): 通道选择
- `frequency` (int): 频率 (1-100 Hz)
- `pulse_width` (int): 脉冲宽度 (0-100 us)

**返回:**
- `bool`: 是否成功

**说明:**
- 自定义波形为单次触发，需持续发送以维持输出

### `client.set_ycy_strength()`

直接设置役次元原生强度。

```python
from pydglab_ws import Channel
from pydglab_ws.ble import YCYMode

# 设置强度 30，自定义模式，频率 50，脉冲 50
await client.set_ycy_strength(
    channel=Channel.A,
    strength=30,
    mode=YCYMode.CUSTOM,
    frequency=50,
    pulse_width=50
)
```

**参数:**
- `channel` (Channel): 通道选择
- `strength` (int): 强度 (1-276)
- `mode` (YCYMode): 模式，默认 CUSTOM
- `frequency` (int): 频率 (自定义模式)，默认 50
- `pulse_width` (int): 脉冲宽度 (自定义模式)，默认 50

**返回:**
- `bool`: 是否成功

### `client.get_electrode_status()`

获取电极连接状态。

```python
from pydglab_ws import Channel
from pydglab_ws.ble import ElectrodeStatus

status = await client.get_electrode_status(Channel.A)
if status == ElectrodeStatus.CONNECTED_ACTIVE:
    print("电极已连接，正在放电")
elif status == ElectrodeStatus.CONNECTED_INACTIVE:
    print("电极已连接，未放电")
else:
    print("电极未连接")
```

**参数:**
- `channel` (Channel): 通道选择

**返回:**
- `ElectrodeStatus`: 电极状态

### `client.get_channel_status()`

获取通道完整状态。

```python
from pydglab_ws import Channel

status = await client.get_channel_status(Channel.A)
if status:
    print(f"电极: {status.electrode_status}")
    print(f"开启: {status.enabled}")
    print(f"强度: {status.strength}")
    print(f"模式: {status.mode}")
```

**参数:**
- `channel` (Channel): 通道选择

**返回:**
- `YCYChannelStatus | None`: 通道状态对象

### `client.stop_channel()`

停止单个通道输出。

```python
from pydglab_ws import Channel

await client.stop_channel(Channel.A)
```

**参数:**
- `channel` (Channel): 通道选择

**返回:**
- `bool`: 是否成功

### `client.stop_all()`

停止所有输出 (双通道 + 马达)。

```python
await client.stop_all()
```

**返回:**
- `bool`: 是否成功

---

## 枚举类型

### `Channel`

通道选择。

```python
from pydglab_ws import Channel

Channel.A  # A 通道
Channel.B  # B 通道
```

### `StrengthOperationType`

强度操作类型。

```python
from pydglab_ws import StrengthOperationType

StrengthOperationType.SET_TO    # 设置为指定值
StrengthOperationType.INCREASE  # 增加
StrengthOperationType.DECREASE  # 减少
```

### `YCYMode`

役次元模式。

```python
from pydglab_ws.ble import YCYMode

YCYMode.OFF        # 关闭 (仅用于状态查询)
YCYMode.PRESET_1   # 预设模式 1
# ...
YCYMode.PRESET_16  # 预设模式 16
YCYMode.CUSTOM     # 自定义模式
```

### `MotorState`

马达状态。

```python
from pydglab_ws.ble import MotorState

MotorState.OFF       # 关闭
MotorState.ON        # 开启
MotorState.PRESET_1  # 预设频率 1
MotorState.PRESET_2  # 预设频率 2
MotorState.PRESET_3  # 预设频率 3
```

### `ElectrodeStatus`

电极连接状态。

```python
from pydglab_ws.ble import ElectrodeStatus

ElectrodeStatus.NOT_CONNECTED      # 未连接
ElectrodeStatus.CONNECTED_ACTIVE   # 已连接，正在放电
ElectrodeStatus.CONNECTED_INACTIVE # 已连接，未放电
```
