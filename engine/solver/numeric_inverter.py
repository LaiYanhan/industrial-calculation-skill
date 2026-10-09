"""
数值逆解与区间阶梯二分器 (Numeric Inverter).
用于穿透 ROUNDUP、IFS 离散选型与分档单价阶梯，反推前端工艺或商业参数。
支持非严格单调、存在折扣跳跃降价区间的阶梯平台端点枚举反解。
"""

from typing import Callable, Optional, Sequence, Tuple


class NumericInverter:
    """
    单调性与分段阶梯感知反解器.
    通过反复黑盒调用前向评估函数，锁定满足目标约束的最优工艺参数自变量。
    """

    @staticmethod
    def bisect(
        forward_eval_fn: Callable[[float], float],
        target_y: float,
        x_min: float,
        x_max: float,
        tol: float = 1e-4,
        max_iter: int = 60
    ) -> Tuple[Optional[float], int]:
        """
        单调区间二分法求解: 寻找满足 forward_eval_fn(x) <= target_y 的最大 x.
        假设 forward_eval_fn 在 [x_min, x_max] 局部单调递增.
        返回 (求得的最优x, 迭代次数). 严格保证 forward_eval_fn(best_x) <= target_y.
        """
        low = x_min
        high = x_max
        iter_count = 0
        best_x = x_min if forward_eval_fn(x_min) <= target_y else None

        while iter_count < max_iter and (high - low) > tol:
            iter_count += 1
            mid = (low + high) / 2.0
            y_mid = forward_eval_fn(mid)

            if y_mid <= target_y:
                best_x = mid
                low = mid
            else:
                high = mid

        return best_x, iter_count

    @classmethod
    def solve_piecewise_stepped_inverse(
        cls,
        forward_eval_fn: Callable[[float], float],
        target_y: float,
        candidate_breakpoints: Sequence[float],
        tol: float = 1e-4,
        max_iter: int = 60
    ) -> Optional[float]:
        """
        非严格单调阶梯反解算法 (结合阶梯平台端点枚举与局部区间求根).
        
        背景: 当设备价格跨越阶梯折扣时(如 99MW 计价 40万/MW，100MW 降为 38万/MW)，
        总投资在门槛右侧发生阶梯突降，函数全局非严格单调。
        
        算法逻辑:
        1. 收集包含所有离散选型步长与折扣门槛的断点集合 candidate_breakpoints;
        2. 将断点从大到小排序，从最大候选区间/端点开始向下检验;
        3. 对每个端点 x_high: 若 forward_eval_fn(x_high) <= target_y，因倒序遍历，立即锁定全局最大可行解;
        4. 若在 [x_low, x_high] 之间存在连续可调节变化且 y_low <= target_y < y_high，
           则调用局部保守二分法求解满足 cost <= target_y 的最大连续根;
        5. 返回全局可行的最大自变量 x.
        """
        if not candidate_breakpoints:
            return None

        sorted_points = sorted(set(candidate_breakpoints), reverse=True)

        for i, pt in enumerate(sorted_points):
            y_pt = forward_eval_fn(pt)
            if y_pt <= target_y:
                return pt

            # 若当前点超预算，但下一个更低点在预算内，且区间内可能存在局部连续过渡
            if i + 1 < len(sorted_points):
                pt_next = sorted_points[i + 1]
                y_next = forward_eval_fn(pt_next)
                if y_next <= target_y:
                    # 局部保守二分查找
                    root_x, _ = cls.bisect(
                        forward_eval_fn=forward_eval_fn,
                        target_y=target_y,
                        x_min=pt_next,
                        x_max=pt,
                        tol=tol,
                        max_iter=max_iter
                    )
                    if root_x is not None:
                        return root_x

        return None
