"""
场景注册中心 (Scenario Registry).
负责动态管理、发现与注册系统内的所有声明式场景包。
"""

from typing import Dict, List, Optional
from scenarios.base import BaseScenarioSpec


class ScenarioRegistry:
    """场景单例注册表"""

    _registry: Dict[str, BaseScenarioSpec] = {}

    @classmethod
    def register(cls, spec: BaseScenarioSpec) -> None:
        cls._registry[spec.scenario_id] = spec

    @classmethod
    def get(cls, scenario_id: str) -> Optional[BaseScenarioSpec]:
        return cls._registry.get(scenario_id)

    @classmethod
    def list_all(cls) -> List[Dict[str, str]]:
        return [
            {
                "scenario_id": sid,
                "class": spec.__class__.__name__,
            }
            for sid, spec in cls._registry.items()
        ]

    @classmethod
    def load_defaults(cls) -> None:
        """注册内置默认场景"""
        try:
            from scenarios.molten_salt_steam.spec import MoltenSaltSteamSpec
            cls.register(MoltenSaltSteamSpec())
        except ImportError:
            pass

        try:
            from scenarios.financial_profit_model.spec import FinancialProfitModelSpec
            cls.register(FinancialProfitModelSpec())
        except ImportError:
            pass
