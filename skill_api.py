"""
工业智能计算 Skill 主调度入口类 (Skill API Entrypoint).
供上层大 Skill 调度器、对话 Agent 或人类命令行直接调用的核心服务封装。
"""

from typing import Any, Dict, List, Optional
import os
import sys

# 确保当前路径在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.fsm.context import ExecutionContext, ExecutionStatus
from engine.fsm.controller import FSMController
from scenarios.registry import ScenarioRegistry


class CalculationSkill:
    """
    智能计算 Skill 外部标准门面接口.
    统一封装场景发现、参数规格查询、状态机流水线触发与变更工作流。
    """

    def __init__(self):
        # 初始化并加载所有默认场景
        ScenarioRegistry.load_defaults()

    def list_scenarios(self) -> List[Dict[str, Any]]:
        """查询当前系统已加载生效的所有计算场景"""
        return ScenarioRegistry.list_all()

    def get_scenario_spec(self, scenario_id: str) -> Optional[Dict[str, Any]]:
        """获取指定场景的参数定义、别名表与必填项"""
        spec = ScenarioRegistry.get(scenario_id)
        if not spec:
            return None
        return {
            "scenario_id": spec.scenario_id,
            "alias_map": spec.alias_map,
            "required_params": spec.required_params,
        }

    def calculate(
        self,
        scenario_id: str,
        inputs: Any,
        targets: Optional[List[str]] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        触发通用有限状态机流水线 (S0 ~ S8) 执行计算.

        :param scenario_id: 场景唯一标识 (如 'molten_salt_steam')
        :param inputs: 原始输入材料 (文本、字典等)
        :param targets: 期望获取的目标输出字段 (可选)
        :param options: 执行配置 (solution_mode, audit_level, generate_excel 等)
        :return: 包含计算结果、执行追踪 (fsm_trace) 与交付物的结构化字典
        """
        spec = ScenarioRegistry.get(scenario_id)
        if not spec:
            return {
                "status": "FAILED",
                "error": f"未找到场景 ID '{scenario_id}', 请先调用 list_scenarios() 查询可用场景",
            }

        opts = options or {}

        # 1. 实例化执行上下文状态总线
        context = ExecutionContext(
            scenario_id=scenario_id,
            raw_input=inputs,
            target_params=targets or [],
            options=opts
        )

        # 2. 调度执行状态机管线
        controller = FSMController(scenario_spec=spec)
        context = controller.execute(context)

        # 3. 组织返回体
        if context.status == ExecutionStatus.COMPLETED:
            return {
                "status": "SUCCESS",
                "execution_id": context.execution_id,
                "scenario_id": scenario_id,
                "solution_mode": context.solution_mode,
                "fsm_trace": context.get_trace(),
                "results": context.final_output.get("results", {}),
                "artifacts": context.artifacts,
                "audit": context.final_output.get("audit", {}),
            }
        elif context.status == ExecutionStatus.INTERRUPTED:
            return {
                "status": "INTERRUPTED",
                "execution_id": context.execution_id,
                "scenario_id": scenario_id,
                "reason": "缺少核心推导自变量，已暂停等待补充澄清",
                "missing_parameters": context.missing_parameters,
                "fsm_trace": context.get_trace(),
            }
        else:
            latest_token = context.get_latest_token()
            return {
                "status": "FAILED",
                "execution_id": context.execution_id,
                "scenario_id": scenario_id,
                "fsm_trace": context.get_trace(),
                "diagnostics": latest_token.diagnostics if latest_token else {},
            }


if __name__ == "__main__":
    # 快速自检演示
    skill = CalculationSkill()
    print("Available Scenarios:", skill.list_scenarios())
    sample_res = skill.calculate(
        scenario_id="molten_salt_steam",
        inputs={"蒸汽压力": 1.5, "蒸汽温度": 200, "蒸汽流量": 100}
    )
    print("\nCalculation Status:", sample_res["status"])
    print("SGS Power (MW):", sample_res.get("results", {}).get("sgs_power_mw"))
    print("Nominal Heater (MW):", sample_res.get("results", {}).get("heater_power_nominal_mw"))
    print("Dynamic Investment (万元):", sample_res.get("results", {}).get("dynamic_investment_wanke"))
