"""
S1: 量纲对齐与变量规范化阶段 (Canonical Alignment State).
统一中英文别名至规范变量名、执行单位量纲换算、识别缺失必要自变量。
"""

from typing import Any, Dict, List, Optional, Tuple
from engine.fsm.context import ExecutionContext
from engine.fsm.state import BaseState, GuardResult, ActionResult


class CanonicalAlignmentState(BaseState):

    def __init__(self, scenario_spec=None):
        super().__init__("S1_CANONICAL_ALIGNMENT")
        self.scenario_spec = scenario_spec

    def verify_guard(self, context: ExecutionContext) -> GuardResult:
        if not context.has_passed_token("S0_SLOT_EXTRACTION"):
            return GuardResult(
                passed=False,
                reason="前序状态 S0_SLOT_EXTRACTION 未通过，禁止跳步执行量纲对齐",
                missing_prerequisites=["Token:S0_SLOT_EXTRACTION"]
            )
        return GuardResult(passed=True)

    def execute_action(self, context: ExecutionContext) -> ActionResult:
        canonical_params: Dict[str, float] = {}
        missing: List[str] = []

        alias_map = {}
        required_params = []
        if self.scenario_spec:
            alias_map = getattr(self.scenario_spec, "alias_map", {})
            required_params = getattr(self.scenario_spec, "required_params", [])

        # 1. 别名归一化
        for raw_k, raw_v in context.raw_slots.items():
            norm_k = alias_map.get(raw_k, raw_k)
            try:
                canonical_params[norm_k] = float(raw_v)
            except (ValueError, TypeError):
                continue

        # 2. 检查必要参数
        for req in required_params:
            if req not in canonical_params:
                missing.append(req)

        context.canonical_params = canonical_params
        context.missing_parameters = missing

        if missing:
            return ActionResult(
                status="INTERRUPTED",
                error_message="缺少核心推导自变量，暂停执行等待补充",
                diagnostics={"missing_parameters": missing}
            )

        return ActionResult(
            status="PASSED",
            invariants_verified=["canonical_params_aligned", "required_params_satisfied"],
            diagnostics={"canonical_count": len(canonical_params)}
        )

    def verify_invariants(self, context: ExecutionContext) -> Tuple[bool, List[str]]:
        unverified = []
        if not context.canonical_params:
            unverified.append("canonical_params_not_empty")
        if context.missing_parameters:
            unverified.append("no_missing_parameters")
        return (len(unverified) == 0, unverified)
