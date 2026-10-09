# 谷电熔盐储热供汽

本场景实现 `输入输出.xlsx` 七张表的电加热、热泵两套计算、设备选型和工程概算。
运行全部遵循 S0–S8。必填压力、温度、流量缺失时在 S1 中断；预算反解时流量由求解器产生。

## 运行

使用普通 CPython 3.11+（本次验收为 Windows CPython 3.13）。安装声明依赖：

```powershell
py -3.13 -m pip install -r scenarios/molten_salt_steam/requirements.txt
# 当前终端选择已安装依赖的 CPython，避免默认 python 指向 MSYS2。
$pythonDirectory = Split-Path (py -3.13 -c "import sys; print(sys.executable)")
$env:PATH = "$pythonDirectory;$env:PATH"
python -m unittest discover -s tests
python subagent_workspace/ci_runner.py molten_salt_steam
```

```python
from skill_api import CalculationSkill

skill = CalculationSkill()
forward = skill.calculate(
    "molten_salt_steam",
    {"蒸汽压力": 1.5, "蒸汽温度": 200, "蒸汽流量": 100},
    options={"generate_excel": True},
)
inverse = skill.calculate(
    "molten_salt_steam",
    {"steam_pressure_mpa": 1.5, "steam_temperature_c": 200,
     "target_dynamic_investment_wanke": 22650},
    targets=["steam_flow_th"],
    options={"solution_mode": "INVERSE"},
)
```

- 压力为绝压 MPa；流量 t/h；温度 degC；功率 MW；热量 MWh；造价万元。
- 默认值、上下界、别名和所有输出单位在 `manifest.yaml` 中。必填项无隐式默认值。
- 熔盐 `salt_type_id=0` 为 HITEC（390/190 degC），`1` 为太阳盐（565/290 degC）。
  可显式指定 `salt_temperature_high_c` 和 `salt_temperature_low_c`，不得超出物性适用温区。
- 饱和线上 P/T 不足以确定焓值，需显式给出 `steam_quality=1` 或
  `feedwater_quality=0`，同时保证温度与饱和温度一致。
- 热泵始终与电加热一起返回，字段以 `heat_pump_` 区分。COP 是显式输入，
  不虚构余热温度到 COP 的拟合关系。原表默认 COP 为 1.3。
- 电加热预算使用 `target_dynamic_investment_wanke`，热泵预算使用
  `target_heat_pump_dynamic_investment_wanke`。一次只能指定一个预算，不能同时固定流量。
  AUTO 根据预算自动选择反解；SEARCH 与 INVERSE 均求声明范围内预算允许的最大流量。
- Excel 仅在 S7 通过后生成，路径位于 `exports/`，响应提供 `artifacts.excel_path`。

## 七表对应关系

| 工作表 | 实现及口径 |
|---|---|
| 设备型号 | `sizing_rules.json` / `sizing.py`；电加热模块 5–30 MW、热泵模块 5–80 MW，超单机容量组合；变压器超 120 MVA 按多台组合 |
| 熔盐参数 | 通用物性适配器：两种盐的冷热端密度、比热、导热和粘度；太阳盐采用区间积分平均比热 |
| 输入 | `manifest.yaml`；包括效率、供汽/谷电时长、运行天数、COP、温区与概算定额 |
| 计算 | `equations.py`；纯代数支持 SymPy；全精度热平衡、热泵功率、年用电和供汽量 |
| 选型 | `sizing.py`；先规整储热量，再据此计算并规整熔盐量；禁止 S4 提前取整 |
| 造价 | `costing_rules.yaml` / `costing.py`；按原表严格小于阈值的阶梯价格及热泵温度/容量分档 |
| 工程概算 | `costing.py`；系统分摊、管理费、技术服务费、预备费、利息、抵扣和固定资产；同时返回两种方案的行列明细 |

`spec.py` 只做配置加载、场景编排和审计；`reporting.py` 持有场景单元格绑定。
通用引擎不持有任何熔盐项目费率或单元格坐标。通用 FSM 增加按场景声明
选择必要参数的钩子、输入冲突/异常失败令牌，所有致命审计违规始终阻断交付。

