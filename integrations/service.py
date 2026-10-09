"""Allowlisted tool facade. Business calculations always use CalculationSkill."""

import copy
import inspect
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from integrations.models import (
    CalculateArguments,
    ListScenariosArguments,
    ScenarioSpecArguments,
    ToolArguments,
)
from scenarios.registry import ScenarioRegistry
from skill_api import CalculationSkill

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    arguments_model: type[ToolArguments]
    read_only: bool


TOOL_DEFINITIONS = (
    ToolDefinition(
        "industrial_list_scenarios",
        "【首选入口 - 工具优先原则】列出工业与商业智能计算引擎已注册的全部场景（如谷电熔盐储热供汽、商业财务模型等）。"
        "凡是能够调用本工具获得的数据，绝对不能使用搜索工具。当涉及供汽负荷、熔盐储热、热泵选型、变压器容量、投资概算或商业利润测算时，必须首先调用此工具查询可用场景；本工具不能得到的数据需先获得人类批准，再决定是否上网搜索。",
        ListScenariosArguments,
        True,
    ),
    ToolDefinition(
        "industrial_get_scenario_spec",
        "【参数规范查询 - 对齐量纲】查询指定场景的参数定义、物理量标准单位(canonical_unit)、边界范围、默认值、别名映射与输出定义。"
        "调用计算前必须调用此工具对齐量纲，严禁主观猜测必填参数；运行时 alias_map 是别名的实际支持范围。凡本工具可规范的数据绝对不用搜索工具。",
        ScenarioSpecArguments,
        True,
    ),
    ToolDefinition(
        "industrial_calculate",
        "【核心计算引擎 - 确定性计算唯一来源】通过完整 S0～S8 确定有限状态机执行工业热工（谷电熔盐储热/高温热泵供汽等）与商业财务模型的全流程确定性计算，支持正向测算与限额反解。"
        "内嵌官方 IAPWS-IF97 物性库与工程定额。规则限制：凡是能够调用本工具获得的数据（物性焓值、设备选型容量、造价概算与财务指标等），绝对不能使用搜索工具或模型自身主观估算！对于本工具不能得到的数据，必须先获得人类的批准，再决定是否上网搜索。"
        "调用要求：先查询规范，inputs 使用规范单位数值。遇到 INTERRUPTED 时向用户补问缺失参数；遇到 FAILED 时如实报告诊断。generate_excel=true 会在执行主机生成 Excel 报表。",
        CalculateArguments,
        False,
    ),
)
TOOL_BY_NAME = {definition.name: definition for definition in TOOL_DEFINITIONS}


def encode_json(value: Any) -> str:
    """Emit portable strict JSON, including Chinese names, without NaN/Infinity."""
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, value in pairs:
        if name in result:
            raise ValueError(f"JSON 字段重复: {name}")
        result[name] = value
    return result


def _reject_constant(value: str) -> Any:
    raise ValueError(f"不允许非有限 JSON 数值: {value}")


