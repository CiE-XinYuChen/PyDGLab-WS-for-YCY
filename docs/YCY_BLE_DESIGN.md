# 役次元 (YCY) 蓝牙客户端设计文档

> **状态**: ✅ 已完成 | **版本**: 1.0 | **最后更新**: 2025-01

## 1. 项目目标

基于现有的 PyDGLab-WS 项目架构，实现役次元设备的蓝牙直连功能，提供与 DG-Lab API 兼容的接口层。

### 1.1 预期效果

```python
# 现有 DG-Lab WebSocket 方式
async with DGLabWSConnect("ws://192.168.1.161:5678") as client:
    await client.set_strength(Channel.A, StrengthOperationType.SET_TO, 50)

# 新增 役次元蓝牙直连方式 (API 保持一致)
async with YCYBLEClient("YCY-XXXXX") as client:
    await client.set_strength(Channel.A, StrengthOperationType.SET_TO, 50)
```

---

## 2. 协议对比分析

### 2.1 通信方式对比

| 特性 | DG-Lab | 役次元 |
|------|--------|--------|
| 传输协议 | WebSocket | BLE (Bluetooth Low Energy) |
| 数据格式 | JSON 文本 | 二进制字节流 |
| 连接方式 | 通过 App 中转 | 直连设备 |
| 服务发现 | 二维码扫描 | BLE UUID 扫描 |

### 2.2 设备参数对比

| 参数 | DG-Lab | 役次元 | 映射难度 |
|------|--------|--------|----------|
| 通道数 | 2 (A/B) | 2 (A/B) | 直接映射 |
| 强度范围 | 0-200 | 1-276 | 需线性映射 |
| 强度上限 | 动态 (App设置) | 固定 276 | 需模拟 |
| 通道开关 | 隐式 (强度=0) | 显式 (0x00/0x01) | 需转换 |

### 2.3 波形/模式对比

#### DG-Lab 波形系统
```
每条波形数据 = 100ms
格式: ((freq1,freq2,freq3,freq4), (str1,str2,str3,str4))
- 频率: 10-240 (每25ms一个值)
- 强度: 0-100 (百分比，每25ms一个值)
- 队列: 最多500条 (50秒)
```

#### 役次元模式系统
```
固定模式: 0x01-0x10 (16种预设体感)
自定义模式: 0x11
- 频率: 1-100 Hz
- 脉冲时间: 0-100 us
- 下发间隔: 最快100ms一次
```

#### 波形兼容性分析

| DG-Lab 特性 | 役次元支持 | 兼容方案 |
|-------------|-----------|----------|
| 动态频率变化 | 部分支持 | 取平均值或首值 |
| 动态强度变化 | 不支持 | 取平均值或忽略 |
| 波形队列 | 不支持 | 软件模拟队列 |
| 100ms精度 | 支持 | 直接对应 |

### 2.4 额外功能对比

| 功能 | DG-Lab | 役次元 |
|------|--------|--------|
| 反馈按钮 | 支持 (10个) | 不支持 |
| 电池电量 | 不支持 | 支持 |
| 马达控制 | 不支持 | 支持 |
| 计步功能 | 不支持 | 支持 |
| 陀螺仪 | 不支持 | 支持 |
| 电极连接检测 | 不支持 | 支持 |

---

## 3. 役次元 BLE 协议详解

### 3.1 BLE 服务特征

```
服务 UUID: 0000ff30-0000-1000-8000-00805f9b34fb
├── FF31 (Write Without Response) - 主机→从机
└── FF32 (Notify) - 从机→主机
```

### 3.2 数据包通用格式

```
┌────────┬────────┬────────────┬────────┐
│ 包头   │ 命令字  │ 数据...    │ 校验和 │
│ 0x35   │ 0xXX   │ ...        │ SUM    │
└────────┴────────┴────────────┴────────┘

校验和 = (包头 + 命令字 + 所有数据字节) & 0xFF
```

### 3.3 命令列表

| 命令字 | 名称 | 方向 | 长度 |
|--------|------|------|------|
| 0x11 | 通道控制 | 主→从 | 10字节 |
| 0x12 | 马达控制 | 主→从 | 4字节 |
| 0x13 | 计步控制 | 主→从 | 4字节 |
| 0x14 | 角度控制 | 主→从 | 4字节 |
| 0x71 | 查询/应答 | 双向 | 变长 |

### 3.4 通道控制命令 (0x11) 详解

```
字节:  1     2     3      4      5-6     7      8      9      10
     ┌─────┬─────┬──────┬──────┬───────┬──────┬──────┬──────┬─────┐
     │0x35 │0x11 │通道号│开关  │ 强度  │ 模式 │ 频率 │脉冲  │校验 │
     └─────┴─────┴──────┴──────┴───────┴──────┴──────┴──────┴─────┘

通道号: 0x01=A, 0x02=B, 0x03=AB同时
开关:   0x00=关闭, 0x01=开启
强度:   0x0001-0x0114 (1-276), 大端序
模式:   0x01-0x10=预设, 0x11=自定义
频率:   0x01-0x64 (1-100Hz), 仅自定义模式有效
脉冲:   0x00-0x64 (0-100us), 仅自定义模式有效
```

### 3.5 查询应答命令 (0x71) 详解

#### 查询请求
```
字节:  1     2     3      4
     ┌─────┬─────┬──────┬─────┐
     │0x35 │0x71 │类型  │校验 │
     └─────┴─────┴──────┴─────┘

类型: 0x01=A通道, 0x02=B通道, 0x03=马达, 0x04=电量, 0x05=计步, 0x06=角度
```

