"""荷载规范辅助（GB 50009-2012）—— 活荷载折减等。

活荷载折减（5.1.2）：设计墙、柱、基础时，其上各层活荷载按总和折减，折减系数
随**计算截面以上的层数 m** 递减（不同时满载）。本表用第1类（住宅/办公/医院/
托幼等，表 5.1.2）。楼面梁折减(5.1.1)按从属面积，另见 beam_live_reduction。
"""
from __future__ import annotations


def live_reduction_vertical(m: int) -> float:
    """竖向构件(墙/柱/基础)活荷载折减系数，m=计算截面以上的层数（GB 50009 表5.1.2，第1类）。"""
    if m <= 1:
        return 1.00
    if m <= 3:
        return 0.85
    if m <= 5:
        return 0.70
    if m <= 8:
        return 0.65
    if m <= 20:
        return 0.60
    return 0.55


def beam_live_reduction(tributary_area_m2: float) -> float:
    """楼面梁活荷载折减系数（GB 50009 5.1.1，第1类）：从属面积 A>25m² 取 0.9，否则 1.0。"""
    return 0.9 if tributary_area_m2 > 25.0 else 1.0
