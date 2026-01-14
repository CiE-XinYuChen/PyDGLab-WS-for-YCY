"""
役次元 BLE 数据模型定义
"""
from dataclasses import dataclass
from typing import Optional, Union

from .enums import YCYQueryType, YCYError, YCYMode, ElectrodeStatus, MotorState

__all__ = (
    "YCYDevice",
    "YCYChannelStatus",
    "YCYResponse",
)


@dataclass
class YCYDevice:
    """
    役次元 BLE 设备信息

    :ivar address: 设备地址 (MAC 或 UUID)
    :ivar name: 设备名称
    :ivar rssi: 信号强度
    """
    address: str
    name: Optional[str] = None
    rssi: Optional[int] = None

    def __str__(self) -> str:
        if self.name:
            return f"{self.name} ({self.address})"
        return self.address


@dataclass
class YCYChannelStatus:
    """
    役次元通道状态

    :ivar electrode_status: 电极连接状态
    :ivar enabled: 通道是否开启
    :ivar strength: 通道强度 (1-276)
    :ivar mode: 通道模式
    """
    electrode_status: ElectrodeStatus
    enabled: bool
    strength: int
    mode: YCYMode


@dataclass
class YCYResponse:
    """
    役次元响应数据

    :ivar response_type: 响应类型
    :ivar data: 响应数据 (根据类型不同而不同)
    """
    response_type: YCYQueryType
    data: Union[YCYChannelStatus, int, YCYError, MotorState, tuple, None] = None

    @property
    def is_error(self) -> bool:
        """是否为错误响应"""
        return self.response_type == YCYQueryType.ERROR

    @property
    def battery(self) -> Optional[int]:
        """获取电池电量 (仅当响应类型为 BATTERY 时有效)"""
        if self.response_type == YCYQueryType.BATTERY:
            return self.data
        return None

    @property
    def channel_status(self) -> Optional[YCYChannelStatus]:
        """获取通道状态 (仅当响应类型为通道状态时有效)"""
        if self.response_type in (YCYQueryType.CHANNEL_A_STATUS, YCYQueryType.CHANNEL_B_STATUS):
            return self.data
        return None

    @property
    def motor_status(self) -> Optional[MotorState]:
        """获取马达状态"""
        if self.response_type == YCYQueryType.MOTOR_STATUS:
            return self.data
        return None

    @property
    def error_code(self) -> Optional[YCYError]:
        """获取错误码"""
        if self.response_type == YCYQueryType.ERROR:
            return self.data
        return None

    @property
    def step_count(self) -> Optional[int]:
        """获取计步数据"""
        if self.response_type == YCYQueryType.STEP_COUNT:
            return self.data
        return None

    @property
    def angle_data(self) -> Optional[tuple]:
        """获取角度数据 (acc_x, acc_y, acc_z, gyro_x, gyro_y, gyro_z)"""
        if self.response_type == YCYQueryType.ANGLE_DATA:
            return self.data
        return None
