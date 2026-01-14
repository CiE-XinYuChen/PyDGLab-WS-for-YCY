<h1 align="center">
  PyDGLab-WS (YCY Fork)
</h1>

<p align="center">
  役次元 (YCY/YOKONEX) 设备蓝牙直连 Python 库
</p>

> [!Important]
> **本分支仅支持役次元 (YCY) 设备蓝牙直连，不再支持郊狼 DG-Lab App。**
> 由于破坏性更改，本仓库无法合并 [原版 PyDGLab-WS](https://github.com/Ljzd-PRO/PyDGLab-WS)。
> 特别说明，本项目不得用于商业用途。若您使用了本项目中的部分代码，请一并开源且标注本仓库、原仓库的指向性链接

<p align="center">
  <a href="https://github.com/CiE-XinYuChen/PyDGLab-WS-for-YCY">
    <img src="https://img.shields.io/github/last-commit/CiE-XinYuChen/PyDGLab-WS-for-YCY/master" alt="Last Commit"/>
  </a>

  <a href="./LICENSE">
    <img src="https://img.shields.io/github/license/CiE-XinYuChen/PyDGLab-WS-for-YCY" alt="BSD 3-Clause"/>
  </a>
</p>

## 💡 特性

- 通过蓝牙直连役次元 (YCY/YOKONEX) 设备，无需通过 App 中转
- 完全使用 asyncio 异步，并发执行各项操作
- 提供 DG-Lab API 兼容接口，方便迁移现有代码
- 使用异步生成器、上下文管理器等，结合语言特性
- 通过 Pydantic, 枚举 管理消息结构和常量，便于开发

### 🔧 支持的操作

- 对 A, B 通道强度进行操作，支持增加、减少、设定到指定值
- 16 种预设模式切换
- 自定义波形 (频率 + 脉冲宽度)
- 获取电池电量
- 马达控制
- 电极连接状态检测

## 🚀 快速开始

### 🔨 安装


**从源码安装:**

```bash
git clone https://github.com/CiE-XinYuChen/PyDGLab-WS-for-YCY.git
cd PyDGLab-WS-for-YCY
pip3 install -e .
```

### 🔵 使用示例

```python3
import asyncio
from pydglab_ws import YCYBLEClient, YCYScanner
from pydglab_ws import Channel, StrengthOperationType


async def main():
    # 扫描设备
    print("正在扫描役次元设备...")
    devices = await YCYScanner.scan(timeout=5.0)

    if not devices:
        print("未找到设备")
        return

    print(f"找到设备: {devices[0]}")

    # 连接设备
    async with YCYBLEClient(devices[0].address) as client:
        print("已连接")

        # 获取电池电量
        battery = await client.get_battery()
        print(f"电池电量: {battery}%")

        # 设置 A 通道强度 (DG-Lab 兼容接口)
        await client.set_strength(Channel.A, StrengthOperationType.SET_TO, 50)

        # 或使用役次元扩展接口
        from pydglab_ws.ble import YCYMode
        await client.set_mode(Channel.A, YCYMode.PRESET_1)

        # 接收数据更新
        async for data in client.data_generator():
            print(f"收到数据: {data}")


if __name__ == "__main__":
    asyncio.run(main())
```

#### 🔧 役次元 BLE 支持的操作

**DG-Lab 兼容接口:**
- `set_strength()` - 设置通道强度 (自动映射 0-200 → 1-276)
- `add_pulses()` - 添加波形到队列 (软件模拟)
- `clear_pulses()` - 清空波形队列
- `data_generator()` - 数据生成器
- `recv_data()` - 接收数据

**DG-Lab 兼容属性:**
- `client_id` - 终端 ID (基于设备地址生成)
- `target_id` - 设备 ID (基于设备地址生成)
- `strength_data` - 当前强度数据
- `not_registered` / `not_bind` - 连接状态
- `bind()` / `rebind()` / `ensure_bind()` - 绑定方法 (BLE 模式下连接即绑定)

**役次元扩展接口:**
- `get_battery()` - 获取电池电量
- `set_motor()` - 控制马达
- `set_mode()` - 设置 16 种预设模式
- `set_custom_wave()` - 设置自定义波形 (频率 + 脉冲宽度)
- `set_ycy_strength()` - 直接设置役次元原生强度
- `get_electrode_status()` - 获取电极连接状态
- `get_channel_status()` - 获取通道完整状态
- `stop_channel()` - 停止单个通道输出
- `stop_all()` - 停止所有输出 (双通道 + 马达)

## 🔄 兼容层

本项目提供与原版 `pydglab-ws` 完全兼容的接口。`DGLabWSServer` 已自动指向 BLE 版本，
现有项目（如 YCY-VRCOSC）**无需任何代码修改**，只需安装本库即可使用 BLE 直连：

```bash
# 卸载原版
pip uninstall pydglab-ws

# 安装本库
pip install -e /path/to/PyDGLab-WS-for-YCY
```

原有代码可直接运行：

```python
from pydglab_ws import DGLabWSServer  # 自动使用 BLE 版本

async with DGLabWSServer() as server:
    client = server.new_local_client()
    # ...
```

## 📖 文档

- [API 参考](docs/API.md) - 完整的接口文档

## 📌 更多

如果您在开发过程中，发现要实现一些常用的功能时并不方便，或者您有什么建议能够使开发更简单快捷，欢迎在 [Issues](https://github.com/CiE-XinYuChen/PyDGLab-WS-for-YCY/issues) 中提出~

### 🔗 链接

- 本项目: [CiE-XinYuChen/PyDGLab-WS-for-YCY](https://github.com/CiE-XinYuChen/PyDGLab-WS-for-YCY)
- 原版 PyDGLab-WS: [Ljzd-PRO/PyDGLab-WS](https://github.com/Ljzd-PRO/PyDGLab-WS)

### 许可证

PyDGLab-WS 使用 BSD 3-Clause 许可证.

Copyright © 2024-2025 by Ljzd-PRO, CiE-XinYuChen.
