"""
役次元 BLE 强度/波形映射测试
"""
import pytest

from pydglab_ws.ble.utils import (
    map_strength_to_ycy,
    map_strength_to_dglab,
    convert_pulse,
)


class TestStrengthToYCY:
    """DG-Lab 强度 -> 役次元强度映射测试"""

    def test_zero_strength(self):
        """强度 0 映射为关闭"""
        enabled, strength = map_strength_to_ycy(0)
        assert enabled is False
        assert strength == 1  # 关闭时默认强度为 1

    def test_negative_strength(self):
        """负强度映射为关闭"""
        enabled, strength = map_strength_to_ycy(-10)
        assert enabled is False
        assert strength == 1

    def test_min_strength(self):
        """强度 1 映射"""
        enabled, strength = map_strength_to_ycy(1)
        assert enabled is True
        # 1 * 275 / 200 + 1 = 2.375 -> 2
        assert strength == 2

    def test_mid_strength(self):
        """强度 100 映射"""
        enabled, strength = map_strength_to_ycy(100)
        assert enabled is True
        # 100 * 275 / 200 + 1 = 138.5 -> 138
        assert strength == 138

    def test_max_strength(self):
        """强度 200 映射"""
        enabled, strength = map_strength_to_ycy(200)
        assert enabled is True
        # 200 * 275 / 200 + 1 = 276
        assert strength == 276

    def test_overflow_strength(self):
        """超过最大强度钳制"""
        enabled, strength = map_strength_to_ycy(300)
        assert enabled is True
        assert strength == 276  # 钳制到最大值

    def test_quarter_strength(self):
        """强度 50 映射"""
        enabled, strength = map_strength_to_ycy(50)
        assert enabled is True
        # 50 * 275 / 200 + 1 = 69.75 -> 69
        assert strength == 69

    def test_three_quarter_strength(self):
        """强度 150 映射"""
        enabled, strength = map_strength_to_ycy(150)
        assert enabled is True
        # 150 * 275 / 200 + 1 = 207.25 -> 207
        assert strength == 207


class TestStrengthToDGLab:
    """役次元强度 -> DG-Lab 强度映射测试"""

    def test_min_strength(self):
        """强度 1 映射为 0"""
        strength = map_strength_to_dglab(1)
        assert strength == 0

    def test_below_min_strength(self):
        """强度小于 1 映射为 0"""
        strength = map_strength_to_dglab(0)
        assert strength == 0

    def test_max_strength(self):
        """强度 276 映射为 200"""
        strength = map_strength_to_dglab(276)
        # (276 - 1) * 200 / 275 = 200
        assert strength == 200

    def test_mid_strength(self):
        """强度 138 映射"""
        strength = map_strength_to_dglab(138)
        # (138 - 1) * 200 / 275 = 99.6 -> 99
        assert strength == 99

    def test_strength_69(self):
        """强度 69 映射"""
        strength = map_strength_to_dglab(69)
        # (69 - 1) * 200 / 275 = 49.45 -> 49
        assert strength == 49


class TestRoundTrip:
    """映射往返测试 - 验证映射的一致性"""

    @pytest.mark.parametrize("dglab_strength", [0, 1, 50, 100, 150, 200])
    def test_roundtrip_dglab_to_ycy_to_dglab(self, dglab_strength):
        """DG-Lab -> YCY -> DG-Lab 往返"""
        enabled, ycy_strength = map_strength_to_ycy(dglab_strength)
        recovered = map_strength_to_dglab(ycy_strength) if enabled else 0

        # 由于整数除法的精度损失，允许 ±1 的误差
        assert abs(recovered - dglab_strength) <= 1

    @pytest.mark.parametrize("ycy_strength", [1, 50, 100, 138, 200, 276])
    def test_roundtrip_ycy_to_dglab_to_ycy(self, ycy_strength):
        """YCY -> DG-Lab -> YCY 往返"""
        dglab_strength = map_strength_to_dglab(ycy_strength)
        enabled, recovered = map_strength_to_ycy(dglab_strength)

        if ycy_strength == 1:
            # 强度 1 对应 DG-Lab 0，会被映射为关闭
            assert enabled is False
        else:
            assert enabled is True
            # 由于整数除法的精度损失，允许 ±2 的误差
            assert abs(recovered - ycy_strength) <= 2


class TestConvertPulse:
    """DG-Lab 波形 -> 役次元自定义模式参数转换测试"""

    def test_basic_pulse(self):
        """基本波形转换"""
        pulse = ((50, 50, 50, 50), (25, 25, 25, 25))
        freq, pulse_width = convert_pulse(pulse)
        assert freq == 50  # 平均频率
        assert pulse_width == 25  # 平均强度作为脉冲宽度

    def test_varying_frequencies(self):
        """不同频率值"""
        pulse = ((20, 40, 60, 80), (50, 50, 50, 50))
        freq, pulse_width = convert_pulse(pulse)
        # (20 + 40 + 60 + 80) / 4 = 50
        assert freq == 50
        assert pulse_width == 50

    def test_varying_strengths(self):
        """不同强度值"""
        pulse = ((100, 100, 100, 100), (10, 20, 30, 40))
        freq, pulse_width = convert_pulse(pulse)
        assert freq == 100
        # (10 + 20 + 30 + 40) / 4 = 25
        assert pulse_width == 25

    def test_high_frequency_clamp(self):
        """高频率钳制到 100"""
        pulse = ((200, 200, 200, 200), (50, 50, 50, 50))
        freq, pulse_width = convert_pulse(pulse)
        # 平均 200，钳制到 100
        assert freq == 100
        assert pulse_width == 50

    def test_low_frequency_clamp(self):
        """低频率钳制到 1"""
        pulse = ((0, 0, 0, 0), (50, 50, 50, 50))
        freq, pulse_width = convert_pulse(pulse)
        # 平均 0，钳制到 1
        assert freq == 1
        assert pulse_width == 50

    def test_zero_strength(self):
        """零强度"""
        pulse = ((50, 50, 50, 50), (0, 0, 0, 0))
        freq, pulse_width = convert_pulse(pulse)
        assert freq == 50
        assert pulse_width == 0

    def test_max_strength(self):
        """最大强度"""
        pulse = ((50, 50, 50, 50), (100, 100, 100, 100))
        freq, pulse_width = convert_pulse(pulse)
        assert freq == 50
        assert pulse_width == 100

    def test_realistic_waveform(self):
        """模拟真实波形 - 递增强度"""
        pulse = ((60, 60, 60, 60), (20, 40, 60, 80))
        freq, pulse_width = convert_pulse(pulse)
        assert freq == 60
        # (20 + 40 + 60 + 80) / 4 = 50
        assert pulse_width == 50

    def test_mixed_values(self):
        """混合值测试"""
        pulse = ((10, 50, 100, 240), (0, 50, 75, 100))
        freq, pulse_width = convert_pulse(pulse)
        # 频率: (10 + 50 + 100 + 240) / 4 = 100
        assert freq == 100
        # 强度: (0 + 50 + 75 + 100) / 4 = 56.25 -> 56
        assert pulse_width == 56
