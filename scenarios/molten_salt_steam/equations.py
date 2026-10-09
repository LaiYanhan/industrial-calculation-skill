"""纯代数热平衡，兼容 float / SymPy；查表、取整与 I/O 均在外部执行。
1 t = 1000 kg，1 MW = 1000 kJ/s，1 h = 3600 s。
t/h × kJ/kg / 3600 = MW，MWh × 3600 / (kJ/kg) = t。
效率、裕量和温区由 manifest 提供，不隐含默认工况。
"""
from typing import TypeVar

Scalar = TypeVar("Scalar")
SECONDS_PER_HOUR = 3600.0
KWH_PER_MWH = 1000.0
UNITS_PER_TEN_THOUSAND = 10000.0


def calc_sgs_power_mw(steam_flow_th: Scalar, h_steam_kj_kg: Scalar,
                      h_feedwater_kj_kg: Scalar) -> Scalar:
    return steam_flow_th * (h_steam_kj_kg - h_feedwater_kj_kg) / SECONDS_PER_HOUR


def calc_heat_produced_mwh(sgs_power_mw: Scalar, supply_hours_h: Scalar,
                           exchange_eff: Scalar) -> Scalar:
    return sgs_power_mw * supply_hours_h / exchange_eff


def calc_heater_power_mw(heat_produced_mwh: Scalar, valley_hours_h: Scalar,
                         heater_eff: Scalar) -> Scalar:
    return heat_produced_mwh / valley_hours_h / heater_eff


def calc_storage_capacity_mwh(heat_produced_mwh: Scalar, storage_eff: Scalar) -> Scalar:
    return heat_produced_mwh / storage_eff


def calc_salt_mass_t(storage_capacity_mwh: Scalar, salt_cp_kj_kg_k: Scalar,
                     temp_high_c: Scalar, temp_low_c: Scalar,
                     safety_margin: Scalar) -> Scalar:
    """连续盐量 (t)；S5 用规整后的储热量调用，再独立规整盐量。"""
    return (storage_capacity_mwh * SECONDS_PER_HOUR * safety_margin
            / salt_cp_kj_kg_k / (temp_high_c - temp_low_c))


def calc_heat_pump_thermal_power_mw(heat_produced_mwh: Scalar,
                                   valley_hours_h: Scalar) -> Scalar:
    return heat_produced_mwh / valley_hours_h


def calc_heat_pump_electric_power_mw(thermal_power_mw: Scalar, cop: Scalar) -> Scalar:
    return thermal_power_mw / cop


def calc_annual_electricity_wan_kwh(power_mw: Scalar, hours_h: Scalar,
                                   operating_days_d: Scalar) -> Scalar:
    return power_mw * hours_h * operating_days_d * KWH_PER_MWH / UNITS_PER_TEN_THOUSAND


def calc_annual_steam_wan_t(steam_flow_th: Scalar, supply_hours_h: Scalar,
                           operating_days_d: Scalar) -> Scalar:
    return steam_flow_th * supply_hours_h * operating_days_d / UNITS_PER_TEN_THOUSAND
