"""
场景构建与脚手架工具 (Scenario Builder & Scaffolding Tool).
专为 AI Agent (如子 Agent、公式扩展 Agent) 提供的标准化场景创建与自迭代脚手架.
支持根据参数、方程、规则与基准用例自动生成完全合规的声明式场景包，
并在沙盒中自动执行 CI 回归测试，全绿通过后自动热加载上线.
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from scenarios.registry import ScenarioRegistry
from subagent_workspace.ci_runner import run_benchmark_suite

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCENARIOS_DIR = PROJECT_ROOT / "scenarios"


class ScenarioBuilder:
    """AI 场景构建与自动迭代器"""

    @staticmethod
    def validate_scenario_metadata(
        scenario_id: str,
        parameters: Dict[str, Any],
        benchmarks: List[Dict[str, Any]],
    ) -> Tuple[bool, List[str]]:
        """依据 docs/AGENT_BEHAVIOR_GUIDELINES.md 校验场景定义合规性"""
        errors = []

        # 1. 场景 ID 规范校验 (英文小写蛇形)
        if not re.match(r"^[a-z][a-z0-9_]*[a-z0-9]$", scenario_id):
            errors.append(f"场景 ID '{scenario_id}' 不符合英文小写蛇形命名规范 (snake_case)")

        # 2. 参数规范与单位声明校验 (严禁无单位数字)
        if not parameters:
            errors.append("场景必须声明至少一个参数")
        for param_name, param_def in parameters.items():
            if not isinstance(param_def, dict):
                errors.append(f"参数 '{param_name}' 的定义必须为字典")
                continue
            if "canonical_unit" not in param_def or not param_def["canonical_unit"]:
                errors.append(f"参数 '{param_name}' 缺少必需的物理/商业单位声明 (canonical_unit)")

        # 3. 金标用例硬门禁校验 (至少包含 1 组常规正解用例)
        if not benchmarks:
            errors.append("场景必须提供至少一组金标基准测试用例 (benchmarks)")
        else:
            has_forward = any(c.get("mode") == "FORWARD" for c in benchmarks)
            if not has_forward:
                errors.append("金标用例中必须包含至少一组常规正解测试用例 (FORWARD)")

        return len(errors) == 0, errors

    @classmethod
    def generate_default_spec_code(
        cls,
        scenario_id: str,
        class_name: str,
        required_params: List[str],
        outputs_keys: List[str]
    ) -> str:
        """为简单代数场景生成默认自省式 spec.py 代码骨架"""
        return f'''"""
{scenario_id} 场景规范实现类.
自动由 ScenarioBuilder 脚手架生成，基于 equations.py 纯函数执行代数平衡求解.
"""

from typing import Any, Dict, List, Tuple
from scenarios.base import BaseScenarioSpec
from engine.fsm.context import ExecutionContext
import scenarios.{scenario_id}.equations as eq


class {class_name}(BaseScenarioSpec):

    def __init__(self):
        super().__init__("{scenario_id}")
        self.required_params = {repr(required_params)}
        self.alias_map = {{}}
        # 自动加载 manifest 中的别名
        import yaml
        from pathlib import Path
        manifest_path = Path(__file__).resolve().parent / "manifest.yaml"
        if manifest_path.exists():
            data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
            for k, v in data.get("parameters", {{}}).items():
                for alias in v.get("aliases", []):
                    self.alias_map[alias] = k

    def lookup_references(self, canonical_params: Dict[str, float]) -> Dict[str, Any]:
        return {{}}

    def solve_continuous(
        self,
        params: Dict[str, float],
        references: Dict[str, Any],
        mode: str = "FORWARD"
    ) -> Dict[str, float]:
        # 默认调用 equations 中的主求值函数或逐个执行方程
        results = {{}}
        if hasattr(eq, "calculate_all"):
            results = eq.calculate_all(params)
        else:
            for fn_name in dir(eq):
                if fn_name.startswith("calc_") and callable(getattr(eq, fn_name)):
                    fn = getattr(eq, fn_name)
                    import inspect
                    sig = inspect.signature(fn)
                    kwargs = {{k: params[k] for k in sig.parameters if k in params}}
                    if len(kwargs) == len(sig.parameters):
                        out_key = fn_name.removeprefix("calc_")
                        results[out_key] = fn(**kwargs)
        return results

    def regularize_discrete(
        self,
        continuous_results: Dict[str, float],
        params: Dict[str, float]
    ) -> Dict[str, Any]:
        return {{}}

    def cascade_metrics(
        self,
        continuous_results: Dict[str, float],
        discrete_results: Dict[str, Any],
        params: Dict[str, float]
    ) -> Dict[str, Any]:
        return {{}}

    def audit_sanity(self, context: ExecutionContext) -> Tuple[List[str], List[str]]:
        violations = []
        warnings = []
        return violations, warnings
'''

    @classmethod
    def create_scenario_package(
        cls,
        scenario_id: str,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        equations_code: str,
        benchmarks: List[Dict[str, Any]],
        sizing_rules: Optional[Dict[str, Any]] = None,
        costing_rules: Optional[Dict[str, Any]] = None,
        custom_spec_code: Optional[str] = None,
        auto_test_and_register: bool = True
    ) -> Dict[str, Any]:
        """
        完整创建场景包目录，包含 manifest.yaml, equations.py, sizing_rules.json,
        costing_rules.yaml, benchmarks.json, spec.py, README.md，并执行沙盒回归测试。
        """
        # 1. 规范校验
        valid, errors = cls.validate_scenario_metadata(scenario_id, parameters, benchmarks)
        if not valid:
            return {
                "status": "VALIDATION_FAILED",
                "errors": errors,
                "scenario_id": scenario_id
            }

        target_dir = SCENARIOS_DIR / scenario_id
        target_dir.mkdir(parents=True, exist_ok=True)

        try:
            # 2. 写入 manifest.yaml
            manifest_data = {
                "scenario_id": scenario_id,
                "version": "1.0.0",
                "name": name,
                "description": description,
                "parameters": parameters,
            }
            (target_dir / "manifest.yaml").write_text(
                yaml.dump(manifest_data, allow_unicode=True, sort_keys=False),
                encoding="utf-8"
            )

            # 3. 写入 equations.py
            (target_dir / "equations.py").write_text(equations_code, encoding="utf-8")

            # 4. 写入 sizing_rules.json
            sizing_data = sizing_rules or {}
            (target_dir / "sizing_rules.json").write_text(
                json.dumps(sizing_data, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )

            # 5. 写入 costing_rules.yaml
            costing_data = costing_rules or {}
            (target_dir / "costing_rules.yaml").write_text(
                yaml.dump(costing_data, allow_unicode=True, sort_keys=False),
                encoding="utf-8"
            )

            # 6. 写入 benchmarks.json
            (target_dir / "benchmarks.json").write_text(
                json.dumps(benchmarks, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )

            # 7. 写入 spec.py
            class_name = "".join(word.capitalize() for word in scenario_id.split("_")) + "Spec"
            required_params = [
                k for k, v in parameters.items() if v.get("required", False)
            ]
            spec_code = custom_spec_code or cls.generate_default_spec_code(
                scenario_id=scenario_id,
                class_name=class_name,
                required_params=required_params,
                outputs_keys=[]
            )
            (target_dir / "spec.py").write_text(spec_code, encoding="utf-8")

            # 8. 写入 README.md
            readme_text = f"# 场景说明: {name}\n\n{description}\n\n## 场景标识\n`{scenario_id}`\n"
            (target_dir / "README.md").write_text(readme_text, encoding="utf-8")

            # 9. 自动测试与沙盒准入校验
            if auto_test_and_register:
                test_passed = run_benchmark_suite(scenario_id)
                if not test_passed:
                    return {
                        "status": "BENCHMARK_TEST_FAILED",
                        "scenario_id": scenario_id,
                        "message": "场景已生成，但未通过沙盒金标回归测试，未予激活上线，请检查 equations.py 与 benchmarks.json 对齐情况",
                    }

                # 重新扫描注册
                ScenarioRegistry.reload()
                return {
                    "status": "SUCCESS",
                    "scenario_id": scenario_id,
                    "message": f"场景 [{scenario_id}] 已成功创建并通过全部沙盒回归测试，已热重载生效！",
                    "scenario_dir": str(target_dir)
                }

            return {
                "status": "CREATED_UNTESTED",
                "scenario_id": scenario_id,
                "scenario_dir": str(target_dir)
            }

        except Exception as exc:
            logger.exception(f"创建场景包失败: {exc}")
            return {
                "status": "ERROR",
                "scenario_id": scenario_id,
                "error": str(exc)
            }
