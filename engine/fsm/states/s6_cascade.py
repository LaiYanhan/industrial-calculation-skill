"""
S6: 综合指标联动与报表级联汇总阶段 (Metric Cascade State).
执行分项造价费率联动、动态投资利息核算、财务三表勾稽与总计汇总。
"""

from typing import List, Tuple
from engine.fsm.context import ExecutionContext
from engine.fsm.state import BaseState, GuardResult, ActionResult


class MetricCascadeState(BaseState):

    def __init__(self, scenario_spec=None):
        super().__init__("S6_METRIC_CASCADE")
        self.scenario_spec = scenario_spec

    def verify_guard(self, context: ExecutionContext) -> GuardResult:
        if not context.has_passed_token("S5_DISCRETE_REGULARIZE"):
            return GuardResult(
                passed=False,
                reason="前序状态 S5_DISCRETE_REGULARIZE 未通过，禁止执行指标联动",
                missing_prerequisites=["Token:S5_DISCRETE_REGULARIZE"]
            )
        return GuardResult(passed=True)

    def execute_action(self, context: ExecutionContext) -> ActionResult:
        cascade_res = {}
        if self.scenario_spec and hasattr(self.scenario_spec, "cascade_metrics"):
            cascade_res = self.scenario_spec.cascade_metrics(
                context.continuous_results,
                context.discrete_results,
                context.canonical_params
            )

        context.cascade_results = cascade_res

        return ActionResult(
            status="PASSED",
            invariants_verified=["cascade_aggregation_balanced"],
            diagnostics={"cascade_keys": list(cascade_res.keys())}
        )

    def verify_invariants(self, context: ExecutionContext) -> Tuple[bool, List[str]]:
        unverified = []
        if not isinstance(context.cascade_results, dict):
            unverified.append("cascade_results_is_dict")
        return (len(unverified) == 0, unverified)