#### 通道状态应答
```
字节:  1     2     3      4      5      6-7     8      9
     ┌─────┬─────┬──────┬──────┬──────┬───────┬──────┬─────┐
     │0x35 │0x71 │类型  │连接  │开关  │ 强度  │ 模式 │校验 │
     └─────┴─────┴──────┴──────┴──────┴───────┴──────┴─────┘

连接状态: 0x00=未接入, 0x01=已接入在放电, 0x02=已接入未放电
```

#### 电池电量应答
```
字节:  1     2     3      4      5
     ┌─────┬─────┬──────┬──────┬─────┐
     │0x35 │0x71 │0x04  │电量  │校验 │
     └─────┴─────┴──────┴──────┴─────┘

电量: 0x00-0x64 (0%-100%)
```

#### 异常上报
```
字节:  1     2     3      4      5
     ┌─────┬─────┬──────┬──────┬─────┐
     │0x35 │0x71 │0x55  │错误码│校验 │
     └─────┴─────┴──────┴──────┴─────┘

错误码: 0x01=校验错误, 0x02=包头错误, 0x03=命令错误, 0x04=数据错误, 0x05=未实现
```

---

## 4. 架构设计

### 4.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         应用层                                   │
│                   (用户代码 / 上层应用)                           │
└─────────────────────────────────────────────────────────────────┘
                                │
                ┌───────────────┴───────────────┐
                ▼                               ▼
┌───────────────────────────┐   ┌───────────────────────────────┐
│      DGLabClient          │   │        YCYBLEClient           │
│   (现有 WebSocket 客户端)  │   │      (新增 BLE 客户端)         │
│                           │   │                               │
│  - DGLabWSClient          │   │  - 实现相同的基础接口          │
│  - DGLabLocalClient       │   │  - 强度/波形映射转换           │
└───────────────────────────┘   │  - 扩展役次元特有功能          │
                                └───────────────────────────────┘
                                                │
                                                ▼
                                ┌───────────────────────────────┐
                                │       YCYBLEProtocol          │
                                │      (BLE 协议编解码)          │
                                │                               │
                                │  - 数据包构建/解析             │
                                │  - 校验和计算                  │
                                │  - 命令编码/解码               │
                                └───────────────────────────────┘
                                                │
                                                ▼
                                ┌───────────────────────────────┐
                                │        BLE 传输层             │
                                │        (bleak 库)             │
                                │                               │
                                │  - 设备扫描                    │
                                │  - 连接管理                    │
                                │  - 特征读写                    │
                                └───────────────────────────────┘
```

### 4.2 模块结构

```
pydglab_ws/
├── __init__.py
├── enums.py                    # 现有枚举 (Channel, StrengthOperationType 等)
├── models.py                   # 现有模型
├── exceptions.py               # 现有异常
├── typing.py                   # 现有类型定义
├── utils.py                    # 现有工具函数
│
├── client/
│   ├── __init__.py
│   ├── base.py                 # 现有: DGLabClient 基类
│   ├── ws.py                   # 现有: WebSocket 客户端
│   ├── local.py                # 现有: 本地客户端
│   └── ble.py                  # 新增: YCYBLEClient
│
├── server/
│   └── server.py               # 现有: WebSocket 服务端
│
└── ble/                        # 新增: BLE 相关模块
    ├── __init__.py
    ├── enums.py                # 役次元特有枚举
    ├── models.py               # 役次元数据模型
    ├── protocol.py             # 协议编解码
    ├── scanner.py              # 设备扫描
    └── exceptions.py           # BLE 相关异常
```

### 4.3 类设计

#### 4.3.1 YCYBLEClient (兼容层)

```python
class YCYBLEClient:
    """役次元蓝牙客户端 - DG-Lab API 兼容接口"""

    # === DG-Lab 兼容接口 ===
    async def set_strength(self, channel: Channel, operation: StrengthOperationType, value: int) -> bool
    async def add_pulses(self, channel: Channel, *pulses: PulseOperation) -> bool
    async def clear_pulses(self, channel: Channel) -> bool
    async def data_generator(self) -> AsyncGenerator[StrengthData | FeedbackButton, None]

    # === 役次元扩展接口 ===
    async def set_mode(self, channel: Channel, mode: YCYMode) -> bool
    async def set_custom_wave(self, channel: Channel, frequency: int, pulse_width: int) -> bool
    async def get_battery(self) -> int
    async def set_motor(self, state: MotorState) -> bool
    async def get_electrode_status(self, channel: Channel) -> ElectrodeStatus
```

#### 4.3.2 YCYBLEProtocol (协议层)

```python
class YCYBLEProtocol:
    """役次元 BLE 协议编解码"""

    @staticmethod
    def build_channel_control(channel, enabled, strength, mode, frequency, pulse_width) -> bytes

    @staticmethod
    def build_query(query_type: QueryType) -> bytes

    @staticmethod
    def parse_response(data: bytes) -> YCYResponse

    @staticmethod
    def calculate_checksum(data: bytes) -> int
```

---

## 5. 关键设计决策

### 5.1 强度映射策略

**问题**: DG-Lab 强度范围 0-200，役次元范围 1-276，如何映射？

**方案选项**:

| 方案 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| A: 线性映射 | `ycy = dglab * 276 / 200` | 简单直接 | 0 无法表示 |
| B: 偏移映射 | `ycy = dglab * 275 / 200 + 1` | 覆盖全范围 | 0需特殊处理 |
| C: 分段映射 | 0→关闭, 1-200→1-276 | 语义清晰 | 略复杂 |

**建议方案**: C (分段映射)
```python
def map_strength_to_ycy(dglab_strength: int) -> tuple[bool, int]:
    """
    返回 (是否开启, 役次元强度值)
    """
    if dglab_strength == 0:
        return (False, 1)  # 关闭通道
    else:
        # 1-200 映射到 1-276
        ycy_strength = int(dglab_strength * 275 / 200) + 1
        return (True, min(ycy_strength, 276))
