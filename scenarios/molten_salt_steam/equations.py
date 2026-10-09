"""
谷电熔盐储热连续物理与热力学代数方程 (Continuous Equations).
公式与 输入输出.xlsx '计算' 与 '选型' 工作表逻辑严格对齐。
"""

import math


def calc_sgs_power_mw(steam_flow_th: float, h_steam_kj_kg: float, h_feedwater_kj_kg: float) -> float:
    """SGS 换热功率 (MW): D * (h_out - h_in) / 3600"""
    return steam_flow_th * (h_steam_kj_kg - h_feedwater_kj_kg) / 3600.0


def calc_heat_produced_mwh(sgs_power_mw: float, supply_hours_h: float, exchange_eff: float = 0.99) -> float:
    """制热量 (MWh): SGS功率 * 供汽时长 / 换热效率"""
    return sgs_power_mw * supply_hours_h / exchange_eff


def calc_heater_power_mw(heat_produced_mwh: float, valley_hours_h: float, heater_eff: float = 0.985) -> float:
    """电加热器理论电功率 (MW): 制热量 / 谷电时长 / 电热效率"""
    return heat_produced_mwh / valley_hours_h / heater_eff


def calc_storage_capacity_mwh(heat_produced_mwh: float, storage_eff: float = 0.99) -> float:
    """储热量 (MWh): 制热量 / 储热效率"""
    return heat_produced_mwh / storage_eff


def calc_salt_mass_t(
    storage_capacity_mwh: float,
    salt_cp_kj_kg_k: float = 1.42,
    temp_high_c: float = 390.0,
    temp_low_c: float = 190.0,
    safety_margin: float = 1.1
) -> float:
    """
    熔盐用量 (吨): ROUNDUP(E * 3600 / cp / delta_T * 1.1, -1)
    """
    delta_t = temp_high_c - temp_low_c
    raw_mass = (storage_capacity_mwh * 3600.0) / salt_cp_kj_kg_k / delta_t * safety_margin
    # 向上规整至 10 的倍数
    return float(math.ceil(raw_mass / 10.0) * 10)