## 复现与差异

1. 原表“计算!D10”用谷电时长计算电加热年供汽量，“计算!J11”用供汽时长。
   `annual_steam_wan_t` 按供汽时长计算；`workbook_heater_annual_steam_wan_t`
   保留 D10 原口径。导出保留原公式。时长不同时返回审计提示。
2. 型号备注要求 SGS 向上取整到 5 MW，而“选型!D10”公式取整到 1 MW。
   `sgs_catalog_power_mw` 为型号建议；`sgs_power_nominal_mw` 按原公式计价。
   标准工况分别为 80 MW 和 76 MW。
3. 原表变压器 IFS 从 16 MVA 起，按理论工作电功率选型；热泵先将
   电功率 / 0.85 取整到 1 MVA。保留此计价口径，完整小容量型谱另列于配置。
   不把超上限需求截断为 120 MVA。
4. “工程概算!G10”的 2254.083467489256 万元是样例平衡项，不能固定套用到其他工况。
   实现按其他费用的线性系数解析求解该项，使概算静态投资与造价控制额一致。
   若固定费用导致辅助工程费为负，S7 拒绝交付，不悄悄截成零。
5. 原表 F21 建设期利息固定为 1000 万元，没有贷款比例、利率与建设期输入。
   因此 `construction_interest_wanke` 是可覆盖的显式定额，没有虚构融资模型。
   原表 F23 的 1.02 分母与 1.5% 分子分别配置；这些是样例概算口径，不代表现行税法。
6. 水蒸气使用 [IAPWS-IF97](https://iapws.org/relguide/IF97-Rev.pdf)，缺失依赖时报错，
   不回退到按温度区分水/蒸汽的粗略线性公式。
   原表使用外部 enthalpy 插件，标准点蒸汽焓与 IF97 相差约 0.032 kJ/kg；
   连续量保持物性计算值，离散选型与全部标杆投资精确一致。
7. 熔盐相关式逐项来自原工作簿，资料没有附论文/国家标准编号。
   输出保留原表导热系数及粘度标签，尤其不擅自把粘度换作 Pa·s。
   审计包含相态、温区、换热两端最小温差、工作负载容量、概算平衡及非负性；
   这不是详细换热器沿程设计或设备厂商性能校核。

## 反解与精度

连续公式不截小数；只在 S5 按声明步长规整。设备价格均为整档全量计价，
跨越折扣门槛时总价可能下降，所以反解枚举报价变化的全部平台右端点，
从高到低找到预算可行的最大流量，不假设全局单调。

在标准压力温度和 22650 万元预算下，最大流量约 100.828730188 t/h。
正向回代不超预算，再增加 0.00001 t/h 即进入超预算档。
数值边界误差与概算平衡容差均在配置声明。

## Excel 交付边界

通用 `ExcelTemplateExporter(template_path).export(output_path, cell_mapping)`
使用 openpyxl，以原子写入保护已有目标文件；不存在伪装成 xlsx 的文本占位文件。
默认禁止覆盖公式、数组区域和合并区域非锚点，错误坐标或缺失表名直接失败。
如确需替换模板公式，必须通过 `formula_overrides` 精确列出地址。

本场景保留七表样式、合并区域、外部链接和原数组公式，以 `formula_values`
写入 Python 本次计算的数值缓存。缓存可由 data_only 读取，但 openpyxl 本身不会重算公式。
Excel 打开时请求重算；“计算”表的原始 enthalpy 插件仍需在 Excel 中可用，
手工改输入后需安装原插件或重新调用 Skill 生成文件。
太阳盐比热、显式裕量/利息和超 120 MVA 多机工况仅替换对应的少数必要公式，
其余公式保留。没有宣称通过 Excel 应用实际重算测试。

## 验收

`benchmarks.json` 含原始标准金标、时长不同、阶梯价格、大容量组合、太阳盐和
两种方案预算反解。CI 真实执行每个逆解并完整正向回代，不再无条件打印通过。
测试同时读取原始工作簿缓存验证工程概算各行列，并检查公式、格式、缓存、
无效输入、不可行预算和失败时不产生交付物。
