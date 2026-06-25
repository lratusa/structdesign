"""
三维刚性楼盖模态分析 —— 每层 3 个自由度 (UX, UY, RZ)。

楼盖平面内刚性：层内各节点的 ux,uy,rz 由楼层主自由度(UX,UY,RZ)按刚体关系约束；
节点 uz,rx,ry 为独立次自由度，做 Guyan 凝聚。解广义特征值得三维振型——
天然包含 X/Y 平动与**扭转**振型，从而可算**周期比 Tt/T1**（规范强制 ≤0.9）。

验证：对称结构 → Tx≈Ty、扭转振型独立；偏心 → 扭转与平动耦联、周期比上升。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List
import numpy as np

from .frame3d import Frame3D, _k_local, _rotation, _transform


def _assemble_K(model: Frame3D):
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
        d = list(range(6*idx[m.ni], 6*idx[m.ni]+6)) + list(range(6*idx[m.nj], 6*idx[m.nj]+6))
        for a in range(12):
            for b in range(12):
                K[d[a], d[b]] += kg[a, b]
    return K, idx, node_ids


@dataclass
class Mode3D:
    period: float
    kind: str          # 'X','Y','扭转'
    ux: float; uy: float; rz_norm: float


@dataclass
class Modal3DResult:
    modes: List[Mode3D]
    T1: float
    Tx: float
    Ty: float
    Tt: float          # 第一扭转周期
    period_ratio: float  # Tt/T1
    floors: List[float]
    # 供 3D 反应谱逐振型用的内部量
    periods_all: list = None       # 各阶周期(与 modes_dyn 列对应)
    gamma_x: list = None           # 各阶 X 向参与系数
    gamma_y: list = None           # 各阶 Y 向参与系数
    modes_dyn: object = None       # 缩减动力自由度振型矩阵(列=各阶)
    Mdd: object = None             # 缩减动力质量阵
    dyn_red: dict = None           # (类型,楼层)->缩减振型中的行号
    floor_nodes: dict = None       # 楼层->节点列表


def flexible_diaphragm_periods(model: Frame3D, floor_mass: Dict[float, float], n: int = 6):
    """**柔性/半刚性楼盖**自振周期（不施加平面内刚性约束）。

    把楼层质量分摊到各节点 ux,uy 自由度，对无质量自由度做 Guyan 静力凝聚后解特征值，
    得到楼盖**完全柔性**下的周期。与刚性楼盖结果构成上下界：刚性=平面内全约束(刚度上限,
    周期下限)，柔性=无平面内约束(周期上限)；真实半刚性楼盖介于两者之间。
    守恒/验证：刚性楼盖是柔性的**带约束子空间** → T_flex ≥ T_rigid（加约束必升频降周期）。
    """
    K, idx, node_ids = _assemble_K(model)
    nodes = model.nodes
    ndof = 6 * len(node_ids)
    fixed = set()
    for nid, nd in nodes.items():
        b = 6 * idx[nid]
        for k, r in enumerate(nd.restraint):
            if r:
                fixed.add(b + k)
    free = [d for d in range(ndof) if d not in fixed]
    floors = sorted({round(nd.z, 3) for nd in nodes.values() if nd.z > 1e-6})
    fnodes = {f: [nid for nid, nd in nodes.items() if abs(nd.z - f) < 1e-3] for f in floors}
    Mvec = np.zeros(ndof)
    for f in floors:
        per = floor_mass[f] / len(fnodes[f])
        for nid in fnodes[f]:
            b = 6 * idx[nid]
            Mvec[b + 0] += per; Mvec[b + 1] += per
    fpos = {d: i for i, d in enumerate(free)}
    dyn = [d for d in free if Mvec[d] > 0]
    sta = [d for d in free if Mvec[d] <= 0]
    if not dyn:
        return []
    Kff = K[np.ix_(free, free)]
    di = [fpos[d] for d in dyn]; si = [fpos[d] for d in sta]
    Kdd = Kff[np.ix_(di, di)]
    try:
        if si:
            Kds = Kff[np.ix_(di, si)]; Kss = Kff[np.ix_(si, si)]; Ksd = Kff[np.ix_(si, di)]
            Kdd = Kdd - Kds @ np.linalg.solve(Kss, Ksd)
        Kdd = 0.5 * (Kdd + Kdd.T) * 1000.0
        Mdd = np.diag([Mvec[d] for d in dyn])
        Lc = np.linalg.cholesky(Mdd); Linv = np.linalg.inv(Lc)
        C = Linv @ Kdd @ Linv.T; C = 0.5 * (C + C.T)
        w2 = np.linalg.eigvalsh(C)
    except np.linalg.LinAlgError:
        return []
    w2 = np.sort(w2[w2 > 1e-9])
    periods = [2 * np.pi / np.sqrt(w) for w in w2]    # 升序 w2 → 降序周期(最长在前)
    return periods[:n]


def rigid_diaphragm_modal(model: Frame3D, floor_mass: Dict[float, float]) -> Modal3DResult:
    """floor_mass: {z标高: 该层平动质量(kg)}。"""
    K, idx, node_ids = _assemble_K(model)
    nodes = model.nodes
    ndof = 6 * len(node_ids)

    # 固定自由度(基础)
    fixed = set()
    for nid, n in nodes.items():
        b = 6 * idx[nid]
        for k, r in enumerate(n.restraint):
            if r:
                fixed.add(b + k)

    # 楼层(z>0)与质心
    floors = sorted({round(n.z, 3) for n in nodes.values() if n.z > 1e-6})
    floor_nodes = {f: [nid for nid, n in nodes.items() if abs(n.z - f) < 1e-3] for f in floors}
    centroid = {f: (np.mean([nodes[k].x for k in floor_nodes[f]]),
                    np.mean([nodes[k].y for k in floor_nodes[f]])) for f in floors}

    # 缩减自由度编号：每层 UX,UY,RZ；每个自由节点 uz,rx,ry
    red = {}
    rid = 0
    for f in floors:
        red[("UX", f)] = rid; red[("UY", f)] = rid+1; red[("RZ", f)] = rid+2; rid += 3
    free_nodes = [nid for nid in node_ids if nodes[nid].z > 1e-6]
    for nid in free_nodes:
        red[("uz", nid)] = rid; red[("rx", nid)] = rid+1; red[("ry", nid)] = rid+2; rid += 3
    nred = rid

    # 约束矩阵 A: 全自由度(6N) → 缩减
    A = np.zeros((ndof, nred))
    for nid in node_ids:
        n = nodes[nid]
        b = 6 * idx[nid]
        if n.z <= 1e-6:
            continue  # 基础固定，位移0
        f = round(n.z, 3)
        xc, yc = centroid[f]
        # ux = UX - (y-yc)RZ ; uy = UY + (x-xc)RZ ; rz = RZ
        A[b+0, red[("UX", f)]] = 1.0
        A[b+0, red[("RZ", f)]] = -(n.y - yc)
        A[b+1, red[("UY", f)]] = 1.0
        A[b+1, red[("RZ", f)]] = (n.x - xc)
        A[b+5, red[("RZ", f)]] = 1.0
        A[b+2, red[("uz", nid)]] = 1.0
        A[b+3, red[("rx", nid)]] = 1.0
        A[b+4, red[("ry", nid)]] = 1.0

    Kr = A.T @ K @ A

    # 质量(全自由度)：水平质量分摊到层内节点 ux,uy
    M = np.zeros(ndof)
    for f in floors:
        per = floor_mass[f] / len(floor_nodes[f])
        for nid in floor_nodes[f]:
            b = 6 * idx[nid]
            M[b+0] += per; M[b+1] += per
    Mr = A.T @ np.diag(M) @ A

    # 动力自由度(有质量) = 各层 UX,UY,RZ；其余(uz,rx,ry)凝聚
    dyn = [red[("UX", f)] for f in floors] + [red[("UY", f)] for f in floors] + [red[("RZ", f)] for f in floors]
    dyn = sorted(dyn)
    sta = [d for d in range(nred) if d not in set(dyn)]
    Kdd = Kr[np.ix_(dyn, dyn)]
    if sta:
        Kds = Kr[np.ix_(dyn, sta)]; Kss = Kr[np.ix_(sta, sta)]; Ksd = Kr[np.ix_(sta, dyn)]
        Kdd = Kdd - Kds @ np.linalg.solve(Kss, Ksd)
    Mdd = Mr[np.ix_(dyn, dyn)]
    Kdd = Kdd * 1000.0    # 刚度 N/mm → N/m，配合质量 kg 得 SI 圆频率

    # 广义特征值：本问题对称正定，用 Cholesky→eigh 解对称广义特征问题，
    # 对**简并子空间给良态正交基**（非对称 np.linalg.eig 在简并处会返回病态、近平行的
    # 特征向量，使后续 X/Y 旋转无法分离——这是对称楼 X/Y 不分的根因）。
    # 非简并结果与 eig 一致；故设计主链数值不变，仅简并条件数改善。
    Kdd = 0.5 * (Kdd + Kdd.T)
    Mdd = 0.5 * (Mdd + Mdd.T)
    try:
        L = np.linalg.cholesky(Mdd)
        Linv = np.linalg.inv(L)
        C = Linv @ Kdd @ Linv.T
        C = 0.5 * (C + C.T)
        w2, Y = np.linalg.eigh(C)        # 升序、标准正交
        vecs = Linv.T @ Y                # 反变换 → M-正交归一振型
    except np.linalg.LinAlgError:        # 质量阵非正定等极端情形：回退旧解法
        w2, vecs = np.linalg.eig(np.linalg.solve(Mdd, Kdd))
        w2 = np.real(w2); vecs = np.real(vecs)
    order = np.argsort(w2)
    w2 = w2[order]; vecs = vecs[:, order]

    # 简并振型子空间正交化：近简并的成对振型按 X/Y 参与系数旋转对齐，
    # 使完全对称结构的平动振型干净分到 X、Y（消除任意线性组合）。
    dyn_idx0 = {d: i for i, d in enumerate(dyn)}
    rx0 = np.zeros(len(dyn)); ry0 = np.zeros(len(dyn))
    for f in floors:
        rx0[dyn_idx0[red[("UX", f)]]] = 1.0
        ry0[dyn_idx0[red[("UY", f)]]] = 1.0
    import math as _m
    k = 0
    while k < len(w2):
        g = k
        while g + 1 < len(w2) and abs(w2[g+1] - w2[k]) <= 0.02 * max(abs(w2[k]), 1.0):
            g += 1
        if g == k + 1:   # 成对简并 → 先 M-正交归一，再旋转使模态1纯X、模态2纯Y
            p1, p2 = vecs[:, k].copy(), vecs[:, g].copy()
            p1 = p1 / _m.sqrt(max(p1 @ (Mdd @ p1), 1e-30))
            p2 = p2 - (p2 @ (Mdd @ p1)) * p1        # M-正交于 p1
            p2 = p2 / _m.sqrt(max(p2 @ (Mdd @ p2), 1e-30))
            ay = np.array([p1 @ (Mdd @ ry0), p2 @ (Mdd @ ry0)])
            theta = _m.atan2(-ay[0], ay[1])         # 使模态1的 Y 参与=0
            c, s = _m.cos(theta), _m.sin(theta)
            vecs[:, k] = c * p1 + s * p2
            vecs[:, g] = -s * p1 + c * p2
        k = g + 1

    dyn_index = {d: i for i, d in enumerate(dyn)}
    # 特征半径(把转角折算成可比位移量级)
    allx = [n.x for n in nodes.values()]; ally = [n.y for n in nodes.values()]
    R = 0.5 * ((max(allx)-min(allx))**2 + (max(ally)-min(ally))**2) ** 0.5
    R = max(R, 1.0)
    modes = []
    for j in range(len(w2)):
        if w2[j] <= 1e-9:
            continue
        T = 2*np.pi/np.sqrt(w2[j])
        phi = vecs[:, j]
        sx = sum(abs(phi[dyn_index[red[("UX", f)]]]) for f in floors)
        sy = sum(abs(phi[dyn_index[red[("UY", f)]]]) for f in floors)
        st = sum(abs(phi[dyn_index[red[("RZ", f)]]]) for f in floors) * R
        trans = (sx**2 + sy**2) ** 0.5
        if st > trans:
            kind = "扭转"
        else:
            kind = "X" if sx >= sy else "Y"
        modes.append(Mode3D(period=T, kind=kind, ux=sx, uy=sy, rz_norm=st))
    modes.sort(key=lambda m: -m.period)
    T1 = modes[0].period if modes else 0.0
    trans_modes = [m for m in modes if m.kind != "扭转"]
    tors_modes = [m for m in modes if m.kind == "扭转"]
    Tt = tors_modes[0].period if tors_modes else 0.0
    Tx = trans_modes[0].period if trans_modes else 0.0
    Ty = trans_modes[1].period if len(trans_modes) > 1 else Tx
    pr = Tt / T1 if T1 > 0 else 0.0

    # 参与系数 γx, γy（缩减动力空间）。dyn_red: (类型,f)->dyn行号
    dyn_red = {}
    for d, i in dyn_index.items():
        for key, rr in red.items():
            if rr == d:
                dyn_red[key] = i
    nmode = vecs.shape[1]
    rx = np.zeros(len(dyn)); ry = np.zeros(len(dyn))
    for f in floors:
        rx[dyn_red[("UX", f)]] = 1.0
        ry[dyn_red[("UY", f)]] = 1.0
    periods_all, gamma_x, gamma_y = [], [], []
    for j in range(nmode):
        phi = vecs[:, j]
        Mphi = Mdd @ phi
        den = phi @ Mphi
        gx = (phi @ (Mdd @ rx)) / den if den != 0 else 0.0
        gy = (phi @ (Mdd @ ry)) / den if den != 0 else 0.0
        T = 2*np.pi/np.sqrt(w2[j]) if w2[j] > 1e-9 else 1e9
        periods_all.append(T); gamma_x.append(gx); gamma_y.append(gy)

    return Modal3DResult(modes=modes, T1=T1, Tx=Tx, Ty=Ty, Tt=Tt,
                         period_ratio=pr, floors=floors,
                         periods_all=periods_all, gamma_x=gamma_x, gamma_y=gamma_y,
                         modes_dyn=vecs, Mdd=Mdd, dyn_red=dyn_red,
                         floor_nodes=floor_nodes)
