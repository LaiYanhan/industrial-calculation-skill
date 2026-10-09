"""
场景金标用例回归测试套件 (Scenario Benchmark Regression Tests).
自动读取各场景下的 benchmarks.json 并执行正向与逆向约束核验。
"""

import json
import os
import unittest
from skill_api import CalculationSkill

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestScenarioRegression(unittest.TestCase):

    def setUp(self):
        self.skill = CalculationSkill()

    def _run_benchmarks_for(self, scenario_id: str):
        bench_file = os.path.join(PROJECT_ROOT, "scenarios", scenario_id, "benchmarks.json")
        self.assertTrue(os.path.exists(bench_file), f"缺少 {scenario_id}/benchmarks.json")

        with open(bench_file, "r", encoding="utf-8") as f:
            cases = json.load(f)

        for case in cases:
            mode = case.get("mode", "FORWARD")
            if mode == "FORWARD":
                inputs = case.get("inputs", {})
                expected = case.get("expected", {})
                tol = case.get("tolerance", 0.05)

                res = self.skill.calculate(scenario_id=scenario_id, inputs=inputs)
                self.assertEqual(res.get("status"), "SUCCESS")

                act_res = res.get("results", {})
                for k, exp_val in expected.items():
                    self.assertIn(k, act_res, f"场景 {scenario_id} 输出缺少字段 {k}")
                    act_val = act_res[k]
                    diff = abs(act_val - exp_val) / (abs(exp_val) + 1e-9)
                    self.assertLessEqual(
                        diff,
                        tol,
                        f"字段 {k} 偏差超标: 预期 {exp_val}, 实际 {act_val}, 偏差 {diff:.2%}"
                    )

    def test_molten_salt_steam_benchmarks(self):
        """回归测试: 谷电熔盐储热工程场景"""
        self._run_benchmarks_for("molten_salt_steam")

    def test_financial_profit_model_benchmarks(self):
        """回归测试: 商业财务利润测算模型"""
        self._run_benchmarks_for("financial_profit_model")


if __name__ == "__main__":
    unittest.main()
