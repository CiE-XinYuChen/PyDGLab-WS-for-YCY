<h1 align="center">
  PyDGLab-WS (YCY Fork)
</h1>

<p align="center">
  役次元 (YCY/YOKONEX) 设备蓝牙直连 Python 库
</p>

> [!Important]
> **本分支仅支持役次元 (YCY) 设备蓝牙直连，不再支持郊狼 DG-Lab App。**
> 如需使用 DG-Lab App，请使用 [原版 PyDGLab-WS](https://github.com/Ljzd-PRO/PyDGLab-WS)。

<p align="center">
  <a href="https://pydglab-ws.readthedocs.io">📖 完整文档</a>
</p>

<p align="center">
  <a href="https://www.codefactor.io/repository/github/ljzd-pro/pydglab-ws">
    <img src="https://www.codefactor.io/repository/github/ljzd-pro/pydglab-ws/badge" alt="CodeFactor" />
  </a>

  <a href="https://codecov.io/gh/Ljzd-PRO/PyDGLab-WS" target="_blank">
      <img src="https://codecov.io/gh/Ljzd-PRO/PyDGLab-WS/branch/master/graph/badge.svg?token=VTr0LB1yWF" alt="codecov"/>
  </a>

  <a href="https://github.com/Ljzd-PRO/PyDGLab-WS/actions/workflows/codecov.yml" target="_blank">
    <img alt="Test Result" src="https://img.shields.io/github/actions/workflow/status/Ljzd-PRO/PyDGLab-WS/codecov.yml">
  </a>

  <a href='https://pydglab-ws.readthedocs.io/'>
    <img src='https://readthedocs.org/projects/pydglab-ws/badge/?version=latest' alt='Documentation Status' />
  </a>

  <a href="https://github.com/Ljzd-PRO/PyDGLab-WS/activity">
    <img src="https://img.shields.io/github/last-commit/Ljzd-PRO/PyDGLab-WS/master" alt="Last Commit"/>
  </a>

  <a href="./LICENSE">
    <img src="https://img.shields.io/github/license/Ljzd-PRO/PyDGLab-WS" alt="BSD 3-Clause"/>
  </a>

  <a href="https://pypi.org/project/pydglab-ws" target="_blank">
    <img src="https://img.shields.io/github/v/release/Ljzd-PRO/PyDGLab-WS?logo=python" alt="Version">
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

**从 PyPI 安装:**

```bash
pip3 install pydglab-ws
```

**从源码安装:**

```bash
git clone https://github.com/Ljzd-PRO/PyDGLab-WS.git
cd PyDGLab-WS
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
- `get_electrode_status()` - 获取电极连接状态

## 📌 更多

如果您在开发过程中，发现要实现一些常用的功能时并不方便，或者您有什么建议能够使开发更简单快捷，欢迎在 Issues 中提出~

### 相关项目

下列为采用了 PyDGLab-WS 的一些项目：
- [Ljzd-PRO/nonebot-plugin-dg-lab-play](https://github.com/Ljzd-PRO/nonebot-plugin-dg-lab-play)：nonebot2 机器人插件 - ⚡在群里和大家一起玩郊狼吧！⚡
- [Ljzd-PRO/HL2-DGLabInjuryExperienceMod](https://github.com/Ljzd-PRO/HL2-DGLabInjuryExperienceMod)：半条命 2 模组 - 用郊狼⚡模拟一下自己和敌人的受伤痛觉~
  > 其中的 PyDGLab-WS-Connector

如果你的项目也应用了 PyDGLab-WS，欢迎在 Issues 页面分享。

### 🔗 链接

- PyPI: 🔗[pydglab-ws](https://pypi.org/project/pydglab-ws/)

### 📐 代码覆盖率

![codecov.io](https://codecov.io/github/Ljzd-PRO/PyDGLab-WS/graphs/tree.svg?token=VTr0LB1yWF)

### 许可证

PyDGLab-WS 使用 BSD 3-Clause 许可证.

Copyright © 2024-2025 by Ljzd-PRO.
