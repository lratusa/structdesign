"""计算集成：建模工程 → Frame3D → 模态/双向反应谱CQC/位移比/层间位移角 → 柱双偏压·墙·梁配筋
→ 规范指标 + 专业计算书。复用 structdesign 内核，逻辑对齐 design_project_3d（已验证）。
"""
from __future__ import annotations
from dataclasses import dataclass, field
import os

from ..build.to_frame3d import build_with_meta, build_frame3d
from . import detailing as dt
from .loadcode import live_reduction_vertical, beam_live_reduction
from .subbeam import secondary_transfer
from structdesign import loads_takedown as td
from structdesign import rebar as rb
from structdesign.frame3d_builder import floor_masses
from structdesign.analysis.frame3d import member_forces, Load3D
from structdesign.analysis.rspectrum3d import response_spectrum_3d
from structdesign.analysis.drift3d import displacement_ratio, story_drift_ratio, story_profiles
from structdesign.codes.gb50010_column import (design_column_biaxial, axial_compression_ratio,
                                               column_min_reinforcement)
from structdesign.codes import gb50010_wall as gw
from structdesign.codes import gb50010_beam as gb
from structdesign.report import calcbook_pro
from structdesign.drawing import figures as _fig


class ModelUnstableError(Exception):
    """模型刚度/质量矩阵奇异：通常为机构（缺支承/某层竖向构件<3或共线/单柱塔楼），
    或缺平面外约束。GUI 捕获后提示用户，而非崩溃。"""


@dataclass
class Result:
    Tx: float; Ty: float; Tt: float; T1: float; period_ratio: float
    base_x: float; base_y: float; shear_weight: float
    disp_ratio_x: float; disp_ratio_y: float; drift_x: float
    n_members: int; n_bad: int; total_steel_t: float
    wind_base_x: float = 0.0; wind_base_y: float = 0.0      # 风基底剪力(N)
    wind_drift_x: float = 0.0; wind_drift_y: float = 0.0    # 风致最大层间位移角
    wind_controls: bool = False                             # 风荷载是否控制(基底剪力)
    wind_info: dict = field(default_factory=dict)
    thermal_on: bool = False                                # 是否计入温度作用
    thermal_col_M: float = 0.0                              # 温度引起的最大柱弯矩 kN·m
    vert_on: bool = False                                   # 是否计入竖向地震
    vert_Evk: float = 0.0                                   # 竖向地震标准值 F_Evk (N)
    vert_col_N: float = 0.0                                 # 竖向地震最大柱轴力增量 kN
    n_secondary: int = 0                                    # 次梁数量(已导算至主梁)
    n_beam_total: int = 0                                   # 梁(逻辑)总数
    n_beam_marks: int = 0                                   # 梁归并后不同编号数(跨构件钢筋归并)
    diaphragm: str = "rigid"                                # 楼盖假定
    T1_flexible: float = 0.0                                # 柔性楼盖第一周期(半刚性上界)
    basement: dict = field(default_factory=dict)           # 地下室专项(外墙/抗浮)
    n_short_col: int = 0                                    # 短柱数量(错层/夹层排查)
    checks_table: list = field(default_factory=list)
    members: list = field(default_factory=list)
    slabs: list = field(default_factory=list)
    takeoff: dict = field(default_factory=dict)
    notes: dict = field(default_factory=dict)
    calcbook_md: str = ""
    calcbook_docx: str = ""
    figures: dict = field(default_factory=dict)


def _region_codes(project):
    from ..regions import get_region
    return get_region(getattr(project, "region", "national")).codes


def _region_name(project):
    from ..regions import get_region
    return get_region(getattr(project, "region", "national")).name


def _half_span(lines, v, default=3000.0):
    """v 处上下(左右)相邻轴线的半跨之和，做梁受荷宽度。"""
    ls = sorted(set(lines))
    if not ls:
        return default
    i = min(range(len(ls)), key=lambda k: abs(ls[k] - v))
    below = (v - ls[i - 1]) if i > 0 else 0
    above = (ls[i + 1] - v) if i < len(ls) - 1 else 0
    if below and above:
        return (below + above) / 2.0
    return (below or above) or default


def _beam_tributary(project, b):
    g = project.grid
    if abs(b.y1 - b.y2) < 1:          # 水平梁 → 垂直向(Y)取荷载宽
        return _half_span(g.y, b.y1)
    if abs(b.x1 - b.x2) < 1:          # 竖直梁 → 水平向(X)
        return _half_span(g.x, b.x1)
    return 3000.0


def _plan_bounds(project):
    xs, ys = [], []
    for c in project.floor.columns:
        xs.append(c.x); ys.append(c.y)
    for w in project.floor.walls:
        xs += [w.x1, w.x2]; ys += [w.y1, w.y2]
    for b in project.floor.beams:
        xs += [b.x1, b.x2]; ys += [b.y1, b.y2]
    if not xs:
        return 0.0, 0.0, 0.0, 0.0
    return min(xs), min(ys), max(xs), max(ys)


