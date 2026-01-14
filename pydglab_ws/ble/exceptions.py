"""
役次元 BLE 相关异常定义
"""

__all__ = (
    "BLEError",
    "DisconnectedError",
    "DeviceNotFoundError",
    "ChecksumError",
)


class BLEError(Exception):
    """BLE 通用异常基类"""
    pass


class DisconnectedError(BLEError):
    """设备断连异常"""

    def __init__(self, message: str = "BLE device disconnected"):
        super().__init__(message)


class DeviceNotFoundError(BLEError):
    """设备未找到异常"""

    def __init__(self, device_address: str = None):
        if device_address:
            message = f"BLE device not found: {device_address}"
        else:
            message = "No YCY BLE device found"
        super().__init__(message)


class ChecksumError(BLEError):
    """校验和错误异常"""

    def __init__(self, expected: int, actual: int):
        super().__init__(f"Checksum error: expected 0x{expected:02X}, got 0x{actual:02X}")
        self.expected = expected
        self.actual = actual
