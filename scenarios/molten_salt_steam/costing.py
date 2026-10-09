"""输入输出.xlsx 造价与工程概算的纯函数；金额统一为万元。

G10 辅助系统金额从静态投资控制额反解。其余费用对三类工程费是线性的，
可用单位增量求斜率，避免循环引用或把基准 G10 固定用于所有规模。
"""
from typing import Any, Mapping, Sequence


def tier_price(quantity: float, tiers: Sequence[Mapping[str, Any]]) -> float:
    for tier in tiers:
        if tier["upper"] is None or quantity < tier["upper"]:
            return float(tier["unit_price"])
    raise ValueError("数量超出计价表范围")


def equipment_costs(discrete: Mapping[str, Any], params: Mapping[str, float],
                    rules: Mapping[str, Any]) -> dict[str, float]:
    pricing = rules["equipment_pricing"]
    heater_mw = discrete["heater_power_nominal_mw"]
    pump_mw = discrete["heat_pump_power_nominal_mw"]
    salt_mass_t = discrete["molten_salt_mass_t"]
    sgs_mw = discrete["sgs_power_nominal_mw"]
    pump_rules = pricing["heat_pump"]
    size = "small" if pump_mw < pump_rules["power_threshold_mw"] else "large"
    source = ("cold" if params["waste_heat_temperature_c"]
              < pump_rules["source_temperature_threshold_c"] else "warm")
    result = {
        "heater_unit_price_wanke_per_mw": tier_price(heater_mw, pricing["heater"]["tiers"]),
        "salt_unit_price_wanke_per_t": tier_price(salt_mass_t, pricing["storage_system"]["tiers"]),
        "sgs_unit_price_wanke_per_mw": tier_price(sgs_mw, pricing["heat_exchange"]["tiers"]),
        "heat_pump_unit_price_wanke_per_mw": float(pump_rules[f"{size}_{source}_wanke_per_mw"]),
    }
    result.update({
        "cost_electric_heater_wanke": heater_mw * result["heater_unit_price_wanke_per_mw"],
        "cost_storage_system_wanke": salt_mass_t * result["salt_unit_price_wanke_per_t"],
        "cost_heat_exchange_wanke": sgs_mw * result["sgs_unit_price_wanke_per_mw"],
        "cost_electrical_system_wanke": discrete["transformer_capacity_mva"] * pricing["electrical_wanke_per_mva"],
        "cost_heat_pump_wanke": pump_mw * result["heat_pump_unit_price_wanke_per_mw"],
        "heat_pump_cost_heat_exchange_wanke": sgs_mw * pump_rules["heat_exchange_wanke_per_mw"],
        "heat_pump_cost_electrical_system_wanke": discrete["heat_pump_transformer_capacity_mva"] * pricing["electrical_wanke_per_mva"],
    })
    result["equipment_investment_wanke"] = sum(result[key] for key in (
        "cost_electric_heater_wanke", "cost_storage_system_wanke",
        "cost_heat_exchange_wanke", "cost_electrical_system_wanke"))
    result["heat_pump_equipment_investment_wanke"] = sum(result[key] for key in (
        "cost_heat_pump_wanke", "cost_storage_system_wanke",
        "heat_pump_cost_heat_exchange_wanke", "heat_pump_cost_electrical_system_wanke"))
    for prefix in ("", "heat_pump_"):
        equipment_wanke = result[prefix + "equipment_investment_wanke"]
        static_wanke = equipment_wanke / rules["economic_ratios"]["equipment_to_static_ratio"]
        result[prefix + "static_investment_wanke"] = static_wanke
        result[prefix + "construction_and_reserve_wanke"] = static_wanke - equipment_wanke
        result[prefix + "dynamic_investment_wanke"] = static_wanke + params["construction_interest_wanke"]
    return result


def allocate_cost(total_wanke: float, weights: Sequence[float]) -> tuple[float, float, float]:
    denominator = sum(weights)
    return tuple(total_wanke * weight / denominator for weight in weights)


def other_fees(construction_wanke: float, equipment_wanke: float,
               installation_wanke: float, params: Mapping[str, float],
               fees: Mapping[str, float]) -> dict[int, float]:
    """返回 C31:C50 的行号→金额映射，行号仅用于对应原表。"""
    civil_wanke = construction_wanke + installation_wanke
    works_wanke = civil_wanke + equipment_wanke
    rows = {
        32: civil_wanke * fees["owner_management_rate"],
        33: works_wanke * fees["tender_rate"],
        34: civil_wanke * fees["supervision_rate"],
        35: (equipment_wanke + civil_wanke * fees["material_construction_weight"]) * fees["material_rate"],
        36: civil_wanke * fees["consulting_rate"],
        37: works_wanke * fees["insurance_rate"],
        39: params["preliminary_work_wanke"],
        40: equipment_wanke * fees["equipment_technical_rate"],
        41: params["design_wanke"],
        42: params["design_review_wanke"],
        43: civil_wanke * fees["evaluation_rate"],
        44: params["inspection_wanke"],
        45: civil_wanke * fees["standards_rate"],
        46: params["commissioning_wanke"],
        48: params["vehicles_wanke"],
        49: civil_wanke * fees["furniture_rate"],
        50: civil_wanke * fees["training_rate"] * fees["training_factor"],
    }
    rows[31] = sum(rows[row] for row in range(32, 38))
    rows[38] = sum(rows[row] for row in range(39, 46))
    rows[47] = sum(rows[row] for row in range(48, 51))
    return rows