```

### 5.2 波形转换策略

**问题**: DG-Lab 复杂波形无法完全映射到役次元的简单自定义模式

**DG-Lab 波形特点**:
- 每100ms可以有4个不同的频率值和强度值
- 支持波形队列，最多500条

**役次元自定义模式特点**:
- 只有单一频率和脉冲宽度
- 无队列概念，需持续下发

**方案选项**:

| 方案 | 描述 | 兼容度 | 复杂度 |
|------|------|--------|--------|
| A: 简化转换 | 取频率平均值，忽略强度变化 | 低 | 低 |
| B: 软件模拟 | 在客户端维护队列，定时下发 | 中 | 中 |
| C: 预设映射 | 将常见波形映射到预设模式 | 低 | 低 |
| D: 混合方案 | B+C，优先匹配预设 | 中 | 高 |

**建议方案**: B (软件模拟队列)
```python
class WaveformQueue:
    """软件模拟波形队列"""

    def __init__(self):
        self._queue: asyncio.Queue[WaveformItem] = asyncio.Queue(maxsize=500)
        self._running = False

    async def add(self, *pulses: PulseOperation):
        for pulse in pulses:
            # 转换 DG-Lab 波形为役次元参数
            freq = self._convert_frequency(pulse)
            await self._queue.put(WaveformItem(freq, 100))  # 100ms

    async def _playback_loop(self, client: YCYBLEClient):
        """每100ms下发一次波形"""
        while self._running:
            item = await self._queue.get()
            await client.set_custom_wave(item.frequency, item.pulse_width)
            await asyncio.sleep(0.1)
```

### 5.3 通道强度上限处理

**问题**: DG-Lab 有动态的强度上限 (a_limit, b_limit)，役次元没有

**方案选项**:

| 方案 | 描述 |
|------|------|
| A: 忽略上限 | 直接使用 276 作为固定上限 |
| B: 软件限制 | 在客户端维护虚拟上限，限制输出 |
| C: 配置项 | 允许用户配置最大强度 |

**建议方案**: B + C
```python
class YCYBLEClient:
    def __init__(self, ..., strength_limit: int = 200):
        self._strength_limit = strength_limit  # 用户可配置

    @property
    def strength_data(self) -> StrengthData:
        return StrengthData(
            a=self._current_a,
            b=self._current_b,
            a_limit=self._strength_limit,  # 虚拟上限
            b_limit=self._strength_limit
        )
```

### 5.4 反馈按钮兼容

**问题**: DG-Lab 有10个反馈按钮，役次元没有

**方案选项**:

| 方案 | 描述 |
|------|------|
| A: 不支持 | `data_generator` 永远不会产生 `FeedbackButton` |
| B: 模拟触发 | 提供手动触发反馈的方法 |
| C: 事件映射 | 将役次元的某些事件映射为反馈 |

**建议方案**: A (不支持，明确文档说明)

### 5.5 连接管理策略

**问题**: BLE 连接不如 WebSocket 稳定，需要处理断连重连

**方案**:
```python
class YCYBLEClient:
    def __init__(self, ..., auto_reconnect: bool = True, reconnect_interval: float = 5.0):
        self._auto_reconnect = auto_reconnect
        self._reconnect_interval = reconnect_interval

    async def _connection_watchdog(self):
        """连接监控协程"""
        while self._auto_reconnect:
            if not self._connected:
                try:
                    await self._connect()
                except BLEConnectionError:
                    await asyncio.sleep(self._reconnect_interval)
```

---

## 6. 设计决策 (已确认)

### 6.1 强度映射
**决策**: 分段映射，无需自定义映射函数

```python
def map_strength_to_ycy(dglab_strength: int) -> tuple[bool, int]:
    """DG-Lab 强度 → 役次元 (开关状态, 强度值)"""
    if dglab_strength == 0:
        return (False, 1)  # 关闭通道
    else:
        ycy_strength = int(dglab_strength * 275 / 200) + 1
        return (True, min(ycy_strength, 276))

def map_strength_to_dglab(ycy_strength: int) -> int:
    """役次元强度 → DG-Lab 强度"""
    return int((ycy_strength - 1) * 200 / 275)
```

### 6.2 波形兼容
**决策**: 软件模拟队列 + 强度百分比映射到脉冲宽度

```python
def convert_pulse(pulse: PulseOperation) -> tuple[int, int]:
    """DG-Lab 波形 → 役次元自定义模式 (频率, 脉冲宽度)"""
    # 频率: 4个值取平均，clamp 到 1-100
    freq = sum(pulse[0]) // 4
    freq = max(1, min(100, freq))

    # 强度百分比: 4个值取平均 → 脉冲宽度 0-100us
    pulse_width = sum(pulse[1]) // 4

    return (freq, pulse_width)
