"""
规则三维框架生成器 —— 给三维模态/可视化用。

节点 N{i}_{k}_{j}：i=0..nx (X向柱列), k=0..ny (Y向柱列), j=0..nz (层,0=基础)。
柱(竖向) + X向梁 + Y向梁。可选把某些柱列设为剪力墙(大截面)。
"""
from __future__ import annotations
from typing import Optional, Set, Tuple
from .analysis.frame3d import Frame3D, Node3D, Member3D


def section_props(b, h):
    """矩形截面 (A, Iy, Iz, J)。Iz 绕局部z(对应高 h 方向)，Iy 绕局部y。"""
    A = b * h
    Iz = b * h**3 / 12.0
    Iy = h * b**3 / 12.0
    bb, hh = min(b, h), max(b, h)
    J = bb**3 * hh * (1/3 - 0.21*(bb/hh)*(1 - (bb/hh)**4/12))  # St.Venant 矩形
    return A, Iy, Iz, J


def build_regular_3d(nx, ny, nz, bx, by, hz,
                     col_bh=(600, 600), beam_bh=(300, 600),
                     E=3.25e4, G=1.35e4,
                     wall_cols: Optional[Set[Tuple[int, int]]] = None,
                     wall_bh=(400, 3000)) -> Frame3D:
    wall_cols = wall_cols or set()
    m = Frame3D()
    for i in range(nx + 1):
        for k in range(ny + 1):
            for j in range(nz + 1):
                r = (True,)*6 if j == 0 else (False,)*6
                m.add_node(Node3D(f"N{i}_{k}_{j}", i*bx, k*by, j*hz, r))
    Acol, Iyc, Izc, Jc = section_props(*col_bh)
    Aw, Iyw, Izw, Jw = section_props(*wall_bh)
    Ab, Iyb, Izb, Jb = section_props(*beam_bh)
    # 柱/墙
    for i in range(nx + 1):
        for k in range(ny + 1):
            is_wall = (i, k) in wall_cols
            for j in range(nz):
                p = (Aw, Iyw, Izw, Jw) if is_wall else (Acol, Iyc, Izc, Jc)
                m.add_member(Member3D(f"Z{i}_{k}_{j+1}", f"N{i}_{k}_{j}", f"N{i}_{k}_{j+1}",
                                      E, G, p[0], p[1], p[2], p[3]))
    # 梁 X 向
    for j in range(1, nz + 1):
        for k in range(ny + 1):
            for i in range(nx):
                m.add_member(Member3D(f"LX{i}_{k}_{j}", f"N{i}_{k}_{j}", f"N{i+1}_{k}_{j}",
                                      E, G, Ab, Iyb, Izb, Jb))
    # 梁 Y 向
    for j in range(1, nz + 1):
        for i in range(nx + 1):
            for k in range(ny):
                m.add_member(Member3D(f"LY{i}_{k}_{j}", f"N{i}_{k}_{j}", f"N{i}_{k+1}_{j}",
                                      E, G, Ab, Iyb, Izb, Jb))
    return m


def floor_masses(model, mass_per_floor):
    """返回 {z: mass} 给模态用。"""
    zs = sorted({round(n.z, 3) for n in model.nodes.values() if n.z > 1e-6})
    return {z: mass_per_floor for z in zs}
