"""
真实框架特征值模态分析（替代剪切层近似）。

用真实框架整体刚度阵 K（含梁柱弯曲、梁的柔度），把楼层质量集中到各楼层节点的
水平自由度(主自由度)，对竖向/转角等次自由度做 Guyan 静力凝聚，解广义特征值
得自振周期/振型/参与系数。比剪切层模型更准（不再假定梁刚性）。

验证：刚性梁门式框架 → 退化为 k=Σ12EI/h³，T=2π√(m/k)（解析解）。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict
import numpy as np

from .frame2d import _local_k, _transform, _elem_length_angle, FrameModel


def assemble_K(model: FrameModel):
    nodes = model.nodes
    node_ids = list(nodes.keys())
    idx = {nid: i for i, nid in enumerate(node_ids)}
    ndof = 3 * len(node_ids)
    K = np.zeros((ndof, ndof))
    for m in model.members.values():
        L, c, s = _elem_length_angle(m, nodes)
        kl = _local_k(m.E, m.A, m.I, L)
        T = _transform(c, s)
        kg = T.T @ kl @ T
        dofs = []
        for nid in (m.ni, m.nj):
            b = 3 * idx[nid]
            dofs += [b, b + 1, b + 2]
        for a in range(6):
            for bb in range(6):
                K[dofs[a], dofs[bb]] += kg[a, bb]
    return K, idx, node_ids


@dataclass
class FrameModalResult:
    periods: List[float]
    omegas: List[float]
    modes: np.ndarray             # 主自由度(各楼层节点ux)振型，列为各阶
    gammas: List[float]
    master_dofs: List[int]        # 全局DOF索引(ux)
    master_mass: List[float]
    master_nodes: List[str]       # 主自由度对应节点
    idx: Dict[str, int]
    n_master: int


def frame_modal(model: FrameModel, floor_masses: List[float]) -> FrameModalResult:
    """floor_masses: 自下而上各层总质量(kg)。楼层=y>0 的不同标高。"""
    K, idx, node_ids = assemble_K(model)
    nodes = model.nodes
    ndof = 3 * len(node_ids)

    # 固定自由度
    fixed = set()
    for nid, n in nodes.items():
        b = 3 * idx[nid]
        for k, r in enumerate(n.restraint):
            if r:
                fixed.add(b + k)

    # 楼层标高（基础以上）
    levels = sorted({round(n.y, 3) for n in nodes.values() if n.y > 1e-6})
    assert len(levels) == len(floor_masses), (len(levels), len(floor_masses))

    masters, master_mass, master_nodes = [], [], []
    for j, lev in enumerate(levels):
        lvl_nodes = [nid for nid, n in nodes.items() if abs(n.y - lev) < 1e-3]
        per = floor_masses[j] / len(lvl_nodes)
        for nid in lvl_nodes:
            d = 3 * idx[nid] + 0  # ux
            if d in fixed:
                continue
            masters.append(d)
            master_mass.append(per)
            master_nodes.append(nid)

    all_free = [d for d in range(ndof) if d not in fixed]
    mset = set(masters)
    slaves = [d for d in all_free if d not in mset]

    Kmm = K[np.ix_(masters, masters)]
    if slaves:
        Kms = K[np.ix_(masters, slaves)]
        Ksm = K[np.ix_(slaves, masters)]
        Kss = K[np.ix_(slaves, slaves)]
        Kcond = Kmm - Kms @ np.linalg.solve(Kss, Ksm)
    else:
        Kcond = Kmm

    # 单位换算：刚度阵由 N/mm → N/m（位移用 m，配合质量 kg 得 SI 圆频率 rad/s）
    Kcond = Kcond * 1000.0

    mvec = np.array(master_mass)
    Mcond = np.diag(mvec)
    A = np.linalg.solve(Mcond, Kcond)
    w2, vecs = np.linalg.eig(A)
    w2 = np.real(w2); vecs = np.real(vecs)
    order = np.argsort(w2)
    w2 = w2[order]; vecs = vecs[:, order]
    omegas = np.sqrt(np.clip(w2, 0, None))
    periods = [float(2 * np.pi / w) if w > 1e-9 else float("inf") for w in omegas]

    ones = np.ones(len(masters))
    gammas = []
    for j in range(len(masters)):
        phi = vecs[:, j]
        mx = np.argmax(np.abs(phi))
        if phi[mx] != 0:
            phi = phi / phi[mx]
        vecs[:, j] = phi
        num = phi @ (mvec * ones)
        den = phi @ (mvec * phi)
        gammas.append(float(num / den) if den != 0 else 0.0)

    return FrameModalResult(
        periods=periods, omegas=[float(x) for x in omegas], modes=vecs,
        gammas=gammas, master_dofs=masters, master_mass=master_mass,
        master_nodes=master_nodes, idx=idx, n_master=len(masters))
