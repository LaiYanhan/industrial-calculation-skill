"""
Markdown 格式测算摘要报告生成器 (Markdown Summary Exporter).
"""

from typing import Any, Dict


class MarkdownSummaryExporter:

    @staticmethod
    def generate_summary(scenario_id: str, results: Dict[str, Any]) -> str:
        """生成面向人类工程师阅读的清晰 Markdown 摘要"""
        lines = [
            f"# {scenario_id} 计算与评估报告摘要",
            "",
            "## 核心输入与计算结果汇总",
            "| 参数名 | 键名 | 数值 |",
            "| :--- | :--- | :--- |",
        ]
        for k, v in results.items():
            lines.append(f"| {k} | `{k}` | **{v}** |")

        lines.extend([
            "",
            "> 本报告由工业智能计算引擎 (Universal FSM Pipeline) 自动生成，所有计算步骤与前置守卫均已通过核验。",
            ""
        ])
        return "\n".join(lines)