```

### 6.3 API 设计
**决策**: 严格兼容 DGLabClient 接口 + 役次元扩展方法

```python
class YCYBLEClient:
    # === DG-Lab 兼容属性 ===
    client_id: UUID4           # 终端 ID (基于设备地址生成)
    target_id: UUID4           # 设备 ID (基于设备地址生成)
    strength_data: StrengthData  # 当前强度数据
    not_registered: bool       # 始终为 False
    not_bind: bool             # 连接时为 False

    # === DG-Lab 兼容方法 ===
    async def set_strength(self, channel, operation, value) -> bool
    async def add_pulses(self, channel, *pulses) -> bool
    async def clear_pulses(self, channel) -> bool
    async def data_generator(self) -> AsyncGenerator[StrengthData, None]
    async def recv_data(self) -> Union[StrengthData, RetCode]
    async def bind(self) -> RetCode
    async def rebind(self) -> RetCode
    async def ensure_bind(self)
    def get_qrcode(self, uri) -> None

    # === 役次元扩展接口 ===
    async def get_battery(self) -> int
    async def set_motor(self, state: MotorState) -> bool
    async def get_electrode_status(self, channel) -> ElectrodeStatus
    async def set_mode(self, channel, mode: YCYMode) -> bool
    async def set_custom_wave(self, channel, frequency, pulse_width) -> bool
```

### 6.4 BLE 依赖
**决策**: 使用 `bleak` 库

- 支持平台: Windows / macOS / Linux
- Android 支持: 后续考虑
- 安装方式: `pip install pydglab-ws[ble]`

### 6.5 设备发现
**决策**: UUID 过滤扫描，无需保存已配对设备

```python
SERVICE_UUID = "0000ff30-0000-1000-8000-00805f9b34fb"

async def scan(self, timeout: float = 5.0) -> List[YCYDevice]:
    devices = await BleakScanner.discover(timeout=timeout)
    return [d for d in devices if SERVICE_UUID in d.metadata.get("uuids", [])]
```

### 6.6 错误处理
**决策**:
- BLE 断连: 抛出 `DisconnectedError` 异常
- 命令发送失败: 返回 `False` (与 DGLabClient 行为一致)

```python
async def set_strength(...) -> bool:
    if not self._connected:
        raise DisconnectedError("BLE device disconnected")
    try:
        await self._send_command(...)
        return True
    except BLEError:
        return False
```

### 6.7 包组织
**决策**: 作为子包 `pydglab_ws/ble/`，通过可选依赖安装

```
pydglab_ws/
├── ble/
│   ├── __init__.py
│   ├── protocol.py
│   ├── enums.py
│   ├── models.py
│   └── exceptions.py
├── client/
│   ├── ble.py          # YCYBLEClient
│   └── ...
└── ...
```

### 6.8 测试策略
**决策**: 4层测试，有硬件配合完整验证

| 层级 | 内容 | CI 运行 | 硬件需求 |
|------|------|---------|---------|
| L1 | 协议编解码、映射函数 | ✅ 自动 | 无 |
| L2 | Mock BLE + 客户端逻辑 | ✅ 自动 | 无 |
| L3 | BLE 模拟器端到端 | 手动触发 | 无 |
| L4 | 真实设备测试 | 手动 | ✅ 需要 |

---

## 7. 实现计划

### Phase 1: 基础框架 ✅
- [x] 创建 `ble/` 模块结构
- [x] 实现 `YCYBLEProtocol` 协议编解码
- [x] 实现基础的 BLE 连接管理

### Phase 2: 核心功能 ✅
- [x] 实现通道控制 (开关、强度、模式)
- [x] 实现状态查询和通知监听
- [x] 实现强度映射转换

### Phase 3: 兼容层 ✅
- [x] 实现 `YCYBLEClient` DG-Lab 兼容接口
- [x] 实现波形队列模拟
- [x] 实现 `data_generator` 异步生成器

### Phase 4: 扩展功能 ✅
- [x] 实现电池电量查询
- [x] 实现马达控制
- [x] 实现电极连接检测

### Phase 5: 完善 ✅
- [x] 编写单元测试 (67 个测试用例)
- [x] 编写使用文档
- [x] 硬件测试验证

---

## 8. 测试策略

### 8.1 测试分层

```
┌─────────────────────────────────────────────────────────────────┐
│                    Level 4: 硬件集成测试                         │
│                 (真实役次元设备，手动/半自动)                      │
└─────────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────┐
│                    Level 3: 端到端测试                           │
│              (BLE 模拟器，完整业务流程验证)                        │
└─────────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────┐
│                    Level 2: 集成测试                             │
│              (Mock BLE 层，客户端逻辑验证)                        │
└─────────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────┐
│                    Level 1: 单元测试                             │
│           (纯函数测试，协议编解码，映射转换)                        │
└─────────────────────────────────────────────────────────────────┘
```

### 8.2 Level 1: 单元测试 (无需硬件)

#### 8.2.1 协议编解码测试

```python
# tests/ble/test_protocol.py

