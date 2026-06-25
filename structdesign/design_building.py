"""
地震工况整榀配筋集成 —— 把全链路串起来。

模态分析→GB50011反应谱→层地震力→灌入整榀框架(水平地震工况)
  + 重力工况 → 荷载组合(含地震) → 能力设计内力调整 → 梁柱配筋。

这是地上结构抗震设计的完整数据流，全部基于内置引擎离线完成。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List

from . import materials
from .analysis.frame2d import FrameModel, Node, Member, NodalLoad, solve
from .analysis.modal import story_stiffness_from_columns
from .analysis.response_spectrum import response_spectrum_analysis
from .frame_builder import build_regular_frame
from .frame_spec import SecBox, FrameSpec
from .loads import CaseForces, envelope, G as GC, E as EC
from .codes import seismic_adjust as sa
from .codes import gb50010_column as gc
from .codes import gb50010_beam as gb


def _model(spec: FrameSpec, gravity: bool, nodal=None) -> FrameModel:
    m = FrameModel()
    for nid, (x, y, r) in spec.nodes.items():
        m.add_node(Node(nid, x, y, r))
    for mid, (ni, nj, sec, w) in spec.members.items():
        m.add_member(Member(mid, ni, nj, sec.E, sec.A, sec.I, w=(w if gravity else 0.0)))
    for ld in (nodal or []):
        m.add_load(ld)
    return m


def _story_stiffnesses(spec, n_bays, n_stories, story_h) -> List[float]:
    ks = []
    for j in range(1, n_stories + 1):
        I_total = sum(spec.members[f"Z{i}_{j}"][2].I for i in range(n_bays + 1))
        E = materials.concrete(spec.members[f"Z0_{j}"][2].concrete).Ec
        ks.append(story_stiffness_from_columns(E, I_total, story_h) * 1000.0)  # N/m
    return ks


@dataclass
class MemberDesign:
    kind: str
    M_gravity: float        # 仅重力下弯矩 (kN·m)
    M_combo: float          # 组合(含地震)设计弯矩 (kN·m)
    M_capacity: float       # 能力设计放大后 (kN·m)
    N: float                # 轴力 (kN)
    As: float               # 配筋 (mm²)
    rho: float = 0.0        # 配筋率
    ok: bool = True         # 截面是否足够(承载力/轴压比/配筋率)
    note: str = ""


@dataclass
class BuildingDesign:
    T1: float
    base_shear: float
    story_shears: List[float]
    stability: float = 0.0      # 整体屈曲系数 λcr(重力下)，>10 则 P-Δ 可忽略
    drift_ratio: float = 0.0    # 顶点位移角 u_top/H
    members: Dict[str, MemberDesign] = field(default_factory=dict)


def seismic_frame_design(n_bays, n_stories, bay_w, story_h,
                         col_factory, beam_factory, w_gravity,
                         story_mass, alpha_max, Tg, seismic_grade="二级",
                         g=9.81, pdelta=True, wall_axes=None, wall_factory=None) -> BuildingDesign:
    spec = build_regular_frame(n_bays, n_stories, bay_w, story_h,
                               col_factory, beam_factory, w_gravity,
                               lateral_per_floor=0.0,
                               wall_axes=wall_axes, wall_sec=wall_factory)
    return _evaluate(spec, n_bays, n_stories, story_h, story_mass,
                     alpha_max, Tg, seismic_grade, g, pdelta)


def _evaluate(spec, n_bays, n_stories, story_h, story_mass,
              alpha_max, Tg, seismic_grade="二级", g=9.81, pdelta=True) -> "BuildingDesign":
    """对给定 spec 跑一遍：模态→反应谱→重力+地震(可含P-Δ)→组合→能力设计→配筋+充分性。"""
    # 1) 真实框架特征值模态分析（替代剪切层；模态与内力同源于真实框架）
    import numpy as np
    from .frame_spec import build_model
    from .analysis.frame_modal import frame_modal
    from .codes import gb50011_spectrum as sp
    masses = [story_mass] * n_stories
    model_full = build_model(spec)
    fm = frame_modal(model_full, masses)
    n_modes = min(n_stories, fm.n_master)
    # 楼层分组(用于层剪力)
    ylev = {}
    for k, nid in enumerate(fm.master_nodes):
        ylev.setdefault(round(model_full.nodes[nid].y, 3), []).append(k)
    levels = sorted(ylev)

    # 2) 重力工况（P-Δ：用重力轴力建几何刚度，施加到重力与地震工况）
    from .analysis.pdelta import solve_with_geometric
    gm = _model(spec, gravity=True)
    g_lin = solve(gm)
    grav_axial = {mid: r.N_axial for mid, r in g_lin.items()} if pdelta else None
    gf = solve_with_geometric(gm, grav_axial) if pdelta else g_lin

    # 3) 地震工况：**逐振型**求构件内力，再对构件内力 SRSS 组合。
    eM_sq = {mid: 0.0 for mid in spec.members}
    eN_sq = {mid: 0.0 for mid in spec.members}
    base_modes, floor_force_modes = [], []
    for jm in range(n_modes):
        Tj = fm.periods[jm]
        aj = sp.alpha(Tj, alpha_max, Tg)
        gj = fm.gammas[jm]
        phi = fm.modes[:, jm]
        lateral = []
        ff = {lev: 0.0 for lev in levels}
        Fsum = 0.0
        for k in range(fm.n_master):
            Fk = aj * gj * phi[k] * fm.master_mass[k] * g   # N
            lateral.append(NodalLoad(fm.master_nodes[k], Fx=Fk))
            Fsum += Fk
            ff[round(model_full.nodes[fm.master_nodes[k]].y, 3)] += Fk
        base_modes.append(Fsum)
        floor_force_modes.append(ff)
        em = _model(spec, gravity=False, nodal=lateral)
        efj = solve_with_geometric(em, grav_axial) if pdelta else solve(em)
        for mid in spec.members:
            Mj = max(abs(efj[mid].Mi), abs(efj[mid].Mj), abs(efj[mid].M_mid))
            eM_sq[mid] += Mj ** 2
            eN_sq[mid] += efj[mid].N_axial ** 2

    base_shear = float(np.sqrt(sum(b ** 2 for b in base_modes)))
    story_shears = []
    for li in range(len(levels)):
        sh_modes = [sum(floor_force_modes[jm][levels[m]] for m in range(li, len(levels)))
                    for jm in range(n_modes)]
        story_shears.append(float(np.sqrt(sum(s ** 2 for s in sh_modes))))

    # 顶点位移角（SRSS 楼层力等效静力施加）
    from .analysis.frame_modal import assemble_K
    Kf, idxf, _ = assemble_K(model_full)
    ndof = 3 * len(model_full.nodes)
    Fv = np.zeros(ndof)
    for lev in levels:
        f_srss = (sum(floor_force_modes[jm][lev] ** 2 for jm in range(n_modes))) ** 0.5
        ks_at = ylev[lev]
        per = f_srss / len(ks_at)
        for k in ks_at:
            Fv[fm.master_dofs[k]] += per
    fixed = set()
    for nid, nd in model_full.nodes.items():
        bb = 3 * idxf[nid]
        for kk, rr in enumerate(nd.restraint):
            if rr:
                fixed.add(bb + kk)
    free = [d for d in range(ndof) if d not in fixed]
    U = np.zeros(ndof)
    U[free] = np.linalg.solve(Kf[np.ix_(free, free)], Fv[free])
    Htot = n_stories * story_h
    utop = max(abs(U[fm.master_dofs[k]]) for k in ylev[levels[-1]])
    drift_ratio = utop / Htot

    # 整体稳定（重力下屈曲系数）
    from .analysis.pdelta import buckling_factor
    try:
        stability = buckling_factor(_model(spec, gravity=True))
    except Exception:
        stability = float("inf")
    bd = BuildingDesign(T1=fm.periods[0], base_shear=base_shear,
                        story_shears=story_shears, stability=stability,
                        drift_ratio=drift_ratio)

    # 4) 逐构件组合 + 能力设计 + 配筋
    for mid, (ni, nj, sec, w) in spec.members.items():
        gM = max(abs(gf[mid].Mi), abs(gf[mid].Mj), abs(gf[mid].M_mid)) / 1e6
        eM = (eM_sq[mid] ** 0.5) / 1e6     # SRSS 后的地震弯矩
        gN = abs(gf[mid].N_axial) / 1e3
        eN = (eN_sq[mid] ** 0.5) / 1e3
        cases = {GC: CaseForces(M=gM, N=gN), EC: CaseForces(M=eM, N=eN)}
        env = envelope(cases, seismic=True)
        M_combo = max(abs(env.M_pos), abs(env.M_neg))
        N = env.N_max
        if sec.kind == "column":
            M_cap, _ = sa.column_moment_magnify(M_combo, seismic_grade)
            cr = gc.design_column_symmetric(sec.b, sec.h, max(N, 1.0), M_cap, sec.concrete, "HRB400")
            As_min, _ = gc.column_min_reinforcement(sec.b, sec.h, seismic_grade)
            As = max(cr.As_total, As_min)
            rho = As / (sec.b * sec.h)
            mu, lim, axial_ok = gc.axial_compression_ratio(N, sec.b, sec.h, sec.concrete, seismic_grade)
            ok = bool(cr.ok and axial_ok and rho <= 0.05)
            note = f"{cr.eccentric},μN={mu:.2f},ρ={rho*100:.1f}%"
            if not axial_ok:
                note += " 轴压比超限"
            if rho > 0.05:
                note += " 配筋率超限(需加大截面/设墙)"
            As = min(As, 0.05 * sec.b * sec.h)   # 配筋率上限封顶(报量用，不足已由ok标记)
            rho = As / (sec.b * sec.h)
        elif sec.kind == "wall":
            from .codes import gb50010_wall as gw
            M_cap = M_combo
            mu = gw.wall_axial_ratio(N, sec.b, sec.h, sec.concrete)
            limit = gw.wall_axial_limit(seismic_grade)
            axial_ok = mu <= limit + 1e-6
            reinf = gw.design_wall_reinforcement(N, sec.b, sec.h, sec.concrete, "HRB400", seismic_grade)
            As = reinf.be_As * 2           # 两端边缘构件纵筋
            rho = As / (sec.b * sec.h)
            ok = bool(axial_ok)
            note = f"墙肢 μN={mu:.2f}/{limit} 竖向{reinf.vert_dist}"
            if not axial_ok:
                note += " 轴压比超限(需加长/加厚墙)"
        else:
            M_cap = M_combo  # 梁不放大弯矩(强柱弱梁是放柱)
            fl = gb.design_flexure(sec.b, sec.h, M_cap, sec.concrete, "HRB400", a_s=40)
            As_min, _ = gb.min_tension_area(sec.b, sec.h, sec.concrete, "HRB400")
            As = max(fl.As, As_min)
            rho = As / (sec.b * (sec.h - 40))
            ok = bool(fl.ok and rho <= 0.025)
            note = ("双筋" if fl.doubly else "单筋") + f",ρ={rho*100:.2f}%"
            if not fl.ok:
                note += " 截面不足(超筋)"
            elif rho > 0.025:
                note += " 配筋率偏高"
            As = min(As, 0.025 * sec.b * (sec.h - 40))  # 配筋率上限封顶(报量用)
            rho = min(rho, 0.025)
        bd.members[mid] = MemberDesign(kind=sec.kind, M_gravity=gM, M_combo=M_combo,
                                       M_capacity=M_cap, N=N, As=As, rho=rho, ok=ok, note=note)
    return bd


@dataclass
class SeismicLoopResult:
    converged: bool
    iterations: int
    history: List[str] = field(default_factory=list)
    final: "BuildingDesign" = None
    final_sections: Dict[str, str] = field(default_factory=dict)


def seismic_closed_loop(n_bays, n_stories, bay_w, story_h,
                        col_factory, beam_factory, w_gravity, story_mass,
                        alpha_max, Tg, seismic_grade="二级", g=9.81,
                        h_step=50.0, max_iter=40,
                        wall_axes=None, wall_factory=None) -> SeismicLoopResult:
    """地震工况下截面自动生长闭环（可含剪力墙）。

    每轮：以当前截面重算模态(周期随截面变)→反应谱→重力+地震组合→能力设计→配筋，
    对"截面不足/轴压比超限/配筋率超限"的构件在建筑可行域内加大截面 h，再重算。
    截面变→刚度变→周期变→地震力重分布，体现真正的抗震迭代设计。
    """
    spec = build_regular_frame(n_bays, n_stories, bay_w, story_h,
                               col_factory, beam_factory, w_gravity,
                               lateral_per_floor=0.0,
                               wall_axes=wall_axes, wall_sec=wall_factory)
    res = SeismicLoopResult(converged=False, iterations=0)
    for it in range(1, max_iter + 1):
        res.iterations = it
        bd = _evaluate(spec, n_bays, n_stories, story_h, story_mass,
                       alpha_max, Tg, seismic_grade, g, pdelta=False)
        changed = False
        n_bad = 0
        for mid, (ni, nj, sec, w) in spec.members.items():
            m = bd.members[mid]
            if not m.ok:
                n_bad += 1
                if sec.h < sec.h_max:
                    sec.h = min(sec.h + h_step, sec.h_max)
                    changed = True
        res.history.append(
            f"第{it}轮: T1={bd.T1:.3f}s 基底剪力={bd.base_shear/1e3:.0f}kN "
            f"不足构件={n_bad}" + ("  → 生长截面重算(重算模态)" if changed else "  → 收敛"))
        if not changed:
            res.converged = (n_bad == 0)
            res.final = bd
            break
    if res.final is None:
        res.final = _evaluate(spec, n_bays, n_stories, story_h, story_mass,
                              alpha_max, Tg, seismic_grade, g)
    for mid, (ni, nj, sec, w) in spec.members.items():
        res.final_sections[mid] = f"{sec.b:.0f}×{sec.h:.0f}"
    return res
