"""
符号与数值双向反解引擎包 (Solver Package).
支持 SymPy 符号代数反解与 SciPy/区间二分阶梯穿透反解。
"""

from engine.solver.symbolic_engine import BaseSymbolicEngine
from engine.solver.numeric_inverter import NumericInverter

__all__ = ["BaseSymbolicEngine", "NumericInverter"]
