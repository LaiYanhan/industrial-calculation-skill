"""
执行上下文状态总线 (Execution Context State Bus).
统一管理整个状态机生命周期内的数据交换、参数规范化、状态令牌传递与追踪。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
import time
import uuid


class ExecutionStatus(str, Enum):
    INITIALIZED = "INITIALIZED"
    RUNNING = "RUNNING"
    INTERRUPTED = "INTERRUPTED"  # 如缺参等待澄清
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class StateToken:
    """
    单状态执行完毕后颁发的状态令牌 (State Token).
    下一状态必须校验上一状态的令牌有效性，确保无法跳步。
    """
    state_id: str
    status: str = "PASSED"  # PASSED | FAILED | INTERRUPTED
    timestamp: float = field(default_factory=time.time)
    duration_ms: float = 0.0
    invariants_verified: List[str] = field(default_factory=list)
    diagnostics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionContext:
    """
    状态机执行上下文总线 (Execution Context).
    唯一合法的数据传递总线，禁止使用全局变量。
    """
    execution_id: str = field(default_factory=lambda: f"calc_{uuid.uuid4().hex[:12]}")
    scenario_id: str = ""
    status: ExecutionStatus = ExecutionStatus.INITIALIZED

    # 1. 原始输入层
    raw_input: Any = None
    raw_slots: Dict[str, Any] = field(default_factory=dict)
    unmatched_context: List[str] = field(default_factory=list)

    # 2. 规范参数层 (S1)
    canonical_params: Dict[str, float] = field(default_factory=dict)
    param_units: Dict[str, str] = field(default_factory=dict)
    missing_parameters: List[str] = field(default_factory=list)

    # 3. 依赖图与拓扑策略 (S2)
    solution_mode: str = "AUTO"  # FORWARD | INVERSE | SEARCH
    target_params: List[str] = field(default_factory=list)
    dof: int = 0  # 系统自由度 Degrees of Freedom

    # 4. 基准查表数据 (S3)
    reference_data: Dict[str, Any] = field(default_factory=dict)

    # 5. 连续求解结果 (S4)
    continuous_results: Dict[str, float] = field(default_factory=dict)

    # 6. 离散规整结果 (S5)
    discrete_results: Dict[str, Any] = field(default_factory=dict)

    # 7. 级联汇总与综合指标 (S6)
    cascade_results: Dict[str, Any] = field(default_factory=dict)

    # 8. 审计与校验记录 (S7)
    audit_passed: bool = False
    audit_violations: List[str] = field(default_factory=list)
    audit_warnings: List[str] = field(default_factory=list)

    # 9. 交付产物 (S8)
    artifacts: Dict[str, Any] = field(default_factory=dict)
    final_output: Dict[str, Any] = field(default_factory=dict)

    # 运行时状态令牌栈与审计链路
    tokens: List[StateToken] = field(default_factory=list)
    options: Dict[str, Any] = field(default_factory=dict)

    def add_token(self, token: StateToken) -> None:
        self.tokens.append(token)

    def has_passed_token(self, state_id: str) -> bool:
        """检查指定状态是否已成功通过"""
        for tok in self.tokens:
            if tok.state_id == state_id and tok.status == "PASSED":
                return True
        return False

    def get_latest_token(self) -> Optional[StateToken]:
        return self.tokens[-1] if self.tokens else None

    def get_trace(self) -> List[Dict[str, Any]]:
        """获取结构化执行追踪链路 (fsm_trace)"""
        return [
            {
                "state": t.state_id,
                "status": t.status,
                "duration_ms": round(t.duration_ms, 2),
                "invariants": t.invariants_verified,
                "diagnostics": t.diagnostics,
            }
            for t in self.tokens
        ]
