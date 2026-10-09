"""领域无关的 openpyxl 模板回填器。

默认禁止覆盖公式，保留样式、数组公式、链接、合并区域和工作表设置。
可显式授权某些公式替换，并为已在 Python 计算的公式提供缓存值。
openpyxl 不计算公式；缓存只代表本次输入，Excel 打开时仍可重算。
"""
import math
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Mapping
from xml.etree import ElementTree as ET
from zipfile import ZipFile

XML_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
CELL_RE = re.compile(r"^\$?([A-Za-z]{1,3})\$?([1-9][0-9]*)$")
MAX_ROW = 1048576  # ECMA-376 spreadsheet grid limits
MAX_COLUMN = 16384


class ExcelTemplateExporter:
    def __init__(self, template_path: str | Path) -> None:
        self.template_path = Path(template_path)

    @staticmethod
    def _cell(workbook: Any, reference: str) -> Any:
        from openpyxl.utils.cell import column_index_from_string
        if "!" in reference:
            sheet_name, coordinate = reference.rsplit("!", 1)
            if sheet_name.startswith("'") and sheet_name.endswith("'"):
                sheet_name = sheet_name[1:-1].replace("''", "'")
            if sheet_name not in workbook.sheetnames:
                raise ValueError(f"未知工作表: {sheet_name}")
            sheet = workbook[sheet_name]
        else:
            sheet, coordinate = workbook.active, reference
        match = CELL_RE.fullmatch(coordinate)
        if not match or int(match[2]) > MAX_ROW or column_index_from_string(match[1]) > MAX_COLUMN:
            raise ValueError(f"非法单元格地址: {reference}")
        coordinate = coordinate.replace("$", "").upper()
        for region in sheet.merged_cells.ranges:
            if coordinate in region and coordinate != region.start_cell.coordinate:
                raise ValueError(f"不能写入合并区域的非锚点: {reference}")
        return sheet[coordinate]

    @staticmethod
    def _write_caches(path: Path, caches: Mapping[str, Mapping[str, Any]],
                      sheet_names: list[str]) -> None:
        """仅更新 OOXML v 元素；保持 openpyxl 输出的 f（包括数组公式）不变。"""
        with ZipFile(path, "r") as source:
            entries = [(info, source.read(info.filename)) for info in source.infolist()]
        # openpyxl 按 worksheets 顺序写 sheetN.xml；编号不是模板原始 rId。
        sheet_paths = {f"xl/worksheets/sheet{index}.xml": caches.get(name, {})
                       for index, name in enumerate(sheet_names, 1)}
        with ZipFile(path, "w") as target:
            for info, data in entries:
                values = sheet_paths.get(info.filename)
                if values:
                    root = ET.fromstring(data)
                    for cell in root.iter(f"{{{XML_NS}}}c"):
                        address = cell.attrib.get("r")
                        if address not in values:
                            continue
                        value = values[address]
                        cached = cell.find(f"{{{XML_NS}}}v")
                        if cached is None:
                            cached = ET.SubElement(cell, f"{{{XML_NS}}}v")
                        if isinstance(value, bool):
                            cell.set("t", "b")
                            cached.text = "1" if value else "0"
                        elif isinstance(value, (float, int)):
                            if not math.isfinite(value):
                                raise ValueError(f"公式缓存不是有限数: {address}")
                            cell.attrib.pop("t", None)
                            cached.text = repr(value)
                        elif isinstance(value, str):
                            cell.set("t", "str")
                            cached.text = value
                        else:
                            raise ValueError(f"不支持的公式缓存: {address}")
                    data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
                target.writestr(info, data)

    def export(self, output_path: str | Path, cell_mapping: Mapping[str, Any],
               *, formula_values: Mapping[str, Any] | None = None,
               formula_overrides: set[str] | None = None) -> str:
        try:
            import openpyxl
            from openpyxl.workbook.properties import CalcProperties
        except ImportError as exc:
            raise RuntimeError("缺少 openpyxl，不能生成 Excel；请安装依赖") from exc
        destination = Path(output_path).resolve()
        template = self.template_path.resolve()
        if destination == template or (destination.exists() and os.path.samefile(destination, template)):
            raise ValueError("输出不能覆盖原始模板")
        if template.suffix.lower() not in (".xlsx", ".xlsm") or destination.suffix.lower() != template.suffix.lower():
            raise ValueError("模板和输出必须具有相同的 .xlsx/.xlsm 格式")
        overrides = formula_overrides or set()
        workbook = openpyxl.load_workbook(template, data_only=False,
                                         keep_vba=template.suffix.lower() == ".xlsm", keep_links=True)
        temporary: Path | None = None
        try:
            for reference, value in cell_mapping.items():
                cell = self._cell(workbook, reference)
                # 数组公式范围的任何单元格都受保护。
                for anchor, array_range in cell.parent.array_formulae.items():
                    from openpyxl.worksheet.cell_range import CellRange
                    if cell.coordinate in CellRange(array_range) and reference not in overrides:
                        raise ValueError(f"禁止覆盖数组公式区域: {reference}")
                    if cell.coordinate in CellRange(array_range) and array_range not in (anchor, f"{anchor}:{anchor}"):
                        raise ValueError(f"不支持局部覆盖多单元格数组公式: {reference}")
                if cell.data_type == "f" and reference not in overrides:
                    raise ValueError(f"禁止覆盖模板公式: {reference}")
                if isinstance(value, float) and not math.isfinite(value):
                    raise ValueError(f"单元格值必须有限: {reference}")
                cell.value = value
            caches: dict[str, dict[str, Any]] = {}
            for reference, value in (formula_values or {}).items():
                cell = self._cell(workbook, reference)
                if cell.data_type != "f":
                    raise ValueError(f"公式缓存指向非公式单元格: {reference}")
                caches.setdefault(cell.parent.title, {})[cell.coordinate] = value
            workbook.calculation = CalcProperties(calcMode="auto", fullCalcOnLoad=True, forceFullCalc=True)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=destination.parent, suffix=destination.suffix, delete=False) as handle:
                temporary = Path(handle.name)
            workbook.save(temporary)
            if caches:
                self._write_caches(temporary, caches, workbook.sheetnames)
            os.replace(temporary, destination)
            temporary = None
        finally:
            workbook.close()
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return str(destination)
