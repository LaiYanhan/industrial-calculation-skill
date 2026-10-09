"""
Excel 报表模板回填导出器 (Excel Template Exporter).
基于原始 .xlsx 模板，安全填报输入参数与关键计算结果，保持原有公式、格式与图表。
"""

import os
from typing import Any, Dict


class ExcelTemplateExporter:
    """Excel 模板填报导出器"""

    def __init__(self, template_path: str = "输入输出.xlsx"):
        self.template_path = template_path

    def export(
        self,
        output_path: str,
        cell_mapping: Dict[str, Any]
    ) -> str:
        """
        基于模板回填单元格并生成目标文件.
        cell_mapping 格式: {"SheetName!Cell": value, ...}
        若 openpyxl 不可用，则安全创建占位标记文件或执行纯文本转储。
        """
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        try:
            import openpyxl
            wb = openpyxl.load_workbook(self.template_path)
            for ref, val in cell_mapping.items():
                if "!" in ref:
                    sheet_name, cell_coord = ref.split("!", 1)
                    if sheet_name in wb.sheetnames:
                        wb[sheet_name][cell_coord] = val
                else:
                    wb.active[ref] = val
            wb.save(output_path)
            return output_path
        except ImportError:
            # 运行环境无 openpyxl 时降级生成说明
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(f"Excel Export Placeholder: template={self.template_path}\n")
                for k, v in cell_mapping.items():
                    f.write(f"{k} = {v}\n")
            return output_path
