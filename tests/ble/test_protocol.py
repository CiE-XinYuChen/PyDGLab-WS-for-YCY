"""
役次元 BLE 协议编解码测试
"""
import pytest

from pydglab_ws.ble.enums import (
    YCYChannel, YCYMode, YCYCommand, YCYQueryType,
    MotorState, ElectrodeStatus, YCYError
)
from pydglab_ws.ble.protocol import YCYBLEProtocol, PACKET_HEADER
from pydglab_ws.ble.exceptions import ChecksumError


class TestChecksum:
    """校验和计算测试"""

    def test_checksum_empty(self):
        """空数据校验和"""
        assert YCYBLEProtocol.calculate_checksum(b"") == 0

    def test_checksum_single_byte(self):
        """单字节校验和"""
        assert YCYBLEProtocol.calculate_checksum(bytes([0x35])) == 0x35

    def test_checksum_multiple_bytes(self):
        """多字节校验和"""
        # 0x35 + 0x11 + 0x01 = 0x47
        assert YCYBLEProtocol.calculate_checksum(bytes([0x35, 0x11, 0x01])) == 0x47

    def test_checksum_overflow(self):
        """校验和溢出 (单字节截断)"""
        # 0xFF + 0xFF = 0x1FE -> 0xFE
        assert YCYBLEProtocol.calculate_checksum(bytes([0xFF, 0xFF])) == 0xFE


class TestBuildChannelControl:
    """通道控制命令构建测试"""

    def test_channel_a_enabled(self):
        """开启 A 通道，强度 100，预设模式 1"""
        cmd = YCYBLEProtocol.build_channel_control(
            channel=YCYChannel.A,
            enabled=True,
            strength=100,
            mode=YCYMode.PRESET_1,
        )
        assert len(cmd) == 10
        assert cmd[0] == PACKET_HEADER  # 包头
        assert cmd[1] == YCYCommand.CHANNEL_CONTROL  # 命令字
        assert cmd[2] == YCYChannel.A  # 通道
        assert cmd[3] == 0x01  # 开启
        assert cmd[4] == 0x00  # 强度高字节
        assert cmd[5] == 0x64  # 强度低字节 (100 = 0x64)
        assert cmd[6] == YCYMode.PRESET_1  # 模式
        assert cmd[7] == 0x00  # 频率 (非自定义模式为 0)
        assert cmd[8] == 0x00  # 脉冲宽度 (非自定义模式为 0)
        # 校验和
        expected_checksum = YCYBLEProtocol.calculate_checksum(cmd[:-1])
        assert cmd[9] == expected_checksum

    def test_channel_b_disabled(self):
        """关闭 B 通道"""
        cmd = YCYBLEProtocol.build_channel_control(
            channel=YCYChannel.B,
            enabled=False,
            strength=50,
            mode=YCYMode.PRESET_5,
        )
        assert cmd[2] == YCYChannel.B
        assert cmd[3] == 0x00  # 关闭

    def test_channel_ab(self):
        """AB 通道同时控制"""
        cmd = YCYBLEProtocol.build_channel_control(
            channel=YCYChannel.AB,
            enabled=True,
            strength=200,
            mode=YCYMode.PRESET_10,
        )
        assert cmd[2] == YCYChannel.AB

    def test_custom_mode_with_frequency(self):
        """自定义模式带频率和脉冲宽度"""
        cmd = YCYBLEProtocol.build_channel_control(
            channel=YCYChannel.A,
            enabled=True,
            strength=150,
            mode=YCYMode.CUSTOM,
            frequency=50,
            pulse_width=30,
        )
        assert cmd[6] == YCYMode.CUSTOM
        assert cmd[7] == 50  # 频率
        assert cmd[8] == 30  # 脉冲宽度

    def test_preset_mode_ignores_frequency(self):
        """预设模式忽略频率和脉冲宽度参数"""
        cmd = YCYBLEProtocol.build_channel_control(
            channel=YCYChannel.A,
            enabled=True,
            strength=100,
            mode=YCYMode.PRESET_1,
            frequency=50,  # 应被忽略
            pulse_width=30,  # 应被忽略
        )
        assert cmd[7] == 0x00  # 频率应为 0
        assert cmd[8] == 0x00  # 脉冲宽度应为 0

    def test_strength_clamp_min(self):
        """强度下限钳制"""
        cmd = YCYBLEProtocol.build_channel_control(
            channel=YCYChannel.A,
            enabled=True,
            strength=0,  # 低于最小值
            mode=YCYMode.PRESET_1,
        )
        # 强度应被钳制为 1
        assert (cmd[4] << 8) | cmd[5] == 1

    def test_strength_clamp_max(self):
        """强度上限钳制"""
        cmd = YCYBLEProtocol.build_channel_control(
            channel=YCYChannel.A,
            enabled=True,
            strength=500,  # 高于最大值
            mode=YCYMode.PRESET_1,
        )
        # 强度应被钳制为 276
        assert (cmd[4] << 8) | cmd[5] == 276

    def test_max_strength_276(self):
        """最大强度 276"""
        cmd = YCYBLEProtocol.build_channel_control(
            channel=YCYChannel.A,
            enabled=True,
            strength=276,
            mode=YCYMode.PRESET_1,
        )
        # 276 = 0x0114
        assert cmd[4] == 0x01
        assert cmd[5] == 0x14

    def test_frequency_clamp(self):
        """自定义模式频率钳制"""
        cmd = YCYBLEProtocol.build_channel_control(
            channel=YCYChannel.A,
            enabled=True,
            strength=100,
            mode=YCYMode.CUSTOM,
            frequency=200,  # 超过最大值 100
            pulse_width=0,
        )
        assert cmd[7] == 100  # 频率钳制为 100

    def test_pulse_width_clamp(self):
        """自定义模式脉冲宽度钳制"""
        cmd = YCYBLEProtocol.build_channel_control(
            channel=YCYChannel.A,
            enabled=True,
            strength=100,
            mode=YCYMode.CUSTOM,
            frequency=50,
            pulse_width=200,  # 超过最大值 100
        )
        assert cmd[8] == 100  # 脉冲宽度钳制为 100