def estimate_project(costs: Mapping[str, float], params: Mapping[str, float],
                     rules: Mapping[str, Any], heat_pump: bool = False) -> dict[str, Any]:
    prefix = "heat_pump_" if heat_pump else ""
    allocations = rules["allocations"]
    row_amounts = {
        3: (costs["cost_storage_system_wanke"], "storage"),
        4: (costs[prefix + "cost_heat_exchange_wanke"], "sgs"),
        5: (costs["cost_heat_pump_wanke" if heat_pump else "cost_electric_heater_wanke"],
            "heat_pump" if heat_pump else "heater"),
        6: (params["thermal_system_wanke"], "thermal"),
        7: (params["water_treatment_wanke"], "treatment"),
        8: (params["water_supply_wanke"], "supply"),
        9: (costs[prefix + "cost_electrical_system_wanke"], "electrical"),
    }
    detail = {row: allocate_cost(amount_wanke, allocations[kind])
              for row, (amount_wanke, kind) in row_amounts.items()}
    base = tuple(sum(parts[column] for parts in detail.values()) for column in range(3))
    auxiliary_weights = allocate_cost(1.0, allocations["auxiliary"])

    def totals(auxiliary_wanke: float) -> tuple[tuple[float, ...], dict[int, float], float, float]:
        parts = tuple(base[column] + auxiliary_wanke * auxiliary_weights[column]
                      for column in range(3))
        fee_rows = other_fees(*parts, params, rules["fees"])
        other_wanke = params["site_clearance_wanke"] + sum(fee_rows[row] for row in (31, 38, 46, 47))
        reserve_wanke = sum(parts) * rules["fees"]["reserve_rate"]
        return parts, fee_rows, other_wanke, reserve_wanke

    base_parts, _, base_other_wanke, base_reserve_wanke = totals(0.0)
    base_static_wanke = sum(base_parts) + base_other_wanke + base_reserve_wanke
    # 对辅助系统的单位增量直接计算变动费率，避免两个大总额相减损失精度。
    variable_params = dict(params)
    for key in ("preliminary_work_wanke", "design_wanke", "design_review_wanke",
                "inspection_wanke", "commissioning_wanke", "vehicles_wanke"):
        variable_params[key] = 0.0
    marginal_fees = other_fees(*auxiliary_weights, variable_params, rules["fees"])
    slope = (sum(auxiliary_weights) * (1 + rules["fees"]["reserve_rate"])
             + sum(marginal_fees[row] for row in (31, 38, 46, 47)))
    target_static_wanke = costs[prefix + "static_investment_wanke"]
    auxiliary_wanke = (target_static_wanke - base_static_wanke) / slope
    parts, fee_rows, other_wanke, reserve_wanke = totals(auxiliary_wanke)
    detail[10] = allocate_cost(auxiliary_wanke, allocations["auxiliary"])
    columns = ("construction", "equipment", "installation", "other")
    static_parts = (*parts, other_wanke + reserve_wanke)
    dynamic_parts = (*parts, static_parts[-1] + params["construction_interest_wanke"])
    deductible_parts = tuple(amount_wanke / (1 + rules["vat"][column]["denominator_rate"])
                             * rules["vat"][column]["deduction_rate"]
                             for column, amount_wanke in zip(columns, dynamic_parts))
    fixed_parts = tuple(amount_wanke - vat_wanke for amount_wanke, vat_wanke
                        in zip(dynamic_parts, deductible_parts))
    rows: dict[str, dict[str, float]] = {}

    def set_row(row: int, amounts: Sequence[float]) -> None:
        rows[str(row)] = {column: amount_wanke for column, amount_wanke in zip("CDEF", amounts)}
        rows[str(row)]["G"] = sum(amounts)

    for row, amounts in detail.items():
        set_row(row, (*amounts, 0.0))
    set_row(2, (*parts, 0.0))
    set_row(11, (0.0, 0.0, 0.0, other_wanke))
    for row, amount_wanke in {12: params["site_clearance_wanke"], 13: fee_rows[31],
                             14: fee_rows[38], 15: fee_rows[46], 16: fee_rows[47],
                             17: 0.0, 18: reserve_wanke,
                             21: params["construction_interest_wanke"]}.items():
        set_row(row, (0.0, 0.0, 0.0, amount_wanke))
    set_row(19, static_parts)
    set_row(20, tuple(amount_wanke / target_static_wanke for amount_wanke in static_parts))
    set_row(22, dynamic_parts)
    set_row(23, deductible_parts)
    set_row(24, fixed_parts)
    for row, amount_wanke in fee_rows.items():
        rows[str(row)] = {"C": amount_wanke}
    return {
        "project_estimate_rows": rows,
        "auxiliary_system_wanke": auxiliary_wanke,
        "construction_cost_wanke": parts[0],
        "equipment_purchase_wanke": parts[1],
        "installation_cost_wanke": parts[2],
        "other_fees_wanke": other_wanke,
        "basic_reserve_wanke": reserve_wanke,
        "deductible_vat_wanke": sum(deductible_parts),
        "fixed_assets_wanke": sum(fixed_parts),
        "estimate_static_investment_wanke": sum(static_parts),
        "estimate_balance_residual_wanke": sum(static_parts) - target_static_wanke,
    }
