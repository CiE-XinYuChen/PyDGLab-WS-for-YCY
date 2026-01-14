"""
役次元 BLE 工具函数
"""
from typing import Tuple

from ..typing import PulseOperation
from .enums import YCYMode

__all__ = (
    "map_strength_to_ycy",
    "map_strength_to_dglab",
    "convert_pulse",
    "dglab_preset_to_ycy_mode",
    "DGLAB_PRESET_TO_YCY",
)

# DG-Lab 预设索引 (0-15) 到 YCY 预设模式的映射
# DG-Lab 预设: 呼吸, 潮汐, 连击, 快速按捏, 按捏渐强, 心跳节奏, 压缩, 节奏步伐,
#              颗粒摩擦, 渐变弹跳, 波浪涟漪, 雨水冲刷, 变速敲击, 信号灯, 挑逗1, 挑逗2
# YCY 预设: PRESET_1 到 PRESET_16
# 暂时做 1:1 索引映射，后续可根据实际效果调整
DGLAB_PRESET_TO_YCY = {
    0: YCYMode.PRESET_1,   # 呼吸
    1: YCYMode.PRESET_2,   # 潮汐
    2: YCYMode.PRESET_3,   # 连击
    3: YCYMode.PRESET_4,   # 快速按捏
    4: YCYMode.PRESET_5,   # 按捏渐强
    5: YCYMode.PRESET_6,   # 心跳节奏
    6: YCYMode.PRESET_7,   # 压缩
    7: YCYMode.PRESET_8,   # 节奏步伐
    8: YCYMode.PRESET_9,   # 颗粒摩擦
    9: YCYMode.PRESET_10,  # 渐变弹跳
    10: YCYMode.PRESET_11, # 波浪涟漪
    11: YCYMode.PRESET_12, # 雨水冲刷
    12: YCYMode.PRESET_13, # 变速敲击
    13: YCYMode.PRESET_14, # 信号灯
    14: YCYMode.PRESET_15, # 挑逗1
    15: YCYMode.PRESET_16, # 挑逗2
}


def dglab_preset_to_ycy_mode(preset_index: int) -> YCYMode:
    """
    将 DG-Lab 预设索引转换为 YCY 预设模式

    :param preset_index: DG-Lab 预设索引 (0-15)
    :return: YCY 预设模式
    """
    return DGLAB_PRESET_TO_YCY.get(preset_index, YCYMode.PRESET_1)


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
        - 频率: 10-240 (DG-Lab 内部参数，非真实 Hz)
        - 强度: 0-100 (百分比，这是产生波形效果的关键)

    役次元自定义模式:
        - 频率: 1-100 Hz (脉冲重复率)
        - 脉冲宽度: 0-100 (占空比/强度)

    转换规则:
        - 频率: 固定使用 100Hz (高频脉冲效果更明显)
        - 脉冲宽度: 强度百分比直接使用 (0-100)

    波形效果主要通过强度百分比的动态变化实现，
    如"呼吸"预设通过强度从 0->100->0 的变化产生渐强渐弱效果。

    :param pulse: DG-Lab 波形操作数据
    :return: (频率, 脉冲宽度)
    """
    frequencies, strengths = pulse

    # 频率固定为 100Hz，让脉冲效果最明显
    freq = 100

    # 强度百分比取平均，作为脉冲宽度
    # 这是产生波形效果的关键参数
    pulse_width = sum(strengths) // 4

    return (freq, pulse_width)
