"""温度作用（GB 50009-2012 第9章 / GB 50010 第8.1节）—— 方案级等效热荷载。

均匀温差 ΔT 使构件产生热应变 εT=α·ΔT；受周边约束时产生温度内力。
做法（不改求解器）：对**水平构件(梁/楼盖)**施加等效热轴力的节点等效力——
构件自由膨胀会把两端节点沿杆轴向外推，等效力 P=E·A·α·ΔT；FEM 求解即得
温度内力（主要表现为结构端部柱的附加弯矩/剪力，及梁轴力）。

诚实边界：均匀温差、不计混凝土收缩/徐变对温度内力的松弛折减、**未按伸缩缝释放**
（设伸缩缝可显著降低温度效应）、楼盖按杆系等代。重要工程须商业软件 + 专项分析。
"""
from __future__ import annotations

ALPHA_CONC = 1.0e-5   # 混凝土线膨胀系数 /°C


def thermal_node_loads(model, member_ids, dT, alpha=ALPHA_CONC):
    """对 member_ids 指定构件施加均匀温差 dT(°C) 的等效节点力，返回 list[Load3D]。

    P = E·A·α·ΔT (N)；膨胀方向把端节点沿杆轴外推（ni 受 -P·û，nj 受 +P·û）。"""
    from structdesign.analysis.frame3d import Load3D
    loads = []
    eps = alpha * dT
    for mid in member_ids:
        m = model.members.get(mid)
        if m is None:
            continue
        ni, nj = model.nodes[m.ni], model.nodes[m.nj]
        dx, dy, dz = nj.x - ni.x, nj.y - ni.y, nj.z - ni.z
        L = (dx * dx + dy * dy + dz * dz) ** 0.5
        if L < 1e-9:
            continue
        ux, uy, uz = dx / L, dy / L, dz / L
        P = m.E * m.A * eps                       # N
        loads.append(Load3D(m.ni, fx=-P * ux, fy=-P * uy, fz=-P * uz))
        loads.append(Load3D(m.nj, fx=P * ux, fy=P * uy, fz=P * uz))
    return loads
