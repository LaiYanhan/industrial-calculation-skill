"""
S3: 基准查表与外部规则加载阶段 (Reference Lookup State).
检索外部物性库 (IAPWS-IF97/CoolProp)、基准税率表、行业常数。
"""

from typing import List, Tuple
from engine.fsm.context import ExecutionContext
from engine.fsm.state import BaseState, GuardResult, ActionResult


class ReferenceLookupState(BaseState):

    def __init__(self, scenario_spec=None):
        super().__init__("S3_REFERENCE_LOOKUP")
        self.scenario_spec = scenario_spec

    def verify_guard(self, context: ExecutionContext) -> GuardResult:
        if not context.has_passed_token("S2_TOPOLOGY_ROUTING"):
            return GuardResult(
                passed=False,
                reason="前序状态 S2_TOPOLOGY_ROUTING 未通过，禁止执行基准查表",
                missing_prerequisites=["Token:S2_TOPOLOGY_ROUTING"]
            )
        return GuardResult(passed=True)

    def execute_action(self, context: ExecutionContext) -> ActionResult:
        ref_data = {}
        if self.scenario_spec and hasattr(self.scenario_spec, "lookup_references"):
            ref_data = self.scenario_spec.lookup_references(context.canonical_params)

        context.reference_data = ref_data

        return ActionResult(
            status="PASSED",
            invariants_verified=["reference_lookup_executed"],
            diagnostics={"reference_keys": list(ref_data.keys())}
        )

    def verify_invariants(self, context: ExecutionContext) -> Tuple[bool, List[str]]:
        unverified = []
        if not isinstance(context.reference_data, dict):
            unverified.append("reference_data_is_dict")
        return (len(unverified) == 0, unverified)