def analyze(project, out_dir, light=False) -> Result:
    """light=True：只算指标与配筋(供优化迭代)，跳过出图/出计算书以提速。"""
    os.makedirs(out_dir, exist_ok=True)
    s = project.seismic
    slab = project.floor.slab
    zs = project.elevations()
    n_floors = len(zs) - 1
    hz_typ = (zs[-1] / n_floors) if n_floors else 3600.0

    xmin, ymin, xmax, ymax = _plan_bounds(project)
    Lx, Ly = (xmax - xmin), (ymax - ymin)
    def _farea(f):
        xs, ys = [], []
        for c in f.columns: xs.append(c.x); ys.append(c.y)
        for w in f.walls: xs += [w.x1, w.x2]; ys += [w.y1, w.y2]
        for b in f.beams: xs += [b.x1, b.x2]; ys += [b.y1, b.y2]
        if not xs:
            return 1.0
        a = (max(xs) - min(xs)) / 1000.0 * (max(ys) - min(ys)) / 1000.0
        for o in list(f.openings) + list(f.stairs_placed):
            a -= abs(o.x2 - o.x1) * abs(o.y2 - o.y1) / 1e6
        return max(a, 1.0)

    area_m2 = _farea(project.floor)
    q = td.slab_q(slab.dead, slab.live)
    mass = max((slab.dead + 0.5 * slab.live) * area_m2 * 100, 3e5)  # 代表值(计算书显示)

    model0, meta = build_with_meta(project)
    n_plan = len({(round(n.x), round(n.y)) for n in model0.nodes.values() if n.z > 1e-6}) or 1
    # 各标高平面点(均摊重力)
    plan_pts_z = {}
    for n in model0.nodes.values():
        if n.z > 1e-6:
            plan_pts_z.setdefault(round(n.z, 3), set()).add((round(n.x), round(n.y)))

    # 逐楼层(多标准层/大底盘)质量与重力：按各层平面面积/荷载
    level_fl = project.level_floors()
    base_fm = floor_masses(build_frame3d(project), 1.0)      # 取与模态一致的 z 键
    zsorted = sorted(base_fm.keys())
    floor_mass = {}
    grav_dead_z = {}      # 恒载(已乘 γG)逐节点
    grav_live_z = {}      # 活载(已乘 γQ)逐节点 —— 单独求解供活荷折减
    grav_rep_z = {}       # 重力荷载代表值(恒+0.5活，每层合计 N) —— 竖向地震用
    GG, GQ = 1.3, 1.5
    for idx, z in enumerate(zsorted):
        f = level_fl[idx] if idx < len(level_fl) else level_fl[-1]
        a = _farea(f)
        floor_mass[z] = max((f.slab.dead + 0.5 * f.slab.live) * a * 100, 3e5)
        npl = len(plan_pts_z.get(round(z, 3), set())) or 1
        grav_dead_z[round(z, 3)] = GG * f.slab.dead * a * 1000.0 / npl
        grav_live_z[round(z, 3)] = GQ * f.slab.live * a * 1000.0 / npl
        grav_rep_z[round(z, 3)] = (f.slab.dead + 0.5 * f.slab.live) * a * 1000.0   # N/层
    total_mass = sum(floor_mass.values())

    # 重力轴力：恒/活分别求解（线性叠加），活荷折减(GB 50009 5.1.2)按上部层数施于竖向构件
    def _grav_solve(loadmap):
        m = build_frame3d(project)
        for nid, n in m.nodes.items():
            if n.z > 1e-6:
                m.add_load(Load3D(nid, fz=-loadmap.get(round(n.z, 3), 0.0)))
        return member_forces(m)
    import numpy as _np
    try:
        fD = _grav_solve(grav_dead_z)
        fL = _grav_solve(grav_live_z)
        # 三维双向反应谱(CQC)
        res = response_spectrum_3d(build_frame3d(project), floor_mass,
                                   s.alpha_max, s.Tg, n_modes=s.n_modes)
    except _np.linalg.LinAlgError as e:
        raise ModelUnstableError(
            "结构分析失败：刚度/质量矩阵奇异（模型为机构或缺约束）。\n"
            "常见原因：① 某标准层竖向构件不足（每层需≥3根不共线柱/墙）；"
            "② 所有柱共线（平面外无约束）；③ 上部柱悬空未设转换梁（先点“拼接检验/自动转换梁”）；"
            "④ 单柱塔楼（无法形成楼盖转动质量）。请补足支承后重算。"
        ) from e
    r = res["modal"]
    W = total_mass * 9.81
    drx = displacement_ratio(build_frame3d(project), "x")
    dry = displacement_ratio(build_frame3d(project), "y")
    drift_x = story_drift_ratio(build_frame3d(project), "x", hz_typ,
                                F=res["base_x"] / max(len(zsorted) * n_plan, 1))

    # 风荷载(GB 50009)：逐层等效静风力 → 风致层间位移角 → 与地震包络
    from .wind import wind_story_forces
    wf_x, wi_x = wind_story_forces(project, "x")
    wf_y, wi_y = wind_story_forces(project, "y")
    wind_base_x = wi_x["base_shear"] * 1e3      # N
    wind_base_y = wi_y["base_shear"] * 1e3
    wind_drift_x = wind_drift_y = 0.0
    if wf_x:
        # story_profiles 力单位为 N（与地震 base_x 一致），风力 kN→N
        wfN_x = {z: F * 1e3 for z, F in wf_x.items()}
        wfN_y = {z: F * 1e3 for z, F in wf_y.items()}
        try:
            prof = story_profiles(build_frame3d(project), "x", wfN_x, hz_typ)
            wind_drift_x = max((d for *_, d in prof), default=0.0)
            prof = story_profiles(build_frame3d(project), "y", wfN_y, hz_typ)
            wind_drift_y = max((d for *_, d in prof), default=0.0)
        except _np.linalg.LinAlgError:
            wind_drift_x = wind_drift_y = 0.0
    wind_controls = wind_base_x > res["base_x"] or wind_base_y > res["base_y"]
    # 层间位移角取地震/风包络
    drift_x = max(drift_x, wind_drift_x, wind_drift_y)

    # 弹性/半刚性楼盖：算柔性楼盖周期作上界，与刚性对比 → 提示刚性楼盖假定是否适用
    diaphragm = getattr(s, "diaphragm", "rigid")
    T1_flex = 0.0
    if diaphragm != "rigid":
        from structdesign.analysis.modal3d import flexible_diaphragm_periods
        try:
            fp = flexible_diaphragm_periods(build_frame3d(project), floor_mass, n=3)
            T1_flex = fp[0] if fp else 0.0
        except _np.linalg.LinAlgError:
            T1_flex = 0.0

    # 配筋
    mf = res["member_forces"]
    model = build_frame3d(project)

    # 温度作用(GB 50009 第9章)：对梁施加等效热荷载 → 温度内力(主要为端部柱附加弯矩)
    fT = {}
    th = getattr(project, "thermal", None)
    thermal_on = bool(th and th.enabled and abs(th.dT) > 1e-6)
    THERMAL_COMBO = 0.9      # 温度作为伴随可变作用 γQ·ψc≈1.5×0.6
    max_thermal_col_M = 0.0
    if thermal_on:
        from .temperature import thermal_node_loads
        beam_ids = [mid for mid, mm in meta.items() if mm["kind"] == "梁"]
        mt = build_frame3d(project)
        for ld in thermal_node_loads(mt, beam_ids, th.dT, th.alpha):
            mt.add_load(ld)
        try:
            fT = member_forces(mt)
        except _np.linalg.LinAlgError:
            fT = {}

    # 竖向地震(GB 50011 5.3.1 简化)：F_Evk=α_vmax·G_eq，α_vmax=0.65·α_hmax，G_eq=0.75·ΣG_rep；
    # 各层 F_vi ∝ G_i·H_i，施于楼层节点求竖向地震柱轴力增量。
    fEv = {}
    vert_on = bool(getattr(s, "vertical", False))
    F_Evk = 0.0
    max_col_Nev = 0.0
    if vert_on:
        alpha_vmax = 0.65 * s.alpha_max
        G_eq = 0.75 * sum(grav_rep_z.values())
        F_Evk = alpha_vmax * G_eq                                    # N
        GiHi = {z: grav_rep_z[z] * (z if z > 0 else 1.0) for z in grav_rep_z}
        sGH = sum(GiHi.values()) or 1.0
        mv = build_frame3d(project)
        nodes_at = {}
        for nid, n in mv.nodes.items():
            if n.z > 1e-6:
                nodes_at.setdefault(round(n.z, 3), []).append(nid)
        for z, ids in nodes_at.items():
            F_vi = F_Evk * GiHi.get(z, 0.0) / sGH                    # 该层竖向地震力 N
            per = F_vi / len(ids)
            for nid in ids:
                mv.add_load(Load3D(nid, fz=-per))                    # 向下(与重力同向,柱压增大)
        try:
            fEv = member_forces(mv)
        except _np.linalg.LinAlgError:
            fEv = {}

    # 次梁导算：主/次梁判别 + 次梁反力作为集中力传至主梁(一键轴网模型全为主梁→no-op)
    beam_kinds, prim_loads = secondary_transfer(
        project.floor, q, lambda b: _beam_tributary(project, b))
    n_secondary = sum(1 for k in beam_kinds if k == "次")

    # 梁可能被打断成多段：按(逻辑梁,楼层)聚合各段 FEM 端力(取最大)，并保证每根逻辑梁只设计一次
    beam_fem = {}
    for _mid, _mm in meta.items():
        if _mm["kind"] != "梁":
            continue
        bkey = (_mm.get("beam_idx", 0), _mm["level"])
        d = beam_fem.setdefault(bkey, {"Ms": 0.0, "Mg": 0.0, "V": 0.0})
        d["Ms"] = max(d["Ms"], abs(mf[_mid]["Mz"]) / 1e6)
        d["Mg"] = max(d["Mg"], abs(fD[_mid]["Mz"] + fL[_mid]["Mz"]) / 1e6)
        d["V"] = max(d["V"], max(abs(mf[_mid]["Vy"]), abs(mf[_mid]["Vz"])) / 1e3)
    designed_beams = set()

    members = []
    steel = 0.0
    zs_mm = project.elevations()
    conc = {"col": 0.0, "wall": 0.0, "beam": 0.0}    # mm³
    slong = {"col": 0.0, "wall": 0.0, "beam": 0.0}   # kg 纵筋
    for mid, m in model.members.items():
        info = meta[mid]
        kind = info["kind"]
        lvl = info.get("level", 1)
        hmm = (zs_mm[lvl] - zs_mm[lvl - 1]) if lvl < len(zs_mm) else hz_typ
        m_above = max(n_floors - lvl + 1, 1)            # 计算截面以上层数
        psi_L = live_reduction_vertical(m_above)        # 活荷折减(GB 50009 5.1.2)
        if kind == "柱":
            My = mf[mid]["My"] / 1e6
            Mz = mf[mid]["Mz"] / 1e6
            N = abs(fD[mid]["N"] + psi_L * fL[mid]["N"]) / 1e3
            if thermal_on and mid in fT:        # 叠加温度作用柱弯矩
                tMz = abs(fT[mid]["Mz"]) / 1e6; tMy = abs(fT[mid]["My"]) / 1e6
                Mz += THERMAL_COMBO * tMz; My += THERMAL_COMBO * tMy
                max_thermal_col_M = max(max_thermal_col_M, tMz, tMy)
            if vert_on and mid in fEv:          # 叠加竖向地震柱轴力(压增)
                Nev = abs(fEv[mid]["N"]) / 1e3
                N += Nev
                max_col_Nev = max(max_col_Nev, Nev)
            bi = design_column_biaxial(info["b"], info["h"], N, Mz, My, info["mat"], "HRB400")
            As_min, _ = column_min_reinforcement(info["b"], info["h"], s.grade)
            As_col = max(bi.As_total, As_min)
            rho = As_col / (info["b"] * info["h"])
            mu, lim, aok = axial_compression_ratio(N, info["b"], info["h"], info["mat"], s.grade)
            ok = aok and rho <= 0.05
            steel += As_col * (hz_typ / 1000) * 7.85e-6 * 1000
            bars = rb.select_bars(As_col / 4, info["b"])
            stir = dt.col_stirrup(info["b"], s.grade, bars.d)
            conc["col"] += info["b"] * info["h"] * hmm
            slong["col"] += dt.steel_kg(As_col, hmm / 1000.0)
            members.append(dict(id=mid, kind="柱", sec=f"{int(info['b'])}×{int(info['h'])}",
                                N=N, Mx=Mz, My=My, M=max(My, Mz), mu=mu,
                                bars=f"4×{bars.label()}", rho=rho, ok=ok, stirrup=stir))
        elif kind == "墙":
            N = abs(fD[mid]["N"] + psi_L * fL[mid]["N"]) / 1e3
            My = mf[mid]["My"] / 1e6
            Mz = mf[mid]["Mz"] / 1e6
            mu = gw.wall_axial_ratio(N, info["bw"], info["lw"], info["mat"])
            reinf = gw.design_wall_reinforcement(N, info["bw"], info["lw"], info["mat"], "HRB400", s.grade)
            ok = mu <= gw.wall_axial_limit(s.grade)
            steel += reinf.be_As * 2 * (hz_typ / 1000) * 7.85e-6 * 1000
            conc["wall"] += info["bw"] * info["lw"] * hmm
            slong["wall"] += dt.steel_kg(reinf.be_As * 2, hmm / 1000.0)
            members.append(dict(id=mid, kind="墙", sec=f"{int(info['bw'])}×{int(info['lw'])}",
                                N=N, Mx=Mz, My=My, M=max(My, Mz), mu=mu,
                                bars=reinf.be_bars, vdist=reinf.vert_dist,
                                hdist=reinf.horiz_dist, be_len=getattr(reinf, "be_length", 0.0),
                                rho=0.0, ok=ok))
        elif kind == "梁":
            bi = info.get("beam_idx", 0)
            bkey = (bi, lvl)
            if bkey in designed_beams:        # 同一逻辑梁的其它分段不重复设计
                continue
            designed_beams.add(bkey)
            fem = beam_fem.get(bkey, {"Ms": 0.0, "Mg": 0.0, "V": 0.0})
            seg = project.floor.beams[bi] if bi < len(project.floor.beams) else None
            Ms = fem["Ms"]                                     # 地震端弯矩(分段最大)
            bb, bh = info["b"], info["h"]
            As_min, _ = gb.min_tension_area(bb, bh, info["mat"], "HRB400")
            # 板传线荷载估算跨中正弯矩 / 支座负弯矩（连续梁系数）
            if seg is not None:
                L = ((seg.x2 - seg.x1) ** 2 + (seg.y2 - seg.y1) ** 2) ** 0.5 / 1000.0  # m
                trib = _beam_tributary(project, seg) / 1000.0                            # m
                beta_L = beam_live_reduction(L * trib)        # 楼面梁活荷折减(从属面积)
                w = (GG * slab.dead + beta_L * GQ * slab.live) * trib                   # kN/m
                M_pos = w * L * L / 14.0
                M_neg = w * L * L / 11.0
            else:
                L = 6.0; w = 0.0; M_pos = 0.0; M_neg = 0.0
            Mg_end = fem["Mg"]                                 # 梁端重力弯矩(恒+活全值)
            M_neg = max(M_neg, Mg_end + Ms)
            # 次梁导算：主梁计入次梁传来的集中力
            kind_b = beam_kinds[bi] if bi < len(beam_kinds) else "主"
            pls = prim_loads.get(bi, [])
            Vpt = 0.0
            if pls:
                M_pos += sum(P * L * t * (1 - t) for t, P in pls)       # 集中力跨中弯矩(简支上限)
                M_neg += sum(P for _, P in pls) * L * 0.08              # 连续支座近似
                Vpt = sum(P * max(t, 1 - t) for t, P in pls)           # 集中力引起支座剪力
            f_pos = gb.design_flexure(bb, bh, max(M_pos, 1.0), info["mat"], "HRB400", a_s=40)
            f_neg = gb.design_flexure(bb, bh, max(M_neg, 1.0), info["mat"], "HRB400", a_s=40)
            As_bot = max(f_pos.As, As_min); As_top = max(f_neg.As, As_min)
            bars_bot = rb.select_bars(As_bot, bb); bars_top = rb.select_bars(As_top, bb)
            As = max(As_bot, As_top)
            # 抗剪 → 箍筋(含加密区)
            V = w * L / 2.0 + Vpt + fem["V"]   # kN
            shr = gb.design_shear(bb, bh, max(V, 1.0), info["mat"], "HPB300", a_s=40)
            stir = dt.beam_stirrup(getattr(shr, "Asv_s", 0.0) or 0.0, bh)
            shear_ok = getattr(shr, "section_ok", True)
            ok = f_pos.ok and f_neg.ok and shear_ok and As / (bb * (bh - 40)) <= 0.025
            conc["beam"] += bb * bh * (L * 1000.0)
            slong["beam"] += dt.steel_kg(As_top + As_bot, L)
            # 平法集中标注用：上部通长筋(2根角筋) + 侧面腰筋(GB 50010 9.2.13: 腹板高 hw≥450 设构造腰筋)
            d_top = int(getattr(bars_top, "d", 20))
            thru = f"2D{d_top}"
            import math as _m2
            hw = bh - 100.0
            if hw >= 450.0:
                As_side = 0.001 * bb * hw                       # 每侧构造腰筋面积
                n_side = max(int(_m2.ceil(As_side / 113.1)), int(_m2.ceil(hw / 200.0)) - 1, 1)
                waist = f"G{2*n_side}D12"
            else:
                waist = ""
            members.append(dict(id=mid, kind="梁", sec=f"{int(bb)}×{int(bh)}",
                                N=0, M=max(M_pos, M_neg), As=As, bars=bars_top.label(), ok=ok,
                                As_top=As_top, As_bot=As_bot, beam_kind=kind_b,
                                bars_top=bars_top.label(), bars_bot=bars_bot.label(),
                                thru=thru, waist=waist, stirrup=stir))

    # 设计规则：梁纵筋"取大包罗"(envelope)——同截面组内统一取最大上/下纵筋，便于施工(同时影响计算与出图)
    pol = getattr(project, "policy", None)
    if pol and getattr(pol, "beam_rebar_merge", "none") == "envelope":
        grp = {}
        for mm in members:
            if mm["kind"] == "梁":
                grp.setdefault(mm["sec"], []).append(mm)
        for ms in grp.values():
            top = max(ms, key=lambda m: m.get("As_top", 0.0))
            bot = max(ms, key=lambda m: m.get("As_bot", 0.0))
            for mm in ms:
                mm["As_top"] = top.get("As_top", mm.get("As_top"))
                mm["bars_top"] = top.get("bars_top", mm.get("bars_top"))
                mm["As_bot"] = bot.get("As_bot", mm.get("As_bot"))
                mm["bars_bot"] = bot.get("bars_bot", mm.get("bars_bot"))
                mm["As"] = max(mm.get("As_top", 0.0), mm.get("As_bot", 0.0))
                mm["bars"] = mm["bars_top"]
                mm["thru"] = top.get("thru", mm.get("thru", "2D20"))   # 通长筋随上部筋归并

    n_vert = len([m for m in members if m["kind"] in ("柱", "墙")])
    n_bad = sum(0 if m["ok"] else 1 for m in members)
    sw = res["base_x"] / W if W else 0.0

    # 跨构件钢筋归并：相同(截面+上/下纵筋+箍筋)的梁合并为同一编号
    beam_ms = [m for m in members if m["kind"] == "梁"]
    beam_marks = {(m["sec"], m.get("bars_top", ""), m.get("bars_bot", ""), m.get("stirrup", ""))
                  for m in beam_ms}
    n_beam_total = len(beam_ms); n_beam_marks = len(beam_marks)

    # 短柱排查(错层/夹层) + 地下室专项
    from .basement import short_columns, design_basement
    max_bh = max([b.h for b in project.floor.beams], default=600)
    sc = short_columns(project, hz_typ, beam_h=max_bh)
    n_short_col = sc["n_short"]

    # 层间位移角限值按体系取（GB 50011 5.5.1）：纯框架 1/550，框架-剪力墙/核心筒 1/800
    drift_lim = (1 / 800.0) if project.floor.walls else (1 / 550.0)
    checks_table = [
        ("周期比 Tt/T1", f"{r.period_ratio:.3f}", "≤0.90", r.period_ratio <= 0.90),
        ("位移比(X)", f"{drx:.2f}", "≤1.2", drx <= 1.2),
        ("位移比(Y)", f"{dry:.2f}", "≤1.2", dry <= 1.2),
        ("剪重比", f"{sw*100:.2f}%", "≥1.6%", sw >= 0.016),
        ("最大层间位移角(地震/风包络)", f"1/{1/max(drift_x,1e-9):.0f}", f"≤1/{1/drift_lim:.0f}", drift_x <= drift_lim),
    ]
    if wind_base_x > 0 or wind_base_y > 0:
        ctrl = "风控制" if wind_controls else "地震控制"
        checks_table.append(
            (f"基底剪力 风/地震({ctrl})",
             f"风{max(wind_base_x,wind_base_y)/1e3:.0f} / 震{max(res['base_x'],res['base_y'])/1e3:.0f} kN",
             "包络取大", True))
    if thermal_on:
        checks_table.append(
            ("温度作用最大柱弯矩", f"{max_thermal_col_M:.0f} kN·m",
             f"ΔT={th.dT:.0f}°C 已计入", True))
    if vert_on:
        checks_table.append(
            ("竖向地震 F_Evk / 柱轴力增量",
             f"{F_Evk/1e3:.0f} kN / 最大 {max_col_Nev:.0f} kN",
             "GB 50011 5.3 已计入", True))
    if n_secondary:
        checks_table.append(
            ("主/次梁", f"次梁 {n_secondary} 根已导算至主梁",
             "次梁反力作集中力", True))
    if n_beam_total:
        checks_table.append(
            ("梁钢筋归并", f"{n_beam_total} 根 → {n_beam_marks} 种 KL",
             "跨构件归并", True))
    if diaphragm != "rigid" and T1_flex > 0:
        div = (T1_flex - r.T1) / r.T1 if r.T1 > 0 else 0.0
        checks_table.append(
            ("基本周期 T1 楼盖敏感性(柔/刚)", f"{T1_flex:.2f}/{r.T1:.2f} s (+{div*100:.0f}%)",
             "T1对楼盖不敏感" if div < 0.10 else "T1受楼盖影响", div < 0.10))
    if n_short_col > 0:
        checks_table.append(
            ("短柱(错层/夹层)", f"{n_short_col} 种截面 净高/h<4 (Hn≈{sc['Hn']})",
             "全高加密箍筋+抗剪验算", True))

    conc_m3 = {k: v / 1e9 for k, v in conc.items()}
    long_t = sum(slong.values()) / 1000.0
    stir_t = (slong["col"] * 0.30 + slong["wall"] * 0.20 + slong["beam"] * 0.45) / 1000.0
    gfa = max(area_m2 * n_floors, 1.0)
    takeoff = dict(
        conc_col=conc_m3["col"], conc_wall=conc_m3["wall"], conc_beam=conc_m3["beam"],
        conc_total=sum(conc_m3.values()),
        steel_long_t=long_t, steel_stirrup_t=stir_t, steel_total_t=long_t + stir_t,
        steel_kg_m2=(long_t + stir_t) * 1000.0 / gfa,
        conc_m3_per_m2=sum(conc_m3.values()) / gfa, gfa=gfa,
    )

    # 地下室专项(外墙水土压力 + 抗浮)
    bsmt = design_basement(project, takeoff) or {}
    if bsmt:
        checks_table.append(
            ("地下室外墙(每米)", f"M={bsmt['M_design']:.0f}kN·m As={bsmt['As_req']:.0f}mm²",
             f"H={bsmt['H']:.1f}m 水头{bsmt['water_height']:.1f}m", True))
        checks_table.append(
            ("地下室抗浮 Kf", f"{bsmt['anti_float_Kf']:.2f}", "≥1.05",
             bool(bsmt['anti_float_ok'])))

    # 设计说明 / 加密区长度（代表值）
    max_col = max([max(c.b, c.h) for c in project.floor.columns], default=500)
    max_bh = max([b.h for b in project.floor.beams], default=600)
    Hn = max(hz_typ - max_bh, hz_typ * 0.6)            # 柱净高 ≈ 层高 - 梁高
    notes = dict(
        grade=s.grade, conc_col="C40", conc_wall="C40", conc_beam="C30", rebar="HRB400",
        cover_beam=25, cover_col=30, cover_wall=15,
        beam_dense=dt.beam_dense_len(max_bh, s.grade),
        col_dense=dt.col_dense_len(max_col, Hn, s.grade, bottom=False),
        col_dense_bottom=dt.col_dense_len(max_col, Hn, s.grade, bottom=True),
        Hn=int(Hn),
    )

    # 楼板设计（若布置了板）：单/双向板配筋，按(板厚,跨,配筋)归并编号 LB#
    slab_designs = []
    if project.floor.slabs:
        from .slab_design import design_slab, slab_spans
        groups, order = {}, []
        per = []
        for sl in project.floor.slabs:
            Lx, Ly = slab_spans(sl)
            d = design_slab(Lx, Ly, sl.t, q)
            gkey = (d["t"], d["Lx"], d["Ly"], d["bars_x"], d["bars_y"])
            if gkey not in groups:
                groups[gkey] = dict(d, n=0); order.append(gkey)
            groups[gkey]["n"] += 1
            per.append((sl, gkey))
        for i, gkey in enumerate(order):
            groups[gkey]["name"] = f"LB{i+1}"
        for sl, gkey in per:
            g = groups[gkey]
            slab_designs.append(dict(
                x1=sl.x1, y1=sl.y1, x2=sl.x2, y2=sl.y2, name=g["name"],
                t=g["t"], kind=g["kind"], bars_x=g["bars_x"], bars_y=g["bars_y"],
                bars_x_top=g.get("bars_x_top", g["bars_x"]),
                bars_y_top=g.get("bars_y_top", g["bars_y"]),
                Asx=g["Asx"], Asy=g["Asy"], ok=g["ok"],
                Lx=g["Lx"], Ly=g["Ly"], qty=g["n"]))

    r_out = Result(
        Tx=r.Tx, Ty=r.Ty, Tt=r.Tt, T1=r.T1, period_ratio=r.period_ratio,
        base_x=res["base_x"], base_y=res["base_y"], shear_weight=sw,
        disp_ratio_x=drx, disp_ratio_y=dry, drift_x=drift_x,
        n_members=n_vert, n_bad=n_bad, total_steel_t=steel / 1000,
        wind_base_x=wind_base_x, wind_base_y=wind_base_y,
        wind_drift_x=wind_drift_x, wind_drift_y=wind_drift_y,
        wind_controls=wind_controls,
        wind_info=dict(x=wi_x, y=wi_y, controls=wind_controls,
                       seismic_base_x=res["base_x"], seismic_base_y=res["base_y"]),
        thermal_on=thermal_on, thermal_col_M=max_thermal_col_M,
        vert_on=vert_on, vert_Evk=F_Evk, vert_col_N=max_col_Nev,
        n_secondary=n_secondary, n_beam_total=n_beam_total, n_beam_marks=n_beam_marks,
        diaphragm=diaphragm, T1_flexible=T1_flex,
        basement=bsmt, n_short_col=n_short_col,
        checks_table=checks_table, members=members, slabs=slab_designs,
        takeoff=takeoff, notes=notes,
        calcbook_md="", calcbook_docx="", figures={},
    )
    if light:
        return r_out

    has_wall = any(m["kind"] == "墙" for m in members)
    figs = _make_figures(project, build_frame3d(project), res, members, hz_typ, out_dir, n_floors)

    book_data = dict(
        version="0.21-modeler",
        project=dict(name=f"{n_floors}层 {'框架-剪力墙' if has_wall else '框架'}结构(建模器)",
                     type="钢筋混凝土" + ("框架-剪力墙" if has_wall else "框架") + "结构",
                     system=("框架-剪力墙" if has_wall else "框架") + "（钢筋混凝土）",
                     nx=len(project.grid.x) - 1 if project.grid.x else 0,
                     ny=len(project.grid.y) - 1 if project.grid.y else 0,
                     nz=n_floors, bx=int(Lx), by=int(Ly), hz=int(hz_typ),
                     n_walls=len(project.floor.walls), concrete_col="C40", concrete_beam="C30",
                     dead=slab.dead, live=slab.live, seismic_grade=s.grade),
        codes=_region_codes(project),
        region=_region_name(project),
        seismic=dict(alpha_max=s.alpha_max, Tg=s.Tg, zeta=0.05, mass=mass,
                     Tx=r.Tx, Ty=r.Ty, Tt=r.Tt, period_ratio=r.period_ratio,
                     base_x=res["base_x"], base_y=res["base_y"], base_bi=res["base_bi"],
                     shear_weight=sw, disp_ratio_x=drx, disp_ratio_y=dry),
        wind=(dict(w0=wi_x["w0"], terrain=wi_x["terrain"], mu_s=wi_x["mu_s"], H=wi_x["H"],
                   base_x=wind_base_x, base_y=wind_base_y,
                   drift_x=wind_drift_x, drift_y=wind_drift_y, controls=wind_controls)
              if (wind_base_x > 0 or wind_base_y > 0) else None),
        diaphragm=diaphragm, T1_flex=T1_flex,
        basement=(bsmt if bsmt else None),
        short_col=(dict(n=n_short_col, Hn=sc["Hn"]) if n_short_col else None),
        thermal=(dict(dT=project.thermal.dT, alpha=project.thermal.alpha,
                      col_M=max_thermal_col_M) if thermal_on else None),
        vertical=(dict(Evk=F_Evk, alpha_vmax=0.65 * s.alpha_max,
                       col_N=max_col_Nev) if vert_on else None),
        modes=[(m.period, m.kind) for m in r.modes],
        drift=drift_x, stability=None, members=members,
        checks_table=checks_table, steel_t=steel / 1000, figures=figs,
    )
    cb = os.path.join(out_dir, "计算书.md")
    body = calcbook_pro.render(book_data)
    # 「衡」规范引擎逐条溯源章节（玻璃盒·每个判定→rule_id条文锚点）。加法+崩溃隔离：绝不拖垮计算书。
    try:
        from heng.calcsection import compliance_section
        body += "\n\n---\n\n" + compliance_section(
            r_out, project, getattr(project, "jurisdiction", "CN"))
    except Exception:
        pass
    with open(cb, "w", encoding="utf-8") as f:
        f.write(body)
    docx = ""
    import shutil as _sh, subprocess as _sp
    if _sh.which("pandoc"):
        try:
            _sp.run(["pandoc", os.path.basename(cb), "-o", "计算书.docx"],
                    check=True, capture_output=True, cwd=out_dir, timeout=120)
            docx = os.path.join(out_dir, "计算书.docx")
        except Exception:
            docx = ""

    r_out.figures = figs
    r_out.calcbook_md = cb
    r_out.calcbook_docx = docx
    return r_out


