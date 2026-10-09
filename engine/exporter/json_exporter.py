"""
标准结构化 JSON 交付导出器 (JSON Delivery Exporter).
"""

import json
from typing import Any, Dict


class JSONDeliveryExporter:

    @staticmethod
    def serialize(payload: Dict[str, Any], indent: int = 2) -> str:
        """安全序列化上下文结果字典为 JSON 文本"""
        return json.dumps(payload, ensure_ascii=False, indent=indent, default=str)
