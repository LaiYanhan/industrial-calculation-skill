"""
声明式场景仓库包 (Scenarios Repository).
存放所有业务与工程计算场景包。所有场景必须继承 BaseScenarioSpec。
"""

from scenarios.base import BaseScenarioSpec
from scenarios.registry import ScenarioRegistry

__all__ = ["BaseScenarioSpec", "ScenarioRegistry"]
