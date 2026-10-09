"""业务验收：独立工作簿金标、热平衡、反解、计价边界与失败路径。"""
import copy
import json
import math
from pathlib import Path
import unittest

import openpyxl
import sympy

from engine.properties.iapws_adapter import WaterSteamPropertyAdapter as Water
from engine.properties.salt_adapter import MoltenSaltPropertyAdapter as Salt
from scenarios.molten_salt_steam import equations as eq
from scenarios.molten_salt_steam.costing import equipment_costs, tier_price
from scenarios.molten_salt_steam.sizing import ceil_to_step, select_transformers
from scenarios.molten_salt_steam.spec import MoltenSaltSteamSpec
from skill_api import CalculationSkill

ROOT = Path(__file__).resolve().parents[1]
BASE = {"steam_pressure_mpa": 1.5, "steam_temperature_c": 200.0, "steam_flow_th": 100.0}


class TestPhysicalProperties(unittest.TestCase):
    def test_if97_official_verification_points(self) -> None:
        # IF97 release tables 5 and 15: P(MPa), T(K), h(kJ/kg).
        for pressure_mpa, temperature_k, enthalpy_kj_kg in (
            (3, 300, 115.331273), (80, 300, 184.142828), (3, 500, 975.542239),
            (0.0035, 300, 2549.91145), (0.0035, 700, 3335.68375), (30, 700, 2631.49474),
        ):
            with self.subTest(pressure=pressure_mpa, temperature=temperature_k):
                self.assertAlmostEqual(Water.get_enthalpy(pressure_mpa, temperature_k - 273.15),
                                       enthalpy_kj_kg, delta=1e-5)

    def test_saturation_requires_quality(self) -> None:
        temperature_c = Water.get_saturation_temperature(1.5)
        with self.assertRaisesRegex(ValueError, "干度"):
            Water.get_enthalpy(1.5, temperature_c)
        self.assertGreater(Water.get_enthalpy(1.5, temperature_c, quality=1),
                           Water.get_enthalpy(1.5, temperature_c, quality=0))
        with self.assertRaises(ValueError):
            Water.get_enthalpy(1.5, 200, quality=1)

    def test_property_boundaries(self) -> None:
        for pressure_mpa, temperature_c in ((0, 20), (-1, 200), (math.nan, 20), (1, math.inf),
                                           (1, -30), (200, 20)):
            with self.subTest(pressure=pressure_mpa, temperature=temperature_c), self.assertRaises(ValueError):
                Water.get_enthalpy(pressure_mpa, temperature_c)
        for getter, temperatures in ((Salt.get_hitec_properties, (189, 401, math.nan)),
                                     (Salt.get_solar_salt_properties, (289, 566, math.inf))):
            for temperature_c in temperatures:
                with self.assertRaises(ValueError):
                    getter(temperature_c)

    def test_salt_workbook_points_and_integral_cp(self) -> None:
        self.assertAlmostEqual(Salt.get_hitec_properties(390)["density_kg_m3"], 1790.66742)
        self.assertAlmostEqual(Salt.get_hitec_properties(190)["viscosity_kg_s_m2"], 9.312331340972857)
        self.assertAlmostEqual(Salt.get_solar_salt_properties(565)["specific_heat_kj_kg_k"], 1.54018)
        self.assertAlmostEqual(Salt.mean_specific_heat("solar_salt", 290, 565), 1.51653)
        with self.assertRaises(ValueError):
            Salt.mean_specific_heat("hitec", 390, 190)

    def test_equations_support_symbolic_inversion_without_rounding(self) -> None:
        flow_th = sympy.Symbol("flow_th", positive=True)
        expression = eq.calc_sgs_power_mw(flow_th, 2800, 100)
        self.assertAlmostEqual(float(sympy.solve(sympy.Eq(expression, 75), flow_th)[0]), 100)
        energy_mwh = sympy.Symbol("energy_mwh")
        mass = eq.calc_salt_mass_t(energy_mwh, 1.42, 390, 190, 1.1)
        self.assertEqual(sympy.diff(mass, energy_mwh, 2), 0)


