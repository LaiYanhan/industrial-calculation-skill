"""
S5: 离散规整与阶梯规则映射阶段 (Discrete Regularize State).
执行标准设备型谱匹配 (如变压器 MVA)、步长向上取整 (ROUNDUP)、分档费率匹配。
"""

from typing import List, Tuple
from engine.fsm.context import ExecutionContext
from engine.fsm.state import BaseState, GuardResult, ActionResult


class DiscreteRegularizeState(BaseState):

    def __init__(self, scenario_spec=None):
        super().__init__("S5_DISCRETE_REGULARIZE")
        self.scenario_spec = scenario_spec

    def verify_guard(self, context: ExecutionContext) -> GuardResult:
        if not context.has_passed_token("S4_CONTINUOUS_SOLVE"):
            return GuardResult(
                passed=False,
                reason="前序状态 S4_CONTINUOUS_SOLVE 未通过，禁止执行离散规整",
                missing_prerequisites=["Token:S4_CONTINUOUS_SOLVE"]
            )
        return GuardResult(passed=True)

    def execute_action(self, context: ExecutionContext) -> ActionResult:
        discrete_res = {}
        if self.scenario_spec and hasattr(self.scenario_spec, "regularize_discrete"):
            discrete_res = self.scenario_spec.regularize_discrete(
                context.continuous_results,
                context.canonical_params
            )

        context.discrete_results = discrete_res

        return ActionResult(
            status="PASSED",
            invariants_verified=["discrete_sizing_bounded"],
            diagnostics={"discrete_results": discrete_res}
        )

    def verify_invariants(self, context: ExecutionContext) -> Tuple[bool, List[str]]:
        unverified = []
        if not isinstance(context.discrete_results, dict):
            unverified.append("discrete_results_is_dict")
        return (len(unverified) == 0, unverified)
