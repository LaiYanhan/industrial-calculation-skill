"""
水和水蒸气热力学物性查表适配器 (Water & Steam Thermodynamic Properties).
依据 IAPWS-IF97 工业标准或 CoolProp 计算焓值、熵与比容。
若环境未安装第三方库，提供工程经验公式拟合兜底。
"""

from typing import Optional


class WaterSteamPropertyAdapter:
    """
    水与水蒸气热工物性查表器.
    主要计算: 给水与蒸汽焓值 (kJ/kg).
    """

    @staticmethod
    def get_enthalpy(pressure_mpa: float, temperature_c: float) -> float:
        """
        根据压力 (MPa) 与温度 (℃) 获取焓值 (kJ/kg).
        优先尝试 iapws 库，无依赖时提供标准热力学拟合近似。
        """
        try:
            from iapws import IAPWS97
            state = IAPWS97(P=pressure_mpa, T=temperature_c + 273.15)
            return float(state.h)
        except ImportError:
            if temperature_c <= 100.0:
                # 给水近似焓 (20℃ 附近基准约 84 kJ/kg): h ≈ 4.187 * T + 0.1 * P
                return 4.187 * temperature_c + 0.1 * pressure_mpa
            else:
                # 蒸汽近似焓 (200℃, 1.5MPa 附近基准约 2795.98 kJ/kg)
                return 2514.0 + 1.4 * temperature_c + 1.3 * pressure_mpa
