"""Generic MCP stdio entry point. Launch by absolute filename from any directory."""

import asyncio
import logging
from pathlib import Path
import sys
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp.server import Server, ServerRequestContext
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolRequestParams,
    CallToolResult,
    ListToolsResult,
    PaginatedRequestParams,
    TextContent,
    Tool,
    ToolAnnotations,
)

from integrations.function_calling import AGENT_INSTRUCTIONS
from integrations.service import IndustrialToolService, TOOL_DEFINITIONS, encode_json, tool_schema

SERVER_NAME = "industrial-calculation"
SERVER_VERSION = "1.0.0"


def create_server(service: IndustrialToolService | None = None) -> Server[Any]:
    facade = service if service is not None else IndustrialToolService()
    tools = [
        Tool(
            name=definition.name,
            description=definition.description,
            input_schema=tool_schema(definition),
            output_schema={
                "type": "object",
                "properties": {"status": {"enum": ["SUCCESS", "INTERRUPTED", "FAILED"]}},
                "required": ["status"],
                "additionalProperties": True,
            },
            annotations=ToolAnnotations(
                read_only_hint=definition.read_only,
                destructive_hint=False,
                idempotent_hint=definition.read_only,
                open_world_hint=False,
            ),
        )
        for definition in TOOL_DEFINITIONS
    ]

    async def list_tools(
        context: ServerRequestContext[Any], params: PaginatedRequestParams | None,
    ) -> ListToolsResult:
        return ListToolsResult(tools=tools)

    async def call_tool(
        context: ServerRequestContext[Any], params: CallToolRequestParams,
    ) -> CallToolResult:
        # Keep protocol handling responsive while the synchronous FSM runs.
        result = await asyncio.to_thread(facade.invoke, params.name, params.arguments or {})
        return CallToolResult(
            content=[TextContent(type="text", text=encode_json(result))],
            structured_content=result,
            is_error=result.get("status") == "FAILED",
        )

    return Server(
        SERVER_NAME,
        version=SERVER_VERSION,
        instructions=AGENT_INSTRUCTIONS,
        on_list_tools=list_tools,
        on_call_tool=call_tool,
    )


async def serve_stdio() -> None:
    server = create_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> None:
    # Stdout belongs exclusively to JSON-RPC; all diagnostics go to stderr.
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    asyncio.run(serve_stdio())


if __name__ == "__main__":
    main()
