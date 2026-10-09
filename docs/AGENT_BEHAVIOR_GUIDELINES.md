# AI Agent 行为准则与架构防腐红线规范 (Agent Behavior Guidelines)

> **【强制执行令】**：本项目致力于构建高可靠、工业级的智能计算 Skill。任何参与本项目的 AI Agent（无论是主 Agent、子 Agent、代码编写 Agent 还是维护 Agent）**必须严格遵循本规范**。
> **违反本规范的任何操作（如乱放文件、修改核心只读区代码、硬编码魔数、跳过状态机步骤）均被视为违规，其产出将被 CI 门禁直接驳回**。

---

## 1. 目录与文件安放铁律 (File Placement Invariants)

为了彻底杜绝“文件漫天散落、临时文档堆积成山”，本项目实行**绝对受限的目录隔离制度**：

| 目录路径 | 读写权限 | 允许放置的文件类型 | 严厉禁止的行为 (Forbidden) |
| :--- | :--- | :--- | :--- |
| **根目录 `/`** | **受限** | 仅允许：`README.md`、`design.md`、`skill_api.py`、`requirements.txt`、`.gitignore` | **严禁**创建任何业务数据 `.xlsx`、临时 `.py`、`.md`、`.txt`、`.json` 或导出文件！ |
| **`docs/`** | **只读 / 架构师专修** | 系统架构文档、PRD、规范说明书、状态机协议 | **严禁**在此存放单次会话临时笔记、调试草稿或场景特定的局部说明。 |
| **`engine/`** | **核心只读保护区** | 通用 FSM 状态机调度、符号反解抽象、物性适配接口、导出器核心代码 | **严禁**在此处编写任何特定业务/工程场景的计算公式！引擎必须保持 100% 领域无关。 |
| **`scenarios/<scenario_id>/`** | **业务开发区** | 场景元数据 `manifest.yaml`、方程 `equations.py`、离散规则 `sizing_rules.json`、费率表 `costing_rules.yaml`、测试集 `benchmarks.json`、专用模板 `templates/`、局部说明 `README.md` | **严禁**在场景目录内引入与该场景无关的通用逻辑，**严禁**修改其他场景目录的文件。 |
| **`subagent_workspace/`** | **子Agent沙盒区** | 子 Agent 迭代、调试、临时草稿、生成补丁中间态 | 正式生效后必须清理临时文件，不能遗留垃圾。 |
| **`tests/`** | **测试套件区** | 基于 `pytest` 的单元测试、状态机集成测试、金标回归测试 | **严禁**在此存放生产逻辑代码。 |
| **`exports/`** | **运行时输出区** | 动态生成的 `.xlsx` 计算报表、导出 JSON 结果 | 运行时产物，禁止提交至版本库长期驻留。 |

---

## 2. 架构防腐与防“史山”代码规范 (Anti-Technical-Debt Rules)

### 2.1 严禁侵蚀核心引擎 (Engine Immutability)
- `engine/` 属于通用计算平台，负责状态调度、SymPy/SciPy 数学求根、Excel 模板公式绑定渲染。
- **违规行为举例**：
  - ❌ *错误*：在 `engine/fsm/controller.py` 里写 `if scenario == "molten_salt": heater_power = ...`
  - ✅ *正确*：将加热器计算逻辑封装在 `scenarios/molten_salt_steam/equations.py` 中，通过通用 FSM 的 `S4_CONTINUOUS_SOLVE` 动态挂载调度。

### 2.2 严禁“魔数”硬编码 (No Magic Numbers)
- 代码中所有系数、物性经验常数、费率、分档规格，必须：
  1. 在 `manifest.yaml` 的 `parameters` 中显式声明；
  2. 或在 `costing_rules.yaml` / `sizing_rules.json` 中配置；
  3. 或在物理物性拟合库中注明学术/国家标准来源（如 GB/T、IAPWS-IF97）。
- **违规行为举例**：
  - ❌ *错误*：`power = flow * (h1 - h2) / 3600 / 0.985`（0.985 是什么？3600 为什么没有单位说明？）
  - ✅ *正确*：`power_mw = (flow_th * (h_out_kj_kg - h_in_kj_kg) / 3600.0) / heater_efficiency`

