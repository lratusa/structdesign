"""画布编辑几何运算（纯函数，无 Qt，可 headless 测试）。

支持：平移(move)、复制(copy=平移生成新对象)、镜像(mirror，对称)、矩形阵列(array)、
点选命中(hit_test)、框选(in_box)。对象为 project 的 Column/Beam/Wall。
"""
from __future__ import annotations
import copy
import math


def _is_point(o):
    return hasattr(o, "x")          # Column 有 x,y；Beam/Wall 有 x1..


def move_obj(o, dx, dy):
    n = copy.deepcopy(o)
    if _is_point(n):
        n.x += dx; n.y += dy
    else:
        n.x1 += dx; n.y1 += dy; n.x2 += dx; n.y2 += dy
    return n


def _mirror_pt(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    dd = dx * dx + dy * dy or 1.0
    t = ((px - ax) * dx + (py - ay) * dy) / dd
    fx, fy = ax + t * dx, ay + t * dy
    return 2 * fx - px, 2 * fy - py


def mirror_obj(o, ax, ay, bx, by):
    n = copy.deepcopy(o)
    if _is_point(n):
        n.x, n.y = _mirror_pt(n.x, n.y, ax, ay, bx, by)
    else:
        n.x1, n.y1 = _mirror_pt(n.x1, n.y1, ax, ay, bx, by)
        n.x2, n.y2 = _mirror_pt(n.x2, n.y2, ax, ay, bx, by)
    return n


def array_objs(objs, nx, ny, dx, dy):
    """矩形阵列：nx×ny 份，间距 dx,dy（含原位 i=j=0）。返回新对象列表(不含原位)。"""
    out = []
    for i in range(nx):
        for j in range(ny):
            if i == 0 and j == 0:
                continue
            for o in objs:
                out.append(move_obj(o, i * dx, j * dy))
    return out


def _rep_point(o):
    if _is_point(o):
        return o.x, o.y
    return (o.x1 + o.x2) / 2.0, (o.y1 + o.y2) / 2.0


def _pt_seg_d2(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    dd = dx * dx + dy * dy
    if dd < 1e-9:
        return (px - x1) ** 2 + (py - y1) ** 2
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / dd))
    fx, fy = x1 + t * dx, y1 + t * dy
    return (px - fx) ** 2 + (py - fy) ** 2


def hit_test(floor, x, y, tol):
    """返回最近构件 (kind, idx)；优先 柱/梁/墙，空白处才命中其下的 板。"""
    best, bd = None, tol * tol
    for i, c in enumerate(floor.columns):
        d = max(abs(c.x - x) - c.b / 2, 0) ** 2 + max(abs(c.y - y) - c.h / 2, 0) ** 2
        if d < bd:
            bd = d; best = ("col", i)
    for kind, lst in (("wopen", getattr(floor, "wall_openings", [])),
                      ("beam", floor.beams), ("wall", floor.walls)):
        for i, b in enumerate(lst):
            d = _pt_seg_d2(x, y, b.x1, b.y1, b.x2, b.y2)
            if d < bd:
                bd = d; best = (kind, i)
    if best is not None:
        return best
    # 区域类(点中内部才选)：板洞/楼梯 优先于 板
    for kind, lst in (("open", getattr(floor, "openings", [])),
                      ("stairp", getattr(floor, "stairs_placed", [])),
                      ("slab", getattr(floor, "slabs", []))):
        for i, s in enumerate(lst):
            if min(s.x1, s.x2) <= x <= max(s.x1, s.x2) and min(s.y1, s.y2) <= y <= max(s.y1, s.y2):
                return (kind, i)
    return None


def in_box(floor, x0, y0, x1, y1):
    """框选：代表点落在矩形内的构件 (kind, idx) 列表。"""
    xlo, xhi = min(x0, x1), max(x0, x1)
    ylo, yhi = min(y0, y1), max(y0, y1)
    out = []
    for kind, lst in (("col", floor.columns), ("beam", floor.beams),
                      ("wall", floor.walls), ("slab", getattr(floor, "slabs", [])),
                      ("open", getattr(floor, "openings", [])),
                      ("wopen", getattr(floor, "wall_openings", [])),
                      ("stairp", getattr(floor, "stairs_placed", []))):
        for i, o in enumerate(lst):
            rx, ry = _rep_point(o)
            if xlo <= rx <= xhi and ylo <= ry <= yhi:
                out.append((kind, i))
    return out


def get_obj(floor, kind, idx):
    return {"col": floor.columns, "beam": floor.beams, "wall": floor.walls,
            "slab": floor.slabs, "open": floor.openings, "wopen": floor.wall_openings,
            "stairp": floor.stairs_placed}[kind][idx]
