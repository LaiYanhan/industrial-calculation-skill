"""
数值逆解与区间阶梯二分器 (Numeric Inverter).
用于穿透 ROUNDUP、IFS 离散选型与分档单价阶梯，反推前端工艺或商业参数。
"""

from typing import Callable, Optional, Tuple


class NumericInverter:
    """
    单调性区间感知二分反解器.
    通过反复黑盒调用前向评估函数，锁定满足目标约束的最优工艺参数自变量。
    """

    @staticmethod
    def bisect(
        forward_eval_fn: Callable[[float], float],
        target_y: float,
        x_min: float,
        x_max: float,
        tol: float = 1e-3,
        max_iter: int = 60
    ) -> Tuple[Optional[float], int]:
        """
        二分法求解: 寻找满足 forward_eval_fn(x) 接近 target_y 的 x.
        假设 forward_eval_fn 在 [x_min, x_max] 上严格单调递增.
        返回 (求得的最优x, 迭代次数).
        """
        low = x_min
        high = x_max
        iter_count = 0

        best_x = None

        while iter_count < max_iter:
            iter_count += 1
            mid = (low + high) / 2.0
            y_mid = forward_eval_fn(mid)

            if abs(y_mid - target_y) <= tol or (high - low) <= tol:
                best_x = mid
                break

            if y_mid < target_y:
                low = mid
                best_x = mid
            else:
                high = mid

        return best_x, iter_count
