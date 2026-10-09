"""
双向反解能力与数值求根测试 (Solver Inversion Tests).
验证区间感知二分法对阶梯选型与造价概算函数反推自变量的有效性。
"""

import unittest
from engine.solver.numeric_inverter import NumericInverter
from skill_api import CalculationSkill


class TestSolverInversion(unittest.TestCase):

    def setUp(self):
        self.skill = CalculationSkill()

    def test_numeric_inverter_simple_monotonic(self):
        """测试纯单调函数的二分反解"""
        # y = 2 * x + 10
        fn = lambda x: 2.0 * x + 10.0
        target = 50.0  # 预期 x = 20.0

        x_found, iters = NumericInverter.bisect(
            forward_eval_fn=fn,
            target_y=target,
            x_min=0.0,
            x_max=100.0,
            tol=1e-3
        )
        self.assertIsNotNone(x_found)
        self.assertAlmostEqual(x_found, 20.0, places=2)

    def test_pipeline_inverse_steam_flow_from_investment(self):
        """
        测试全流程预算反解:
        已知总动态投资 22650 万元，反推所需最大供汽能力是否收敛至 100 t/h 附近
        """
        res = self.skill.calculate(
            scenario_id="molten_salt_steam",
            inputs={
                "steam_pressure_mpa": 1.5,
                "steam_temperature_c": 200.0,
                "target_dynamic_investment_wanke": 22650.0
            },
            targets=["steam_flow_th"],
            options={"solution_mode": "INVERSE"}
        )
        self.assertEqual(res["status"], "SUCCESS")
        flow_found = res["results"]["steam_flow_th"]
        self.assertIsNotNone(flow_found)
        self.assertTrue(90.0 <= flow_found <= 110.0)

if __name__ == "__main__":
    unittest.main()
