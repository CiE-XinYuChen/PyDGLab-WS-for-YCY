"""
役次元 BLE 客户端

提供 DG-Lab API 兼容接口，同时支持役次元扩展功能。
"""
import asyncio
import logging
import uuid
from typing import AsyncGenerator, Any, Optional, Type, TypeVar, Union

logger = logging.getLogger(__name__)

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from pydantic import UUID4

from ..enums import Channel, StrengthOperationType, RetCode
from ..models import StrengthData
from ..typing import PulseOperation
from ..ble.enums import YCYChannel, YCYMode, YCYQueryType, MotorState, ElectrodeStatus
from ..ble.exceptions import DisconnectedError, BLEError
from ..ble.models import YCYDevice, YCYChannelStatus, YCYResponse
from ..ble.protocol import YCYBLEProtocol
from ..ble.scanner import YCYScanner, SERVICE_UUID
from ..ble.utils import map_strength_to_ycy, map_strength_to_dglab, convert_pulse

__all__ = ("YCYBLEClient",)

# BLE 特征 UUID
WRITE_CHAR_UUID = "0000ff31-0000-1000-8000-00805f9b34fb"
NOTIFY_CHAR_UUID = "0000ff32-0000-1000-8000-00805f9b34fb"

_DataType = TypeVar("_DataType", Type[StrengthData], Type[RetCode])


