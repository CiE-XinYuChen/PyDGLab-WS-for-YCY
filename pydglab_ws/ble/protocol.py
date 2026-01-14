"""
役次元 BLE 协议编解码
"""
from typing import Optional

from .enums import (
    YCYChannel, YCYMode, YCYCommand, YCYQueryType, YCYError,
    MotorState, ElectrodeStatus
)
from .exceptions import ChecksumError
from .models import YCYResponse, YCYChannelStatus

__all__ = ("YCYBLEProtocol",)

# 协议常量
PACKET_HEADER = 0x35


class YCYBLEProtocol:
    """
    役次元 BLE 协议编解码器

    数据包格式:
        ┌────────┬────────┬────────────┬────────┐
        │ 包头   │ 命令字  │ 数据...    │ 校验和 │
        │ 0x35   │ 0xXX   │ ...        │ SUM    │
        └────────┴────────┴────────────┴────────┘

    校验和 = (所有前面字节之和) & 0xFF
    """

    @staticmethod
    def calculate_checksum(data: bytes) -> int:
        """
        计算校验和

        :param data: 不含校验和的数据
        :return: 校验和 (单字节)
        """
        return sum(data) & 0xFF

    @staticmethod
    def build_channel_control(
        channel: YCYChannel,
        enabled: bool,
        strength: int,
        mode: YCYMode,
        frequency: int = 0,
        pulse_width: int = 0
    ) -> bytes:
        """
        构建通道控制命令

        命令格式 (10 字节):
            字节 1: 包头 0x35
            字节 2: 命令字 0x11
            字节 3: 通道号 (0x01/0x02/0x03)
            字节 4: 开关状态 (0x00/0x01)
            字节 5-6: 强度 (大端序, 0x0001-0x0114)
            字节 7: 模式 (0x01-0x10 或 0x11)
            字节 8: 频率 (仅自定义模式, 0x01-0x64)
            字节 9: 脉冲时间 (仅自定义模式, 0x00-0x64)
            字节 10: 校验和

        :param channel: 通道
        :param enabled: 是否开启
        :param strength: 强度 (1-276)
        :param mode: 模式
        :param frequency: 频率 (1-100Hz, 仅自定义模式有效)
        :param pulse_width: 脉冲宽度 (0-100us, 仅自定义模式有效)
        :return: 命令字节
        """
        # 强度限制
        strength = max(1, min(276, strength))

        # 非自定义模式时，频率和脉冲宽度固定为 0
        if mode != YCYMode.CUSTOM:
            frequency = 0
            pulse_width = 0
        else:
            frequency = max(1, min(100, frequency))
            pulse_width = max(0, min(100, pulse_width))

        data = bytes([
            PACKET_HEADER,
            YCYCommand.CHANNEL_CONTROL,
            channel,
            0x01 if enabled else 0x00,
            (strength >> 8) & 0xFF,  # 强度高字节
            strength & 0xFF,          # 强度低字节
            mode,
            frequency,
            pulse_width,
        ])

        checksum = YCYBLEProtocol.calculate_checksum(data)
        return data + bytes([checksum])

    @staticmethod
    def build_motor_control(state: MotorState) -> bytes:
        """
        构建马达控制命令

        命令格式 (4 字节):
            字节 1: 包头 0x35
            字节 2: 命令字 0x12
            字节 3: 状态
            字节 4: 校验和

        :param state: 马达状态
        :return: 命令字节
        """
        data = bytes([
            PACKET_HEADER,
            YCYCommand.MOTOR_CONTROL,
            state,
        ])
        checksum = YCYBLEProtocol.calculate_checksum(data)
        return data + bytes([checksum])

    @staticmethod
    def build_step_control(state: int) -> bytes:
        """
        构建计步控制命令

        :param state: 状态 (0x00=关闭, 0x01=开启, 0x02=清零, 0x03=暂停, 0x04=恢复)
        :return: 命令字节
        """
        data = bytes([
            PACKET_HEADER,
            YCYCommand.STEP_CONTROL,
            state,
        ])
        checksum = YCYBLEProtocol.calculate_checksum(data)
        return data + bytes([checksum])

    @staticmethod
    def build_angle_control(enabled: bool) -> bytes:
        """
        构建角度控制命令

        :param enabled: 是否开启
        :return: 命令字节
        """
        data = bytes([
            PACKET_HEADER,
            YCYCommand.ANGLE_CONTROL,
            0x01 if enabled else 0x00,
        ])
        checksum = YCYBLEProtocol.calculate_checksum(data)
        return data + bytes([checksum])

    @staticmethod
    def build_query(query_type: YCYQueryType) -> bytes:
        """
        构建查询命令

        命令格式 (4 字节):
            字节 1: 包头 0x35
            字节 2: 命令字 0x71
            字节 3: 查询类型
            字节 4: 校验和

        :param query_type: 查询类型
        :return: 命令字节
        """
        data = bytes([
            PACKET_HEADER,
            YCYCommand.QUERY,
            query_type,
        ])
        checksum = YCYBLEProtocol.calculate_checksum(data)
        return data + bytes([checksum])

    @staticmethod
    def parse_response(data: bytes, verify_checksum: bool = True) -> Optional[YCYResponse]:
        """
        解析响应数据

        :param data: 原始响应字节
        :param verify_checksum: 是否验证校验和
        :return: 解析后的响应对象
        :raises ChecksumError: 校验和错误
        """
        if len(data) < 4:
            return None

        # 验证包头
        if data[0] != PACKET_HEADER:
            return None

        # 验证校验和
        if verify_checksum:
            expected_checksum = YCYBLEProtocol.calculate_checksum(data[:-1])
            actual_checksum = data[-1]
            if expected_checksum != actual_checksum:
                raise ChecksumError(expected_checksum, actual_checksum)

        # 验证命令字 (响应应该是查询命令)
        if data[1] != YCYCommand.QUERY:
            return None

        response_type = YCYQueryType(data[2])

        # 根据响应类型解析数据
        if response_type in (YCYQueryType.CHANNEL_A_STATUS, YCYQueryType.CHANNEL_B_STATUS):
            # 通道状态应答 (9 字节)
            if len(data) < 9:
                return None
            channel_status = YCYChannelStatus(
                electrode_status=ElectrodeStatus(data[3]),
                enabled=data[4] == 0x01,
                strength=(data[5] << 8) | data[6],
                mode=YCYMode(data[7]),
            )
            return YCYResponse(response_type=response_type, data=channel_status)

        elif response_type == YCYQueryType.MOTOR_STATUS:
            # 马达状态应答 (5 字节)
            if len(data) < 5:
                return None
            return YCYResponse(
                response_type=response_type,
                data=MotorState(data[3])
            )

        elif response_type == YCYQueryType.BATTERY:
            # 电池电量应答 (5 字节)
            if len(data) < 5:
                return None
            return YCYResponse(
                response_type=response_type,
                data=data[3]  # 0-100
            )

        elif response_type == YCYQueryType.STEP_COUNT:
            # 计步数据应答 (6 字节)
            if len(data) < 6:
                return None
            step_count = (data[3] << 8) | data[4]
            return YCYResponse(
                response_type=response_type,
                data=step_count
            )

        elif response_type == YCYQueryType.ANGLE_DATA:
            # 角度数据应答 (16 字节)
            if len(data) < 16:
                return None
            acc_x = (data[3] << 8) | data[4]
            acc_y = (data[5] << 8) | data[6]
            acc_z = (data[7] << 8) | data[8]
            gyro_x = (data[9] << 8) | data[10]
            gyro_y = (data[11] << 8) | data[12]
            gyro_z = (data[13] << 8) | data[14]
            return YCYResponse(
                response_type=response_type,
                data=(acc_x, acc_y, acc_z, gyro_x, gyro_y, gyro_z)
            )

        elif response_type == YCYQueryType.ERROR:
            # 异常上报 (5 字节)
            if len(data) < 5:
                return None
            return YCYResponse(
                response_type=response_type,
                data=YCYError(data[3])
            )

        return YCYResponse(response_type=response_type, data=None)
