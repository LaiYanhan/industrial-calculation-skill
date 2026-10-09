# 声明式场景包配置规范与扩展标准 (Scenario Schema Specification)

本文档面向系统开发者以及**公式维护子 Agent (Formula Dev Sub-Agent)**，定义新增或修改计算场景时必须遵守的文件组织与语法契约。

---

## 1. 场景目录结构

每个独立计算场景必须存放在 `scenarios/<scenario_id>/` 目录下。场景 ID 必须使用英文小写蛇形命名 (`snake_case`)：

```
scenarios/<scenario_id>/
├── manifest.yaml           # [必需] 场景元数据、参数字典、别名与单位
├── equations.py            # [必需] 连续代数与物理守恒方程定义
├── sizing_rules.json       # [可选] 离散选型步长与标准型谱表
├── costing_rules.yaml      # [可选] 概算费率表、分档计价规则
├── benchmarks.json         # [必需] 金标测试集 (至少1组正解+1组反解)
└── README.md               # [必需] 场景业务背景与计算说明
```

---

## 2. 核心文件规范细节

### 2.1 `manifest.yaml` 规格

定义场景的整体描述、所有输入输出参数的元数据、物理量单位及别名映射：

```yaml
scenario_id: "molten_salt_steam"
version: "1.0.0"
name: "谷电熔盐储热供蒸汽计算场景"
description: "根据蒸汽参数、谷电时长计算电加热器/热泵功率、储热量及工程总造价"

parameters:
  steam_pressure_mpa:
    type: "float"
    canonical_unit: "MPa"
    aliases: ["蒸汽压力", "主汽压", "压力", "供汽压力"]
    description: "供汽端蒸汽压力"
    bounds: [0.1, 25.0]
    default: 1.5
    required: true

  steam_temperature_c:
    type: "float"
    canonical_unit: "degC"
    aliases: ["蒸汽温度", "供汽温度", "主汽温"]
    description: "供汽过热/饱和蒸汽温度"
    bounds: [100.0, 600.0]
    default: 200.0
    required: true

  steam_flow_th:
    type: "float"
    canonical_unit: "t/h"
    aliases: ["蒸汽流量", "产汽量", "供汽能力"]
    description: "小时供汽流量"
    bounds: [0.1, 5000.0]
    required: true

  total_investment_wanke:
    type: "float"
    canonical_unit: "万元"
    aliases: ["总投资", "动态投资", "工程造价"]
    description: "工程项目最终动态总投资"
    bounds: [0.0, 1000000.0]
    is_target_candidate: true
```

---

### 2.2 `equations.py` 规格

定义纯函数式的连续物理或财务代数方程。**严禁包含有副作用的全局变量，所有函数必须支持符号变量代入**：

```python
"""
场景连续代数方程组。
所有函数必须是纯函数 (Pure Functions)，接收浮点数或 SymPy Symbol 对象。
"""
from typing import Dict, Any

def calc_thermal_power_mw(steam_flow_th, delta_enthalpy_kj_kg):
    """SGS 换热热功率 (MW)"""
    return steam_flow_th * delta_enthalpy_kj_kg / 3600.0

def calc_heat_produced_mwh(thermal_power_mw, supply_hours_h, heat_loss_efficiency):
    """总制热量 (MWh)"""
    return thermal_power_mw * supply_hours_h / heat_loss_efficiency

def calc_heater_power_mw(heat_produced_mwh, valley_hours_h, heater_efficiency):
    """电加热器理论电功率 (MW)"""
    return heat_produced_mwh / valley_hours_h / heater_efficiency
```

---

### 2.3 `sizing_rules.json` 规格

定义离散规整规则，支持向上步长取整 (`CEIL_TO_STEP`) 或固定档位匹配 (`NEXT_GREATER_OR_EQUAL`)：

```json
{
  "electric_heater": {
    "target_param": "heater_power_mw",
    "rule": "CEIL_TO_STEP",
    "step": 5.0,
    "min": 5.0,
    "max": 120.0
  },
  "transformer": {
    "target_param": "transformer_capacity_mva",
    "rule": "NEXT_GREATER_OR_EQUAL",
    "standards": [6.3, 8.0, 10.0, 12.5, 16.0, 20.0, 25.0, 31.5, 40.0, 50.0, 63.0, 90.0, 120.0],
    "power_factor": 1.0
  }
}
```

---

### 2.4 `costing_rules.yaml` 规格

定义阶梯分档单价与工程概算费率联动表：

```yaml
equipment_pricing:
  electric_heater:
    rule: "STEPPED"
    tiers:
      - upper_mw: 100.0
        unit_price_wanke_per_mw: 40.0
      - upper_mw: 200.0
        unit_price_wanke_per_mw: 38.0
      - upper_mw: 9999.0
        unit_price_wanke_per_mw: 35.0

cascade_rates:
  construction_and_reserve:
    rate_of_equipment_total: 0.25      # 建设及备用占设备总额比例
  static_investment_ratio:
    equipment_to_static: 0.80          # 设备投资占静态投资 80% 反算
```

---

### 2.5 `benchmarks.json` 规格 (金标回归测试契约)

场景必须包含**至少 1 组常规正解用例**与**至少 1 组反解用例**，作为 CI 准入门禁：

```json
[
  {
    "case_id": "standard_forward_case_1",
    "description": "标准基准工况正解: 100t/h 蒸汽求加热功率与总投资",
    "mode": "FORWARD",
    "inputs": {
      "steam_pressure_mpa": 1.5,
      "steam_temperature_c": 200.0,
      "steam_flow_th": 100.0,
      "steam_supply_hours_h": 8.0,
      "valley_power_hours_h": 8.0
    },
    "expected": {
      "sgs_thermal_power_mw": 75.33,
      "heater_power_nominal_mw": 80.0,
      "transformer_capacity_mva": 90.0
    },
    "tolerance": 0.01
  },
  {
    "case_id": "standard_inverse_case_2",
    "description": "反解用例: 限定变压器容量 90MVA 反推蒸汽流量",
    "mode": "INVERSE",
    "target_param": "steam_flow_th",
    "given": {
      "transformer_capacity_mva": 90.0,
      "steam_pressure_mpa": 1.5,
      "steam_temperature_c": 200.0
    },
    "expected_range": [95.0, 105.0]
  }
]
```
