"""
役次元 BLE 设备扫描器
"""
from typing import List, Optional

from bleak import BleakScanner
from bleak.backends.device import BLEDevice

from .models import YCYDevice

__all__ = ("YCYScanner",)

# 役次元设备服务 UUID
SERVICE_UUID = "0000ff30-0000-1000-8000-00805f9b34fb"


class YCYScanner:
    """
    役次元 BLE 设备扫描器

    通过服务 UUID 过滤役次元设备
    """

    @staticmethod
    async def scan(timeout: float = 5.0) -> List[YCYDevice]:
        """
        扫描役次元 BLE 设备

        :param timeout: 扫描超时时间 (秒)
        :return: 发现的役次元设备列表
        """
        devices = await BleakScanner.discover(timeout=timeout, return_adv=True)

        ycy_devices = []
        for device, adv_data in devices.values():
            # 检查服务 UUID
            service_uuids = adv_data.service_uuids or []
            if SERVICE_UUID.lower() in [uuid.lower() for uuid in service_uuids]:
                ycy_devices.append(YCYDevice(
                    address=device.address,
                    name=device.name,
                    rssi=adv_data.rssi
                ))

        return ycy_devices

    @staticmethod
    async def find_device(
        address: Optional[str] = None,
        name: Optional[str] = None,
        timeout: float = 5.0
    ) -> Optional[YCYDevice]:
        """
        查找指定的役次元设备

        :param address: 设备地址
        :param name: 设备名称
        :param timeout: 扫描超时时间 (秒)
        :return: 找到的设备，未找到返回 None
        """
        devices = await YCYScanner.scan(timeout=timeout)

        for device in devices:
            if address and device.address.lower() == address.lower():
                return device
            if name and device.name and name.lower() in device.name.lower():
                return device

        # 如果没有指定条件，返回第一个设备
        if not address and not name and devices:
            return devices[0]

        return None
