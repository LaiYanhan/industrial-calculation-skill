"""
谷电熔盐储热供蒸汽计算场景实现类 (Molten Salt Steam Scenario Spec).
完整组装物性查表、能量方程、离散选型与造价概算联动。
"""

import math
from typing import Any, Dict, List, Tuple

from scenarios.base import BaseScenarioSpec
from engine.properties.iapws_adapter import WaterSteamPropertyAdapter
from engine.properties.salt_adapter import MoltenSaltPropertyAdapter
from engine.fsm.context import ExecutionContext
import scenarios.molten_salt_steam.equations as eq


class MoltenSaltSteamSpec(BaseScenarioSpec):

    def __init__(self):
        super().__init__("molten_salt_steam")
        self.alias_map = {
            "蒸汽压力": "steam_pressure_mpa",
            "主汽压": "steam_pressure_mpa",
            "压力": "steam_pressure_mpa",
            "蒸汽温度": "steam_temperature_c",
            "主汽温": "steam_temperature_c",
            "温度": "steam_temperature_c",
            "蒸汽流量": "steam_flow_th",
            "产汽量": "steam_flow_th",
            "流量": "steam_flow_th",
            "给水压力": "feedwater_pressure_mpa",
            "给水温度": "feedwater_temperature_c",
            "供汽时长": "steam_supply_hours_h",
            "谷电时长": "valley_power_hours_h",
            "总投资": "total_investment_wanke",
        }
        self.required_params = [
            "steam_pressure_mpa",
            "steam_temperature_c",
            "steam_flow_th",
        ]

    def lookup_references(self, canonical_params: Dict[str, float]) -> Dict[str, Any]:
        p_steam = canonical_params.get("steam_pressure_mpa", 1.5)
        t_steam = canonical_params.get("steam_temperature_c", 200.0)
        p_fw = canonical_params.get("feedwater_pressure_mpa", 0.1)
        t_fw = canonical_params.get("feedwater_temperature_c", 20.0)

        # 查水水蒸气焓值 (kJ/kg)
        h_steam = WaterSteamPropertyAdapter.get_enthalpy(p_steam, t_steam)
        h_fw = WaterSteamPropertyAdapter.get_enthalpy(p_fw, t_fw)

        # 查 HITEC 熔盐物性
        salt_props = MoltenSaltPropertyAdapter.get_hitec_properties(390.0)

        return {
            "steam_enthalpy_kj_kg": round(h_steam, 2),
            "feedwater_enthalpy_kj_kg": round(h_fw, 2),
            "salt_density_high": salt_props["density_kg_m3"],
            "salt_cp": salt_props["specific_heat_kj_kg_k"],
        }

    def solve_continuous(
        self,
        params: Dict[str, float],
        references: Dict[str, Any],
        mode: str = "FORWARD"
    ) -> Dict[str, float]:
        flow = params.get("steam_flow_th", 100.0)
        h_s = references.get("steam_enthalpy_kj_kg", 2795.98)
        h_f = references.get("feedwater_enthalpy_kj_kg", 84.01)

        t_supply = params.get("steam_supply_hours_h", 8.0)
        t_valley = params.get("valley_power_hours_h", 8.0)
        eta_heater = params.get("heater_efficiency", 0.985)
        eta_hex = params.get("heat_exchange_efficiency", 0.99)
        eta_storage = params.get("storage_efficiency", 0.99)

        sgs_power = eq.calc_sgs_power_mw(flow, h_s, h_f)
        heat_produced = eq.calc_heat_produced_mwh(sgs_power, t_supply, eta_hex)
        heater_power = eq.calc_heater_power_mw(heat_produced, t_valley, eta_heater)
        storage_cap = eq.calc_storage_capacity_mwh(heat_produced, eta_storage)
        salt_mass = eq.calc_salt_mass_t(storage_cap, references.get("salt_cp", 1.42))

        return {
            "sgs_power_mw": round(sgs_power, 2),
            "heat_produced_mwh": round(heat_produced, 2),
            "heater_power_theoretical_mw": round(heater_power, 2),
            "storage_capacity_theoretical_mwh": round(storage_cap, 2),
            "molten_salt_mass_t": salt_mass,
        }

    def regularize_discrete(
        self,
        continuous_results: Dict[str, float],
        params: Dict[str, float]
    ) -> Dict[str, Any]:
        p_th = continuous_results.get("heater_power_theoretical_mw", 77.25)
        # 规整至整十数 ROUNDUP(..., -1)
        p_nominal = float(math.ceil(p_th / 10.0) * 10)

        # 变压器容量选择标准档位
        standards = [16.0, 20.0, 25.0, 31.5, 40.0, 50.0, 63.0, 90.0, 120.0]
        trafo_mva = standards[-1]
        for s in standards:
            if s >= p_nominal:
                trafo_mva = s
                break

        # 储热量 ROUNDUP(..., -1)
        stor_th = continuous_results.get("storage_capacity_theoretical_mwh", 614.9)
        storage_nominal = float(math.ceil(stor_th / 10.0) * 10)

        return {
            "heater_power_nominal_mw": p_nominal,
            "transformer_capacity_mva": trafo_mva,
            "storage_capacity_mwh": storage_nominal,
        }

    def cascade_metrics(
        self,
        continuous_results: Dict[str, float],
        discrete_results: Dict[str, Any],
        params: Dict[str, float]
    ) -> Dict[str, Any]:
        p_nom = discrete_results.get("heater_power_nominal_mw", 80.0)
        salt_m = continuous_results.get("molten_salt_mass_t", 8650.0)
        sgs_p = continuous_results.get("sgs_power_mw", 75.33)
        trafo = discrete_results.get("transformer_capacity_mva", 90.0)

        # 分项设备造价
        cost_heater = p_nom * (40.0 if p_nom < 100.0 else 38.0)
        cost_salt = salt_m * (1.2 if salt_m < 10000.0 else 1.1)
        cost_hex = sgs_p * 35.0
        cost_elec = trafo * 12.0

        equipment_total = cost_heater + cost_salt + cost_hex + cost_elec
        # 静态投资: 设备投资占 80% 反算
        static_investment = equipment_total / 0.8
        construction_reserve = static_investment - equipment_total
        # 动态投资: 静态投资 + 建设期利息 1000 万元
        dynamic_investment = static_investment + 1000.0

        return {
            "cost_electric_heater_wanke": round(cost_heater, 2),
            "cost_storage_system_wanke": round(cost_salt, 2),
            "cost_heat_exchange_wanke": round(cost_hex, 2),
            "cost_electrical_system_wanke": round(cost_elec, 2),
            "equipment_investment_wanke": round(equipment_total, 2),
            "construction_and_reserve_wanke": round(construction_reserve, 2),
            "static_investment_wanke": round(static_investment, 2),
            "dynamic_investment_wanke": round(dynamic_investment, 2),
        }

    def audit_sanity(self, context: ExecutionContext) -> Tuple[List[str], List[str]]:
        violations = []
        warnings = []

        p_steam = context.canonical_params.get("steam_pressure_mpa", 1.5)
        t_steam = context.canonical_params.get("steam_temperature_c", 200.0)

        # 换热夹点审查: 蒸汽温度不得超过熔盐最高供热温度 390℃
        if t_steam >= 390.0:
            violations.append(f"蒸汽温度 {t_steam}℃ 超出 HITEC 熔盐最高温区 390℃，无法完成热交换")

        # 压力审查
        if p_steam <= 0:
            violations.append(f"蒸汽压力 {p_steam}MPa 非法，必须为正数")

        return violations, warnings
