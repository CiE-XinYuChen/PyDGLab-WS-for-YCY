"""
役次元 BLE 工具函数
"""
from typing import Tuple

from ..typing import PulseOperation

__all__ = (
    "map_strength_to_ycy",
    "map_strength_to_dglab",
    "convert_pulse",
)


def map_strength_to_ycy(dglab_strength: int) -> Tuple[bool, int]:
    """
    将 DG-Lab 强度映射到役次元强度

    DG-Lab: 0-200
    役次元: 1-276 (0 表示关闭通道)

    :param dglab_strength: DG-Lab 强度值 (0-200)
    :return: (是否开启通道, 役次元强度值)
    """
    if dglab_strength <= 0:
        return (False, 1)  # 关闭通道，强度默认为 1

    # 1-200 映射到 1-276
    ycy_strength = int(dglab_strength * 275 / 200) + 1
    return (True, min(ycy_strength, 276))


def map_strength_to_dglab(ycy_strength: int) -> int:
    """
    将役次元强度映射到 DG-Lab 强度

    役次元: 1-276
    DG-Lab: 0-200

    :param ycy_strength: 役次元强度值 (1-276)
    :return: DG-Lab 强度值 (0-200)
    """
    if ycy_strength <= 1:
        return 0
    return int((ycy_strength - 1) * 200 / 275)


def convert_pulse(pulse: PulseOperation) -> Tuple[int, int]:
    """
    将 DG-Lab 波形数据转换为役次元自定义模式参数

    DG-Lab 波形格式:
        ((freq1, freq2, freq3, freq4), (str1, str2, str3, str4))
        - 频率: 10-240 (每 25ms 一个值)
        - 强度: 0-100 (百分比)

    役次元自定义模式:
        - 频率: 1-100 Hz
        - 脉冲宽度: 0-100 us

    转换规则:
        - 频率: 取 4 个频率值的平均，clamp 到 1-100
        - 脉冲宽度: 取 4 个强度百分比的平均 (直接作为脉冲宽度 0-100us)

    :param pulse: DG-Lab 波形操作数据
    :return: (频率, 脉冲宽度)
    """
    frequencies, strengths = pulse

    # 频率取平均，clamp 到 1-100
    freq = sum(frequencies) // 4
    freq = max(1, min(100, freq))

    # 强度百分比取平均，作为脉冲宽度 (0-100us)
    pulse_width = sum(strengths) // 4

    return (freq, pulse_width)