class YCYBLEClient:
    """
    役次元 BLE 客户端

    提供 DG-Lab API 兼容接口，同时支持役次元扩展功能。

    使用示例::

        async with YCYBLEClient("XX:XX:XX:XX:XX:XX") as client:
            await client.set_strength(Channel.A, StrengthOperationType.SET_TO, 50)

    :param device: 设备地址、BLEDevice 对象或 YCYDevice 对象
    :param strength_limit: 虚拟强度上限 (DG-Lab 兼容, 默认 200)
    """

    def __init__(
        self,
        device: Union[str, BLEDevice, YCYDevice],
        strength_limit: int = 200
    ):
        # 设备信息
        if isinstance(device, YCYDevice):
            self._device_address = device.address
        elif isinstance(device, BLEDevice):
            self._device_address = device.address
        else:
            self._device_address = device

        # BLE 客户端
        self._client: Optional[BleakClient] = None
        self._connected = False

        # 通知队列
        self._notification_queue: asyncio.Queue[bytes] = asyncio.Queue()

        # 通道状态缓存 (役次元原始强度 1-276)
        self._channel_a_strength = 1
        self._channel_b_strength = 1
        self._channel_a_enabled = False
        self._channel_b_enabled = False

        # 通道模式缓存 (预设模式)
        self._channel_a_mode: YCYMode = YCYMode.PRESET_1
        self._channel_b_mode: YCYMode = YCYMode.PRESET_1

        # 虚拟强度上限 (DG-Lab 兼容)
        self._strength_limit = strength_limit

        # 波形播放器
        self._waveform_player_a: Optional[_WaveformPlayer] = None
        self._waveform_player_b: Optional[_WaveformPlayer] = None

        # DG-Lab 兼容: 基于设备地址生成 UUID
        self._client_id: UUID4 = uuid.uuid5(uuid.NAMESPACE_DNS, f"ycy-client-{self._device_address}")
        self._target_id: UUID4 = uuid.uuid5(uuid.NAMESPACE_DNS, f"ycy-device-{self._device_address}")

    # ==================== DG-Lab 兼容属性 ====================

    @property
    def client_id(self) -> UUID4:
        """DG-Lab 兼容: 终端 ID (基于设备地址生成)"""
        return self._client_id

    @property
    def target_id(self) -> UUID4:
        """DG-Lab 兼容: App/设备 ID (基于设备地址生成)"""
        return self._target_id

    @property
    def not_registered(self) -> bool:
        """DG-Lab 兼容: 终端是否未注册 (BLE 模式下始终为 False)"""
        return False

    @property
    def not_bind(self) -> bool:
        """DG-Lab 兼容: 终端是否未绑定 (BLE 模式下连接即绑定)"""
        return not self.connected

    def get_qrcode(self, uri: str = None) -> None:
        """DG-Lab 兼容: 获取二维码 (BLE 模式不适用，始终返回 None)"""
        return None

    async def register(self):
        """DG-Lab 兼容: 注册终端 (BLE 模式下无需操作)"""
        pass

    async def bind(self) -> RetCode:
        """DG-Lab 兼容: 等待绑定 (BLE 模式下连接即绑定)"""
        if self.connected:
            return RetCode.SUCCESS
        return RetCode.CLIENT_DISCONNECTED

    async def rebind(self) -> RetCode:
        """DG-Lab 兼容: 重新绑定 (BLE 模式下等同于 bind)"""
        return await self.bind()

    async def ensure_bind(self):
        """DG-Lab 兼容: 确保绑定 (BLE 模式下无需操作)"""
        pass

    @property
    def strength_data(self) -> StrengthData:
        """
        DG-Lab 兼容: 获取当前强度数据

        :return: 包含 A/B 通道强度和上限的数据
        """
        return StrengthData(
            a=map_strength_to_dglab(self._channel_a_strength) if self._channel_a_enabled else 0,
            b=map_strength_to_dglab(self._channel_b_strength) if self._channel_b_enabled else 0,
            a_limit=self._strength_limit,
            b_limit=self._strength_limit
        )

    # ==================== 连接管理 ====================

    @property
    def connected(self) -> bool:
        """是否已连接"""
        return self._connected and self._client is not None and self._client.is_connected

    async def connect(self) -> bool:
        """
        连接到 BLE 设备

        :return: 是否连接成功
        """
        if self.connected:
            return True

        self._client = BleakClient(
            self._device_address,
            disconnected_callback=self._on_disconnect
        )
        try:
            await self._client.connect()
            self._connected = True
            logger.info(f"BLE 设备已连接: {self._device_address}")

            # 启动通知
            await self._client.start_notify(NOTIFY_CHAR_UUID, self._notification_handler)

            # 初始化波形播放器
            self._waveform_player_a = _WaveformPlayer(self, Channel.A)
            self._waveform_player_b = _WaveformPlayer(self, Channel.B)

            return True
        except Exception as e:
            logger.error(f"BLE 连接失败: {type(e).__name__}: {e}")
            self._connected = False
            return False

    def _on_disconnect(self, client: BleakClient):
        """BLE 设备断开连接回调"""
        logger.warning(f"BLE 设备已断开连接: {self._device_address}")
        self._connected = False

    async def disconnect(self):
        """断开 BLE 连接"""
        # 停止波形播放器
        if self._waveform_player_a:
            await self._waveform_player_a.stop()
        if self._waveform_player_b:
            await self._waveform_player_b.stop()

        if self._client:
            try:
                await self._client.disconnect()
            except Exception:
                pass
        self._connected = False

    async def __aenter__(self) -> "YCYBLEClient":
        await self.connect()
        if not self.connected:
            raise BLEError(f"Failed to connect to device: {self._device_address}")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()

    def _notification_handler(self, sender: int, data: bytearray):
        """BLE 通知处理"""
        self._notification_queue.put_nowait(bytes(data))

    async def _send_command(self, command: bytes) -> bool:
        """
        发送命令到设备

        :param command: 命令字节
        :return: 是否发送成功
        """
        if not self.connected:
            raise DisconnectedError()

        try:
            await self._client.write_gatt_char(WRITE_CHAR_UUID, command, response=False)
            return True
        except Exception:
            return False

    async def _wait_response(self, timeout: float = 1.0) -> Optional[YCYResponse]:
        """
        等待设备响应

        :param timeout: 超时时间 (秒)
        :return: 响应对象
        """
        try:
            data = await asyncio.wait_for(self._notification_queue.get(), timeout=timeout)
            return YCYBLEProtocol.parse_response(data)
        except asyncio.TimeoutError:
            return None

    # ==================== DG-Lab 兼容接口 ====================

    async def set_strength(
        self,
        channel: Channel,
        operation_type: StrengthOperationType,
        value: int
    ) -> bool:
        """
        设置强度 (DG-Lab 兼容接口)

        :param channel: 通道选择 (Channel.A 或 Channel.B)
        :param operation_type: 操作类型 (增加/减少/设定)
        :param value: 强度值 (DG-Lab 范围 0-200)
        :return: 是否成功
        """
        if not self.connected:
            raise DisconnectedError()

        # 获取当前 DG-Lab 强度
        if channel == Channel.A:
            current_dglab = map_strength_to_dglab(self._channel_a_strength) if self._channel_a_enabled else 0
        else:
            current_dglab = map_strength_to_dglab(self._channel_b_strength) if self._channel_b_enabled else 0

        # 计算新的 DG-Lab 强度
        if operation_type == StrengthOperationType.SET_TO:
            new_dglab = value
        elif operation_type == StrengthOperationType.INCREASE:
            new_dglab = current_dglab + value
        elif operation_type == StrengthOperationType.DECREASE:
            new_dglab = current_dglab - value
        else:
            new_dglab = value

        # 限制范围
        new_dglab = max(0, min(self._strength_limit, new_dglab))

        # 转换为役次元强度
        enabled, ycy_strength = map_strength_to_ycy(new_dglab)

        # 更新缓存
        if channel == Channel.A:
            self._channel_a_strength = ycy_strength
            self._channel_a_enabled = enabled
            ycy_channel = YCYChannel.A
            current_mode = self._channel_a_mode
        else:
            self._channel_b_strength = ycy_strength
            self._channel_b_enabled = enabled
            ycy_channel = YCYChannel.B
            current_mode = self._channel_b_mode

        # 构建并发送命令，保持当前预设模式
        command = YCYBLEProtocol.build_channel_control(
            channel=ycy_channel,
            enabled=enabled,
            strength=ycy_strength,
            mode=current_mode,  # 保持当前预设模式
            frequency=0,
            pulse_width=0
        )

        logger.info(f"set_strength: channel={channel}, strength={ycy_strength}, mode={current_mode.name}, cmd={command.hex()}")
        return await self._send_command(command)

    async def add_pulses(
        self,
        channel: Channel,
        *pulses: PulseOperation
    ) -> bool:
        """
        添加波形到队列 (DG-Lab 兼容接口)

        波形会被转换为役次元自定义模式并通过软件队列播放。

        :param channel: 通道选择
        :param pulses: 波形数据 (每条 100ms)
        :return: 是否成功
        """
        if not self.connected:
            raise DisconnectedError()

        player = self._waveform_player_a if channel == Channel.A else self._waveform_player_b
        if player:
            await player.add(*pulses)
            return True
        return False

    async def clear_pulses(self, channel: Channel) -> bool:
        """
        清空波形队列 (DG-Lab 兼容接口)

        :param channel: 通道选择
        :return: 是否成功
        """
        if not self.connected:
            raise DisconnectedError()

        player = self._waveform_player_a if channel == Channel.A else self._waveform_player_b
        if player:
            await player.clear()
            return True
        return False

    async def recv_data(self) -> Union[StrengthData, RetCode]:
        """
        接收数据 (DG-Lab 兼容接口)

        :return: 强度数据或状态码
        """
        if not self.connected:
            raise DisconnectedError()

        try:
            data = await asyncio.wait_for(self._notification_queue.get(), timeout=1.0)
            response = YCYBLEProtocol.parse_response(data, verify_checksum=False)

            if response and response.response_type in (
                YCYQueryType.CHANNEL_A_STATUS,
                YCYQueryType.CHANNEL_B_STATUS
            ):
                # 更新缓存
                status = response.channel_status
                if response.response_type == YCYQueryType.CHANNEL_A_STATUS:
                    self._channel_a_strength = status.strength
                    self._channel_a_enabled = status.enabled
                else:
                    self._channel_b_strength = status.strength
                    self._channel_b_enabled = status.enabled

                # 返回 DG-Lab 格式的强度数据
                return StrengthData(
                    a=map_strength_to_dglab(self._channel_a_strength) if self._channel_a_enabled else 0,
                    b=map_strength_to_dglab(self._channel_b_strength) if self._channel_b_enabled else 0,
                    a_limit=self._strength_limit,
                    b_limit=self._strength_limit
                )

            return RetCode.SUCCESS
        except asyncio.TimeoutError:
            return RetCode.SUCCESS

    async def data_generator(
        self,
        *targets: _DataType,
        poll_interval: float = 1.0,
    ) -> AsyncGenerator[Union[StrengthData, RetCode], Any]:
        """
        数据生成器 (DG-Lab 兼容接口)

        定期轮询设备状态并返回 StrengthData，与 WebSocket 版本行为一致。

        :param targets: 目标类型过滤
        :param poll_interval: 轮询间隔 (秒)
        :yield: 强度数据或状态码
        """
        while True:
            if not self.connected:
                yield RetCode.CLIENT_DISCONNECTED
                break

            try:
                # 返回当前强度数据
                data = self.strength_data
                if not targets or type(data) in targets:
                    yield data

                # 等待下次轮询
                await asyncio.sleep(poll_interval)

            except Exception:
                yield RetCode.CLIENT_DISCONNECTED
                break

    # ==================== 役次元扩展接口 ====================

    async def get_battery(self) -> int:
        """
        获取电池电量

        :return: 电量百分比 (0-100)
        """
        if not self.connected:
            raise DisconnectedError()

        command = YCYBLEProtocol.build_query(YCYQueryType.BATTERY)
        await self._send_command(command)

        response = await self._wait_response()
        if response and response.battery is not None:
            return response.battery
        return -1

    async def set_motor(self, state: MotorState) -> bool:
        """
        控制马达

        :param state: 马达状态
        :return: 是否成功
        """
        if not self.connected:
            raise DisconnectedError()

        command = YCYBLEProtocol.build_motor_control(state)
        return await self._send_command(command)

    async def get_electrode_status(self, channel: Channel) -> ElectrodeStatus:
        """
        获取电极连接状态

        :param channel: 通道选择
        :return: 电极状态
        """
        if not self.connected:
            raise DisconnectedError()

        query_type = YCYQueryType.CHANNEL_A_STATUS if channel == Channel.A else YCYQueryType.CHANNEL_B_STATUS
        command = YCYBLEProtocol.build_query(query_type)
        await self._send_command(command)

        response = await self._wait_response()
        if response and response.channel_status:
            return response.channel_status.electrode_status
        return ElectrodeStatus.NOT_CONNECTED

    async def get_channel_status(self, channel: Channel) -> Optional[YCYChannelStatus]:
        """
        获取通道完整状态

        :param channel: 通道选择
        :return: 通道状态
        """
        if not self.connected:
            raise DisconnectedError()

        query_type = YCYQueryType.CHANNEL_A_STATUS if channel == Channel.A else YCYQueryType.CHANNEL_B_STATUS
        command = YCYBLEProtocol.build_query(query_type)
        await self._send_command(command)

        response = await self._wait_response()
        if response:
            return response.channel_status
        return None

    async def set_mode(self, channel: Channel, mode: YCYMode) -> bool:
        """
        设置通道模式 (16 种预设模式)

        :param channel: 通道选择
        :param mode: 模式
        :return: 是否成功
        """
        if not self.connected:
            raise DisconnectedError()

        ycy_channel = YCYChannel.A if channel == Channel.A else YCYChannel.B

        # 获取当前强度
        if channel == Channel.A:
            strength = self._channel_a_strength
            enabled = self._channel_a_enabled
        else:
            strength = self._channel_b_strength
            enabled = self._channel_b_enabled

        command = YCYBLEProtocol.build_channel_control(
            channel=ycy_channel,
            enabled=enabled,
            strength=strength,
            mode=mode,
            frequency=0,
            pulse_width=0
        )

        return await self._send_command(command)

    async def set_pulse_preset(self, channel: Channel, preset_index: int) -> bool:
        """
        设置通道波形预设 (使用 DG-Lab 预设索引)

        将 DG-Lab 预设索引映射到 YCY 内置预设模式，设备会自动循环播放该预设波形。
        这种方式比自定义模式更稳定，不需要持续发送波形数据。

        :param channel: 通道选择
        :param preset_index: DG-Lab 预设索引 (0-15)
            0=呼吸, 1=潮汐, 2=连击, 3=快速按捏, 4=按捏渐强, 5=心跳节奏,
            6=压缩, 7=节奏步伐, 8=颗粒摩擦, 9=渐变弹跳, 10=波浪涟漪,
            11=雨水冲刷, 12=变速敲击, 13=信号灯, 14=挑逗1, 15=挑逗2
        :return: 是否成功
        """
        if not self.connected:
            logger.warning(f"set_pulse_preset: 设备未连接")
            raise DisconnectedError()

        from ..ble.utils import dglab_preset_to_ycy_mode

        ycy_mode = dglab_preset_to_ycy_mode(preset_index)
        ycy_channel = YCYChannel.A if channel == Channel.A else YCYChannel.B

        # 更新模式缓存（即使强度为0也要记住模式，下次设置强度时会使用）
        if channel == Channel.A:
            self._channel_a_mode = ycy_mode
            strength = self._channel_a_strength
            enabled = self._channel_a_enabled
        else:
            self._channel_b_mode = ycy_mode
            strength = self._channel_b_strength
            enabled = self._channel_b_enabled

        logger.info(f"set_pulse_preset: 已缓存模式 channel={channel}, mode={ycy_mode.name}")

        # 如果通道未启用，只缓存模式不发送命令（下次设置强度时会带上模式）
        if not enabled or strength <= 1:
            logger.info(f"set_pulse_preset: 仅缓存模式，跳过发送 (enabled={enabled}, strength={strength})")
            return True

        command = YCYBLEProtocol.build_channel_control(
            channel=ycy_channel,
            enabled=True,
            strength=strength,
            mode=ycy_mode,
            frequency=0,
            pulse_width=0
        )

        logger.info(f"set_pulse_preset: channel={channel}, preset={preset_index}, mode={ycy_mode.name}, strength={strength}, cmd={command.hex()}")
        return await self._send_command(command)

    async def set_custom_wave(
        self,
        channel: Channel,
        frequency: int,
        pulse_width: int
    ) -> bool:
        """
        设置自定义波形

        :param channel: 通道选择
        :param frequency: 频率 (1-100 Hz)
        :param pulse_width: 脉冲宽度 (0-100 us)
        :return: 是否成功
        """
        if not self.connected:
            logger.warning(f"set_custom_wave: 设备未连接")
            raise DisconnectedError()

        ycy_channel = YCYChannel.A if channel == Channel.A else YCYChannel.B

        # 获取当前强度
        if channel == Channel.A:
            strength = self._channel_a_strength
            enabled = self._channel_a_enabled
        else:
            strength = self._channel_b_strength
            enabled = self._channel_b_enabled

        # 如果通道未启用（强度为0），跳过发送
        if not enabled or strength <= 1:
            # 每 50 次记录一次跳过日志，避免刷屏
            if not hasattr(self, '_skip_count'):
                self._skip_count = {}
            ch_key = str(channel)
            self._skip_count[ch_key] = self._skip_count.get(ch_key, 0) + 1
            if self._skip_count[ch_key] % 50 == 1:
                logger.info(f"set_custom_wave: 跳过发送 (通道={channel}, enabled={enabled}, strength={strength}, 已跳过{self._skip_count[ch_key]}次)")
            return True  # 返回成功但不发送命令

        command = YCYBLEProtocol.build_channel_control(
            channel=ycy_channel,
            enabled=enabled,
            strength=strength,
            mode=YCYMode.CUSTOM,
            frequency=frequency,
            pulse_width=pulse_width
        )

        # 每 10 次记录一次发送日志
        if not hasattr(self, '_send_count'):
            self._send_count = {}
        ch_key = str(channel)
        self._send_count[ch_key] = self._send_count.get(ch_key, 0) + 1
        if self._send_count[ch_key] % 10 == 1:
            logger.info(f"set_custom_wave: 发送命令 channel={channel}, strength={strength}, freq={frequency}, pw={pulse_width}, cmd={command.hex()}")

        return await self._send_command(command)

    async def set_ycy_strength(
        self,
        channel: Channel,
        strength: int,
        mode: YCYMode = YCYMode.CUSTOM,
        frequency: int = 50,
        pulse_width: int = 50
    ) -> bool:
        """
        直接设置役次元强度

        :param channel: 通道选择
        :param strength: 强度 (1-276)
        :param mode: 模式
        :param frequency: 频率 (自定义模式)
        :param pulse_width: 脉冲宽度 (自定义模式)
        :return: 是否成功
        """
        if not self.connected:
            raise DisconnectedError()

        ycy_channel = YCYChannel.A if channel == Channel.A else YCYChannel.B
        enabled = strength > 0

        # 更新缓存
        if channel == Channel.A:
            self._channel_a_strength = strength
            self._channel_a_enabled = enabled
        else:
            self._channel_b_strength = strength
            self._channel_b_enabled = enabled

        command = YCYBLEProtocol.build_channel_control(
            channel=ycy_channel,
            enabled=enabled,
            strength=max(1, strength),
            mode=mode,
            frequency=frequency,
            pulse_width=pulse_width
        )

        return await self._send_command(command)

    async def stop_channel(self, channel: Channel) -> bool:
        """
        停止通道输出

        :param channel: 通道选择
        :return: 是否成功
        """
        if not self.connected:
            raise DisconnectedError()

        # 停止该通道的波形播放器
        if channel == Channel.A and self._waveform_player_a:
            await self._waveform_player_a.stop()
            await self._waveform_player_a.clear()
        elif channel == Channel.B and self._waveform_player_b:
            await self._waveform_player_b.stop()
            await self._waveform_player_b.clear()

        ycy_channel = YCYChannel.A if channel == Channel.A else YCYChannel.B

        # 更新缓存
        if channel == Channel.A:
            self._channel_a_enabled = False
        else:
            self._channel_b_enabled = False

        # 注意: mode 必须是有效值 (0x01-0x10 或 0x11), 不能用 0x00
        command = YCYBLEProtocol.build_channel_control(
            channel=ycy_channel,
            enabled=False,
            strength=1,
            mode=YCYMode.PRESET_1,  # 使用有效模式
            frequency=0,
            pulse_width=0
        )

        return await self._send_command(command)

    async def stop_all(self) -> bool:
        """
        停止所有输出 (双通道 + 马达)

        :return: 是否成功
        """
        if not self.connected:
            raise DisconnectedError()

        # 停止波形播放器
        if self._waveform_player_a:
            await self._waveform_player_a.stop()
            await self._waveform_player_a.clear()
        if self._waveform_player_b:
            await self._waveform_player_b.stop()
            await self._waveform_player_b.clear()

        # 更新缓存
        self._channel_a_enabled = False
        self._channel_b_enabled = False

        # 停止 A 通道
        cmd_a = YCYBLEProtocol.build_channel_control(
            channel=YCYChannel.A,
            enabled=False,
            strength=1,
            mode=YCYMode.PRESET_1,
            frequency=0,
            pulse_width=0
        )
        await self._send_command(cmd_a)

        # 停止 B 通道
        cmd_b = YCYBLEProtocol.build_channel_control(
            channel=YCYChannel.B,
            enabled=False,
            strength=1,
            mode=YCYMode.PRESET_1,
            frequency=0,
            pulse_width=0
        )
        await self._send_command(cmd_b)

        # 停止马达
        cmd_motor = YCYBLEProtocol.build_motor_control(MotorState.OFF)
        await self._send_command(cmd_motor)

        return True

    # ==================== 静态方法 ====================

    @staticmethod
    async def scan(timeout: float = 5.0):
        """
        扫描役次元设备

        :param timeout: 扫描超时 (秒)
        :return: 设备列表
        """
        return await YCYScanner.scan(timeout=timeout)