class TestBuildMotorControl:
    """马达控制命令构建测试"""

    def test_motor_off(self):
        """关闭马达"""
        cmd = YCYBLEProtocol.build_motor_control(MotorState.OFF)
        assert len(cmd) == 4
        assert cmd[0] == PACKET_HEADER
        assert cmd[1] == YCYCommand.MOTOR_CONTROL
        assert cmd[2] == MotorState.OFF
        expected_checksum = YCYBLEProtocol.calculate_checksum(cmd[:-1])
        assert cmd[3] == expected_checksum

    def test_motor_on(self):
        """开启马达"""
        cmd = YCYBLEProtocol.build_motor_control(MotorState.ON)
        assert cmd[2] == MotorState.ON

    def test_motor_preset(self):
        """马达预设模式"""
        cmd = YCYBLEProtocol.build_motor_control(MotorState.PRESET_1)
        assert cmd[2] == MotorState.PRESET_1


class TestBuildQuery:
    """查询命令构建测试"""

    def test_query_channel_a(self):
        """查询 A 通道状态"""
        cmd = YCYBLEProtocol.build_query(YCYQueryType.CHANNEL_A_STATUS)
        assert len(cmd) == 4
        assert cmd[0] == PACKET_HEADER
        assert cmd[1] == YCYCommand.QUERY
        assert cmd[2] == YCYQueryType.CHANNEL_A_STATUS
        expected_checksum = YCYBLEProtocol.calculate_checksum(cmd[:-1])
        assert cmd[3] == expected_checksum

    def test_query_battery(self):
        """查询电池电量"""
        cmd = YCYBLEProtocol.build_query(YCYQueryType.BATTERY)
        assert cmd[2] == YCYQueryType.BATTERY


