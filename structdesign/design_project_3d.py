"""
三维一键总流程 —— 读参数 → 三维分析 → 配筋 → 三维计算书。

串通：3D刚性楼盖模态(周期比) + 逐振型反应谱CQC(双向地震) + 位移比 + 层间位移角
→ 柱双偏压 + 墙肢三维配筋 → 三维计算书 + 轴测可视化。
说明：刚性楼盖假定、未做弹性楼板面外；高层最终须商业三维软件复核+注册工程师签字。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Set, Tuple
import os

from . import loads_takedown as td
from . import rebar as rb
from .frame3d_builder import build_regular_3d, floor_masses
from .analysis.frame3d import member_forces, Load3D
from .analysis.rspectrum3d import response_spectrum_3d
from .analysis.drift3d import displacement_ratio, story_drift_ratio
from .codes.gb50010_column import design_column_biaxial, axial_compression_ratio, column_min_reinforcement
from .codes import gb50010_wall as gw
from .drawing.iso3d import save_svg


@dataclass
class Project3DResult:
    Tx: float; Ty: float; Tt: float; period_ratio: float
    base_x: float; base_y: float; shear_weight: float
    disp_ratio_x: float; disp_ratio_y: float
    drift_x: float
    n_members: int; n_bad: int; total_steel_t: float
    checks: dict = field(default_factory=dict)
    files: dict = field(default_factory=dict)


def design_project_3d(nx, ny, nz, bx, by, hz, out_dir,
                      col_bh=(700, 700), beam_bh=(350, 700),
                      wall_cols: Set[Tuple[int, int]] = None, wall_bh=(400, 4000),
                      dead_kpa=6.0, live_kpa=2.5, alpha_max=0.16, Tg=0.45,
                      seismic_grade="二级", n_modes=12) -> Project3DResult:
    os.makedirs(out_dir, exist_ok=True)
    wall_cols = wall_cols or set()
    q = td.slab_q(dead_kpa, live_kpa)
    mass = (dead_kpa + 0.5 * live_kpa) * (nx*bx/1000) * (ny*by/1000) * 100  # kg/floor 估算
    mass = max(mass, 3e5)

    def build():
        return build_regular_3d(nx, ny, nz, bx, by, hz, col_bh=col_bh, beam_bh=beam_bh,
                                wall_cols=wall_cols, wall_bh=wall_bh)

    # 重力轴力
    mg = build()
    w_node = q * (bx/1000) * (by/1000) * 1000 / 4   # 简化节点竖向力(N)
    for nid, n in mg.nodes.items():
        if n.z > 0:
            mg.add_load(Load3D(nid, fz=-w_node))
    fG = member_forces(mg)

    # 三维反应谱(CQC)
    res = response_spectrum_3d(build(), floor_masses(build(), mass), alpha_max, Tg, n_modes=n_modes)
    r = res["modal"]
    W = nz * mass * 9.81
    drx = displacement_ratio(build(), "x")
    dry = displacement_ratio(build(), "y")
    drift_x = story_drift_ratio(build(), "x", hz, F=res["base_x"]/(nz*(nx+1)*(ny+1)))

    # 配筋（柱双偏压 / 墙肢三维内力 / 梁受弯）
    from .codes import gb50010_beam as gb
    from .report import calcbook_pro
    mf = res["member_forces"]
    model = build()
    n_bad = 0; steel = 0.0
    members = []
    for mid, m in model.members.items():
        My = mf[mid]["My"] / 1e6; Mz = mf[mid]["Mz"] / 1e6
        N = abs(fG[mid]["N"]) / 1e3
        if mid.startswith("Z"):
            is_wall = max(m.Iy, m.Iz) > 5e10
            if is_wall:
                mu = gw.wall_axial_ratio(N, wall_bh[0], wall_bh[1], "C40")
                reinf = gw.design_wall_reinforcement(N, wall_bh[0], wall_bh[1], "C40", "HRB400", seismic_grade)
                ok = mu <= gw.wall_axial_limit(seismic_grade)
                steel += reinf.be_As * 2 * (hz/1000) * 7.85e-6 * 1000
                members.append(dict(id=mid, kind="墙", sec=f"{wall_bh[0]}×{wall_bh[1]}",
                                    N=N, M=max(My, Mz), Mx=Mz, My=My, mu=mu,
                                    bars=reinf.be_bars, vdist=reinf.vert_dist, rho=0.0, ok=ok))
            else:
                bi = design_column_biaxial(col_bh[0], col_bh[1], N, Mz, My, "C40", "HRB400")
                As_min, _ = column_min_reinforcement(col_bh[0], col_bh[1], seismic_grade)
                As_col = max(bi.As_total, As_min)        # 计入最小配筋率
                rho = As_col / (col_bh[0] * col_bh[1])
                mu, lim, aok = axial_compression_ratio(N, col_bh[0], col_bh[1], "C40", seismic_grade)
                ok = aok and rho <= 0.05
                steel += As_col * (hz/1000) * 7.85e-6 * 1000
                bars = rb.select_bars(As_col/4, col_bh[0])
                members.append(dict(id=mid, kind="柱", sec=f"{col_bh[0]}×{col_bh[1]}",
                                    N=N, Mx=Mz, My=My, M=max(My, Mz), mu=mu,
                                    bars=f"4×{bars.label()}", rho=rho, ok=ok))
            n_bad += 0 if ok else 1
        elif mid.startswith("L"):
            # 梁：重力 + 地震弯矩包络
            Mg = abs(fG[mid]["Mz"]) / 1e6
            Mb = max(Mg, Mg + Mz)
            fl = gb.design_flexure(beam_bh[0], beam_bh[1], Mb, "C30", "HRB400", a_s=40)
            As_min, _ = gb.min_tension_area(beam_bh[0], beam_bh[1], "C30", "HRB400")
            As = max(fl.As, As_min)
            bars = rb.select_bars(As, beam_bh[0])
            ok = fl.ok and As/(beam_bh[0]*(beam_bh[1]-40)) <= 0.025
            # 梁纵筋不计入竖向构件用钢汇总
            members.append(dict(id=mid, kind="梁", sec=f"{beam_bh[0]}×{beam_bh[1]}",
                                N=0, M=Mb, As=As, bars=bars.label(), ok=ok))

    n_vert = len([m for m in members if m["kind"] in ("柱", "墙")])
    checks = {
        "周期比 Tt/T1≤0.90": (r.period_ratio, r.period_ratio <= 0.90),
        "位移比 X≤1.2": (drx, drx <= 1.2),
        "位移比 Y≤1.2": (dry, dry <= 1.2),
        "剪重比": (res["base_x"]/W, 0.016 <= res["base_x"]/W),
        "层间位移角 X≤1/800": (drift_x, drift_x <= 1/800),
    }
    out = Project3DResult(
        Tx=r.Tx, Ty=r.Ty, Tt=r.Tt, period_ratio=r.period_ratio,
        base_x=res["base_x"], base_y=res["base_y"], shear_weight=res["base_x"]/W,
        disp_ratio_x=drx, disp_ratio_y=dry, drift_x=drift_x,
        n_members=n_vert, n_bad=sum(0 if m["ok"] else 1 for m in members),
        total_steel_t=steel/1000, checks=checks)

    # 专业计算书数据
    checks_table = [
        ("周期比 Tt/T1", f"{r.period_ratio:.3f}", "≤0.90", r.period_ratio <= 0.90),
        ("位移比(X)", f"{drx:.2f}", "≤1.2", drx <= 1.2),
        ("位移比(Y)", f"{dry:.2f}", "≤1.2", dry <= 1.2),
        ("剪重比", f"{res['base_x']/W*100:.2f}%", "≥1.6%", res['base_x']/W >= 0.016),
        ("最大层间位移角", f"1/{1/max(drift_x,1e-9):.0f}", "≤1/800", drift_x <= 1/800),
    ]
    book_data = dict(
        version="0.17",
        project=dict(name=f"{nx}×{ny}跨×{nz}层 框架-剪力墙", type="多层/高层钢筋混凝土框架-剪力墙结构",
                     system="框架-剪力墙（钢筋混凝土）", nx=nx, ny=ny, nz=nz, bx=bx, by=by, hz=hz,
                     n_walls=len(wall_cols), concrete_col="C40", concrete_beam="C30",
                     dead=dead_kpa, live=live_kpa, seismic_grade=seismic_grade),
        codes=["《建筑结构荷载规范》GB 50009-2012",
               "《混凝土结构设计规范》GB 50010-2010(2015年版)",
               "《建筑抗震设计规范》GB 50011-2010(2016年版)",
               "《高层建筑混凝土结构技术规程》JGJ 3-2010",
               "《建筑地基基础设计规范》GB 50007-2011"],
        seismic=dict(alpha_max=alpha_max, Tg=Tg, zeta=0.05, mass=mass,
                     Tx=r.Tx, Ty=r.Ty, Tt=r.Tt, period_ratio=r.period_ratio,
                     base_x=res["base_x"], base_y=res["base_y"], base_bi=res["base_bi"],
                     shear_weight=res["base_x"]/W, disp_ratio_x=drx, disp_ratio_y=dry),
        modes=[(m.period, m.kind) for m in r.modes],
        drift=drift_x, stability=None, members=members,
        checks_table=checks_table, steel_t=steel/1000,
    )

    # 插图（轴测图 + 代表柱配筋大样）
    from .drawing import figures as _fig
    figs = {}
    try:
        _fig.axon_png(build(), os.path.join(out_dir, "三维模型图.png"),
                      title=f"{nx}x{ny}bay x {nz}F  Frame-Wall")
        figs["model"] = "三维模型图.png"
        rep_col = next((m for m in members if m["kind"] == "柱"), None)
        if rep_col:
            cb_bars = rb.select_bars(0.012*col_bh[0]*col_bh[1]/4, col_bh[0])
            _fig.section_png(col_bh[0], col_bh[1], cb_bars.n, cb_bars.n, cb_bars.d, 10,
                             os.path.join(out_dir, "柱大样.png"),
                             title=f"Column {rep_col['id']}", n_side=2)
            figs["col_section"] = "柱大样.png"
        # 楼层结构平面简图
        _fig.floor_plan_png(nx, ny, bx, by, wall_cols, col_bh[0], wall_bh[1],
                            os.path.join(out_dir, "平面简图.png"),
                            title=f"Structural Floor Plan ({nx}x{ny} bays)")
        figs["plan"] = "平面简图.png"
        # 墙肢配筋大样
        if wall_cols:
            _fig.wall_section_png(wall_bh[0], wall_bh[1], 25, 6, 8,
                                  os.path.join(out_dir, "墙大样.png"), title="Shear Wall")
            figs["wall_section"] = "墙大样.png"
        # 楼层剪力/位移角分布曲线（基底剪力按倒三角 Fi∝Hi 分配，GB 50011 5.2.1）
        from .analysis.drift3d import story_profiles
        zlevels = sorted({round(n.z, 3) for n in build().nodes.values() if n.z > 1e-6})
        Hsum = sum(zlevels) or 1.0
        ffx = {z: res["base_x"] * z / Hsum for z in zlevels}
        ffy = {z: res["base_y"] * z / Hsum for z in zlevels}
        prof_x = story_profiles(build(), "x", ffx, hz)
        prof_y = story_profiles(build(), "y", ffy, hz)
        _fig.story_curves_png(prof_x, prof_y, 1/800,
                              os.path.join(out_dir, "楼层曲线.png"),
                              title="Story Shear & Inter-story Drift")
        figs["curves"] = "楼层曲线.png"
    except Exception:
        pass
    book_data["figures"] = figs
    cb = os.path.join(out_dir, "三维计算书.md")
    with open(cb, "w", encoding="utf-8") as f:
        f.write(calcbook_pro.render(book_data))
    out.files["三维计算书_md"] = cb
    # 专业 Word 版（pandoc 转换；无 pandoc 时跳过）
    import shutil as _sh, subprocess as _sp
    if _sh.which("pandoc"):
        try:
            # 在 out_dir 内运行，使相对图片路径可解析并嵌入 Word
            _sp.run(["pandoc", os.path.basename(cb), "-o", "三维计算书.docx"],
                    check=True, capture_output=True, cwd=out_dir)
            out.files["三维计算书_docx"] = os.path.join(out_dir, "三维计算书.docx")
        except Exception:
            pass
    out.files["三维模型_svg"] = save_svg(os.path.join(out_dir, "三维模型.svg"),
                                       model=build(), title=f"{nx}×{ny}跨×{nz}层 三维模型")
    out._book_data = book_data
    return out


if __name__ == "__main__":
    pass
