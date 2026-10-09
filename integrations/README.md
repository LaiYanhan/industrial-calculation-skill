# 大模型工具接入与跨主机交付

本目录提供原生 Function Calling、MCP stdio 和可选 LangChain 接口。所有计算统一调用 `CalculationSkill.calculate()`，完整经过 S0～S8；接入层不包含场景公式，不修改计算引擎。这里的命令不会注册服务、修改客户端设置或创建后台服务。

## 交付到其他主机

开发主机在项目根目录执行：

```console
python -m integrations.package
```

输出 `exports/industrial-calculation-tools.zip`。源码包包含计算引擎、场景及费率配置、七表 Excel 模板、内置 IAPWS 物性库、接入代码、说明和测试；不包含 `.venv`、Git 数据、客户端配置、API 密钥或历史报表。**目标主机须重新创建虚拟环境并安装依赖**，不要复制开发主机的虚拟环境。

目标主机解压后进入项目目录，使用 Python 3.10 或以上版本。Windows PowerShell：

```powershell
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r integrations/requirements-mcp.txt
./.venv/Scripts/python.exe -m integrations.configure mcp-config
```

Linux / macOS：

```sh
python3 -m venv .venv
./.venv/bin/python -m pip install -r integrations/requirements-mcp.txt
./.venv/bin/python -m integrations.configure mcp-config
```

选择依赖：

| 用途 | 安装清单 |
| --- | --- |
| 只要函数定义和本地分发器，无模型 SDK | `integrations/requirements.txt` |
| MCP 客户端 | `integrations/requirements-mcp.txt`，使用官方 MCP Python SDK 2.x |
| OpenAI 兼容原生 SDK 示例 | `integrations/requirements-native.txt` |
| LangChain | `integrations/requirements-langchain.txt` |
| 全部接入与回归测试 | `integrations/requirements-test.txt` |

每份清单均包含核心计算依赖。内网离线安装需提前在匹配目标操作系统、CPU 架构及 Python 版本的环境准备 wheelhouse，再使用 `pip install --no-index --find-links <wheelhouse> -r <清单>`。源码包本身不含依赖 wheel。

## 三个工具及共同调用契约

| 工具 | 参数 / 行为 |
| --- | --- |
| `industrial_list_scenarios` | `{}`；返回实际已注册场景及描述 |
| `industrial_get_scenario_spec` | `scenario_id`；返回 manifest 元数据、参数单位、默认值、边界、输出，以及运行时 `required_params` 和 `alias_map` |
| `industrial_calculate` | 场景 ID、参数列表、反解目标、求解模式和 Excel 开关 |

建议调用顺序：列出场景 → 查询规范 → 收集参数 → 执行计算。当前内置场景为 `molten_salt_steam`（熔盐供汽与工程概算）和 `financial_profit_model`（利润及销量反解）。

标准计算参数如下。`inputs` 采用名称/数值列表，兼容严格 JSON Schema；不要传自由格式的参数字典。

```json
{
  "scenario_id": "molten_salt_steam",
  "inputs": [
    {"name": "steam_pressure_mpa", "value": 1.5},
    {"name": "steam_temperature_c", "value": 200},
    {"name": "steam_flow_th", "value": 100}
  ],
  "targets": null,
  "solution_mode": "AUTO",
  "generate_excel": false
}
```

数值必须有限且使用 `canonical_unit`（例如 MPa、℃、t/h、万元）；不接受 `"1.5 MPa"` 等字符串。支持运行时 `alias_map` 列出的中文别名；重复参数、同一参数的规范名与别名并存、额外选项或未知工具会报错。强制使用 STRICT 审计，不能通过工具参数关闭。

熔盐预算反解时，将流量输入替换成 `target_dynamic_investment_wanke=22650`，设置 `targets=["steam_flow_th"]`；模式可用 `AUTO` 或 `INVERSE`。不要同时提供固定流量和投资预算。财务利润反解使用 `unit_price_cny`、`target_net_profit_wanke` 及 `targets=["sales_volume"]`。其它工况的边界与默认值以查询的规范和场景审计为准。

结果直接保留引擎语义：

- `SUCCESS`：包含 `results`、`warnings`、`audit`、`fsm_trace`、`execution_id`、`artifacts`。
- `INTERRUPTED`：按 `missing_parameters` 向用户询问，不擅自补齐必填输入。此状态不是 MCP 执行错误。
- `FAILED`：保留引擎 `diagnostics` 或接入层 `error`；MCP 同时设置 `isError=true`。

`generate_excel` 默认关闭。设为 `true` 时，报表写入**执行主机**的项目 `exports/`，`artifacts.excel_path` 是该主机绝对路径。MCP 返回文本 JSON 和相同的 `structuredContent`，不会自动传输文件；需要由调用应用读取/交付该路径下的报表。

## 原生 Function Calling / 自建 Agent

在项目可导入的 Python 环境中（项目根目录或将根目录加入 `sys.path`）：

