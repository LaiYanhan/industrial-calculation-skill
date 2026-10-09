"""
S8: 结构化交付与多模态导出阶段 (Report Delivery State).
组装标准 JSON 响应体，调用 Excel/Markdown 导出器产出交付物。
"""

from typing import List, Tuple
from engine.fsm.context import ExecutionContext
from engine.fsm.state import BaseState, GuardResult, ActionResult


class ReportDeliveryState(BaseState):

    def __init__(self, scenario_spec=None):
        super().__init__("S8_REPORT_DELIVERY")
        self.scenario_spec = scenario_spec

    def verify_guard(self, context: ExecutionContext) -> GuardResult:
        if not context.has_passed_token("S7_SANITY_AUDIT"):
            return GuardResult(
                passed=False,
                reason="前序状态 S7_SANITY_AUDIT 未通过，禁止执行最终报表交付",
                missing_prerequisites=["Token:S7_SANITY_AUDIT"]
            )
        return GuardResult(passed=True)

    def execute_action(self, context: ExecutionContext) -> ActionResult:
        # 汇总全部结果
        combined_results = {}
        combined_results.update(context.canonical_params)
        combined_results.update(context.reference_data)
        combined_results.update(context.continuous_results)
        combined_results.update(context.discrete_results)
        combined_results.update(context.cascade_results)

        context.final_output = {
            "execution_id": context.execution_id,
            "scenario_id": context.scenario_id,
            "solution_mode": context.solution_mode,
            "results": combined_results,
            "audit": {
                "passed": context.audit_passed,
                "warnings": context.audit_warnings,
                "violations": context.audit_violations,
            },
            "fsm_trace": context.get_trace()
        }

        # 如果 options 中要求导出 Excel / Markdown
        if context.options.get("generate_excel", False) and self.scenario_spec:
            if hasattr(self.scenario_spec, "export_excel"):
                excel_path = self.scenario_spec.export_excel(context)
                context.artifacts["excel_path"] = excel_path

        return ActionResult(
            status="PASSED",
            invariants_verified=["final_output_packaged", "delivery_completed"],
            diagnostics={"artifacts": list(context.artifacts.keys())}
        )

    def verify_invariants(self, context: ExecutionContext) -> Tuple[bool, List[str]]:
        unverified = []
        if not context.final_output:
            unverified.append("final_output_not_empty")
        return (len(unverified) == 0, unverified)
