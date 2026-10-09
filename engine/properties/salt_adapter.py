"""通用熔盐物性适配器，温度 degC；保留全精度，不混淆原表单位。

相关式来源：输入输出.xlsx「熔盐参数」E5:E12、K5:K12。
原始资料未附论文/国标编号，不能将其宣称为国家标准或认证物性。
导热系数沿用原表 kcal/(m·h·degC)，粘度沿用原表 (kg·s)/m²；
未验证原表粘度标签，不把该数值擅自当成 Pa·s。
"""
import math

# 系数按常数项、一次项、二次项、三次项排列，温度自变量单位 degC。
HITEC_DENSITY_COEFFICIENTS = (2115.0, -0.9721, 0.0003602)
HITEC_CONDUCTIVITY_COEFFICIENTS = (0.3015, 0.00104, -4.02e-6, 3.283e-9)
HITEC_CP_KJ_KG_K = 1.42
HITEC_VISCOSITY_FACTOR = 5.771e7
HITEC_VISCOSITY_EXPONENT = -3.001
HITEC_VISCOSITY_OFFSET = 0.9426
HITEC_RANGE_C = (190.0, 400.0)
SOLAR_DENSITY_COEFFICIENTS = (2090.0, -0.636)
SOLAR_CP_COEFFICIENTS = (1.443, 0.000172)  # kJ/(kg·K)
SOLAR_CONDUCTIVITY_COEFFICIENTS = (0.443, 1.9e-4)
SOLAR_VISCOSITY_COEFFICIENTS = (22.714, -0.12, 2.281e-4, -1.474e-7)
SOLAR_RANGE_C = (290.0, 565.0)


def _polynomial(temperature_c: float, coefficients: tuple[float, ...]) -> float:
    return sum(coefficient * temperature_c ** degree
               for degree, coefficient in enumerate(coefficients))


def _validate(temperature_c: float, bounds_c: tuple[float, float]) -> None:
    if not math.isfinite(temperature_c) or not bounds_c[0] <= temperature_c <= bounds_c[1]:
        raise ValueError(f"熔盐温度必须位于 {bounds_c} degC，收到 {temperature_c}")


class MoltenSaltPropertyAdapter:
    @staticmethod
    def get_hitec_properties(temp_c: float) -> dict[str, float]:
        _validate(temp_c, HITEC_RANGE_C)
        return {
            "density_kg_m3": _polynomial(temp_c, HITEC_DENSITY_COEFFICIENTS),
            "specific_heat_kj_kg_k": HITEC_CP_KJ_KG_K,
            "thermal_conductivity_kcal_m_h_k": _polynomial(temp_c, HITEC_CONDUCTIVITY_COEFFICIENTS),
            "viscosity_kg_s_m2": HITEC_VISCOSITY_FACTOR * temp_c ** HITEC_VISCOSITY_EXPONENT + HITEC_VISCOSITY_OFFSET,
        }

    @staticmethod
    def get_solar_salt_properties(temp_c: float) -> dict[str, float]:
        _validate(temp_c, SOLAR_RANGE_C)
        return {
            "density_kg_m3": _polynomial(temp_c, SOLAR_DENSITY_COEFFICIENTS),
            "specific_heat_kj_kg_k": _polynomial(temp_c, SOLAR_CP_COEFFICIENTS),
            "thermal_conductivity_kcal_m_h_k": _polynomial(temp_c, SOLAR_CONDUCTIVITY_COEFFICIENTS),
            "viscosity_kg_s_m2": _polynomial(temp_c, SOLAR_VISCOSITY_COEFFICIENTS),
        }

    @classmethod
    def mean_specific_heat(cls, material: str, low_c: float, high_c: float) -> float:
        """积分平均比热：HITEC 常数、太阳盐线性式，端点均值即精确积分均值。"""
        if high_c <= low_c:
            raise ValueError("熔盐热端温度必须高于冷端温度")
        getters = {"hitec": cls.get_hitec_properties, "solar_salt": cls.get_solar_salt_properties}
        if material not in getters:
            raise ValueError(f"未知熔盐: {material}")
        getter = getters[material]
        return (getter(low_c)["specific_heat_kj_kg_k"]
                + getter(high_c)["specific_heat_kj_kg_k"]) / 2
