"""
S0: 槽位抽取阶段 (Slot Extraction State).
从自然语言、工程文本或键值字典中提取原始业务槽位。
"""

import re
from typing import Any, Dict, List, Tuple
from engine.fsm.context import ExecutionContext
from engine.fsm.state import BaseState, GuardResult, ActionResult


class SlotExtractionState(BaseState):

    def __init__(self):
        super().__init__("S0_SLOT_EXTRACTION")

    def verify_guard(self, context: ExecutionContext) -> GuardResult:
        if context.raw_input is None:
            return GuardResult(passed=False, reason="原始输入 raw_input 为空，无法进行槽位抽取")
        return GuardResult(passed=True)

    def execute_action(self, context: ExecutionContext) -> ActionResult:
        raw_inp = context.raw_input
        extracted_slots: Dict[str, Any] = {}

        if isinstance(raw_inp, dict):
            # 已经是结构化/半结构化字典输入
            extracted_slots.update(raw_inp)
        elif isinstance(raw_inp, str):
            # 自然语言/文本简单模式识别 (示例骨架: 提取形如 '参数名: 数值' 或 '参数名 123.4')
            pattern = re.compile(r"([^\d\s:：=]+)[:：=\s]+([0-9]+(?:\.[0-9]+)?)")
            matches = pattern.findall(raw_inp)
            for k, v in matches:
                extracted_slots[k.strip()] = float(v)

        context.raw_slots = extracted_slots

        if not extracted_slots:
            return ActionResult(
                status="FAILED",
                error_message="未能从原始输入中抽取任何有效业务槽位",
                diagnostics={"raw_input_snippet": str(raw_inp)[:200]}
            )

        return ActionResult(
            status="PASSED",
            invariants_verified=["raw_slots_non_empty"],
            diagnostics={"extracted_count": len(extracted_slots)}
        )

    def verify_invariants(self, context: ExecutionContext) -> Tuple[bool, List[str]]:
        unverified = []
        if not context.raw_slots:
            unverified.append("raw_slots_not_empty")
        return (len(unverified) == 0, unverified)
