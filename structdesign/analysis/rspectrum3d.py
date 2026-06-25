"""
三维振型分解反应谱法（逐振型 → 3D 构件内力 → CQC 组合 → 双向）。

对每个振型 j、每个地震方向 d：
  等效惯性力 F_j = α(Tj)·γ_jd·g·[M]·φ_j（缩减楼层空间）→ 还原为 3D 节点荷载
  → 解 3D 杆系得各构件内力 → 对各振型按 CQC 组合 → 两方向按 0.85 规则组合。
得到每构件用于配筋的 (N, My, Mz, V)。
"""
from __future__ import annotations
from typing import Dict, Optional
import numpy as np

from .frame3d import Frame3D, Node3D, Member3D, Load3D, member_forces, _rotation, _k_local, _transform, solve
from .modal3d import rigid_diaphragm_modal
from ..codes import gb50011_spectrum as sp
from ..codes.cqc import cqc
from ..codes.seismic_torsion import bidirectional_combination


def _modal_member_forces(model, r, jmode, dirn, alpha_max, Tg, g=9.81):
    """单振型 jmode、方向 dirn 的等效力 → 全部构件内力。"""
    Tj = r.periods_all[jmode]
    aj = sp.alpha(Tj, alpha_max, Tg)
    gamma = (r.gamma_x if dirn == "x" else r.gamma_y)[jmode]
    phi = r.modes_dyn[:, jmode]
    f_red = aj * gamma * g * (r.Mdd @ phi)      # 缩减楼层力(N / N·mm)

    # 还原为 3D 节点荷载
    loads = []
    for f, nodes_at in r.floor_nodes.items():
        Fx = f_red[r.dyn_red[("UX", f)]]
        Fy = f_red[r.dyn_red[("UY", f)]]
        Mz = f_red[r.dyn_red[("RZ", f)]]
        nper = len(nodes_at)
        for nid in nodes_at:
            loads.append(Load3D(nid, fx=Fx/nper, fy=Fy/nper, mz=Mz/nper))
    # 临时把荷载装上求解
    saved = model.loads
    model.loads = loads
    mf = member_forces(model)
    model.loads = saved
    key = "UX" if dirn == "x" else "UY"   # 基底剪力取对应方向分量
    vb = abs(float(np.sum([f_red[r.dyn_red[(key, f)]] for f in r.floors])))
    return mf, vb


def response_spectrum_3d(model: Frame3D, floor_mass: Dict[float, float],
                         alpha_max: float, Tg: float, zeta: float = 0.05,
                         n_modes: int = 12) -> Dict:
    r = rigid_diaphragm_modal(model, floor_mass)
    nmode = min(n_modes, r.modes_dyn.shape[1])
    comps = ["N", "My", "Mz", "Vy", "Vz"]
    mids = list(model.members.keys())

    design = {mid: {} for mid in mids}
    base = {}
    for dirn in ("x", "y"):
        # 每构件每分量收集各振型响应
        per_mode = {mid: {c: [] for c in comps} for mid in mids}
        periods = []
        base_modes = []
        for j in range(nmode):
            periods.append(r.periods_all[j])
            mf, vb = _modal_member_forces(model, r, j, dirn, alpha_max, Tg)
            base_modes.append(vb)
            for mid in mids:
                for c in comps:
                    per_mode[mid][c].append(mf[mid][c])
        # CQC 组合
        for mid in mids:
            for c in comps:
                design[mid].setdefault(c + "_" + dirn, cqc(per_mode[mid][c], periods, zeta))
        base[dirn] = cqc(base_modes, periods, zeta)

    # 双向 0.85 组合 → 设计内力
    out = {}
    for mid in mids:
        d = design[mid]
        out[mid] = dict(
            My=bidirectional_combination(d["My_x"], d["My_y"]),
            Mz=bidirectional_combination(d["Mz_x"], d["Mz_y"]),
            Vy=bidirectional_combination(d["Vy_x"], d["Vy_y"]),
            Vz=bidirectional_combination(d["Vz_x"], d["Vz_y"]),
            N=max(d["N_x"], d["N_y"]),
        )
    return dict(member_forces=out, base_x=base["x"], base_y=base["y"],
                base_bi=bidirectional_combination(base["x"], base["y"]),
                modal=r, n_modes=nmode)
