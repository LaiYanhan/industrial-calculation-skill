# 工业智能计算 Skill (Industrial Calculation Engine)

本项目是一个高可靠、强类型、模块化的**工业与商业智能计算 Skill**。该 Skill 能够作为核心引擎被上层大 Skill 调度，或直接供工程师交互使用。

系统支持从长文本、文档与表格中智能提取参数并完成单位对齐，支持类似 `输入输出.xlsx` 的多层级设备选型与工程概算计算，支持**任意多元线性与非线性代数方程组、以及包含离散阶梯折扣的复杂工程与经济模型全向反向逆解**（支持给定任意已知参数组合反求目标未知量），并具备防止代码堆砌史山的独立子 Agent 维护生命周期。

---

## 目录索引与导航

-  **[系统详细架构设计 (design.md)](./design.md)**：包含全局拓扑图、双环拓扑图、通用状态机规范与多领域落地矩阵。
-  **[产品需求规格说明书 (docs/PRD.md)](./docs/PRD.md)**：详细功能与非功能性需求、验收标准。
-  **[AI Agent 行为准则与防史山红线 (docs/AGENT_BEHAVIOR_GUIDELINES.md)](./docs/AGENT_BEHAVIOR_GUIDELINES.md)**：**所有参与代码编写的 Agent 必须严格阅读并遵守！**
-  **[虚拟环境与依赖配置手册 (docs/ENVIRONMENT_SETUP.md)](./docs/ENVIRONMENT_SETUP.md)**：专属独立虚拟环境 `.venv` 激活与无缝调度指南。
-  **[通用状态机流水线协议 (docs/STATE_MACHINE_SPEC.md)](./docs/STATE_MACHINE_SPEC.md)**：S0~S8 各状态详细前置守卫、动作与后置不变量契约。
-  **[声明式场景包配置规范 (docs/SCENARIO_SCHEMA_SPEC.md)](./docs/SCENARIO_SCHEMA_SPEC.md)**：新增或修改公式时的标准目录与文件格式规范。
-  **[外部接口调用参考 (docs/API_REFERENCE.md)](./docs/API_REFERENCE.md)**：上层大 Skill 调用与错误码参考。
-  **[大模型工具接入与跨主机交付 (integrations/README.md)](./integrations/README.md)**：原生 Function Calling、MCP stdio、LangChain 适配及目标主机配置生成。
-  **[Excel计算差异与运行时警告规范 (docs/EXCEL_DIFFERENCES_AND_WARNINGS.md)](./docs/EXCEL_DIFFERENCES_AND_WARNINGS.md)**：6项原表差异详细定位、简略描述与超限报错规范。
-  **[AI 新增计算场景与公式扩展操作指南 (docs/AI_SCENARIO_EXTENSION_GUIDE.md)](./docs/AI_SCENARIO_EXTENSION_GUIDE.md)**：AI 自迭代脚手架、编程式建场景与沙盒回归全绿准入指引。
---

## 目录结构规划