class TestParseResponse:
    """响应解析测试"""

    def test_parse_channel_status(self):
        """解析通道状态响应"""
        # 构建响应: 通道A, 已连接放电, 开启, 强度256, 预设模式1
        response_data = bytes([
            PACKET_HEADER,
            YCYCommand.QUERY,
            YCYQueryType.CHANNEL_A_STATUS,
            ElectrodeStatus.CONNECTED_ACTIVE,  # 电极状态
            0x01,  # 开启
            0x01, 0x00,  # 强度 256 (大端序)
            YCYMode.PRESET_1,  # 模式
        ])
        checksum = YCYBLEProtocol.calculate_checksum(response_data)
        response_data = response_data + bytes([checksum])

        result = YCYBLEProtocol.parse_response(response_data)
        assert result is not None
        assert result.response_type == YCYQueryType.CHANNEL_A_STATUS
        assert result.channel_status is not None
        assert result.channel_status.electrode_status == ElectrodeStatus.CONNECTED_ACTIVE
        assert result.channel_status.enabled is True
        assert result.channel_status.strength == 256
        assert result.channel_status.mode == YCYMode.PRESET_1

    def test_parse_battery(self):
        """解析电池电量响应"""
        response_data = bytes([
            PACKET_HEADER,
            YCYCommand.QUERY,
            YCYQueryType.BATTERY,
            75,  # 75% 电量
        ])
        checksum = YCYBLEProtocol.calculate_checksum(response_data)
        response_data = response_data + bytes([checksum])

        result = YCYBLEProtocol.parse_response(response_data)
        assert result is not None
        assert result.response_type == YCYQueryType.BATTERY
        assert result.battery == 75

    def test_parse_motor_status(self):
        """解析马达状态响应"""
        response_data = bytes([
            PACKET_HEADER,
            YCYCommand.QUERY,
            YCYQueryType.MOTOR_STATUS,
            MotorState.ON,
        ])
        checksum = YCYBLEProtocol.calculate_checksum(response_data)
        response_data = response_data + bytes([checksum])

        result = YCYBLEProtocol.parse_response(response_data)
        assert result is not None
        assert result.response_type == YCYQueryType.MOTOR_STATUS
        assert result.motor_status == MotorState.ON

    def test_parse_step_count(self):
        """解析计步数据响应"""
        response_data = bytes([
            PACKET_HEADER,
            YCYCommand.QUERY,
            YCYQueryType.STEP_COUNT,
            0x03, 0xE8,  # 1000 步 (大端序)
        ])
        checksum = YCYBLEProtocol.calculate_checksum(response_data)
        response_data = response_data + bytes([checksum])

        result = YCYBLEProtocol.parse_response(response_data)
        assert result is not None
        assert result.response_type == YCYQueryType.STEP_COUNT
        assert result.step_count == 1000

    def test_parse_error(self):
        """解析错误响应"""
        response_data = bytes([
            PACKET_HEADER,
            YCYCommand.QUERY,
            YCYQueryType.ERROR,
            YCYError.CHECKSUM_ERROR,
        ])
        checksum = YCYBLEProtocol.calculate_checksum(response_data)
        response_data = response_data + bytes([checksum])

        result = YCYBLEProtocol.parse_response(response_data)
        assert result is not None
        assert result.response_type == YCYQueryType.ERROR
        assert result.error_code == YCYError.CHECKSUM_ERROR

    def test_parse_invalid_header(self):
        """无效包头返回 None"""
        response_data = bytes([0x00, 0x71, 0x04, 50, 0x00])
        result = YCYBLEProtocol.parse_response(response_data, verify_checksum=False)
        assert result is None

    def test_parse_short_data(self):
        """数据过短返回 None"""
        response_data = bytes([PACKET_HEADER, 0x71])
        result = YCYBLEProtocol.parse_response(response_data, verify_checksum=False)
        assert result is None

    def test_parse_checksum_error(self):
        """校验和错误抛出异常"""
        response_data = bytes([
            PACKET_HEADER,
            YCYCommand.QUERY,
            YCYQueryType.BATTERY,
            50,
            0xFF,  # 错误的校验和
        ])
        with pytest.raises(ChecksumError):
            YCYBLEProtocol.parse_response(response_data, verify_checksum=True)

    def test_parse_skip_checksum_verification(self):
        """跳过校验和验证"""
        response_data = bytes([
            PACKET_HEADER,
            YCYCommand.QUERY,
            YCYQueryType.BATTERY,
            50,
            0xFF,  # 错误的校验和
        ])
        # 不应抛出异常
        result = YCYBLEProtocol.parse_response(response_data, verify_checksum=False)
        assert result is not None
        assert result.battery == 50

    def test_parse_non_query_command(self):
        """非查询命令返回 None"""
        response_data = bytes([
            PACKET_HEADER,
            YCYCommand.CHANNEL_CONTROL,  # 非 QUERY 命令
            0x01,
            0x00,
        ])
        checksum = YCYBLEProtocol.calculate_checksum(response_data)
        response_data = response_data + bytes([checksum])

        result = YCYBLEProtocol.parse_response(response_data)
        assert result is None


class TestBuildStepControl:
    """计步控制命令构建测试"""

    def test_step_enable(self):
        """开启计步"""
        cmd = YCYBLEProtocol.build_step_control(0x01)
        assert len(cmd) == 4
        assert cmd[0] == PACKET_HEADER
        assert cmd[1] == YCYCommand.STEP_CONTROL
        assert cmd[2] == 0x01

    def test_step_clear(self):
        """清零计步"""
        cmd = YCYBLEProtocol.build_step_control(0x02)
        assert cmd[2] == 0x02


class TestBuildAngleControl:
    """角度控制命令构建测试"""

    def test_angle_enable(self):
        """开启角度上报"""
        cmd = YCYBLEProtocol.build_angle_control(True)
        assert len(cmd) == 4
        assert cmd[0] == PACKET_HEADER
        assert cmd[1] == YCYCommand.ANGLE_CONTROL
        assert cmd[2] == 0x01

    def test_angle_disable(self):
        """关闭角度上报"""
        cmd = YCYBLEProtocol.build_angle_control(False)
        assert cmd[2] == 0x00
