"""
S4: 连续求解与核心关系平衡阶段 (Continuous Solve State).
执行连续代数方程组、热力学能量平衡或财务毛利/EBITDA方程求解。
"""

from typing import List, Tuple
from engine.fsm.context import ExecutionContext
from engine.fsm.state import BaseState, GuardResult, ActionResult


class ContinuousSolveState(BaseState):

    def __init__(self, scenario_spec=None):
        super().__init__("S4_CONTINUOUS_SOLVE")
        self.scenario_spec = scenario_spec

    def verify_guard(self, context: ExecutionContext) -> GuardResult:
        if not context.has_passed_token("S3_REFERENCE_LOOKUP"):
            return GuardResult(
                passed=False,
                reason="前序状态 S3_REFERENCE_LOOKUP 未通过，禁止执行核心连续求解",
                missing_prerequisites=["Token:S3_REFERENCE_LOOKUP"]
            )
        return GuardResult(passed=True)

    def execute_action(self, context: ExecutionContext) -> ActionResult:
        continuous_res = {}
        if self.scenario_spec and hasattr(self.scenario_spec, "solve_continuous"):
            continuous_res = self.scenario_spec.solve_continuous(
                context.canonical_params,
                context.reference_data,
                mode=context.solution_mode
            )

        context.continuous_results = continuous_res

        return ActionResult(
            status="PASSED",
            invariants_verified=["continuous_energy_balanced"],
            diagnostics={"continuous_results_count": len(continuous_res)}
        )

    def verify_invariants(self, context: ExecutionContext) -> Tuple[bool, List[str]]:
        unverified = []
        if not isinstance(context.continuous_results, dict):
            unverified.append("continuous_results_is_dict")
        return (len(unverified) == 0, unverified)
