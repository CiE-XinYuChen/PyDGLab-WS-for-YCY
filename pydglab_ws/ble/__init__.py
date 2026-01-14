"""
役次元 (YCY) BLE 模块

此模块提供役次元设备的蓝牙直连功能。
需要安装可选依赖: pip install pydglab-ws[ble]
"""

from .enums import *
from .exceptions import *
from .models import *
from .protocol import *
from .scanner import *
from .utils import *

__all__ = (
    # enums
    "YCYChannel",
    "YCYMode",
    "YCYCommand",
    "YCYQueryType",
    "YCYError",
    "MotorState",
    "ElectrodeStatus",
    # exceptions
    "BLEError",
    "DisconnectedError",
    "DeviceNotFoundError",
    "ChecksumError",
    # models
    "YCYDevice",
    "YCYChannelStatus",
    "YCYResponse",
    # protocol
    "YCYBLEProtocol",
    # scanner
    "YCYScanner",
    # utils
    "map_strength_to_ycy",
    "map_strength_to_dglab",
    "convert_pulse",
)
