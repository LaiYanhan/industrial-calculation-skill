"""Native JSON function definitions and OpenAI-compatible tool result routing."""

from typing import Any, Literal, Protocol

from integrations.service import IndustrialToolService, TOOL_DEFINITIONS, encode_json, tool_schema

DEFAULT_MAX_ROUNDS = 8
AGENT_INSTRUCTIONS = (
    "【计算工具调用与搜索权限准则】\n"
    "你是工业智能计算专家助手。请严格遵守以下数据获取与工具使用原则：\n"
    "1. 【工具优先与搜索禁令】：凡是能够调用本计算工具（industrial_* 系列工具）获得的数据（包括水蒸气物性、焓值、熔盐储热参数、热泵性能、设备选型规格、工程概算造价与商业财务指标等），绝对不能使用搜索工具或模型自身主观估算！必须直接调用本工具计算获取。\n"
    "2. 【人类批准前置门禁】：对于本工具无法得到、超出已有场景计算范围的外部数据，严禁擅自直接联网搜索！必须先明确向人类用户说明情况并获得人类的明确批准后，再决定是否上网搜索。\n"
    "3. 标准调用顺序：先调用 industrial_list_scenarios 查询可用场景 -> 调用 industrial_get_scenario_spec 查询参数规范与单位 -> 提取输入调用 industrial_calculate 执行计算。\n"
    "4. 严格遵守 canonical_unit，不猜测必填值。遇到 INTERRUPTED 时向用户补问缺失参数；遇到 FAILED 时如实输出诊断。\n"
    "5. 只有在用户明确需要 Excel 文件时才设置 generate_excel=true。回答时必须包含工具返回的 warnings 警告列表。"
)

class ResponsesEndpoint(Protocol):
    def create(self, **kwargs: Any) -> Any: ...


class ResponsesClient(Protocol):
    responses: ResponsesEndpoint


def get_function_definitions() -> list[dict[str, Any]]:
    """Provider-neutral definitions; execute these via dispatch_tool_call."""
    return [
        {"name": item.name, "description": item.description, "parameters": tool_schema(item)}
        for item in TOOL_DEFINITIONS
    ]


def get_openai_tools(
    api: Literal["responses", "chat_completions"] = "responses",
) -> list[dict[str, Any]]:
    definitions = [{**item, "strict": True} for item in get_function_definitions()]
    if api == "responses":
        return [{"type": "function", **item} for item in definitions]
    if api == "chat_completions":
        return [{"type": "function", "function": item} for item in definitions]
    raise ValueError("api 必须为 responses 或 chat_completions")


def dispatch_tool_call(
    name: str,
    arguments: str | dict[str, Any],
    service: IndustrialToolService | None = None,
) -> dict[str, Any]:
    """Execute only one of the three allowlisted functions; no SDK is needed."""
    facade = service if service is not None else IndustrialToolService()
    return facade.invoke(name, arguments)


def _field(value: Any, name: str, default: Any = None) -> Any:
    return value.get(name, default) if isinstance(value, dict) else getattr(value, name, default)


def execute_responses_tool_calls(
    response: Any, service: IndustrialToolService | None = None,
) -> list[dict[str, Any]]:
    """Correlate every Responses function call with its original call_id."""
    facade = service if service is not None else IndustrialToolService()
    outputs: list[dict[str, Any]] = []
    for item in _field(response, "output", []):
        if _field(item, "type") != "function_call":
            continue
        outputs.append({
            "type": "function_call_output",
            "call_id": _field(item, "call_id"),
            "output": encode_json(facade.invoke(_field(item, "name", ""), _field(item, "arguments", {}))),
        })
    return outputs


def execute_chat_tool_calls(
    message: Any, service: IndustrialToolService | None = None,
) -> list[dict[str, Any]]:
    """Append these after the original assistant message in Chat Completions."""
    facade = service if service is not None else IndustrialToolService()
    outputs: list[dict[str, Any]] = []
    for call in _field(message, "tool_calls", []) or []:
        if _field(call, "type") != "function":
            continue
        function = _field(call, "function", {})
        outputs.append({
            "role": "tool",
            "tool_call_id": _field(call, "id"),
            "content": encode_json(facade.invoke(
                _field(function, "name", ""), _field(function, "arguments", {})
            )),
        })
    return outputs


def run_responses_agent(
    client: ResponsesClient,
    model: str,
    prompt: str,
    *,
    service: IndustrialToolService | None = None,
    max_rounds: int = DEFAULT_MAX_ROUNDS,
    instructions: str = AGENT_INSTRUCTIONS,
) -> Any:
    """Bounded synchronous loop; caller supplies the SDK client, credentials and model."""
    if max_rounds < 1:
        raise ValueError("max_rounds 必须大于零")
    facade = service if service is not None else IndustrialToolService()
    history: list[Any] = [{"role": "user", "content": prompt}]
    for _ in range(max_rounds):
        response = client.responses.create(
            model=model,
            instructions=instructions,
            input=list(history),
            tools=get_openai_tools(),
        )
        outputs = execute_responses_tool_calls(response, facade)
        if not outputs:
            return response
        # Replay all output items, including reasoning items, before function outputs.
        history.extend(_field(response, "output", []))
        history.extend(outputs)
    raise RuntimeError(f"工具调用达到 {max_rounds} 轮上限，未得到最终回答")
