"""七表模板的场景绑定。只写输入/平衡项，保留原表公式并填入本次计算缓存。"""
from pathlib import Path
from typing import Any

import openpyxl

from engine.exporter.excel_exporter import ExcelTemplateExporter
from engine.fsm.context import ExecutionContext
from engine.properties.salt_adapter import MoltenSaltPropertyAdapter
from scenarios.molten_salt_steam.costing import allocate_cost

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def export_report(context: ExecutionContext, manifest: dict[str, Any],
                  costing_rules: dict[str, Any]) -> str:
    template = PROJECT_ROOT / "输入输出.xlsx"
    # 输出始终位于 exports，调用者只指定文件名，不能写到根目录或覆盖模板。
    output = PROJECT_ROOT / "exports" / f"molten_salt_steam_{context.execution_id}.xlsx"
    result = context.final_output["results"]
    params = context.canonical_params
    mapping: dict[str, Any] = {}
    caches: dict[str, Any] = {}
    overrides: set[str] = set()
    input_keys = (
        "steam_pressure_mpa", "steam_temperature_c", "steam_flow_th",
        "feedwater_pressure_mpa", "feedwater_temperature_c", "steam_supply_hours_h",
        "valley_power_hours_h", "operating_days_d", "heater_efficiency",
        "waste_heat_temperature_c", "heat_pump_cop", "heat_exchange_efficiency", "storage_efficiency")
    for row, key in enumerate(input_keys, 2):
        mapping[f"输入!D{row}"] = result[key]
    profile = manifest["salt_profiles"][str(int(params["salt_type_id"]))]
    mapping.update({"选型!D5": profile["label"], "选型!D6": params["salt_temperature_high_c"],
                    "选型!D7": params["salt_temperature_low_c"]})
    for profile_id, column, getter in (
        ("0", "E", MoltenSaltPropertyAdapter.get_hitec_properties),
        ("1", "K", MoltenSaltPropertyAdapter.get_solar_salt_properties),
    ):
        current = manifest["salt_profiles"][profile_id]
        selected = int(params["salt_type_id"]) == int(profile_id)
        high_c = params["salt_temperature_high_c"] if selected else current["high_c"]
        low_c = params["salt_temperature_low_c"] if selected else current["low_c"]
        mapping[f"熔盐参数!{column}3"] = high_c
        mapping[f"熔盐参数!{column}4"] = low_c
        for offset, temperature_c in enumerate((high_c, low_c)):
            properties = getter(temperature_c)
            for row, key in ((5, "density_kg_m3"), (7, "thermal_conductivity_kcal_m_h_k"),
                             (9, "viscosity_kg_s_m2"), (11, "specific_heat_kj_kg_k")):
                caches[f"熔盐参数!{column}{row + offset}"] = properties[key]
    calculations = {
        "D3": "steam_enthalpy_kj_kg", "D4": "feedwater_enthalpy_kj_kg", "D5": "sgs_power_mw",
        "D6": "heat_produced_mwh", "D7": "heater_power_theoretical_mw",
        "D8": "storage_capacity_theoretical_mwh", "D9": "annual_electricity_wan_kwh",
        "D10": "workbook_heater_annual_steam_wan_t",
        "J3": "steam_enthalpy_kj_kg", "J4": "feedwater_enthalpy_kj_kg", "J5": "sgs_power_mw",
        "J6": "heat_produced_mwh", "J7": "heat_pump_thermal_power_mw", "J8": "heat_pump_electric_power_mw",
        "J9": "storage_capacity_theoretical_mwh", "J10": "heat_pump_annual_electricity_wan_kwh",
        "J11": "annual_steam_wan_t",
    }
    caches.update({f"计算!{cell}": result[key] for cell, key in calculations.items()})
    for row, key in ((2, "heater_power_nominal_mw"), (3, "heat_pump_power_nominal_mw"),
                     (4, "storage_capacity_mwh"), (8, "salt_cp_kj_kg_k"), (9, "molten_salt_mass_t"),
                     (10, "sgs_power_nominal_mw"), (11, "transformer_capacity_mva"),
                     (12, "heat_pump_transformer_capacity_mva")):
        caches[f"选型!D{row}"] = result[key]
    if params["salt_type_id"] == 1:
        mapping["选型!D8"] = "=AVERAGE(熔盐参数!K11:K12)"
        overrides.add("选型!D8")
    if params["salt_mass_margin"] != manifest["parameters"]["salt_mass_margin"]["default"]:
        mapping["选型!D9"] = f'=ROUNDUP(D4*3600/D8/(D6-D7)*{params["salt_mass_margin"]},-1)'
        overrides.add("选型!D9")
    # 原模板 IFS 没有 >120MVA 分支，多机工况显式替换成所选组合的加和。
    for row, key in ((11, "transformer_banks_mva"), (12, "heat_pump_transformer_banks_mva")):
        if len(result[key]) > 1:
            mapping[f"选型!D{row}"] = "=SUM(" + ",".join(str(value) for value in result[key]) + ")"
            overrides.add(f"选型!D{row}")
    for row, key in ((3, "heater_unit_price_wanke_per_mw"), (4, "salt_unit_price_wanke_per_t"),
                     (5, "sgs_unit_price_wanke_per_mw"), (13, "heat_pump_unit_price_wanke_per_mw"),
                     (14, "salt_unit_price_wanke_per_t")):
        caches[f"造价!D{row}"] = result[key]
    for row, key in ((3, "cost_electric_heater_wanke"), (4, "cost_storage_system_wanke"),
                     (5, "cost_heat_exchange_wanke"), (6, "cost_electrical_system_wanke"),
                     (7, "equipment_investment_wanke"), (8, "construction_and_reserve_wanke"),
                     (9, "static_investment_wanke"), (13, "cost_heat_pump_wanke"),
                     (14, "cost_storage_system_wanke"), (15, "heat_pump_cost_heat_exchange_wanke"),
                     (16, "heat_pump_cost_electrical_system_wanke"), (17, "heat_pump_equipment_investment_wanke"),
                     (18, "heat_pump_construction_and_reserve_wanke"), (19, "heat_pump_static_investment_wanke")):
        caches[f"造价!E{row}"] = result[key]
    mapping["工程概算!G10"] = result["auxiliary_system_wanke"]
    for cell, key in (("G6", "thermal_system_wanke"), ("G7", "water_treatment_wanke"),
                      ("G8", "water_supply_wanke"), ("F12", "site_clearance_wanke"),
                      ("C39", "preliminary_work_wanke"), ("C41", "design_wanke"),
                      ("C42", "design_review_wanke"), ("C44", "inspection_wanke"),
                      ("C46", "commissioning_wanke"), ("C48", "vehicles_wanke")):
        mapping[f"工程概算!{cell}"] = params[key]
    if params["construction_interest_wanke"] != manifest["parameters"]["construction_interest_wanke"]["default"]:
        mapping["工程概算!F21"] = "=" + str(params["construction_interest_wanke"])
        overrides.add("工程概算!F21")
    # 仅缓存模板已有公式；未使用的空白单元格不填零以免改变版式。
    workbook = openpyxl.load_workbook(template, data_only=False, keep_links=True)
    try:
        for row, columns in result["project_estimate_rows"].items():
            for column, value in columns.items():
                cell = f"{column}{row}"
                if workbook["工程概算"][cell].data_type == "f":
                    caches[f"工程概算!{cell}"] = value
        caches["工程概算!I19"] = result["estimate_balance_residual_wanke"]
        for column, value in zip("KLM", allocate_cost(result["cost_heat_pump_wanke"],
                                                       costing_rules["allocations"]["heat_pump"])):
            caches[f"工程概算!{column}5"] = value
        caches["工程概算!N5"] = result["cost_heat_pump_wanke"]
    finally:
        workbook.close()
    return ExcelTemplateExporter(template).export(output, mapping, formula_values=caches,
                                                  formula_overrides=overrides)