class TestYCYProtocol:
    """协议编解码测试"""

    @pytest.mark.parametrize("data,expected_checksum", [
        (bytes([0x35, 0x11, 0x01, 0x01, 0x00, 0x50, 0x01, 0x00, 0x00]), 0x99),
        (bytes([0x35, 0x71, 0x01]), 0xA7),
    ])
    def test_checksum_calculation(self, data, expected_checksum):
        """校验和计算测试"""
        assert YCYBLEProtocol.calculate_checksum(data) == expected_checksum

    @pytest.mark.parametrize("channel,enabled,strength,mode,freq,pulse,expected", [
        # A通道开启，强度100，预设模式1
        (YCYChannel.A, True, 100, YCYMode.PRESET_1, 0, 0,
         bytes([0x35, 0x11, 0x01, 0x01, 0x00, 0x64, 0x01, 0x00, 0x00, 0xA7])),
        # B通道关闭
        (YCYChannel.B, False, 0, YCYMode.PRESET_1, 0, 0,
         bytes([0x35, 0x11, 0x02, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x49])),
        # AB通道，自定义模式，频率50Hz，脉冲50us
        (YCYChannel.AB, True, 200, YCYMode.CUSTOM, 50, 50,
         bytes([0x35, 0x11, 0x03, 0x01, 0x00, 0xC8, 0x11, 0x32, 0x32, 0x87])),
    ])
    def test_build_channel_control(self, channel, enabled, strength, mode, freq, pulse, expected):
        """通道控制命令构建测试"""
        result = YCYBLEProtocol.build_channel_control(
            channel, enabled, strength, mode, freq, pulse
        )
        assert result == expected

    @pytest.mark.parametrize("data,expected_type,expected_values", [
        # 通道A状态应答
        (bytes([0x35, 0x71, 0x01, 0x01, 0x01, 0x00, 0x64, 0x01, 0xCE]),
         YCYResponseType.CHANNEL_A_STATUS,
         {"connected": True, "enabled": True, "strength": 100, "mode": 1}),
        # 电池电量应答
        (bytes([0x35, 0x71, 0x04, 0x50, 0xFA]),
         YCYResponseType.BATTERY,
         {"battery": 80}),
        # 异常上报
        (bytes([0x35, 0x71, 0x55, 0x01, 0xFC]),
         YCYResponseType.ERROR,
         {"error_code": YCYError.CHECKSUM_ERROR}),
    ])
    def test_parse_response(self, data, expected_type, expected_values):
        """响应解析测试"""
        response = YCYBLEProtocol.parse_response(data)
        assert response.type == expected_type
        for key, value in expected_values.items():
            assert getattr(response, key) == value
```

#### 8.2.2 强度映射测试

```python
# tests/ble/test_mapping.py

class TestStrengthMapping:
    """强度映射转换测试"""

    @pytest.mark.parametrize("dglab_strength,expected_enabled,expected_ycy", [
        (0, False, 1),      # 0 → 关闭
        (1, True, 2),       # 1 → 开启，最低强度
        (100, True, 138),   # 中间值
        (200, True, 276),   # 最大值
    ])
    def test_dglab_to_ycy_strength(self, dglab_strength, expected_enabled, expected_ycy):
        """DG-Lab → 役次元强度映射"""
        enabled, ycy_strength = map_strength_to_ycy(dglab_strength)
        assert enabled == expected_enabled
        assert ycy_strength == expected_ycy

    @pytest.mark.parametrize("ycy_strength,expected_dglab", [
        (1, 0),
        (138, 100),
        (276, 200),
    ])
    def test_ycy_to_dglab_strength(self, ycy_strength, expected_dglab):
        """役次元 → DG-Lab 强度映射"""
        dglab_strength = map_strength_to_dglab(ycy_strength)
        assert dglab_strength == expected_dglab
```

#### 8.2.3 波形转换测试

```python
# tests/ble/test_waveform.py

class TestWaveformConversion:
    """波形转换测试"""

    @pytest.mark.parametrize("pulse,expected_freq", [
        # 频率取平均值
        (((10, 20, 30, 40), (100, 100, 100, 100)), 25),
        (((100, 100, 100, 100), (50, 50, 50, 50)), 100),
    ])
    def test_pulse_to_frequency(self, pulse, expected_freq):
        """DG-Lab 波形 → 役次元频率"""
        freq = convert_pulse_to_frequency(pulse)
        assert freq == expected_freq
```

### 8.3 Level 2: 集成测试 (Mock BLE)

#### 8.3.1 BLE Mock 设计

```python
# tests/ble/mock_ble.py

class MockBLEDevice:
    """模拟役次元 BLE 设备"""

    def __init__(self):
        self.connected = False
        self.channel_a = ChannelState()
        self.channel_b = ChannelState()
        self.battery = 100
        self._notifications: asyncio.Queue = asyncio.Queue()
        self._received_commands: List[bytes] = []

    async def connect(self):
        self.connected = True

    async def disconnect(self):
        self.connected = False

    async def write_characteristic(self, uuid: str, data: bytes):
        """模拟写入特征"""
        if uuid != "ff31":
            raise BLEError("Invalid characteristic")

        self._received_commands.append(data)

        # 解析命令并更新状态
        if data[1] == 0x11:  # 通道控制
            self._handle_channel_control(data)
        elif data[1] == 0x71:  # 查询
            response = self._build_query_response(data[2])
            await self._notifications.put(response)

    async def start_notify(self, uuid: str, callback):
        """模拟开始通知"""
        if uuid != "ff32":
            raise BLEError("Invalid characteristic")

        asyncio.create_task(self._notification_loop(callback))

    async def _notification_loop(self, callback):
        while self.connected:
            try:
                data = await asyncio.wait_for(
                    self._notifications.get(),
                    timeout=0.1
                )
                await callback(data)
            except asyncio.TimeoutError:
                continue

    def _handle_channel_control(self, data: bytes):
        """处理通道控制命令"""
        channel = data[2]
        enabled = data[3] == 0x01
        strength = (data[4] << 8) | data[5]
        mode = data[6]

        if channel in (0x01, 0x03):
            self.channel_a.enabled = enabled
            self.channel_a.strength = strength
            self.channel_a.mode = mode
        if channel in (0x02, 0x03):
            self.channel_b.enabled = enabled
            self.channel_b.strength = strength
            self.channel_b.mode = mode


class MockBLEScanner:
    """模拟 BLE 扫描器"""

    def __init__(self, devices: List[MockBLEDevice] = None):
        self.devices = devices or []

    async def discover(self, timeout: float = 5.0) -> List[MockBLEDevice]:
        return self.devices
