"""熔盐供汽场景编排：加载声明、查物性、调用纯函数并审计结果。"""
import json
import math
from pathlib import Path
from typing import Any

import yaml

from engine.fsm.context import ExecutionContext
from engine.properties.iapws_adapter import WaterSteamPropertyAdapter
from engine.properties.salt_adapter import MoltenSaltPropertyAdapter
from scenarios.base import BaseScenarioSpec
from scenarios.molten_salt_steam import equations as eq
from scenarios.molten_salt_steam.costing import equipment_costs, estimate_project
from scenarios.molten_salt_steam.inversion import maximize_flow_under_budget
from scenarios.molten_salt_steam.sizing import size_equipment

SCENARIO_DIR = Path(__file__).resolve().parent


class MoltenSaltSteamSpec(BaseScenarioSpec):
    def __init__(self) -> None:
        super().__init__("molten_salt_steam")
        self.manifest = yaml.safe_load((SCENARIO_DIR / "manifest.yaml").read_text(encoding="utf-8-sig"))
        self.sizing_rules = json.loads((SCENARIO_DIR / "sizing_rules.json").read_text(encoding="utf-8-sig"))
        self.costing_rules = yaml.safe_load((SCENARIO_DIR / "costing_rules.yaml").read_text(encoding="utf-8-sig"))
        definitions = self.manifest["parameters"]
        self.alias_map = {alias: key for key, definition in definitions.items()
                          for alias in definition.get("aliases", [])}
        self.required_params = [key for key, definition in definitions.items() if definition.get("required")]
        self.budget_keys = ("target_dynamic_investment_wanke", "target_heat_pump_dynamic_investment_wanke")

    def infer_solution_mode(self, params: dict[str, float], targets: list[str]) -> str:
        return "INVERSE" if any(key in params for key in self.budget_keys) else "FORWARD"

    def get_required_parameters(self, params: dict[str, float], targets: list[str],
                                mode: str) -> list[str]:
        if mode == "AUTO":
            mode = self.infer_solution_mode(params, targets)
        if mode in ("INVERSE", "SEARCH"):
            if targets and targets != ["steam_flow_th"]:
                raise ValueError("此场景预算反解仅支持目标 steam_flow_th")
            required = ["steam_pressure_mpa", "steam_temperature_c"]
            if not any(key in params for key in self.budget_keys):
                required.append(self.budget_keys[0])
            return required
        return list(self.required_params)

    def align_parameters(self, params: dict[str, float]) -> dict[str, float]:
        definitions = self.manifest["parameters"]
        unknown = set(params) - set(definitions)
        if unknown:
            raise ValueError(f"未声明的参数: {sorted(unknown)}")
        aligned = {key: float(definition["default"]) for key, definition in definitions.items()
                   if "default" in definition and not definition.get("required")}
        aligned.update(params)
        for key, value in aligned.items():
            definition = definitions[key]
            if not math.isfinite(value):
                raise ValueError(f"{key} 必须为有限数")
            if "bounds" in definition and not definition["bounds"][0] <= value <= definition["bounds"][1]:
                raise ValueError(f"{key} 超出范围 {definition['bounds']} {definition['canonical_unit']}")
            if "enum" in definition and value not in definition["enum"]:
                raise ValueError(f"{key} 必须属于 {definition['enum']}")
        profile = self.manifest["salt_profiles"][str(int(aligned["salt_type_id"]))]
        aligned.setdefault("salt_temperature_high_c", profile["high_c"])
        aligned.setdefault("salt_temperature_low_c", profile["low_c"])
        if aligned["salt_temperature_high_c"] <= aligned["salt_temperature_low_c"]:
            raise ValueError("熔盐高温必须高于低温")
        if sum(key in aligned for key in self.budget_keys) > 1:
            raise ValueError("一次反解只能给定一个方案的投资预算")
        return aligned

    def lookup_references(self, canonical_params: dict[str, float]) -> dict[str, Any]:
        params = self.align_parameters(canonical_params)
        steam = WaterSteamPropertyAdapter.get_properties(params["steam_pressure_mpa"], params["steam_temperature_c"],
                                                         params.get("steam_quality"))
        feedwater = WaterSteamPropertyAdapter.get_properties(params["feedwater_pressure_mpa"], params["feedwater_temperature_c"],
                                                             params.get("feedwater_quality"))
        profile = self.manifest["salt_profiles"][str(int(params["salt_type_id"]))]
        material = profile["material"]
        getter = (MoltenSaltPropertyAdapter.get_hitec_properties if material == "hitec"
                  else MoltenSaltPropertyAdapter.get_solar_salt_properties)
        hot = getter(params["salt_temperature_high_c"])
        cold = getter(params["salt_temperature_low_c"])
        cp_kj_kg_k = MoltenSaltPropertyAdapter.mean_specific_heat(
            material, params["salt_temperature_low_c"], params["salt_temperature_high_c"])
        return {
            "steam_enthalpy_kj_kg": steam["enthalpy_kj_kg"],
            "feedwater_enthalpy_kj_kg": feedwater["enthalpy_kj_kg"],
            "steam_quality": steam["quality"],
            "feedwater_quality": feedwater["quality"],
            "salt_cp_kj_kg_k": cp_kj_kg_k,
            "salt_material": material,
            "salt_properties_high": hot, "salt_properties_low": cold,
            "salt_density_high_kg_m3": hot["density_kg_m3"],
            "salt_density_low_kg_m3": cold["density_kg_m3"],
        }

    def _continuous(self, params: dict[str, float], references: dict[str, Any]) -> dict[str, float]:
        steam_flow_th = params["steam_flow_th"]
        sgs_power_mw = eq.calc_sgs_power_mw(steam_flow_th, references["steam_enthalpy_kj_kg"],
                                           references["feedwater_enthalpy_kj_kg"])
        if sgs_power_mw <= 0:
            raise ValueError("蒸汽出口焓必须高于给水焓")
        heat_mwh = eq.calc_heat_produced_mwh(sgs_power_mw, params["steam_supply_hours_h"],
                                            params["heat_exchange_efficiency"])
        heater_mw = eq.calc_heater_power_mw(heat_mwh, params["valley_power_hours_h"], params["heater_efficiency"])
        storage_mwh = eq.calc_storage_capacity_mwh(heat_mwh, params["storage_efficiency"])
        pump_thermal_mw = eq.calc_heat_pump_thermal_power_mw(heat_mwh, params["valley_power_hours_h"])
        pump_electric_mw = eq.calc_heat_pump_electric_power_mw(pump_thermal_mw, params["heat_pump_cop"])
        return {
            "steam_flow_th": steam_flow_th,
            "sgs_power_mw": sgs_power_mw,
            "heat_produced_mwh": heat_mwh,
            "heater_power_theoretical_mw": heater_mw,
            "storage_capacity_theoretical_mwh": storage_mwh,
            "salt_cp_kj_kg_k": references["salt_cp_kj_kg_k"],
            "molten_salt_mass_theoretical_t": eq.calc_salt_mass_t(
                storage_mwh, references["salt_cp_kj_kg_k"], params["salt_temperature_high_c"],
                params["salt_temperature_low_c"], params["salt_mass_margin"]),
            "heat_pump_thermal_power_mw": pump_thermal_mw,
            "heat_pump_electric_power_mw": pump_electric_mw,
            "annual_electricity_wan_kwh": eq.calc_annual_electricity_wan_kwh(
                heater_mw, params["valley_power_hours_h"], params["operating_days_d"]),
            "heat_pump_annual_electricity_wan_kwh": eq.calc_annual_electricity_wan_kwh(
                pump_electric_mw, params["valley_power_hours_h"], params["operating_days_d"]),
            "annual_steam_wan_t": eq.calc_annual_steam_wan_t(
                steam_flow_th, params["steam_supply_hours_h"], params["operating_days_d"]),
            "workbook_heater_annual_steam_wan_t": eq.calc_annual_steam_wan_t(
                steam_flow_th, params["valley_power_hours_h"], params["operating_days_d"]),
        }

    def solve_continuous(self, params: dict[str, float], references: dict[str, Any],
                         mode: str = "FORWARD") -> dict[str, float]:
        resolved = self.align_parameters(params)
        if mode in ("INVERSE", "SEARCH"):
            if "steam_flow_th" in params:
                raise ValueError("预算反解不应同时固定 steam_flow_th")
            budget_key = next((key for key in self.budget_keys if key in resolved), None)
            if budget_key is None:
                raise ValueError("缺少投资预算")
            cost_key = budget_key.removeprefix("target_")
            unit_continuous = self._continuous({**resolved, "steam_flow_th": 1.0}, references)

            def evaluate_cost(flow_th: float) -> float:
                trial_params = {**resolved, "steam_flow_th": flow_th}
                continuous = self._continuous(trial_params, references)
                discrete = size_equipment(continuous, trial_params, self.sizing_rules)
                return equipment_costs(discrete, trial_params, self.costing_rules)[cost_key]

            lower_th, upper_th = self.manifest["parameters"]["steam_flow_th"]["bounds"]
            resolved["steam_flow_th"] = maximize_flow_under_budget(
                unit_continuous, self.sizing_rules, lower_th, upper_th,
                resolved[budget_key], evaluate_cost)
        elif mode != "FORWARD":
            raise ValueError(f"不支持的求解方向 {mode}")
        elif any(key in params for key in self.budget_keys):
            raise ValueError("投资预算输入需使用 INVERSE/SEARCH/AUTO 模式")
        return self._continuous(resolved, references)

    def regularize_discrete(self, continuous_results: dict[str, float],
                            params: dict[str, float]) -> dict[str, Any]:
        return size_equipment(continuous_results, self.align_parameters(params), self.sizing_rules)

    def cascade_metrics(self, continuous_results: dict[str, float],
                        discrete_results: dict[str, Any], params: dict[str, float]) -> dict[str, Any]:
        params = self.align_parameters(params)
        costs = equipment_costs(discrete_results, params, self.costing_rules)
        result: dict[str, Any] = dict(costs)
        result.update(estimate_project(costs, params, self.costing_rules))
        result.update({"heat_pump_" + key: value for key, value
                       in estimate_project(costs, params, self.costing_rules, heat_pump=True).items()})
        return result

    def audit_sanity(self, context: ExecutionContext) -> tuple[list[str], list[str]]:
        params = self.align_parameters(context.canonical_params)
        references = context.reference_data
        continuous = context.continuous_results
        discrete = context.discrete_results
        cascade = context.cascade_results
        violations: list[str] = []
        warnings: list[str] = []
        pinch_c = params["minimum_pinch_c"]
        if params["salt_temperature_high_c"] - params["steam_temperature_c"] < pinch_c:
            violations.append("热端熔盐/蒸汽夹点温差不足")
        if params["salt_temperature_low_c"] - params["feedwater_temperature_c"] < pinch_c:
            violations.append("冷端熔盐/给水夹点温差不足")
        if references["steam_quality"] < 1:
            violations.append("供汽工况处于液相，不能作为蒸汽出口")
        if references["feedwater_quality"] > 0:
            violations.append("给水工况不在液相")
        tolerance = self.manifest["numerics"]["balance_tolerance_wanke"]
        for prefix in ("", "heat_pump_"):
            if abs(cascade[prefix + "estimate_balance_residual_wanke"]) > tolerance:
                violations.append(f"{prefix}工程概算未与静态投资平衡")
            for suffix in ("auxiliary_system_wanke", "fixed_assets_wanke", "other_fees_wanke",
                           "deductible_vat_wanke", "static_investment_wanke", "dynamic_investment_wanke"):
                if cascade[prefix + suffix] < -tolerance or not math.isfinite(cascade[prefix + suffix]):
                    violations.append(f"{prefix + suffix} 非法：固定费用与投资控制额不相容")
        for nominal, theoretical in (("heater_power_nominal_mw", "heater_power_theoretical_mw"),
                                     ("storage_capacity_mwh", "storage_capacity_theoretical_mwh"),
                                     ("sgs_power_nominal_mw", "sgs_power_mw"),
                                     ("heat_pump_power_nominal_mw", "heat_pump_thermal_power_mw")):
            if discrete[nominal] < continuous[theoretical] and not math.isclose(
                    discrete[nominal], continuous[theoretical],
                    rel_tol=self.manifest["numerics"]["audit_relative_tolerance"]):
                violations.append(f"{nominal} 小于理论需求")
        transformer = self.sizing_rules["transformer"]
        for capacity, load, factor in (
            ("transformer_capacity_mva", "heater_power_theoretical_mw", "heater_power_factor"),
            ("heat_pump_transformer_capacity_mva", "heat_pump_electric_power_mw", "heat_pump_power_factor"),
        ):
            if discrete[capacity] < continuous[load] / transformer[factor] and not math.isclose(
                    discrete[capacity], continuous[load] / transformer[factor],
                    rel_tol=self.manifest["numerics"]["audit_relative_tolerance"]):
                violations.append(f"{capacity} 不足以覆盖工作负载")
        for key in self.budget_keys:
            if key in params and cascade[key.removeprefix("target_")] > params[key] + tolerance:
                violations.append("反解结果超出投资预算")
        if params["steam_supply_hours_h"] != params["valley_power_hours_h"]:
            warnings.append("原表计算!D10 使用谷电时长；annual_steam_wan_t 使用供汽时长，另保留原表口径字段")
        if discrete["sgs_power_nominal_mw"] != discrete["sgs_catalog_power_mw"]:
            warnings.append("SGS 造价按选型公式的 1 MW 步长；型号建议按备注的 5 MW 步长，分开返回")
        warnings.append("物性粘度标签与概算税率沿用原始工作簿，未声明为现行规范")
        return violations, warnings

    def export_excel(self, context: ExecutionContext) -> str:
        from scenarios.molten_salt_steam.reporting import export_report
        return export_report(context, self.manifest, self.costing_rules)
