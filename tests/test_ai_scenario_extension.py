"""
AI 动态新增计算场景与公式扩展能力测试 (AI Scenario Extension Tests).
验证 AI Agent 能够通过 API 或脚手架动态创建新场景包、沙盒回归测试、热重载生效并执行计算。
"""

import shutil
import unittest
from pathlib import Path

from skill_api import CalculationSkill

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEMO_SCENARIO_ID = "test_demo_carbon_calc"
DEMO_DIR = PROJECT_ROOT / "scenarios" / DEMO_SCENARIO_ID


class TestAIScenarioExtension(unittest.TestCase):

    def tearDown(self):
        # 清理测试生成的场景目录
        if DEMO_DIR.exists():
            shutil.rmtree(DEMO_DIR, ignore_errors=True)
        # 重新扫描注册表
        CalculationSkill().reload_scenarios()

    def test_ai_can_dynamically_create_test_and_calculate_new_scenario(self):
        """测试 AI 完整创建新公式场景、沙盒CI回归并投入实际计算的生命周期"""
        skill = CalculationSkill()

        # 1. 准备新场景的声明式参数、方程与金标测试用例
        parameters = {
            "power_generation_mwh": {
                "type": "float",
                "canonical_unit": "MWh",
                "description": "发电量",
                "bounds": [0.0, 1000000.0],
                "required": True,
                "aliases": ["发电量", "上网电量"]
            },
            "emission_factor_t_per_mwh": {
                "type": "float",
                "canonical_unit": "t/MWh",
                "description": "碳排放因子",
                "bounds": [0.0, 5.0],
                "default": 0.581,
                "aliases": ["排放因子", "电网碳因子"]
            }
        }

        # 纯代数连续方程
        equations_code = '''"""碳排放计算纯函数"""
def calc_carbon_emission_t(power_generation_mwh: float, emission_factor_t_per_mwh: float = 0.581) -> float:
    """碳排放量 (吨): 发电量 * 排放因子"""
    return round(power_generation_mwh * emission_factor_t_per_mwh, 3)
'''

        # 金标测试用例 (供沙盒CI自检)
        benchmarks = [
            {
                "case_id": "carbon_forward_case_1",
                "description": "基准正向用例: 1000 MWh, 因子 0.581",
                "mode": "FORWARD",
                "inputs": {
                    "power_generation_mwh": 1000.0,
                    "emission_factor_t_per_mwh": 0.581
                },
                "expected": {
                    "carbon_emission_t": 581.0
                },
                "tolerance": 0.001
            }
        ]

        # 2. AI 调用统一接口创建新场景包
        create_res = skill.create_scenario(
            scenario_id=DEMO_SCENARIO_ID,
            name="火电与绿电碳减排测算模型",
            description="根据发电量与电网碳排放因子测算总碳排放量与核减指标",
            parameters=parameters,
            equations_code=equations_code,
            benchmarks=benchmarks,
            auto_test_and_register=True
        )

        # 断言创建成功并沙盒全绿通过
        self.assertEqual(create_res["status"], "SUCCESS", create_res)
        self.assertTrue(DEMO_DIR.exists())
        self.assertTrue((DEMO_DIR / "manifest.yaml").exists())
        self.assertTrue((DEMO_DIR / "equations.py").exists())
        self.assertTrue((DEMO_DIR / "spec.py").exists())

        # 3. 验证新场景已在注册中心生效
        all_scenarios = skill.list_scenarios()
        registered_ids = [s["scenario_id"] for s in all_scenarios]
        self.assertIn(DEMO_SCENARIO_ID, registered_ids)

        # 4. 验证新场景能够立即被状态机调用执行真实计算
        calc_res = skill.calculate(
            scenario_id=DEMO_SCENARIO_ID,
            inputs={"上网电量": 2000.0, "排放因子": 0.6}
        )
        self.assertEqual(calc_res["status"], "SUCCESS")
        self.assertAlmostEqual(
            calc_res["results"]["carbon_emission_t"],
            1200.0,
            places=2
        )


if __name__ == "__main__":
    unittest.main()