class TestMoltenSaltBusiness(unittest.TestCase):
    def setUp(self) -> None:
        self.skill = CalculationSkill()
        self.spec = MoltenSaltSteamSpec()

    def calculate(self, overrides: dict[str, float] | None = None) -> dict:
        response = self.skill.calculate("molten_salt_steam", BASE | (overrides or {}))
        self.assertEqual(response["status"], "SUCCESS", response)
        self.assertEqual(len(response["fsm_trace"]), 9)
        return response["results"]

    def test_workbook_exact_discrete_costs_and_complete_estimate(self) -> None:
        result = self.calculate()
        workbook = openpyxl.load_workbook(ROOT / "输入输出.xlsx", data_only=True)
        self.addCleanup(workbook.close)
        bindings = {"选型!D2": "heater_power_nominal_mw", "选型!D3": "heat_pump_power_nominal_mw",
                    "选型!D4": "storage_capacity_mwh", "选型!D9": "molten_salt_mass_t",
                    "选型!D10": "sgs_power_nominal_mw", "选型!D11": "transformer_capacity_mva",
                    "选型!D12": "heat_pump_transformer_capacity_mva", "造价!E7": "equipment_investment_wanke",
                    "造价!E17": "heat_pump_equipment_investment_wanke", "造价!E19": "heat_pump_static_investment_wanke"}
        for reference, key in bindings.items():
            sheet, cell = reference.split("!")
            self.assertEqual(result[key], workbook[sheet][cell].value, reference)
        for row, columns in result["project_estimate_rows"].items():
            for column, actual in columns.items():
                expected = workbook["工程概算"][f"{column}{row}"].value
                if isinstance(expected, (int, float)):
                    self.assertAlmostEqual(actual, expected, delta=1e-7,
                                           msg=f"工程概算!{column}{row}")
        # 外部 enthalpy 插件与 IF97 存在约 0.032 kJ/kg 的差别，不能冒称完全相同。
        self.assertAlmostEqual(result["steam_enthalpy_kj_kg"], workbook["计算"]["D3"].value, delta=0.04)
        self.assertAlmostEqual(result["feedwater_enthalpy_kj_kg"], workbook["计算"]["D4"].value, delta=0.01)

    def test_energy_balance_and_rounding_order(self) -> None:
        result = self.calculate()
        self.assertAlmostEqual(result["heater_power_theoretical_mw"] * 8 * .985,
                               result["sgs_power_mw"] * 8 / .99)
        self.assertAlmostEqual(result["storage_capacity_theoretical_mwh"] * .99,
                               result["heat_produced_mwh"])
        raw_from_selected = 620 * 3600 * 1.1 / 1.42 / 200
        self.assertEqual(result["molten_salt_mass_t"], math.ceil(raw_from_selected / 10) * 10)
        self.assertEqual(result["sgs_catalog_power_mw"], 80)
        self.assertEqual(result["sgs_power_nominal_mw"], 76)

    def test_unequal_hours_and_annual_units(self) -> None:
        result = self.calculate({"steam_supply_hours_h": 10})
        self.assertEqual(result["annual_steam_wan_t"], 33)
        self.assertEqual(result["workbook_heater_annual_steam_wan_t"], 26.4)
        self.assertEqual(result["storage_capacity_mwh"], 770)
        self.assertEqual(result["molten_salt_mass_t"], 10740)
        self.assertEqual(result["dynamic_investment_wanke"], 25642.5)

    def test_tier_boundaries_are_exclusive(self) -> None:
        pricing = self.spec.costing_rules["equipment_pricing"]
        for kind, points in (
            ("heater", ((99.999, 40), (100, 38), (200, 35))),
            ("storage_system", ((9999.99, 1.2), (10000, 1.1), (20000, 1))),
            ("heat_exchange", ((249.99, 35), (250, 32), (350, 30))),
        ):
            for quantity, expected in points:
                self.assertEqual(tier_price(quantity, pricing[kind]["tiers"]), expected)

    def test_heat_pump_temperature_and_power_tiers(self) -> None:
        result = self.calculate()
        params = self.spec.align_parameters(BASE)
        for power_mw, temperature_c, expected in ((149,49,94), (149,50,80), (150,49,85), (150,50,73)):
            costs = equipment_costs(result | {"heat_pump_power_nominal_mw": power_mw},
                                    params | {"waste_heat_temperature_c": temperature_c}, self.spec.costing_rules)
            self.assertEqual(costs["heat_pump_unit_price_wanke_per_mw"], expected)
        self.assertEqual(self.calculate({"waste_heat_temperature_c": 50})["heat_pump_static_investment_wanke"], 25650)

    def test_large_capacity_combines_equipment(self) -> None:
        result = self.calculate({"steam_flow_th": 300})
        self.assertEqual(result["transformer_banks_mva"], [120, 120])
        self.assertEqual(result["heat_pump_transformer_banks_mva"], [120, 90])
        self.assertEqual(sum(result["heater_modules_mw"]), result["heater_power_nominal_mw"])
        self.assertTrue(all(value <= 30 for value in result["heater_modules_mw"]))
        self.assertEqual(result["dynamic_investment_wanke"], 57281.25)

    def test_transformer_uses_working_load_and_rounding_is_stable(self) -> None:
        standards = self.spec.sizing_rules["transformer"]["standards_mva"]
        self.assertEqual(select_transformers(31.5, standards, 1e-10), [31.5])
        self.assertEqual(select_transformers(31.50001, standards, 1e-10), [40])
        self.assertEqual(select_transformers(120.1, standards, 1e-10), [120, 16])
        self.assertEqual(ceil_to_step(80.00000000000001, 10, 1e-10), 80)
        self.assertEqual(ceil_to_step(80.00001, 10, 1e-10), 90)

    def test_solar_salt_and_custom_temperatures(self) -> None:
        result = self.calculate({"salt_type_id": 1, "steam_temperature_c": 400})
        self.assertEqual(result["salt_material"], "solar_salt")
        self.assertEqual(result["salt_temperature_high_c"], 565)
        self.assertAlmostEqual(result["salt_cp_kj_kg_k"], 1.51653)
        self.assertEqual(result["molten_salt_mass_t"], 6840)
        cooler = self.calculate({"salt_temperature_high_c": 350})
        self.assertGreater(cooler["molten_salt_mass_t"], 8650)

    def test_custom_costs_rebalance_estimate_without_mutating_input(self) -> None:
        params = BASE | {"thermal_system_wanke": 50, "design_wanke": 450, "construction_interest_wanke": 500}
        original = copy.deepcopy(params)
        response = self.skill.calculate("molten_salt_steam", params)
        self.assertEqual(response["status"], "SUCCESS", response)
        result = response["results"]
        self.assertEqual(params, original)
        self.assertAlmostEqual(result["estimate_static_investment_wanke"], 21650, delta=1e-7)
        self.assertEqual(result["dynamic_investment_wanke"], 22150)
        self.assertAlmostEqual(result["fixed_assets_wanke"] + result["deductible_vat_wanke"], 22150, delta=1e-7)

    def test_invalid_inputs_block_delivery(self) -> None:
        for override in ({"heater_efficiency": 0}, {"steam_flow_th": -1}, {"steam_flow_th": math.nan},
                         {"steam_pressure_mpa": math.inf}, {"salt_type_id": .5},
                         {"heat_pump_cop": "invalid"}, {"steam_temperature_c": 389},
                         {"steam_temperature_c": 100}, {"steam_flow_th": 20},
                         {"salt_temperature_low_c": 390}, {"typo_parameter": 100}):
            with self.subTest(override=override):
                response = self.skill.calculate("molten_salt_steam", BASE | override)
                self.assertEqual(response["status"], "FAILED", response)
                self.assertNotIn("artifacts", response)
                self.assertNotIn("S8_REPORT_DELIVERY", str(response["fsm_trace"]))

    def test_missing_flow_is_not_silently_defaulted(self) -> None:
        response = self.skill.calculate("molten_salt_steam", {"steam_pressure_mpa": 1.5, "steam_temperature_c": 200})
        self.assertEqual(response["status"], "INTERRUPTED")
        self.assertEqual(response["missing_parameters"], ["steam_flow_th"])

    def test_fatal_audit_cannot_be_bypassed_and_alias_conflicts_fail(self) -> None:
        response = self.skill.calculate("molten_salt_steam", BASE | {"steam_temperature_c": 389},
                                        options={"audit_level": "WARN", "generate_excel": True})
        self.assertEqual(response["status"], "FAILED")
        self.assertNotIn("artifacts", response)
        response = self.skill.calculate("molten_salt_steam", BASE | {"流量": 200})
        self.assertEqual(response["status"], "FAILED")

    def test_saturated_steam_with_explicit_quality(self) -> None:
        result = self.calculate({"steam_temperature_c": Water.get_saturation_temperature(1.5),
                                 "steam_quality": 1})
        self.assertEqual(result["steam_quality"], 1)

    def test_inverse_gold_cases_are_actually_executed(self) -> None:
        cases = json.loads((ROOT / "scenarios/molten_salt_steam/benchmarks.json").read_text(encoding="utf-8-sig"))
        for case in cases:
            if case["mode"] != "INVERSE":
                continue
            with self.subTest(case=case["case_id"]):
                response = self.skill.calculate("molten_salt_steam", case["given"], targets=[case["target_param"]],
                                                options={"solution_mode": "INVERSE"})
                self.assertEqual(response["status"], "SUCCESS", response)
                flow_th = response["results"]["steam_flow_th"]
                self.assertTrue(case["expected_range"][0] <= flow_th <= case["expected_range"][1])
                budget_key = next(key for key in case["given"] if key.startswith("target_"))
                metric_key = budget_key.removeprefix("target_")
                forward_inputs = {key: value for key, value in case["given"].items() if key != budget_key}
                forward = self.calculate(forward_inputs | {"steam_flow_th": flow_th})
                self.assertLessEqual(forward[metric_key], case["given"][budget_key])
                beyond = self.calculate(forward_inputs | {"steam_flow_th": flow_th + 1e-5})
                self.assertGreater(beyond[metric_key], case["given"][budget_key])

    def test_inverse_rejects_infeasible_budget_and_overconstraint(self) -> None:
        given = {"steam_pressure_mpa": 1.5, "steam_temperature_c": 200, "target_dynamic_investment_wanke": 1}
        response = self.skill.calculate("molten_salt_steam", given)
        self.assertEqual(response["status"], "FAILED")
        self.assertIn("无可行解", str(response["diagnostics"]))
        response = self.skill.calculate("molten_salt_steam", BASE | {"target_dynamic_investment_wanke": 22650})
        self.assertEqual(response["status"], "FAILED")

    def test_inverse_searches_beyond_price_drop(self) -> None:
        # Heater tier at 100 MW can lower cost. Compare against an independent dense search.
        given = {"steam_pressure_mpa": 1.5, "steam_temperature_c": 200, "target_dynamic_investment_wanke": 27000}
        response = self.skill.calculate("molten_salt_steam", given)
        self.assertEqual(response["status"], "SUCCESS", response)
        found_th = response["results"]["steam_flow_th"]
        params = self.spec.align_parameters(BASE)
        references = self.spec.lookup_references(params)
        for flow_th in range(math.ceil(found_th), 501):
            continuous = self.spec.solve_continuous(params | {"steam_flow_th": flow_th}, references)
            discrete = self.spec.regularize_discrete(continuous, params)
            cost = equipment_costs(discrete, params, self.spec.costing_rules)["dynamic_investment_wanke"]
            self.assertGreater(cost, 27000)

    def test_manifest_declares_every_output_unit(self) -> None:
        result = self.calculate()
        declared = self.spec.manifest["parameters"] | self.spec.manifest["outputs"]
        for key in result:
            self.assertIn(key, declared)
            self.assertTrue(declared[key]["canonical_unit"])
