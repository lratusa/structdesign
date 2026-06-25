"""
真三维构件配筋 demo —— 柱双向偏压 + 墙肢三维内力 + CQC 振型组合。

(a) 三维双向地震分析(X/Y两工况)→ 各柱取 N,My,Mz(0.85双向组合)→ 双偏压配筋；
    墙肢取三维 N、面内 M → 墙配筋。
(b) CQC 组合：用本楼平动/扭转周期，演示 CQC 比 SRSS 更准(扭转耦联放大边榀响应)。
运行：python demo_3d_design.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from structdesign.frame3d_builder import build_regular_3d, floor_masses
from structdesign.analysis.frame3d import member_forces, solve, Load3D
from structdesign.analysis.modal3d import rigid_diaphragm_modal
from structdesign.codes.gb50010_column import design_column_biaxial
from structdesign.codes import gb50010_wall as gw
from structdesign.codes.seismic_torsion import bidirectional_combination
from structdesign.codes.cqc import cqc, srss
from structdesign import rebar as rb


def lateral_forces(model, direction, F):
    tops = [nid for nid, n in model.nodes.items() if n.z > 0]
    for nid in tops:
        model.add_load(Load3D(nid, fx=(F if direction == "x" else 0),
                              fy=(F if direction == "y" else 0)))


def main():
    nx, ny, nz = 3, 3, 12
    bx = by = 8000.0
    walls = {(1, 1), (1, 2), (2, 1), (2, 2)}
    def build():
        return build_regular_3d(nx, ny, nz, bx, by, 3600, col_bh=(700, 700),
                                beam_bh=(350, 700), wall_cols=walls, wall_bh=(400, 4000))

    # 三个工况：重力(竖向)、X地震、Y地震（等效静力，简化）
    mg = build()
    for nid, n in mg.nodes.items():
        if n.z > 0:
            mg.add_load(Load3D(nid, fz=-200e3))
    fG = member_forces(mg)
    mx = build(); lateral_forces(mx, "x", 30e3); fX = member_forces(mx)
    my = build(); lateral_forces(my, "y", 30e3); fY = member_forces(my)

    print("=" * 60)
    print("(a) 三维构件配筋：柱双向偏压 + 墙肢三维内力")
    print("=" * 60)
    # 取一根角柱 与 一片墙
    col_id = "Z0_0_1"   # 角柱底层
    g, x, y = fG[col_id], fX[col_id], fY[col_id]
    N = abs(g["N"]) / 1e3
    My = bidirectional_combination(x["My"], y["My"]) / 1e6
    Mz = bidirectional_combination(x["Mz"], y["Mz"]) / 1e6
    bi = design_column_biaxial(700, 700, N, Mz, My, "C40", "HRB400")
    bars = rb.select_bars(bi.As_total / 4, 700)
    print(f"  角柱 {col_id}: N={N:.0f}kN  Mx={Mz:.0f}  My={My:.0f} kN·m")
    print(f"    双偏压配筋 As={bi.As_total:.0f}mm²(ρ={bi.rho*100:.2f}%)  "
          f"四角每边~{bars.label()}  (单偏压基线 As0={bi.As0:.0f})")

    wall_id = "Z1_1_1"
    gw_, xw, yw = fG[wall_id], fX[wall_id], fY[wall_id]
    Nw = abs(gw_["N"]) / 1e3
    Mw = bidirectional_combination(xw["Mz"], yw["Mz"]) / 1e6
    mu = gw.wall_axial_ratio(Nw, 400, 4000, "C40")
    reinf = gw.design_wall_reinforcement(Nw, 400, 4000, "C40", "HRB400", "二级")
    print(f"  墙肢 {wall_id}: N={Nw:.0f}kN  面内M={Mw:.0f}kN·m  μN={mu:.2f}")
    print(f"    竖向分布筋 {reinf.vert_dist}；边缘构件 {reinf.be_bars}")

    print("\n" + "=" * 60)
    print("(b) CQC 振型组合 vs SRSS（扭转耦联）")
    print("=" * 60)
    r = rigid_diaphragm_modal(build(), floor_masses(build(), 9e5))
    # 取平动主振型与第一扭转振型(周期接近)，假设边榀对二者响应同量级
    T_tr, T_to = r.Tx, r.Tt
    resp = [100.0, 60.0]    # 边榀对[平动,扭转]的代表响应
    Ts = [T_tr, T_to]
    print(f"  平动周期 {T_tr:.3f}s, 扭转周期 {T_to:.3f}s (相近→强相关)")
    print(f"  边榀响应 SRSS={srss(resp):.1f}  CQC={cqc(resp, Ts):.1f}  "
          f"→ CQC 比 SRSS 大 {(cqc(resp,Ts)/srss(resp)-1)*100:.0f}%（扭转耦联被正确放大）")
    print("\nSRSS 假设振型独立，对平动-扭转相近的情形低估边榀内力；CQC 更准——三维必备。")


if __name__ == "__main__":
    main()
