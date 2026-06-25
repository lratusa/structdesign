"""
真三维框架有限元 —— 每节点 6 自由度（ux,uy,uz,rx,ry,rz）。

3D 梁柱单元含：轴向(EA)、两方向弯曲(EIy,EIz)、St.Venant 扭转(GJ)。
支持任意空间走向（3D 坐标变换）。这是从 2D 平面跨到工程级三维的基础——
能算双向地震、扭转耦联，以及核心筒翼缘协同（对侧墙肢经楼盖发展轴力偶）。

验证：悬臂双向弯曲 PH³/3EI、扭转 TL/GJ、翼缘组合截面平行轴定理。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Tuple
import numpy as np


@dataclass
class Node3D:
    id: str
    x: float
    y: float
    z: float
    restraint: Tuple[bool, bool, bool, bool, bool, bool] = (False,)*6


@dataclass
class Member3D:
    id: str
    ni: str
    nj: str
    E: float
    G: float
    A: float
    Iy: float
    Iz: float
    J: float


@dataclass
class Load3D:
    node: str
    fx: float = 0.0
    fy: float = 0.0
    fz: float = 0.0
    mx: float = 0.0
    my: float = 0.0
    mz: float = 0.0


def _k_local(E, G, A, Iy, Iz, J, L):
    c1 = E * A / L
    c2 = 12 * E * Iz / L**3
    c3 = 6 * E * Iz / L**2
    c4 = 12 * E * Iy / L**3
    c5 = 6 * E * Iy / L**2
    c6 = G * J / L
    c7 = 4 * E * Iz / L
    c8 = 2 * E * Iz / L
    c9 = 4 * E * Iy / L
    c10 = 2 * E * Iy / L
    k = np.zeros((12, 12))
    ent = {
        (0, 0): c1, (0, 6): -c1,
        (1, 1): c2, (1, 5): c3, (1, 7): -c2, (1, 11): c3,
        (2, 2): c4, (2, 4): -c5, (2, 8): -c4, (2, 10): -c5,
        (3, 3): c6, (3, 9): -c6,
        (4, 4): c9, (4, 8): c5, (4, 10): c10,
        (5, 5): c7, (5, 7): -c3, (5, 11): c8,
        (6, 6): c1,
        (7, 7): c2, (7, 11): -c3,
        (8, 8): c4, (8, 10): c5,
        (9, 9): c6,
        (10, 10): c9,
        (11, 11): c7,
    }
    for (i, j), v in ent.items():
        k[i, j] = v
        k[j, i] = v
    return k


def _rotation(ni: Node3D, nj: Node3D):
    dx, dy, dz = nj.x - ni.x, nj.y - ni.y, nj.z - ni.z
    L = (dx*dx + dy*dy + dz*dz) ** 0.5
    x = np.array([dx, dy, dz]) / L
    up = np.array([0.0, 0.0, 1.0])
    if abs(x @ up) > 0.999:           # 构件竖直 → 换参考向量
        up = np.array([0.0, 1.0, 0.0])
    z = np.cross(x, up); z /= np.linalg.norm(z)
    y = np.cross(z, x)
    R = np.vstack([x, y, z])          # 行=局部轴(全局坐标)
    return R, L


def _transform(R):
    T = np.zeros((12, 12))
    for b in range(4):
        T[3*b:3*b+3, 3*b:3*b+3] = R
    return T


@dataclass
class Frame3D:
    nodes: Dict[str, Node3D] = field(default_factory=dict)
    members: Dict[str, Member3D] = field(default_factory=dict)
    loads: List[Load3D] = field(default_factory=list)

    def add_node(self, n): self.nodes[n.id] = n; return self
    def add_member(self, m): self.members[m.id] = m; return self
    def add_load(self, l): self.loads.append(l); return self


def solve(model: Frame3D):
    """返回 (U_dict, idx)。U_dict[node]=长度6数组(ux,uy,uz,rx,ry,rz)。"""
    nodes = model.nodes
    node_ids = list(nodes.keys())
    idx = {nid: i for i, nid in enumerate(node_ids)}
    ndof = 6 * len(node_ids)
    K = np.zeros((ndof, ndof))
    for m in model.members.values():
        ni, nj = nodes[m.ni], nodes[m.nj]
        R, L = _rotation(ni, nj)
        kl = _k_local(m.E, m.G, m.A, m.Iy, m.Iz, m.J, L)
        T = _transform(R)
        kg = T.T @ kl @ T
        dofs = list(range(6*idx[m.ni], 6*idx[m.ni]+6)) + list(range(6*idx[m.nj], 6*idx[m.nj]+6))
        for a in range(12):
            for b in range(12):
                K[dofs[a], dofs[b]] += kg[a, b]
    F = np.zeros(ndof)
    for ld in model.loads:
        b = 6 * idx[ld.node]
        F[b:b+6] += [ld.fx, ld.fy, ld.fz, ld.mx, ld.my, ld.mz]
    fixed = set()
    for nid, n in nodes.items():
        b = 6 * idx[nid]
        for k, r in enumerate(n.restraint):
            if r:
                fixed.add(b + k)
    free = [d for d in range(ndof) if d not in fixed]
    U = np.zeros(ndof)
    if free:
        U[free] = np.linalg.solve(K[np.ix_(free, free)], F[free])
    return {nid: U[6*idx[nid]:6*idx[nid]+6] for nid in node_ids}, idx


def member_forces(model: Frame3D):
    """求解并返回各构件局部杆端力。

    返回 {mid: dict(N, Vy, Vz, T, My, Mz)}，取两端绝对值较大者(设计用)。
    局部分量顺序: [N,Vy,Vz,T,My,Mz]_i, [..]_j。N 压为正。
    """
    U, idx = solve(model)
    out = {}
    for m in model.members.values():
        ni, nj = model.nodes[m.ni], model.nodes[m.nj]
        R, L = _rotation(ni, nj)
        kl = _k_local(m.E, m.G, m.A, m.Iy, m.Iz, m.J, L)
        T = _transform(R)
        ug = np.concatenate([U[m.ni], U[m.nj]])
        fl = kl @ (T @ ug)
        Ni, Vyi, Vzi, Ti, Myi, Mzi, Nj, Vyj, Vzj, Tj, Myj, Mzj = fl
        out[m.id] = dict(
            N=Ni,                       # 压为正(局部x正为拉→ Ni 取号)
            Vy=max(abs(Vyi), abs(Vyj)),
            Vz=max(abs(Vzi), abs(Vzj)),
            T=max(abs(Ti), abs(Tj)),
            My=max(abs(Myi), abs(Myj)),   # 绕局部y弯矩
            Mz=max(abs(Mzi), abs(Mzj)),   # 绕局部z弯矩
        )
    return out


def rigid_link(E=2e5, A=1e8, I=1e12, J=1e12, G=8e4):
    """返回一个"近似刚性"连杆的材料/截面参数(很大刚度)，用于楼盖刚接耦合。"""
    return dict(E=E, G=G, A=A, Iy=I, Iz=I, J=J)