```

#### 8.3.2 客户端集成测试

```python
# tests/ble/test_client_integration.py

@pytest.fixture
def mock_device():
    return MockBLEDevice()

@pytest.fixture
def mock_scanner(mock_device):
    return MockBLEScanner([mock_device])

class TestYCYBLEClientIntegration:
    """YCYBLEClient 集成测试"""

    @pytest.mark.asyncio
    async def test_connect_and_disconnect(self, mock_device, mock_scanner):
        """连接和断开测试"""
        client = YCYBLEClient(scanner=mock_scanner)
        await client.connect()
        assert mock_device.connected is True

        await client.disconnect()
        assert mock_device.connected is False

    @pytest.mark.asyncio
    async def test_set_strength_dglab_compatible(self, mock_device, mock_scanner):
        """DG-Lab 兼容接口 - 设置强度"""
        client = YCYBLEClient(scanner=mock_scanner)
        await client.connect()

        # 使用 DG-Lab 风格 API
        await client.set_strength(Channel.A, StrengthOperationType.SET_TO, 100)

        # 验证设备状态
        assert mock_device.channel_a.enabled is True
        assert mock_device.channel_a.strength == 138  # 100 * 275/200 + 1

    @pytest.mark.asyncio
    async def test_data_generator(self, mock_device, mock_scanner):
        """数据生成器测试"""
        client = YCYBLEClient(scanner=mock_scanner)
        await client.connect()

        # 模拟设备发送状态更新
        mock_device._notifications.put_nowait(
            bytes([0x35, 0x71, 0x01, 0x01, 0x01, 0x00, 0x64, 0x01, 0xCE])
        )

        async for data in client.data_generator(StrengthData):
            assert isinstance(data, StrengthData)
            assert data.a == 73  # 100 * 200/275
            break
```

### 8.4 Level 3: 端到端测试 (BLE 模拟器)

#### 8.4.1 使用 BLE 模拟器

对于更真实的端到端测试，可以使用软件 BLE 模拟器：

**Linux (使用 BlueZ)**:
```bash
# 创建虚拟 HCI 设备
sudo hciattach /dev/null any

# 使用 btvirt 创建虚拟蓝牙适配器
sudo btvirt -l2
```

**macOS/Windows**: 需要使用 BLE dongle + 专用固件

#### 8.4.2 端到端测试用例

```python
# tests/ble/test_e2e.py

@pytest.mark.e2e
@pytest.mark.skipif(not BLE_SIMULATOR_AVAILABLE, reason="BLE simulator not available")
class TestE2E:
    """端到端测试 (需要 BLE 模拟器)"""

    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """完整工作流程测试"""
        # 1. 扫描设备
        client = YCYBLEClient()
        devices = await client.scan(timeout=5.0)
        assert len(devices) > 0

        # 2. 连接设备
        await client.connect(devices[0])
        assert client.connected

        # 3. 获取初始状态
        battery = await client.get_battery()
        assert 0 <= battery <= 100

        # 4. 设置强度
        await client.set_strength(Channel.A, StrengthOperationType.SET_TO, 50)
        await asyncio.sleep(0.5)

        # 5. 验证状态
        status = await client.get_channel_status(Channel.A)
        assert status.enabled is True

        # 6. 清理
        await client.set_strength(Channel.A, StrengthOperationType.SET_TO, 0)
        await client.disconnect()
```

### 8.5 Level 4: 硬件测试 (真实设备)

#### 8.5.1 手动测试清单

```markdown
## 硬件测试检查清单

### 连接测试
- [ ] 设备扫描能发现役次元设备
- [ ] 能成功连接设备
- [ ] 断开连接后能重新连接
- [ ] 设备关机后客户端能检测到断连

### 通道控制测试
- [ ] A 通道开启/关闭正常
- [ ] B 通道开启/关闭正常
- [ ] AB 通道同时控制正常
- [ ] 强度 1-276 全范围可调
- [ ] 16 种预设模式可切换
- [ ] 自定义模式频率可调 (1-100Hz)
- [ ] 自定义模式脉冲宽度可调 (0-100us)

### 状态查询测试
- [ ] 通道状态查询正常
- [ ] 电池电量查询正常
- [ ] 电极连接检测正常

### DG-Lab 兼容性测试
- [ ] set_strength() 强度映射正确
- [ ] add_pulses() 波形转换正常
- [ ] clear_pulses() 执行正常
- [ ] data_generator() 能接收状态更新

### 边界测试
- [ ] 强度值 0 (关闭通道)
- [ ] 强度值 276 (最大)
- [ ] 频率值 1Hz (最低)
- [ ] 频率值 100Hz (最高)
- [ ] 快速连续发送命令 (100ms 间隔)
```

#### 8.5.2 自动化硬件测试脚本

```python
# tests/ble/test_hardware.py

@pytest.mark.hardware
@pytest.mark.skipif(not HARDWARE_TEST_ENABLED, reason="Hardware test disabled")
class TestHardware:
    """硬件测试 (需要真实设备)"""

    @pytest.fixture
    async def real_client(self):
        """连接真实设备"""
        client = YCYBLEClient()
        devices = await client.scan(timeout=10.0, name_prefix="YCY")
        if not devices:
            pytest.skip("No YCY device found")
        await client.connect(devices[0])
        yield client
        await client.disconnect()

    @pytest.mark.asyncio
    async def test_strength_range(self, real_client):
        """强度范围测试"""
        for strength in [1, 50, 100, 150, 200, 276]:
            await real_client.set_ycy_strength(Channel.A, strength)
            await asyncio.sleep(0.2)
            status = await real_client.get_channel_status(Channel.A)
            assert status.strength == strength

    @pytest.mark.asyncio
    async def test_mode_switch(self, real_client):
        """模式切换测试"""
        for mode in range(1, 17):  # 16种预设模式
            await real_client.set_mode(Channel.A, YCYMode(mode))
            await asyncio.sleep(0.2)
            status = await real_client.get_channel_status(Channel.A)
            assert status.mode == mode
