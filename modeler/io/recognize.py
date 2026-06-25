"""按图层自动识别构件（DWG/DXF 底图 → 柱/墙/梁/轴网）。

策略：先按**图层名关键字**把图层归类为 column/wall/beam/axis/other（可用 overrides 覆盖），
再按几何规则提取：
- 柱：column 层上的闭合矩形 → Column(中心, 宽, 高)；无矩形则取 column 层上的点(默认截面)。
- 墙：wall 层上的**平行线对**(间距≈墙厚) → Wall(中线, t=间距)；落单线按默认厚度。
- 梁：beam 层上的线 → Beam(默认截面)。
- 轴网：axis 层上的竖线 x 集合 + 横线 y 集合（近邻合并）。

诚实边界：纯几何/图层启发式，复杂底图(填充柱、文字标注柱、斜墙、弧梁)可能漏识/误识；
返回 report(图层归类 + 各类数量 + 未归类图层) 供人工用 overrides 修正后重识别。
"""
from __future__ import annotations
import math
from ..project import Column, Beam, Wall, StandardFloor, Grid

LAYER_KEYWORDS = {
    "column": ["柱", "KZ", "COL", "框柱", "GZ"],
    "wall":   ["墙", "WALL", "SHEAR", "剪力墙", "JLQ"],
    "beam":   ["梁", "BEAM", "KL", "框梁", "WKL", "LL"],
    "axis":   ["轴", "AXIS", "GRID", "DOTE", "中心线", "PUB_DIM"],
}


def classify_layer(name: str, overrides: dict = None) -> str:
    if overrides and name in overrides:
        return overrides[name]
    up = name.upper()
    for role, kws in LAYER_KEYWORDS.items():
        for kw in kws:
            k = kw.upper()
            if (k.isascii() and k in up) or (not kw.isascii() and kw in name):
                return role
    return "other"


def _ang(l):
    return math.atan2(l[3] - l[1], l[2] - l[0]) % math.pi


def _len(l):
    return ((l[2] - l[0]) ** 2 + (l[3] - l[1]) ** 2) ** 0.5


def _parallel(a, b, tol=0.05):
    da = abs(_ang(a) - _ang(b))
    return da < tol or abs(da - math.pi) < tol


def _perp_dist(a, b):
    """b 中点到直线 a 的垂距。"""
    x0, y0 = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
    dx, dy = a[2] - a[0], a[3] - a[1]
    L = math.hypot(dx, dy) or 1.0
    return abs((x0 - a[0]) * dy - (y0 - a[1]) * dx) / L


def _overlap(a, b):
    """两平行线投影到 a 方向是否有重叠。"""
    dx, dy = a[2] - a[0], a[3] - a[1]
    L = math.hypot(dx, dy) or 1.0
    ux, uy = dx / L, dy / L
    def proj(px, py):
        return (px - a[0]) * ux + (py - a[1]) * uy
    ta = sorted([proj(a[0], a[1]), proj(a[2], a[3])])
    tb = sorted([proj(b[0], b[1]), proj(b[2], b[3])])
    return min(ta[1], tb[1]) - max(ta[0], tb[0]) > 0.2 * L


def _midline(a, b):
    """两平行线 → 中线(取 a 端点投影到中位)。简化：a、b 对应端点取中点。"""
    # 端点配对：a起点配 b 中较近端
    if math.hypot(b[0] - a[0], b[1] - a[1]) <= math.hypot(b[2] - a[0], b[3] - a[1]):
        p1 = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        p2 = ((a[2] + b[2]) / 2, (a[3] + b[3]) / 2)
    else:
        p1 = ((a[0] + b[2]) / 2, (a[1] + b[3]) / 2)
        p2 = ((a[2] + b[0]) / 2, (a[3] + b[1]) / 2)
    return (p1[0], p1[1], p2[0], p2[1])


def _walls_from_lines(wall_lines, default_t, tmin=60.0, tmax=600.0):
    used = set(); walls = []
    for i, a in enumerate(wall_lines):
        if i in used:
            continue
        best = None
        for j in range(i + 1, len(wall_lines)):
            if j in used:
                continue
            b = wall_lines[j]
            if not _parallel(a, b):
                continue
            d = _perp_dist(a, b)
            if tmin <= d <= tmax and _overlap(a, b):
                if best is None or d < best[1]:
                    best = (j, d)
        if best:
            j, d = best
            used.add(i); used.add(j)
            mx = _midline(a, wall_lines[j])
            walls.append(Wall(mx[0], mx[1], mx[2], mx[3], int(round(d))))
        else:
            used.add(i)
            walls.append(Wall(a[0], a[1], a[2], a[3], int(default_t)))
    return walls


def _merge(vals, tol):
    vals = sorted(vals)
    out = []
    for v in vals:
        if out and abs(v - out[-1]) <= tol:
            continue
        out.append(v)
    return out


def _grid_from_axes(axis_lines, tol):
    xs, ys = [], []
    for (x1, y1, x2, y2) in axis_lines:
        if abs(x2 - x1) < tol and _len((x1, y1, x2, y2)) > tol:      # 竖线
            xs.append(round((x1 + x2) / 2))
        elif abs(y2 - y1) < tol and _len((x1, y1, x2, y2)) > tol:    # 横线
            ys.append(round((y1 + y2) / 2))
    return _merge(xs, tol), _merge(ys, tol)


def recognize(drawing, col_default=(500, 500), wall_t=200, beam_sec=(300, 600),
              merge_tol=150.0, overrides=None):
    """返回 (StandardFloor, Grid, report)。"""
    role_of = {ly: classify_layer(ly, overrides) for ly in drawing.layers}

    # 柱：column 层矩形
    cols = []
    for (cx, cy, w, h, ly) in drawing.rects:
        if role_of.get(ly) == "column":
            cols.append(Column(round(cx), round(cy), int(round(w)), int(round(h))))
    if not cols:                                  # 退化：column 层上的点
        for (px, py), ly in zip(drawing.points, drawing.point_layer):
            if role_of.get(ly) == "column":
                cols.append(Column(round(px), round(py), col_default[0], col_default[1]))

    # 墙：wall 层平行线对
    wall_lines = [l for l, ly in zip(drawing.lines, drawing.line_layer) if role_of.get(ly) == "wall"]
    walls = _walls_from_lines(wall_lines, wall_t)

    # 梁：beam 层的线
    beams = [Beam(l[0], l[1], l[2], l[3], beam_sec[0], beam_sec[1])
             for l, ly in zip(drawing.lines, drawing.line_layer) if role_of.get(ly) == "beam"]

    # 轴网：axis 层
    axis_lines = [l for l, ly in zip(drawing.lines, drawing.line_layer) if role_of.get(ly) == "axis"]
    gx, gy = _grid_from_axes(axis_lines, merge_tol)

    fl = StandardFloor(columns=cols, beams=beams, walls=walls)
    report = dict(layers=role_of, n_col=len(cols), n_wall=len(walls), n_beam=len(beams),
                  n_axis_x=len(gx), n_axis_y=len(gy),
                  unclassified=sorted(ly for ly, r in role_of.items() if r == "other"))
    return fl, Grid(gx, gy), report
