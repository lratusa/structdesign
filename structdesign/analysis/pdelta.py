"""
P-Δ 二阶效应与屈曲分析（几何刚度法）。

轴向压力会降低构件抗弯刚度（几何刚度 Kg）。二阶分析：先线性求轴力，再用
(K - Kg) 重解，得到考虑重力在侧移上附加效应的二阶内力——高层抗震必需。

验证：屈曲临界荷载收敛到欧拉解 Pcr=π²EI/(μL)²（铰接 μ=1，悬臂 μ=2）。
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict
import numpy as np

from .frame2d import _transform, _elem_length_angle, FrameModel, solve
from .frame_modal import assemble_K


def _local_kg(P, L):
    """几何刚度阵（局部，压为正 P）。仅横向/转角自由度。"""
    c = P / L
    return c * np.array([
        [0, 0, 0, 0, 0, 0],
        [0, 6/5, L/10, 0, -6/5, L/10],
        [0, L/10, 2*L**2/15, 0, -L/10, -L**2/30],
        [0, 0, 0, 0, 0, 0],
        [0, -6/5, -L/10, 0, 6/5, -L/10],
        [0, L/10, -L**2/30, 0, -L/10, 2*L**2/15],
    ], dtype=float)


def assemble_KG(model: FrameModel, axial: Dict[str, float]):
    """几何刚度阵装配。axial[mid]=该构件轴力(压为正, N)。"""
    nodes = model.nodes
    node_ids = list(nodes.keys())
    idx = {nid: i for i, nid in enumerate(node_ids)}
    ndof = 3 * len(node_ids)
    KG = np.zeros((ndof, ndof))
    for m in model.members.values():
        L, c, s = _elem_length_angle(m, nodes)
        kgl = _local_kg(axial.get(m.id, 0.0), L)
        T = _transform(c, s)
        kgg = T.T @ kgl @ T
        dofs = []
        for nid in (m.ni, m.nj):
            b = 3 * idx[nid]
            dofs += [b, b + 1, b + 2]
        for a in range(6):
            for bb in range(6):
                KG[dofs[a], dofs[bb]] += kgg[a, bb]
    return KG, idx


def _free_dofs(model, idx):
    fixed = set()
    for nid, n in model.nodes.items():
        b = 3 * idx[nid]
        for k, r in enumerate(n.restraint):
            if r:
                fixed.add(b + k)
    return [d for d in range(3 * len(model.nodes)) if d not in fixed]


def buckling_factor(model: FrameModel) -> float:
    """线性屈曲：返回参考荷载的临界放大系数 λcr（最小正特征值）。

    线性求轴力 → 几何刚度 → 解 (K - λ Kg)φ=0 → λcr。各构件临界轴力=λcr×当前轴力。
    """
    res = solve(model)
    axial = {mid: r.N_axial for mid, r in res.items()}  # 压为正
    K, idx, _ = assemble_K(model)
    KG, _ = assemble_KG(model, axial)
    free = _free_dofs(model, idx)
    Kff = K[np.ix_(free, free)]
    KGff = KG[np.ix_(free, free)]
    # (K - λ KG)φ=0 → 标准特征值 inv(K)·KG 的特征值 μ=1/λ
    A = np.linalg.solve(Kff, KGff)
    mu = np.linalg.eigvals(A)
    mu = np.real(mu[np.abs(np.imag(mu)) < 1e-6])
    pos = mu[mu > 1e-9]
    if len(pos) == 0:
        return float("inf")
    return float(1.0 / np.max(pos))


def second_order_solve(model: FrameModel):
    """二阶分析：用本模型线性轴力建几何刚度 → (K-Kg) 重解。"""
    res1 = solve(model)
    axial = {mid: r.N_axial for mid, r in res1.items()}
    return solve_with_geometric(model, axial)


def solve_with_geometric(model: FrameModel, axial: Dict[str, float]):
    """用**外部给定轴力** axial(压为正) 构造几何刚度，解 (K-Kg)u=F(本模型荷载)。

    用于 P-Δ：把重力产生的轴力作为几何刚度施加到地震(侧向)工况上，
    得到考虑重力-侧移耦合的二阶地震内力。
    """
    K, idx, _ = assemble_K(model)
    KG, _ = assemble_KG(model, axial)
    from .frame2d import _local_k, _transform as _T, _elem_length_angle as _ela
    nodes = model.nodes
    ndof = 3 * len(nodes)
    F = np.zeros(ndof)
    # 固端力 + 节点荷载（复用 solve 的等效，再叠加）——简化：用线性解的等效荷载
    # 这里直接对位移做修正：F 来自原模型
    node_ids = list(nodes.keys())
    idx2 = {nid: i for i, nid in enumerate(node_ids)}
    # 重新装配 F（节点荷载 + 均布固端力）
    fef_store = {}
    from .frame2d import _fef_local
    for m in model.members.values():
        L, c, s = _ela(m, nodes)
        fl, wy = _fef_local(m.w, c, s, L)
        T = _T(c, s)
        fg = T.T @ fl
        dofs = []
        for nid in (m.ni, m.nj):
            b = 3 * idx2[nid]
            dofs += [b, b + 1, b + 2]
        for a in range(6):
            F[dofs[a]] += fg[a]
        fef_store[m.id] = (L, c, s, fl)
    for ld in model.loads:
        b = 3 * idx2[ld.node]
        F[b] += ld.Fx; F[b + 1] += ld.Fy; F[b + 2] += ld.Mz
    Keff = K - KG
    free = _free_dofs(model, idx2)
    U = np.zeros(ndof)
    U[free] = np.linalg.solve(Keff[np.ix_(free, free)], F[free])
    # 杆端力
    out = {}
    from .frame2d import MemberResult
    for m in model.members.values():
        L, c, s, fl = fef_store[m.id]
        T = _T(c, s)
        kl = _local_k(m.E, m.A, m.I, L)
        dofs = []
        for nid in (m.ni, m.nj):
            b = 3 * idx2[nid]
            dofs += [b, b + 1, b + 2]
        ul = T @ U[dofs]
        f_local = kl @ ul - fl
        Ni, Vi, Mi, Nj, Vj, Mj = f_local
        wy = -m.w * c
        M_mid = (Mj - Mi) / 2.0 + (-wy) * L**2 / 8.0
        out[m.id] = MemberResult(Ni, Vi, Mi, Nj, Vj, Mj, M_mid=M_mid, N_axial=Ni)
    return out