### 2.3 必须严格遵循强类型与单位显式声明
- 所有 Python 函数必须具备完整的类型注解 (`Type Hints`)。
- 变量命名强制包含物理量或量纲后缀：
  - 压力：`pressure_mpa`
  - 温度：`temperature_c` 或 `temperature_k`
  - 流量：`flow_th`（吨/小时）或 `flow_kgs`（千克/秒）
  - 功率：`power_mw` 或 `power_kw`
  - 金额：`cost_wanke`（万元）或 `cost_cny`（元）
- 严禁出现无量纲、含义模糊的单字母变量（除纯数学方程中的临时符号 $x, y, z$ 外）。

### 2.4 工具优先与联网搜索门禁 (Tool Primacy & Human Approval Gate)
- **能够调用工具获得的数据绝对不能使用搜索工具**：所有已支持的工程热工物性（如水蒸气焓值）、熔盐储热参数、热泵性能、设备选型规格、工程概算造价与商业财务指标等，必须直接调用本工具计算，严禁使用 web_search 联网检索或自身记忆估算。
- **不能得到的数据先获得人类批准，再决定是否上网搜索**：若用户提出的需求包含本工具当前未支持、无法通过已有计算场景得出的外部数据，严禁擅自直接联网搜索，必须先向人类用户请示说明，获得人类明确批准后，方可决定是否上网搜索。

---

## 3. 严格状态机流水线契约 (FSM Execution Discipline)

Agent 在执行业务计算或编写计算调度代码时，**绝对禁止随意跳步**：

1. **不可跳越性 (No Skipping States)**：
   - 必须按 `S0 槽位抽取` $\to$ `S1 量纲对齐` $\to$ `S2 拓扑判定` $\to$ `S3 基准查表` $\to$ `S4 连续求解` $\to$ `S5 离散规整` $\to$ `S6 指标联动` $\to$ `S7 常理审计` $\to$ `S8 报表交付` 单向流转。
   - 严禁直接从 `S0` 跨过量纲校验直接进行 `S4` 求解！
2. **状态令牌机制 (Token Passing)**：
   - 每个状态的输出由 `ExecutionContext` 统一管理，并产生状态执行凭据 (`StateToken`)。
   - 下一状态在执行前必须校验前序状态的凭据。
3. **失败即阻断 (Fail-Fast & Graceful Rollback)**：
   - `S1` 发现自变量缺失时，必须中断执行，输出精准缺参清单，等待人类或外部上层 Agent 补齐；禁止“擅自假设一个默认值悄悄计算”。
   - `S7` 常理审计未通过（如出现物理温度交叉、负投资额、负税额）时，必须中断交付并给出违背业务规则的明确根因。

---

## 4. 新场景开发 6 步标准生命周期 (Scenario Dev Standard Protocol)

当后续 AI Agent 接收到“新增计算公式/新建计算场景”的任务时，必须严格执行以下标准 6 步流程，禁止私自省略：

```
[1. 定义元数据 manifest.yaml]
              │
              ▼
[2. 编写代数方程 equations.py]
              │
              ▼
[3. 配置离散规则 sizing_rules.json & costing_rules.yaml]
              │
              ▼
[4. 录入基准金标用例 benchmarks.json]
              │
              ▼
[5. 沙盒运行回归测试 pytest tests/]
              │
        ┌─────┴─────┐
     全部通过?    未通过?
        │           │
       是           └──► 回退修改并记录错误原因
        ▼
[6. 场景注册与正式发布 registry.py]
```

### 规范检查清单 (Checklist for Agents)
- [ ] 场景 ID 是否为英文小写蛇形命名（如 `molten_salt_steam`）？
- [ ] `manifest.yaml` 是否包含了所有的输入输出参数，且标明了 `canonical_unit`？
- [ ] `equations.py` 中的公式是否支持符号提取，便于求解器做正反解？
- [ ] `benchmarks.json` 中是否包含**至少 1 组常规正解用例**和**至少 1 组逆向反解用例**？
- [ ] 是否在沙盒环境中执行了 `pytest` 并获得了 100% 通过？
- [ ] 场景目录下是否包含简明扼要的 `README.md` 说明该场景的工艺/业务含义？

---

## 5. 违规处罚与自动化门禁 (CI Enforcement)

项目集成自动化合规检查工具（Linter / CI Guard）：
1. 检查根目录下是否存在未注册文件；
2. 检查代码中是否存在未带量纲后缀的浮点参数；
3. 检查核心 `engine/` 是否被非授权篡改；
4. 检查是否跳过回归测试。
任何一项违背，整个构建流程直接终止。
