"""
CQC 完全二次型振型组合（GB 50011 5.2.3 条文说明 / Der Kiureghian）。

考虑相近振型间的相关性（扭转耦联时尤为重要）。SRSS 假设振型独立，对周期接近的
平动-扭转耦联会低估；CQC 用相关系数 ρij 修正。

  ρij = 8ζ²(1+r)·r^1.5 / [(1-r²)² + 4ζ²·r·(1+r)²],  r = Tj/Ti (≤1)
  S = √(ΣΣ ρij·Si·Sj)

验证：ρii=1；振型分离 r→0 则 ρij→0(退化为 SRSS)；振型相近 r→1 则 ρij→1。
"""
from __future__ import annotations
import math
from typing import List


def correlation(Ti: float, Tj: float, zeta: float = 0.05) -> float:
    """两振型相关系数 ρij。"""
    if Ti <= 0 or Tj <= 0:
        return 0.0
    r = min(Ti, Tj) / max(Ti, Tj)      # 0<r<=1
    num = 8 * zeta**2 * (1 + r) * r**1.5
    den = (1 - r**2)**2 + 4 * zeta**2 * r * (1 + r)**2
    return num / den


def cqc(values: List[float], periods: List[float], zeta: float = 0.05) -> float:
    """CQC 组合。values: 各振型的响应(同一物理量)，periods: 对应自振周期。"""
    n = len(values)
    s = 0.0
    for i in range(n):
        for j in range(n):
            s += correlation(periods[i], periods[j], zeta) * values[i] * values[j]
    return math.sqrt(max(s, 0.0))


def srss(values: List[float]) -> float:
    return math.sqrt(sum(v*v for v in values))
