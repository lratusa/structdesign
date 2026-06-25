"""楼板设计：单向/双向板判别 + 弯矩 + 双向配筋 + 板厚校核。

- 长短跨比 Ly/Lx > 2 → 单向板；否则双向板。
- 双向板用 Marcus(Grashof) 简化法分配荷载到两个方向（四边支承，偏安全、无需查表）：
    px = Ly^4/(Lx^4+Ly^4)  → 短跨承担 px；Mx = px·q·Lx²/8, My = (1-px)·q·Ly²/8。
- 每米板带按受弯设计 As；满足最小配筋率 0.15%。板厚按跨高比粗校核。
依据 GB 50010。属方案/初步设计深度，未做弹性楼板有限元/精确边界连续系数。
"""
from __future__ import annotations
import math
from ..project import Slab


def _slab_bars(As_per_m):
    """每米 As(mm²/m) → 直径@间距字符串。"""
    for d in (8, 10, 12, 14):
        a = math.pi * d * d / 4.0
        s = int(a / max(As_per_m, 1e-6) * 1000.0)
        s = min(s, 200) // 10 * 10
        if s >= 100:
            return f"C{d}@{s}", a / (s / 1000.0)
    return "C14@100", math.pi * 14 * 14 / 4.0 / 0.1


def _as_from_M(M_kNm, t):
    h0 = t - 20.0
    As = M_kNm * 1e6 / (0.9 * h0 * 360.0)          # HRB400 fy=360
    return max(As, 0.0)


def design_slab(Lx, Ly, t, q):
    """Lx<=Ly(短/长跨, m)；t 板厚 mm；q 设计面荷载 kN/m²。返回设计字典。"""
    if Lx > Ly:
        Lx, Ly = Ly, Lx
    ratio = Ly / max(Lx, 1e-6)
    one_way = ratio > 2.0
    if one_way:
        Mx = q * Lx ** 2 / 8.0            # 主受力(短跨)跨中
        My = max(Mx * 0.25, q * Lx ** 2 / 24.0)   # 分布筋方向
    else:
        px = Ly ** 4 / (Lx ** 4 + Ly ** 4)
        Mx = px * q * Lx ** 2 / 8.0
        My = (1 - px) * q * Ly ** 2 / 8.0
    As_min = 0.0015 * 1000.0 * t          # 最小配筋率 0.15% 每米
    Asx = max(_as_from_M(Mx, t), As_min)
    Asy = max(_as_from_M(My, t), As_min)
    bx, _ = _slab_bars(Asx)
    by, _ = _slab_bars(Asy)
    # 支座负筋(连续边)：支座弯矩约 1.2×跨中（板面/上部钢筋），伸入跨内约 Ln/4
    Asx_t = max(_as_from_M(Mx * 1.2, t), As_min)
    Asy_t = max(_as_from_M(My * 1.2, t), As_min)
    bxt, _ = _slab_bars(Asx_t)
    byt, _ = _slab_bars(Asy_t)
    # 板厚跨高比粗校核：单向 Lx/30，双向 Lx/40（短跨）
    t_min = Lx * 1000.0 / (30.0 if one_way else 40.0)
    ok = t >= t_min * 0.9
    return dict(kind=("单向板" if one_way else "双向板"),
                Lx=round(Lx, 2), Ly=round(Ly, 2), t=int(t), t_min=int(round(t_min)),
                Mx=round(Mx, 1), My=round(My, 1), Asx=round(Asx), Asy=round(Asy),
                bars_x=bx, bars_y=by, bars_x_top=bxt, bars_y_top=byt,
                Asx_top=round(Asx_t), Asy_top=round(Asy_t), ok=ok)


def auto_slabs(gx, gy, t=120):
    """按轴网各区格自动生成楼板。gx/gy 为排序后的轴线坐标。"""
    gx = sorted(set(gx)); gy = sorted(set(gy))
    out = []
    for i in range(len(gx) - 1):
        for k in range(len(gy) - 1):
            out.append(Slab(gx[i], gy[k], gx[i + 1], gy[k + 1], t))
    return out


def slab_spans(slab):
    """返回 (Lx, Ly) 短/长跨, 单位 m。"""
    a = abs(slab.x2 - slab.x1) / 1000.0
    b = abs(slab.y2 - slab.y1) / 1000.0
    return (min(a, b), max(a, b))