```

### 8.6 CI/CD 配置

#### 8.6.1 GitHub Actions 配置

```yaml
# .github/workflows/test-ble.yml

name: BLE Module Tests

on:
  push:
    paths:
      - 'pydglab_ws/ble/**'
      - 'pydglab_ws/client/ble.py'
      - 'tests/ble/**'
  pull_request:
    paths:
      - 'pydglab_ws/ble/**'
      - 'pydglab_ws/client/ble.py'
      - 'tests/ble/**'

jobs:
  unit-tests:
    name: Unit Tests (No Hardware)
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.9', '3.10', '3.11', '3.12']

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          pip install -e ".[dev,ble]"

      - name: Run unit tests
        run: |
          pytest tests/ble/test_protocol.py tests/ble/test_mapping.py tests/ble/test_waveform.py -v --cov=pydglab_ws.ble --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          files: ./coverage.xml
          flags: ble-unit

  integration-tests:
    name: Integration Tests (Mock BLE)
    runs-on: ubuntu-latest
    needs: unit-tests

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -e ".[dev,ble]"

      - name: Run integration tests
        run: |
          pytest tests/ble/test_client_integration.py -v --cov=pydglab_ws --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          files: ./coverage.xml
          flags: ble-integration

  # 端到端和硬件测试需要手动触发
  e2e-tests:
    name: E2E Tests (Manual Trigger)
    runs-on: ubuntu-latest
    if: github.event_name == 'workflow_dispatch'

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -e ".[dev,ble]"

      - name: Run E2E tests
        run: |
          pytest tests/ble/test_e2e.py -v -m e2e
```

### 8.7 测试目录结构

```
tests/
├── conftest.py                    # 现有: 全局 fixtures
├── app_simulator.py               # 现有: DG-Lab App 模拟器
├── test_main.py                   # 现有: WebSocket 测试
├── test_models.py                 # 现有: 模型测试
├── test_utils.py                  # 现有: 工具函数测试
│
└── ble/                           # 新增: BLE 测试目录
    ├── __init__.py
    ├── conftest.py                # BLE 测试 fixtures
    ├── mock_ble.py                # BLE Mock 实现
    │
    ├── test_protocol.py           # Level 1: 协议单元测试
    ├── test_mapping.py            # Level 1: 映射转换测试
    ├── test_waveform.py           # Level 1: 波形转换测试
    │
    ├── test_client_integration.py # Level 2: 客户端集成测试
    │
    ├── test_e2e.py                # Level 3: 端到端测试
    │
    └── test_hardware.py           # Level 4: 硬件测试
```

### 8.8 测试运行命令

```bash
# 运行所有单元测试 (CI 默认)
pytest tests/ble/test_protocol.py tests/ble/test_mapping.py -v

# 运行集成测试
pytest tests/ble/test_client_integration.py -v

# 运行端到端测试 (需要 BLE 模拟器)
pytest tests/ble/test_e2e.py -v -m e2e

# 运行硬件测试 (需要真实设备)
HARDWARE_TEST_ENABLED=1 pytest tests/ble/test_hardware.py -v -m hardware

# 运行所有 BLE 测试 (除硬件测试外)
pytest tests/ble/ -v --ignore=tests/ble/test_hardware.py

# 生成覆盖率报告
pytest tests/ble/ -v --cov=pydglab_ws.ble --cov-report=html
```

---

## 9. 硬件测试结果

### 9.1 测试环境
- **设备**: YYC-DJ (役次元设备)
- **平台**: macOS (Darwin 25.2.0)
- **BLE 库**: bleak >= 0.21.0

### 9.2 测试结果汇总

| 测试项 | 结果 | 备注 |
|--------|------|------|
| 设备扫描 | ✅ 通过 | UUID 过滤正常工作 |
| BLE 连接 | ✅ 通过 | 连接稳定 |
| 电池电量查询 | ✅ 通过 | 返回 50% |
| 通道状态查询 | ✅ 通过 | 需添加 YCYMode.OFF=0x00 |
| 役次元强度控制 | ✅ 通过 | set_ycy_strength() |
| DG-Lab set_strength(SET_TO) | ✅ 通过 | 强度映射正确 |
| DG-Lab set_strength(INCREASE) | ✅ 通过 | 增量操作正常 |
| DG-Lab set_strength(DECREASE) | ✅ 通过 | 减量操作正常 |
| 波形队列 add_pulses() | ✅ 通过 | 软件模拟正常 |
| 波形清除 clear_pulses() | ✅ 通过 | |
| 单元测试 | ✅ 137/137 通过 | 包含 67 个 BLE 测试 |

### 9.3 发现的问题及修复

1. **YCYMode 枚举缺少 OFF 值**
   - 问题: 设备返回模式 0 时抛出 ValueError
   - 修复: 添加 `YCYMode.OFF = 0x00`

---

## 10. 已知限制

### 10.1 波形兼容性限制

> ⚠️ **重要**: DG-Lab 波形数据无法完美映射到 YCY 设备

#### 问题描述

DG-Lab 和 YCY 的波形系统存在根本性差异，导致通过 `add_pulses()` 接口发送的 DG-Lab 波形数据无法在 YCY 设备上产生预期效果。

| 特性 | DG-Lab | YCY | 兼容性 |
|------|--------|-----|--------|
| 波形定义 | 软件定义，每100ms发送数据 | 设备内置16种预设 | ❌ 不兼容 |
| 频率参数 | 10-240 (内部参数，非Hz) | 1-100 Hz (真实频率) | ❌ 语义不同 |
| 动态变化 | 支持频率+强度同时变化 | 仅支持固定模式参数 | ❌ 无法模拟 |
| 波形队列 | 最多500条 (50秒) | 不支持队列 | ⚠️ 软件模拟 |

#### DG-Lab 波形格式
```python
# 每条数据代表 100ms
((freq1, freq2, freq3, freq4), (str1, str2, str3, str4))
# freq: 10-240 (DG-Lab 内部参数，不是真正的 Hz)
# str: 0-100 (强度百分比)
```

#### YCY 自定义模式
```python
# 固定参数，设备持续输出
frequency: 1-100  # 真实的脉冲重复频率 (Hz)
pulse_width: 0-100  # 脉冲宽度 (us)
```

#### 当前实现的问题

当前 `add_pulses()` 实现尝试将 DG-Lab 波形数据转换为 YCY 自定义模式：

```python
def convert_pulse(pulse: PulseOperation) -> Tuple[int, int]:
    frequencies, strengths = pulse
    freq = 100  # 固定使用 100Hz
    pulse_width = sum(strengths) // 4  # 强度平均值
    return (freq, pulse_width)