```python
from integrations.function_calling import get_openai_tools, dispatch_tool_call

tools = get_openai_tools(api="responses")
# 将 tools 交给模型。收到函数调用后，用模型返回的 name / arguments 分发：
result = dispatch_tool_call("industrial_calculate", {
    "scenario_id": "molten_salt_steam",
    "inputs": [
        {"name": "steam_pressure_mpa", "value": 1.5},
        {"name": "steam_temperature_c", "value": 200},
        {"name": "steam_flow_th", "value": 100},
    ],
    "targets": None,
    "solution_mode": "AUTO",
    "generate_excel": False,
})
print(result["status"])
```

`get_function_definitions()` 返回与供应商无关的函数定义。OpenAI Responses 与 Chat Completions 的工具定义分别使用 `get_openai_tools("responses")` 和 `get_openai_tools("chat_completions")`。两种定义均启用 `strict=true`；模型生成的参数必须包含全部字段，无反解目标时 `targets=null`。直接通过 Python/MCP/LangChain 调用时可省略 `targets`、`solution_mode` 和 `generate_excel`，由参数模型应用上述默认值。

Responses 的完整同步 Agent 循环已封装（调用模型会使用调用方账户的 API 配额）：

```python
import os
from openai import OpenAI
from integrations.function_calling import run_responses_agent

with OpenAI() as client:  # 由目标主机设置 OPENAI_API_KEY
    response = run_responses_agent(
        client=client,
        model=os.environ["OPENAI_MODEL"],  # 自行选择支持工具调用的模型
        prompt="计算1.5MPa、200℃、100t/h熔盐供汽项目的动态投资。",
        max_rounds=8,
    )
    print(response.output_text)
```

循环会保留推理项及全部 `response.output`，并用原 `call_id` 回传每个函数结果。自行编排时可使用 `execute_responses_tool_calls(response)`；先将 `response.output` 追加进历史，再追加函数结果。Chat Completions 使用 `execute_chat_tool_calls(message)`，先追加原始 assistant 消息，再追加返回的 `role="tool"` 消息。

非 Python Agent 可以导出定义，并通过 stdin/stdout 调度（在目标主机激活虚拟环境后）：

```console
python -m integrations.configure function-tools --api generic
python -m integrations.configure function-tools --api responses
python -m integrations.configure function-tools --api chat_completions
python -m integrations.configure invoke industrial_calculate
```

最后一条从 stdin 读取一个 JSON 对象，输入结束后输出结果；`FAILED` 的退出码为 1，`SUCCESS` / `INTERRUPTED` 为 0。不要仅凭退出码判断业务计算成功，要读取 `status`。

## 其它 MCP 客户端

在**目标主机虚拟环境**运行 `python -m integrations.configure mcp-config`，会输出通用 `mcpServers` JSON。将其中的条目合并到该主机客户端配置中；不同客户端的配置文件位置和外层结构请按客户端说明处理。生成内容使用目标主机 Python 和脚本的绝对路径，支持中文、空格路径及任意工作目录；搬迁项目后须重新生成。

客户端实际启动方式等价于：

```console
<目标虚拟环境的python> <目标项目绝对路径>/integrations/mcp_server.py
```

服务仅提供 stdio；由 MCP 客户端管理子进程生命周期。stdout 专用于 JSON-RPC，日志走 stderr，无端口或模型密钥要求。已验证官方 SDK 客户端及 `2025-06-18` 协议握手。这里的 stdio 服务适用于在使用主机部署源码；跨网络远程访问需要另行部署 HTTP 传输与认证。

## LangChain（可选）

```python
from integrations.langchain_tools import get_langchain_tools

tools = get_langchain_tools()
# 传给所用模型的 bind_tools(tools)，或所用 Agent 的 tools 参数。
result = tools[0].invoke({})
print(result)
```

三个工具均为带共享 Pydantic 参数模型的 `StructuredTool`。普通字段校验错误遵循 LangChain 自身异常机制；有效调用的业务结果保留上述三种状态。

## 验证

安装 `integrations/requirements-test.txt` 后，使用该虚拟环境执行：

```console
python -m unittest discover -s tests
python subagent_workspace/ci_runner.py molten_salt_steam
```

接入测试包含真实 MCP stdio 子进程、旧协议握手、原生 SDK 的离线 MockTransport、LangChain 调用、缺参和失败语义，以及解压到含中文/空格的新路径后的计算与 Excel 导出。测试不请求在线模型。只装核心依赖时，可选接入测试会跳过；验收接入功能须安装完整测试清单，确保无跳过。

协议实现依据：[OpenAI Function Calling](https://developers.openai.com/api/docs/guides/function-calling)、[MCP Python SDK 低层服务](https://py.sdk.modelcontextprotocol.io/advanced/low-level-server/)、[LangChain 工具](https://docs.langchain.com/oss/python/langchain/tools)。
