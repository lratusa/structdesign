"""图纸导入：DXF 直读（ezdxf）/ DWG 经 ODA File Converter 转 DXF 再读（ezdxf.addons.odafc）。

提取 直线 / 点(圆心、POINT) / 闭合矩形 / 图层名 / 范围(bounds)，供画布显示、捕捉与**按图层自动识别构件**。
DWG 需本机装免费 ODA File Converter；未装时 odafc 会抛错，调用方应回退提示用 DXF。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Tuple, Set
import os
import ezdxf


@dataclass
class Drawing:
    lines: List[Tuple[float, float, float, float]] = field(default_factory=list)  # x1,y1,x2,y2
    points: List[Tuple[float, float]] = field(default_factory=list)               # 圆心/点
    layers: Set[str] = field(default_factory=set)
    bounds: Tuple[float, float, float, float] = (0, 0, 0, 0)                       # xmin,ymin,xmax,ymax
    line_layer: List[str] = field(default_factory=list)                           # 与 lines 等长
    rects: List[Tuple[float, float, float, float, str]] = field(default_factory=list)  # 闭合矩形 cx,cy,w,h,layer
    point_layer: List[str] = field(default_factory=list)                          # 与 points 等长

    def snap_points(self) -> List[Tuple[float, float]]:
        """捕捉候选点：所有线端点 + 点。"""
        pts = list(self.points)
        for (x1, y1, x2, y2) in self.lines:
            pts.append((x1, y1)); pts.append((x2, y2))
        return pts


def _maybe_rect(pts, layer, rects):
    """若 pts(闭合)近似为轴对齐矩形(3~5点)，记入 rects。"""
    p = pts[:-1] if len(pts) >= 2 and pts[0] == pts[-1] else pts
    if not (3 <= len(p) <= 5):
        return
    xs = [q[0] for q in p]; ys = [q[1] for q in p]
    w = max(xs) - min(xs); h = max(ys) - min(ys)
    if w < 1 or h < 1:
        return
    corners = sum(1 for (qx, qy) in p
                  if (abs(qx - min(xs)) < 0.06 * w or abs(qx - max(xs)) < 0.06 * w)
                  and (abs(qy - min(ys)) < 0.06 * h or abs(qy - max(ys)) < 0.06 * h))
    if corners >= max(3, len(p) - 1):
        rects.append(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, w, h, layer))


def _read_doc(path: str):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".dwg":
        from ezdxf.addons import odafc          # 需 ODA File Converter 可执行文件
        return odafc.readfile(path)
    return ezdxf.readfile(path)


def import_drawing(path: str) -> Drawing:
    doc = _read_doc(path)
    msp = doc.modelspace()
    d = Drawing()
    xs: List[float] = []
    ys: List[float] = []

    def add_line(x1, y1, x2, y2, layer):
        d.lines.append((x1, y1, x2, y2)); d.line_layer.append(layer)
        xs.extend([x1, x2]); ys.extend([y1, y2])

    for e in msp:
        t = e.dxftype()
        layer = e.dxf.layer
        if t == "LINE":
            a, b = e.dxf.start, e.dxf.end
            add_line(a.x, a.y, b.x, b.y, layer); d.layers.add(layer)
        elif t in ("CIRCLE", "POINT"):
            c = e.dxf.center if t == "CIRCLE" else e.dxf.location
            d.points.append((c.x, c.y)); d.point_layer.append(layer); d.layers.add(layer)
            xs.append(c.x); ys.append(c.y)
        elif t == "LWPOLYLINE":
            pts = [(p[0], p[1]) for p in e.get_points()]
            closed = getattr(e, "closed", False)
            if closed and len(pts) > 2:
                _maybe_rect(pts + [pts[0]], layer, d.rects)
                pts = pts + [pts[0]]
            for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
                add_line(x1, y1, x2, y2, layer)
            d.layers.add(layer)
        elif t == "POLYLINE":
            vs = [(v.dxf.location.x, v.dxf.location.y) for v in e.vertices]
            if getattr(e, "is_closed", False) and len(vs) > 2:
                _maybe_rect(vs + [vs[0]], layer, d.rects)
                vs = vs + [vs[0]]
            for (x1, y1), (x2, y2) in zip(vs, vs[1:]):
                add_line(x1, y1, x2, y2, layer)
            d.layers.add(layer)
    if xs:
        d.bounds = (min(xs), min(ys), max(xs), max(ys))
    return d
