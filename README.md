# 工业智能计算 Skill (Industrial Calculation Engine)

本项目是一个高可靠、强类型、模块化的**工业与商业智能计算 Skill**。该 Skill 能够作为核心引擎被上层大 Skill 调度，或直接供工程师交互使用。

系统支持从长文本、文档与表格中智能提取参数并完成单位对齐，支持类似 `输入输出.xlsx` 的多层级设备选型与工程概算计算，支持 $a+b+c=d$ 类方程与经济总投资的全向反向逆解，并具备防止代码堆砌史山的独立子 Agent 维护生命周期。

---

## 目录索引与导航

- 📘 **[系统详细架构设计 (design.md)](./design.md)**：包含全局拓扑图、双环拓扑图、通用状态机规范与多领域落地矩阵。
- 📋 **[产品需求规格说明书 (docs/PRD.md)](./docs/PRD.md)**：详细功能与非功能性需求、验收标准。
- 🛑 **[AI Agent 行为准则与防史山红线 (docs/AGENT_BEHAVIOR_GUIDELINES.md)](./docs/AGENT_BEHAVIOR_GUIDELINES.md)**：**所有参与代码编写的 Agent 必须严格阅读并遵守！**
- ⚙️ **[通用状态机流水线协议 (docs/STATE_MACHINE_SPEC.md)](./docs/STATE_MACHINE_SPEC.md)**：S0~S8 各状态详细前置守卫、动作与后置不变量契约。
- 📦 **[声明式场景包配置规范 (docs/SCENARIO_SCHEMA_SPEC.md)](./docs/SCENARIO_SCHEMA_SPEC.md)**：新增或修改公式时的标准目录与文件格式规范。
- 🔌 **[外部接口调用参考 (docs/API_REFERENCE.md)](./docs/API_REFERENCE.md)**：上层大 Skill 调用与错误码参考。

---

## 目录结构规划

```
skills/calculate/
├── design.md                          # 全局架构与详细设计说明书
├── README.md                          # 本说明文档
├── skill_api.py                       # 供上层大Skill调用的标准入口类
├── 输入输出.xlsx                      # 工业熔盐储热工程原始标杆文件
│
├── docs/                              # 核心规范与准则库 (只读区)
│   ├── AGENT_BEHAVIOR_GUIDELINES.md   # [核心红线] AI行为准则与防腐规范
│   ├── PRD.md                         # 需求规格说明书
│   ├── STATE_MACHINE_SPEC.md          # 状态机S0-S8协议规范
│   ├── SCENARIO_SCHEMA_SPEC.md        # 声明式场景包规范
│   └── API_REFERENCE.md               # 外部调用接口文档
│
├── engine/                            # 核心计算引擎代码骨架 (核心只读区)
│   ├── fsm/                           # 确定有限状态机运行时
│   │   ├── context.py                 # 执行上下文状态总线 (ExecutionContext)
│   │   ├── state.py                   # 抽象状态基类与令牌
│   │   ├── controller.py              # 状态机调度器
│   │   └── states/                    # S0 ~ S8 各阶段状态实现抽象
│   ├── solver/                        # 符号代数求解与二分逆解抽象
│   ├── properties/                    # 物性查表 (IAPWS) 与常数库适配器
│   └── exporter/                      # Excel/JSON/Markdown 导出器
│
├── scenarios/                         # 声明式场景仓库 (业务扩展区)
│   ├── base.py                        # 场景抽象基类
│   ├── registry.py                    # 场景注册中心
│   ├── molten_salt_steam/             # 标杆工业场景: 谷电熔盐供汽选型与概算
│   └── financial_profit_model/        # 标杆商业场景: 财务利润与EBITDA测算
│
├── subagent_workspace/                # 子Agent独立沙盒与变更验证工作区
│   └── ci_runner.py                   # 沙盒回归测试执行器
│
├── tests/                             # 自动化测试套件
│   ├── test_fsm_pipeline.py           # 状态机流转与防跳步测试
│   ├── test_solver_inversion.py       # 符号反解测试
│   └── test_scenario_regression.py    # 场景金标用例回归测试
│
└── exports/                           # 运行时动态生成的 Excel 报表落盘区
```

---

## 核心开发红线摘要

1. **严禁在根目录下乱建临时文件**：所有新增计算场景只能放置在 `scenarios/<scenario_id>/` 目录内；
2. **严禁在 `engine/` 内编写特定业务场景的硬编码逻辑**：核心引擎保持领域无关，具体公式必须声明化；
3. **计算步骤不可跳跃**：必须按 S0~S8 单步执行并满足前置守卫后才可推进；
4. **测试门禁**：新场景必须包含 `benchmarks.json`，且在沙盒中通过全量回归测试方可正式发布生效。