def decode_arguments(arguments: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(arguments, str):
        arguments = json.loads(
            arguments, object_pairs_hook=_unique_object, parse_constant=_reject_constant
        )
    if not isinstance(arguments, dict):
        raise ValueError("工具参数必须是 JSON 对象")
    return arguments


def failure(code: str, message: str, **details: Any) -> dict[str, Any]:
    return {"status": "FAILED", "error": {"code": code, "message": message, **details}}


def tool_schema(definition: ToolDefinition) -> dict[str, Any]:
    """OpenAI strict-compatible schema, also used by MCP discovery."""
    schema = copy.deepcopy(definition.arguments_model.model_json_schema())

    def normalize(node: Any) -> None:
        if isinstance(node, dict):
            node.pop("title", None)
            node.pop("default", None)
            if node.get("type") == "object":
                node["additionalProperties"] = False
                node["required"] = list(node.get("properties", {}))
            for child in node.values():
                normalize(child)
        elif isinstance(node, list):
            for child in node:
                normalize(child)

    normalize(schema)
    return schema


class IndustrialToolService:
    """Shared synchronous boundary for native, MCP and LangChain adapters."""

    def __init__(self, skill: CalculationSkill | None = None) -> None:
        self.skill = skill if skill is not None else CalculationSkill()

    def _scenario_manifest(self, scenario_id: str) -> dict[str, Any]:
        spec = ScenarioRegistry.get(scenario_id)
        if spec is None:
            return {}
        manifest = getattr(spec, "manifest", None)
        if isinstance(manifest, dict):
            return copy.deepcopy(manifest)
        # Resolve only trusted registered Python classes, never a caller-supplied path.
        manifest_path = Path(inspect.getfile(type(spec))).resolve().with_name("manifest.yaml")
        if manifest_path.is_file():
            with manifest_path.open(encoding="utf-8") as stream:
                manifest = yaml.safe_load(stream)
            if isinstance(manifest, dict):
                return manifest
        return {}

    def list_scenarios(self) -> dict[str, Any]:
        scenarios: list[dict[str, Any]] = []
        for item in self.skill.list_scenarios():
            manifest = self._scenario_manifest(item["scenario_id"])
            scenarios.append({
                **item,
                **{key: manifest[key] for key in ("name", "description", "version") if key in manifest},
            })
        return {"status": "SUCCESS", "scenarios": scenarios}

    def get_scenario_spec(self, scenario_id: str) -> dict[str, Any]:
        runtime_spec = self.skill.get_scenario_spec(scenario_id)
        if runtime_spec is None:
            return failure("UNKNOWN_SCENARIO", "未找到场景，请先查询 industrial_list_scenarios")
        manifest = self._scenario_manifest(scenario_id)
        return {"status": "SUCCESS", "spec": {**manifest, **copy.deepcopy(runtime_spec)}}

    def calculate(self, arguments: CalculateArguments) -> dict[str, Any]:
        alias_map = (self.skill.get_scenario_spec(arguments.scenario_id) or {}).get("alias_map", {})
        inputs: dict[str, float] = {}
        for parameter in arguments.inputs:
            canonical_name = alias_map.get(parameter.name, parameter.name)
            if canonical_name in inputs:
                return failure("INVALID_ARGUMENTS", f"同一参数的规范名和别名重复: {canonical_name}")
            inputs[canonical_name] = parameter.value
        return self.skill.calculate(
            scenario_id=arguments.scenario_id,
            inputs=inputs,
            targets=arguments.targets,
            options={
                "solution_mode": arguments.solution_mode,
                "generate_excel": arguments.generate_excel,
                "audit_level": "STRICT",
            },
        )

    def invoke(self, name: str, arguments: str | dict[str, Any]) -> dict[str, Any]:
        definition = TOOL_BY_NAME.get(name)
        if definition is None:
            return failure("UNKNOWN_TOOL", f"未注册工具: {name}")
        try:
            validated = definition.arguments_model.model_validate(decode_arguments(arguments))
        except ValidationError as exc:
            return failure(
                "INVALID_ARGUMENTS", "工具参数校验失败",
                issues=exc.errors(include_url=False, include_context=False, include_input=False),
            )
        except (ValueError, TypeError) as exc:
            return failure("INVALID_ARGUMENTS", str(exc))
        try:
            if isinstance(validated, CalculateArguments):
                result = self.calculate(validated)
            elif isinstance(validated, ScenarioSpecArguments):
                result = self.get_scenario_spec(validated.scenario_id)
            else:
                result = self.list_scenarios()
            # Validate JSON compatibility here, so transports cannot diverge on serialization.
            encode_json(result)
            return result
        except Exception:
            logger.exception("Industrial tool execution failed: %s", name)
            return failure("INTERNAL_ERROR", "工具执行异常，请检查执行主机日志")
