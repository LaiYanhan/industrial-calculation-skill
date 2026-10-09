"""
预算反解：遍历离散价格函数的所有平台端点与阶梯跳跃门槛，求预算内最大流量。

阶梯单价会在折扣门槛发生向下跳跃（如 99MW 按 40万/MW，100MW 降为 38万/MW），
整段投资函数非严格单调，严禁直接使用朴素二分法。
本模块通过收集所有选型规整步长与造价折扣阶梯断点，构建平台端点集，
调用底层 NumericInverter.solve_piecewise_stepped_inverse 执行倒序平台枚举与区间求根。
"""

import math
from typing import Any, Callable, Mapping

from engine.solver.numeric_inverter import NumericInverter


def maximize_flow_under_budget(
    unit_continuous: Mapping[str, float], rules: Mapping[str, Any],
    lower_flow_th: float, upper_flow_th: float, budget_wanke: float,
    evaluate_cost: Callable[[float], float],
) -> float:
    boundaries_th = {lower_flow_th, upper_flow_th}

    def add_steps(coefficient: float, step: float) -> None:
        if coefficient <= 0 or step <= 0:
            return
        for count in range(1, math.ceil(coefficient * upper_flow_th / step) + 1):
            flow_th = count * step / coefficient
            if lower_flow_th <= flow_th <= upper_flow_th:
                boundaries_th.add(flow_th)

    # 1. 离散设备选型步长端点 (Sizing Rounding Steps)
    for key, step in (
        ("heater_power_theoretical_mw", rules["electric_heater"]["roundup_mw"]),
        ("heat_pump_thermal_power_mw", rules["heat_pump"]["roundup_mw"]),
        ("storage_capacity_theoretical_mwh", rules["storage"]["roundup_mwh"]),
        ("sgs_power_mw", rules["sgs"]["roundup_mw"]),
    ):
        if key in unit_continuous and unit_continuous[key] > 0:
            add_steps(unit_continuous[key], step)

    # 2. 变压器标准型谱离散门槛 (Transformer Standard Tiers)
    transformer = rules["transformer"]
    standards_mva = transformer["standards_mva"]
    max_mva = standards_mva[-1]
    for coefficient, rounded in (
        (unit_continuous["heater_power_theoretical_mw"] / transformer["heater_power_factor"], False),
        (unit_continuous["heat_pump_electric_power_mw"] / transformer["heat_pump_power_factor"], True),
    ):
        if coefficient <= 0:
            continue
        for bank in range(math.ceil(coefficient * upper_flow_th / max_mva) + 1):
            for capacity_mva in standards_mva:
                threshold_mva = bank * max_mva + capacity_mva
                if rounded:
                    step_mva = transformer["heat_pump_demand_step_mva"]
                    threshold_mva = math.floor(threshold_mva / step_mva) * step_mva
                flow_th = threshold_mva / coefficient
                if lower_flow_th <= flow_th <= upper_flow_th:
                    boundaries_th.add(flow_th)

    # 3. 造价分档折扣门槛 (Pricing Tier Thresholds - 产生负跳跃降价的临界点)
    # 电加热器阶梯折扣: 100 MW, 200 MW
    heater_coef = unit_continuous.get("heater_power_theoretical_mw", 0.0)
    if heater_coef > 0:
        for cap_mw in (100.0, 200.0):
            f_th = cap_mw / heater_coef
            if lower_flow_th <= f_th <= upper_flow_th:
                boundaries_th.add(f_th)

    # 换热系统阶梯折扣: 250 MW, 350 MW
    sgs_coef = unit_continuous.get("sgs_power_mw", 0.0)
    if sgs_coef > 0:
        for cap_mw in (250.0, 350.0):
            f_th = cap_mw / sgs_coef
            if lower_flow_th <= f_th <= upper_flow_th:
                boundaries_th.add(f_th)

    # 热泵阶梯折扣: 150 MWt
    hp_coef = unit_continuous.get("heat_pump_thermal_power_mw", 0.0)
    if hp_coef > 0:
        f_th = 150.0 / hp_coef
        if lower_flow_th <= f_th <= upper_flow_th:
            boundaries_th.add(f_th)

    # 4. 调用 NumericInverter 求解非严格单调阶梯反解
    optimal_flow = NumericInverter.solve_piecewise_stepped_inverse(
        forward_eval_fn=evaluate_cost,
        target_y=budget_wanke,
        candidate_breakpoints=list(boundaries_th),
        tol=1e-4,
        max_iter=60
    )

    if optimal_flow is not None:
        return optimal_flow

    raise ValueError("给定预算在声明流量范围内无可行解")
