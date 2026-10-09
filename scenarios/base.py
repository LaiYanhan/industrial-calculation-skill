"""
场景规范抽象基类 (Base Scenario Specification).
所有具体的计算场景 (如熔盐储热供汽、商业财务模型) 必须继承本类，提供对应的方程组与规则实现。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Tuple
from engine.fsm.context import ExecutionContext


class BaseScenarioSpec(ABC):
    """
    业务场景规范抽象接口.
    解耦通用状态机流水线与具体业务公式。
    """

    def __init__(self, scenario_id: str):
        self.scenario_id = scenario_id
        self.alias_map: Dict[str, str] = {}
        self.required_params: List[str] = []

    @abstractmethod
    def lookup_references(self, canonical_params: Dict[str, float]) -> Dict[str, Any]:
        """S3: 检索该场景所需的外部物性或基准数据"""
        pass

    @abstractmethod
    def solve_continuous(
        self,
        params: Dict[str, float],
        references: Dict[str, Any],
        mode: str = "FORWARD"
    ) -> Dict[str, float]:
        """S4: 执行连续核心方程求解 (支持正解与反解)"""
        pass

    @abstractmethod
    def regularize_discrete(
        self,
        continuous_results: Dict[str, float],
        params: Dict[str, float]
    ) -> Dict[str, Any]:
        """S5: 执行离散工程选型与阶梯规整"""
        pass

    @abstractmethod
    def cascade_metrics(
        self,
        continuous_results: Dict[str, float],
        discrete_results: Dict[str, Any],
        params: Dict[str, float]
    ) -> Dict[str, Any]:
        """S6: 执行指标联动与综合概算/报表汇总"""
        pass

    @abstractmethod
    def audit_sanity(self, context: ExecutionContext) -> Tuple[List[str], List[str]]:
        """S7: 业务不变量常理审计 (返回 violations, warnings)"""
        pass

    def export_excel(self, context: ExecutionContext) -> str:
        """S8: 导出专用 Excel 报表 (可选实现)"""
        return ""
