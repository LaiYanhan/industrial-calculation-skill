"""
通用有限状态机核心模块 (Universal Finite State Machine).
负责计算管线的不可逾越单步流转、前置守卫检验、状态令牌传递与异常阻断。
"""

from engine.fsm.context import ExecutionContext, StateToken, ExecutionStatus
from engine.fsm.state import BaseState, GuardResult, ActionResult
from engine.fsm.controller import FSMController

__all__ = [
    "ExecutionContext",
    "StateToken",
    "ExecutionStatus",
    "BaseState",
    "GuardResult",
    "ActionResult",
    "FSMController",
]
