"""
2D 杆系有限元（直接刚度法）—— 内置默认分析引擎。

支持：梁柱框架单元(轴向+弯曲)、节点约束、节点荷载、单元均布荷载(全局方向)。
求解节点位移与单元杆端力（含跨中弯矩）。可用经典解析解验证（wL²/8、wL²/12）。

这是 L3 分析层的内置实现。截面变化(EI/EA 变)会改变刚度→内力重分布，
使外层闭环(墙肢/截面生长→重分析)成立。外部引擎(ETABS/YJK)可经 solver.Analyzer 替换。
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
import numpy as np


@dataclass
class Node:
    id: str
    x: float
    y: float
    # 约束: True=固定该自由度。顺序 (ux, uy, rz)
    restraint: Tuple[bool, bool, bool] = (False, False, False)


@dataclass
class Member:
    id: str
    ni: str
    nj: str
    E: float          # 弹性模量 N/mm²
    A: float          # 截面面积 mm²
    I: float          # 惯性矩 mm⁴
    w: float = 0.0    # 全局 -Y 方向均布荷载 (N/mm)，重力为正


@dataclass
class NodalLoad:
    node: str
    Fx: float = 0.0   # N
    Fy: float = 0.0   # N (向上为正)
    Mz: float = 0.0   # N·mm


@dataclass
class MemberResult:
    Ni: float; Vi: float; Mi: float    # i 端 轴力/剪力/弯矩 (局部)
    Nj: float; Vj: float; Mj: float    # j 端
    M_mid: float                        # 跨中弯矩(含均布)
    N_axial: float                      # 轴力(压为正)


@dataclass
class FrameModel:
    nodes: Dict[str, Node] = field(default_factory=dict)
    members: Dict[str, Member] = field(default_factory=dict)
    loads: List[NodalLoad] = field(default_factory=list)

    def add_node(self, n: Node): self.nodes[n.id] = n; return self
    def add_member(self, m: Member): self.members[m.id] = m; return self
    def add_load(self, l: NodalLoad): self.loads.append(l); return self


def _elem_length_angle(m: Member, nodes):
    ni, nj = nodes[m.ni], nodes[m.nj]
    dx, dy = nj.x - ni.x, nj.y - ni.y
    L = math.hypot(dx, dy)
    return L, dx / L, dy / L  # L, c, s


def _local_k(E, A, I, L):
    EA_L = E * A / L
    EI = E * I
    k = np.array([
        [EA_L, 0, 0, -EA_L, 0, 0],
        [0, 12*EI/L**3, 6*EI/L**2, 0, -12*EI/L**3, 6*EI/L**2],
        [0, 6*EI/L**2, 4*EI/L, 0, -6*EI/L**2, 2*EI/L],
        [-EA_L, 0, 0, EA_L, 0, 0],
        [0, -12*EI/L**3, -6*EI/L**2, 0, 12*EI/L**3, -6*EI/L**2],
        [0, 6*EI/L**2, 2*EI/L, 0, -6*EI/L**2, 4*EI/L],
    ], dtype=float)
    return k


def _transform(c, s):
    T = np.zeros((6, 6))
    R = np.array([[c, s, 0], [-s, c, 0], [0, 0, 1]])
    T[0:3, 0:3] = R
    T[3:6, 3:6] = R
    return T


def _fef_local(w, c, s, L):
    """全局 -Y 均布荷载 w(N/mm) 的局部固端力向量(6,)。
    局部垂直分量 wy_local = -w·(投影)，这里把 w 视为全局 -Y。
    局部 y 轴方向(由 c,s 旋转): 全局到局部, w 全局向量=(0,-w)。
    局部分量: wx_l = (0)*c+(-w)*s = -w·s ; wy_l = -(0)*s+(-w)*c = -w·c
    """
    wx_l = -w * s     # 轴向分量
    wy_l = -w * c     # 横向分量(局部y)
    # 横向均布的固端力(局部): 剪力 wy_l*L/2, 弯矩 wy_l*L²/12
    f = np.array([
        wx_l * L / 2,
        wy_l * L / 2,
        wy_l * L**2 / 12,
        wx_l * L / 2,
        wy_l * L / 2,
        -wy_l * L**2 / 12,
    ], dtype=float)
    return f, wy_l


def solve(model: FrameModel) -> Dict[str, MemberResult]:
    nodes = model.nodes
    node_ids = list(nodes.keys())
    idx = {nid: i for i, nid in enumerate(node_ids)}
    ndof = 3 * len(node_ids)
    K = np.zeros((ndof, ndof))
    F = np.zeros(ndof)

    # 单元装配 + 固端力等效节点荷载
    fef_store = {}
    for m in model.members.values():
        L, c, s = _elem_length_angle(m, nodes)
        kl = _local_k(m.E, m.A, m.I, L)
        T = _transform(c, s)
        kg = T.T @ kl @ T
        dofs = []
        for nid in (m.ni, m.nj):
            b = 3 * idx[nid]
            dofs += [b, b+1, b+2]
        for a in range(6):
            for bb in range(6):
                K[dofs[a], dofs[bb]] += kg[a, bb]
        # 等效节点荷载（重力沿全局 -Y，向下）
        fl, wy_l = _fef_local(m.w, c, s, L)
        fg = T.T @ fl
        for a in range(6):
            F[dofs[a]] += fg[a]
        fef_store[m.id] = (L, c, s, fl, wy_l)

    # 节点荷载
    for ld in model.loads:
        b = 3 * idx[ld.node]
        F[b] += ld.Fx
        F[b+1] += ld.Fy
        F[b+2] += ld.Mz

    # 约束
    fixed = []
    for nid, n in nodes.items():
        b = 3 * idx[nid]
        for k2, r in enumerate(n.restraint):
            if r:
                fixed.append(b + k2)
    free = [d for d in range(ndof) if d not in fixed]

    U = np.zeros(ndof)
    if free:
        Kff = K[np.ix_(free, free)]
        Ff = F[free]
        U[free] = np.linalg.solve(Kff, Ff)

    # 单元杆端力
    results = {}
    for m in model.members.values():
        L, c, s, fl, wy_l = fef_store[m.id]
        T = _transform(c, s)
        kl = _local_k(m.E, m.A, m.I, L)
        dofs = []
        for nid in (m.ni, m.nj):
            b = 3 * idx[nid]
            dofs += [b, b+1, b+2]
        ug = U[dofs]
        ul = T @ ug
        f_local = kl @ ul - fl   # 杆端力 = k·u - 等效节点荷载
        Ni, Vi, Mi, Nj, Vj, Mj = f_local
        # 跨中弯矩：端弯矩线性插值 + 均布 wL²/8 抛物线增量
        M_mid = (Mj - Mi) / 2.0 + (-wy_l) * L**2 / 8.0
        N_axial = Ni  # 压为正
        results[m.id] = MemberResult(Ni, Vi, Mi, Nj, Vj, Mj,
                                     M_mid=M_mid, N_axial=N_axial)
    return results