```

**问题**：
1. DG-Lab 的 `freq` 参数含义与 YCY 的 `frequency` 完全不同
2. DG-Lab 波形效果依赖频率+强度的**动态变化**，而 YCY 只能输出固定参数
3. 转换后的效果与原始 DG-Lab 波形预设差异很大

### 10.2 推荐方案

#### 方案 A: 使用 YCY 内置预设模式 (推荐)

YCY 设备有 16 种内置预设模式 (`PRESET_1` 到 `PRESET_16`)，设备会自动循环播放波形效果。

```python
from pydglab_ws.client import YCYBLEClient
from pydglab_ws.ble.enums import YCYMode

async with YCYBLEClient("XX:XX:XX:XX:XX:XX") as client:
    # 设置强度
    await client.set_strength(Channel.A, StrengthOperationType.SET_TO, 50)

    # 使用 YCY 内置预设 (推荐)
    await client.set_mode(Channel.A, YCYMode.PRESET_1)
```

**优点**：
- 设备固件内置波形效果，稳定可靠
- 不需要持续发送数据
- 无通信延迟和丢包问题

**API 接口**：
```python
# 直接使用 YCY 预设模式
await client.set_mode(channel: Channel, mode: YCYMode) -> bool

# 或使用 DG-Lab 预设索引 (自动映射)
await client.set_pulse_preset(channel: Channel, preset_index: int) -> bool
```

**预设映射表**：
```python
# DG-Lab 预设索引 -> YCY 预设模式
DGLAB_PRESET_TO_YCY = {
    0: YCYMode.PRESET_1,   # 呼吸
    1: YCYMode.PRESET_2,   # 潮汐
    2: YCYMode.PRESET_3,   # 连击
    3: YCYMode.PRESET_4,   # 快速按捏
    4: YCYMode.PRESET_5,   # 按捏渐强
    5: YCYMode.PRESET_6,   # 心跳节奏
    6: YCYMode.PRESET_7,   # 压缩
    7: YCYMode.PRESET_8,   # 节奏步伐
    8: YCYMode.PRESET_9,   # 颗粒摩擦
    9: YCYMode.PRESET_10,  # 渐变弹跳
    10: YCYMode.PRESET_11, # 波浪涟漪
    11: YCYMode.PRESET_12, # 雨水冲刷
    12: YCYMode.PRESET_13, # 变速敲击
    13: YCYMode.PRESET_14, # 信号灯
    14: YCYMode.PRESET_15, # 挑逗1
    15: YCYMode.PRESET_16, # 挑逗2
}
```

> **注意**: DG-Lab 和 YCY 的预设效果可能不完全相同，需要实际测试确认映射关系。

#### 方案 B: 使用 add_pulses() (有限兼容)

如果必须使用 `add_pulses()` 接口，需要了解以下限制：

```python
# 仍可使用，但效果与 DG-Lab 设备不同
await client.add_pulses(Channel.A, *pulse_data)
```

**限制**：
- 波形效果与 DG-Lab 原始预设差异较大
- 需要持续发送数据维持输出
- 可能存在通信延迟和抖动

### 10.3 上层应用适配建议

对于需要同时支持 DG-Lab 和 YCY 设备的应用，建议：

```python
# 检测是否为 BLE 模式（YCY 设备）
if hasattr(client, 'set_pulse_preset'):
    # YCY BLE 模式: 使用内置预设
    await client.set_pulse_preset(channel, preset_index)
else:
    # DG-Lab WebSocket 模式: 发送波形数据
    await client.add_pulses(channel, *pulse_data)
```

---

## 11. 参考资料

- [役次元蓝牙通讯协议 V1.6](./YCY-YOKONEX-OpenSource/Bluetooth/役次元电击蓝牙通讯.pdf)
- [DG-Lab Socket 协议](./PROTOCOL.md)
- [bleak 文档](https://bleak.readthedocs.io/)
- [PyDGLab-WS 文档](https://pydglab-ws.readthedocs.io/)
