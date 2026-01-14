"""
役次元 BLE 协议枚举定义
"""
import enum
from enum import IntEnum

__all__ = (
    "YCYChannel",
    "YCYMode",
    "YCYCommand",
    "YCYQueryType",
    "YCYError",
    "MotorState",
    "ElectrodeStatus",
)


@enum.unique
class YCYChannel(IntEnum):
    """
    役次元通道枚举

    :ivar A: A 通道
    :ivar B: B 通道
    :ivar AB: AB 通道同时控制
    """
    A = 0x01
    B = 0x02
    AB = 0x03


@enum.unique
class YCYMode(IntEnum):
    """
    役次元模式枚举

    :ivar OFF: 关闭/未设置
    :ivar PRESET_1 - PRESET_16: 16 种预设模式
    :ivar CUSTOM: 自定义模式 (使用频率和脉冲宽度参数)
    """
    OFF = 0x00
    PRESET_1 = 0x01
    PRESET_2 = 0x02
    PRESET_3 = 0x03
    PRESET_4 = 0x04
    PRESET_5 = 0x05
    PRESET_6 = 0x06
    PRESET_7 = 0x07
    PRESET_8 = 0x08
    PRESET_9 = 0x09
    PRESET_10 = 0x0A
    PRESET_11 = 0x0B
    PRESET_12 = 0x0C
    PRESET_13 = 0x0D
    PRESET_14 = 0x0E
    PRESET_15 = 0x0F
    PRESET_16 = 0x10
    CUSTOM = 0x11


@enum.unique
class YCYCommand(IntEnum):
    """
    役次元命令字枚举

    :ivar CHANNEL_CONTROL: 通道控制命令
    :ivar MOTOR_CONTROL: 马达控制命令
    :ivar STEP_CONTROL: 计步控制命令
    :ivar ANGLE_CONTROL: 角度控制命令
    :ivar QUERY: 查询命令
    """
    CHANNEL_CONTROL = 0x11
    MOTOR_CONTROL = 0x12
    STEP_CONTROL = 0x13
    ANGLE_CONTROL = 0x14
    QUERY = 0x71


@enum.unique
class YCYQueryType(IntEnum):
    """
    役次元查询类型枚举

    :ivar CHANNEL_A_STATUS: 通道 A 状态
    :ivar CHANNEL_B_STATUS: 通道 B 状态
    :ivar MOTOR_STATUS: 马达状态
    :ivar BATTERY: 电池电量
    :ivar STEP_COUNT: 计步数据
    :ivar ANGLE_DATA: 角度数据
    :ivar ERROR: 异常上报
    """
    CHANNEL_A_STATUS = 0x01
    CHANNEL_B_STATUS = 0x02
    MOTOR_STATUS = 0x03
    BATTERY = 0x04
    STEP_COUNT = 0x05
    ANGLE_DATA = 0x06
    ERROR = 0x55


@enum.unique
class YCYError(IntEnum):
    """
    役次元错误码枚举

    :ivar CHECKSUM_ERROR: 校验码错误
    :ivar HEADER_ERROR: 包头错误
    :ivar COMMAND_ERROR: 命令错误
    :ivar DATA_ERROR: 数据错误
    :ivar NOT_IMPLEMENTED: 暂未实现
    """
    CHECKSUM_ERROR = 0x01
    HEADER_ERROR = 0x02
    COMMAND_ERROR = 0x03
    DATA_ERROR = 0x04
    NOT_IMPLEMENTED = 0x05


@enum.unique
class MotorState(IntEnum):
    """
    马达状态枚举

    :ivar OFF: 马达关闭
    :ivar ON: 马达开启
    :ivar PRESET_1: 预设频率 1
    :ivar PRESET_2: 预设频率 2
    :ivar PRESET_3: 预设频率 3
    """
    OFF = 0x00
    ON = 0x01
    PRESET_1 = 0x11
    PRESET_2 = 0x12
    PRESET_3 = 0x13


@enum.unique
class ElectrodeStatus(IntEnum):
    """
    电极连接状态枚举

    :ivar NOT_CONNECTED: 未接入
    :ivar CONNECTED_ACTIVE: 已接入在放电
    :ivar CONNECTED_INACTIVE: 已接入未放电
    """
    NOT_CONNECTED = 0x00
    CONNECTED_ACTIVE = 0x01
    CONNECTED_INACTIVE = 0x02
