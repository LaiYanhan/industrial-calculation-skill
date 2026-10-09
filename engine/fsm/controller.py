"""
状态机调度控制器 (FSM Controller).
负责管理状态注册表，按拓扑顺序调度 S0 ~ S8，拦截非法越级与跳步，管理管线中断与自愈回退。
"""

from typing import List, Optional, Type
import logging

from engine.fsm.context import ExecutionContext, ExecutionStatus
from engine.fsm.state import BaseState

logger = logging.getLogger("FSMController")


class FSMController:
    """
    通用有限状态机调度中枢.
    保证流水线单向不可逆、单步守卫通过、状态令牌链式衔接。
    """

    def __init__(self, scenario_spec=None):
        self.scenario_spec = scenario_spec
        self.pipeline: List[BaseState] = []
        self._build_default_pipeline()

    def _build_default_pipeline(self) -> None:
        """加载标准 S0 ~ S8 阶段"""
        from engine.fsm.states.s0_extraction import SlotExtractionState
        from engine.fsm.states.s1_alignment import CanonicalAlignmentState
        from engine.fsm.states.s2_topology import TopologyRoutingState
        from engine.fsm.states.s3_reference import ReferenceLookupState
        from engine.fsm.states.s4_solve import ContinuousSolveState
        from engine.fsm.states.s5_regularize import DiscreteRegularizeState
        from engine.fsm.states.s6_cascade import MetricCascadeState
        from engine.fsm.states.s7_audit import SanityAuditState
        from engine.fsm.states.s8_delivery import ReportDeliveryState

        self.pipeline = [
            SlotExtractionState(),
            CanonicalAlignmentState(scenario_spec=self.scenario_spec),
            TopologyRoutingState(scenario_spec=self.scenario_spec),
            ReferenceLookupState(scenario_spec=self.scenario_spec),
            ContinuousSolveState(scenario_spec=self.scenario_spec),
            DiscreteRegularizeState(scenario_spec=self.scenario_spec),
            MetricCascadeState(scenario_spec=self.scenario_spec),
            SanityAuditState(scenario_spec=self.scenario_spec),
            ReportDeliveryState(scenario_spec=self.scenario_spec),
        ]

    def execute(self, context: ExecutionContext) -> ExecutionContext:
        """
        按顺序执行管线流水线.
        一旦遇到 FAILED 或 INTERRUPTED，立即安全终止并保留当前上下文现场。
        """
        context.status = ExecutionStatus.RUNNING

        for state in self.pipeline:
            # 严格防跳步校验：本状态必须满足自身守卫
            token = state.run(context)

            if token.status == "INTERRUPTED":
                context.status = ExecutionStatus.INTERRUPTED
                logger.info(f"FSM halted at {state.state_id}: {token.diagnostics}")
                break
            elif token.status == "FAILED":
                context.status = ExecutionStatus.FAILED
                logger.error(f"FSM failed at {state.state_id}: {token.diagnostics}")
                break

        if context.status == ExecutionStatus.RUNNING:
            context.status = ExecutionStatus.COMPLETED

        return context
