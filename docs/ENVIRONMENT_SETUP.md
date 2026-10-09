# 运行环境与独立虚拟环境配置规范 (Environment Setup Manual)

本项目提供开箱即用的专属独立虚拟环境（`.venv`），实现环境自包含与零外部依赖污染。本说明书指导开发者、上层大 Skill 调度器以及自动化工具如何激活与使用该环境。

---

## 1. 虚拟环境规格

| 属性 | 配置值 | 说明 |
| :--- | :--- | :--- |
| **虚拟环境目录** | `.venv/` (位于项目根目录下) | 已加入 `.gitignore`，避免二进制文件提交进仓库 |
| **基础解释器版本**| Python 3.11+ (当前构建使用 CPython 3.13) | 64-bit 标准 CPython |
| **依赖清单文件** | `requirements.txt` | 包含 `openpyxl`, `PyYAML`, `sympy`, `scipy`, `numpy`, `iapws` |
| **离线查表支持** | `engine/properties/vendor/iapws/` | 内置打包，支持脱机环境免在线 pip 安装即插即用 |

---

## 2. 虚拟环境激活与日常使用

根据您使用的操作系统与终端类型，选择对应的指令：

### 2.1 Windows PowerShell
```powershell
# 1. 激活虚拟环境 (首次运行若提示执行策略限制，可先执行 Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass)
.\.venv\Scripts\Activate.ps1

# 2. 运行验证
python -m unittest discover -s tests
python subagent_workspace/ci_runner.py molten_salt_steam
```

### 2.2 Windows CMD (命令提示符)
```cmd
:: 1. 激活虚拟环境
.venv\Scripts\activate.bat

:: 2. 运行验证
python -m unittest discover -s tests
python subagent_workspace/ci_runner.py molten_salt_steam
```

### 2.3 Git Bash / MSYS2 / Linux / macOS
```bash
# 1. 激活虚拟环境 (Windows Git Bash)
source .venv/Scripts/activate

# 或标准 Linux/macOS
# source .venv/bin/activate

# 2. 运行验证
python -m unittest discover -s tests
python subagent_workspace/ci_runner.py molten_salt_steam
```

---

## 3. 免激活：直接使用虚拟环境解释器调用 (推荐给大 Skill)

外部大 Skill 或调用脚本在集成时，**无需先激活环境**，只需直接指定虚拟环境中的 Python 可执行文件路径即可：

### 命令行直接调用：
```bash
# Windows
.\.venv\Scripts\python.exe skill_api.py

# 自动化测试
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

### Python 代码内以子进程方式调度：
```python
import subprocess
import os

skill_root = os.path.dirname(os.path.abspath(__file__))
venv_python = os.path.join(skill_root, ".venv", "Scripts", "python.exe")

# 调用 calculation skill 的 CLI 或脚本
result = subprocess.run(
    [venv_python, os.path.join(skill_root, "skill_api.py")],
    capture_output=True,
    text=True,
    encoding="utf-8"
)
print(result.stdout)
```

---

## 4. 依赖重新构建与更新流程 (若需重建环境)

若在全新的机器上克隆本项目，或需要重建 `.venv`，可按以下标准命令三步完成：

```powershell
# 步骤 1：创建干净的虚拟环境
py -3.13 -m venv .venv

# 步骤 2：安装项目核心依赖
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 步骤 3：一键回归测试验证环境就绪
.\.venv\Scripts\python.exe -m unittest discover -s tests
```
