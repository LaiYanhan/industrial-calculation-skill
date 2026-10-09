# 智能计算 Skill 外部接口契约 (API Reference)

本文档面向**外部大 Skill 调度器**及调用方，定义本 Skill 的标准化 Python / JSON 调用接口。

---

## 1. 核心接口清单

### 1.1 场景发现接口: `list_scenarios()`

**描述**：查询当前引擎中已加载生效的所有计算场景概览。

**调用示例**：
```python
from skill_api import CalculationSkill

skill = CalculationSkill()
scenarios = skill.list_scenarios()
```

**返回格式**：
```json
[
  {
    "scenario_id": "molten_salt_steam",
    "version": "1.0.0",
    "name": "谷电熔盐储热供蒸汽计算场景",
    "description": "根据蒸汽参数、谷电时长计算加热功率、储热量及工程总造价"
  },
  {
    "scenario_id": "financial_profit_model",
    "version": "1.0.0",
    "name": "企业财务商业利润测算场景",
    "description": "根据产品销量、成本结构与税率计算毛利、EBITDA及税后净利润"
  }
]
```

---

### 1.2 场景规格查询接口: `get_scenario_spec(scenario_id)`

**描述**：获取指定场景的参数字典、别名映射、取值边界与默认值（上层大 Skill 可据此组织自然语言 Prompt 或校验输入槽位）。

**调用示例**：
```python
spec = skill.get_scenario_spec("molten_salt_steam")
```

---

### 1.3 核心计算执行接口: `calculate(...)`

**描述**：触发通用状态机流水线 (S0~S8) 执行计算。

**函数签名**：
```python
def calculate(
    scenario_id: str,
    inputs: Dict[str, Any],
    targets: Optional[List[str]] = None,
    options: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    ...
```

**请求参数说明**：
- `scenario_id` (str, 必需): 目标场景 ID；
- `inputs` (dict, 必需): 输入槽位字典（支持标准键名或常见中文别名，如 `{"蒸汽流量": 100, "蒸汽压力": 1.5}`）；
- `targets` (list, 可选): 指定需要获取的核心目标参数列表。若为空，默认返回该场景全部输出指标；
- `options` (dict, 可选):
  - `solution_mode`: `"AUTO"` (自动识别) | `"FORWARD"` (强制正解) | `"INVERSE"` (强制反解)；
  - `generate_excel`: `bool`，是否在 `exports/` 目录落盘生成真实 `.xlsx` 文件（默认 `True`）；
  - `audit_level`: `"STRICT"` (违背常理报错中断) | `"PERMISSIVE"` (警告但不中断)。

**返回数据结构**：
```json
{
  "status": "SUCCESS",
  "execution_id": "calc_20261009_001",
  "scenario_id": "molten_salt_steam",
  "fsm_trace": [
    {"state": "S0_SLOT_EXTRACTION", "status": "PASSED"},
    {"state": "S1_CANONICAL_ALIGNMENT", "status": "PASSED"},
    {"state": "S2_TOPOLOGY_ROUTING", "mode": "FORWARD", "status": "PASSED"},
    {"state": "S3_REFERENCE_LOOKUP", "status": "PASSED"},
    {"state": "S4_CONTINUOUS_SOLVE", "status": "PASSED"},
    {"state": "S5_DISCRETE_REGULARIZE", "status": "PASSED"},
    {"state": "S6_METRIC_CASCADE", "status": "PASSED"},
    {"state": "S7_SANITY_AUDIT", "status": "PASSED"},
    {"state": "S8_REPORT_DELIVERY", "status": "PASSED"}
  ],
  "results": {
    "sgs_thermal_power_mw": 75.33,
    "heat_produced_mwh": 608.75,
    "heater_power_nominal_mw": 80.0,
    "transformer_capacity_mva": 90.0,
    "total_investment_wanke": 22650.0
  },
  "artifacts": {
    "excel_path": "exports/molten_salt_steam_result_20261009_001.xlsx",
    "markdown_summary": "### 测算报告摘要\n..."
  }
}
```

---

## 2. 异常错误码规范 (Error Codes)

| 错误码 | 触发状态 | 含义 | 建议应对动作 |
| :--- | :--- | :--- | :--- |
| `ERR_SLOT_EMPTY` | S0 | 无法从输入材料中抽取任何有效参数 | 提示用户提供具体的工艺参数或工程说明 |
| `ERR_PARAM_MISSING` | S1 | 关键独立自变量缺失 | 提取 `missing_parameters` 字段，向用户发起定向提问 |
| `ERR_DOF_CONFLICT` | S2 | 系统自由度不为 0 (过约束或欠约束) | 提示用户输入参数存在矛盾或缺少约束方程 |
| `ERR_PROPERTY_OUT_OF_BOUNDS` | S3 | 查表工况超出物性或标准范围 | 检查输入的压力、温度是否超温超压 |
| `ERR_SOLVER_DIVERGE` | S4 | 代数方程求解发散或无解 | 检查数值合理性，调整初值猜想 |
| `ERR_CAPACITY_OVERFLOW` | S5 | 离散设备选型超出型谱库最大规格 | 提示并自动推荐多台设备并联方案 |
| `ERR_SANITY_VIOLATION` | S7 | 触发领域常理审计致命违规（如温差交叉） | 阻断计算并告知工艺设计不合理原因 |
