"""次梁导算（主/次梁判别 + 次梁荷载传至主梁）。

YJK 区分主梁(KL，两端支于柱)与次梁(L，支于其它梁)。次梁承受板传荷载，其支座反力
以**集中力**形式传给所承托的主梁；主梁设计须计入这些集中力。

判别：梁两端均落柱 → 主梁；否则(至少一端落在其它梁上) → 次梁。
对一键轴网模型(梁均在柱间)全为主梁，本模块为 no-op（向后兼容）。
"""
from __future__ import annotations

TOL = 200.0   # mm 对位容差


def _col_pts(floor):
    return [(c.x, c.y) for c in floor.columns]


def _at_col(x, y, cps):
    return any(abs(x - cx) < TOL and abs(y - cy) < TOL for cx, cy in cps)


def classify_beams(floor):
    """返回 list[str]：每根梁 '主' 或 '次'。"""
    cps = _col_pts(floor)
    out = []
    for b in floor.beams:
        e1 = _at_col(b.x1, b.y1, cps)
        e2 = _at_col(b.x2, b.y2, cps)
        out.append("主" if (e1 and e2) else "次")
    return out


def _t_on_seg(px, py, b):
    """点 (px,py) 是否落在梁 b 跨内(不含端点)；是则返回沿梁的位置比 t∈(0,1)，否则 None。"""
    dx, dy = b.x2 - b.x1, b.y2 - b.y1
    L2 = dx * dx + dy * dy
    if L2 < 1.0:
        return None
    t = ((px - b.x1) * dx + (py - b.y1) * dy) / L2
    if t <= 1e-3 or t >= 1 - 1e-3:
        return None
    projx, projy = b.x1 + t * dx, b.y1 + t * dy
    if (px - projx) ** 2 + (py - projy) ** 2 > TOL * TOL:
        return None
    return t


def secondary_transfer(floor, q, tributary_fn):
    """次梁导算。q=板传面荷载(kN/m²)，tributary_fn(beam)->受荷宽(mm)。

    返回 (kinds, prim_loads)：
      kinds[i]      = '主'/'次'
      prim_loads[i] = [(t, P_kN), ...]  第 i 根主梁上来自次梁的集中力(位置比 t、力 P)。
    """
    kinds = classify_beams(floor)
    prim_loads = {i: [] for i in range(len(floor.beams))}
    for j, b in enumerate(floor.beams):
        if kinds[j] != "次":
            continue
        L = ((b.x2 - b.x1) ** 2 + (b.y2 - b.y1) ** 2) ** 0.5 / 1000.0    # m
        w = q * tributary_fn(b) / 1000.0                                 # kN/m
        R = w * L / 2.0                                                  # 每端反力 kN
        for (ex, ey) in [(b.x1, b.y1), (b.x2, b.y2)]:
            for i, pb in enumerate(floor.beams):
                if i == j or kinds[i] != "主":
                    continue
                t = _t_on_seg(ex, ey, pb)
                if t is not None:
                    prim_loads[i].append((t, R))
                    break
    return kinds, prim_loads
