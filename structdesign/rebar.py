"""
钢筋数据库与选筋（离散化）。

把连续的“需要面积 As”落到现实的“n 根 D 直径”的离散组合，并尊重
单层最大根数（净距/排布）。这是问题域④“算得过≠建得出”的第一步。
"""
from __future__ import annotations
import math
from dataclasses import dataclass
from typing import List, Optional

# 梁柱常用纵筋直径 (mm)。梁纵筋实践上少用 12/14，故主筋从 16 起，
# 优先少根大直径，避免"算得过但排不下/不经济"的多根小筋。
MAIN_DIAMETERS = [16, 18, 20, 22, 25, 28, 32]
# 常用箍筋直径 (mm)
STIRRUP_DIAMETERS = [6, 8, 10, 12]


def area(d: float) -> float:
    """单根钢筋面积 (mm²)。"""
    return math.pi * d * d / 4.0


@dataclass
class BarChoice:
    n: int
    d: float

    @property
    def As(self) -> float:
        return self.n * area(self.d)

    def __str__(self) -> str:
        return f"{self.n}⋌D{int(self.d)}"  # 例如 3⋌D22 → 显示 3D22

    def label(self) -> str:
        return f"{self.n}D{int(self.d)}"


def max_bars_per_layer(b: float, d: float, cover: float = 25.0,
                       stirrup_d: float = 8.0) -> int:
    """单层最大根数：按净距 max(25, d) 估算 (规范 9.2.1)。"""
    clear = max(25.0, d)
    avail = b - 2 * cover - 2 * stirrup_d  # 可布筋净宽
    n = int(math.floor((avail - d) / (d + clear))) + 1
    return max(n, 2)


def select_bars(As_req: float, b: float,
                diameters: Optional[List[float]] = None,
                cover: float = 25.0, stirrup_d: float = 8.0,
                max_layers: int = 2, max_over: float = 0.30) -> Optional[BarChoice]:
    """为受拉钢筋选一个 n·D 组合：满足 As>=As_req，超配尽量小、根数适中。

    返回浪费率最小者；若都超过 max_over 仍取最接近的可行解。
    """
    diameters = diameters or MAIN_DIAMETERS
    if As_req <= 0:
        return BarChoice(2, diameters[0])     # 无计算需求 → 最小构造2根
    candidates: List[BarChoice] = []
    for d in diameters:
        nmax = max_bars_per_layer(b, d, cover, stirrup_d) * max_layers
        a1 = area(d)
        n = max(2, math.ceil(As_req / a1))
        if n > nmax:
            continue
        candidates.append(BarChoice(n, d))
    if not candidates:
        # 退而求其次：用最大直径多层
        d = diameters[-1]
        n = max(2, math.ceil(As_req / area(d)))
        return BarChoice(n, d)

    def over(c: BarChoice) -> float:
        return (c.As - As_req) / As_req

    feasible = [c for c in candidates if over(c) <= max_over]
    pool = feasible if feasible else candidates
    # 实践偏好：在可接受浪费(≤max_over)内优先"少根"，并列再比浪费率。
    # 避免选出 8 根小直径这类排不下/不经济的方案。
    pool.sort(key=lambda c: (c.n, round(over(c), 4)))
    return pool[0]
