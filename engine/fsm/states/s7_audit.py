"""
S7: 业务不变量与合理性常理审计阶段 (Sanity Audit State).
审查热工夹点温差、设备裕量合理性、借贷平衡、非负性约束等领域硬性门禁。
"""

from typing import List, Tuple
from engine.fsm.context import ExecutionContext
from engine.fsm.state import BaseState, GuardResult, ActionResult


class SanityAuditState(BaseState):

    def __init__(self, scenario_spec=None):
        super().__init__("S7_SANITY_AUDIT")
        self.scenario_spec = scenario_spec

    def verify_guard(self, context: ExecutionContext) -> GuardResult:
        if not context.has_passed_token("S6_METRIC_CASCADE"):
            return GuardResult(
                passed=False,
                reason="前序状态 S6_METRIC_CASCADE 未通过，禁止执行常理审计",
                missing_prerequisites=["Token:S6_METRIC_CASCADE"]
            )
        return GuardResult(passed=True)

    def execute_action(self, context: ExecutionContext) -> ActionResult:
        violations = []
        warnings = []

        if self.scenario_spec and hasattr(self.scenario_spec, "audit_sanity"):
            violations, warnings = self.scenario_spec.audit_sanity(context)

        context.audit_violations = violations
        context.audit_warnings = warnings
        context.audit_passed = (len(violations) == 0)

        # violations 是致命违规，任何审计级别都不能将其降级为可交付警告。
        if violations:
            return ActionResult(
                status="FAILED",
                error_message="常理审计未通过，存在违背领域规则的致命违规",
                diagnostics={"violations": violations, "warnings": warnings}
            )

        return ActionResult(
            status="PASSED",
            invariants_verified=["domain_sanity_checked", "zero_fatal_violations"],
            diagnostics={"violations_count": len(violations), "warnings_count": len(warnings)}
        )

    def verify_invariants(self, context: ExecutionContext) -> Tuple[bool, List[str]]:
        unverified = []
        if not context.audit_passed:
            unverified.append("audit_passed_strictly")
        return (len(unverified) == 0, unverified)