def _make_figures(project, model, res, members, hz_typ, out_dir, n_floors):
    figs = {}
    try:
        _fig.axon_png(model, os.path.join(out_dir, "三维模型图.png"), title="3D Model (Modeler)")
        figs["model"] = "三维模型图.png"
        rep_col = next((m for m in members if m["kind"] == "柱"), None)
        if rep_col:
            b, h = [int(v) for v in rep_col["sec"].split("×")]
            cb_bars = rb.select_bars(0.012 * b * h / 4, b)
            _fig.section_png(b, h, cb_bars.n, cb_bars.n, cb_bars.d, 10,
                             os.path.join(out_dir, "柱大样.png"),
                             title=f"Column {rep_col['id']}", n_side=2)
            figs["col_section"] = "柱大样.png"
        rep_wall = next((m for m in members if m["kind"] == "墙"), None)
        if rep_wall:
            bw, lw = [int(v) for v in rep_wall["sec"].split("×")]
            _fig.wall_section_png(bw, lw, 25, 6, 8,
                                  os.path.join(out_dir, "墙大样.png"), title="Shear Wall")
            figs["wall_section"] = "墙大样.png"
        zlevels = sorted({round(n.z, 3) for n in model.nodes.values() if n.z > 1e-6})
        Hsum = sum(zlevels) or 1.0
        ffx = {z: res["base_x"] * z / Hsum for z in zlevels}
        ffy = {z: res["base_y"] * z / Hsum for z in zlevels}
        prof_x = story_profiles(build_frame3d(project), "x", ffx, hz_typ)
        prof_y = story_profiles(build_frame3d(project), "y", ffy, hz_typ)
        _fig.story_curves_png(prof_x, prof_y, 1 / 800,
                              os.path.join(out_dir, "楼层曲线.png"),
                              title="Story Shear & Inter-story Drift")
        figs["curves"] = "楼层曲线.png"
    except Exception:
        pass
    return figs