```
skills/calculate/
├── design.md                          # 全局架构与详细设计说明书
├── README.md                          # 本说明文档
├── requirements.txt                   # 项目核心依赖清单
├── .venv/                             # [已预装] 项目专属隔离虚拟环境
├── skill_api.py                       # 供上层大Skill调用的标准入口类
│
├── integrations/                      # 外部协议适配区；统一调用 skill_api，不包含业务公式
│   ├── function_calling.py            # 原生函数定义、分发器与 Responses Agent 循环
│   ├── mcp_server.py                  # 通用 MCP stdio 服务
│   ├── langchain_tools.py             # 可选 LangChain StructuredTool
│   ├── configure.py                   # 在目标主机输出配置，不修改客户端
│   └── package.py                     # 跨主机源码交付包生成器
│
├── docs/                              # 核心规范与准则库 (只读区)
│   ├── ENVIRONMENT_SETUP.md           # 虚拟环境配置与激活指南
│   ├── AGENT_BEHAVIOR_GUIDELINES.md   # [核心红线] AI行为准则与防腐规范
│   ├── PRD.md                         # 需求规格说明书
│   ├── STATE_MACHINE_SPEC.md          # 状态机S0-S8协议规范
│   ├── SCENARIO_SCHEMA_SPEC.md        # 声明式场景包规范
│   └── API_REFERENCE.md               # 外部调用接口文档
│
├── engine/                            # 核心计算引擎代码 (核心只读区)
│   ├── fsm/                           # 确定有限状态机运行时 (FSM S0~S8)
│   │   ├── context.py                 # 执行上下文状态总线 (ExecutionContext)
│   │   ├── state.py                   # 抽象状态基类与令牌 (BaseState, StateToken)
│   │   ├── controller.py              # 状态机调度器 (FSMController)
│   │   └── states/                    # S0 ~ S8 各阶段状态实现抽象
│   ├── solver/                        # 符号代数求解与二分逆解 (NumericInverter)
│   ├── properties/                    # 物性查表与常数库适配器
│   │   ├── iapws_adapter.py           # 水蒸气 IAPWS-IF97 适配器 (优先加载内置离线包)
│   │   ├── salt_adapter.py            # 熔盐物性多项式计算
│   │   ├── finance_adapter.py         # 商业基准费率适配器
│   │   └── vendor/iapws/              # [内置离线物性库] 完整打包的 IAPWS-IF97 查表与计算模块
│   └── exporter/                      # Excel/JSON/Markdown 多模态导出器
│       └── excel_exporter.py          # 基于 openpyxl 的七表联动公式保留回填器
│
├── scenarios/                         # 声明式场景仓库 (业务扩展区)
│   ├── base.py                        # 场景抽象基类 (BaseScenarioSpec)
│   ├── registry.py                    # 场景注册中心 (ScenarioRegistry)
│   ├── molten_salt_steam/             # 标杆工业场景: 谷电熔盐供汽选型与概算
│   │   ├── templates/输入输出.xlsx    # [模板与标杆数据] 原始工程 7 表工作簿
│   │   ├── manifest.yaml              # 场景元数据、参数、边界与别名
│   │   ├── sizing.py / sizing_rules.json  # 设备工程离散选型与阶梯规整
│   │   ├── costing.py / costing_rules.yaml# 分项设备造价与工程概算费率联动
│   │   ├── inversion.py               # 预算反解与最大产汽能力平台搜索
│   │   ├── reporting.py               # Excel 单元格无损映射与公式缓存回填
│   │   ├── spec.py                    # 场景全生命周期编排与常理审计门禁
│   │   └── benchmarks.json            # 标杆正反向金标回归测试集
│   └── financial_profit_model/        # 标杆商业场景: 财务利润与EBITDA测算
│
├── subagent_workspace/                # 子Agent独立沙盒与变更验证工作区
│   ├── README.md                      # 子Agent开发操作流程
│   └── ci_runner.py                   # 沙盒回归测试执行器
│
├── tests/                             # 自动化测试套件
│   ├── test_fsm_pipeline.py           # 状态机流转与防跳步测试
│   ├── test_solver_inversion.py       # 符号反解测试
│   ├── test_scenario_regression.py    # 场景金标用例全量正反向回归测试
│   ├── test_excel_delivery.py         # 七表 Excel 格式与公式缓存保留验证
│   └── test_molten_salt_business.py   # 熔盐工程全流程业务数值深度对齐测试
│
└── exports/                           # 运行时动态生成的 Excel 报表落盘区
```
---

## 核心开发红线摘要

1. **严禁在根目录下乱建临时文件**：所有新增计算场景只能放置在 `scenarios/<scenario_id>/` 目录内；
2. **严禁在 `engine/` 内编写特定业务场景的硬编码逻辑**：核心引擎保持领域无关，具体公式必须声明化；
3. **计算步骤不可跳跃**：必须按 S0~S8 单步执行并满足前置守卫后才可推进；
4. **测试门禁**：新场景必须包含 `benchmarks.json`，且在沙盒中通过全量回归测试方可正式发布生效。

---

## 跨环境无缝移植与离线自包含打包说明

为了保证本项目作为子模块能够在各种环境（包括离线内网、独立服务器、或被上层大 Skill 跨目录调用）中即插即用：

1. **绝不硬编码绝对路径**：
   - 根目录、场景配置、模板文件与输出目录均采用基于当前文件的相对解析：`Path(__file__).resolve()`。
   - 无论从项目根目录、父级目录还是任意工作目录下通过 `import` 调用 `CalculationSkill`，均能正确读取 `输入输出.xlsx` 模板并将报表安全写入 `exports/`。

2. **相关查表与物性库直接打包就绪**：
   - 水和水蒸气国际标准热力学计算库（IAPWS-IF97）已完整打包进 `engine/properties/vendor/iapws/` 目录中。
   - 系统优先加载内置打包的查表库，无需依赖外部网络或全局 `pip install iapws`，解压即用。
   - 熔盐物性多项式、设备规格型号库、工程造价阶梯单价表均在场景包中离线配置。
