"""
抽象状态基类与契约定义 (Base State Contract).
所有具体的计算状态 (S0 ~ S8) 必须继承 BaseState，实现严格的前置守卫与后置不变量验证。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List
import time

from engine.fsm.context import ExecutionContext, StateToken


@dataclass
class GuardResult:
    """前置守卫检验结果"""
    passed: bool
    reason: str = ""
    missing_prerequisites: List[str] = field(default_factory=list)


@dataclass
class ActionResult:
    """状态动作执行结果"""
    status: str = "PASSED"  # PASSED | FAILED | INTERRUPTED
    invariants_verified: List[str] = field(default_factory=list)
    diagnostics: Dict[str, Any] = field(default_factory=dict)
    error_message: str = ""


class BaseState(ABC):
    """
    通用状态抽象基类 (Abstract State).
    规定子类必须实现:
    1. verify_guard: 前置守卫检查 (确保前序状态已完成，输入齐备)
    2. execute_action: 状态核心动作
    3. verify_invariants: 后置不变量校验 (确保本阶段计算结果自洽无非法值)
    """

    def __init__(self, state_id: str):
        self.state_id = state_id

    def run(self, context: ExecutionContext) -> StateToken:
        """模板方法: 封装守卫检查 -> 核心动作 -> 不变量校验 -> 颁发令牌流程"""
        start_time = time.time()

        # 1. 检验前置守卫
        guard = self.verify_guard(context)
        if not guard.passed:
            duration_ms = (time.time() - start_time) * 1000
            token = StateToken(
                state_id=self.state_id,
                status="FAILED",
                duration_ms=duration_ms,
                diagnostics={"guard_failure": guard.reason, "missing": guard.missing_prerequisites}
            )
            context.add_token(token)
            return token

        # 2. 执行核心动作
        try:
            action_res = self.execute_action(context)
        except (ValueError, ArithmeticError, KeyError, RuntimeError, OSError, ImportError) as exc:
            # 无效输入、物性越界或交付失败均应留下失败令牌，禁止越过本状态。
            action_res = ActionResult(
                status="FAILED", error_message=str(exc),
                diagnostics={"error_type": type(exc).__name__, "error": str(exc)})
        if action_res.status != "PASSED":
            duration_ms = (time.time() - start_time) * 1000
            token = StateToken(
                state_id=self.state_id,
                status=action_res.status,
                duration_ms=duration_ms,
                diagnostics=action_res.diagnostics
            )
            context.add_token(token)
            return token

        # 3. 校验后置不变量
        invariants_ok, unverified = self.verify_invariants(context)
        duration_ms = (time.time() - start_time) * 1000

        if not invariants_ok:
            token = StateToken(
                state_id=self.state_id,
                status="FAILED",
                duration_ms=duration_ms,
                diagnostics={"invariant_failure": f"Failed invariants: {unverified}"}
            )
            context.add_token(token)
            return token

        # 4. 成功颁发令牌
        token = StateToken(
            state_id=self.state_id,
            status="PASSED",
            duration_ms=duration_ms,
            invariants_verified=action_res.invariants_verified,
            diagnostics=action_res.diagnostics
        )
        context.add_token(token)
        return token

    @abstractmethod
    def verify_guard(self, context: ExecutionContext) -> GuardResult:
        """检查本状态的前置条件与必要上游状态令牌"""
        pass

    @abstractmethod
    def execute_action(self, context: ExecutionContext) -> ActionResult:
        """执行本状态的核心业务逻辑"""
        pass

    @abstractmethod
    def verify_invariants(self, context: ExecutionContext) -> tuple[bool, List[str]]:
        """检验本状态计算产出的后置不变量 (返回 是否通过, 未通过项列表)"""
        pass
