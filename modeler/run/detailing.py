"""配筋构造：箍筋（抗剪 + 加密区）、材料统计辅助。

箍筋记法 "C8@100/200(2)" = φ8，加密区@100 / 非加密区@200，2 肢。
梁箍按抗剪需求选直径/间距 + 加密区(GB 50011 6.3.4)；柱箍取抗震构造(加密区按等级)。
"""
from __future__ import annotations
import math


def beam_stirrup(Asv_s, h, legs=2):
    """Asv_s: 抗剪所需 Asv/s (mm²/mm)；h: 梁高 mm。"""
    for d in (8, 10, 12):
        a = legs * math.pi * d * d / 4.0
        s = a / max(Asv_s, 1e-6)                       # 满足抗剪的最大间距
        s_norm = int(min(s, h / 2.0, 200))
        s_norm = max((s_norm // 25) * 25, 100)
        if s_norm >= 100:
            s_dense = max(min(s_norm, 100, int((h / 4) // 25 * 25)), 75)
            return f"C{d}@{s_dense}/{s_norm}({legs})"
    return f"C12@100/150({legs})"


def col_stirrup(b, grade="二级", d_long=20):
    """柱抗震箍筋构造：加密区间距 min(纵筋系数·d, b/4, 100)，非加密区 min(b,200)。"""
    big = b >= 700
    d = 10 if (grade in ("一级", "二级") or big) else 8
    mult = 6 if grade == "一级" else 8
    s_dense = min(100, mult * d_long, int(b / 4))
    s_dense = max((int(s_dense) // 10) * 10, 80)
    s_norm = max((min(int(b), 200) // 25) * 25, 150)
    return f"C{d}@{s_dense}/{s_norm}"


def beam_dense_len(hb, grade="二级"):
    """梁端箍筋加密区长度 GB 50011 6.3.3：一级 max(2hb,500)；其余 max(1.5hb,500)。"""
    f = 2.0 if grade == "一级" else 1.5
    return round(max(f * hb, 500.0))


def col_dense_len(hc, Hn, grade="二级", bottom=False):
    """柱端箍筋加密区长度 GB 50011 6.3.9：max(hc, Hn/6, 500)；底层柱根另取 Hn/3。"""
    L = max(hc, Hn / 6.0, 500.0)
    if bottom:
        L = max(L, Hn / 3.0)
    return round(L)


_DENS = 7.85e-6   # 钢 kg/mm³ ·1000 → 与项目一致: As(mm²)*len(m)*7.85e-6*1000 = kg


def steel_kg(As_mm2, length_m):
    return As_mm2 * length_m * _DENS * 1000.0
