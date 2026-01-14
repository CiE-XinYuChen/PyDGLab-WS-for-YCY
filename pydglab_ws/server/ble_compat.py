"""
DGLabWSServer 兼容层

提供与 DGLabWSServer 相同的接口，但内部使用 BLE 直连。
使用独立线程运行 BLE 以兼容 qasync 等特殊事件循环。
"""
import asyncio
import logging
import threading
import queue
from typing import Optional, List, Callable, Any, Union

from ..client import YCYBLEClient
from ..ble import YCYScanner, YCYDevice
from ..enums import Channel, StrengthOperationType, RetCode
from ..models import StrengthData
from ..typing import PulseOperation

__all__ = ("DGLabBLEServer",)

logger = logging.getLogger(__name__)


class BLEThread(threading.Thread):
    """独立的 BLE 线程，运行自己的事件循环"""

    def __init__(self, scan_timeout: float, strength_limit: int, device_address: str = None):
        super().__init__(daemon=True)
        self._scan_timeout = scan_timeout
        self._strength_limit = strength_limit
        self._device_address = device_address
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._client: Optional[YCYBLEClient] = None
        self._ready = threading.Event()
        self._error: Optional[Exception] = None
        self._devices: List[YCYDevice] = []
        self._should_stop = False  # 显式停止标志

    def run(self):
        """线程主函数"""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._connect())
            self._ready.set()
            logger.info("BLE 线程: run_forever() 开始运行")
            # 保持事件循环运行
            while True:
                try:
                    self._loop.run_forever()
                    # 如果 run_forever() 正常退出 (被 stop() 调用)，检查是否应该继续
                    if self._should_stop:
                        logger.info("BLE 线程: run_forever() 因 stop() 调用而退出")
                        break
                    else:
                        # 意外退出，重新启动 run_forever()
                        logger.warning("BLE 线程: run_forever() 意外退出，正在重启...")
                except Exception as inner_e:
                    logger.error(f"BLE 线程 run_forever 异常: {type(inner_e).__name__}: {inner_e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    # 短暂等待后重试
                    import time
                    time.sleep(0.1)
        except Exception as e:
            logger.error(f"BLE 线程异常: {type(e).__name__}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self._error = e
            self._ready.set()
        # 不关闭 loop，让 daemon 线程自动清理
        logger.info("BLE 线程: 主循环退出，但不关闭 loop")

    async def _connect(self):
        """连接 BLE 设备"""
        if self._device_address:
            self._client = YCYBLEClient(
                self._device_address,
                strength_limit=self._strength_limit
            )
        else:
            logger.info("正在扫描役次元设备...")
            self._devices = await YCYScanner.scan(timeout=self._scan_timeout)

            if not self._devices:
                raise RuntimeError("未找到役次元设备，请确认设备已开机")

            device = self._devices[0]
            logger.info(f"找到设备: {device}, 正在连接...")

            self._client = YCYBLEClient(
                device,
                strength_limit=self._strength_limit
            )

        success = await self._client.connect()
        if not success:
            raise RuntimeError("BLE 连接失败")

        logger.info("BLE 设备已连接")

    def run_coro(self, coro, timeout: float = 5.0):
        """在 BLE 线程中运行协程并返回结果（阻塞）"""
        if not self._loop or self._loop.is_closed():
            # 协程需要关闭以避免警告
            coro.close()
            logger.error("run_coro: BLE loop 不可用或已关闭")
            return False
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        try:
            return future.result(timeout=timeout)
        except Exception as e:
            logger.error(f"BLE 操作失败: {e}")
            return False

    def fire_and_forget(self, coro):
        """在 BLE 线程中运行协程（非阻塞，不等待结果）"""
        if self._should_stop:
            logger.warning(f"fire_and_forget: BLE 线程已标记停止")
            coro.close()
            return False
        if not self._loop:
            logger.warning(f"fire_and_forget: BLE loop 为 None")
            coro.close()
            return False
        if self._loop.is_closed():
            logger.error(f"fire_and_forget: BLE loop 已关闭，无法恢复")
            coro.close()
            return False
        # 即使 loop 暂时不运行也尝试提交，因为 run() 会自动重启 run_forever()
        try:
            asyncio.run_coroutine_threadsafe(coro, self._loop)
            return True
        except Exception as e:
            logger.error(f"fire_and_forget 失败: {type(e).__name__}: {e}")
            coro.close()
            return False

    def stop(self):
        """停止 BLE 线程"""
        import traceback
        logger.info(f"BLEThread.stop() 被调用")
        logger.info(f"stop() 调用栈:\n{''.join(traceback.format_stack())}")
        self._should_stop = True  # 设置停止标志
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)


class BLEClientProxy:
    """BLE 客户端代理，在主线程中使用，操作转发到 BLE 线程"""

    def __init__(self, ble_thread: BLEThread):
        self._ble_thread = ble_thread
        self._client = ble_thread._client

    @property
    def client_id(self):
        return self._client.client_id

    @property
    def target_id(self):
        return self._client.target_id

    @property
    def not_registered(self) -> bool:
        return self._client.not_registered

    @property
    def not_bind(self) -> bool:
        return self._client.not_bind

    @property
    def connected(self) -> bool:
        return self._client.connected

    @property
    def strength_data(self) -> StrengthData:
        return self._client.strength_data

    def get_qrcode(self, uri: str) -> Optional[str]:
        """BLE 模式不需要二维码"""
        return None

    async def bind(self) -> RetCode:
        return RetCode.SUCCESS

    async def rebind(self) -> RetCode:
        """BLE 模式下重连"""
        logger.info("BLE 重连中...")
        return RetCode.SUCCESS

    async def ensure_bind(self):
        pass

    async def set_strength(
        self,
        channel: Channel,
        operation_type: StrengthOperationType,
        value: int
    ) -> bool:
        # 使用非阻塞方式，避免卡住主事件循环
        return self._ble_thread.fire_and_forget(
            self._client.set_strength(channel, operation_type, value)
        )

    async def add_pulses(self, channel: Channel, *pulses: PulseOperation) -> bool:
        # 在添加前先清空旧波形，合并为一个原子操作
        logger.info(f"BLEClientProxy.add_pulses: channel={channel}, pulses数量={len(pulses)}")
        async def _clear_and_add():
            try:
                logger.info(f"_clear_and_add 开始执行: channel={channel}, client.connected={self._client.connected}")
                logger.info(f"_clear_and_add: waveform_player_a={self._client._waveform_player_a}, waveform_player_b={self._client._waveform_player_b}")
                await self._client.clear_pulses(channel)
                logger.info(f"_clear_and_add: clear_pulses 完成")
                await self._client.add_pulses(channel, *pulses)
                logger.info(f"_clear_and_add 执行完成: channel={channel}")
                return True
            except Exception as e:
                logger.error(f"_clear_and_add 异常: {type(e).__name__}: {e}")
                import traceback
                logger.error(traceback.format_exc())
                return False
        result = self._ble_thread.fire_and_forget(_clear_and_add())
        logger.info(f"BLEClientProxy.add_pulses: fire_and_forget 返回 {result}")
        return result

    async def clear_pulses(self, channel: Channel) -> bool:
        # clear_pulses 现在是 no-op，因为 add_pulses 会自动清空
        # 保留方法以保持接口兼容
        return True

    async def set_pulse_preset(self, channel: Channel, preset_index: int) -> bool:
        """
        设置通道波形预设 (推荐方式)

        直接使用 YCY 内置预设模式，设备会自动循环播放波形。
        比 add_pulses 更稳定，不需要持续发送数据。

        :param channel: 通道选择
        :param preset_index: DG-Lab 预设索引 (0-15)
        :return: 是否成功
        """
        logger.info(f"BLEClientProxy.set_pulse_preset: channel={channel}, preset_index={preset_index}")
        return self._ble_thread.fire_and_forget(
            self._client.set_pulse_preset(channel, preset_index)
        )

    async def stop_all(self) -> bool:
        # stop_all 需要等待确认
        return self._ble_thread.run_coro(
            self._client.stop_all()
        )

    async def data_generator(self, *targets, poll_interval: float = 1.0):
        """数据生成器"""
        while True:
            if not self._client.connected:
                yield RetCode.CLIENT_DISCONNECTED
                break

            yield self._client.strength_data
            await asyncio.sleep(poll_interval)


class DGLabBLEServer:
    """
    DGLabWSServer 兼容层 - 使用 BLE 直连代替 WebSocket

    :param device_address: 指定设备地址，如果为 None 则自动扫描
    :param scan_timeout: 扫描超时时间 (秒)
    :param strength_limit: 虚拟强度上限
    :param host: 忽略 (兼容参数)
    :param port: 忽略 (兼容参数)
    :param heartbeat_interval: 忽略 (兼容参数)
    """

    def __init__(
        self,
        host: str = None,
        port: int = None,
        heartbeat_interval: float = None,
        device_address: Optional[str] = None,
        scan_timeout: float = 10.0,
        strength_limit: int = 200,
        **kwargs
    ):
        self._device_address = device_address
        self._scan_timeout = scan_timeout
        self._strength_limit = strength_limit
        self._ble_thread: Optional[BLEThread] = None
        self._client_proxy: Optional[BLEClientProxy] = None

    async def __aenter__(self) -> "DGLabBLEServer":
        """启动 BLE 线程并连接设备"""
        self._ble_thread = BLEThread(
            self._scan_timeout,
            self._strength_limit,
            self._device_address
        )
        self._ble_thread.start()

        # 等待连接完成
        self._ble_thread._ready.wait(timeout=self._scan_timeout + 15)

        if self._ble_thread._error:
            raise self._ble_thread._error

        if not self._ble_thread._client:
            raise RuntimeError("BLE 连接失败")

        self._client_proxy = BLEClientProxy(self._ble_thread)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """停止 BLE 线程"""
        # BLE 线程使用 daemon=True，当主进程退出时会自动清理
        # 这里不主动停止 BLE 线程，避免 qasync 任务冲突导致意外关闭
        # 只在显式调用 stop() 时才停止
        logger.info(f"__aexit__ 被调用: exc_type={exc_type}, 不停止 BLE 线程")
        pass  # 不做任何清理，让 daemon 线程自动退出

    def new_local_client(self, max_queue: int = 32) -> BLEClientProxy:
        """获取 BLE 客户端代理"""
        if not self._client_proxy:
            raise RuntimeError("服务器未启动")
        return self._client_proxy

    @property
    def heartbeat_interval(self) -> Optional[float]:
        return None

    @heartbeat_interval.setter
    def heartbeat_interval(self, value: float):
        pass

    @property
    def heartbeat_enabled(self) -> bool:
        return False
