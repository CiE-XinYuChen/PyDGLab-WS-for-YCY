from .server import *
from .ble_compat import *

# 让 DGLabWSServer 指向 BLE 版本，实现零修改兼容
DGLabWSServer = DGLabBLEServer
