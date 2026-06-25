"""板式楼梯(AT 型，双跑)典型详图设计。

输入层高 → 定踏步数/踏步尺寸(踏步高 150~175、踏步宽 ~280)→ 梯板厚(斜长/28)→ 受弯配筋。
产出供出图：剖面(踏步轮廓+梯板+配筋+标注) + 平面(双跑+休息平台) + 说明。
"""
from __future__ import annotations
import math


def _bars_at(As_per_m):
    for d in (10, 12, 14, 16):
        a = math.pi * d * d / 4.0
        s = int(min(a / max(As_per_m, 1e-6) * 1000.0, 200) // 10 * 10)
        if s >= 100:
            return f"C{d}@{s}"
    return "C16@100"


def design_stair(floor_h=3600.0, width=1600.0, going=280.0, riser_target=160.0, live=3.5):
    n = max(2, round(floor_h / riser_target))
    if n % 2:
        n += 1                          # 双跑取偶数
    riser = floor_h / n
    spf = n // 2                        # 每跑踏步数
    flight_run = (spf - 1) * going      # 平台间水平投影(踏步数-1段)
    rise_half = floor_h / 2.0
    incline = math.hypot(flight_run, rise_half)
    t = max(100, int(round(incline / 28.0 / 10.0) * 10))
    w = t / 1000.0 * 25.0 + live + 1.0   # kN/m (自重+活+踏步)
    L = incline / 1000.0
    M = w * L * L / 10.0
    h0 = t - 20.0
    As = M * 1e6 / (0.9 * h0 * 360.0)
    As = max(As, 0.0015 * t * 1000.0)
    return dict(floor_h=round(floor_h), n=n, spf=spf, riser=round(riser), going=int(going),
                width=int(width), flight_run=round(flight_run), incline=round(incline),
                t=t, bars=_bars_at(As), As=round(As))
