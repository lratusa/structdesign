"""
楼板/次梁竖向荷载导算 —— 把面荷载 q(kN/m²) 转成支承梁线荷载 w(kN/m=N/mm)。

  - 单向板：w = q · 受荷宽度(板跨的一半各侧 → 梁间距)。
  - 双向板：按 45° 分块，短边梁受三角形、长边梁受梯形；给出"荷载守恒等效均布"
    （Σ w·L = q·lx·ly，精确）与三角形/梯形峰值，供配筋使用。
单位约定：q[kN/m²], 长度[m] → w[kN/m]，数值上 1 kN/m = 1 N/mm。
"""
from __future__ import annotations
from dataclasses import dataclass


def one_way_udl(q, beam_spacing):
    """单向板：梁线荷载 w = q · 受荷宽度(=梁间距)。返回 kN/m。"""
    return q * beam_spacing


@dataclass
class TwoWayLoads:
    lx: float          # 短跨
    ly: float          # 长跨
    q: float
    w_short: float     # 短边梁(长lx)荷载守恒等效均布 (kN/m)
    w_long: float      # 长边梁(长ly)荷载守恒等效均布 (kN/m)
    p_peak: float      # 三角形/梯形峰值线荷载 (kN/m) = q·lx/2
    total_load: float  # 总荷载 (kN)


def two_way_beam_loads(q, lx, ly) -> TwoWayLoads:
    """双向板(lx≤ly)四边梁荷载。45°分块，荷载守恒等效均布。

    短边梁(沿短边,长lx)受三角形: 面积 lx²/4 → w_short=q·lx/4
    长边梁(沿长边,长ly)受梯形:   w_long = q·lx(2ly-lx)/(4ly)
    校验: 2·w_short·lx + 2·w_long·ly = q·lx·ly (精确)
    """
    if lx > ly:
        lx, ly = ly, lx
    w_short = q * lx / 4.0
    w_long = q * lx * (2 * ly - lx) / (4.0 * ly)
    return TwoWayLoads(lx=lx, ly=ly, q=q, w_short=w_short, w_long=w_long,
                       p_peak=q * lx / 2.0, total_load=q * lx * ly)


def moment_equiv_triangular(p_peak):
    """三角形分布(峰值p)→受弯等效均布(同最大弯矩): w_eq = (2/3)·...

    简支梁三角形(两端0中间p): Mmax=p·L²/12; 等效均布 w·L²/8=p·L²/12 → w=2p/3·(8/12)...
    实际 w_eq = p·(8/12)/... 取 5/6·p 的常用近似见规范；这里给出严格的 2/3·p?
    严格: w_eq = p·(2/3)? Mmax_tri=pL²/12, w_eq=8/12·p=2/3·p。返回 2/3·p。
    """
    return 2.0 / 3.0 * p_peak


def slab_q(dead_kpa, live_kpa, gG=1.3, gQ=1.5):
    """面荷载设计值组合: q = gG·恒 + gQ·活 (kN/m²)。"""
    return gG * dead_kpa + gQ * live_kpa
