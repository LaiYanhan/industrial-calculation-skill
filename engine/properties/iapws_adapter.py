"""通用水/水蒸气物性，IAPWS-IF97 (R7-97, 2012)。
来源 https://iapws.org/relguide/IF97-Rev.pdf
压力均为绝压 MPa；不使用无相区约束的经验焓值兜底。
"""
import math
from typing import Any

CELSIUS_OFFSET_K = 273.15  # SI 温标定义
CRITICAL_PRESSURE_MPA = 22.064  # IAPWS-IF97 §4
TRIPLE_PRESSURE_MPA = 0.000611657  # IAPWS 三相点
SATURATION_TOLERANCE_K = 1e-6  # 数值判别精度，不是工艺裕量


class WaterSteamPropertyAdapter:
    @staticmethod
    def _state(pressure_mpa: float, temperature_c: float | None = None,
               quality: float | None = None) -> Any:
        if not math.isfinite(pressure_mpa) or pressure_mpa <= 0:
            raise ValueError("压力必须为正有限绝压 (MPa)")
        if temperature_c is not None and not math.isfinite(temperature_c):
            raise ValueError("温度必须为有限数 (degC)")
        if quality is not None and (not math.isfinite(quality) or not 0 <= quality <= 1):
            raise ValueError("干度必须位于 [0,1]")
        try:
            from iapws import IAPWS97
        except ImportError as exc:
            raise RuntimeError("缺少 iapws；请安装场景 requirements.txt，禁止经验公式代替 IF97") from exc
        try:
            if quality is not None:
                state = IAPWS97(P=pressure_mpa, x=quality)
                if temperature_c is not None and abs(state.T - CELSIUS_OFFSET_K - temperature_c) > SATURATION_TOLERANCE_K:
                    raise ValueError("指定温度与压力对应的饱和温度不一致")
                return state
            if temperature_c is None:
                raise ValueError("必须提供温度或饱和干度")
            temperature_k = temperature_c + CELSIUS_OFFSET_K
            if TRIPLE_PRESSURE_MPA <= pressure_mpa < CRITICAL_PRESSURE_MPA:
                saturated = IAPWS97(P=pressure_mpa, x=0)
                if abs(temperature_k - saturated.T) <= SATURATION_TOLERANCE_K:
                    raise ValueError("饱和线上 P/T 不能确定焓，请显式指定干度 quality")
            return IAPWS97(P=pressure_mpa, T=temperature_k)
        except (NotImplementedError, OverflowError) as exc:
            raise ValueError(f"工况超出 IAPWS-IF97 有效范围: {pressure_mpa} MPa, {temperature_c} degC") from exc

    @classmethod
    def get_properties(cls, pressure_mpa: float, temperature_c: float | None = None,
                       quality: float | None = None) -> dict[str, float]:
        state = cls._state(pressure_mpa, temperature_c, quality)
        result = {
            "enthalpy_kj_kg": float(state.h),
            "entropy_kj_kg_k": float(state.s),
            "specific_volume_m3_kg": float(state.v),
            "density_kg_m3": float(state.rho),
            "temperature_c": float(state.T - CELSIUS_OFFSET_K),
            "quality": float(state.x),
        }
        if not all(math.isfinite(value) for value in result.values()):
            raise ValueError("IAPWS 返回非有限物性")
        return result

    @classmethod
    def get_enthalpy(cls, pressure_mpa: float, temperature_c: float | None = None,
                     quality: float | None = None) -> float:
        return cls.get_properties(pressure_mpa, temperature_c, quality)["enthalpy_kj_kg"]

    @classmethod
    def get_saturation_temperature(cls, pressure_mpa: float) -> float:
        return cls.get_properties(pressure_mpa, quality=0)["temperature_c"]
