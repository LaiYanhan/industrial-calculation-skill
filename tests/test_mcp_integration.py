"""Real stdio interoperability and extracted-package portability checks."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any
import unittest
from zipfile import ZipFile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
HAS_MCP = importlib.util.find_spec("mcp") is not None
TEST_TIMEOUT_S = 45


def arguments(**parameters: float) -> dict[str, Any]:
    return {"scenario_id": "molten_salt_steam",
            "inputs": [{"name": name, "value": value} for name, value in parameters.items()],
            "targets": None, "solution_mode": "AUTO", "generate_excel": False}


@unittest.skipUnless(HAS_MCP, "安装 integrations/requirements-mcp.txt 后运行 MCP 测试")
class TestMCPStdio(unittest.IsolatedAsyncioTestCase):
    async def test_real_stdio_discovery_calculation_and_recoverable_failures(self) -> None:
        from mcp import Client, StdioServerParameters
        with tempfile.TemporaryDirectory(prefix="industrial_mcp_") as workdir:
            process = StdioServerParameters(
                command=sys.executable, args=[str(PROJECT_ROOT / "integrations" / "mcp_server.py")],
                cwd=workdir, env={"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"},
            )
            async with Client(process, read_timeout_seconds=TEST_TIMEOUT_S) as client:
                listed = await client.list_tools()
                self.assertEqual(len(listed.tools), 3)
                self.assertFalse(listed.tools[2].annotations.read_only_hint)
                spec = await client.call_tool("industrial_get_scenario_spec", {"scenario_id": "molten_salt_steam"})
                self.assertEqual(spec.structured_content["spec"]["parameters"]
                                 ["steam_pressure_mpa"]["canonical_unit"], "MPa")
                result = await client.call_tool("industrial_calculate", arguments(
                    steam_pressure_mpa=1.5, steam_temperature_c=200, steam_flow_th=100))
                self.assertFalse(result.is_error)
                self.assertEqual(result.structured_content["status"], "SUCCESS")
                self.assertEqual(result.structured_content["results"]["dynamic_investment_wanke"], 22650)
                self.assertEqual(len(result.structured_content["fsm_trace"]), 9)
                self.assertEqual(json.loads(result.content[0].text), result.structured_content)
                inverse = arguments(steam_pressure_mpa=1.5, steam_temperature_c=200,
                                    target_dynamic_investment_wanke=22650)
                inverse["targets"] = ["steam_flow_th"]
                result = await client.call_tool("industrial_calculate", inverse)
                self.assertEqual(result.structured_content["solution_mode"], "INVERSE")
                result = await client.call_tool("industrial_calculate", arguments(steam_pressure_mpa=1.5))
                self.assertEqual(result.structured_content["status"], "INTERRUPTED")
                self.assertFalse(result.is_error)
                result = await client.call_tool("industrial_calculate", {"scenario_id": "molten_salt_steam"})
                self.assertEqual(result.structured_content["error"]["code"], "INVALID_ARGUMENTS")
                self.assertTrue(result.is_error)
                result = await client.call_tool("unknown", {})
                self.assertEqual(result.structured_content["error"]["code"], "UNKNOWN_TOOL")
                # An invalid call must not crash the subprocess or poison later requests.
                self.assertEqual((await client.call_tool("industrial_list_scenarios", {}))
                                 .structured_content["status"], "SUCCESS")

    async def test_legacy_mcp_handshake_and_jsonrpc_stdout(self) -> None:
        process = await asyncio.create_subprocess_exec(
            sys.executable, str(PROJECT_ROOT / "integrations" / "mcp_server.py"),
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"},
        )

        async def send(message: dict[str, Any]) -> None:
            assert process.stdin is not None
            process.stdin.write((json.dumps(message) + "\n").encode("utf-8"))
            await process.stdin.drain()

        async def receive() -> dict[str, Any]:
            assert process.stdout is not None
            line = await asyncio.wait_for(process.stdout.readline(), TEST_TIMEOUT_S)
            self.assertTrue(line, "MCP server exited before replying")
            return json.loads(line)

        try:
            await send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                "protocolVersion": "2025-06-18", "capabilities": {},
                "clientInfo": {"name": "legacy-test-client", "version": "1.0"}}})
            initialized = await receive()
            self.assertEqual(initialized["result"]["protocolVersion"], "2025-06-18")
            await send({"jsonrpc": "2.0", "method": "notifications/initialized"})
            await send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
            listed = await receive()
            self.assertEqual(len(listed["result"]["tools"]), 3)
            await send({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
                "name": "industrial_list_scenarios", "arguments": {}}})
            result = await receive()
            self.assertEqual(json.loads(result["result"]["content"][0]["text"])["status"], "SUCCESS")
        finally:
            assert process.stdin is not None
            process.stdin.close()
            try:
                await asyncio.wait_for(process.communicate(), TEST_TIMEOUT_S)
            except asyncio.TimeoutError:
                process.kill()
                await process.communicate()


class TestPortablePackage(unittest.TestCase):
    def test_package_contains_sources_templates_and_no_runtime_or_machine_config(self) -> None:
        from integrations.package import build_package
        with tempfile.TemporaryDirectory(prefix="industrial_zip_") as workdir:
            output = build_package(Path(workdir) / "delivery.zip")
            with ZipFile(output) as archive:
                names = archive.namelist()
            self.assertIn("skill_api.py", names)
            self.assertIn("integrations/mcp_server.py", names)
            self.assertIn("scenarios/molten_salt_steam/templates/输入输出.xlsx", names)
            self.assertIn("engine/properties/vendor/iapws/iapws97.py", names)
            self.assertIn("engine/properties/vendor/iapws/VERSION", names)
            self.assertIn("subagent_workspace/ci_runner.py", names)
            for name in names:
                self.assertFalse(Path(name).is_absolute())
                self.assertNotIn("..", Path(name).parts)
                self.assertFalse(any(part in {".venv", ".git", "exports", "__pycache__", ".codex"}
                                     for part in Path(name).parts))
                self.assertFalse(name.endswith((".pyc", ".zip", ".env")))

    def test_native_cli_and_configuration_from_relocated_directory(self) -> None:
        from integrations.package import build_package
        with tempfile.TemporaryDirectory(prefix="industrial_relocate_") as workdir:
            temporary = Path(workdir)
            relocated = temporary / "搬迁后的工程 with spaces"
            with ZipFile(build_package(temporary / "delivery.zip")) as archive:
                archive.extractall(relocated)
            env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
            config_result = subprocess.run(
                [sys.executable, str(relocated / "integrations" / "configure.py"), "mcp-config"],
                cwd=temporary, capture_output=True, encoding="utf-8", env=env, timeout=TEST_TIMEOUT_S,
            )
            self.assertEqual(config_result.returncode, 0, config_result.stderr)
            config = json.loads(config_result.stdout)["mcpServers"]["industrial-calculation"]
            self.assertEqual(Path(config["args"][0]).parent.parent, relocated)
            self.assertEqual(config["command"], str(Path(sys.executable).absolute()))
            invocation = subprocess.run(
                [sys.executable, str(relocated / "integrations" / "configure.py"), "invoke", "industrial_calculate"],
                input=json.dumps(arguments(steam_pressure_mpa=1.5, steam_temperature_c=200, steam_flow_th=100)),
                cwd=temporary, capture_output=True, encoding="utf-8", env=env, timeout=TEST_TIMEOUT_S,
            )
            self.assertEqual(invocation.returncode, 0, invocation.stderr)
            result = json.loads(invocation.stdout)
            self.assertEqual(result["status"], "SUCCESS")
            self.assertEqual(result["results"]["dynamic_investment_wanke"], 22650)

    @unittest.skipUnless(HAS_MCP, "需要 MCP 可选依赖")
    def test_relocated_mcp_excel_uses_packaged_template_and_new_exports(self) -> None:
        from mcp import Client, StdioServerParameters
        from integrations.package import build_package

        async def verify(root: Path, cwd: Path) -> None:
            process = StdioServerParameters(command=sys.executable,
                args=[str(root / "integrations" / "mcp_server.py")], cwd=cwd,
                env={"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"})
            async with Client(process, read_timeout_seconds=TEST_TIMEOUT_S) as client:
                params = arguments(steam_pressure_mpa=1.5, steam_temperature_c=200, steam_flow_th=100)
                params["generate_excel"] = True
                result = await client.call_tool("industrial_calculate", params)
                self.assertFalse(result.is_error)
                self.assertEqual(result.structured_content["status"], "SUCCESS")
                path = Path(result.structured_content["artifacts"]["excel_path"])
                self.assertEqual(path.parent, root / "exports")
                self.assertTrue(path.is_file())

        with tempfile.TemporaryDirectory(prefix="industrial_moved_mcp_") as workdir:
            temporary = Path(workdir)
            relocated = temporary / "可移植工程 with spaces"
            with ZipFile(build_package(temporary / "delivery.zip")) as archive:
                archive.extractall(relocated)
            asyncio.run(verify(relocated, temporary))


if __name__ == "__main__":
    unittest.main()
