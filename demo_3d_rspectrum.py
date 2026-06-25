"""
真三维振型分解反应谱 → 逐振型 CQC → 双偏压配筋（全自动）。

完整链路：3D刚性楼盖模态 → 逐振型等效力解3D构件内力 → CQC组合 → 双向0.85 →
柱双偏压配筋 + 墙肢三维配筋。这是把三维分析真正"算到配筋"。
运行：python demo_3d_rspectrum.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from structdesign.frame3d_builder import build_regular_3d, floor_masses
from structdesign.analysis.frame3d import member_forces, Load3D
from structdesign.analysis.rspectrum3d import response_spectrum_3d
from structdesign.codes.gb50010_column import design_column_biaxial, axial_compression_ratio
from structdesign.codes import gb50010_wall as gw
from structdesign import rebar as rb


def main():
    nx, ny, nz = 3, 2, 10
    walls = {(1, 1)}
    cb, wb = (650, 650), (400, 3500)

    def build():
        return build_regular_3d(nx, ny, nz, 8000, 7000, 3600, col_bh=cb,
                                beam_bh=(350, 700), wall_cols=walls, wall_bh=wb)

    # 重力轴力
    mg = build()
    for nid, n in mg.nodes.items():
        if n.z > 0:
            mg.add_load(Load3D(nid, fz=-180e3))
    fG = member_forces(mg)

    # 三维反应谱(逐振型→CQC→双向)
    res = response_spectrum_3d(build(), floor_masses(build(), 7e5), 0.16, 0.40, n_modes=12)
    r = res["modal"]
    W = nz * 7e5 * 9.81

    print("=" * 64)
    print(f"真三维抗震设计 {nx}×{ny}跨×{nz}层（含核心墙）逐振型CQC")
    print("=" * 64)
    print(f"  Tx={r.Tx:.2f}s Ty={r.Ty:.2f}s Tt={r.Tt:.2f}s 周期比={r.period_ratio:.3f}"
          f" {'✔' if r.period_ratio<=0.9 else '✗'}")
    print(f"  基底剪力(CQC) Vx={res['base_x']/1e3:.0f} Vy={res['base_y']/1e3:.0f} kN"
          f"  双向={res['base_bi']/1e3:.0f}kN 剪重比={res['base_x']/W*100:.2f}%")

    mf = res["member_forces"]
    print("\n  底层构件双偏压/墙配筋（N自重力，M自CQC双向地震）：")
    n_bad = 0
    total_As = 0.0
    for mid in [m for m in mf if m.endswith("_1")][:6]:
        N = abs(fG[mid]["N"]) / 1e3
        My = mf[mid]["My"] / 1e6
        Mz = mf[mid]["Mz"] / 1e6
        is_wall = max_iy(build(), mid)
        if is_wall:
            mu = gw.wall_axial_ratio(N, wb[0], wb[1], "C40")
            reinf = gw.design_wall_reinforcement(N, wb[0], wb[1], "C40", "HRB400", "二级")
            ok = mu <= gw.wall_axial_limit("二级")
            print(f"    墙 {mid}: N={N:.0f}kN 面内M={max(My,Mz):.0f} μN={mu:.2f} "
                  f"竖筋{reinf.vert_dist} 边缘{reinf.be_bars} {'✔' if ok else '✗'}")
            n_bad += 0 if ok else 1
        else:
            bi = design_column_biaxial(cb[0], cb[1], N, Mz, My, "C40", "HRB400")
            mu, lim, aok = axial_compression_ratio(N, cb[0], cb[1], "C40", "二级")
            bars = rb.select_bars(bi.As_total/4, cb[0])
            ok = aok and bi.rho <= 0.05
            total_As += bi.As_total
            print(f"    柱 {mid}: N={N:.0f}kN Mx={Mz:.0f} My={My:.0f} → As={bi.As_total:.0f}"
                  f"(ρ={bi.rho*100:.1f}%) 每角~{bars.label()} μN={mu:.2f} {'✔' if ok else '✗'}")
            n_bad += 0 if ok else 1

    print(f"\n  本批 {'全部满足' if n_bad==0 else f'{n_bad}个不足'}")
    print("\n这是三维分析真正算到配筋：逐振型→CQC(考虑扭转耦联)→双向→柱双偏压。2D 无此能力。")


def max_iy(model, mid):
    m = model.members[mid]
    return max(m.Iy, m.Iz) > 5e10


if __name__ == "__main__":
    main()
