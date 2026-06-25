"""
三维模型轴测可视化（等轴测 SVG）。

把 3D 节点投影到 2D 等轴测，画杆系：柱/墙/梁着色；可叠加变形(静力或振型)放大显示。
"""
from __future__ import annotations
import math
from typing import Optional, Dict


def _iso(x, y, z):
    """等轴测投影：屏幕坐标(px向右, py向下)。"""
    cx = math.cos(math.radians(30))
    sx = math.sin(math.radians(30))
    px = (x - y) * cx
    py = (x + y) * sx - z      # z 向上 → 屏幕向上(负)
    return px, py


def model_svg(model, deformed: Optional[Dict[str, list]] = None, mag: float = 0.0,
              title: str = "三维模型") -> str:
    nodes = model.nodes
    # 计算投影范围
    pts = {}
    for nid, n in nodes.items():
        dx = dy = dz = 0.0
        if deformed is not None and nid in deformed:
            d = deformed[nid]
            dx, dy, dz = d[0]*mag, d[1]*mag, d[2]*mag
        pts[nid] = _iso(n.x + dx, n.y + dy, n.z + dz)
    xs = [p[0] for p in pts.values()]; ys = [p[1] for p in pts.values()]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    margin = 40
    span = max(maxx - minx, maxy - miny) or 1
    scale = 620.0 / span
    W = (maxx - minx) * scale + 2*margin
    H = (maxy - miny) * scale + 2*margin + 30

    def sx(px): return (px - minx) * scale + margin
    def sy(py): return (py - miny) * scale + margin + 20

    def color(mid):
        if mid.startswith("Z") and _is_wall(model, mid):
            return ("#b00", 3.0)          # 墙 红粗
        if mid.startswith("Z") or mid.startswith("w"):
            return ("#333", 1.6)          # 柱
        return ("#69c", 0.8)              # 梁

    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.0f}" height="{H:.0f}" '
         f'viewBox="0 0 {W:.0f} {H:.0f}" font-family="sans-serif">',
         f'<rect width="{W:.0f}" height="{H:.0f}" fill="white"/>',
         f'<text x="{margin}" y="18" font-size="14" font-weight="bold">{title}</text>']
    # 先画梁(底层叠放)，后画柱/墙
    members = sorted(model.members.values(), key=lambda m: 0 if m.id.startswith("L") else 1)
    for m in members:
        ni, nj = pts[m.ni], pts[m.nj]
        col, wdt = color(m.id)
        s.append(f'<line x1="{sx(ni[0]):.1f}" y1="{sy(ni[1]):.1f}" '
                 f'x2="{sx(nj[0]):.1f}" y2="{sy(nj[1]):.1f}" stroke="{col}" stroke-width="{wdt}"/>')
    if deformed is not None:
        s.append(f'<text x="{margin}" y="{H-10:.0f}" font-size="11" fill="#555">'
                 f'变形放大 ×{mag:.0f}（红=墙 / 黑=柱 / 蓝=梁）</text>')
    else:
        s.append(f'<text x="{margin}" y="{H-10:.0f}" font-size="11" fill="#555">'
                 f'红=墙 / 黑=柱 / 蓝=梁（等轴测）</text>')
    s.append('</svg>')
    return "\n".join(s)


def _is_wall(model, mid):
    m = model.members[mid]
    # 墙：截面惯性矩远大于一般柱(经验阈值)
    return max(m.Iy, m.Iz) > 5e10


def save_svg(path, **kw):
    with open(path, "w", encoding="utf-8") as f:
        f.write(model_svg(**kw))
    return path
