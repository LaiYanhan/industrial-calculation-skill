"""
熔盐物性拟合计算适配器 (Molten Salt Property Adapter).
包含 HITEC 熔盐与太阳盐在不同温度下的密度、比热、导热系数与粘度拟合多项式。
"""

from typing import Dict


class MoltenSaltPropertyAdapter:
    """
    熔盐物性经验多项式计算.
    公式来源于工程设计实测数据与国标拟合。
    """

    @staticmethod
    def get_hitec_properties(temp_c: float) -> Dict[str, float]:
        """HITEC 熔盐 (适用温区 190℃ ~ 400℃)"""
        density = 0.0003602 * (temp_c ** 2) - 0.9721 * temp_c + 2115.0
        cp = 1.42  # kJ/kg/℃
        conductivity = (
            3.283e-9 * (temp_c ** 3)
            - 4.02e-6 * (temp_c ** 2)
            + 0.00104 * temp_c
            + 0.3015
        )
        viscosity = 5.771e7 * (temp_c ** -3.001) + 0.9426

        return {
            "density_kg_m3": round(density, 2),
            "specific_heat_kj_kg_k": cp,
            "thermal_conductivity": round(conductivity, 4),
            "viscosity": round(viscosity, 4),
        }

    @staticmethod
    def get_solar_salt_properties(temp_c: float) -> Dict[str, float]:
        """太阳盐 (适用温区 290℃ ~ 565℃)"""
        density = 2090.0 - 0.636 * temp_c
        cp = (1443.0 + 0.172 * temp_c) / 1000.0
        conductivity = 0.443 + 1.9e-4 * temp_c
        viscosity = (
            22.714
            - 0.12 * temp_c
            + 2.281 * (temp_c ** 2) / 1e4
            - 1.474 * (temp_c ** 3) / 1e7
        )

        return {
            "density_kg_m3": round(density, 2),
            "specific_heat_kj_kg_k": round(cp, 4),
            "thermal_conductivity": round(conductivity, 4),
            "viscosity": round(viscosity, 4),
        }
