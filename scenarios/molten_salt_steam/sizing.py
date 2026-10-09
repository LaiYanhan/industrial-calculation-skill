"""熔盐项目离散选型；所有步长、型谱和功率因数由配置传入。"""
import math
from typing import Any, Mapping, Sequence

from scenarios.molten_salt_steam import equations as eq


def ceil_to_step(value: float, step: float, tolerance: float) -> float:
    """正数向上规整；仅消除整数边界的浮点运算尾差。"""
    if not math.isfinite(value) or value < 0 or not math.isfinite(step) or step <= 0:
        raise ValueError("规整量必须非负有限，步长必须为正有限数")
    scaled = value / step
    nearest = round(scaled)
    count = nearest if abs(scaled - nearest) <= tolerance else math.ceil(scaled)
    return float(count * step)


def select_transformers(demand_mva: float, standards_mva: Sequence[float],
                        tolerance: float) -> list[float]:
    """超过最大档时，多台最大档加一个余量档；绝不截断负载容量。"""
    if demand_mva <= 0 or not math.isfinite(demand_mva):
        raise ValueError("变压器负载必须为正有限数 (MVA)")
    if not standards_mva or any(value <= 0 for value in standards_mva):
        raise ValueError("变压器型谱必须为非空正数列表")
    if list(standards_mva) != sorted(set(standards_mva)):
        raise ValueError("变压器型谱必须严格递增")
    maximum_mva = standards_mva[-1]
    full_count = math.floor(demand_mva / maximum_mva)
    banks_mva = [float(maximum_mva)] * full_count
    remainder_mva = demand_mva - full_count * maximum_mva
    if remainder_mva > tolerance:
        banks_mva.append(float(next(capacity_mva for capacity_mva in standards_mva
                                    if capacity_mva + tolerance >= remainder_mva)))
    return banks_mva


def module_bank(power_mw: float, maximum_mw: float) -> list[float]:
    count = math.floor(power_mw / maximum_mw)
    remainder_mw = power_mw - count * maximum_mw
    return [maximum_mw] * count + ([remainder_mw] if remainder_mw > 0 else [])


def size_equipment(continuous: Mapping[str, float], params: Mapping[str, float],
                   rules: Mapping[str, Any]) -> dict[str, Any]:
    tolerance = rules["roundoff_tolerance"]
    heater_mw = ceil_to_step(continuous["heater_power_theoretical_mw"],
                             rules["electric_heater"]["roundup_mw"], tolerance)
    pump_mw = ceil_to_step(continuous["heat_pump_thermal_power_mw"],
                           rules["heat_pump"]["roundup_mw"], tolerance)
    storage_mwh = ceil_to_step(continuous["storage_capacity_theoretical_mwh"],
                               rules["storage"]["roundup_mwh"], tolerance)
    salt_mass_t = eq.calc_salt_mass_t(
        storage_mwh, continuous["salt_cp_kj_kg_k"], params["salt_temperature_high_c"],
        params["salt_temperature_low_c"], params["salt_mass_margin"])
    transformer = rules["transformer"]
    heater_banks_mva = select_transformers(
        continuous["heater_power_theoretical_mw"] / transformer["heater_power_factor"],
        transformer["standards_mva"], tolerance)
    pump_demand_mva = ceil_to_step(
        continuous["heat_pump_electric_power_mw"] / transformer["heat_pump_power_factor"],
        transformer["heat_pump_demand_step_mva"], tolerance)
    pump_banks_mva = select_transformers(pump_demand_mva, transformer["standards_mva"], tolerance)
    return {
        "heater_power_nominal_mw": heater_mw,
        "heat_pump_power_nominal_mw": pump_mw,
        "storage_capacity_mwh": storage_mwh,
        "molten_salt_mass_t": ceil_to_step(salt_mass_t, rules["salt"]["roundup_t"], tolerance),
        "sgs_power_nominal_mw": ceil_to_step(continuous["sgs_power_mw"],
                                            rules["sgs"]["roundup_mw"], tolerance),
        "sgs_catalog_power_mw": ceil_to_step(continuous["sgs_power_mw"],
                                            rules["sgs"]["catalog_step_mw"], tolerance),
        "transformer_capacity_mva": sum(heater_banks_mva),
        "heat_pump_transformer_capacity_mva": sum(pump_banks_mva),
        "transformer_banks_mva": heater_banks_mva,
        "heat_pump_transformer_banks_mva": pump_banks_mva,
        "heater_modules_mw": module_bank(heater_mw, rules["electric_heater"]["module_max_mw"]),
        "heat_pump_modules_mw": module_bank(pump_mw, rules["heat_pump"]["module_max_mw"]),
    }
