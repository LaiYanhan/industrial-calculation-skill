"""Print host-local launch configuration or schemas; never edit client settings."""

import argparse
import json
from pathlib import Path
import sys
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def mcp_client_config() -> dict[str, Any]:
    """Run this on the destination host after creating its virtual environment."""
    return {
        "mcpServers": {
            "industrial-calculation": {
                # Do not resolve interpreter symlinks: POSIX venv symlinks must remain in the venv.
                "command": str(Path(sys.executable).absolute()),
                "args": [str(Path(__file__).resolve().with_name("mcp_server.py"))],
                "env": {"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"},
            }
        }
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("mcp-config", help="输出当前主机 MCP 配置，不注册或修改客户端")
    schemas = commands.add_parser("function-tools", help="输出原生工具 JSON 定义")
    schemas.add_argument("--api", choices=("responses", "chat_completions", "generic"), default="responses")
    invoke = commands.add_parser("invoke", help="从 stdin 读取一份 JSON 对象并执行工具")
    invoke.add_argument("name")
    args = parser.parse_args(argv)
    if args.command == "mcp-config":
        result = mcp_client_config()
    elif args.command == "function-tools":
        from integrations.function_calling import get_function_definitions, get_openai_tools
        result = get_function_definitions() if args.api == "generic" else get_openai_tools(args.api)
    else:
        from integrations.function_calling import dispatch_tool_call
        result = dispatch_tool_call(args.name, sys.stdin.read())
    print(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2))
    return 1 if isinstance(result, dict) and result.get("status") == "FAILED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
