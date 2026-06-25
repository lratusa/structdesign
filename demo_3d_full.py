"""
三维设计主线 + 可视化 demo。

(a) 刚性楼盖三维模态 → X/Y 平动周期 + 扭转周期 + 周期比(规范≤0.9) + 双向反应谱基底剪力。
(b) 三维模型轴测可视化（含侧移变形）。
运行：python demo_3d_full.py → 生成 三维模型.svg / 三维变形.svg
"""
import os
import sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from structdesign.frame3d_builder import build_regular_3d, floor_masses
from structdesign.analysis.modal3d import rigid_diaphragm_modal
from structdesign.analysis.frame3d import solve, Load3D
from structdesign.codes import gb50011_spectrum as sp
from structdesign.codes.seismic_torsion import bidirectional_combination
from structdesign.drawing.iso3d import save_svg

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    nx, ny, nz = 3, 3, 12
    bx = by = 8000.0
    hz = 3600.0
    mass = 9e5
    # 框架-核心：中间 2×2 柱列设墙(角部核心)
    walls = {(1, 1), (1, 2), (2, 1), (2, 2)}
    m = build_regular_3d(nx, ny, nz, bx, by, hz, col_bh=(700, 700),
                         beam_bh=(350, 700), wall_cols=walls, wall_bh=(400, 4000))
    fm = floor_masses(m, mass)
    r = rigid_diaphragm_modal(m, fm)

    alpha_max, Tg = 0.16, 0.45
    Vx = sp.alpha(r.Tx, alpha_max, Tg) * (mass * 9.81 * nz) * 0.85   # 简化基底剪力(主振型)
    Vy = sp.alpha(r.Ty, alpha_max, Tg) * (mass * 9.81 * nz) * 0.85
    Vbi = bidirectional_combination(Vx, Vy)

    print("=" * 60)
    print(f"三维框架-核心 {nx}×{ny}跨 × {nz}层（中部核心墙）")
    print("=" * 60)
    print(f"  Tx={r.Tx:.3f}s  Ty={r.Ty:.3f}s  Tt(扭转)={r.Tt:.3f}s")
    print(f"  周期比 Tt/T1 = {r.period_ratio:.3f}  (规范≤0.90) "
          f"→ {'✔满足' if r.period_ratio <= 0.9 else '✗超限(扭转偏大,需加强周边)'}")
    print(f"  双向反应谱基底剪力: Vx={Vx/1e3:.0f}kN Vy={Vy/1e3:.0f}kN 组合={Vbi/1e3:.0f}kN")
    print("  前 6 阶振型：")
    for md in r.modes[:6]:
        print(f"    T={md.period:.3f}s  {md.kind}")

    # (b) 可视化：无变形 + 侧移变形(顶层施加 X 力)
    save_svg(os.path.join(HERE, "三维模型.svg"), model=m, title="三维框架-核心模型")
    m2 = build_regular_3d(nx, ny, nz, bx, by, hz, col_bh=(700, 700),
                          beam_bh=(350, 700), wall_cols=walls, wall_bh=(400, 4000))
    tops = [nid for nid, n in m2.nodes.items() if abs(n.z - nz*hz) < 1]
    for nid in tops:
        m2.add_load(Load3D(nid, fx=200e3))
    U, _ = solve(m2)
    defo = {nid: list(U[nid][:3]) for nid in U}
    save_svg(os.path.join(HERE, "三维变形.svg"), model=m2, deformed=defo, mag=80,
             title="三维模型侧移变形(X向)")
    print("\n  已生成 三维模型.svg / 三维变形.svg")
    print("\n这是把三维引擎接进设计主线：刚性楼盖模态→周期比/双向地震，2D 无法给出这些指标。")


if __name__ == "__main__":
    main()
