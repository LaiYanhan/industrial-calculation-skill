"""
场景注册中心 (Scenario Registry).
负责动态管理、发现与注册系统内的所有声明式场景包。
支持根据 scenarios/ 目录自动扫描动态发现新场景 (无需修改核心代码)。
"""

import importlib
import inspect
import logging
from pathlib import Path
from typing import Dict, List, Optional
from scenarios.base import BaseScenarioSpec

logger = logging.getLogger(__name__)


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
    def discover_scenarios(cls) -> List[str]:
        """
        动态扫描 scenarios/ 目录下的所有子包.
        只要子目录下包含继承 BaseScenarioSpec 的 spec.py，即自动实例化并注册.
        AI 新增计算场景时只需在 scenarios/ 下按规范创建目录，无需修改任何核心代码.
        """
        discovered = []
        scenarios_root = Path(__file__).resolve().parent

        for child in scenarios_root.iterdir():
            if child.is_dir() and not child.name.startswith(("_", ".")):
                spec_file = child / "spec.py"
                if spec_file.exists():
                    try:
                        module_name = f"scenarios.{child.name}.spec"
                        mod = importlib.import_module(module_name)
                        # 支持热重载更新
                        importlib.reload(mod)
                        for attr_name in dir(mod):
                            attr = getattr(mod, attr_name)
                            if (
                                inspect.isclass(attr)
                                and issubclass(attr, BaseScenarioSpec)
                                and attr is not BaseScenarioSpec
                            ):
                                instance = attr()
                                cls.register(instance)
                                discovered.append(instance.scenario_id)
                                break
                    except Exception as exc:
                        logger.warning(f"扫描场景目录 {child.name} 失败: {exc}")

        return discovered

    @classmethod
    def load_defaults(cls) -> None:
        """加载与发现所有场景"""
        cls.discover_scenarios()

    @classmethod
    def reload(cls) -> List[str]:
        """清空并重新扫描加载所有场景"""
        cls._registry.clear()
        return cls.discover_scenarios()
