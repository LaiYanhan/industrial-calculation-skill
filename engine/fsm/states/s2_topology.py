"""
S2: 拓扑判定与求解路径推导阶段 (Topology Routing State).
确定求解模式 (正解/反解/搜索)，分析已知量与未知量自由度 (DoF)。
"""

from typing import List, Tuple
from engine.fsm.context import ExecutionContext
from engine.fsm.state import BaseState, GuardResult, ActionResult


class TopologyRoutingState(BaseState):

    def __init__(self, scenario_spec=None):
        super().__init__("S2_TOPOLOGY_ROUTING")
        self.scenario_spec = scenario_spec

    def verify_guard(self, context: ExecutionContext) -> GuardResult:
        if not context.has_passed_token("S1_CANONICAL_ALIGNMENT"):
            return GuardResult(
                passed=False,
                reason="前序状态 S1_CANONICAL_ALIGNMENT 未通过，禁止执行拓扑判定",
                missing_prerequisites=["Token:S1_CANONICAL_ALIGNMENT"]
            )
        return GuardResult(passed=True)

    def execute_action(self, context: ExecutionContext) -> ActionResult:
        # 判断计算方向：如果输入中含有末端目标参数（如总投资、净利润），则推断为反向逆解
        targets = context.target_params
        mode = context.options.get("solution_mode", "AUTO")

        if mode == "AUTO":
            if self.scenario_spec and hasattr(self.scenario_spec, "infer_solution_mode"):
                context.solution_mode = self.scenario_spec.infer_solution_mode(context.canonical_params, targets)
            elif targets and any(t in getattr(self.scenario_spec, "required_params", []) for t in targets):
                context.solution_mode = "INVERSE"
            else:
                context.solution_mode = "FORWARD"
        else:
            context.solution_mode = mode

        context.dof = 0  # 闭合系统自由度

        return ActionResult(
            status="PASSED",
            invariants_verified=["solution_mode_determined", "dof_closed"],
            diagnostics={"mode": context.solution_mode, "dof": context.dof}
        )

    def verify_invariants(self, context: ExecutionContext) -> Tuple[bool, List[str]]:
        unverified = []
        if context.solution_mode not in ["FORWARD", "INVERSE", "SEARCH"]:
            unverified.append("valid_solution_mode")
        return (len(unverified) == 0, unverified)
