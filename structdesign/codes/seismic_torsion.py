"""
多向地震组合 + 偶然偏心扭转（GB 50011 5.2.3 / 4.3.5）。

  - 双向水平地震组合：S = max(√(Sx²+(0.85Sy)²), √(Sy²+(0.85Sx)²))
  - 偶然偏心：垂直地震方向取 ±5% 边长，刚性楼盖下按平动+扭转分配层剪力到各榀。
"""
from __future__ import annotations
import math
from dataclasses import dataclass
from typing import List, Tuple


def bidirectional_combination(Sx: float, Sy: float) -> float:
    """双向水平地震作用效应组合 (5.2.3)。Sx/Sy 为两方向单算的效应。"""
    return max(math.hypot(Sx, 0.85 * Sy), math.hypot(Sy, 0.85 * Sx))


@dataclass
class TorsionResult:
    x_cr: float                 # 刚心位置
    e_accidental: float         # 偶然偏心
    frame_forces: List[float]   # 各榀分配剪力
    amplification: List[float]  # 各榀相对纯平动的放大系数


def torsional_distribution(V: float, frames: List[Tuple[float, float]],
                           plan_dim: float, ecc_ratio: float = 0.05) -> TorsionResult:
    """刚性楼盖偶然偏心扭转分配。

    frames: [(x_i, k_i)] 各抗侧力榀的位置与抗侧刚度(同方向)。
    plan_dim: 垂直地震方向的平面尺寸；偶然偏心 e=ecc_ratio·plan_dim。
    F_i = V·ki/Σk(平动) + T·ki·di/Σ(kj·dj²)(扭转), di=xi-x_cr, T=V·e。
    """
    xs = [f[0] for f in frames]
    ks = [f[1] for f in frames]
    sk = sum(ks)
    x_cr = sum(k * x for x, k in frames) / sk
    e = ecc_ratio * plan_dim
    T = V * e
    di = [x - x_cr for x in xs]
    Ip = sum(k * d * d for k, d in zip(ks, di))  # 抗扭刚度
    forces, amp = [], []
    for k, d in zip(ks, di):
        f_tr = V * k / sk
        f_to = (T * k * d / Ip) if Ip > 0 else 0.0
        # 取偶然偏心两侧不利者(±e)，放大边榀
        f = f_tr + abs(f_to)
        forces.append(f)
        amp.append(f / f_tr if f_tr != 0 else 1.0)
    return TorsionResult(x_cr=x_cr, e_accidental=e, frame_forces=forces, amplification=amp)
