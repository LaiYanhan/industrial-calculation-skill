# 公式维护子 Agent 独立沙盒工作区 (Sub-Agent Workspace)

本目录为**公式维护子 Agent (Formula Dev Sub-Agent)** 专属工作沙盒。

## 工作协议
1. 子 Agent 接收到新增公式或修改场景需求后，**严禁修改 `engine/` 核心目录**。
2. 所有新场景必须在 `scenarios/<scenario_id>/` 目录下遵循《场景配置规范》编写；
3. 开发完成后，必须在当前沙盒执行回归测试：
   ```bash
   python subagent_workspace/ci_runner.py <scenario_id>
   ```
4. 只有回归测试输出 **100% 通过 (全绿准入)** 时，方可通知主调度 Agent 注册上线。
