"""
通用有限状态机流水线测试 (FSM Pipeline Tests).
验证状态机不可跳步性、前置守卫拦截、参数缺失中断与成功流转。
"""

import unittest
from engine.fsm.context import ExecutionContext, ExecutionStatus
from engine.fsm.controller import FSMController
from engine.fsm.states.s4_solve import ContinuousSolveState
from scenarios.molten_salt_steam.spec import MoltenSaltSteamSpec


class TestFSMPipeline(unittest.TestCase):

    def setUp(self):
        self.spec = MoltenSaltSteamSpec()
        self.controller = FSMController(scenario_spec=self.spec)

    def test_full_pipeline_success(self):
        """测试正常参数输入下，S0~S8全流程通畅执行"""
        ctx = ExecutionContext(
            scenario_id="molten_salt_steam",
            raw_input={"蒸汽压力": 1.5, "蒸汽温度": 200, "蒸汽流量": 100}
        )
        ctx = self.controller.execute(ctx)

        self.assertEqual(ctx.status, ExecutionStatus.COMPLETED)
        self.assertTrue(ctx.has_passed_token("S0_SLOT_EXTRACTION"))
        self.assertTrue(ctx.has_passed_token("S1_CANONICAL_ALIGNMENT"))
        self.assertTrue(ctx.has_passed_token("S4_CONTINUOUS_SOLVE"))
        self.assertTrue(ctx.has_passed_token("S8_REPORT_DELIVERY"))

        # 检查核心计算结果
        results = ctx.final_output.get("results", {})
        self.assertAlmostEqual(results.get("heater_power_nominal_mw", 0.0), 80.0, places=0)
        self.assertAlmostEqual(results.get("transformer_capacity_mva", 0.0), 90.0, places=0)

    def test_missing_parameter_interruption(self):
        """测试缺少核心自变量时，状态机在 S1 阶段安全中断并输出追问列表"""
        # 故意缺少 '蒸汽流量'
        ctx = ExecutionContext(
            scenario_id="molten_salt_steam",
            raw_input={"蒸汽压力": 1.5, "蒸汽温度": 200}
        )
        ctx = self.controller.execute(ctx)

        self.assertEqual(ctx.status, ExecutionStatus.INTERRUPTED)
        self.assertIn("steam_flow_th", ctx.missing_parameters)
        # S4 绝不应该被执行
        self.assertFalse(ctx.has_passed_token("S4_CONTINUOUS_SOLVE"))

    def test_guard_prevents_skipping(self):
        """测试直接调用中游状态 (如S4) 时，因缺乏上游令牌被守卫直接拦截"""
        ctx = ExecutionContext(scenario_id="molten_salt_steam")
        s4_state = ContinuousSolveState(scenario_spec=self.spec)

        token = s4_state.run(ctx)
        self.assertEqual(token.status, "FAILED")
        self.assertIn("guard_failure", token.diagnostics)


if __name__ == "__main__":
    unittest.main()
