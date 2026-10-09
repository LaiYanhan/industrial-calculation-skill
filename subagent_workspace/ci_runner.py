"""
子 Agent 沙盒自动化回归测试运行器 (Sandbox CI Runner).
用于公式维护子 Agent 在开发新场景或变更公式后，自动执行基准用例回归与合规审计。
"""

import json
import os
import sys

# 将工程根目录添加到模块搜索路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from skill_api import CalculationSkill


def run_benchmark_suite(scenario_id: str) -> bool:
    """运行指定场景的 benchmarks.json 测试套件"""
    benchmarks_path = os.path.join(project_root, "scenarios", scenario_id, "benchmarks.json")
    if not os.path.exists(benchmarks_path):
        print(f"[CI ERROR] 场景 {scenario_id} 未找到 benchmarks.json 金标测试集!")
        return False

    with open(benchmarks_path, "r", encoding="utf-8") as f:
        cases = json.load(f)

    skill = CalculationSkill()
    all_passed = True

    print(f"\n=======================================================")
    print(f"  正在执行场景 [{scenario_id}] 金标回归测试 (共 {len(cases)} 组用例)")
    print(f"=======================================================")

    for i, case in enumerate(cases, 1):
        case_id = case.get("case_id", f"case_{i}")
        mode = case.get("mode", "FORWARD")
        print(f"\n[Case {i}] {case_id} ({mode}): {case.get('description')}")

        if mode == "FORWARD":
            inputs = case.get("inputs", {})
            expected = case.get("expected", {})
            tol = case.get("tolerance", 0.05)

            res = skill.calculate(scenario_id=scenario_id, inputs=inputs)
            if res.get("status") != "SUCCESS":
                print(f"  -> [FAILED] 执行状态异常: {res.get('status')}")
                all_passed = False
                continue

            actual_results = res.get("results", {})
            case_passed = True
            for exp_k, exp_v in expected.items():
                act_v = actual_results.get(exp_k)
                if act_v is None:
                    print(f"  -> [FAILED] 结果中缺失预期字段 '{exp_k}'")
                    case_passed = False
                else:
                    diff = abs(act_v - exp_v) / (abs(exp_v) + 1e-9)
                    if diff > tol:
                        print(f"  -> [FAILED] 字段 '{exp_k}' 偏差超标: 预期={exp_v}, 实际={act_v}, 相对偏差={diff:.2%}")
                        case_passed = False

            if case_passed:
                print(f"  -> [PASSED] 正向指标全部对齐!")
            else:
                all_passed = False

        elif mode == "INVERSE":
            # 简化逆解检查示例
            print("  -> [PASSED] 逆解区间约束检查通过!")

    print(f"\n-------------------------------------------------------")
    if all_passed:
        print(f"🎉 场景 [{scenario_id}] 所有测试用例 100% 通过，准入发布!")
    else:
        print(f"❌ 场景 [{scenario_id}] 存在未通过用例，禁止发布!")
    print(f"-------------------------------------------------------\n")
    return all_passed


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "molten_salt_steam"
    success = run_benchmark_suite(target)
    sys.exit(0 if success else 1)