class _WaveformPlayer:
    """
    波形播放器 - 软件模拟 DG-Lab 波形队列

    将 DG-Lab 波形数据转换为役次元自定义模式并播放。
    """

    def __init__(self, client: YCYBLEClient, channel: Channel):
        self._client = client
        self._channel = channel
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=500)
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def add(self, *pulses: PulseOperation):
        """添加波形到队列"""
        added_count = 0
        for pulse in pulses:
            freq, pulse_width = convert_pulse(pulse)
            try:
                self._queue.put_nowait((freq, pulse_width))
                added_count += 1
            except asyncio.QueueFull:
                # 队列满时丢弃
                pass

        logger.info(f"波形队列 {self._channel}: 添加了 {added_count} 条波形, 队列大小: {self._queue.qsize()}, 播放器运行中: {self._running}")

        # 确保播放器在运行
        if not self._running:
            logger.info(f"波形播放器 {self._channel} 未运行，正在启动...")
            await self.start()

    async def clear(self):
        """清空队列"""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    async def start(self):
        """启动播放"""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._playback_loop())

    async def stop(self):
        """停止播放"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _playback_loop(self):
        """播放循环 - 每 100ms 下发一次"""
        logger.info(f"波形播放器 {self._channel} 已启动")
        play_count = 0
        while self._running:
            try:
                freq, pulse_width = await asyncio.wait_for(
                    self._queue.get(), timeout=0.1
                )
                play_count += 1
                if play_count % 10 == 1:  # 每10次记录一次
                    logger.info(f"播放波形 {self._channel}: freq={freq}, pulse_width={pulse_width}, 已播放{play_count}次")
                result = await self._client.set_custom_wave(
                    self._channel, freq, pulse_width
                )
                if not result:
                    logger.warning(f"波形播放器 {self._channel}: set_custom_wave 返回 False")
                await asyncio.sleep(0.1)  # 100ms 间隔
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                logger.info(f"波形播放器 {self._channel} 被取消")
                break
            except Exception as e:
                logger.error(f"波形播放器 {self._channel} 异常: {type(e).__name__}: {e}")
                import traceback
                logger.error(traceback.format_exc())
                continue
        logger.info(f"波形播放器 {self._channel} 已停止, 共播放 {play_count} 次")
