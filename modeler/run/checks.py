"""各层拼接检验：相邻标准层竖向构件(柱/墙)连续性检查（多塔/大底盘/转换排查）。

上层某处有竖向构件、紧邻下层同位置无支承 → 悬空竖向构件 → 需设转换(转换梁/层)。
首层竖向构件落基础，不算悬空。位置按 TOL 容差比对。
"""
from __future__ import annotations

TOL = 200.0   # mm，竖向构件平面对位容差


def _vkey(x, y):
    return (round(x / TOL), round(y / TOL))


def _vert_points(fl):
    """返回该标准层竖向构件平面点 {key: (x,y,kind)}。"""
    pts = {}
    for c in fl.columns:
        pts[_vkey(c.x, c.y)] = (c.x, c.y, "柱")
    for w in fl.walls:
        mx, my = (w.x1 + w.x2) / 2.0, (w.y1 + w.y2) / 2.0
        pts[_vkey(mx, my)] = (mx, my, "墙")
    return pts


def auto_transfer(project, bw=500):
    """对每个悬空竖向构件，在其下层的两侧支承柱间设**转换梁**(深梁，分两段在悬空点相交，
    形成支承节点)。返回新增转换梁信息；同时改写下层 beams（使模型成立、分析时该梁承托上部荷载）。
    依赖 Beam 类。"""
    from ..project import Beam
    issues = continuity_check(project)
    lf = project.level_floors()
    added = []
    done = set()
    for iss in issues:
        j = iss["level"]; x = iss["x"]; y = iss["y"]
        below = lf[j - 2]
        tag = (round(x), round(y), id(below))
        if tag in done:
            continue
        done.add(tag)
        cols = below.columns

        def find(axis):
            if axis == "x":
                same = [c for c in cols if abs(c.y - y) < 300]
                lo = [c for c in same if c.x < x - 1]; hi = [c for c in same if c.x > x + 1]
                if lo and hi:
                    return max(lo, key=lambda c: c.x), min(hi, key=lambda c: c.x)
            else:
                same = [c for c in cols if abs(c.x - x) < 300]
                lo = [c for c in same if c.y < y - 1]; hi = [c for c in same if c.y > y + 1]
                if lo and hi:
                    return max(lo, key=lambda c: c.y), min(hi, key=lambda c: c.y)
            return None
        sup = find("x") or find("y")
        if not sup:
            continue
        L, R = sup
        span = ((R.x - L.x) ** 2 + (R.y - L.y) ** 2) ** 0.5
        hb = min(max(round(span / 5 / 50) * 50, 700), 2000)   # 转换深梁
        below.beams.append(Beam(L.x, L.y, x, y, bw, hb))
        below.beams.append(Beam(x, y, R.x, R.y, bw, hb))
        added.append(dict(level=j - 1, x=x, y=y, span=round(span), bw=bw, hb=int(hb),
                          msg=f"第{j-1}层 ({int(x)},{int(y)}) 设转换梁 {bw}×{int(hb)}（跨{int(span)}）"))
    return added


def continuity_check(project):
    """返回悬空竖向构件列表：[{level, x, y, kind, msg}]（level 从 2 起）。"""
    lf = project.level_floors()
    issues = []
    for j in range(2, len(lf) + 1):
        cur = _vert_points(lf[j - 1])
        below = _vert_points(lf[j - 2])
        for k, (x, y, kind) in cur.items():
            if k not in below:
                issues.append(dict(level=j, x=x, y=y, kind=kind,
                                   msg=f"第{j}层 ({int(x)},{int(y)}) 处{kind}下层无支承 → 需转换"))
    return issues
