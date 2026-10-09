"""预算反解：遍历离散价格函数的所有平台右端点，求预算内最大流量。

阶梯单价会在折扣门槛下降，整段函数不单调，不能用普通二分法。
连续功率/储热量均与流量线性，盐量仅随规整储热量变化，因而以下
断点集合完整覆盖报价变化。候选只是纯函数试算；FSM 仍按 S0~S8 运行。
"""
import math
from typing import Any, Callable, Mapping


def maximize_flow_under_budget(
    unit_continuous: Mapping[str, float], rules: Mapping[str, Any],
    lower_flow_th: float, upper_flow_th: float, budget_wanke: float,
    evaluate_cost: Callable[[float], float],
) -> float:
    boundaries_th = {lower_flow_th, upper_flow_th}

    def add_steps(coefficient: float, step: float) -> None:
        for count in range(1, math.ceil(coefficient * upper_flow_th / step) + 1):
            flow_th = count * step / coefficient
            if lower_flow_th <= flow_th <= upper_flow_th:
                boundaries_th.add(flow_th)

    for key, step in (
        ("heater_power_theoretical_mw", rules["electric_heater"]["roundup_mw"]),
        ("heat_pump_thermal_power_mw", rules["heat_pump"]["roundup_mw"]),
        ("storage_capacity_theoretical_mwh", rules["storage"]["roundup_mwh"]),
        ("sgs_power_mw", rules["sgs"]["roundup_mw"]),
    ):
        add_steps(unit_continuous[key], step)
    transformer = rules["transformer"]
    standards_mva = transformer["standards_mva"]
    max_mva = standards_mva[-1]
    for coefficient, rounded in (
        (unit_continuous["heater_power_theoretical_mw"] / transformer["heater_power_factor"], False),
        (unit_continuous["heat_pump_electric_power_mw"] / transformer["heat_pump_power_factor"], True),
    ):
        for bank in range(math.ceil(coefficient * upper_flow_th / max_mva) + 1):
            for capacity_mva in standards_mva:
                threshold_mva = bank * max_mva + capacity_mva
                if rounded:
                    step_mva = transformer["heat_pump_demand_step_mva"]
                    threshold_mva = math.floor(threshold_mva / step_mva) * step_mva
                flow_th = threshold_mva / coefficient
                if lower_flow_th <= flow_th <= upper_flow_th:
                    boundaries_th.add(flow_th)
    for flow_th in sorted(boundaries_th, reverse=True):
        if evaluate_cost(flow_th) <= budget_wanke:
            return flow_th
    raise ValueError("给定预算在声明流量范围内无可行解")
